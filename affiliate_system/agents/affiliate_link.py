"""Agent 3: Affiliate Link Generator"""
import hashlib
import os
import secrets
import string
from datetime import datetime


class AffiliateLinkAgent:
    """Generates unique tracking links and manages commission rules per affiliate/product."""

    BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:5000")

    COMMISSION_TIERS = {
        "bronze": {"min_conversions": 0, "multiplier": 1.0},
        "silver": {"min_conversions": 50, "multiplier": 1.25},
        "gold": {"min_conversions": 150, "multiplier": 1.5},
        "platinum": {"min_conversions": 500, "multiplier": 2.0},
    }

    CAMPAIGN_TEMPLATES = {
        "default": "Standard affiliate campaign",
        "summer_sale": "Summer promotion with 30% bonus commission",
        "new_user": "New user acquisition campaign",
        "loyalty": "Loyalty program for existing users",
        "flash_sale": "24-hour flash sale campaign",
    }

    def generate_tracking_code(self, affiliate_id: int, product_id: int, campaign: str = "default") -> str:
        """Generate a unique, deterministic tracking code."""
        timestamp = datetime.utcnow().isoformat()
        raw = f"{affiliate_id}-{product_id}-{campaign}-{timestamp}-{secrets.token_hex(4)}"
        hash_val = hashlib.md5(raw.encode()).hexdigest()[:8]
        prefix = "".join(secrets.choice(string.ascii_uppercase) for _ in range(3))
        return f"{prefix}{hash_val.upper()}"

    def build_affiliate_url(self, tracking_code: str) -> str:
        return f"{self.BASE_URL}/track/{tracking_code}"

    def get_commission_rate(self, product: dict, affiliate: dict) -> float:
        """Calculate effective commission rate based on product base rate and affiliate tier."""
        base_rate = product.get("commission_rate", 10.0)
        total_conversions = affiliate.get("total_conversions", 0)

        tier = "bronze"
        for tier_name, tier_info in sorted(
            self.COMMISSION_TIERS.items(),
            key=lambda x: x[1]["min_conversions"],
            reverse=True,
        ):
            if total_conversions >= tier_info["min_conversions"]:
                tier = tier_name
                break

        multiplier = self.COMMISSION_TIERS[tier]["multiplier"]
        effective_rate = base_rate * multiplier
        return round(min(effective_rate, 50.0), 2)

    def get_affiliate_tier(self, total_conversions: int) -> str:
        tier = "bronze"
        for tier_name, info in sorted(
            self.COMMISSION_TIERS.items(),
            key=lambda x: x[1]["min_conversions"],
            reverse=True,
        ):
            if total_conversions >= info["min_conversions"]:
                tier = tier_name
                break
        return tier

    def generate_link_bundle(self, affiliate: dict, products: list, campaign: str = "default") -> list:
        """Generate affiliate links for multiple products at once."""
        links = []
        for product in products:
            code = self.generate_tracking_code(affiliate["id"], product["id"], campaign)
            commission = self.get_commission_rate(product, affiliate)
            links.append({
                "affiliate_id": affiliate["id"],
                "product_id": product["id"],
                "tracking_code": code,
                "url": self.build_affiliate_url(code),
                "campaign": campaign,
                "commission_rate": commission,
                "tier": self.get_affiliate_tier(affiliate.get("total_conversions", 0)),
            })
        return links

    def get_campaign_info(self, campaign: str) -> dict:
        return {
            "name": campaign,
            "description": self.CAMPAIGN_TEMPLATES.get(campaign, "Custom campaign"),
            "available_campaigns": list(self.CAMPAIGN_TEMPLATES.keys()),
        }

    def validate_link(self, tracking_code: str) -> dict:
        """Validate a tracking code and return its metadata."""
        from models import AffiliateLink
        link = AffiliateLink.query.filter_by(tracking_code=tracking_code).first()
        if not link:
            return {"valid": False, "error": "Link not found"}
        if link.status != "active":
            return {"valid": False, "error": "Link is inactive"}
        return {
            "valid": True,
            "link_id": link.id,
            "product_id": link.product_id,
            "affiliate_id": link.affiliate_id,
            "campaign": link.campaign,
        }
