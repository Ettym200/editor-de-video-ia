import os
import requests
import subprocess
import random

PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "/app/outputs")

STYLE_QUERIES = {
    "pt": ["business", "technology", "success", "city"],
    "en": ["business", "technology", "success", "city"],
    "it": ["italy", "business", "technology"],
    "hu": ["hungary", "business", "technology"],
}


def fetch_broll(language: str = "pt", count: int = 3) -> list:
    if not PEXELS_API_KEY:
        return []

    queries = STYLE_QUERIES.get(language, STYLE_QUERIES["en"])
    query = random.choice(queries)

    headers = {"Authorization": PEXELS_API_KEY}
    response = requests.get(
        "https://api.pexels.com/videos/search",
        headers=headers,
        params={"query": query, "per_page": 10, "orientation": "landscape"},
        timeout=10,
    )

    if response.status_code != 200:
        return []

    videos = response.json().get("videos", [])
    clips = []

    for video in videos[:count]:
        files = video.get("video_files", [])
        hd_file = next((f for f in files if f.get("quality") == "hd"), files[0] if files else None)
        if not hd_file:
            continue

        clip_path = os.path.join(OUTPUT_DIR, f"broll_{video['id']}.mp4")
        if not os.path.exists(clip_path):
            _download_and_vary(hd_file["link"], clip_path)

        clips.append(clip_path)

    return clips


def _download_and_vary(url: str, output_path: str):
    """Baixa clipe e aplica pequena variação para evitar conteúdo repetido no YouTube."""
    tmp_path = output_path + ".tmp.mp4"

    with requests.get(url, stream=True, timeout=30) as r:
        with open(tmp_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)

    # Variação aleatória: espelhar OU ajustar velocidade levemente OU filtro de cor
    variation = random.choice(["mirror", "speed", "color"])

    if variation == "mirror":
        vf = "hflip"
    elif variation == "speed":
        speed = random.choice(["0.95", "1.05"])
        vf = f"setpts={1/float(speed)}*PTS"
    else:
        brightness = round(random.uniform(-0.05, 0.05), 2)
        vf = f"eq=brightness={brightness}"

    subprocess.run([
        "ffmpeg", "-i", tmp_path,
        "-vf", vf, "-c:a", "copy",
        output_path, "-y"
    ], check=True)

    os.remove(tmp_path)
