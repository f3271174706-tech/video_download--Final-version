from pathlib import Path
from urllib.parse import unquote
import re

import httpx
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response
from pydantic import BaseModel

from downloader import MOBILE_UA, apply_quality, cleanup_old_files, download_video_for_stream, extract_video_info, download_video

app = FastAPI(title="抖音/X 无水印下载器")

@app.on_event("startup")
async def startup_cleanup():
    cleanup_old_files()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# gzip 压缩（>500B 的响应自动压缩）
app.add_middleware(GZipMiddleware, minimum_size=500)

static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)


class CachedStaticFiles(StaticFiles):
    """Static files with Cache-Control headers for better performance."""
    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        if response.status_code == 200 and isinstance(response, Response):
            # JS/CSS/图片：缓存 7 天
            if path.endswith(('.js', '.css', '.jpg', '.png', '.webp', '.gif', '.ico')):
                response.headers['Cache-Control'] = 'public, max-age=604800, immutable'
            # HTML：缓存 10 分钟（方便更新）
            elif path.endswith('.html'):
                response.headers['Cache-Control'] = 'public, max-age=600'
        return response


app.mount("/static", CachedStaticFiles(directory=str(static_dir)), name="static")


class ParseRequest(BaseModel):
    url: str


class DownloadRequest(BaseModel):
    url: str
    quality: str = "1080p"
    type: str = "video"
    image_index: int = 0


@app.get("/")
async def index():
    from fastapi.responses import HTMLResponse
    html_path = static_dir / "index.html"
    if html_path.exists():
        return HTMLResponse(html_path.read_text(encoding="utf-8"), headers={"Cache-Control": "public, max-age=600"})
    return HTMLResponse("<h1>index.html not found</h1>", status_code=404)


@app.get("/v1")
async def index_v1():
    from fastapi.responses import HTMLResponse
    html_path = static_dir / "index-v1.html"
    if html_path.exists():
        return HTMLResponse(html_path.read_text(encoding="utf-8"), headers={"Cache-Control": "public, max-age=600"})
    return HTMLResponse("<h1>index-v1.html not found</h1>", status_code=404)


@app.get("/v2")
async def index_v2():
    from fastapi.responses import HTMLResponse
    html_path = static_dir / "index-v2.html"
    if html_path.exists():
        return HTMLResponse(html_path.read_text(encoding="utf-8"), headers={"Cache-Control": "public, max-age=600"})
    return HTMLResponse("<h1>index-v2.html not found</h1>", status_code=404)


@app.post("/api/parse")
async def parse_video(req: ParseRequest):
    url = req.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="请输入视频链接")

    try:
        info = extract_video_info(url)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"解析失败: {str(e)}")

    media_type = info.get("type", "video")
    result = {
        "success": True,
        "title": info["title"],
        "thumbnail": info["thumbnail"],
        "duration": info.get("duration", 0),
        "platform": info["platform"],
        "type": media_type,
    }
    if media_type == "photo":
        result["images"] = info.get("images", [])
        result["video_url"] = ""
        result["music_url"] = info.get("music_url", "")
    elif media_type == "live_photo":
        result["video_url"] = info.get("video_url", "")
        result["video_urls"] = info.get("video_urls", [])
        result["images"] = info.get("images", [])
        result["music_url"] = info.get("music_url", "")
    else:
        result["video_url"] = info.get("video_url", "")
        result["m3u8_url"] = info.get("m3u8_url", "")
    return result


