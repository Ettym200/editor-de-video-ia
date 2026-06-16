import os
import json
import re
import subprocess
import anthropic
from broll import fetch_broll

OUTPUT_DIR = os.getenv("OUTPUT_DIR", "/app/outputs")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
HYPERFRAMES_BIN = os.getenv("HYPERFRAMES_BIN", "hyperframes")


def process_video(job_id: str, payload: dict, update_status):
    input_path = payload["input_path"]
    language = payload["language"]
    style = payload["style"]
    use_broll = payload["broll"]
    output_path = os.path.join(OUTPUT_DIR, f"{job_id}_output.mp4")

    update_status(job_id, "processing", 15, "Transcrevendo áudio...")
    transcript_path = os.path.join(OUTPUT_DIR, f"{job_id}_transcript.json")
    transcribe(input_path, transcript_path, language)

    update_status(job_id, "processing", 30, "Removendo silêncios e erros...")
    cut_path = os.path.join(OUTPUT_DIR, f"{job_id}_cut.mp4")
    rough_cut(input_path, cut_path)

    broll_clips = []
    if use_broll:
        update_status(job_id, "processing", 50, "Buscando clipes de b-roll...")
        broll_clips = fetch_broll(language)

    update_status(job_id, "processing", 65, "Gerando animações e motion graphics...")
    duration = get_video_duration(cut_path)
    composition_path = os.path.join(OUTPUT_DIR, f"{job_id}_comp.html")
    animated_path = os.path.join(OUTPUT_DIR, f"{job_id}_animated.mp4")
    generate_composition(cut_path, transcript_path, duration, style, broll_clips, composition_path, language)
    render_composition(composition_path, animated_path)

    update_status(job_id, "processing", 90, "Finalizando...")
    merge_audio(cut_path, animated_path, output_path)

    for path in [cut_path, animated_path, composition_path, transcript_path]:
        if os.path.exists(path):
            os.remove(path)


def rough_cut(input_path: str, output_path: str):
    """Remove silêncios usando silencedetect + concat demuxer."""

    # 1. Detecta silêncios
    result = subprocess.run([
        "ffmpeg", "-i", input_path,
        "-af", "silencedetect=noise=-35dB:d=0.5",
        "-f", "null", "-"
    ], capture_output=True, text=True)

    log = result.stderr

    # 2. Extrai intervalos de silêncio
    silence_starts = [float(x) for x in re.findall(r"silence_start: (\S+)", log)]
    silence_ends = [float(x) for x in re.findall(r"silence_end: (\S+)", log)]

    duration = get_video_duration(input_path)

    if not silence_starts:
        # Sem silêncios detectados — copia direto
        subprocess.run(["cp", input_path, output_path], check=True)
        return

    # 3. Monta intervalos de fala (inverso dos silêncios)
    keep = []
    prev = 0.0
    for start, end in zip(silence_starts, silence_ends):
        if start - prev > 0.3:
            keep.append((prev, start))
        prev = end
    if duration - prev > 0.3:
        keep.append((prev, duration))

    if not keep:
        subprocess.run(["cp", input_path, output_path], check=True)
        return

    # 4. Monta filtergraph select
    expr_parts = [f"between(t,{s:.3f},{e:.3f})" for s, e in keep]
    expr = "+".join(expr_parts)

    result = subprocess.run([
        "ffmpeg", "-i", input_path,
        "-filter_complex",
        f"[0:v]select='{expr}',setpts=N/FRAME_RATE/TB[v];"
        f"[0:a]aselect='{expr}',asetpts=N/SR/TB[a]",
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-c:a", "aac",
        output_path, "-y"
    ], capture_output=True, text=True)

    if result.returncode != 0:
        print(f"rough_cut erro: {result.stderr[-500:]}")
        subprocess.run(["cp", input_path, output_path], check=True)


