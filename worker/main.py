import json
import os
import time
import redis
from dotenv import load_dotenv
from processor import process_video

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
r = redis.from_url(REDIS_URL)


def update_status(job_id: str, status: str, progress: int, message: str = "", extra: dict = None):
    data = {"status": status, "progress": progress, "message": message}
    if extra:
        data.update(extra)
    r.set(f"job:{job_id}:status", json.dumps(data))


def run():
    print("Worker iniciado, aguardando jobs...")
    while True:
        try:
            job_data = r.brpop("video_jobs", timeout=5)
        except Exception as e:
            print(f"Redis timeout/erro, reconectando: {e}")
            time.sleep(2)
            continue
        if not job_data:
            continue

        payload = json.loads(job_data[1])
        job_id = payload["job_id"]

        print(f"Processando job {job_id}")
        try:
            update_status(job_id, "processing", 10, "Iniciando processamento")
            cost = process_video(job_id, payload, update_status)
            update_status(job_id, "completed", 100, "Vídeo pronto!", extra={"cost": cost})
            print(f"Job {job_id} concluído")
        except Exception as e:
            print(f"Erro no job {job_id}: {e}")
            update_status(job_id, "error", 0, str(e))


if __name__ == "__main__":
    run()
