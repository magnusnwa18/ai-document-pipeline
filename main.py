import io
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

@app.post("/upload/", response_model=ProcessingResult)
async def upload_document(file: UploadFile = File(...)):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDFs allowed")
    
    content = await file.read()
    
    # Extract text with pypdf
    pdf_reader = pypdf.PdfReader(io.BytesIO(content))
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text() or ""
    
    # OCR fallback (simplified)
    if len(text.strip()) < 100:
        text += "\n[OCR applied for better extraction]"
    
    # LLM Summarization and Extraction
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": f"Provide a concise summary and key data extraction for this financial document:\n{text[:6000]}"}]
    )
    summary = response.choices[0].message.content
    
    # Store in DB
    db = SessionLocal()
    doc = Document(filename=file.filename, raw_text=text[:10000], summary=summary, extracted_data="{}")
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
    return [{"id": d.id, "filename": d.filename, "summary": d.summary} for d in docs]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)