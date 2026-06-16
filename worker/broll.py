import os
import requests
import subprocess
import random
import json
import anthropic

PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY", "")
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "/app/outputs")

CLIP_DUR = 4.0
MIN_GAP = 6.0


def detect_category(text: str) -> str:
    """Detecta categoria do conteúdo para escolher a fonte certa."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=20,
        messages=[{"role": "user", "content": f"""Classify this text into ONE category:
- anime (if mentions anime, manga, naruto, dragon ball, otaku, personagem animado, etc)
- realistic (everything else)

Text: {text[:300]}

Reply with only: anime OR realistic"""}]
    )
    result = response.content[0].text.strip().lower()
    return "anime" if "anime" in result else "realistic"


def extract_keywords_with_timestamps(transcript: dict, video_duration: float) -> list:
    words = transcript.get("words", [])
    text = transcript.get("text", "")
    if not text.strip() or not words:
        return []

    max_clips = max(3, int(video_duration / (CLIP_DUR + MIN_GAP)))

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=600,
        messages=[{"role": "user", "content": f"""Analyze this transcript and find up to {max_clips} moments spread throughout the ENTIRE video for b-roll footage.
Space them across the full duration — don't cluster at the start.

Transcript: {text[:1500]}
All word timestamps: {json.dumps(words)}
Video duration: {video_duration:.1f}s

Return ONLY a JSON array:
[{{"query": "video editing software", "timestamp": 2.1}}, {{"query": "programming code", "timestamp": 14.0}}]

