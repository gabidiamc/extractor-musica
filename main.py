import os
import time
import requests
import yt_dlp
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_ydl_opts():
    return {
        "format": "bestaudio/best",
        "quiet": True,
        "no_warnings": True,
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "visionos"],
                "player_skip": ["webpage", "configs"],
            }
        },
    }


_cache = {}


def _resolve(v: str):
    cached = _cache.get(v)
    if cached and time.time() - cached[1] < 3600:
        return cached[0]
    with yt_dlp.YoutubeDL(get_ydl_opts()) as ydl:
        info = ydl.extract_info(f"https://www.youtube.com/watch?v={v}", download=False)
    _cache[v] = (info, time.time())
    return info


@app.get("/")
def health():
    return {"ok": True}


@app.get("/audio")
def get_audio_info(v: str = Query(..., description="ID del video")):
    try:
        info = _resolve(v)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {
        "title": info.get("title"),
        "artist": info.get("uploader") or info.get("channel"),
        "duration": info.get("duration"),
        "thumbnail": info.get("thumbnail"),
        "stream_url": f"/stream?v={v}",
    }


@app.get("/stream")
def stream(request: Request, v: str = Query(...)):
    try:
        info = _resolve(v)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    audio_url = info.get("url")
    if not audio_url:
        raise HTTPException(status_code=404, detail="No se encontró audio")

    headers = dict(info.get("http_headers") or {})
    rng = request.headers.get("range")
    if rng:
        headers["Range"] = rng

    r = requests.get(audio_url, headers=headers, stream=True, timeout=30)
    out_headers = {
        "Accept-Ranges": "bytes",
        "Content-Type": r.headers.get("content-type", "audio/mp4"),
    }
    for k in ("Content-Length", "Content-Range"):
        if k in r.headers:
            out_headers[k] = r.headers[k]

    return StreamingResponse(
        r.iter_content(chunk_size=65536),
        status_code=r.status_code,
        headers=out_headers,
    )
