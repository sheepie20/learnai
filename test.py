from openai import OpenAI
from dotenv import load_dotenv
import time

load_dotenv()
import os 
SCW_SECRET_KEY = os.getenv("SCW_SECRET_KEY")

client = OpenAI(
    base_url = "https://api.scaleway.ai/081a7467-24a7-41ae-b329-add54b3d9831/v1",
    api_key = SCW_SECRET_KEY,
)

def get_response():
    response = client.chat.completions.create(
        model="deepseek-r1-distill-llama-70b",
        messages=[
            { "role": "system", "content": """You are a notes generator. Take detailed and comprehensive notes on everything given to you. 
    Explain everything clearly and in great detail. You will receive transcripts of YouTube videos. 
    Only include the notes. Take notes on EVERY ASPECT of the transcript. Do not miss one. IF YOU DON'T KNOW SOMETHING ABOUT IT, DON'T MAKE THINGS UP. 
    Don't include \"[\" or \"]\" at all in the notes.""" },
            { "role": "user", "content": """fortnite balls""" },
        ],
        max_tokens=4096,
        temperature=0.6,
        top_p=0.3,
        presence_penalty=2,
        stream=False,
    )
    return response

failure = True
response = None
while failure:
    
    try:
        response = get_response()
        failure = False
    except:
        failure = True
        print("An error occurred, retrying in 10 seconds...")
        time.sleep(10)
        


try: thoughts = str(response.choices[0].message.content).split("<think>")[0]
except IndexError: thoughts = "No thoughts provided."
try: res = str(response.choices[0].message.content).split("</think>")[1]
except IndexError: res = "No response provided."

print(res)