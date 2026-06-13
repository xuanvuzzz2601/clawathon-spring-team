"""Agent 4: Referral Tracking & Rewards"""
import json
import os
from datetime import datetime, timedelta
from openai import OpenAI


class RewardsTrackerAgent:
    """Monitors conversions, calculates rewards, and generates performance reports."""

    BONUS_THRESHOLDS = [
        {"min_conversions": 100, "bonus_pct": 20, "label": "Century Bonus"},
        {"min_conversions": 50, "bonus_pct": 10, "label": "Half-Century Bonus"},
        {"min_conversions": 25, "bonus_pct": 5, "label": "Quarter Bonus"},
    ]

    def __init__(self):
        self.client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL"),
        )
        self.model = os.getenv("DEFAULT_LLM_MODEL", "google/gemma-4-31b-it")

    def calculate_period_rewards(self, affiliate_id: int, period_days: int = 30) -> dict:
        """Calculate total rewards for an affiliate over a period."""
        from models import AffiliateLink, Conversion, Affiliate
        from database import db

        affiliate = Affiliate.query.get(affiliate_id)
        if not affiliate:
            return {"error": "Affiliate not found"}

        period_end = datetime.utcnow()
        period_start = period_end - timedelta(days=period_days)

        links = AffiliateLink.query.filter_by(affiliate_id=affiliate_id).all()
        link_ids = [l.id for l in links]

        conversions = Conversion.query.filter(
            Conversion.link_id.in_(link_ids),
            Conversion.timestamp >= period_start,
            Conversion.timestamp <= period_end,
            Conversion.status == "approved",
        ).all()

        total_commission = sum(c.commission_amount for c in conversions)
        total_order_value = sum(c.order_value for c in conversions)
        conversion_count = len(conversions)

        bonus_amount = 0.0
        bonuses_earned = []
        for threshold in self.BONUS_THRESHOLDS:
            if conversion_count >= threshold["min_conversions"]:
                bonus = total_commission * threshold["bonus_pct"] / 100
                bonus_amount += bonus
                bonuses_earned.append({
                    "label": threshold["label"],
                    "amount": bonus,
                    "pct": threshold["bonus_pct"],
                })
                break

        total_reward = total_commission + bonus_amount

        return {
            "affiliate_id": affiliate_id,
            "affiliate_name": affiliate.name,
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "conversion_count": conversion_count,
            "total_order_value": round(total_order_value, 2),
            "base_commission": round(total_commission, 2),
            "bonus_amount": round(bonus_amount, 2),
            "total_reward": round(total_reward, 2),
            "bonuses_earned": bonuses_earned,
        }

    def get_performance_metrics(self, affiliate_id: int) -> dict:
        """Get comprehensive performance metrics for an affiliate."""
        from models import AffiliateLink, Click, Conversion, Affiliate

        affiliate = Affiliate.query.get(affiliate_id)
        if not affiliate:
            return {}

        links = AffiliateLink.query.filter_by(affiliate_id=affiliate_id).all()
        link_ids = [l.id for l in links]

        total_clicks = sum(l.clicks for l in links)
        total_conversions = sum(l.conversions for l in links)
        total_revenue = sum(l.revenue_generated for l in links)
        conversion_rate = (total_conversions / total_clicks * 100) if total_clicks > 0 else 0

        best_link = max(links, key=lambda l: l.conversions, default=None)
        top_campaign = {}
        campaign_stats = {}
        for link in links:
            c = link.campaign
            if c not in campaign_stats:
                campaign_stats[c] = {"clicks": 0, "conversions": 0}
            campaign_stats[c]["clicks"] += link.clicks
            campaign_stats[c]["conversions"] += link.conversions

        return {
            "affiliate_id": affiliate_id,
            "affiliate_name": affiliate.name,
            "total_links": len(links),
            "total_clicks": total_clicks,
            "total_conversions": total_conversions,
            "total_revenue": round(total_revenue, 2),
            "conversion_rate": round(conversion_rate, 2),
            "best_performing_link": best_link.tracking_code if best_link else None,
            "campaign_breakdown": campaign_stats,
            "tier": self._get_tier(total_conversions),
        }

    def generate_ai_report(self, affiliate_id: int) -> str:
        """Use LLM to generate a natural language performance report."""
        metrics = self.get_performance_metrics(affiliate_id)
        rewards = self.calculate_period_rewards(affiliate_id)

        prompt = f"""You are a performance analyst for zalopay affiliate program.
Write a brief, encouraging performance summary report in Vietnamese for this affiliate.

Performance Data:
- Tên affiliate: {metrics.get('affiliate_name')}
- Tổng clicks: {metrics.get('total_clicks')}
- Tổng conversions: {metrics.get('total_conversions')}
- Tỷ lệ chuyển đổi: {metrics.get('conversion_rate')}%
- Doanh thu tạo ra: {metrics.get('total_revenue'):,.0f} VND
- Hạng hiện tại: {metrics.get('tier')}
- Thưởng kỳ này: {rewards.get('total_reward', 0):,.0f} VND

Write 3-4 sentences: performance summary, highlights, and actionable improvement tip.
Keep it positive and motivating. Respond in Vietnamese only."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300,
                temperature=0.7,
            )
            return response.choices[0].message.content.strip()
        except Exception:
            return f"Affiliate {metrics.get('affiliate_name')} đã có hiệu suất tốt với {metrics.get('total_conversions')} conversions và tỷ lệ chuyển đổi {metrics.get('conversion_rate')}%."

    def process_pending_rewards(self) -> list:
        """Process all pending reward calculations."""
        from models import Reward, Affiliate
        affiliates = Affiliate.query.filter_by(status="active").all()
        processed = []
        for affiliate in affiliates:
            calc = self.calculate_period_rewards(affiliate.id, 30)
            if calc.get("total_reward", 0) > 0:
                processed.append({
                    "affiliate_id": affiliate.id,
                    "amount": calc["total_reward"],
                    "conversions": calc["conversion_count"],
                })
        return processed

    def _get_tier(self, conversions: int) -> str:
        if conversions >= 500:
            return "platinum"
        elif conversions >= 150:
            return "gold"
        elif conversions >= 50:
            return "silver"
        return "bronze"

    def get_leaderboard(self, limit: int = 10) -> list:
        """Get top affiliates by earnings."""
        from models import Affiliate
        affiliates = Affiliate.query.filter_by(status="active").order_by(
            Affiliate.total_earnings.desc()
        ).limit(limit).all()
        return [
            {
                "rank": i + 1,
                "affiliate_id": a.id,
                "name": a.name,
                "username": a.username,
                "total_conversions": a.total_conversions,
                "total_earnings": a.total_earnings,
                "tier": self._get_tier(a.total_conversions),
            }
            for i, a in enumerate(affiliates)
        ]
