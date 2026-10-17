import os
import tempfile
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

COOKIE_CONTENT = os.environ.get("YOUTUBE_COOKIES", "")
COOKIE_FILE = None
if COOKIE_CONTENT:
    f = tempfile.NamedTemporaryFile(delete=False, mode="w", encoding="utf-8", suffix=".txt")
    f.write(COOKIE_CONTENT)
    f.close()
    COOKIE_FILE = f.name


@app.get("/")
def health():
    return {"ok": True}


@app.get("/audio")
def get_audio_stream(v: str = Query(..., description="ID del video de YouTube")):
    ydl_opts = {"format": "bestaudio[ext=m4a]/bestaudio/best", "quiet": True, "no_warnings": True}
    if COOKIE_FILE:
        ydl_opts["cookiefile"] = COOKIE_FILE
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={v}", download=False)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    stream_url = info.get("url")
    if not stream_url:
        raise HTTPException(status_code=404, detail="No se encontró enlace de audio")
    return {
        "title": info.get("title"),
        "artist": info.get("uploader") or info.get("channel"),
        "duration": info.get("duration"),
        "thumbnail": info.get("thumbnail"),
        "stream_url": stream_url,
    }
