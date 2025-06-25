from fastapi import APIRouter, HTTPException
import logging

logger = logging.getLogger(__name__)

from pydantic import BaseModel
from typing import List, Dict, Optional
import os
from dotenv import load_dotenv
from supabase import create_client
import google.generativeai as genai
from datetime import datetime

from app.models import (
    UserResumeData,
    ResumeStorageResponse,
    StructuredResumeStorageResponse,
)

load_dotenv()
router = APIRouter()

# Validate environment variables
supabase_url = os.getenv("supabase_url")
supabase_key = os.getenv("supabase_key")
gemini_key = os.getenv("GEMINI_API_KEY")
if not supabase_url or not supabase_key:
    logger.error(
        f"Missing Supabase configuration: supabase_url={supabase_url}, supabase_key set={bool(supabase_key)}"
    )
    raise RuntimeError(
        "Supabase URL or Key not configured. Please set supabase_url and supabase_key in environment."
    )
if not gemini_key:
    logger.error("Missing Gemini API Key: GEMINI_API_KEY not set in environment")
    raise RuntimeError(
        "Gemini API Key not configured. Please set GEMINI_API_KEY in environment."
    )

# Initialize clients
supabase = create_client(supabase_url, supabase_key)
genai.configure(api_key=gemini_key)


def get_embedding(text: str) -> List[float]:
    """Generate embedding for text using Gemini"""
    try:
        response = genai.embed_content(
            model="models/embedding-001",
            content=text,
            task_type="RETRIEVAL_DOCUMENT",
            title="Resume Section",
        )
        return response["embedding"]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gemini embedding error: {str(e)}")


def extract_text_from_education(educations: List[Dict]) -> str:
    """Extract meaningful text from education section"""
    education_texts = []
    for edu in educations:
        parts = []
        if edu.get("school"):
            parts.append(edu["school"])
        if edu.get("degree"):
            parts.append(edu["degree"])
        if edu.get("gpa"):
            parts.append(f"GPA: {edu['gpa']}")
        if edu.get("descriptions"):
            parts.extend(edu["descriptions"])

        if parts:
            education_texts.append(" ".join(parts))

    return " | ".join(education_texts) if education_texts else ""


def extract_text_from_work_experiences(work_experiences: List[Dict]) -> str:
    """Extract meaningful text from work experiences section"""
    work_texts = []
    for work in work_experiences:
        parts = []
        if work.get("jobTitle"):
            parts.append(work["jobTitle"])
        if work.get("company"):
            parts.append(work["company"])
        if work.get("descriptions"):
            parts.extend(work["descriptions"])

        if parts:
            work_texts.append(" ".join(parts))

    return " | ".join(work_texts) if work_texts else ""


def extract_text_from_projects(projects: List[Dict]) -> str:
    """Extract meaningful text from projects section"""
    project_texts = []
    for project in projects:
        parts = []
        if project.get("project"):
            parts.append(project["project"])
        if project.get("descriptions"):
            parts.extend(project["descriptions"])

        if parts:
            project_texts.append(" ".join(parts))

    return " | ".join(project_texts) if project_texts else ""


def extract_text_from_skills(skills: Dict) -> str:
    """Extract meaningful text from skills section"""
    skill_texts = []

    # Featured skills
    if skills.get("featuredSkills"):
        for skill in skills["featuredSkills"]:
            if skill.get("skill") and skill["skill"].strip():
                skill_texts.append(skill["skill"])

    # Skill descriptions
    if skills.get("descriptions"):
        skill_texts.extend(skills["descriptions"])

    return " | ".join(skill_texts) if skill_texts else ""


