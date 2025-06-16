import os
import json
import re
import traceback
import asyncio  # Added for asyncio.to_thread
from typing import List
from fastapi import HTTPException

# Attempt to import and initialize client as per the image provided by the user
# This assumes the 'google-genai' package provides 'genai' directly under 'google'
# and has a 'Client' attribute.
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
gemini_client = None

if GEMINI_API_KEY:
    try:
        from google import (
            genai as google_genai_module,
        )  # Using an alias to avoid potential conflicts

        gemini_client = google_genai_module.Client(api_key=GEMINI_API_KEY)
        print("Gemini client initialized using 'google.genai.Client' pattern.")
    except ImportError:
        print("ERROR: Failed to import 'genai' from 'google'.")
        print(
            "Ensure the 'google-genai' package is installed and provides this import structure."
        )
        print(
            "Alternatively, the standard import is 'import google.generativeai as genai'."
        )
        gemini_client = None
    except AttributeError:
        print("ERROR: 'genai.Client' not found after import.")
        print(
            "The 'google-genai' package might use a different API (e.g., google.generativeai.GenerativeModel)."
        )
        gemini_client = None
    except Exception as e:
        print(f"An unexpected error occurred during Gemini client initialization: {e}")
        gemini_client = None
else:
    print(
        "Warning: GEMINI_API_KEY environment variable not set. Gemini service will not work."
    )


async def generate_learning_questions_from_gemini(prompt: str) -> List[str]:
    """
    Uses the Gemini API to generate learning gap questions based on the prompt.
    The prompt should instruct Gemini to return a JSON array of strings.
    Uses the client.models.generate_content method as per user's image.
    """
    if not gemini_client:
        raise HTTPException(
            status_code=503,
            detail="Gemini client is not configured, API key missing, or library issue. Please check server logs.",
        )

    try:
        # Using client.models.generate_content as per the image
        # Running the synchronous call in a separate thread
        response = await asyncio.to_thread(
            gemini_client.models.generate_content,
            model="gemini-2.0-flash",  # Model from the user's image
            contents=prompt,
        )  # Assuming response structure is similar regarding .text and .prompt_feedback
        if response.text:
            print(response.text)  # For debugging, log the response text
            try:
                # Clean the response text before parsing
                text = response.text

                # Remove markdown code block markers if present
                if text.startswith("```json") or text.startswith("```"):
                    text = re.sub(r"^```json\s*", "", text)
                    text = re.sub(r"^```\s*", "", text)
                    text = re.sub(r"\s*```$", "", text)

                # Clean up text and attempt to parse
                text = text.strip()
                questions_list = json.loads(text)

                if not isinstance(questions_list, list):
                    print(
                        f"Warning: Gemini response was not a JSON list as expected. Response text: {response.text}"
                    )
                    raise HTTPException(
                        status_code=500,
                        detail="Gemini API returned an unexpected format. Expected a JSON array of strings.",
                    )
                return questions_list
            except json.JSONDecodeError as json_err:
                print(
                    f"Error: Failed to decode JSON from Gemini response: {json_err}. Response text: {response.text}"
                )  # Fallback: Try to extract array using regex if JSON parsing fails
                # This handles cases where the array is embedded in markdown or other text
                array_match = re.search(
                    r'\[\s*"[^"]*"(?:\s*,\s*"[^"]*")*\s*\]', response.text
                )
                if array_match:
                    try:
                        questions_list = json.loads(array_match.group(0))
                        if isinstance(questions_list, list):
                            print(
                                f"Successfully extracted questions using regex fallback: {questions_list}"
                            )
                            return questions_list
                    except:
                        pass  # Continue to the exception if regex extraction failed too

                raise HTTPException(
                    status_code=500,
                    detail="Failed to parse response from Gemini API. The response was not valid JSON.",
                )
        else:
            # Check for prompt feedback if response.text is empty
            # The exact structure of prompt_feedback might vary; adapting from previous code.
            if (
                hasattr(response, "prompt_feedback")
                and response.prompt_feedback
                and response.prompt_feedback.block_reason
            ):
                block_reason_message = (
                    response.prompt_feedback.block_reason_message
                    or "Content blocked by API."
                )
                print(f"Gemini API call blocked: {block_reason_message}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Content generation blocked by API: {block_reason_message}",
                )
            # Fallback if no specific block reason is found but text is empty
            print(
                f"Error: Gemini API returned an empty response. Full response: {response}"
            )
            raise HTTPException(
                status_code=500, detail="Gemini API returned an empty response."
            )
    except Exception as e:
        print(f"Error calling Gemini API with client.models.generate_content: {e}")
        traceback.print_exc()
        # Check if it's an API error from the Gemini library itself that might already be an HTTPException
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while communicating with the Gemini API: {str(e)}",
        )
