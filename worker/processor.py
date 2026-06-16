import os
import json
import re
import subprocess
import anthropic
from broll import fetch_broll

OUTPUT_DIR = os.getenv("OUTPUT_DIR", "/app/outputs")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")


def process_video(job_id: str, payload: dict, update_status):
    input_path = payload["input_path"]
    language = payload["language"]
    style = payload["style"]
    use_broll = payload["broll"]
    output_path = os.path.join(OUTPUT_DIR, f"{job_id}_output.mp4")

    update_status(job_id, "processing", 20, "Removendo silêncios...")
    cut_path = os.path.join(OUTPUT_DIR, f"{job_id}_cut.mp4")
    rough_cut(input_path, cut_path)

    update_status(job_id, "processing", 40, "Transcrevendo áudio...")
    transcript_path = os.path.join(OUTPUT_DIR, f"{job_id}_transcript.json")
    transcribe(cut_path, transcript_path, language)

    broll_clips = []
    if use_broll:
        update_status(job_id, "processing", 50, "Buscando b-roll...")
        with open(transcript_path) as f:
            transcript_data = json.load(f)
        cut_duration = get_video_duration(cut_path)
        probe = subprocess.run([
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height", "-of", "csv=p=0", cut_path
        ], capture_output=True, text=True)
        try:
            vid_w, vid_h = [int(x) for x in probe.stdout.strip().split(",")]
        except Exception:
            vid_w, vid_h = 1080, 1920
        broll_clips = fetch_broll(language, transcript=transcript_data, video_duration=cut_duration,
                                   video_width=vid_w, video_height=vid_h)

    update_status(job_id, "processing", 65, "Aplicando legendas e efeitos...")
    with open(transcript_path) as f:
        transcript = json.load(f)

    subtitle_path = os.path.join(OUTPUT_DIR, f"{job_id}.srt")
    generate_srt(transcript, subtitle_path)

    update_status(job_id, "processing", 80, "Renderizando vídeo final...")
    apply_effects(cut_path, subtitle_path, style, broll_clips, output_path)

    for path in [cut_path, subtitle_path, transcript_path]:
        if os.path.exists(path):
            os.remove(path)


def rough_cut(input_path: str, output_path: str):
    """Remove silêncios e aplica punch-in zoom no início de cada corte."""
    result = subprocess.run([
        "ffmpeg", "-i", input_path,
        "-af", "silencedetect=noise=-35dB:d=0.5",
        "-f", "null", "-"
    ], capture_output=True, text=True)

    log = result.stderr
    silence_starts = [float(x) for x in re.findall(r"silence_start: (\S+)", log)]
    silence_ends = [float(x) for x in re.findall(r"silence_end: (\S+)", log)]
    duration = get_video_duration(input_path)

    if not silence_starts:
        subprocess.run(["cp", input_path, output_path], check=True)
        return

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

    # Extrai cada segmento com punch-in zoom nos primeiros 0.3s
    tmp_dir = output_path + "_segments"
    os.makedirs(tmp_dir, exist_ok=True)
    segment_files = []
    concat_list = os.path.join(tmp_dir, "list.txt")

    ZOOM_DUR = 0.3   # duração do zoom em segundos
    ZOOM_MAX = 1.06  # zoom máximo (6%)

    for i, (start, end) in enumerate(keep):
        seg_path = os.path.join(tmp_dir, f"seg_{i:04d}.mp4")
        seg_dur = end - start

        # Zoom in nos primeiros ZOOM_DUR segundos, depois volta a 1.0
        # Usa scale+crop que é muito mais rápido que zoompan
        zoom_filter = (
            f"scale=iw*{ZOOM_MAX}:ih*{ZOOM_MAX},"
            f"crop=iw/{ZOOM_MAX}:ih/{ZOOM_MAX}:"
            f"x='(iw-ow)/2*(1-min(t/{ZOOM_DUR},1))':"
            f"y='(ih-oh)/2*(1-min(t/{ZOOM_DUR},1))'"
            if seg_dur > ZOOM_DUR else "null"
        )

        r = subprocess.run([
            "ffmpeg",
            "-ss", str(start), "-t", str(seg_dur),
            "-i", input_path,
            "-vf", zoom_filter,
            "-c:v", "libx264", "-preset", "fast",
            "-c:a", "aac",
            seg_path, "-y"
        ], capture_output=True, text=True)

        if r.returncode == 0:
            segment_files.append(seg_path)
        else:
            # fallback sem zoom
            subprocess.run([
                "ffmpeg",
                "-ss", str(start), "-t", str(seg_dur),
                "-i", input_path,
                "-c:v", "libx264", "-preset", "fast", "-c:a", "aac",
                seg_path, "-y"
            ], capture_output=True)
            if os.path.exists(seg_path):
                segment_files.append(seg_path)

    if not segment_files:
        subprocess.run(["cp", input_path, output_path], check=True)
        import shutil; shutil.rmtree(tmp_dir, ignore_errors=True)
        return

    # Concatena todos os segmentos
    with open(concat_list, "w") as f:
        for seg in segment_files:
            f.write(f"file '{seg}'\n")

    result = subprocess.run([
        "ffmpeg", "-f", "concat", "-safe", "0",
        "-i", concat_list,
        "-c:v", "libx264", "-preset", "fast", "-c:a", "aac",
        output_path, "-y"
    ], capture_output=True, text=True)

    import shutil
    shutil.rmtree(tmp_dir, ignore_errors=True)

    if result.returncode != 0:
        print(f"rough_cut concat erro: {result.stderr[-300:]}")
        subprocess.run(["cp", input_path, output_path], check=True)


