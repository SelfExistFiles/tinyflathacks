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
    """
    确保内容开头只有一段用 --- 包裹的 Front Matter
    如果已有 Front Matter，则提取并修正；如果没有，则新建。
    """
    content = content.lstrip()
    
    # 如果开头有 ---，提取第一段 Front Matter
    if content.startswith('---'):
        lines = content.splitlines()
        # 找到第二个 --- 的位置
        end_index = -1
        for i in range(1, len(lines)):
            if lines[i].strip() == '---':
                end_index = i
                break
        
        if end_index != -1:
            # 提取 Front Matter 内容（去掉第一行和最后一行 ---）
            fm_lines = lines[1:end_index]
            # 剩余内容作为正文
            body_lines = lines[end_index+1:]
            body = '\n'.join(body_lines).lstrip()
            
            # 构建 Front Matter 字典
            fm_dict = {}
            for line in fm_lines:
                if ':' in line:
                    key, val = line.split(':', 1)
                    fm_dict[key.strip()] = val.strip()
            
            # 覆盖或补充关键字段
            fm_dict['title'] = default_title
            fm_dict['date'] = default_date
            fm_dict['thumbnail'] = thumbnail_url
            if 'draft' not in fm_dict:
                fm_dict['draft'] = 'false'
            
            # 重新拼接 Front Matter（按固定顺序）
            ordered_keys = ['title', 'date', 'description', 'categories', 'tags', 'thumbnail', 'draft']
            new_fm_lines = []
            for key in ordered_keys:
                if key in fm_dict:
                    val = fm_dict[key]
                    # 处理 categories 和 tags
                    if key in ['categories', 'tags']:
                        val_str = val.strip('"\'')
                        if val_str.startswith('[') and val_str.endswith(']'):
                            new_fm_lines.append(f'{key}: {val_str}')
                        else:
                            items = [item.strip().strip('"\'') for item in val_str.split(',')]
                            new_fm_lines.append(f'{key}: [{", ".join(items)}]')
                    else:
                        # 确保字符串值被引号包裹（除非是布尔值或数字）
                        if isinstance(val, str) and val not in ['true', 'false'] and not val.isdigit():
                            if not (val.startswith('"') or val.startswith("'")):
                                val = f'"{val}"'
                        new_fm_lines.append(f'{key}: {val}')
            
            return '---\n' + '\n'.join(new_fm_lines) + '\n---\n\n' + body
    
    # 如果没有 Front Matter，直接创建新的
    return f'''---
title: {default_title}
date: {default_date}
thumbnail: {thumbnail_url}
draft: false
---

{content}'''

def generate_and_save():
    api_key = os.getenv("GEMINI_API_KEY")
    unsplash_key = os.getenv("UNSPLASH_ACCESS_KEY")

    if not api_key:
        print("错误: 未找到 GEMINI_API_KEY 环境变量")
        sys.exit(1)

    client = genai.Client(api_key=api_key)
    chosen = random.choice(topics)
    today = datetime.date.today().strftime("%Y-%m-%d")

    # 修复图片路径：确保 static/images 目录存在，且路径正确
    img_filename = f"/{chosen['title']}-{today}.jpg"

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
1. Front Matter (MUST be wrapped with --- on separate lines, YAML format):
   ---
   title: "How We..."
   date: "{today}"
   description: "..."
   categories: ["Living Room"]
   tags: ["Small Spaces"]
   thumbnail: "{thumbnail_url}"
   draft: false
   ---
2. Intro & Before: The Cluttered Nightmare (Include markdown image `![Before Makeover]({thumbnail_url})`)
3. The Fix & Furniturebox Discoveries
4. After: How It Changed Our Daily Life
5. Budget Breakdown & Final Verdict

Word count: 1200 - 1500 words. Return standard Markdown directly.
"""

    full_content = generate_article_with_gemini(client, prompt)

    # 提取 AI 生成的标题（用于文件名）
    title_match = re.search(r'^title:\s*["\']?(.*?)["\']?\s*$', full_content, re.MULTILINE)
    raw_title = title_match.group(1).strip() if title_match else chosen['title']
    file_slug = slugify(raw_title)

    # 修正 Front Matter（传入提取到的标题，以确保一致性）
    full_content = ensure_front_matter(
        full_content,
        raw_title,
        today,
        thumbnail_url
    )

    # 保存文件
    filename = f"content/posts/{file_slug}.md"
    os.makedirs(os.path.dirname(filename), exist_ok=True)

    with open(filename, "w", encoding="utf-8") as f:
        f.write(full_content)

    print(f"✅ 文章与配图处理完成，成功保存至: {filename}")

if __name__ == "__main__":
    generate_and_save()