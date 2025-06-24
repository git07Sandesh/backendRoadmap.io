import numpy as np
from sklearn.cluster import KMeans
import uuid
from supabase import create_client, Client
import os
import json
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# -------------------- FastAPI Router --------------------
router = APIRouter()


class ClusteringRequest(BaseModel):
    user_id: str


# -------------------- Supabase Init --------------------
load_dotenv()
supabase_url = os.getenv("supabase_url")
supabase_key = os.getenv("supabase_key")

if not supabase_url or not supabase_key:
    raise RuntimeError("Supabase URL or Key missing from environment")

supabase = create_client(supabase_url, supabase_key)


# -------------------- Helpers --------------------
def upsert_user_cluster(
    supabase: Client, user_id: str, cluster_uuid: str, similarity: float
):
    existing = (
        supabase.table("user_cluster_map")
        .select("id")
        .eq("user_id", user_id)
        .eq("cluster_id", cluster_uuid)
        .execute()
    )

    if existing.data:
        supabase.table("user_cluster_map").update({"similarity_score": similarity}).eq(
            "user_id", user_id
        ).eq("cluster_id", cluster_uuid).execute()
    else:
        supabase.table("user_cluster_map").insert(
            {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "cluster_id": cluster_uuid,
                "similarity_score": similarity,
            }
        ).execute()


def find_closest_job_title(centroid: list[float], job_embeddings: list[dict]) -> str:
    centroid_vec = np.array(centroid)
    best_score = float("-inf")
    best_title = "General Cluster"

    for job in job_embeddings:
        job_vec = (
            json.loads(job["embedding"])
            if isinstance(job["embedding"], str)
            else job["embedding"]
        )
        job_vec = np.array(job_vec)
        sim = np.dot(centroid_vec, job_vec) / (
            np.linalg.norm(centroid_vec) * np.linalg.norm(job_vec)
        )
        if sim > best_score:
            best_score = sim
            best_title = job["job_title"]

    return best_title


def find_matching_cluster(
    centroid: list[float], existing_clusters: list[dict], threshold: float = 0.6
):
    centroid_vec = np.array(centroid)
    scored_matches = []

    for cluster in existing_clusters:
        cluster_vec = (
            json.loads(cluster["embedding"])
            if isinstance(cluster["embedding"], str)
            else cluster["embedding"]
        )
        cluster_vec = np.array(cluster_vec)
        sim = np.dot(centroid_vec, cluster_vec) / (
            np.linalg.norm(centroid_vec) * np.linalg.norm(cluster_vec)
        )
        scored_matches.append((sim, cluster["cluster_id"], cluster["name"]))

    scored_matches.sort(reverse=True)

    if scored_matches and scored_matches[0][0] >= threshold:
        return scored_matches[0][1], scored_matches[0][2]

    return None, None