def transcribe(input_path: str, transcript_path: str, language: str):
    """Usa ffmpeg para extrair áudio e whisper para transcrever."""
    try:
        import whisper
        audio_path = transcript_path.replace(".json", ".wav")
        subprocess.run([
            "ffmpeg", "-i", input_path, "-ar", "16000", "-ac", "1",
            audio_path, "-y"
        ], capture_output=True, check=True)

        model = whisper.load_model("small")
        result = model.transcribe(audio_path, language=language if language != "auto" else None, word_timestamps=True)

        words = []
        for seg in result.get("segments", []):
            for w in seg.get("words", []):
                words.append({"word": w["word"], "start": w["start"], "end": w["end"]})

        with open(transcript_path, "w") as f:
            json.dump({"words": words, "text": result.get("text", "")}, f)

        if os.path.exists(audio_path):
            os.remove(audio_path)
    except Exception as e:
        print(f"transcribe erro (usando fallback vazio): {e}")
        with open(transcript_path, "w") as f:
            json.dump({"words": [], "text": ""}, f)


def generate_srt(transcript: dict, srt_path: str):
    """Gera arquivo .srt a partir do transcript."""
    words = transcript.get("words", [])
    if not words:
        open(srt_path, "w").close()
        return

    # Agrupa palavras em legendas de ~5 palavras ou 3 segundos
    segments = []
    chunk = []
    chunk_start = None

    for w in words:
        if chunk_start is None:
            chunk_start = w["start"]
        chunk.append(w["word"])
        duration = w["end"] - chunk_start
        if len(chunk) >= 5 or duration >= 3.0:
            segments.append((chunk_start, w["end"], " ".join(chunk).strip()))
            chunk = []
            chunk_start = None

    if chunk and chunk_start is not None:
        segments.append((chunk_start, words[-1]["end"], " ".join(chunk).strip()))

    def fmt(t):
        h = int(t // 3600)
        m = int((t % 3600) // 60)
        s = int(t % 60)
        ms = int((t % 1) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    with open(srt_path, "w", encoding="utf-8") as f:
        for i, (start, end, text) in enumerate(segments, 1):
            f.write(f"{i}\n{fmt(start)} --> {fmt(end)}\n{text}\n\n")


def apply_effects(input_path: str, subtitle_path: str, style: str, broll_clips: list, output_path: str):
    """Aplica color grade, zoom, fade, legendas e b-roll via FFmpeg."""

    duration = get_video_duration(input_path)
    fade_dur = min(0.5, duration * 0.05)

    style_filters = {
        "modern":    "eq=contrast=1.1:brightness=0.02:saturation=1.2",
        "cinematic": "eq=contrast=1.2:brightness=-0.05:saturation=0.85",
        "minimal":   "eq=contrast=1.0:brightness=0.0:saturation=0.9",
        "energetic": "eq=contrast=1.3:brightness=0.05:saturation=1.4",
    }
    color = style_filters.get(style, style_filters["modern"])

    # Fade in e fade out
    fade = f"fade=t=in:st=0:d={fade_dur:.2f},fade=t=out:st={duration-fade_dur:.2f}:d={fade_dur:.2f}"

    has_subs = os.path.exists(subtitle_path) and os.path.getsize(subtitle_path) > 0

    sub_styles = {
        "modern":    "FontName=Arial,FontSize=14,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=2,Bold=1,Alignment=10,MarginV=120",
        "cinematic": "FontName=Georgia,FontSize=14,PrimaryColour=&H0000D7FF,OutlineColour=&H00000000,Outline=2,Bold=0,Alignment=10,MarginV=120",
        "minimal":   "FontName=Helvetica,FontSize=12,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=1,Bold=0,Alignment=10,MarginV=120",
        "energetic": "FontName=Impact,FontSize=16,PrimaryColour=&H0000FFFF,OutlineColour=&H00000000,Outline=3,Bold=1,Alignment=10,MarginV=120",
    }
    sub_style = sub_styles.get(style, sub_styles["modern"])

    if broll_clips:
        clip_dur = 4.0

        # Detecta dimensões do vídeo principal
        probe = subprocess.run([
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=p=0", input_path
        ], capture_output=True, text=True)
        try:
            w, h = [int(x) for x in probe.stdout.strip().split(",")]
        except Exception:
            w, h = 1080, 1920

        inputs_list = ["-i", input_path]
        filter_parts = [f"[0:v]{color}[base]"]

        prev = "[base]"
        for i, (broll_path, timestamp) in enumerate(broll_clips):
            inputs_list += ["-i", broll_path]
            idx = i + 1
            broll_actual_dur = min(clip_dur, get_video_duration(broll_path))
            st = timestamp

            # Escala e corta o b-roll para preencher exatamente as dimensões do vídeo principal
            filter_parts.append(
                f"[{idx}:v]scale={w}:{h}:force_original_aspect_ratio=increase,"
                f"crop={w}:{h},setsar=1[b{idx}]"
            )
            out_label = f"[v{idx}]"
            filter_parts.append(
                f"{prev}[b{idx}]overlay=0:0:enable='between(t,{st:.2f},{st+broll_actual_dur:.2f})'{out_label}"
            )
            prev = out_label

        if has_subs:
            filter_parts.append(f"{prev}subtitles='{subtitle_path}':force_style='{sub_style}'[out]")
            out_map = "[out]"
        else:
            out_map = prev

        filter_complex = ";".join(filter_parts)
        maps = ["-map", out_map, "-map", "0:a"]

        result = subprocess.run([
            "ffmpeg", *inputs_list,
            "-filter_complex", filter_complex,
            *maps,
            "-c:v", "libx264", "-preset", "fast", "-c:a", "aac",
            output_path, "-y"
        ], capture_output=True, text=True)

        if result.returncode == 0:
            return
        print(f"apply_effects broll erro: {result.stderr[-500:]}")

    # Sem b-roll
    filters = [color, fade]
    if has_subs:
        filters.append(f"subtitles='{subtitle_path}':force_style='{sub_style}'")
    vf = ",".join(filters)

    result = subprocess.run([
        "ffmpeg", "-i", input_path,
        "-vf", vf,
        "-c:v", "libx264", "-preset", "fast", "-c:a", "aac",
        output_path, "-y"
    ], capture_output=True, text=True)

    if result.returncode != 0:
        print(f"apply_effects erro (zoom): {result.stderr[-300:]}")
        # fallback sem zoom (mais rápido)
        vf_simple = color
        if has_subs:
            vf_simple += f",subtitles='{subtitle_path}':force_style='{sub_style}'"
        subprocess.run([
            "ffmpeg", "-i", input_path, "-vf", vf_simple,
            "-c:v", "libx264", "-c:a", "aac", output_path, "-y"
        ], capture_output=True)


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
