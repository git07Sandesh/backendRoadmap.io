from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

# Import routers
from app.routers import resume, insights, tagExtraction, roadmap

app = FastAPI(
    title="API",
    description="FastAPI backend to parse resumes and generate learning insights.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(resume.router, prefix="/api/v1", tags=["Resume Parsing"])
app.include_router(insights.router, prefix="/api/v1", tags=["Learning Insights"])
app.include_router(tagExtraction.router, prefix="/api/v1", tags=["Tag Extraction"])
app.include_router(roadmap.router, prefix="/api/v1", tags=["Roadmap Generation"])

@app.get("/")
async def root():
    return {"message": "Resume Parser API is running. Use endpoints under /api/v1/"}


# ✅ Local development runner
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
