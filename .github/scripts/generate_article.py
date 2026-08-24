import os
import sys
import datetime
import random
import re
import time
import requests
from google import genai

# 主题池与对应 Furniturebox UK 产品线及 Unsplash 搜索关键词
topics = [
    {
        "title": "small-dining-room-makeover",
        "desc": "小户型餐厅/客厅角落改造，使用 Furniturebox 的折叠/可伸缩餐桌",
        "furniturebox_products": ["Chelsea White Extendable Dining Table", "Novara Velvet Chairs", "Roma Glass Table Set"],
        "unsplash_query": "scandinavian dining room table apartment"
    },
    {
        "title": "compact-living-room-zones",
        "desc": "利用 Furniturebox 的小巧沙发与嵌套茶几，在小客厅划分工作与放松区域",
        "furniturebox_products": ["Santorini Velvet Sofa", "Lucia Nest of Tables", "Sienna High Gloss Coffee Table"],
        "unsplash_query": "modern compact living room sofa"
    },
    {
        "title": "balcony-and-patio-hacks",
        "desc": "英国小阳台/狭长后院改造，利用 Furniturebox 户外 Bistro 套装实现早晨咖啡自由",
        "furniturebox_products": ["Barcelona Rattan Bistro Set", "Milan Folding Garden Set"],
        "unsplash_query": "small balcony bistro set apartment"
    }
]

def slugify(title):
    """将标题转换为干净安全的 ASCII 文件名 slug"""
    slug = title.lower()
    slug = slug.replace('²', '2').replace('³', '3')
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[-\s]+', '-', slug)
    slug = slug.strip('-')
    if len(slug) > 60:
        slug = slug[:60].rstrip('-')
    return slug

def fetch_unsplash_image(query, output_path, access_key):
    """
    使用 Unsplash 官方 API Key 随机获取高质量符合关键词的配图并保存到本地
    """
    print(f"🖼️ 正在从 Unsplash 检索符合关键词 '{query}' 的配图...")
    if not access_key:
        print("⚠️ 未配置 UNSPLASH_ACCESS_KEY，降级使用网络占位图。")
        return False

    url = "https://api.unsplash.com/photos/random"
    headers = {
        "Authorization": f"Client-ID {access_key}"
    }
    params = {
        "query": query,
        "orientation": "landscape"
    }

    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            image_url = data["urls"]["regular"]
            
            img_data = requests.get(image_url, timeout=15).content
            with open(output_path, "wb") as f:
                f.write(img_data)
            print(f"✅ Unsplash 配图成功保存至: {output_path}")
            return True
        else:
            print(f"⚠️ Unsplash API 返回错误状态码: {response.status_code}, 响应: {response.text}")
    except Exception as e:
        print(f"ℹ️ 从 Unsplash 获取图片失败 ({e})，使用默认占位图。")
    return False

def generate_article_with_gemini(client, prompt, max_retries=3):
    """
    使用 Google Gemini API 生成文章，带重试与降级机制
    """
    models_to_try = ['gemini-2.5-flash', 'gemini-2.0-flash']

    for attempt in range(1, max_retries + 1):
        for model_name in models_to_try:
            try:
                print(f"正在尝试使用 Gemini 生成文章 (第 {attempt} 轮尝试): {model_name} ...")
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt
                )
                if response.text:
                    return response.text
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    wait_time = attempt * 10
                    print(f"⚠️ {model_name} 触发限流 (429)，等待 {wait_time} 秒...")
                    time.sleep(wait_time)
                elif "503" in err_str or "UNAVAILABLE" in err_str:
                    wait_time = attempt * 8
                    print(f"⚠️ {model_name} 服务繁忙 (503)，等待 {wait_time} 秒...")
                    time.sleep(wait_time)
                else:
                    print(f"⚠️ {model_name} 报错: {e}")

    raise RuntimeError("所有 Gemini 模型生成尝试均失败，请检查 GEMINI_API_KEY 是否存在及额度情况。")