def create_full_resume_text(resume: Dict) -> str:
    """Create a comprehensive text representation of the entire resume"""
    texts = []

    # Profile
    if resume.get("profile"):
        profile = resume["profile"]
        profile_parts = []
        for key in ["name", "summary"]:
            if profile.get(key):
                profile_parts.append(profile[key])
        if profile_parts:
            texts.append(" ".join(profile_parts))

    # Add section texts
    education_text = extract_text_from_education(resume.get("educations", []))
    if education_text:
        texts.append(education_text)

    work_text = extract_text_from_work_experiences(resume.get("workExperiences", []))
    if work_text:
        texts.append(work_text)

    projects_text = extract_text_from_projects(resume.get("projects", []))
    if projects_text:
        texts.append(projects_text)

    skills_text = extract_text_from_skills(resume.get("skills", {}))
    if skills_text:
        texts.append(skills_text)

    return " | ".join(texts)


@router.post("/store-user-resume", response_model=ResumeStorageResponse)
async def store_user_resume(user_resume: UserResumeData):
    """
    Store user resume data with embeddings in Supabase
    """
    try:
        resume_dict = user_resume.resume.dict(by_alias=True)

        # Generate embeddings for each section
        embeddings_generated = {
            "education": False,
            "work_experience": False,
            "projects": False,
            "skills": False,
            "full_resume": False,
        }

        # Education embedding
        education_text = extract_text_from_education(resume_dict.get("educations", []))
        education_embedding = None
        if education_text:
            education_embedding = get_embedding(education_text)
            embeddings_generated["education"] = True

        # Work experience embedding
        work_text = extract_text_from_work_experiences(
            resume_dict.get("workExperiences", [])
        )
        work_embedding = None
        if work_text:
            work_embedding = get_embedding(work_text)
            embeddings_generated["work_experience"] = True

        # Projects embedding
        projects_text = extract_text_from_projects(resume_dict.get("projects", []))
        projects_embedding = None
        if projects_text:
            projects_embedding = get_embedding(projects_text)
            embeddings_generated["projects"] = True

        # Skills embedding
        skills_text = extract_text_from_skills(resume_dict.get("skills", {}))
        skills_embedding = None
        if skills_text:
            skills_embedding = get_embedding(skills_text)
            embeddings_generated["skills"] = True

        # Full resume embedding
        full_text = create_full_resume_text(resume_dict)
        full_embedding = None
        if full_text:
            full_embedding = get_embedding(full_text)
            embeddings_generated["full_resume"] = True

        # Prepare data for Supabase
        current_time = datetime.utcnow().isoformat()
        resume_data = {
            "user_id": user_resume.user_id,
            "resume_data": resume_dict,
            "education_embedding": education_embedding,
            "work_experience_embedding": work_embedding,
            "projects_embedding": projects_embedding,
            "skills_embedding": skills_embedding,
            "full_resume_embedding": full_embedding,
            "created_at": current_time,
            "updated_at": current_time,
        }

        # Execute upsert and check for errors
        result = (
            supabase.table("user_resumes")
            .upsert(resume_data, on_conflict="user_id")
            .execute()
        )
        if hasattr(result, "error") and result.error:
            logger.error(f"Supabase upsert error: {result.error}")
            # Raise HTTPException with detailed Supabase error
            raise HTTPException(
                status_code=500, detail=f"Supabase error: {result.error.message}"
            )
        # Log warning if no data returned
        if not result.data:
            logger.warning(f"Supabase upsert returned empty data: {result}")

        return ResumeStorageResponse(
            success=True,
            message="Resume stored successfully with embeddings",
            user_id=user_resume.user_id,
            embeddings_generated=embeddings_generated,
        )

    except HTTPException as e:
        raise e
    except Exception as e:
        # Log full exception stack
        logger.exception("Error occurred in store_user_resume")
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while storing the resume: {str(e)}",
        )


@router.get("/get-user-resume/{user_id}")
async def get_user_resume(user_id: str):
    """
    Retrieve user resume data from Supabase
    """
    try:
        result = (
            supabase.table("user_resumes").select("*").eq("user_id", user_id).execute()
        )

        if not result.data:
            raise HTTPException(
                status_code=404, detail="Resume not found for this user"
            )

        return {"success": True, "data": result.data[0]}

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while retrieving the resume: {str(e)}",
        )


