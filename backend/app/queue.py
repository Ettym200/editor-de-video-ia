import json
import os
import redis
from dotenv import load_dotenv

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
r = redis.from_url(REDIS_URL)


def enqueue_job(job_id: str, input_path: str, language: str, style: str, broll: bool,
                user_prompt: str = "", clarification_answers: dict = {}, broll_position: str = "fullscreen",
                custom_image_paths: list = []):
    payload = {
        "job_id": job_id,
        "input_path": input_path,
        "language": language,
        "style": style,
        "broll": broll,
        "user_prompt": user_prompt,
        "clarification_answers": clarification_answers,
        "broll_position": broll_position,
        "custom_image_paths": custom_image_paths,
    }
    r.set(f"job:{job_id}:status", json.dumps({"status": "queued", "progress": 0}))
    r.lpush("video_jobs", json.dumps(payload))


def get_job_status(job_id: str):
    data = r.get(f"job:{job_id}:status")
    if not data:
        return None
    return json.loads(data)
