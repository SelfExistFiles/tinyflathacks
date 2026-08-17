import os
import sys
import datetime
import random
import re
import requests
from google import genai

# 主题池与对应图片关键词
topics = [
    {
        "title": "bathroom-makeover",
        "desc": "小户型浴室改造，重点是收纳和空间利用",
        "image_keywords": ["bathroom+storage", "small+bathroom+renovation", "bathroom+organization", "compact+bathroom"]
    },
    {
        "title": "hallway-storage", 
        "desc": "小户型玄关收纳，如何让入口不再杂乱",
        "image_keywords": ["hallway+storage", "entryway+organization", "small+hallway", "corridor+storage"]
    },
    {
        "title": "kitchen-foldable-furniture",
        "desc": "小户型厨房的折叠家具选择与使用体验",
        "image_keywords": ["foldable+kitchen+table", "small+kitchen+organization", "compact+kitchen", "kitchen+storage+solutions"]
    },
    {
        "title": "living-room-zones",
        "desc": "如何在一个小客厅里划分出工作、用餐、放松三个区域",
        "image_keywords": ["small+living+room+design", "multi+functional+furniture", "compact+living+room", "small+apartment+living+room"]
    }
]

def get_unsplash_thumbnail(query_keywords):
    """从 Unsplash 获取与主题匹配的图片"""
    api_key = os.getenv("UNSPLASH_API_KEY")
    if not api_key:
        return "https://images.unsplash.com/photo-1555041469-a586c61ea9bc?w=800"
    
    keyword = random.choice(query_keywords)
    url = f"https://api.unsplash.com/photos/random?query={keyword}&orientation=landscape&client_id={api_key}&w=800"
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.json()["urls"]["regular"]
        else:
            return "https://images.unsplash.com/photo-1555041469-a586c61ea9bc?w=800"
    except:
        return "https://images.unsplash.com/photo-1555041469-a586c61ea9bc?w=800"

def force_fix_front_matter(content):
    """
    强制修复 Front Matter - 无论 AI 生成什么格式，都强行提取 title 并重建
    """
    lines = content.split('\n')
    
    # 1. 尝试提取 title
    title = None
    for line in lines[:30]:  # 只在前30行找
        match = re.search(r'^title:\s*["\']?(.+?)["\']?$', line.strip())
        if match:
            title = match.group(1).strip()
            break
    
    # 如果没找到 title，用默认值
    if not title:
        title = "Tiny Flat Hack - Storage Solution"
        print("⚠️ 未找到 title，使用默认值")
    
    # 2. 尝试提取 description
    description = None
    for line in lines[:30]:
        match = re.search(r'^description:\s*["\']?(.+?)["\']?$', line.strip())
        if match:
            description = match.group(1).strip()
            break
    
    if not description:
        description = f"Tips and ideas for {title.lower()}"
    
    # 3. 尝试提取 categories
    categories = ["DIY", "Home Improvement"]
    for i, line in enumerate(lines[:30]):
        if 'categories:' in line:
            # 看下一行有没有列表项
            if i + 1 < len(lines) and lines[i+1].strip().startswith('-'):
                cats = []
                for j in range(i+1, min(i+6, len(lines))):
                    if lines[j].strip().startswith('-'):
                        cats.append(lines[j].strip()[1:].strip().strip('"'))
                    else:
                        break
                if cats:
                    categories = cats
            break
    
    # 4. 尝试提取 tags
    tags = ["small-space", "organization", "storage"]
    for i, line in enumerate(lines[:30]):
        if 'tags:' in line:
            if i + 1 < len(lines) and lines[i+1].strip().startswith('-'):
                tag_list = []
                for j in range(i+1, min(i+6, len(lines))):
                    if lines[j].strip().startswith('-'):
                        tag_list.append(lines[j].strip()[1:].strip().strip('"'))
                    else:
                        break
                if tag_list:
                    tags = tag_list
            break
    
    # 5. 提取正文（跳过前面的 Front Matter 部分）
    body_start = 0
    dash_count = 0
    for i, line in enumerate(lines):
        if line.strip() == '---':
            dash_count += 1
            if dash_count == 2:
                body_start = i + 1
                break
    
    # 如果找不到第二个 ---，从第一个 --- 后面找
    if body_start == 0:
        for i, line in enumerate(lines):
            if line.strip() == '---':
                body_start = i + 1
                break
    
    # 如果还是找不到，从头开始
    if body_start == 0 or body_start >= len(lines):
        body_start = 0
    
    body_lines = lines[body_start:]
    # 移除正文中可能存在的孤立 ---
    body_lines = [line if line.strip() != '---' else '--- (separator)' for line in body_lines]
    
    # 6. 重建干净的 Front Matter
    today = datetime.date.today().strftime("%Y-%m-%d")
    clean_front_matter = f"""---
title: "{title}"
date: {today}
description: "{description}"
categories:
{chr(10).join(['  - "' + c.strip('"') + '"' for c in categories])}
tags:
{chr(10).join(['  - "' + t.strip('"') + '"' for t in tags])}
draft: false
thumbnail: "{get_unsplash_thumbnail(['home', 'interior'])}"
---"""
    
    # 7. 组装最终内容
    final_content = clean_front_matter + '\n' + '\n'.join(body_lines)
    return final_content, title

