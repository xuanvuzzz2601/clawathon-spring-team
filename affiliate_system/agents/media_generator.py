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

        prompt = f"""You are an expert marketing copywriter for zalopay Vietnam.
Generate compelling {content_type} content for {platform} platform.

Product Information:
- Name: {product['name']}
- Description: {product['description']}
- Price: {product['price']:,.0f} VND
- Category: {product['category']}
- Commission Rate: {product['commission_rate']}%

Style: {variant_style}

Return a JSON object with exactly these fields:
{{
  "title": "catchy headline (max 80 chars)",
  "body": "main content text (150-300 chars for social, adapt for platform)",
  "hashtags": "5-8 relevant hashtags as space-separated string",
  "call_to_action": "action button text (max 30 chars)",
  "key_benefits": ["benefit 1", "benefit 2", "benefit 3"]
}}

Respond in Vietnamese. Return ONLY the JSON, no markdown."""

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
            enhance_prompt = f"""Translate this Vietnamese product description into a vivid English image generation prompt.
Product: {product.get('name', '')}
User description: {description}
Category: {product.get('category', '')}

Write a detailed English prompt for generating a professional marketing image.
Focus on visual elements, style, mood, and composition. Max 200 words.
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
