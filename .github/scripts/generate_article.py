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
    slug = title.lower()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[-\s]+', '-', slug)
    slug = slug.strip('-')
    if len(slug) > 60:
        slug = slug[:60].rstrip('-')
    return slug

def get_unsplash_thumbnail(query_keywords):
    """从 Unsplash 获取与主题匹配的图片"""
    api_key = os.getenv("UNSPLASH_API_KEY")
    if not api_key:
        print("⚠️ 未设置 UNSPLASH_API_KEY，使用默认图片")
        return "https://images.unsplash.com/photo-1555041469-a586c61ea9bc?w=800"
    
    keyword = random.choice(query_keywords)
    url = f"https://api.unsplash.com/photos/random?query={keyword}&orientation=landscape&client_id={api_key}&w=800"
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.json()["urls"]["regular"]
        else:
            print(f"⚠️ Unsplash API 返回状态码 {response.status_code}，使用默认图片")
            return "https://images.unsplash.com/photo-1555041469-a586c61ea9bc?w=800"
    except Exception as e:
        print(f"⚠️ Unsplash 请求失败: {e}，使用默认图片")
        return "https://images.unsplash.com/photo-1555041469-a586c61ea9bc?w=800"

def clean_front_matter(content):
    """
    清理 AI 生成的 Markdown，确保 Front Matter 格式正确
    1. 找到第一个 --- 和第二个 --- 之间的内容作为 YAML
    2. 如果在 YAML 内或之后有孤立的 ---，移除或替换
    3. 确保 YAML 中的字符串不包含未转义的冒号和特殊字符
    """
    lines = content.splitlines()
    front_matter_lines = []
    body_lines = []
    in_front_matter = False
    front_matter_count = 0
    
    for line in lines:
        stripped = line.strip()
        
        # 处理 YAML 分隔符
        if stripped == '---':
            front_matter_count += 1
            if front_matter_count == 1:
                # 第一次遇到 ---：开始 Front Matter
                in_front_matter = True
                front_matter_lines.append(line)
                continue
            elif front_matter_count == 2:
                # 第二次遇到 ---：结束 Front Matter
                in_front_matter = False
                front_matter_lines.append(line)
                continue
        
        # 分类行
        if in_front_matter:
            front_matter_lines.append(line)
        else:
            # 正文里孤立的 '---' 替换掉
            if stripped == '---':
                body_lines.append('"—"')
            else:
                body_lines.append(line)
    
    # 如果 Front Matter 没有正确闭合，强制补一个
    if front_matter_count < 2:
        print("⚠️ 检测到 Front Matter 未闭合，自动补全")
        front_matter_lines.append('---')
        front_matter_count += 1
    
    # 如果完全没有找到 Front Matter（可能 AI 没生成），手动创建一个
    if front_matter_count == 0:
        print("⚠️ 未检测到 Front Matter，手动创建")
        today = datetime.date.today().strftime("%Y-%m-%d")
        front_matter_lines = [
            '---',
            f'title: "未命名文章"',
            f'date: {today}',
            'description: "自动生成的文章"',
            'categories:',
            '  - "未分类"',
            'tags:',
            '  - "自动生成"',
            'draft: false',
            '---'
        ]
        # 把原内容作为正文
        body_lines = content.splitlines()
    
    cleaned = '\n'.join(front_matter_lines + body_lines)
    return cleaned

def generate_and_save():
    """主生成函数"""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ 错误: 未找到 GEMINI_API_KEY 环境变量")
        print("请设置: export GEMINI_API_KEY='你的API密钥'")
        sys.exit(1)

    print("✅ 找到 GEMINI_API_KEY")
    
    client = genai.Client(api_key=api_key)
    chosen = random.choice(topics)
    print(f"📌 选中主题: {chosen['title']}")
    
    # 获取配图
    thumbnail_url = get_unsplash_thumbnail(chosen["image_keywords"])
    print(f"🖼️ 配图地址: {thumbnail_url[:80]}...")
    
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

    **内容结构要求（非常重要）：**
    1. Front Matter（YAML 格式）必须严格遵循以下格式，分隔符 '---' 必须单独成行：
       ---
       title: "你的标题"
       date: {datetime.date.today().strftime("%Y-%m-%d")}
       description: "一句话概括"
       categories:
         - "分类名"
       tags:
         - "标签1"
         - "标签2"
       draft: false
       ---
    2. **重要警告**：正文中绝对不能再出现单独成行的 '---'，否则会导致 YAML 解析失败。如果需要使用分隔线，请使用 '***' 或 '___' 代替。
    3. 引言：点出问题，让读者产生共鸣
    4. "Before" 部分：描述改造前的糟糕状态（具体细节）
    5. "The Plan" 或 "What We Changed"：列出具体改动
    6. "After" 部分：改造后的对比感受
    7. 一个简短的总结或建议

    **字数要求：** 1200-1500 词

    请直接输出 Markdown 格式的文章，不要加额外的说明文字。确保 Front Matter 格式完全正确，以 '---' 开始和结束，正文中不要使用 '---'。
    """

    print("🤖 正在调用 Gemini API 生成文章...")
    try:
        response = client.models.generate_content(
            model='gemini-3.1-flash-lite',
            contents=prompt
        )
        print("✅ Gemini API 调用成功")
    except Exception as e:
        print(f"❌ Gemini API 调用失败: {e}")
        sys.exit(1)

    full_content = response.text
    print(f"📄 生成内容长度: {len(full_content)} 字符")
    
    # ---- 清理 Front Matter 格式 ----
    print("🧹 正在清理 Front Matter 格式...")
    full_content = clean_front_matter(full_content)
    
    # ---- 从文章中提取 title 来生成文件名 ----
    # 更宽松的 title 匹配
    title_match = re.search(r'^title:\s*["\']?(.+?)["\']?$', full_content, re.MULTILINE)
    if title_match:
        raw_title = title_match.group(1).strip()
        # 如果标题太长，截断
        if len(raw_title) > 80:
            raw_title = raw_title[:80]
        file_slug = slugify(raw_title)
        filename = f"content/posts/{file_slug}.md"
        print(f"📝 提取到标题: {raw_title[:60]}...")
    else:
        # fallback：如果提取不到标题，用主题名
        filename = f"content/posts/{chosen['title']}.md"
        print("⚠️ 警告：未能从文章中提取标题，使用默认文件名")

    # 确保目录存在
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    
    # 在文章开头插入图片引用（thumbnail）
    if full_content.startswith("---"):
        parts = full_content.split("---", 2)
        if len(parts) >= 3:
            front_matter = parts[1]
            if "thumbnail:" not in front_matter:
                front_matter += f'\nthumbnail: "{thumbnail_url}"'
            full_content = f"---{front_matter}---{parts[2]}"
    else:
        # 如果没有 Front Matter，直接在前面加
        full_content = f'---\nthumbnail: "{thumbnail_url}"\n---\n{full_content}'
    
    # 保存文件
    try:
        with open(filename, "w", encoding="utf-8") as f:
            f.write(full_content)
        print(f"✅ 文章已成功生成并保存至: {filename}")
        print(f"🖼️ 配图: {thumbnail_url}")
    except Exception as e:
        print(f"❌ 保存文件失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 TinyFlatHacks 文章生成器")
    print("=" * 60)
    generate_and_save()
    print("=" * 60)
    print("🎉 完成！")
