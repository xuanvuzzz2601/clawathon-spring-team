"""Agent 1: Product Reader & Media Generator"""
import base64
import json
import os
from openai import OpenAI


class MediaGeneratorAgent:
    """Reads product information and generates marketing media content using LLM."""

    PLATFORMS = ["instagram", "facebook", "tiktok", "linkedin", "twitter"]
    CONTENT_TYPES = ["post", "story", "carousel", "video_script", "banner"]

    def __init__(self):
        self.client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL"),
        )
        self.model = os.getenv("DEFAULT_LLM_MODEL", "google/gemma-4-31b-it")
        self._image_client = None

    @property
    def image_client(self):
        if self._image_client is None:
            key = os.getenv("IMAGE_API_KEY")
            if not key:
                raise ValueError("IMAGE_API_KEY is not set. Add a real OpenAI API key to use image generation.")
            self._image_client = OpenAI(
                api_key=key,
                base_url=os.getenv("IMAGE_API_BASE_URL", "https://api.openai.com/v1"),
            )
        return self._image_client

    def generate(self, product: dict, platform: str = "instagram", content_type: str = "post", variant: str = "A") -> dict:
        """Generate marketing content for a product on a specific platform."""
        variant_style = {
            "A": "professional and informative",
            "B": "casual and engaging with emojis",
            "C": "urgent and promotional with limited-time offer",
        }.get(variant, "professional")

        prompt = f"""Bạn là chuyên gia marketing của VNG Corporation / ZaloPay Việt Nam.

QUY TẮC BẮT BUỘC (phải tuân thủ tuyệt đối):
1. CHỈ tạo nội dung quảng bá cho sản phẩm/dịch vụ thuộc hệ sinh thái VNG, Zalopay hoặc GreenNode.
2. TUYỆT ĐỐI KHÔNG đề cập bất kỳ tên đối thủ nào: MoMo, VNPay, ShopeePay, Moca, VNPT Pay, Viettel Pay, hay bất kỳ ví điện tử/fintech/ngân hàng nào khác.
3. KHÔNG so sánh với đối thủ, kể cả gián tiếp.
4. Mọi nội dung phải gắn với thương hiệu Zalopay hoặc VNG.
5. Nếu mô tả sản phẩm không rõ ràng, hãy kết nối nó với hệ sinh thái Zalopay.

Tạo nội dung {content_type} cho nền tảng {platform}.
Phong cách: {variant_style}

Thông tin sản phẩm:
- Tên: {product['name']}
- Mô tả: {product['description']}
- Giá: {product['price']:,.0f} VND
- Danh mục: {product['category']}
- Hoa hồng: {product['commission_rate']}%

Trả về JSON với đúng các trường sau:
{{
  "title": "tiêu đề hấp dẫn (tối đa 80 ký tự)",
  "body": "nội dung chính (150-300 ký tự, phù hợp {platform})",
  "hashtags": "5-8 hashtag liên quan cách nhau bằng khoảng trắng, bắt đầu bằng #zalopay",
  "call_to_action": "văn bản nút hành động (tối đa 30 ký tự)",
  "key_benefits": ["lợi ích 1", "lợi ích 2", "lợi ích 3"]
}}

Trả lời bằng tiếng Việt. Chỉ trả về JSON, không có markdown."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=600,
                temperature=0.7,
            )
            raw = response.choices[0].message.content.strip()
            raw = raw.replace("```json", "").replace("```", "").strip()
            return json.loads(raw)
        except (json.JSONDecodeError, Exception):
            return self._fallback_content(product, platform, content_type)

    def generate_ab_test(self, product: dict, platform: str) -> list:
        """Generate A/B/C test variants for a product."""
        results = []
        for variant in ["A", "B", "C"]:
            content = self.generate(product, platform, "post", variant)
            content["variant"] = variant
            results.append(content)
        return results

    def generate_image(self, description: str, size: str = "1024x1024", product: dict = None) -> dict:
        """Generate a product image from a text description using gpt-image-1."""
        image_model = os.getenv("IMAGE_MODEL", "openai/gpt-image-1")

        # If product info is provided, build a richer English prompt via LLM
        if product:
            enhance_prompt = f"""You are a marketing designer for Zalopay / VNG Vietnam.

STRICT RULES:
- The image must represent Zalopay or VNG branding ONLY.
- NEVER include logos, names, or visual references to competitors (MoMo, VNPay, ShopeePay, etc.).
- Use ZaloPay brand colors (blue #1A73E8, purple accents) when relevant.
- If the brand name appears as text in the image, it MUST be spelled "Zalopay" (lowercase 'p') — NEVER "ZaloPay" (uppercase 'P' is forbidden).

Translate this Vietnamese description into a detailed English image generation prompt:
Product: {product.get('name', '')}
User description: {description}
Category: {product.get('category', '')}

Write a detailed English prompt for a professional marketing image.
Focus on: visual elements, style, mood, composition, ZaloPay branding. Max 200 words.
Return ONLY the prompt text, no explanation."""
            try:
                resp = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": enhance_prompt}],
                    max_tokens=250,
                    temperature=0.6,
                )
                enhanced = resp.choices[0].message.content.strip()
            except Exception:
                enhanced = description
        else:
            enhanced = description

        response = self.image_client.images.generate(
            model=image_model,
            prompt=enhanced,
            size=size,
            n=1,
        )

        image_data = response.data[0]
        result = {
            "image_url": getattr(image_data, "url", None),
            "revised_prompt": getattr(image_data, "revised_prompt", enhanced),
            "original_description": description,
            "size": size,
            "model": image_model,
        }

        # gpt-image-1 may return b64_json instead of url
        if not result["image_url"] and hasattr(image_data, "b64_json") and image_data.b64_json:
            result["image_b64"] = image_data.b64_json
            result["image_url"] = f"data:image/png;base64,{image_data.b64_json}"

        return result

    def _fallback_content(self, product: dict, platform: str, content_type: str) -> dict:
        return {
            "title": f"Khám phá {product['name']} ngay hôm nay!",
            "body": f"{product['description'][:200]}... Đăng ký ngay để nhận ưu đãi đặc biệt từ zalopay!",
            "hashtags": "#zalopay #ViDienTu #ThanhToanOnline #TienLoi #AnToan",
            "call_to_action": "Đăng ký ngay",
            "key_benefits": ["Nhanh chóng", "An toàn", "Tiện lợi"],
        }
