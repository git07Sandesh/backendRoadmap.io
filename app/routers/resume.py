# filepath: c:\Users\rajka\backendRoadmap.io\app\routers\resume.py
from fastapi import APIRouter, File, UploadFile, HTTPException
import traceback
import io

# Assuming your models and parsers are structured as previously discussed
from app.models import Resume
from app.parsers import (
    parse_resume_from_pdf_stream,
)  # Make sure this function exists and is correctly imported

router = APIRouter()


@router.post("/parse-resume/", response_model=Resume)
async def parse_resume_endpoint(file: UploadFile = File(...)):
    """
    Upload a resume PDF file and get the parsed structured data.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400, detail="Invalid file type. Only PDF files are accepted."
        )

    try:
        pdf_bytes = await file.read()
        pdf_stream = io.BytesIO(pdf_bytes)

        parsed_resume = parse_resume_from_pdf_stream(pdf_stream)

        return parsed_resume
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Error processing file {file.filename}: {e}")
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while parsing the resume: {str(e)}",
        )
