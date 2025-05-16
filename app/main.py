from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware  # Add this import
import traceback  # For detailed error logging

from app.models import Resume  # Pydantic model for response
from app.parsers import parse_resume_from_pdf_stream  # Main parsing function

app = FastAPI(
    title="OpenResume Heuristic Parser API",
    description="FastAPI backend to parse resumes from PDF files using translated heuristic logic.",
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)


@app.post("/parse-resume/", response_model=Resume)
async def parse_resume_endpoint(file: UploadFile = File(...)):
    """
    Upload a resume PDF file and get the parsed structured data.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400, detail="Invalid file type. Only PDF files are accepted."
        )

    try:
        # PyMuPDF needs bytes, so read the file content
        pdf_bytes = await file.read()

        # Use BytesIO to treat bytes as a file-like object for PyMuPDF
        import io

        pdf_stream = io.BytesIO(pdf_bytes)

        parsed_resume = parse_resume_from_pdf_stream(pdf_stream)
        return parsed_resume
    except Exception as e:
        print(f"Error processing file {file.filename}: {e}")
        traceback.print_exc()  # Print full traceback to console for debugging
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while parsing the resume: {str(e)}",
        )


@app.get("/")
async def root():
    return {
        "message": "Resume Parser API is running. Use the /parse-resume/ endpoint to upload a PDF."
    }


if __name__ == "__main__":
    import uvicorn

    # For development, run with: uvicorn app.main:app --reload
    uvicorn.run(app, host="0.0.0.0", port=8000)


# virtual env - clusterpath