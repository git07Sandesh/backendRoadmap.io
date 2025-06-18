import os
import json
import re
import traceback
import asyncio
from typing import List
from fastapi import HTTPException

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
gemini_client = None

if GEMINI_API_KEY:
    try:
        from google import genai as google_genai_module
        gemini_client = google_genai_module.Client(api_key=GEMINI_API_KEY)
        print("✅ Gemini client initialized.")
    except ImportError:
        print("❌ Failed to import 'genai'. Ensure correct package is installed.")
    except Exception as e:
        print(f"❌ Unexpected error during Gemini init: {e}")
else:
    print("⚠️ GEMINI_API_KEY not set.")

def clean_gemini_output(text: str) -> str:
    """Removes markdown-style ```json and ``` from Gemini output."""
    text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    text = re.sub(r"\s*```$", "", text.strip())
    return text.strip()

async def generate_learning_questions_from_gemini(prompt: str) -> List[str]:
    if not gemini_client:
        raise HTTPException(status_code=503, detail="Gemini not configured.")

    try:
        response = await asyncio.to_thread(
            gemini_client.models.generate_content,
            model="gemini-2.0-flash",
            contents=prompt,
        )

        text = clean_gemini_output(response.text or "")
        print("📄 Gemini Response:\n", text)

        try:
            questions = json.loads(text)
            if isinstance(questions, list):
                return questions
            raise ValueError("Expected a list of strings.")
        except json.JSONDecodeError:
            print("⚠️ JSONDecodeError in questions")
            array_match = re.search(r'\[\s*"[^"]*"(?:\s*,\s*"[^"]*")*\s*\]', text)
            if array_match:
                questions = json.loads(array_match.group(0))
                return questions
            raise HTTPException(status_code=500, detail="Gemini returned invalid JSON.")
    except Exception as e:
        print(f"❌ Gemini learning questions error: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

async def generate_roadmap_from_gemini(prompt: str) -> dict:
    if not gemini_client:
        raise HTTPException(status_code=503, detail="Gemini not configured.")

    try:
        response = await asyncio.to_thread(
            gemini_client.models.generate_content,
            model="gemini-2.0-flash",
            contents=prompt,
        )

        text = clean_gemini_output(response.text or "")
        print("🧠 Gemini roadmap raw response:\n", text)

        try:
            roadmap = json.loads(text)
            if isinstance(roadmap, dict):
                return roadmap
            raise ValueError("Expected a dictionary.")
        except json.JSONDecodeError as e:
            print("❌ JSONDecodeError:", e)

            dict_match = re.search(r'\{(?:[^{}]|(?R))*\}', text, re.DOTALL)
            if dict_match:
                try:
                    fallback_json = dict_match.group(0)
                    print("🛟 Fallback JSON:\n", fallback_json)
                    roadmap = json.loads(fallback_json)
                    return roadmap
                except Exception as inner_err:
                    print("❌ Fallback parse error:", inner_err)

            raise HTTPException(status_code=500, detail="Gemini returned invalid JSON.")
    except Exception as e:
        print("❌ Gemini roadmap generation failed:", e)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Gemini error: {str(e)}")