@app.get("/api/stream")
async def stream_video(
    request: Request,
    video_url: str = Query(..., description="Video URL"),
    quality: str = Query("1080p", description="Quality: 720p, 1080p, hd"),
    m3u8_url: str = Query("", description="M3U8 URL for ffmpeg download"),
):
    """流式代理 + Range 支持（边下边传，可拖进度条）"""
    video_url = unquote(video_url)
    m3u8_url = unquote(m3u8_url) if m3u8_url else ""
    if "douyin" in video_url or "snssdk" in video_url:
        video_url = apply_quality(video_url, quality)

    # m3u8 需要 ffmpeg 处理，走先下载后返回
    if m3u8_url and ".m3u8" in m3u8_url:
        file_path, filename = download_video_for_stream(video_url, m3u8_url)
        return FileResponse(path=file_path, media_type="video/mp4", filename=filename)

    # 构建请求头
    headers = {"User-Agent": MOBILE_UA}
    referer_map = {
        "douyin": "https://www.iesdouyin.com/",
        "snssdk": "https://www.iesdouyin.com/",
        "video.twimg.com": "https://x.com/",
        "tiktokcdn": "https://www.tiktok.com/",
        "bilibili": "https://www.bilibili.com/",
        "bilivideo": "https://www.bilibili.com/",
    }
    for domain, ref in referer_map.items():
        if domain in video_url:
            headers["Referer"] = ref
            break

    # 传递浏览器的 Range 请求头
    range_header = request.headers.get("range")
    if range_header:
        headers["Range"] = range_header

    try:
        # 不用 async with，手动管理生命周期，避免 StreamingResponse 迭代前连接被关
        client = httpx.AsyncClient(follow_redirects=True, timeout=httpx.Timeout(connect=10, read=300, write=10, pool=10))
        req = client.build_request("GET", video_url, headers=headers)
        stream_resp = await client.send(req, stream=True)

        # Fallback: play URL 返回空内容时，用 CDN 直链
        content_length = int(stream_resp.headers.get("content-length", 0))
        if content_length == 0 and "aweme.snssdk.com" in video_url:
            await stream_resp.aclose()
            vid_match = re.search(r'video_id=([^&]+)', video_url)
            if vid_match:
                direct_url = vid_match.group(1)
                req = client.build_request("GET", direct_url, headers={"User-Agent": MOBILE_UA})
                stream_resp = await client.send(req, stream=True)

        if stream_resp.status_code >= 400:
            await stream_resp.aclose()
            await client.aclose()
            raise HTTPException(status_code=502, detail=f"源返回 {stream_resp.status_code}")

        # 构建响应头
        resp_headers = {}
        for key in ("content-type", "content-length", "content-range", "accept-ranges"):
            val = stream_resp.headers.get(key)
            if val:
                resp_headers[key] = val

        async def chunk_iter():
            try:
                async for chunk in stream_resp.aiter_bytes(65536):
                    yield chunk
            finally:
                await stream_resp.aclose()
                await client.aclose()

        status_code = 206 if (range_header and stream_resp.status_code == 206) else 200
        return StreamingResponse(
            chunk_iter(),
            status_code=status_code,
            headers=resp_headers,
            media_type=stream_resp.headers.get("content-type", "video/mp4"),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"流式连接失败: {str(e)}")


@app.post("/api/download")
async def download_video_api(req: DownloadRequest):
    import os
    from urllib.parse import quote

    url = req.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="请输入视频链接")

    try:
        file_path, filename = download_video(
            url, quality=req.quality, media_type=req.type, image_index=req.image_index
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"下载失败: {str(e)}")

    if filename.endswith(".mp3"):
        media_type = "audio/mpeg"
    elif filename.endswith(".zip"):
        media_type = "application/zip"
    elif filename.endswith(".webp") or filename.endswith(".jpg") or filename.endswith(".png"):
        media_type = "image/" + filename.rsplit(".", 1)[-1]
    else:
        media_type = "video/mp4"

    file_size = os.path.getsize(file_path)
    encoded_name = quote(filename)

    def file_iter():
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                yield chunk

    return StreamingResponse(
        file_iter(),
        media_type=media_type,
        headers={
            "Content-Length": str(file_size),
            "Content-Disposition": f"attachment; filename*=utf-8''{encoded_name}",
            "Accept-Ranges": "bytes",
        },
    )
