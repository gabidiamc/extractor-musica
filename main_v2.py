import os
import tempfile
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp
import requests
from fastapi import Request
from fastapi.responses import StreamingResponse

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


_cache = {}

def _resolve(v):
    import time
    c = _cache.get(v)
    if c and time.time() - c[1] < 3600:
        return c[0]
    opts = {"format": "bestaudio[ext=m4a]/bestaudio", "quiet": True, "no_warnings": True}
    if COOKIE_FILE:
        opts["cookiefile"] = COOKIE_FILE
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(f"https://www.youtube.com/watch?v={v}", download=False)
    _cache[v] = (info, time.time())
    return info


@app.get("/stream")
def stream(request: Request, v: str = Query(...)):
    try:
        info = _resolve(v)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    headers = dict(info.get("http_headers") or {})
    rng = request.headers.get("range")
    if rng:
        headers["Range"] = rng
    r = requests.get(info["url"], headers=headers, stream=True, timeout=30)
    out = {"Accept-Ranges": "bytes", "Content-Type": "audio/mp4" if info.get("ext") == "m4a" else "audio/webm"}
    for k in ("Content-Length", "Content-Range"):
        if k in r.headers:
            out[k] = r.headers[k]
    return StreamingResponse(r.iter_content(65536), status_code=r.status_code, headers=out)
