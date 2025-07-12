import os
import json
import aiohttp
from bs4 import BeautifulSoup
from hoshino import Service, priv, util
from hoshino.typing import CQEvent, MessageSegment

sv = Service('查番', help_='AGE动漫番剧搜索插件\n用法：查番 番剧名称', enable_on_default=False)

# 配置文件
from .config import HEADERS, CACHE_DIR, SSL_CONTEXT

os.makedirs(CACHE_DIR, exist_ok=True)

def _get_cache_path(user_id: str) -> str:
    return os.path.join(CACHE_DIR, f"{user_id}.json")

def _save_cache(user_id: str, data: dict):
    cache_path = _get_cache_path(user_id)
    with open(cache_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def _load_cache(user_id: str) -> dict:
    cache_path = _get_cache_path(user_id)
    if not os.path.exists(cache_path):
        return None
    with open(cache_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def _build_anime_message(anime: dict):
    # 返回消息段列表而不是拼接字符串
    msg = []
    if anime.get('封面图'):
        msg.append(MessageSegment.image(anime['封面图']))
    
    text_content = [
        f"📺 标题：{anime['标题']}",
        f"⏱ 首播：{anime['首播时间']}",
        f"📝 简介：{anime['简介'][:100]}...",
        f"🔗 详情：{anime['详情链接']}"
    ]
    
    if anime.get('播放链接'):
        text_content.append(f"▶️ 播放：{anime['播放链接']}")
    
    msg.append(MessageSegment.text('\n'.join(text_content)))
    return msg

async def _fetch_search_results(keyword: str) -> str:
    url = 'https://www.agedm.org/search'
    conn = aiohttp.TCPConnector(ssl=SSL_CONTEXT)
    async with aiohttp.ClientSession(headers=HEADERS, connector=conn) as session:
        async with session.get(url, params={'query': keyword, 'page': 1}) as resp:
            resp.raise_for_status()
            return await resp.text()

def _parse_results(html: str, keyword: str) -> dict:
    soup = BeautifulSoup(html, 'html.parser')
    anime_list = []

    for item in soup.find_all('div', class_='cata_video_item'):
        title_tag = item.find('h5')
        if not title_tag:
            continue

        cover_img = item.find('img', class_='video_thumbs')
        play_btn = item.find('a', class_='btn-danger')

        anime = {
            '标题': title_tag.text.strip(),
            '详情链接': title_tag.a['href'] if title_tag.a else '',
            '首播时间': _extract_detail(item, '首播时间'),
            '简介': _extract_detail(item, '简介'),
            '封面图': cover_img['data-original'] if cover_img else '',
            '播放链接': play_btn['href'] if play_btn else ''
        }
        anime_list.append(anime)

    return {'番剧列表': anime_list}

def _extract_detail(soup, field: str) -> str:
    field_span = soup.find('span', string=lambda t: t and t.strip().startswith(f"{field}："))
    if not field_span:
        return ''

    detail_div = field_span.find_parent('div', class_='video_detail_info')
    field_span.extract()
    return detail_div.get_text(strip=True)

@sv.on_prefix('查番')
async def search_anime(bot, ev: CQEvent):
    keyword = ev.message.extract_plain_text().strip()
    if not keyword:
        await bot.send(ev, "请输入要查询的番剧名称，例如：查番 遮天")
        return

    try:
        html = await _fetch_search_results(keyword)
        result = _parse_results(html, keyword)
        anime_list = result['番剧列表']
        total = len(anime_list)

        if total == 0:
            await bot.send(ev, f"未找到与「{keyword}」相关的番剧")
            return

        if total > 2:
            page_size = 2
            total_pages = (total + page_size - 1) // page_size
            cache_data = {
                "keyword": keyword,
                "all_results": anime_list,
                "total_pages": total_pages,
                "current_page": 1,
                "page_size": page_size
            }
            _save_cache(ev.user_id, cache_data)

            await bot.send(ev, f"🔍找到{total}条结果（第1/{total_pages}页）")
            for anime in anime_list[:page_size]:
                for msg_seg in _build_anime_message(anime):
                    await bot.send(ev, msg_seg)
            await bot.send(ev, "输入 下一页 继续查看，上一页 返回")
        else:
            await bot.send(ev, f"找到{total}条结果：")
            for anime in anime_list:
                for msg_seg in _build_anime_message(anime):
                    await bot.send(ev, msg_seg)

    except Exception as e:
        sv.logger.error(f"搜索失败: {str(e)}", exc_info=True)
        await bot.send(ev, "番剧查询服务暂时不可用，请稍后再试")

@sv.on_keyword('下一页')
async def next_page(bot, ev: CQEvent):
    cache = _load_cache(ev.user_id)
    if not cache:
        await bot.send(ev, "请先使用【查番】进行搜索")
        return

    current_page = cache['current_page'] + 1
    if current_page > cache['total_pages']:
        await bot.send(ev, "已经是最后一页了")
        return

    start = (current_page - 1) * cache['page_size']
    page_data = cache['all_results'][start:start + cache['page_size']]

    cache['current_page'] = current_page
    _save_cache(ev.user_id, cache)

    await bot.send(ev, f"📖第{current_page}/{cache['total_pages']}页")
    for anime in page_data:
        for msg_seg in _build_anime_message(anime):
            await bot.send(ev, msg_seg)
    if current_page < cache['total_pages']:
        await bot.send(ev, "输入【下一页】继续查看，【上一页】返回")

@sv.on_keyword('上一页')
async def prev_page(bot, ev: CQEvent):
    cache = _load_cache(ev.user_id)
    if not cache:
        await bot.send(ev, "请先使用【查番】进行搜索")
        return

    current_page = cache['current_page'] - 1
    if current_page < 1:
        await bot.send(ev, "已经是第一页了")
        return

    start = (current_page - 1) * cache['page_size']
    page_data = cache['all_results'][start:start + cache['page_size']]

    cache['current_page'] = current_page
    _save_cache(ev.user_id, cache)

    await bot.send(ev, f"📖第{current_page}/{cache['total_pages']}页")
    for anime in page_data:
        for msg_seg in _build_anime_message(anime):
            await bot.send(ev, msg_seg)
    await bot.send(ev, "输入【下一页】继续查看，【上一页】返回")