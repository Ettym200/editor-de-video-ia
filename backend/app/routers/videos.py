import uuid
import os
import aiofiles
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from app.queue import enqueue_job

router = APIRouter()

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "/app/uploads")
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "/app/outputs")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)


@router.post("/upload")
async def upload_video(
    file: UploadFile = File(...),
    language: str = Form("pt"),
    style: str = Form("modern"),
    broll: bool = Form(True),
):
    if not file.filename.endswith((".mp4", ".mov", ".avi", ".mkv")):
        raise HTTPException(400, "Formato de vídeo não suportado")

    job_id = str(uuid.uuid4())
    input_path = os.path.join(UPLOAD_DIR, f"{job_id}_input.mp4")

    async with aiofiles.open(input_path, "wb") as f:
        content = await file.read()
        await f.write(content)

    enqueue_job(job_id, input_path, language, style, broll)

    return {"job_id": job_id, "status": "queued"}


@router.get("/{job_id}/download")
def download_video(job_id: str):
    output_path = os.path.join(OUTPUT_DIR, f"{job_id}_output.mp4")
    if not os.path.exists(output_path):
        raise HTTPException(404, "Vídeo não encontrado")
    return FileResponse(output_path, media_type="video/mp4", filename="video_editado.mp4")