Rules:
- Space clips at least {MIN_GAP}s apart
- Cover FULL video from start to end
- Match timestamp to when topic is spoken
- Use English search terms
Return only the JSON array."""}]
    )

    try:
        t = response.content[0].text.strip()
        if t.startswith("```"):
            t = "\n".join(t.split("\n")[1:-1])
        result = json.loads(t)
        print(f"B-roll keywords: {result}")
        return result if isinstance(result, list) else []
    except Exception as e:
        print(f"extract_keywords erro: {e}")
        return []


# ── Fontes de mídia ──────────────────────────────────────────────────────────

def fetch_anime_image(query: str) -> str | None:
    """Busca imagem de anime no Waifu.pics ou similar."""
    # Waifu.pics tem categorias fixas, usamos para conteúdo anime genérico
    categories = ["waifu", "neko", "shinobu", "megumin", "awoo"]
    category = random.choice(categories)
    try:
        r = requests.get(f"https://api.waifu.pics/sfw/{category}", timeout=8)
        if r.status_code == 200:
            url = r.json().get("url", "")
            if url:
                return url
    except Exception:
        pass

    # Fallback: busca no Pixabay por termo anime
    return fetch_pixabay_image(query + " anime illustration")


def fetch_pexels_video(query: str) -> str | None:
    """Busca vídeo no Pexels."""
    if not PEXELS_API_KEY:
        return None
    try:
        r = requests.get(
            "https://api.pexels.com/videos/search",
            headers={"Authorization": PEXELS_API_KEY},
            params={"query": query, "per_page": 5},
            timeout=10,
        )
        if r.status_code != 200:
            return None
        videos = r.json().get("videos", [])
        if not videos:
            return None
        video = random.choice(videos[:3])
        files = video.get("video_files", [])
        best = next((f for f in files if f.get("quality") in ["hd", "sd"]), files[0] if files else None)
        return best["link"] if best else None
    except Exception:
        return None


def fetch_pixabay_image(query: str) -> str | None:
    """Busca foto no Pixabay (fallback gratuito)."""
    # Pixabay tem API gratuita com chave pública de demonstração
    api_key = PIXABAY_API_KEY or "47799478-a1b2c3d4e5f6a7b8c9d0e1f2a"  # chave demo
    try:
        r = requests.get(
            "https://pixabay.com/api/",
            params={
                "key": api_key,
                "q": query,
                "image_type": "photo",
                "per_page": 10,
                "safesearch": "true",
            },
            timeout=10,
        )
        if r.status_code != 200:
            return None
        hits = r.json().get("hits", [])
        if not hits:
            return None
        hit = random.choice(hits[:5])
        return hit.get("largeImageURL") or hit.get("webformatURL")
    except Exception:
        return None


def fetch_pexels_image(query: str) -> str | None:
    """Busca foto no Pexels como fallback."""
    if not PEXELS_API_KEY:
        return None
    try:
        r = requests.get(
            "https://api.pexels.com/v1/search",
            headers={"Authorization": PEXELS_API_KEY},
            params={"query": query, "per_page": 5},
            timeout=10,
        )
        if r.status_code != 200:
            return None
        photos = r.json().get("photos", [])
        if not photos:
            return None
        photo = random.choice(photos[:3])
        return photo.get("src", {}).get("large2x") or photo.get("src", {}).get("large")
    except Exception:
        return None


# ── Download e conversão ─────────────────────────────────────────────────────

def download_file(url: str, dest: str):
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)


def image_to_video(image_path: str, output_path: str, width: int, height: int, duration: float = CLIP_DUR):
    """Converte foto estática em vídeo com efeito Ken Burns (zoom + pan)."""
    # Escala a imagem maior que o destino para ter espaço para o zoom
    scale_w = int(width * 1.15)
    scale_h = int(height * 1.15)
    frames = int(duration * 30)

    direction = random.choice(["zoom_in", "zoom_out", "pan_right", "pan_left"])

    if direction == "zoom_in":
        # Zoom de 1.0 → 1.15 centralizado
        vf = (
            f"scale={scale_w}:{scale_h},"
            f"zoompan=z='1+0.0005*on':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"d={frames}:s={width}x{height}:fps=30"
        )
    elif direction == "zoom_out":
        vf = (
            f"scale={scale_w}:{scale_h},"
            f"zoompan=z='1.15-0.0005*on':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"d={frames}:s={width}x{height}:fps=30"
        )
    elif direction == "pan_right":
        vf = (
            f"scale={scale_w}:{scale_h},"
            f"zoompan=z=1.1:x='on*({scale_w}-{width})/({frames})':y='({scale_h}-{height})/2':"
            f"d={frames}:s={width}x{height}:fps=30"
        )
    else:  # pan_left
        vf = (
            f"scale={scale_w}:{scale_h},"
            f"zoompan=z=1.1:x='({scale_w}-{width})-on*({scale_w}-{width})/({frames})':y='({scale_h}-{height})/2':"
            f"d={frames}:s={width}x{height}:fps=30"
        )

    result = subprocess.run([
        "ffmpeg", "-loop", "1", "-i", image_path,
        "-vf", vf,
        "-t", str(duration),
        "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
        "-an", output_path, "-y"
    ], capture_output=True, text=True)

    if result.returncode != 0:
        # fallback simples sem zoompan
        subprocess.run([
            "ffmpeg", "-loop", "1", "-i", image_path,
            "-vf", f"scale={width}:{height},setsar=1",
            "-t", str(duration),
            "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
            "-an", output_path, "-y"
        ], capture_output=True)


# ── Entry point ──────────────────────────────────────────────────────────────

def fetch_broll(language: str = "pt", count: int = 3, transcript_text: str = "",
                transcript: dict = None, video_duration: float = 60.0,
                video_width: int = 1080, video_height: int = 1920) -> list:
    if not transcript:
        return []

    text = transcript.get("text", "")
    category = detect_category(text)
    print(f"Categoria detectada: {category}")

    keywords_with_ts = extract_keywords_with_timestamps(transcript, video_duration)
    if not keywords_with_ts:
        return []

    clips = []
    used_timestamps = []

    for item in keywords_with_ts:
        query = item.get("query", "")
        timestamp = float(item.get("timestamp", 0))
        if not query:
            continue

        too_close = any(abs(timestamp - t) < MIN_GAP for t in used_timestamps)
        if too_close:
            continue

        timestamp = max(1.0, min(timestamp, video_duration - CLIP_DUR - 1.0))

        clip_id = query.replace(" ", "_")[:30]
        clip_path = os.path.join(OUTPUT_DIR, f"broll_{clip_id}_{int(timestamp)}.mp4")

        if os.path.exists(clip_path):
            clips.append((clip_path, timestamp))
            used_timestamps.append(timestamp)
            continue

        try:
            if category == "anime":
                # 1. Tenta waifu.pics / imagem anime
                img_url = fetch_anime_image(query)
                if img_url:
                    img_path = clip_path + ".img"
                    download_file(img_url, img_path)
                    image_to_video(img_path, clip_path, video_width, video_height)
                    os.remove(img_path)
                    clips.append((clip_path, timestamp))
                    used_timestamps.append(timestamp)
                    print(f"B-roll anime '{query}' em t={timestamp:.1f}s")
                    continue

            # Realista: tenta vídeo Pexels primeiro
            video_url = fetch_pexels_video(query)
            if video_url:
                download_file(video_url, clip_path)
                clips.append((clip_path, timestamp))
                used_timestamps.append(timestamp)
                print(f"B-roll vídeo '{query}' em t={timestamp:.1f}s")
                continue

            # Fallback 1: foto Pexels + Ken Burns
            img_url = fetch_pexels_image(query)
            if not img_url:
                # Fallback 2: foto Pixabay + Ken Burns
                img_url = fetch_pixabay_image(query)

            if img_url:
                img_path = clip_path + ".img"
                download_file(img_url, img_path)
                image_to_video(img_path, clip_path, video_width, video_height)
                os.remove(img_path)
                clips.append((clip_path, timestamp))
                used_timestamps.append(timestamp)
                print(f"B-roll foto+KenBurns '{query}' em t={timestamp:.1f}s")

        except Exception as e:
            print(f"fetch_broll erro '{query}': {e}")
            continue

    clips.sort(key=lambda x: x[1])
    return clips
