"""
抖音/TikTok API 模块
使用 f2 库提取抖音内容（支持动图 live_photo）
使用 TikTokApi 库提取 TikTok 内容
"""

import asyncio
import re
from typing import Optional

from config import config, get_logger

logger = get_logger(__name__)


async def _extract_tiktok_api(url: str) -> Optional[dict]:
    """
    使用 TikTokApi 提取 TikTok 内容

    Args:
        url: TikTok 链接

    Returns:
        dict: 提取结果，失败返回 None
    """
    try:
        from TikTokApi import TikTokApi

        logger.info(f"调用 TikTok API: {url}")

        # 获取 Cookie
        tiktok_cookie = config.get("cookies.tiktok", "")

        # 创建 API 实例
        api = TikTokApi()

        # 设置代理（国内需要代理访问 TikTok）
        proxy_url = config.get("network.proxy", "")
        proxies = None
        if proxy_url:
            proxies = [{"server": proxy_url}]

        # 设置 Cookie
        if tiktok_cookie:
            # 将 cookie 字符串转换为字典格式
            cookies = {}
            for item in tiktok_cookie.split(';'):
                item = item.strip()
                if '=' in item:
                    key, value = item.split('=', 1)
                    cookies[key.strip()] = value.strip()

            # 创建 session 并设置 cookie
            await api.create_sessions(
                headless=True,
                cookies=[cookies],
                browser="chromium",
                proxies=proxies,
                timeout=60000,  # 增加超时到 60 秒
                allow_partial_sessions=True  # 允许部分 session 失败
            )
        else:
            await api.create_sessions(
                headless=True,
                browser="chromium",
                proxies=proxies,
                timeout=60000,
                allow_partial_sessions=True
            )

        try:
            # 获取视频信息
            video = api.video(url=url)
            video_info = await video.info()

            if not video_info:
                logger.warning("TikTok API 返回空数据")
                return None

            # 提取标题
            desc = video_info.get('desc', '未知标题')

            # 提取视频 URL
            video_data = video_info.get('video', {})
            play_addr = video_data.get('play_addr', {})
            url_list = play_addr.get('url_list', [])
            video_url = url_list[0] if url_list else ''

            # 提取封面
            cover = video_data.get('cover', {}).get('url_list', [''])[0] if video_data.get('cover', {}).get('url_list') else ''

            # 提取时长
            duration = video_data.get('duration', 0)

            # 检查是否是图片帖子
            images = video_info.get('images', [])
            if images:
                # 图片帖子
                image_urls = []
                for img in images:
                    img_url = img.get('url_list', [''])[0] if img.get('url_list') else ''
                    if img_url:
                        image_urls.append(img_url)

                return {
                    "title": desc,
                    "thumbnail": image_urls[0] if image_urls else cover,
                    "duration": 0,
                    "type": "photo",
                    "images": image_urls,
                    "platform": "tiktok",
                }
            else:
                # 视频帖子
                return {
                    "title": desc,
                    "thumbnail": cover,
                    "duration": duration,
                    "type": "video",
                    "video_url": video_url,
                    "platform": "tiktok",
                }

        finally:
            await api.close_sessions()

    except Exception as e:
        logger.error(f"TikTok API 调用失败: {e}")
        return None