def ensure_front_matter(content, default_title, default_date, thumbnail_url):
    """确保 Front Matter 被 --- 包裹"""
    # 如果开头已经有 ---，则跳过
    if content.strip().startswith('---'):
        return content
    
    # 尝试提取第一段 YAML 内容（可能没有 ---）
    lines = content.split('\n')
    front_matter_lines = []
    normal_content_lines = []
    in_front_matter = False
    
    # 简单检测：如果第一行是 title: 开头，则认为进入了 Front Matter
    if lines and re.match(r'^\s*title\s*:', lines[0], re.I):
        in_front_matter = True
    
    for i, line in enumerate(lines):
        if in_front_matter:
            # 如果遇到空行且已经收集了标题和日期，则认为 Front Matter 结束
            if line.strip() == '' and i > 0:
                in_front_matter = False
                normal_content_lines.append(line)
                continue
            front_matter_lines.append(line)
        else:
            normal_content_lines.append(line)
    
    # 如果根本没有检测到 Front Matter，直接在最前面插入带 --- 的空白格式
    if not front_matter_lines:
        return f"---\ntitle: {default_title}\ndate: {default_date}\nthumbnail: {thumbnail_url}\ndraft: false\n---\n\n{content}"
    
    # 否则用 --- 包裹
    return '---\n' + '\n'.join(front_matter_lines) + '\n---\n\n' + '\n'.join(normal_content_lines).lstrip()

def generate_and_save():
    api_key = os.getenv("GEMINI_API_KEY")
    unsplash_key = os.getenv("UNSPLASH_ACCESS_KEY")

    if not api_key:
        print("错误: 未找到 GEMINI_API_KEY 环境变量")
        sys.exit(1)

    client = genai.Client(api_key=api_key)
    chosen = random.choice(topics)
    today = datetime.date.today().strftime("%Y-%m-%d")

    img_filename = f"static/images/{chosen['title']}-{today}.jpg"
    os.makedirs("static/images", exist_ok=True)

    image_generated = fetch_unsplash_image(chosen["unsplash_query"], img_filename, unsplash_key)
    thumbnail_url = f"/{img_filename}" if image_generated else "https://images.unsplash.com/photo-1555041469-a586c61ea9bc?w=800"

    prompt = f"""
    Please write a blog post in native British English for tinyflathacks.co.uk.

    **Topic:** {chosen['desc']}
    **Promoted Brand & Products:** Reference Furniturebox.co.uk items ({', '.join(chosen['furniturebox_products'])}), highlighting Next Day Free UK Delivery, budget-friendliness, and space-saving cleverness.

    **Tone & Persona (STRICT):**
    1. Write in 1st person ("I" or "we") as a genuine UK renter living in London, Manchester, or Bristol.
    2. Use British English spelling throughout (organise, colour, flat, cosy, bloody, sorted).
    3. Naturally use slang like "proper useful", "a bit of a faff", "honestly", "sorted", "nightmare".
    4. Add witty British self-deprecation about tight staircases, rainy weather, or assembly failures.
    5. NO AI buzzwords (delve, unleash, realm, tapestry, game-changer).

    **Structure:**
    1. Front Matter (YAML format):
       title: "How We..." (must sound authentic)
       date: "{today}"
       description: "..."
       categories: ["Living Room"]
       tags: ["Small Spaces"]
       thumbnail: "{thumbnail_url}"
       draft: false
    2. Intro & Before: The Cluttered Nightmare (Include markdown image `![Before Makeover]({thumbnail_url})`)
    3. The Fix & Furniturebox Discoveries
    4. After: How It Changed Our Daily Life
    5. Budget Breakdown & Final Verdict

    Word count: 1200 - 1500 words. Return standard Markdown directly.
    """

    full_content = generate_article_with_gemini(client, prompt)

    # 修正 Front Matter 格式
    full_content = ensure_front_matter(
        full_content, 
        raw_title if 'raw_title' in locals() else chosen['title'],
        today,
        thumbnail_url
    )

    # 提取 Front Matter 标题
    title_match = re.search(r'^title:\s*["\']?(.*?)["\']?\s*$', full_content, re.MULTILINE)
    if title_match and title_match.group(1):
        raw_title = title_match.group(1).strip()
        file_slug = slugify(raw_title)
        filename = f"content/posts/{file_slug}.md"
        print(f"📝 成功提取标题: {raw_title}")
    else:
        filename = f"content/posts/{chosen['title']}.md"
        print("⚠️ 未找到明确标题，使用默认主题名作文件名")

    os.makedirs(os.path.dirname(filename), exist_ok=True)

    with open(filename, "w", encoding="utf-8") as f:
        f.write(full_content)

    print(f"✅ 文章与配图处理完成，成功保存至: {filename}")

if __name__ == "__main__":
    generate_and_save()