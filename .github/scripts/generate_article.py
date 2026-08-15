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

def slugify(title):
    """将标题转换为适合文件名的 slug"""
    # 转小写，移除特殊字符，空格替换为短横线
    slug = title.lower()
    slug = re.sub(r'[^\w\s-]', '', slug)  # 移除标点符号
    slug = re.sub(r'[-\s]+', '-', slug)   # 空格和连续短横线替换为单个短横线
    slug = slug.strip('-')
    # 截断过长的 slug（保留前 60 个字符）
    if len(slug) > 60:
        slug = slug[:60].rstrip('-')
    return slug

def get_unsplash_thumbnail(query_keywords):
    """从 Unsplash 获取与主题匹配的图片"""
    api_key = os.getenv("UNSPLASH_API_KEY")
    if not api_key:
        # fallback 到固定图片
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

def generate_and_save():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("错误: 未找到 GEMINI_API_KEY 环境变量")
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
       - "proper"（用作强调，如 "proper useful"）
       - "faff"（指麻烦事）
       - "honestly" 或 "to be fair"
       - "I'll be honest with you" 或 "right, let me tell you"
       - "a bit of a nightmare"
    4. 包含幽默感和适度的自嘲（比如提到自己测量错了尺寸、买错了东西、拖延了很久才动手）
    5. 不要使用 "delve into"、"unleash"、"realm" 这类典型的 AI 套话
    6. 段落要短，句子要有节奏感，不要写长难句
    7. 要有具体的数字（如房间尺寸、花费金额、时间）

    **内容结构要求：**
    1. Front Matter（YAML 格式）包含：
       - title:（必须是一个有吸引力、口语化、带点好奇心的标题，像一个真实博主会写的，比如 "How We Finally Fixed Our Tiny Bathroom (Without Breaking Anything)" 或 "The £200 Hallway Hack That Changed Everything"）
       - date（设为今天）
       - description（一句话概括，吸引人点击）
       - categories
       - tags
       - draft: false
    2. 引言：点出问题，让读者产生共鸣
    3. "Before" 部分：描述改造前的糟糕状态（具体细节）
    4. "The Plan" 或 "What We Changed"：列出具体改动
    5. "After" 部分：改造后的对比感受
    6. 一个简短的总结或建议

    **字数要求：** 1200-1500 词

    请直接输出 Markdown 格式的文章，不要加额外的说明文字。
    """

    print(f"正在生成文章: {chosen['title']} ...")
    response = client.models.generate_content(
        model='gemini-3.1-flash-lite',
        contents=prompt
    )

    full_content = response.text
    today = datetime.date.today().strftime("%Y-%m-%d")
    
    # ---- 从文章中提取 title 来生成文件名 ----
    title_match = re.search(r'^title:\s*"(.+?)"', full_content, re.MULTILINE)
    if title_match:
        raw_title = title_match.group(1)
        file_slug = slugify(raw_title)
        filename = f"content/posts/{file_slug}.md"
        print(f"📝 提取到标题: {raw_title}")
    else:
        # fallback：如果提取不到标题，用原来的命名方式
        filename = f"content/posts/{chosen['title']}.md"
        print("⚠️ 警告：未能从文章中提取标题，使用默认文件名")

    os.makedirs(os.path.dirname(filename), exist_ok=True)
    
    # 在文章开头插入图片引用
    if full_content.startswith("---"):
        parts = full_content.split("---", 2)
        if len(parts) >= 3:
            front_matter = parts[1]
            if "thumbnail:" not in front_matter:
                front_matter += f'\nthumbnail: "{thumbnail_url}"'
            full_content = f"---{front_matter}---{parts[2]}"
    
    with open(filename, "w", encoding="utf-8") as f:
        f.write(full_content)
        
    print(f"✅ 文章已成功生成并保存至: {filename}")
    print(f"🖼️ 配图: {thumbnail_url}")

if __name__ == "__main__":
    generate_and_save()