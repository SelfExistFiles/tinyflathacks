import os
import sys
import datetime
import random
import re
import time
import requests
from openai import OpenAI

# AnyRouter 中转站配置
ANYROUTER_API_KEY = os.getenv("ANYROUTER_API_KEY")
ANYROUTER_BASE_URL = os.getenv("ANYROUTER_BASE_URL", "https://anyrouter.top")

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
    
def generate_article_with_claude(client, prompt, max_retries=3):
    """
    使用 AnyRouter 上的 Claude 模型生成文章，自带重试机制
    """
    # 包含了精简别名与全称，确保兼容 AnyRouter 的不同分组映射
    models_to_try = [
        "claude-3-5-sonnet",            # 别名（最常兼容）
        "claude-3-7-sonnet",            # 别名
        "claude-3-5-sonnet-20241022",   # 完整型号
        "claude-3-7-sonnet-20250219",   # 完整型号
        "claude-3-5-haiku-20241022",    # 修正拼写后的 Haiku
        "claude-3-5-haiku",             # Haiku 别名
    ]

    for attempt in range(1, max_retries + 1):
        for model_name in models_to_try:
            try:
                print(f"正在尝试使用 AnyRouter Claude 模型生成文章 (第 {attempt} 轮尝试): {model_name} ...")
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7
                )
                content = response.choices[0].message.content
                if content:
                    return content
            except Exception as e:
                err_str = str(e)
                print(f"⚠️ 模型 {model_name} 响应异常: {err_str}")
                time.sleep(2)

    raise RuntimeError("所有 Claude 模型生成尝试均失败，请检查 AnyRouter API Key 额度与节点状态。")

def generate_and_save():
    if not ANYROUTER_API_KEY:
        print("错误: 未找到 ANYROUTER_API_KEY 环境变量")
        sys.exit(1)

    unsplash_key = os.getenv("UNSPLASH_ACCESS_KEY")

    # 初始化 AnyRouter OpenAI SDK Client
    client = OpenAI(
        api_key=ANYROUTER_API_KEY,
        base_url=ANYROUTER_BASE_URL
    )

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

    full_content = generate_article_with_claude(client, prompt)

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
