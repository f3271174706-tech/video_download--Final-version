# 部署指南

## 本地开发

```bash
# 安装依赖
pip install -r requirements.txt

# 启动服务（默认端口 8001）
python main.py

# 访问
# v3 白色液态玻璃: http://127.0.0.1:8001
# v1 经典暗色: http://127.0.0.1:8001/v1
# v2 WebGL 玻璃: http://127.0.0.1:8001/v2
```
# 部署文档（私密）

## 服务器

| 项 | 值 |
|----|-----|
| IP | 103.236.88.224 |
| SSH 端口 | 44715 |
| 登录 | `ssh root@103.236.88.224 -p 44715` |
| 密钥 | `C:\Users\32711\.ssh\id_ed25519`（Ed25519，仅密钥登录） |
| 私钥 | 见下方 |
| 公钥 | `ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIEIGd9+rBtIQ0wnJ1MYSjqVHJvi/juU980GFSGF90D2K 32711@A7` |
| 代理 | `http://127.0.0.1:7897`（mihomo） |
| 规格 | 4核4G 30M / 30G SSD |

## 项目目录

| 项目 | 路径 | 服务名 | 端口 |
|------|------|--------|------|
| Project 1 | `/root/DOWN/` | douyin-dl | 9000 |
| Project 2 | `/root/Liquid-glass-UI-3.0/` | douyin-dl2 | 9001 |

## Cloudflare Tunnel

两个隧道均为本地配置（`cloudflared tunnel create`），config 文件方式运行。

### fzpnowm.top（Tunnel: `255822ac`）

```bash
# 配置文件
cat /root/.cloudflared/config-fzpnowm.yml
# 服务
systemctl status cloudflared-fzpnowm
# 日志
journalctl -u cloudflared-fzpnowm --no-pager -n 20
```

### fzp.me（Tunnel: `6ba4df3f`）

```bash
# 配置文件
cat /root/.cloudflared/config-fzpme.yml
# 服务
systemctl status cloudflared-fzpme
# 日志
journalctl -u cloudflared-fzpme --no-pager -n 20
```

### 重启规则

两个服务均 `Restart=on-failure` + `RestartSec=5`。

| 场景 | 自动恢复 | 说明 |
|------|:--------:|------|
| 进程崩溃/异常退出 | ✅ | systemd `Restart=on-failure` |
| Edge 波动（进程存活但隧道不通） | ✅ | crontab 每 5 分钟 `check-tunnels.sh` |
| 服务器重启 | ✅ | systemd 开机自启 |
| 修改 config 或 credentials 后 | ❌ | 手动 `systemctl restart` |

手动重启：
```bash
systemctl restart cloudflared-fzpnowm cloudflared-fzpme
```

## 健康检查

脚本：`/root/check-tunnels.sh`
Crontab：`*/5 * * * *`
日志：`/var/log/check-tunnels.log`

三层检查：
1. Tunnel 进程存活 → `systemctl is-active` → 挂了重启
2. 本地后端存活 → `curl localhost:9000 / 9001` → 挂了重启并 wait 5s
3. 域名公网可达 → `curl https://域名` → 后端正常但域名不通 → 重启 tunnel

## 下载文件自动清理

脚本：`/root/cleanup-downloads.sh`
Crontab：`0 * * * *`（每小时整点）
日志：`/var/log/cleanup-downloads.log`

清理目录（超过 60 分钟的文件）：

| 项目 | 目录 |
|------|------|
| Project 1 | `/root/DOWN/downloads/`, `temp/` |
| Project 2 | `/root/Liquid-glass-UI-3.0/downloads/`, `temp/` |

手动执行：`/root/cleanup-downloads.sh`

## 服务管理

```bash
# 后端服务
systemctl restart douyin-dl     # Project 1
systemctl restart douyin-dl2    # Project 2
journalctl -u douyin-dl --no-pager -n 30   # 查看日志
journalctl -u douyin-dl2 --no-pager -n 30

# 重启后验证
curl -s -o /dev/null -w '%{http_code}' http://localhost:9000/
curl -s -o /dev/null -w '%{http_code}' http://localhost:9001/
```

## 服务器补丁

`server_patches.py` 对云服务器 `downloader.py` 做以下修改：

- 添加 `_curl_get` / `_curl_download`（subprocess curl，走代理）
- TikTok 改用 ssstiktok.cc 爬取
- Twitter 提取改用 `_curl_get` 调用 fxtwitter API
- Twitter 下载增加 m3u8 → ffmpeg 合成
- 环境变量 `HTTP_PROXY` / `HTTPS_PROXY` 自动检测