@router.delete("/delete-user-resume/{user_id}")
async def delete_user_resume(user_id: str):
    """
    Delete user resume data from Supabase
    """
    try:
        result = (
            supabase.table("user_resumes").delete().eq("user_id", user_id).execute()
        )

        return {
            "success": True,
            "message": f"Resume deleted successfully for user {user_id}",
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while deleting the resume: {str(e)}",
        )


@router.post("/store-structured-resume", response_model=StructuredResumeStorageResponse)
async def store_structured_resume(user_resume: UserResumeData):
    """
    Store user resume data with structured columns and embeddings in Supabase
    """
    try:
        resume_dict = user_resume.resume.dict(by_alias=True)

        # Generate embeddings for each section
        embeddings_generated = {
            "education": False,
            "work_experience": False,
            "projects": False,
            "skills": False,
            "full_resume": False,
        }

        # Education embedding
        education_text = extract_text_from_education(resume_dict.get("educations", []))
        education_embedding = None
        if education_text:
            education_embedding = get_embedding(education_text)
            embeddings_generated["education"] = True

        # Work experience embedding
        work_text = extract_text_from_work_experiences(
            resume_dict.get("workExperiences", [])
        )
        work_embedding = None
        if work_text:
            work_embedding = get_embedding(work_text)
            embeddings_generated["work_experience"] = True

        # Projects embedding
        projects_text = extract_text_from_projects(resume_dict.get("projects", []))
        projects_embedding = None
        if projects_text:
            projects_embedding = get_embedding(projects_text)
            embeddings_generated["projects"] = True

        # Skills embedding
        skills_text = extract_text_from_skills(resume_dict.get("skills", {}))
        skills_embedding = None
        if skills_text:
            skills_embedding = get_embedding(skills_text)
            embeddings_generated["skills"] = True

        # Full resume embedding
        full_text = create_full_resume_text(resume_dict)
        full_embedding = None
        if full_text:
            full_embedding = get_embedding(full_text)
            embeddings_generated["full_resume"] = True

        # Prepare data for Supabase to match the 'user_resumes' table schema
        current_time = datetime.utcnow().isoformat()
        resume_data_for_upsert = {
            "user_id": user_resume.user_id,
            "resume_data": resume_dict,
            "education_embedding": education_embedding,
            "work_experience_embedding": work_embedding,
            "projects_embedding": projects_embedding,
            "skills_embedding": skills_embedding,
            "full_resume_embedding": full_embedding,
            "created_at": current_time,
            "updated_at": current_time,
        }

        # Store in Supabase (upsert to handle updates)
        result = (
            supabase.table("user_resumes")
            .upsert(resume_data_for_upsert, on_conflict="user_id")
            .execute()
        )

        if not result.data:
            raise HTTPException(
                status_code=500, detail="Failed to store structured resume in database"
            )

        # ---- NEW: Trigger job matching after storing resume ----
        if full_embedding:
            try:
                supabase.rpc(
                    "calculate_and_store_job_matches",
                    {
                        "p_user_id": user_resume.user_id,
                        "p_user_embedding": full_embedding,
                    },
                ).execute()
                logger.info(
                    f"Successfully calculated job matches for user {user_resume.user_id}"
                )
            except Exception as rpc_error:
                # Log the error but don't fail the main request
                logger.error(
                    f"Failed to calculate job matches for user {user_resume.user_id}: {rpc_error}"
                )
        # ---- END NEW SECTION ----

        return StructuredResumeStorageResponse(
            success=True,
            message="Structured resume stored successfully with embeddings",
            user_id=user_resume.user_id,
            embeddings_generated=embeddings_generated,
            data_id=(
                str(result.data[0].get("id"))
                if result.data and result.data[0].get("id") is not None
                else None
            ),
        )

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while storing the structured resume: {str(e)}",
        )