async def _extract_douyin_api(url: str) -> Optional[dict]:
    """
    使用 f2 提取抖音内容（视频/图片/动图）

    Args:
        url: 抖音链接（支持分享链接、短链接、长链接）

    Returns:
        dict: 提取结果，失败返回 None
    """
    try:
        from f2.apps.douyin.crawler import DouyinCrawler
        from f2.apps.douyin.utils import AwemeIdFetcher
        from f2.apps.douyin.model import PostDetail

        logger.info(f"调用抖音 API (f2): {url}")

        # 获取 aweme_id
        aweme_id = await AwemeIdFetcher.get_aweme_id(url)
        if not aweme_id:
            logger.warning("无法获取 aweme_id")
            return None

        logger.info(f"aweme_id: {aweme_id}")

        # 构建 kwargs
        douyin_cookie = config.get("cookies.douyin", "")
        kwargs = {
            'proxies': {'http://': None, 'https://': None},
            'headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36',
                'referer': 'https://www.douyin.com/',
            },
            'cookie': douyin_cookie or '',
        }

        # 获取帖子详情
        async with DouyinCrawler(kwargs) as crawler:
            params = PostDetail(aweme_id=aweme_id)
            result = await crawler.fetch_post_detail(params)

        if not result or 'aweme_detail' not in result:
            logger.warning("f2 返回空数据")
            return None

        detail = result['aweme_detail']
        aweme_type = detail.get('aweme_type', 0)
        desc = detail.get('desc', '未知标题')

        # 获取封面
        cover = ''
        video_cover = detail.get('video', {}).get('cover', {})
        if video_cover and video_cover.get('url_list'):
            cover = video_cover['url_list'][0]

        # 判断类型
        # aweme_type: 68=动图, 0=视频, 51=图文
        images = detail.get('images', [])

        # 检查是否是动图（live_photo）
        # 动图必须满足：aweme_type == 68 或者 images 中有视频数据
        is_live_photo = aweme_type == 68
        if not is_live_photo and images:
            # 只有当 images 中有 video 字段且包含有效视频 URL 时才认为是动图
            for img in images:
                video_info = img.get('video', {})
                if video_info:
                    play_addr = video_info.get('play_addr', {})
                    url_list = play_addr.get('url_list', [])
                    if url_list and any('douyinvod' in url or 'zjcdn' in url for url in url_list):
                        is_live_photo = True
                        break

        if is_live_photo and images:
            # 动图类型
            image_urls = []
            video_urls = []

            for img in images:
                # 获取图片 URL
                url_list = img.get('url_list', [])
                if url_list:
                    image_urls.append(url_list[0])

                # 获取视频 URL（在 img.video.play_addr.url_list 中）
                video_info = img.get('video', {})
                if video_info:
                    play_addr = video_info.get('play_addr', {})
                    v_url_list = play_addr.get('url_list', [])
                    if v_url_list:
                        video_urls.append(v_url_list[0])

            # 获取音乐
            music_url = ''
            music_info = detail.get('music', {})
            if music_info:
                play_url = music_info.get('play_url', {})
                if isinstance(play_url, dict) and play_url.get('uri'):
                    music_url = play_url['uri']
                elif isinstance(play_url, str):
                    music_url = play_url

            # 如果没有视频 URL，降级为普通图片类型
            if not video_urls:
                return {
                    "title": desc,
                    "thumbnail": image_urls[0] if image_urls else cover,
                    "duration": 0,
                    "type": "photo",
                    "images": image_urls,
                    "music_url": music_url,
                    "platform": "douyin",
                }

            return {
                "title": desc,
                "thumbnail": image_urls[0] if image_urls else cover,
                "duration": 0,
                "type": "live_photo",
                "video_url": video_urls[0] if video_urls else "",
                "video_urls": video_urls,
                "images": image_urls,
                "music_url": music_url,
                "platform": "douyin",
            }

        elif images:
            # 普通图片类型
            image_urls = []
            for img in images:
                url_list = img.get('url_list', [])
                if url_list:
                    image_urls.append(url_list[0])

            # 获取音乐
            music_url = ''
            music_info = detail.get('music', {})
            if music_info:
                play_url = music_info.get('play_url', {})
                if isinstance(play_url, dict) and play_url.get('uri'):
                    music_url = play_url['uri']
                elif isinstance(play_url, str):
                    music_url = play_url

            return {
                "title": desc,
                "thumbnail": image_urls[0] if image_urls else cover,
                "duration": 0,
                "type": "photo",
                "images": image_urls,
                "music_url": music_url,
                "platform": "douyin",
            }

        else:
            # 视频类型
            video_info = detail.get('video', {})
            play_addr = video_info.get('play_addr', {})
            url_list = play_addr.get('url_list', [])

            duration = video_info.get('duration', 0)

            return {
                "title": desc,
                "thumbnail": cover,
                "duration": duration,
                "type": "video",
                "video_url": url_list[0] if url_list else "",
                "platform": "douyin",
            }

    except Exception as e:
        logger.error(f"抖音 API 调用失败: {e}")
        return None


def extract_with_api(url: str, platform: str) -> Optional[dict]:
    """
    使用 API 提取内容（同步包装，用于非 async 环境）

    Args:
        url: 视频链接
        platform: 平台名称

    Returns:
        dict: 提取结果，失败返回 None
    """
    if not config.get("api.enabled", True):
        return None

    try:
        if platform == "douyin":
            result = asyncio.run(_extract_douyin_api(url))
        elif platform == "tiktok":
            result = asyncio.run(_extract_tiktok_api(url))
        else:
            return None

        if result:
            logger.info(f"API 提取成功: {result.get('title', '')[:30]}...")
        return result

    except Exception as e:
        logger.error(f"API 提取失败: {e}")
        return None


async def extract_with_api_async(url: str, platform: str) -> Optional[dict]:
    """
    使用 API 提取内容（异步版本，用于 async 环境如 FastAPI）

    Args:
        url: 视频链接
        platform: 平台名称

    Returns:
        dict: 提取结果，失败返回 None
    """
    if not config.get("api.enabled", True):
        return None

    try:
        if platform == "douyin":
            result = await _extract_douyin_api(url)
        elif platform == "tiktok":
            result = await _extract_tiktok_api(url)
        else:
            return None

        if result:
            logger.info(f"API 提取成功: {result.get('title', '')[:30]}...")
        return result

    except Exception as e:
        logger.error(f"API 提取失败: {e}")
        return None
