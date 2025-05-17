# filepath: c:\Users\rajka\backendRoadmap.io\app\routers\insights.py
from fastapi import APIRouter, HTTPException
from typing import Dict, List
import traceback

# Assuming your models and services are structured as previously discussed
from app.models import (
    LearningQuestionRequest,
)  # Make sure this model is defined in app.models.py
from app.services.gemini_service import (
    generate_learning_questions_from_gemini,
)  # Make sure this service function exists

router = APIRouter()


@router.post("/generate-learning-questions/", response_model=Dict[str, List[str]])
async def generate_learning_questions_endpoint(request_data: LearningQuestionRequest):
    """
    Receives a prompt and uses the Gemini API to generate learning gap questions.
    The prompt should instruct Gemini to return a JSON array of strings.
    """
    try:
        questions = await generate_learning_questions_from_gemini(request_data.prompt)
        return {"questions": questions}
    except HTTPException as e:
        # Re-raise HTTPExceptions from the service layer or validation
        raise e
    except Exception as e:
        print(f"Unexpected error in /generate-learning-questions/ endpoint: {e}")
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"An internal server error occurred while generating learning questions: {str(e)}",
        )
