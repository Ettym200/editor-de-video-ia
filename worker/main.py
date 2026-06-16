import json
import os
import time
import redis
from dotenv import load_dotenv
from processor import process_video

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
r = redis.from_url(REDIS_URL)


def update_status(job_id: str, status: str, progress: int, message: str = ""):
    r.set(f"job:{job_id}:status", json.dumps({
        "status": status,
        "progress": progress,
        "message": message,
    }))


def run():
    print("Worker iniciado, aguardando jobs...")
    while True:
        job_data = r.brpop("video_jobs", timeout=5)
        if not job_data:
            continue

        payload = json.loads(job_data[1])
        job_id = payload["job_id"]

        print(f"Processando job {job_id}")
        try:
            update_status(job_id, "processing", 10, "Iniciando processamento")
            process_video(job_id, payload, update_status)
            update_status(job_id, "completed", 100, "Vídeo pronto!")
            print(f"Job {job_id} concluído")
        except Exception as e:
            print(f"Erro no job {job_id}: {e}")
            update_status(job_id, "error", 0, str(e))


if __name__ == "__main__":
    run()
