import os
import shutil
import uuid
import asyncio
import aiofiles
import requests
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from PyPDF2 import PdfReader
from dotenv import load_dotenv
from typing import Optional

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

app = FastAPI()

# Allow Android App to access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

TEMP_DIR = "temp_pdfs"
os.makedirs(TEMP_DIR, exist_ok=True)


@app.get("/")
def home():
    return {"message": "CodeSage backend is running successfully!"}


async def extract_text_from_pdf(file_path: str) -> str:
    reader = PdfReader(file_path)
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"
    return text


async def generate_questions(text: str, timeout: Optional[int] = 30) -> str:
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    prompt = f"""
    You are an AI teacher. Generate:
    - 5 one-mark questions with answers
    - 5 five-mark questions with answers
    - 5 ten-mark questions with answers

    Text:
    {text}
    """

    data = {
        "model": "gpt-4.1-mini",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7
    }

    try:
        # Run blocking requests.post in a thread to avoid blocking event loop
        response = await asyncio.to_thread(
            requests.post,
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=timeout
        )
        response.raise_for_status()
        res_json = response.json()
        return res_json["choices"][0]["message"]["content"]
    except requests.exceptions.Timeout:
        raise HTTPException(status_code=408, detail="Request to OpenRouter API timed out")
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Error generating questions: {e}")


@app.post("/upload_pdf")
async def upload_pdf(file: UploadFile = File(...)):
    file_id = str(uuid.uuid4())
    temp_path = os.path.join(TEMP_DIR, f"{file_id}_{file.filename}")

    # Async write uploaded file to temp directory
    async with aiofiles.open(temp_path, "wb") as out_file:
        while content := await file.read(1024):  # read in chunks
            await out_file.write(content)

    try:
        text = await extract_text_from_pdf(temp_path)
        questions = await generate_questions(text)
        return {"questions": questions, "filename": file.filename}
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
