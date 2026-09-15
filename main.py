from fastapi import FastAPI, BackgroundTasks, Request, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from pydantic import BaseModel
import yt_dlp
import uvicorn
import os
import tempfile
import uuid
import imageio_ffmpeg
import urllib.parse

def get_cookie_file():
    env_cookies = os.environ.get("YOUTUBE_COOKIES")
    if env_cookies:
        cookie_path = os.path.join(tempfile.gettempdir(), "youtube_cookies.txt")
        with open(cookie_path, "w", encoding="utf-8") as f:
            f.write(env_cookies.replace('\\n', '\n'))
        return cookie_path
    if os.path.exists("cookies.txt"):
        return "cookies.txt"
    if os.path.exists("/etc/secrets/cookies.txt"):
        return "/etc/secrets/cookies.txt"
    return None

app = FastAPI()

static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir)

app.mount("/static", StaticFiles(directory=static_dir), name="static")

progress_store = {}

class URLRequest(BaseModel):
    url: str

@app.get("/", response_class=HTMLResponse)
async def get_index():
    try:
        with open(os.path.join(static_dir, "index.html"), "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "Frontend not found. Please ensure static/index.html exists."

@app.get("/api/progress")
async def get_progress(task_id: str):
    return JSONResponse(content=progress_store.get(task_id, {"status": "unknown"}))

@app.post("/api/extract")
async def extract_info(request: URLRequest):
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
    }
    cookie_file = get_cookie_file()
    if cookie_file:
        ydl_opts['cookiefile'] = cookie_file
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(request.url, download=False)
            
            formats = []
            has_audio = False
            
            for f in info_dict.get('formats', []):
                vcodec = f.get('vcodec')
                acodec = f.get('acodec')
                if vcodec != 'none' and acodec != 'none' and f.get('url'):
                    has_audio = True
                    res_height = f.get('height', 0)
                    fallback = f"/bestvideo[height<={res_height}]+bestaudio/best[height<={res_height}]/best" if res_height else "/best"
                    formats.append({
                        'format_id': f"{f.get('format_id')}{fallback}",
                        'ext': f.get('ext'),
                        'resolution': f.get('resolution') or f"{f.get('width', '')}x{f.get('height', '')}",
                        'url': f.get('url'),
                        'filesize': f.get('filesize', 0) or 0,
                        'format_note': f.get('format_note', ''),
                        'needs_merge': False
                    })
                elif vcodec != 'none' and acodec == 'none' and f.get('url'):
                    res_height = f.get('height', 0)
                    if res_height and res_height >= 720:
                        fallback = f"/bestvideo[height<={res_height}]+bestaudio/best[height<={res_height}]/best"
                        formats.append({
                            'format_id': f"{f.get('format_id')}+bestaudio/{f.get('format_id')}{fallback}",
                            'ext': 'mp4',
                            'resolution': f.get('resolution') or f"{f.get('width', '')}x{f.get('height', '')}",
                            'url': None, 
                            'filesize': f.get('filesize', 0) or 0,
                            'format_note': f"HQ {f.get('format_note', '')}",
                            'needs_merge': True
                        })
            
            if not formats and info_dict.get('url'):
                formats.append({
                    'format_id': 'best',
                    'ext': info_dict.get('ext', 'mp4'),
                    'resolution': 'Best Available',
                    'url': info_dict.get('url'),
                    'filesize': 0,
                    'format_note': 'Combined',
                    'needs_merge': False
                })
                
            def get_res_val(fmt):
                res_str = str(fmt.get('resolution') or '')
                if 'x' in res_str:
                    parts = res_str.split('x')
                    if len(parts) > 1 and parts[-1].isdigit():
                        return int(parts[-1])
                return 0
                
            formats = sorted(formats, key=get_res_val, reverse=True)
            
            seen = {}
            for fmt in formats:
                res = fmt['resolution']
                if res not in seen:
                    seen[res] = fmt
                else:
                    if not fmt['needs_merge'] and seen[res]['needs_merge']:
                        seen[res] = fmt

            unique_formats = list(seen.values())
            unique_formats = sorted(unique_formats, key=get_res_val, reverse=True)

            response_data = {
                'title': info_dict.get('title'),
                'thumbnail': info_dict.get('thumbnail'),
                'duration': info_dict.get('duration'),
                'uploader': info_dict.get('uploader'),
                'formats': unique_formats,
                'original_url': request.url
            }
            return JSONResponse(content=response_data)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=400)


@app.get("/api/download")
async def download_video(url: str, format_id: str, task_id: str, background_tasks: BackgroundTasks):
    out_dir = tempfile.gettempdir()
    file_id = str(uuid.uuid4())
    out_tmpl = os.path.join(out_dir, f"{file_id}.%(ext)s")
    
    ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
    
    progress_store[task_id] = {"status": "starting", "percent": 0}
    
    def my_hook(d):
        if d['status'] == 'downloading':
            downloaded = d.get('downloaded_bytes', 0)
            total = d.get('total_bytes', 0) or d.get('total_bytes_estimate', 0)
            percent = (downloaded / total * 100) if total > 0 else 0
            
            # Keep track of current status safely without overwriting previous "merging" if multiple streams download
            progress_store[task_id] = {
                'status': 'downloading',
                'downloaded': downloaded,
                'total': total,
                'percent': percent
            }
        elif d['status'] == 'finished':
            progress_store[task_id] = {
                'status': 'merging',
                'percent': 100
            }

    ydl_opts = {
        'format': format_id,
        'outtmpl': out_tmpl,
        'ffmpeg_location': ffmpeg_path,
        'merge_output_format': 'mp4',
        'quiet': True,
        'no_warnings': True,
        'progress_hooks': [my_hook],
    }
    cookie_file = get_cookie_file()
    if cookie_file:
        ydl_opts['cookiefile'] = cookie_file
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            
            final_filename = filename
            base, ext = os.path.splitext(filename)
            if os.path.exists(base + '.mp4'):
                final_filename = base + '.mp4'
            elif os.path.exists(base + '.mkv'):
                final_filename = base + '.mkv'
                
            safe_title = "".join([c for c in info.get('title', 'video') if c.isalpha() or c.isdigit() or c==' ']).rstrip()
            download_name = f"{safe_title}.mp4"
            
            progress_store[task_id] = {"status": "completed", "percent": 100}
            
            def cleanup(path, tid):
                try:
                    if os.path.exists(path):
                        os.remove(path)
                    if tid in progress_store:
                        del progress_store[tid]
                except:
                    pass
                    
            background_tasks.add_task(cleanup, final_filename, task_id)
            
            return FileResponse(path=final_filename, filename=download_name, media_type='video/mp4')
            
    except Exception as e:
        progress_store[task_id] = {"status": "error", "message": str(e)}
        return JSONResponse(content={"error": str(e)}, status_code=400)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
