# app/routers/resume.py
from fastapi import APIRouter, File, UploadFile, HTTPException
from typing import Annotated  # For Python 3.9+
import io

from ..services import resume_parser  # Relative import for service
from ..models.extraction_log import ExtractionLog  # Import the new log model

router = APIRouter()


@router.post("/parse_and_log/", response_model=ExtractionLog)
async def parse_resume_and_log_upload(
    file: Annotated[UploadFile, File(...)],
):
    """
    Receives a resume file (PDF, DOCX, TXT), extracts its text content,
    cleans it, and returns a structured JSON log.
    """
    filename = file.filename
    if not (
        filename.lower().endswith(".pdf")
        or filename.lower().endswith(".docx")
        or filename.lower().endswith(".txt")
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Please upload a PDF, DOCX, or TXT file.",
        )

    try:
        contents = await file.read()
        file_stream = io.BytesIO(contents)

        # Call the new service function for Phase 1
        extraction_log_data = await resume_parser.process_resume_file_to_log(
            file_stream, filename
        )

        # Depending on the status, you might want to handle it differently
        # For now, we return the log directly. If it failed, the log contains error details.
        if extraction_log_data.extraction_status == "failure":
            # You could raise an HTTPException here if you prefer to use HTTP status codes for failure
            # For example, if error_message is present, raise a 422 or 500
            # For now, returning the log with failure status as per plan
            pass

        return extraction_log_data
    except HTTPException:  # Re-raise HTTPExceptions directly
        raise
    except Exception as e:
        # Log the exception for debugging
        print(
            f"An unexpected error occurred in the /parse_and_log/ endpoint: {str(e)}"
        )  # Replace with proper logging
        # Return a generic error log or raise a 500 error
        # For consistency with the plan, we can try to create a failure log
        # This part might be redundant if process_resume_file_to_log handles all errors
        # and returns an ExtractionLog with status="failure"
        return ExtractionLog(
            resume_filename=filename,
            file_type_processed=(
                filename.split(".")[-1] if "." in filename else "unknown"
            ),
            extraction_status="failure",
            error_message=f"Endpoint error: {str(e)}",
        )
    finally:
        if file and not file.file.closed:
            await file.close()