## 从本地上传文件

```bash
# 代码文件
scp -P 44715 "d:/mycode/douyin-downloader 2.0/main.py" root@103.236.88.224:/root/douyin-downloader-2.0/
scp -P 44715 "d:/mycode/douyin-downloader 2.0/downloader.py" root@103.236.88.224:/root/douyin-downloader-2.0/

# Project 2 文件
scp -P 44715 "d:/mycode/Liquid glass UI 3.0-mimo/main.py" root@103.236.88.224:/root/Liquid-glass-UI-3.0/
scp -P 44715 "d:/mycode/Liquid glass UI 3.0-mimo/downloader.py" root@103.236.88.224:/root/Liquid-glass-UI-3.0/
scp -P 44715 "d:/mycode/Liquid glass UI 3.0-mimo/static/index.html" root@103.236.88.224:/root/Liquid-glass-UI-3.0/static/
scp -P 44715 "d:/mycode/Liquid glass UI 3.0-mimo/static/bg.png" "d:/mycode/Liquid glass UI 3.0-mimo/static/bg2.jpg" "d:/mycode/Liquid glass UI 3.0-mimo/static/bg3.png" root@103.236.88.224:/root/Liquid-glass-UI-3.0/static/
scp -P 44715 "d:/mycode/Liquid glass UI 3.0-mimo/static/html2canvas.min.js" "d:/mycode/Liquid glass UI 3.0-mimo/static/liquidGL.js" root@103.236.88.224:/root/Liquid-glass-UI-3.0/static/
```

## SSH 安全

- 密码登录已禁用：`PasswordAuthentication no`
- Root 仅密钥登录：`PermitRootLogin prohibit-password`
- 暴力破解来源已阻断（曾来自 `218.71.38.151`）

```bash
# 查看最近 SSH 攻击
journalctl -u sshd --no-pager -p err -n 20
```

## 修复记录

### 2026-06-10 · Project 2 上线与修复

- 新建 fzp.me 隧道（`6ba4df3f`，本地 config 方式），废弃旧 FZP-ME-2
- 静态文件上传：`bg.png`, `bg2.jpg`, `bg3.png`, `html2canvas.min.js`, `liquidGL.js`
- 修复 `liquidGL is not defined`：移除 JS 脚本的 `defer` 属性
- 静态资源加 `?v=2` 破除浏览器缓存
- `server_patches.py` 应用到 Project 2 的 `downloader.py`
- SSH 禁用密码登录，仅密钥认证
- 更新 `check-tunnels.sh`：增加域名可达性检查和防误判逻辑

### 2026-06-11 · 代码审查修复

- **下载文件自动清理**：新增 `/root/cleanup-downloads.sh`，crontab 每小时清理超过 60 分钟的下载文件
- **Project 2 幻灯片修复**：`_make_slides_video` 从单图循环改为全图片逐张拼接（移植自 Project 1）
- **Project 2 Twitter 下载回退**：新增 `_download_twitter_video`，直链失败自动走 m3u8/ffmpeg（解决服务端 `video.twimg.com` 被封）
- **Project 1 死代码清理**：删除未使用的 `_extract_ytdlp` 及 `yt-dlp` 导入
- **流式代理 + Range 支持**：`/api/stream` 改为 httpx 流式代理（边下边传），传递浏览器 Range 头返回 206，支持拖进度条；m3u8 仍走先下载后返回；超时设为 connect=10s, read=300s

## SSH 密钥对

### 私钥（`~/.ssh/id_ed25519`）

```
-----BEGIN OPENSSH PRIVATE KEY-----
b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAAAMwAAAAtzc2gtZW
QyNTUxOQAAACBCBnffqwbSENMJydTGEo6lRyb4v47lPfNBhUhhfdA9igAAAJDpfa+Y6X2v
mAAAAAtzc2gtZWQyNTUxOQAAACBCBnffqwbSENMJydTGEo6lRyb4v47lPfNBhUhhfdA9ig
AAAEDl5WRZJ0vTjTIyC4ZOdW03TTIMzXPCfpshetY75S39u0IGd9+rBtIQ0wnJ1MYSjqVH
Jvi/juU980GFSGF90D2KAAAACDMyNzExQEE3AQIDBAU=
-----END OPENSSH PRIVATE KEY-----
```

### 公钥

```
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIEIGd9+rBtIQ0wnJ1MYSjqVHJvi/juU980GFSGF90D2K 32711@A7
```

> ⚠️ 此文件已在 `.gitignore` 中，不会被提交到 GitHub。