def transcribe(input_path: str, transcript_path: str, language: str):
    """Usa HyperFrames para transcrever o vídeo."""
    result = subprocess.run([
        HYPERFRAMES_BIN, "transcribe", input_path,
        "--language", language, "--json",
    ], capture_output=True, text=True)

    default = os.path.join(os.path.dirname(input_path), "transcript.json")
    if os.path.exists(default):
        os.rename(default, transcript_path)
    elif result.stdout.strip():
        with open(transcript_path, "w") as f:
            f.write(result.stdout)
    else:
        with open(transcript_path, "w") as f:
            json.dump({"words": [], "text": ""}, f)


def generate_composition(video_path, transcript_path, duration, style, broll_clips, composition_path, language):
    """Claude gera HTML de composição para HyperFrames."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    with open(transcript_path) as f:
        transcript = json.load(f)

    words = transcript.get("words", [])
    text = transcript.get("text", "")[:500]

    style_guide = {
        "modern": "Clean white text, smooth fade transitions, blue accents",
        "cinematic": "Golden text, dramatic scale animations, dark overlays",
        "minimal": "Minimal white text, subtle animations",
        "energetic": "Bold colorful text, fast zoom animations",
    }.get(style, "modern clean style")

    broll_info = f"B-roll clips available: {broll_clips}" if broll_clips else ""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8192,
        messages=[{"role": "user", "content": f"""Generate a HyperFrames HTML composition for video editing.

VIDEO: duration={duration:.1f}s, language={language}
STYLE: {style_guide}
TRANSCRIPT: {text}
WORD TIMESTAMPS (first 15): {json.dumps(words[:15])}
{broll_info}

Generate complete HTML using the HyperFrames blank template:
- viewport 1920x1080
- GSAP from CDN for animations
- Main video: id="a-roll" src="__VIDEO_SRC__" data-duration="{duration:.1f}" data-track-index="0"
- Audio: id="a-roll-audio" src="__VIDEO_SRC__" data-track-index="2"
- Add subtitle overlays synced to speech using data-start/data-duration attributes
- Add zoom-in effects on key moments with GSAP
- Add lower-third text for important phrases
- Use data-composition-id="main" on root div