# -------------------- Main Logic --------------------
def create_clusters_from_user_sections(user_id: str):
    try:
        section_keys = [
            "education_embedding",
            "work_experience_embedding",
            "projects_embedding",
            "skills_embedding",
        ]
        supabase.table("user_cluster_map").delete().eq("user_id", user_id).execute()

        user = (
            supabase.table("user_resumes")
            .select("*")
            .eq("user_id", user_id)
            .single()
            .execute()
            .data
        )
        print(f"[DEBUG] Raw user resume sections for {user_id}:")

        vectors = []
        sources = []

        for key in section_keys:
            raw = user.get(key)
            print(f"   {key}: {raw}")
            if raw:
                try:
                    vec = json.loads(raw) if isinstance(raw, str) else raw
                    if isinstance(vec, list) and all(
                        isinstance(x, (float, int)) for x in vec
                    ):
                        vectors.append(vec)
                        sources.append(key)
                except Exception as e:
                    print(f"[ERROR] Failed to parse {key}: {e}")

        if len(vectors) < 2:
            raise ValueError(
                "Not enough valid section vectors to cluster (need at least 2)."
            )

        kmeans = KMeans(n_clusters=len(vectors), n_init=10, random_state=42)
        kmeans.fit(vectors)
        centroids = kmeans.cluster_centers_

        existing_clusters = (
            supabase.table("cluster_definitions")
            .select("cluster_id, name, embedding")
            .execute()
            .data
        )
        job_rows = (
            supabase.table("job_embeddings")
            .select("job_title, embedding")
            .execute()
            .data
        )

        centroid_cluster_pairs = []
        used_existing_ids = set()

        for idx, centroid in enumerate(centroids):
            source = sources[idx] if idx < len(sources) else "unknown"
            existing_id, existing_name = find_matching_cluster(
                centroid.tolist(), existing_clusters, threshold=0.6
            )
            print(
                f"→ Centroid {idx+1} best match: {existing_name or 'None'} (from section: {source})"
            )

            if existing_id and existing_id not in used_existing_ids:
                used_existing_ids.add(existing_id)
                print(f"🟡 Reusing existing cluster: {existing_name}")
                centroid_cluster_pairs.append((centroid, existing_id))
                continue

            cluster_id = str(uuid.uuid4())
            cluster_name = find_closest_job_title(centroid.tolist(), job_rows)
            print(f"🟢 Creating new cluster: {cluster_name}")

            supabase.table("cluster_definitions").insert(
                {
                    "cluster_id": cluster_id,
                    "name": cluster_name,
                    "embedding": centroid.tolist(),
                    "created_by": None,
                }
            ).execute()

            centroid_cluster_pairs.append((centroid, cluster_id))
            existing_clusters.append(
                {
                    "cluster_id": cluster_id,
                    "name": cluster_name,
                    "embedding": centroid.tolist(),
                }
            )

        other_users = (
            supabase.table("user_resumes")
            .select("user_id, full_resume_embedding")
            .execute()
            .data
        )
        other_users = [u for u in other_users if u["full_resume_embedding"]]

        for centroid, cluster_id in centroid_cluster_pairs:
            for u in other_users:
                target_embedding = (
                    json.loads(u["full_resume_embedding"])
                    if isinstance(u["full_resume_embedding"], str)
                    else u["full_resume_embedding"]
                )
                sim = 1 - np.linalg.norm(
                    np.array(centroid) - np.array(target_embedding)
                )
                upsert_user_cluster(supabase, u["user_id"], cluster_id, sim)

    except Exception as e:
        print(f"[ERROR] Clustering failed: {str(e)}")
        raise


# -------------------- FastAPI Routes --------------------
@router.post("/generate-new-clusters-from-resume")
def trigger_clustering(request: ClusteringRequest):
    try:
        create_clusters_from_user_sections(user_id=request.user_id)
        return {
            "status": "success",
            "message": "Clusters generated and user mappings updated.",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cluster-graph/{user_id}")
def get_cluster_graph(user_id: str):
    user_clusters = (
        supabase.table("user_cluster_map")
        .select("cluster_id")
        .eq("user_id", user_id)
        .execute()
        .data
    )
    cluster_ids = [uc["cluster_id"] for uc in user_clusters]

    if not cluster_ids:
        return {"name": "root", "children": []}

    clusters = (
        supabase.table("cluster_definitions")
        .select("cluster_id, name")
        .in_("cluster_id", cluster_ids)
        .execute()
        .data
    )
    cluster_name_map = {c["cluster_id"]: c["name"] for c in clusters}

    all_entries = (
        supabase.table("user_cluster_map")
        .select("user_id, cluster_id, similarity_score")
        .in_("cluster_id", cluster_ids)
        .execute()
        .data
    )

    cluster_tree = {}
    for entry in all_entries:
        cid = entry["cluster_id"]
        if cid not in cluster_tree:
            cluster_tree[cid] = []
        cluster_tree[cid].append(
            {"name": entry["user_id"][:6], "value": round(entry["similarity_score"], 2)}
        )

    return {
        "name": "root",
        "children": [
            {"name": cluster_name_map[cid], "children": cluster_tree[cid]}
            for cid in cluster_ids
            if cid in cluster_tree
        ],
    }
