import sys, time
sys.path.insert(0, '.')
from downloader import extract_video_info

url = "https://v.douyin.com/Bbj45TPBLlI/"
start = time.time()
try:
    info = extract_video_info(url)
    elapsed = time.time() - start
    print(f"Time: {elapsed:.1f}s")
    print(f"type: {info.get('type')}")
    print(f"video_url: {info.get('video_url', '')[:120]}")
    print(f"video_urls: {len(info.get('video_urls', []))}")
    print(f"images: {len(info.get('images', []))}")
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
