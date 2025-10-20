import os
import shutil
import uuid
from fastapi import FastAPI, File, UploadFile ,Request
from fastapi.middleware.cors import CORSMiddleware
from PyPDF2 import PdfReader
import requests
from dotenv import load_dotenv

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

def extract_text_from_pdf(file_path):
    reader = PdfReader(file_path)
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"
    return text

def generate_questions(text):
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

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers=headers,
        json=data
    )

    if response.status_code == 200:
        res_json = response.json()
        return res_json["choices"][0]["message"]["content"]
    else:
        return f"Error generating questions: {response.text}"
@app.get('/')
def home(request: Request):
    return jsonify({"message": "CodeSage backend is running successfully!"})
@app.post("/upload_pdf")
async def upload_pdf(file: UploadFile = File(...)):
    file_id = str(uuid.uuid4())
    temp_path = os.path.join(TEMP_DIR, f"{file_id}_{file.filename}")
    with open(temp_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        text = extract_text_from_pdf(temp_path)
        questions = generate_questions(text)
        return {"questions": questions}
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