Return ONLY the complete HTML, no explanation."""}]
    )

    html = response.content[0].text.strip()
    if html.startswith("```"):
        html = "\n".join(html.split("\n")[1:-1])
    # Usa file:// para o Chrome headless conseguir acessar o arquivo local
    html = html.replace("__VIDEO_SRC__", f"file://{video_path}").replace("__VIDEO_DURATION__", str(duration))
    html = html.replace(f'src="{video_path}"', f'src="file://{video_path}"')
    html = html.replace(f"src='{video_path}'", f"src='file://{video_path}'")

    with open(composition_path, "w", encoding="utf-8") as f:
        f.write(html)


def render_composition(composition_path: str, output_path: str):
    """Renderiza HTML com HyperFrames servindo vídeo via HTTP local."""
    import shutil
    import threading
    import http.server
    import socketserver

    comp_dir = composition_path.replace(".html", "_dir")
    os.makedirs(comp_dir, exist_ok=True)

    port = 18765

    class RangeHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
        """HTTP handler com suporte a Range requests (necessário para vídeo no Chrome)."""

        def do_GET(self):
            path = self.translate_path(self.path)
            if not os.path.isfile(path):
                self.send_error(404)
                return

            file_size = os.path.getsize(path)
            range_header = self.headers.get("Range")

            if range_header:
                # Parse "bytes=start-end"
                try:
                    byte_range = range_header.replace("bytes=", "")
                    start_str, end_str = byte_range.split("-")
                    start = int(start_str) if start_str else 0
                    end = int(end_str) if end_str else file_size - 1
                    end = min(end, file_size - 1)
                    length = end - start + 1

                    self.send_response(206)
                    self.send_header("Content-Type", self.guess_type(path))
                    self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
                    self.send_header("Content-Length", str(length))
                    self.send_header("Accept-Ranges", "bytes")
                    self.end_headers()

                    with open(path, "rb") as f:
                        f.seek(start)
                        remaining = length
                        while remaining > 0:
                            chunk = f.read(min(65536, remaining))
                            if not chunk:
                                break
                            self.wfile.write(chunk)
                            remaining -= len(chunk)
                except Exception:
                    self.send_error(416)
            else:
                self.send_response(200)
                self.send_header("Content-Type", self.guess_type(path))
                self.send_header("Content-Length", str(file_size))
                self.send_header("Accept-Ranges", "bytes")
                self.end_headers()
                with open(path, "rb") as f:
                    while True:
                        chunk = f.read(65536)
                        if not chunk:
                            break
                        self.wfile.write(chunk)

        def log_message(self, format, *args):
            pass  # silencia logs do servidor HTTP

    class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
        daemon_threads = True

    os.chdir("/app")
    httpd = ThreadedHTTPServer(("0.0.0.0", port), RangeHTTPRequestHandler)

    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()

    # Atualiza o HTML para usar http://localhost
    with open(composition_path, "r", encoding="utf-8") as f:
        html = f.read()

    html = html.replace("file:///app/", f"http://localhost:{port}/")
    html = html.replace("/app/outputs/", f"http://localhost:{port}/outputs/")
    html = html.replace("/app/uploads/", f"http://localhost:{port}/uploads/")

    index_path = os.path.join(comp_dir, "index.html")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(html)

    result = subprocess.run([
        HYPERFRAMES_BIN, "render", comp_dir,
        "--output", output_path,
        "--quality", "standard", "--fps", "30",
        "--browser-arg", "--no-sandbox",
    ], capture_output=True, text=True)

    httpd.shutdown()
    shutil.rmtree(comp_dir, ignore_errors=True)

    if result.returncode != 0:
        raise RuntimeError(f"HyperFrames render falhou: {result.stderr[-500:]}")


def merge_audio(original: str, animated: str, output_path: str):
    """Merge áudio do vídeo cortado com o vídeo animado."""
    result = subprocess.run([
        "ffmpeg", "-i", animated, "-i", original,
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "copy", "-c:a", "aac", "-shortest",
        output_path, "-y"
    ], capture_output=True, text=True)

    if result.returncode != 0:
        subprocess.run(["cp", animated, output_path], check=True)


def add_animations(input_path: str, output_path: str, style: str, broll_clips: list):
    """Aplica color grade por estilo e insere b-roll se disponível."""

    style_filters = {
        "modern":     "eq=contrast=1.1:brightness=0.02:saturation=1.2",
        "cinematic":  "eq=contrast=1.2:brightness=-0.05:saturation=0.85",
        "minimal":    "eq=contrast=1.0:brightness=0.0:saturation=0.9",
        "energetic":  "eq=contrast=1.3:brightness=0.05:saturation=1.4",
    }
    color_filter = style_filters.get(style, style_filters["modern"])

    if broll_clips:
        duration = get_video_duration(input_path)
        mid = duration / 2
        broll = broll_clips[0]
        broll_dur = min(5.0, get_video_duration(broll))

        result = subprocess.run([
            "ffmpeg",
            "-i", input_path,
            "-i", broll,
            "-filter_complex",
            f"[0:v]{color_filter}[main];"
            f"[1:v]scale=1920:1080:force_original_aspect_ratio=decrease,"
            f"pad=1920:1080:(ow-iw)/2:(oh-ih)/2[broll];"
            f"[main][broll]overlay=enable='between(t,{mid},{mid+broll_dur})'[v]",
            "-map", "[v]", "-map", "0:a",
            "-c:v", "libx264", "-c:a", "aac",
            output_path, "-y"
        ], capture_output=True, text=True)

        if result.returncode == 0:
            return

    # Sem b-roll
    result = subprocess.run([
        "ffmpeg", "-i", input_path,
        "-vf", color_filter,
        "-c:a", "copy",
        output_path, "-y"
    ], capture_output=True, text=True)

    if result.returncode != 0:
        subprocess.run(["cp", input_path, output_path], check=True)


def get_video_duration(video_path: str) -> float:
    result = subprocess.run([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        video_path
    ], capture_output=True, text=True)
    try:
        return float(result.stdout.strip())
    except Exception:
        return 60.0
