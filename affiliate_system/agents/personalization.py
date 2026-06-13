"""Agent 2: Media Personalization & Assembly"""
import json
import os
from openai import OpenAI


class PersonalizationAgent:
    """Customizes media content based on individual affiliate profiles and audience demographics."""

    DEMOGRAPHICS_PROFILES = {
        "gen_z": {"tone": "casual, trendy, fun", "language": "Gen Z slang", "focus": "FOMO, peer influence, viral trends"},
        "millennial": {"tone": "practical, value-driven", "language": "conversational", "focus": "financial benefits, convenience, lifestyle upgrade"},
        "professional": {"tone": "formal, data-driven", "language": "business language", "focus": "ROI, efficiency, professional growth"},
        "general": {"tone": "friendly, clear", "language": "simple Vietnamese", "focus": "ease of use, security, savings"},
    }

    def __init__(self):
        self.client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL"),
        )
        self.model = os.getenv("DEFAULT_LLM_MODEL", "google/gemma-4-31b-it")

    def personalize(self, content: dict, affiliate: dict) -> dict:
        """Adapt content to match affiliate's audience demographics and interests."""
        demographics = affiliate.get("demographics", "general")
        profile = self.DEMOGRAPHICS_PROFILES.get(demographics, self.DEMOGRAPHICS_PROFILES["general"])
        interests = affiliate.get("interests", "")
        platform = affiliate.get("platform", "social_media")

        prompt = f"""You are a content personalization expert for zalopay Vietnam.
Adapt this marketing content for a specific affiliate's audience.

Original Content:
- Title: {content.get('title', '')}
- Body: {content.get('body', '')}
- Hashtags: {content.get('hashtags', '')}
- CTA: {content.get('call_to_action', '')}

Affiliate Profile:
- Demographics: {demographics}
- Interests: {interests}
- Platform: {platform}
- Tone: {profile['tone']}
- Language style: {profile['language']}
- Key focus: {profile['focus']}

Rewrite the content to perfectly match this audience. Keep the core message but adapt tone, language, and emphasis.

Return JSON with same fields:
{{
  "title": "adapted title",
  "body": "adapted body text",
  "hashtags": "adapted hashtags",
  "call_to_action": "adapted CTA",
  "personalization_notes": "brief note on what was adapted"
}}

Respond in Vietnamese. Return ONLY the JSON."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
                temperature=0.6,
            )
            raw = response.choices[0].message.content.strip()
            raw = raw.replace("```json", "").replace("```", "").strip()
            result = json.loads(raw)
            result["personalized"] = True
            result["demographics_target"] = demographics
            return result
        except (json.JSONDecodeError, Exception):
            content["personalized"] = True
            content["personalization_notes"] = f"Được tùy chỉnh cho đối tượng {demographics}"
            return content

    def score_content(self, content: dict, affiliate: dict) -> float:
        """Score content relevance for a specific affiliate audience (0-100)."""
        demographics = affiliate.get("demographics", "general")
        interests = affiliate.get("interests", "")

        prompt = f"""Rate this marketing content relevance score from 0-100 for the target audience.

Content: {content.get('title', '')} - {content.get('body', '')[:100]}
Target: {demographics} audience interested in {interests}

Return ONLY a single integer number between 0 and 100."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=10,
                temperature=0.3,
            )
            score_text = response.choices[0].message.content.strip()
            score = float("".join(c for c in score_text if c.isdigit() or c == "."))
            return min(100.0, max(0.0, score))
        except Exception:
            return 75.0

    def select_best_variant(self, variants: list, affiliate: dict) -> dict:
        """Select best A/B/C content variant for a specific affiliate."""
        if not variants:
            return {}
        best = max(variants, key=lambda v: self.score_content(v, affiliate))
        best["selected_for"] = affiliate.get("username", "affiliate")
        return best
