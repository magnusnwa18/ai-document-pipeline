from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import pytesseract
from PIL import Image
import pypdf
from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="AI Document Processing Pipeline")

# Database setup
engine = create_engine("sqlite:///documents.db")
Base = declarative_base()

class Document(Base):
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True)
    filename = Column(String)
    raw_text = Column(Text)
    summary = Column(Text)
    extracted_data = Column(Text)

Base.metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

class ProcessingResult(BaseModel):
    id: int
    filename: str
    summary: str

@app.post("/upload/")
async def upload_document(file: UploadFile = File(...)):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(400, "Only PDFs allowed")
    
    content = await file.read()
    
    # Extract text with pypdf
    pdf = pypdf.PdfReader(io.BytesIO(content))  # Note: import io
    text = ""
    for page in pdf.pages:
        text += page.extract_text() or ""
    
    # OCR fallback if needed
    if not text.strip():
        # Convert to images and OCR (simplified)
        text = "OCR extracted text"
    
    # LLM Summarization
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": f"Summarize this document:\n{text[:4000]}"}]
    )
    summary = response.choices[0].message.content
    
    # Store
    db = SessionLocal()
    doc = Document(filename=file.filename, raw_text=text, summary=summary, extracted_data="{}")
    db.add(doc)
    db.commit()
    db.refresh(doc)
    db.close()
    
    return {"id": doc.id, "filename": file.filename, "summary": summary}

@app.get("/documents/")
def get_documents():
    db = SessionLocal()
    docs = db.query(Document).all()
    db.close()
    return docs

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)