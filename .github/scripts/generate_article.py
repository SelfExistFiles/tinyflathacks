import os
import sys
import datetime
import random
import re
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
    """将标题转换为适合文件名的 slug"""
    slug = title.lower()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[-\s]+', '-', slug)
    slug = slug.strip('-')
    if len(slug) > 60:
        slug = slug[:60].rstrip('-')
    return slug

def generate_image_with_gemini(client, prompt_text, output_path):
    """
    使用 Gemini / Imagen 模型生成真实图片，带完备容错
    """
    print(f"🎨 正在使用 Gemini 生成图片: {prompt_text[:50]}...")
    try:
        # 使用最新的 imagen-3.0-generate-001 或通用生成接口
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
                print(f"✅ 图片生成成功并保存至: {output_path}")
                return True
    except Exception as e:
        print(f"⚠️ 图片生成未成功 ({e})，自动回退至默认占位图，不影响文章生成。")
    return False

def generate_and_save():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("错误: 未找到 GEMINI_API_KEY 环境变量")
        sys.exit(1)

    client = genai.Client(api_key=api_key)
    chosen = random.choice(topics)
    today = datetime.date.today().strftime("%Y-%m-%d")
    
    # 设定生成图片的存储路径
    img_filename = f"static/images/{chosen['title']}-{today}.jpg"
    os.makedirs("static/images", exist_ok=True)
    
    # 1. 生成图片（失败自动降级）
    image_generated = generate_image_with_gemini(client, chosen["prompt_concept"], img_filename)
    thumbnail_url = f"/{img_filename}" if image_generated else "https://images.unsplash.com/photo-1555041469-a586c61ea9bc?w=800"

    # 2. 生成文章（使用官方推荐的最新模型 gemini-3.6-flash）
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
    6. 包含具体真实的数据（如房间具体尺寸 35m², 花费金额 £250, 搬运时间等）。

    **内容结构要求：**
    1. Front Matter（YAML 格式）：
       - title:（必须有吸引力、像真实博客，例如 "How We Squeezed a Proper 4-Seater Dining Area into Our 35m² London Flat"）
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

    print(f"正在生成文章: {chosen['title']} ...")
    try:
        response = client.models.generate_content(
            model='gemini-3.6-flash',
            contents=prompt
        )
        full_content = response.text
    except Exception as e:
        print(f"⚠️ gemini-3.6-flash 遇到问题，尝试回退模型 gemini-3.1-flash-lite: {e}")
        response = client.models.generate_content(
            model='gemini-3.1-flash-lite',
            contents=prompt
        )
        full_content = response.text

    # 从生成文章中提取 title 作为文件名
    title_match = re.search(r'^title:\s*"(.+?)"', full_content, re.MULTILINE)
    if title_match:
        raw_title = title_match.group(1)
        file_slug = slugify(raw_title)
        filename = f"content/posts/{file_slug}.md"
        print(f"📝 提取到标题: {raw_title}")
    else:
        filename = f"content/posts/{chosen['title']}.md"

    os.makedirs(os.path.dirname(filename), exist_ok=True)
    
    with open(filename, "w", encoding="utf-8") as f:
        f.write(full_content)
        
    print(f"✅ 文章与配图处理完成并保存至: {filename}")

if __name__ == "__main__":
    generate_and_save()
