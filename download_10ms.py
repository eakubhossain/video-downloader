import asyncio
from playwright.async_api import async_playwright
import os
import subprocess

URL = "https://app.10minuteschool.com/skills/courses/learn/ghore-boshe-spoken-english/lesson/69"
DOWNLOAD_DIR = os.path.expanduser("~/Downloads")

async def extract_and_download():
    print("Starting browser for manual login...")
    async with async_playwright() as p:
        # Launch the actual Google Chrome browser to avoid bot detection
        browser = await p.chromium.launch(
            headless=False, 
            channel="chrome",
            args=['--disable-blink-features=AutomationControlled']
        )
        context = await browser.new_context()
        page = await context.new_page()
        
        m3u8_url = None
        
        # Catch the stream url in the background
        async def handle_request(request):
            nonlocal m3u8_url
            url = request.url
            if (".m3u8" in url or "vimeo.com" in url or "master.json" in url) and ("?" in url or "token" in url or "video" in url):
                if m3u8_url is None: # Only catch the first valid video stream link
                    print(f"\n[+] Found video stream URL!\n")
                    m3u8_url = url
                
        page.on("request", handle_request)
        
        print("\n" + "="*50)
        print("Please log in and play the video in the opened browser window.")
        print("Waiting for you to log in...")
        print("="*50 + "\n")
        
        # Navigate to the video directly. If not logged in, it redirects to login.
        try:
            await page.goto(URL, timeout=60000)
        except:
            pass
            
        # Wait until we catch the m3u8 link (checking every 2 seconds)
        # Give the user up to 5 minutes to log in and play the video
        for _ in range(150):
            if m3u8_url:
                break
            await asyncio.sleep(2)
            
        user_agent = None
        if m3u8_url:
            user_agent = await page.evaluate("navigator.userAgent")
            
        await browser.close()
        
        if m3u8_url:
            import imageio_ffmpeg
            ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
            print("Successfully extracted video stream URL! Starting download via yt-dlp...\n")
            
            os.chdir(DOWNLOAD_DIR)
            command = [
                "yt-dlp",
                m3u8_url,
                "--ffmpeg-location", ffmpeg_path,
                "--cookies-from-browser", "chrome",
                "--add-header", "Referer: https://app.10minuteschool.com/",
                "--add-header", "Origin: https://app.10minuteschool.com",
                "--user-agent", user_agent,
                "--downloader", "m3u8:native",
                "-o",
                "%(title)s.%(ext)s"
            ]
            subprocess.run(command)
            print("\nDownload complete! The video is saved in your Downloads folder.")
        else:
            print("\nFailed to find the video stream URL. Did you log in and play the video?")

if __name__ == "__main__":
    asyncio.run(extract_and_download())
