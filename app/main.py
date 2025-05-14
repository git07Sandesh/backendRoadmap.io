from fastapi import FastAPI
from .routers import resume as resume_router  # Corrected import
from app.routers import linkedin 
from fastapi.middleware.cors import CORSMiddleware

from .config import (
    settings,
)  # Import settings to ensure it's loaded, though not directly used here often

app = FastAPI(title="Resume Parser API")

# Include routers
app.include_router(resume_router.router, prefix="/resume", tags=["resume"])

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(linkedin.router, prefix="/linkedin", tags=["LinkedIn"])


@app.get("/")
async def root():
    
    return {
        "message": "Welcome to the Resume Parser API. Go to /docs for API documentation."
    }


# The if __name__ == "__main__": block is tricky with relative imports if you run this file directly.
# It's better to run FastAPI apps using Uvicorn from the project root directory.
# Example: uvicorn app.main:app --reload from c:\Users\rajka\backendRoadmap.io
#
# If you still want to run it directly for some reason (e.g. simple testing without full project structure in PYTHONPATH):
# import sys
# import os
# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


if __name__ == "__main__":
    import uvicorn

    # To run this directly, you might need to adjust PYTHONPATH or run as a module
    # For simplicity, assuming you run from the root with `python -m app.main` or use uvicorn
    print("Running Uvicorn. Navigate to http://127.0.0.1:8000")
    print("For API docs, go to http://127.0.0.1:8000/docs")
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True, workers=1)

# To run the application:
# 1. Ensure your conda environment 'clusterpath' is activated.
# 2. Ensure .env file is in the root directory (c:\Users\rajka\backendRoadmap.io) with SUPABASE_URL and SUPABASE_KEY.
# 3. From the root directory (c:\Users\rajka\backendRoadmap.io), run:
#    uvicorn app.main:app --reload
