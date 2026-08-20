import os
import sys
import datetime
import random
import re
import time
from google import genai
from google.genai import types

# 主题池与对应 Furniturebox UK 产品线
topics = [
    {
        "title": "small-dining-room-makeover",
        "desc": "小户型餐厅/客厅角落改造，使用 Furniturebox 的折叠/可伸缩餐桌",
        "furniturebox_products": ["Chelsea White Extendable Dining Table", "Novara Velvet Chairs", "Roma Glass Table Set"],
        "prompt_concept": "A bright UK apartment dining corner with a chic extendable dining table and velvet chairs, warm natural light from sash windows, modern stylish Scandinavian-UK interior, photorealistic."
    },
    {
        "title": "compact-living-room-zones",
        "desc": "利用 Furniturebox 的小巧沙发与嵌套茶几，在小客厅划分工作与放松区域",
        "furniturebox_products": ["Santorini Velvet Sofa", "Lucia Nest of Tables", "Sienna High Gloss Coffee Table"],
        "prompt_concept": "A compact modern British living room with a sleek velvet sofa and a wooden nest of coffee tables, aesthetic UK home decor, photorealistic 8k."
    },
    {
        "title": "balcony-and-patio-hacks",
        "desc": "英国小阳台/狭长后院改造，利用 Furniturebox 户外 Bistro 套装实现早晨咖啡自由",
        "furniturebox_products": ["Barcelona Rattan Bistro Set", "Milan Folding Garden Set"],
        "prompt_concept": "A charming small London flat balcony with a rattan bistro table and two folding chairs, fairy lights, potted plants, overlooking brick terraced houses."
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

def generate_image_with_gemini(client, prompt_text, output_path):
    """
    使用 generate_images 标准接口生成图片，若无权限或格式不匹配则优雅降级
    """
    print(f"🎨 正在尝试生成配图...")
    try:
        result = client.models.generate_images(
            model='imagen-3.0-generate-002',
            prompt=prompt_text,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio="16:9",
                output_mime_type="image/jpeg"
            )
        )
        
        if result and hasattr(result, 'generated_images') and result.generated_images:
            for generated_image in result.generated_images:
                with open(output_path, "wb") as f:
                    f.write(generated_image.image.image_bytes)
                print(f"✅ Gemini 配图成功保存至: {output_path}")
                return True
    except Exception as e:
        print(f"ℹ️ 生图 API 未响应 ({e})，使用默认高品质占位图。")
    return False

def generate_article_with_retry(client, prompt, max_retries=3):
    """
    带指数退避和重试机制的文章生成，应对 429 (限流) 和 503 (服务器高负载)
    """
    models_to_try = ['gemini-3.1-flash-lite', 'gemini-3.6-flash']
    
    for attempt in range(1, max_retries + 1):
        for model_name in models_to_try:
            try:
                print(f"正在尝试使用模型生成文章 (第 {attempt} 轮尝试): {model_name} ...")
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt
                )
                if response.text:
                    return response.text
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    wait_time = attempt * 12
                    print(f"⚠️ {model_name} 触发限流 (429)，等待 {wait_time} 秒...")
                    time.sleep(wait_time)
                elif "503" in err_str or "UNAVAILABLE" in err_str:
                    wait_time = attempt * 10
                    print(f"⚠️ {model_name} 服务繁忙 (503)，等待 {wait_time} 秒...")
                    time.sleep(wait_time)
                else:
                    print(f"⚠️ {model_name} 报错: {e}")
                    
    raise RuntimeError("所有模型生成尝试均失败，请检查 API 额度与 Key 状态。")

def generate_and_save():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("错误: 未找到 GEMINI_API_KEY 环境变量")
        sys.exit(1)

    client = genai.Client(api_key=api_key)
    chosen = random.choice(topics)
    today = datetime.date.today().strftime("%Y-%m-%d")
    
    img_filename = f"static/images/{chosen['title']}-{today}.jpg"
    os.makedirs("static/images", exist_ok=True)
    
    image_generated = generate_image_with_gemini(client, chosen["prompt_concept"], img_filename)
    thumbnail_url = f"/{img_filename}" if image_generated else "https://images.unsplash.com/photo-1555041469-a586c61ea9bc?w=800"

    prompt = f"""
    请以 tinyflathacks.co.uk 的风格写一篇英文博客文章。

    **文章主题：** {chosen['desc']}
    **重点提及的本地家具品牌与产品：** 参考 Furniturebox.co.uk 的产品（如 {', '.join(chosen['furniturebox_products'])}），突出其“Next Day Free UK Delivery”、“Budget-Friendly”和“Space-Saving Designs”的特点。

    **写作风格要求（必须严格遵守以去除 AI 味）：**
    1. 用第一人称 "I" 或 "we" 写作，像一个住在大不列颠（如 London, Manchester 或 Bristol）的真实租房者/小户型屋主在分享亲身经历。
    2. 使用英式拼写（organise 而不是 organize, colour 而不是 color, flat 而不是 apartment, cosy 而不是 cozy）。
    3. 语言极度口语化且地道，自然嵌入以下英式表达：
       - "proper useful" 或 "proper bargain"
       - "faff"（指麻烦事，如 "assembling flat-pack furniture can be a bit of a faff"）
       - "honestly" 或 "to be fair"
       - "a bit of a nightmare"
       - "sorted"
    4. 带有适度的英式自嘲幽默（比如吐槽英国阴雨天晾衣服、卷尺量错尺寸、搬运大体积家具卡在狭窄楼道等）。
    5. **绝对禁止**使用典型 AI 套话（如 "delve into", "unleash", "realm", "tapestry", "game-changer"）。
    6. 包含具体真实的数据（如房间具体尺寸 35m2, 花费金额 £250, 搬运时间等）。

    **内容结构要求：**
    1. Front Matter（YAML 格式）：
       - title:（必须有吸引力、像真实博客，例如 "How We Squeezed a Proper 4-Seater Dining Area into Our 35m2 London Flat"）
       - date: "{today}"
       - description
       - categories
       - tags
       - thumbnail: "{thumbnail_url}"
       - draft: false
    2. 引言：吐槽空间太小的痛点，引发英国租房党共鸣。
    3. "Before: The Cluttered Nightmare"：改造前的惨状（附带 Markdown 图片占位符 `![Before Makeover]({thumbnail_url})`）。
    4. "The Fix & Furniturebox Discoveries"：如何挑选 Furniturebox.co.uk 的家具（提到次日送达和性价比）。
    5. "After: How It Changed Our Daily Life"：改造后的体验与空间对比。
    6. "Budget & Final Verdict"：花费明细清单与实用小建议。

    **字数要求：** 1200-1500 词

    请直接输出标准的 Markdown 内容。
    """

    full_content = generate_article_with_retry(client, prompt)

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
