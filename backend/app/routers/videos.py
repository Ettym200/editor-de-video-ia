import uuid
import os
import json
import aiofiles
import anthropic
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from app.queue import enqueue_job

router = APIRouter()

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "/app/uploads")
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "/app/outputs")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)


class AnalyzePromptRequest(BaseModel):
    prompt: str


class AnalyzePromptResponse(BaseModel):
    needs_clarification: bool
    questions: list[str]
    summary: str
    needs_position_picker: bool = False


@router.post("/analyze-prompt", response_model=AnalyzePromptResponse)
async def analyze_prompt(body: AnalyzePromptRequest):
    """Analisa o prompt do cliente e retorna perguntas de clarificação se necessário."""
    if not body.prompt.strip():
        return AnalyzePromptResponse(needs_clarification=False, questions=[], summary="")

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=600,
        messages=[{"role": "user", "content": f"""You are analyzing a video editing instruction from a client.

Client instruction: "{body.prompt}"

Determine if this instruction contains ambiguous requests that need clarification before processing.
Ambiguous examples: "remove errors", "identify problems", "cut bad parts", "improve quality", "fix mistakes"
Clear examples: "search for Rio de Janeiro images", "add Copa do Mundo b-roll", "use yellow subtitles"

Also detect if the instruction mentions a specific POSITION or LOCATION for b-roll images/videos
(e.g., "canto superior direito", "top-right corner", "no centro", "no lado esquerdo", "corner", "side", etc.)

Return a JSON object:
{{
  "needs_clarification": true/false,
  "questions": ["question 1 in Portuguese", "question 2 in Portuguese"],
  "summary": "brief summary in Portuguese of what will be done with this prompt",
  "needs_position_picker": true/false
}}

If needs_clarification is true, write 1-3 specific questions in Portuguese to understand exactly what the client wants.
If false, questions should be empty array.
Set needs_position_picker to true if a specific visual position/location for b-roll is mentioned.
Return only the JSON object."""}]
    )

    try:
        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = "\n".join(text.split("\n")[1:-1])
        data = json.loads(text)
        return AnalyzePromptResponse(
            needs_clarification=data.get("needs_clarification", False),
            questions=data.get("questions", []),
            summary=data.get("summary", ""),
            needs_position_picker=data.get("needs_position_picker", False),
        )
    except Exception:
        return AnalyzePromptResponse(needs_clarification=False, questions=[], summary="")


@router.post("/upload")
async def upload_video(
    file: UploadFile = File(...),
    language: str = Form("pt"),
    style: str = Form("modern"),
    broll: bool = Form(True),
    user_prompt: str = Form(""),
    clarification_answers: str = Form("{}"),
    broll_position: str = Form("fullscreen"),
):
    if not file.filename.endswith((".mp4", ".mov", ".avi", ".mkv")):
        raise HTTPException(400, "Formato de vídeo não suportado")

    job_id = str(uuid.uuid4())
    input_path = os.path.join(UPLOAD_DIR, f"{job_id}_input.mp4")

    async with aiofiles.open(input_path, "wb") as f:
        content = await file.read()
        await f.write(content)

    try:
        answers = json.loads(clarification_answers)
    except Exception:
        answers = {}

    enqueue_job(job_id, input_path, language, style, broll, user_prompt, answers, broll_position)

    return {"job_id": job_id, "status": "queued"}


@router.get("/{job_id}/download")
def download_video(job_id: str):
    output_path = os.path.join(OUTPUT_DIR, f"{job_id}_output.mp4")
    if not os.path.exists(output_path):
        raise HTTPException(404, "Vídeo não encontrado")
    return FileResponse(output_path, media_type="video/mp4", filename="video_editado.mp4")
