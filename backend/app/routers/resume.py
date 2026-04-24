from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
from ..db import get_db
from .. import models
from ..nlp import extract_text_features
from typing import Optional
import logging, traceback, io

router = APIRouter(prefix="/resume", tags=["resume"])

logging.basicConfig(level=logging.DEBUG)

# ---------- File reading ----------

def _read_pdf(file_bytes: bytes) -> str:
    try:
        import PyPDF2
        reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
        return "".join([p.extract_text() or "" for p in reader.pages])
    except Exception as e:
        logging.error(f"PDF read error: {e}")
        return ""

def _read_docx(file_bytes: bytes) -> str:
    try:
        import docx
        doc = docx.Document(io.BytesIO(file_bytes))
        return "\n".join([p.text for p in doc.paragraphs])
    except Exception as e:
        logging.error(f"DOCX read error: {e}")
        return ""

# ---------- ATS SCORE ONLY ----------

def calculate_ats_score(text):
    text = text.lower()

    keywords = [
        "python", "machine learning", "react",
        "data science", "cloud", "nlp",
        "flask", "pandas", "numpy"
    ]

    score = 0

    for word in keywords:
        if word in text:
            score += 10

    return min(score, 100)

# ---------- Upload ----------

@router.post("/upload")
async def upload_resume(
    file: UploadFile = File(...),
    user_email: Optional[str] = None,
    db: Session = Depends(get_db)
):
    try:
        b = await file.read()

        content = ""
        if file.content_type == "application/pdf":
            content = _read_pdf(b)
        elif file.content_type in (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/msword"
        ):
            content = _read_docx(b)
        elif file.content_type.startswith("text/"):
            content = b.decode("utf-8", errors="ignore")
        else:
            raise HTTPException(status_code=400, detail="Unsupported file type")

        if not content.strip():
            raise HTTPException(status_code=400, detail="No text extracted")

        # User
        user = db.query(models.User).filter(models.User.email == (user_email or "default@resume.com")).first()
        if not user:
            user = models.User(email=user_email or "default@resume.com")
            db.add(user)
            db.flush()

        # Resume
        resume = models.Resume(
            user_id=user.id,
            filename=file.filename,
            content=content[:50000]
        )
        db.add(resume)
        db.flush()

        # Analysis
        analysis = extract_text_features(content[:100000])

        analysis_row = models.ResumeAnalysis(
            resume_id=resume.id,
            keywords=",".join(analysis.get("keywords", [])),
            entities=str(analysis.get("entities", [])),
            nouns=",".join(analysis.get("nouns", [])),
            sentence_to_platform=str(analysis.get("sentence_to_platform", {})),
            score=analysis.get("score", 0)
        )

        db.add(analysis_row)
        db.commit()

        return {"resume_id": resume.id, "filename": file.filename}

    except Exception as e:
        logging.error("Upload failed:\n" + traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

# ---------- Analysis ----------

@router.get("/analysis/{resume_id}")
def get_analysis(resume_id: int, db: Session = Depends(get_db)):
    r = db.query(models.Resume).filter(models.Resume.id == resume_id).first()

    if not r or not r.analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    a = r.analysis
    import ast

    # ✅ ONLY ATS SCORE
    ats_score = calculate_ats_score(r.content)

    return {
        "resume_id": r.id,
        "filename": r.filename,
        "content": r.content,
        "keywords": [k for k in (a.keywords or "").split(",") if k],
        "entities": ast.literal_eval(a.entities) if a.entities else [],
        "nouns": [n for n in (a.nouns or "").split(",") if n],
        "sentence_to_platform": ast.literal_eval(a.sentence_to_platform) if a.sentence_to_platform else {},
        "score": ats_score   # ✅ ONLY THIS
    }