@router.get("/get-structured-resume/{user_id}")
async def get_structured_resume(user_id: str):
    """
    Retrieve structured user resume data from Supabase and reconstruct the original format
    """
    try:
        result = (
            supabase.table("user_resumes").select("*").eq("user_id", user_id).execute()
        )

        if not result.data:
            raise HTTPException(
                status_code=404, detail="Resume not found for this user"
            )

        data = result.data[0]

        # Reconstruct the response from the user_resumes table format
        reconstructed_resume = {
            "user_id": data["user_id"],
            "resume": data.get("resume_data", {}),
            "metadata": {
                "created_at": data.get("created_at"),
                "updated_at": data.get("updated_at"),
                "has_embeddings": {
                    "education": data.get("education_embedding") is not None,
                    "work_experience": data.get("work_experience_embedding")
                    is not None,
                    "projects": data.get("projects_embedding") is not None,
                    "skills": data.get("skills_embedding") is not None,
                    "full_resume": data.get("full_resume_embedding") is not None,
                },
            },
        }

        return {"success": True, "data": reconstructed_resume}

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while retrieving the structured resume: {str(e)}",
        )


@router.delete("/delete-structured-resume/{user_id}")
async def delete_structured_resume(user_id: str):
    """
    Delete structured user resume data from Supabase
    """
    try:
        result = (
            supabase.table("user_resumes").delete().eq("user_id", user_id).execute()
        )

        return {
            "success": True,
            "message": f"Structured resume deleted successfully for user {user_id}",
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while deleting the structured resume: {str(e)}",
        )


@router.get("/search-resumes-by-skills")
async def search_resumes_by_skills(query: str, limit: int = 10):
    """
    Search resumes by skills using embedding similarity
    """
    try:
        # Generate embedding for the search query
        query_embedding = get_embedding(query)

        # Use Supabase's vector similarity search (requires pgvector extension)
        # This is a placeholder - actual implementation depends on your Supabase setup
        result = supabase.rpc(
            "search_resumes_by_skills_similarity",
            {
                "query_embedding": query_embedding,
                "match_threshold": 0.7,
                "match_count": limit,
            },
        ).execute()

        return {
            "success": True,
            "query": query,
            "results": result.data if result.data else [],
            "count": len(result.data) if result.data else 0,
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while searching resumes: {str(e)}",
        )


@router.get("/user/{user_id}/job-circle-graph")
async def get_zoomable_job_user_tree(user_id: str, job_limit: int = 10, user_limit: int = 10):
    try:
        jobs_result = (
            supabase.table("user_job_match")
            .select("job_id, similarity_score, job_embeddings(job_title)")
            .eq("user_id", user_id)
            .order("similarity_score", desc=True)
            .limit(job_limit)
            .execute()
        )

        if not jobs_result.data:
            return {"name": "Top Jobs", "children": []}

        root_children = []

        for job in jobs_result.data:
            job_id = job["job_id"]
            job_title = job["job_embeddings"]["job_title"]

            # Get top users for this job
            users_result = (
                supabase.table("user_job_match")
                .select("user_id, similarity_score")
                .eq("job_id", job_id)
                .order("similarity_score", desc=True)
                .limit(user_limit)
                .execute()
            )

            user_children = [
                {
                    "name": f"User {user['user_id'][:8]}",
                    "value": round(user["similarity_score"], 4)
                }
                for user in users_result.data
            ]

            # Compute average similarity to use as job node value
            job_avg_value = (
                round(sum(child["value"] for child in user_children) / len(user_children), 4)
                if user_children else 0.0
            )

            job_node = {
                "name": job_title,
                "value": job_avg_value,  # ⬅️ this is what was missing
                "children": user_children
            }

            root_children.append(job_node)

        return {
            "name": f"User {user_id[:8]} Top Jobs",
            "children": root_children
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error building graph: {str(e)}")


