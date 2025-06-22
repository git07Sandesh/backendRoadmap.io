# Structured Resume Storage API

This document explains the new structured resume storage endpoints that store resume data in organized columns for better querying and reconstruction.

## Overview

The structured approach stores resume data in separate columns instead of a single JSON blob:
- **Profile data**: Individual columns for name, email, phone, etc.
- **Section data**: JSON columns for work experiences, education, projects, skills
- **Embeddings**: Vector embeddings for semantic search
- **Metadata**: Timestamps and tracking information

## Endpoints

### 1. Store Structured Resume
**POST** `/api/v1/store-structured-resume`

Stores resume data with structured columns and generates embeddings.

**Request Body:**
```json
{
    "user_id": "790fa985-3145-460f-9586-84b08217ef61",
    "resume": {
        "profile": {
            "name": "John Doe",
            "email": "john@example.com",
            "phone": "(555) 123-4567",
            "url": "github.com/johndoe",
            "summary": "Software Developer",
            "location": "New York, NY"
        },
        "workExperiences": [...],
        "educations": [...],
        "projects": [...],
        "skills": {...},
        "custom": {}
    }
}
```

**Response:**
```json
{
    "success": true,
    "message": "Structured resume stored successfully with embeddings",
    "user_id": "790fa985-3145-460f-9586-84b08217ef61",
    "embeddings_generated": {
        "education": true,
        "work_experience": true,
        "projects": true,
        "skills": true,
        "full_resume": true
    },
    "data_id": "abc123-def456-..."
}
```

### 2. Get Structured Resume
**GET** `/api/v1/get-structured-resume/{user_id}`

Retrieves and reconstructs the original resume format from structured storage.

**Response:**
```json
{
    "success": true,
    "data": {
        "user_id": "790fa985-3145-460f-9586-84b08217ef61",
        "resume": {
            "profile": {...},
            "workExperiences": [...],
            "educations": [...],
            "projects": [...],
            "skills": {...},
            "custom": {}
        },
        "metadata": {
            "created_at": "2025-06-22T10:30:00Z",
            "updated_at": "2025-06-22T10:30:00Z",
            "has_embeddings": {
                "education": true,
                "work_experience": true,
                "projects": true,
                "skills": true,
                "full_resume": true
            }
        }
    }
}
```

### 3. Delete Structured Resume
**DELETE** `/api/v1/delete-structured-resume/{user_id}`

Deletes the structured resume data for a user.

### 4. Search Resumes by Skills
**GET** `/api/v1/search-resumes-by-skills?query=Python&limit=10`

Searches resumes using semantic similarity on skills embeddings.

**Parameters:**
- `query`: Search query (e.g., "Python machine learning")
- `limit`: Maximum results to return (default: 10)

## Database Schema

The structured approach uses a `structured_user_resumes` table with:

### Profile Columns (for easy querying)
- `profile_name` TEXT
- `profile_email` TEXT  
- `profile_phone` TEXT
- `profile_url` TEXT
- `profile_summary` TEXT
- `profile_location` TEXT

### JSON Columns (for complex data)
- `work_experiences` JSONB
- `educations` JSONB
- `projects` JSONB
- `skills` JSONB
- `custom` JSONB

### Embedding Columns (requires pgvector)
- `education_embedding` vector(768)
- `work_experience_embedding` vector(768)
- `projects_embedding` vector(768)
- `skills_embedding` vector(768)
- `full_resume_embedding` vector(768)

## Setup Instructions

1. **Run the SQL schema** in your Supabase SQL editor:
   ```bash
   # Execute the contents of supabase_schema_structured_resumes.sql
   ```

2. **Enable pgvector extension** (optional, for vector search):
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```

3. **Configure environment variables**:
   ```env
   SUPABASE_URL=your_supabase_url
   SUPABASE_KEY=your_supabase_key
   GEMINI_API_KEY=your_gemini_api_key
   ```

## Benefits

### 1. **Better Querying**
- Search by name, email, location directly
- Filter by specific skills or experience
- Aggregate data across profiles

### 2. **Reconstruction**
- Original format can be perfectly reconstructed
- Maintains data integrity and structure
- Supports backwards compatibility

### 3. **Semantic Search**
- Vector embeddings enable similarity search
- Find candidates with similar skills/experience
- Support for AI-powered matching

### 4. **Performance**
- Indexed columns for fast queries
- Structured data reduces parsing overhead
- Optimized for common access patterns

## Example Usage

```python
import requests

# Store resume
response = requests.post(
    "http://localhost:8000/api/v1/store-structured-resume",
    json={
        "user_id": "123e4567-e89b-12d3-a456-426614174000",
        "resume": {
            # ... resume data
        }
    }
)

# Retrieve resume
response = requests.get(
    "http://localhost:8000/api/v1/get-structured-resume/123e4567-e89b-12d3-a456-426614174000"
)

# Search by skills
response = requests.get(
    "http://localhost:8000/api/v1/search-resumes-by-skills",
    params={"query": "Python FastAPI", "limit": 5}
)
```

## Migration from Original Format

If you have existing data in the `user_resumes` table, you can migrate it using:

```python
# Migration script example
def migrate_existing_resumes():
    # Fetch from old table
    old_resumes = supabase.table("user_resumes").select("*").execute()
    
    for resume in old_resumes.data:
        # Convert to new format and store
        structured_data = convert_to_structured_format(resume)
        supabase.table("structured_user_resumes").insert(structured_data).execute()
```
