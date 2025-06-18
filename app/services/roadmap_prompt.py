import json

def build_prompt(resume_data: dict, flattened_tags: list[str], job: dict) -> str:
    tag_str = ", ".join(flattened_tags)
    job_title = job.get("title", "Unknown Role")
    job_desc = job.get("description", "")

    return f"""
You are a career guidance assistant. Based on the user's resume and experience, generate a personalized skill roadmap to help them succeed in the job below.

[User Resume JSON]
{json.dumps(resume_data, indent=2)}

[Skill Tags extracted from resume]
{tag_str}

[Target Job]
Title: {job_title}
Description: {job_desc}

🧠 Objective:
Design a learning roadmap that builds on their current knowledge and fills their learning gaps.

📋 Instructions:
- Organize roadmap by skill categories like: Tools, Concepts, Soft Skills, etc.
- For each skill: include a description, estimated time to learn, and level (Beginner, Intermediate, Advanced)
- Focus on what's most relevant to the job
- Avoid repeating skills they already know unless depth needs improvement

📤 Strictly, respond ONLY in this JSON format:

{{
  "CATEGORY_NAME": {{
    "Skill Name": {{
      "description": "...",
      "time": "3-5 hours",
      "level": "Beginner"
    }},
    ...
  }}
}}
"""
