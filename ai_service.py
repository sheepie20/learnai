from together import Together
from typing import Optional, List, Dict
from dotenv import load_dotenv
import re
from youtube import fetch_transcript
import aiohttp
import asyncio
import json
import os

load_dotenv()

class NoteTaker:
    def __init__(self):
        self.api_key = os.getenv("TOGETHER_API_KEY")
        self.api_url = "https://api.together.xyz/v1/chat/completions"
        self.default_system_message = """Take detailed and comprehensive notes on everything given to you. 
        Explain everything clearly and in great detail. You will receive transcripts of YouTube videos. 
        Only include the notes. Take notes on EVERY ASPECT of the transcript. Do not miss one. Don't include \"[\" or \"]\" at all in the notes."""

    def _preprocess_text(self, text: str) -> str:
        print(f"Preprocessing text")
        # Replace multiple newlines with a single newline to preserve paragraph breaks
        text = re.sub(r'\n\s*\n', '\n\n', text)
        # Replace single newlines with spaces
        text = re.sub(r'(?<!\n)\n(?!\n)', ' ', text)
        # Remove any extra whitespace
        text = re.sub(r'\s+', ' ', text)
        # Clean up the final text
        return text.strip()

    async def generate_notes(self, text: str) -> str:
        print(f"Generating notes from text")
        # Preprocess the text before sending to the API
        cleaned_text = self._preprocess_text(text)
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.api_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "deepseek-ai/DeepSeek-V3",
                    "messages": [
                        {
                            "role": "system",
                            "content": self.default_system_message
                        },
                        {
                            "role": "user",
                            "content": cleaned_text
                        }
                    ],
                    "max_tokens": 4096,
                    "temperature": 0.7
                }
            ) as response:
                result = await response.json()
                return result["choices"][0]["message"]["content"]

class TranscriptionService:
    async def transcribe(self, url: str) -> str:
        """
        Download and transcribe audio from a YouTube URL.
        
        Args:
            url: YouTube URL to transcribe
            
        Returns:
            The transcribed text
        """
        return await fetch_transcript(url)

class QuizGenerator:
    def __init__(self):
        self.api_key = os.getenv("TOGETHER_API_KEY")
        self.api_url = "https://api.together.xyz/v1/chat/completions"
        self.system_message = """You are a quiz generator. Generate 10 multiple choice questions based on the provided notes. Yes, make them based on the notes, but make them original and don't copy examples or questions from the notes.
        Each question should have 4 options (A, B, C, D) and include the correct answer. Format your response as a JSON array 
        with each question object containing: question_text, options (A through D), and correct_answer (A, B, C, or D).
        
        Question Quality Requirements:
        - Make questions challenging but fair
        - Avoid similar questions
        - Avoid obvious answers
        - Keep questions concise
        - Ensure all options are plausible
        
        Mathematical Notation:
        When including mathematical expressions:
        1. Use standard LaTeX notation wrapped in $ signs for inline math
        2. For example: "What is the derivative of $x^2 + 2x + 1$?"
        3. Do not escape any LaTeX characters in the expressions
        4. Use single $ for inline math, $$ for display math
        
        Example Response Format:
        {
        "questions": [
            {
            "question_text": "What is the derivative of $x^2 + 2x + 1$?",
            "options": {
                "A": "$2x + 2$",
                "B": "$x^2 + 2$",
                "C": "$2x$",
                "D": "$x + 1$"
            },
            "correct_answer": "A"
            },
            // ... nine more questions
        ]
        }
        """

    def _clean_latex(self, text: str) -> str:
        """Clean LaTeX notation to make it JSON-safe"""
        # No need to escape LaTeX backslashes anymore
        return text

    async def generate_quiz(self, notes: str) -> dict:
        print(f"Generating quiz")
        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.api_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "deepseek-ai/DeepSeek-V3",
                    "messages": [
                        {
                            "role": "system",
                            "content": self.system_message
                        },
                        {
                            "role": "user",
                            "content": notes
                        }
                    ],
                    "max_tokens": 4096,
                    "temperature": 0.7
                }
            ) as response:
                result = await response.json()
                content = result["choices"][0]["message"]["content"]
                
                # Extract JSON from markdown code block if present
                json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
                if json_match:
                    content = json_match.group(1)

                # Clean LaTeX notation in the content
                content = self._clean_latex(content)

                # Parse the response content as JSON
                try:
                    quiz_data = json.loads(content)
                    
                    # Validate the quiz structure
                    if not isinstance(quiz_data, dict) or 'questions' not in quiz_data:
                        raise Exception("Invalid quiz format: missing questions array")
                    
                    questions = quiz_data['questions']
                    if not isinstance(questions, list):
                        raise Exception("Invalid quiz format: questions must be an array")
                    
                    if len(questions) != 10:
                        raise Exception(f"Expected 10 questions, got {len(questions)}")
                    
                    # Validate each question's format
                    for i, q in enumerate(questions):
                        if not all(k in q for k in ('question_text', 'options', 'correct_answer')):
                            raise Exception(f"Question {i+1}: missing required fields")
                        if not all(k in q['options'] for k in ('A', 'B', 'C', 'D')):
                            raise Exception(f"Question {i+1}: missing one or more options")
                        if q['correct_answer'] not in ('A', 'B', 'C', 'D'):
                            raise Exception(f"Question {i+1}: invalid correct_answer '{q['correct_answer']}'")
                    
                    return quiz_data
                except json.JSONDecodeError as e:
                    raise Exception("Failed to generate valid quiz questions: JSON parsing error") from e
                except Exception as e:
                    raise Exception(f"Failed to generate valid quiz questions: {str(e)}")
                
class ChatBot:
    def __init__(self, notes: str):
        self.api_key = os.getenv("TOGETHER_API_KEY")
        self.api_url = "https://api.together.xyz/v1/chat/completions"
        self.system_message = f"""You are a helpful study assistant.
Please answer questions using only the information in the notes below:
---
{notes}
---
If you’re not sure about the answer, it’s okay to say “I don’t know.”
If the question is unrelated to the notes, just let me know that it’s outside the scope."""
        self.history: List[Dict[str, str]] = []  # List of {role: 'user'/'assistant', content: str}

    def add_user_message(self, message: str):
        self.history.append({"role": "user", "content": message})

    def add_assistant_message(self, message: str):
        self.history.append({"role": "assistant", "content": message})

    async def chat(self, question: str) -> str:
        self.add_user_message(question)
        messages = [
            {"role": "system", "content": self.system_message}
        ] + self.history
        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.api_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "deepseek-ai/DeepSeek-V3",
                    "messages": messages,
                    "max_tokens": 1024,
                    "temperature": 0.7
                }
            ) as response:
                result = await response.json()
                ai_message = result["choices"][0]["message"]["content"]
                self.add_assistant_message(ai_message)
                return ai_message