def generate_and_save():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ 错误: 未找到 GEMINI_API_KEY 环境变量")
        sys.exit(1)

    client = genai.Client(api_key=api_key)
    chosen = random.choice(topics)
    
    # 获取配图
    thumbnail_url = get_unsplash_thumbnail(chosen["image_keywords"])
    
    prompt = f"""
    请以 tinyflathacks.co.uk 的风格写一篇英文博客文章。

    **文章主题：** {chosen['desc']}

    **写作风格要求（必须严格遵守）：**
    1. 用第一人称 "I" 或 "we" 写作，像一个普通英国人在分享自己的亲身经历
    2. 使用英式拼写（organise 而不是 organize, colour 而不是 color, flat 而不是 apartment）
    3. 语言口语化，包含以下英式口语表达（适当使用，不要堆砌）：
       - "proper"、"faff"、"honestly"、"to be fair"
       - "I'll be honest with you"、"a bit of a nightmare"
    4. 包含幽默感和适度的自嘲
    5. 不要使用 "delve into"、"unleash"、"realm" 这类 AI 套话
    6. 段落要短，句子要有节奏感
    7. 要有具体的数字（如房间尺寸、花费金额、时间）

    **内容结构要求：**
    1. Front Matter 包含以下字段（用 YAML 格式，以 --- 包裹）：
       title: 一个有吸引力的标题
       date: {datetime.date.today().strftime("%Y-%m-%d")}
       description: 一句话概括
       categories: ["分类1", "分类2"]
       tags: ["标签1", "标签2", "标签3"]
       draft: false
    2. 正文结构：引言 -> "Before" 部分 -> "The Plan" -> "After" 部分 -> 总结

    **字数要求：** 1200-1500 词

    请直接输出 Markdown 格式的文章，不要加额外的说明文字。
    """

    print(f"正在生成文章: {chosen['title']} ...")
    response = client.models.generate_content(
        model='gemini-3.1-flash-lite',
        contents=prompt
    )

    full_content = response.text
    
    # ---- 强制修复 Front Matter ----
    print("正在修复 Front Matter 格式...")
    fixed_content, title = force_fix_front_matter(full_content)
    
    # ---- 生成安全的文件名（用时间戳，不依赖标题） ----
    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    random_suffix = random.randint(1000, 9999)
    # 从标题取前几个词作为文件名的可读部分
    title_words = re.sub(r'[^\w\s]', '', title).strip().lower().split()[:4]
    title_slug = '-'.join(title_words) if title_words else chosen['title']
    filename = f"content/posts/{timestamp}-{title_slug}-{random_suffix}.md"
    
    # 确保目录存在
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    
    # 保存文件
    with open(filename, "w", encoding="utf-8") as f:
        f.write(fixed_content)
        
    print(f"✅ 文章已成功生成并保存至: {filename}")
    print(f"📝 标题: {title[:80]}...")
    print(f"🖼️ 配图: {thumbnail_url}")

if __name__ == "__main__":
    generate_and_save()
