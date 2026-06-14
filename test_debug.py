import httpx, re, json

MOBILE_UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"

url = "https://v.douyin.com/Bbj45TPBLlI/"
headers = {"User-Agent": MOBILE_UA}
r = httpx.get(url, headers=headers, follow_redirects=False, timeout=30)
location = r.headers.get("location", "")
m = re.search(r"/note/(\d+)", location)
item_id = m.group(1)
share_url = f"https://www.iesdouyin.com/share/note/{item_id}/"

r = httpx.get(share_url, headers={"User-Agent": MOBILE_UA, "Referer": share_url}, follow_redirects=True, timeout=30)
html = r.text

video_url = ""
has_video_hint = '"img_bitrate":null' in html
images = []
img_start = html.find('"images":[')
if img_start >= 0:
    arr_start = img_start + 9
    depth = 0
    end = arr_start
    for i in range(arr_start, min(arr_start + 500000, len(html))):
        if html[i] == "[":
            depth += 1
        elif html[i] == "]":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    img_data = html[arr_start:end]
    for block in re.finditer(r'"url_list":\["(https?:[^"]+)"', img_data):
        raw = block.group(1).replace("\\u002F", "/")
        try:
            img_url = json.loads('"' + raw + '"')
        except:
            img_url = raw
        if "tos-cn-i-" in img_url and img_url not in images:
            images.append(img_url)

print(f"video_url empty: {not video_url}")
print(f"has_video_hint: {has_video_hint}")
print(f"images count: {len(images)}")
print(f"html length: {len(html)}")
print(f"would trigger: {not video_url and (has_video_hint or len(images) <= 1 or len(html) < 10000)}")
