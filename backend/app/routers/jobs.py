from fastapi import APIRouter, HTTPException
from app.queue import get_job_status

router = APIRouter()


@router.get("/{job_id}")
def job_status(job_id: str):
    status = get_job_status(job_id)
    if not status:
        raise HTTPException(404, "Job não encontrado")
    return status
