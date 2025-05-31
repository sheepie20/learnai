import os
import json
import asyncio
import aiohttp
import tiktoken
import re
import google.generativeai as genai
from typing import Optional, List, Dict
from dotenv import load_dotenv
from youtube import fetch_transcript



load_dotenv()

# Configure Google Generative AI with API key
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

tokenizer = tiktoken.get_encoding("cl100k_base")

def split_by_tokens(text: str, max_tokens_per_chunk: int = 2000, model: str = "gpt-3.5-turbo") -> list[str]:
    encoding = tiktoken.encoding_for_model(model)
    tokens = encoding.encode(text)

    chunks = []
    for i in range(0, len(tokens), max_tokens_per_chunk):
        chunk_tokens = tokens[i:i + max_tokens_per_chunk]
        chunk_text = encoding.decode(chunk_tokens)
        chunks.append(chunk_text)

    return chunks

class NotePolisher:
    def __init__(self):
        self.system_message = (
            "You are a professional educational writer. "
            "Polish the given notes to make them clearer, easier to understand, and well-organized. "
            "Do not skip or remove information—just improve phrasing, structure, and flow. "
            "Make it friendly for students while keeping it accurate and complete."
            "Do NOT send anything else but the notes. Do not say anything like \"Notes:\" or \"Okay, here are the polished notes:\""
            "Use Markdown Formatting"
        )
        # Use Gemini Pro model
        self.model = genai.GenerativeModel('models/gemini-2.5-flash-preview-05-20')

    async def polish_notes(self, raw_notes: str) -> str:
        try:
            # Create the prompt with system message and user content
            prompt = f"{self.system_message}\n\nNotes to polish:\n{raw_notes}"
            
            # Call Gemini API asynchronously
            response = await asyncio.to_thread(
                self.model.generate_content,
                prompt,
                generation_config={
                    "temperature": 0.7,
                    "max_output_tokens": 4096,
                }
            )
            
            print("Received response from Gemini API - polishing notes")
            return response.text
        except Exception as e:
            print(f"Error with Gemini API: {e}")
            raise

class NoteTaker:
    def __init__(self):
        self.default_system_message = (
            "Take detailed and comprehensive notes on everything given to you. "
            "Explain everything clearly and in great detail. You will receive transcripts of YouTube videos. "
            "Only include the notes. Take notes on EVERY ASPECT of the transcript. Do not miss one. "
            "Don't include \"[\" or \"]\" at all in the notes."
        )
        # Use Gemini Pro model
        self.model = genai.GenerativeModel('models/gemini-2.5-flash-preview-05-20')

    def _preprocess_text(self, text: str) -> str:
        print("Preprocessing text")
        text = re.sub(r'\n\s*\n', '\n\n', text)
        text = re.sub(r'(?<!\n)\n(?!\n)', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    async def _call_model(self, chunk: str) -> str:
        try:
            # Create the prompt with system message and user content
            prompt = f"{self.default_system_message}\n\nContent to take notes on:\n{chunk}"
            
            # Call Gemini API asynchronously
            response = await asyncio.to_thread(
                self.model.generate_content,
                prompt,
                generation_config={
                    "temperature": 0.7,
                    "max_output_tokens": 8120,
                }
            )
            
            print("Received response from Gemini API - generating notes")
            return response.text
        except Exception as e:
            print(f"Error with Gemini API: {e}")
            raise

    async def generate_notes(self, text: str) -> str:
        print("Generating notes")
        text = self._preprocess_text(text)
        
        # Split text into chunks
        chunks = split_by_tokens(text, max_tokens_per_chunk=4000, model="gpt-3.5-turbo")
        print(f"Split text into {len(chunks)} chunks")
        
        # Process each chunk
        notes_chunks = []
        for i, chunk in enumerate(chunks):
            print(f"Processing chunk {i+1}/{len(chunks)}")
            chunk_notes = await self._call_model(chunk)
            notes_chunks.append(chunk_notes)
        
        # Combine notes
        combined_notes = "\n\n".join(notes_chunks)
        
        # Polish notes if there are multiple chunks
        if len(chunks) > 1:
            print("Polishing combined notes")
            polisher = NotePolisher()
            combined_notes = await polisher.polish_notes(combined_notes)
        
        return combined_notes

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
        # Use Gemini Pro model
        self.model = genai.GenerativeModel('models/gemini-2.5-flash-preview-05-20')

    def _clean_latex(self, text: str) -> str:
        """Clean LaTeX notation to make it JSON-safe"""
        # No need to escape LaTeX backslashes anymore
        return text

    async def generate_quiz(self, notes: str) -> dict:
        print(f"Generating quiz")
        try:
            # Create the prompt with system message and notes
            prompt = f"{self.system_message}\n\nNotes to generate quiz from:\n{notes}"
            
            # Call Gemini API asynchronously
            response = await asyncio.to_thread(
                self.model.generate_content,
                prompt,
                generation_config={
                    "temperature": 0.7,
                    "max_output_tokens": 8120,
                }
            )
            
            print("Received response from Gemini API - generating quiz")
            content = response.text
            
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
        except Exception as e:
            print(f"Error with Gemini API: {e}")
            raise
class ChatBot:
    def __init__(self, notes: str):
        self.system_message = f"""You are a helpful study assistant.\n\nPlease answer questions using only the information in the notes below:\n---\n{notes}\n---\n\nFormatting instructions:\n- Avoid using LaTeX or math formatting unless absolutely necessary.\n- If you must include math, use plain text and keep it simple.\n- Use Markdown for code, lists, and tables only if it improves clarity.\n\nIf you're not sure about the answer, it's okay to say "I don't know."\nIf the question is unrelated to the notes, just let me know that it's outside the scope."""
        self.history: List[Dict[str, str]] = []  # List of {role: 'user'/'assistant', content: str}
        # Use Gemini Pro model
        self.model = genai.GenerativeModel('models/gemini-2.5-flash-preview-05-20')

    def add_user_message(self, message: str):
        self.history.append({"role": "user", "content": message})

    def add_assistant_message(self, message: str):
        self.history.append({"role": "assistant", "content": message})

    async def chat(self, question: str) -> str:
        self.add_user_message(question)
        
        try:
            # Prepare full prompt with system message and conversation history
            full_prompt = self.system_message + "\n\nConversation History:\n"
            
            for msg in self.history:
                role = "User" if msg["role"] == "user" else "Assistant"
                full_prompt += f"\n{role}: {msg['content']}"
            
            # Call Gemini API asynchronously
            response = await asyncio.to_thread(
                self.model.generate_content,
                full_prompt,
                generation_config={
                    "temperature": 0.7,
                    "max_output_tokens": 8120,
                }
            )
            
            if not response.text:
                raise Exception("Empty response from Gemini API")
                
            ai_message = response.text
            self.add_assistant_message(ai_message)
            return ai_message
            
        except Exception as e:
            print(f"[ChatBot ERROR] Failed to get response: {e}")
            return "Sorry, I couldn't get a response from the AI service. Please try again later."
