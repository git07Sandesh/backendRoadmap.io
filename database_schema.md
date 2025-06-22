# User Resume Storage Database Schema

## Table: user_resumes

This table stores user resume data with embeddings for different sections.

### SQL Schema

```sql
-- Create the user_resumes table
CREATE TABLE user_resumes (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL UNIQUE,
    resume_data JSONB NOT NULL,
    education_embedding vector(768),
    work_experience_embedding vector(768),
    projects_embedding vector(768),
    skills_embedding vector(768),
    full_resume_embedding vector(768),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for better performance
CREATE INDEX idx_user_resumes_user_id ON user_resumes(user_id);
CREATE INDEX idx_user_resumes_created_at ON user_resumes(created_at);

-- Create vector similarity search indexes (if using pgvector)
CREATE INDEX idx_education_embedding ON user_resumes USING ivfflat (education_embedding vector_cosine_ops);
CREATE INDEX idx_work_experience_embedding ON user_resumes USING ivfflat (work_experience_embedding vector_cosine_ops);
CREATE INDEX idx_projects_embedding ON user_resumes USING ivfflat (projects_embedding vector_cosine_ops);
CREATE INDEX idx_skills_embedding ON user_resumes USING ivfflat (skills_embedding vector_cosine_ops);
CREATE INDEX idx_full_resume_embedding ON user_resumes USING ivfflat (full_resume_embedding vector_cosine_ops);

-- Add RLS policies if needed
ALTER TABLE user_resumes ENABLE ROW LEVEL SECURITY;

-- Example policy (adjust based on your authentication setup)
CREATE POLICY "Users can only access their own resumes" ON user_resumes
    FOR ALL USING (auth.uid() = user_id);
```

### Column Descriptions

- `id`: Primary key, auto-incrementing
- `user_id`: UUID of the user (should match your user authentication system)
- `resume_data`: JSONB field containing the complete resume data
- `education_embedding`: Vector embedding for education section (768 dimensions for Gemini embeddings)
- `work_experience_embedding`: Vector embedding for work experience section
- `projects_embedding`: Vector embedding for projects section
- `skills_embedding`: Vector embedding for skills section
- `full_resume_embedding`: Vector embedding for the entire resume
- `created_at`: Timestamp when the record was created
- `updated_at`: Timestamp when the record was last updated

### Notes

1. The embedding vectors are 768-dimensional as that's the default for Gemini's embedding model
2. You'll need to enable the `pgvector` extension in Supabase for vector operations
3. The JSONB field allows for flexible storage and querying of resume data
4. RLS (Row Level Security) policies should be configured based on your authentication setup

### Required Supabase Extensions

Make sure these extensions are enabled in your Supabase project:

```sql
-- Enable pgvector extension for vector operations
CREATE EXTENSION IF NOT EXISTS vector;
```

### Example Queries

```sql
-- Find similar resumes based on skills
SELECT user_id, resume_data->'profile'->>'name' as name
FROM user_resumes
WHERE skills_embedding IS NOT NULL
ORDER BY skills_embedding <-> (SELECT skills_embedding FROM user_resumes WHERE user_id = 'target-user-id')
LIMIT 10;

-- Search for resumes with similar work experience
SELECT user_id, resume_data->'profile'->>'name' as name
FROM user_resumes
WHERE work_experience_embedding IS NOT NULL
ORDER BY work_experience_embedding <-> (SELECT work_experience_embedding FROM user_resumes WHERE user_id = 'target-user-id')
LIMIT 10;
```
