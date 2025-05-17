from dotenv import load_dotenv  # Add this import

load_dotenv()  # Add this line to load the .env file

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import routers
from app.routers import resume, insights

app = FastAPI(
    title="API",
    description="FastAPI backend to parse resumes and generate learning insights.",  # Updated description
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
# You can choose a prefix, e.g., "/api/v1", for versioning or grouping
app.include_router(resume.router, prefix="/api/v1", tags=["Resume Parsing"])
app.include_router(insights.router, prefix="/api/v1", tags=["Learning Insights"])


@app.get("/")
async def root():
    return {"message": "Resume Parser API is running. Use endpoints under /api/v1/"}


if __name__ == "__main__":
    import uvicorn

    # For development, run with: uvicorn app.main:app --reload
    uvicorn.run(app, host="0.0.0.0", port=5000)
