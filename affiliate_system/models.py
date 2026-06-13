from datetime import datetime
from database import db
from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(200), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="affiliate")  # 'admin' | 'affiliate'
    affiliate_id = db.Column(db.Integer, db.ForeignKey("affiliates.id"), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    affiliate = db.relationship("Affiliate", backref="user", uselist=False, foreign_keys=[affiliate_id])

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "role": self.role,
            "affiliate_id": self.affiliate_id,
            "is_active": self.is_active,
        }


class Product(db.Model):
    __tablename__ = "products"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(100))
    image_url = db.Column(db.String(500))
    commission_rate = db.Column(db.Float, default=10.0)
    status = db.Column(db.String(20), default="active")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    links = db.relationship("AffiliateLink", backref="product", lazy=True)
    media = db.relationship("MediaContent", backref="product", lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "price": self.price,
            "category": self.category,
            "image_url": self.image_url,
            "commission_rate": self.commission_rate,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
        }


class Affiliate(db.Model):
    __tablename__ = "affiliates"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(200), unique=True, nullable=False)
    username = db.Column(db.String(100), unique=True, nullable=False)
    demographics = db.Column(db.String(50), default="general")
    interests = db.Column(db.Text)
    platform = db.Column(db.String(50), default="social_media")
    status = db.Column(db.String(20), default="active")
    total_clicks = db.Column(db.Integer, default=0)
    total_conversions = db.Column(db.Integer, default=0)
    total_earnings = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    links = db.relationship("AffiliateLink", backref="affiliate", lazy=True)
    rewards = db.relationship("Reward", backref="affiliate", lazy=True)
    media = db.relationship("MediaContent", backref="affiliate", lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "username": self.username,
            "demographics": self.demographics,
            "interests": self.interests,
            "platform": self.platform,
            "status": self.status,
            "total_clicks": self.total_clicks,
            "total_conversions": self.total_conversions,
            "total_earnings": self.total_earnings,
            "created_at": self.created_at.isoformat(),
        }


class AffiliateLink(db.Model):
    __tablename__ = "affiliate_links"
    id = db.Column(db.Integer, primary_key=True)
    affiliate_id = db.Column(db.Integer, db.ForeignKey("affiliates.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    tracking_code = db.Column(db.String(32), unique=True, nullable=False)
    campaign = db.Column(db.String(100), default="default")
    commission_rate = db.Column(db.Float, default=10.0)
    clicks = db.Column(db.Integer, default=0)
    conversions = db.Column(db.Integer, default=0)
    revenue_generated = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default="active")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    click_events = db.relationship("Click", backref="link", lazy=True)
    conversion_events = db.relationship("Conversion", backref="link", lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "affiliate_id": self.affiliate_id,
            "affiliate_name": self.affiliate.name if self.affiliate else None,
            "product_id": self.product_id,
            "product_name": self.product.name if self.product else None,
            "tracking_code": self.tracking_code,
            "campaign": self.campaign,
            "commission_rate": self.commission_rate,
            "clicks": self.clicks,
            "conversions": self.conversions,
            "revenue_generated": self.revenue_generated,
            "conversion_rate": round(self.conversions / self.clicks * 100, 2) if self.clicks > 0 else 0,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
        }


class Click(db.Model):
    __tablename__ = "clicks"
    id = db.Column(db.Integer, primary_key=True)
    link_id = db.Column(db.Integer, db.ForeignKey("affiliate_links.id"), nullable=False)
    ip_address = db.Column(db.String(50))
    user_agent = db.Column(db.String(500))
    referer = db.Column(db.String(500))
    country = db.Column(db.String(50))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "link_id": self.link_id,
            "ip_address": self.ip_address,
            "country": self.country,
            "timestamp": self.timestamp.isoformat(),
        }


class Conversion(db.Model):
    __tablename__ = "conversions"
    id = db.Column(db.Integer, primary_key=True)
    link_id = db.Column(db.Integer, db.ForeignKey("affiliate_links.id"), nullable=False)
    order_id = db.Column(db.String(100))
    order_value = db.Column(db.Float, nullable=False)
    commission_amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default="pending")
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "link_id": self.link_id,
            "order_id": self.order_id,
            "order_value": self.order_value,
            "commission_amount": self.commission_amount,
            "status": self.status,
            "timestamp": self.timestamp.isoformat(),
        }


class MediaContent(db.Model):
    __tablename__ = "media_content"
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    affiliate_id = db.Column(db.Integer, db.ForeignKey("affiliates.id"), nullable=True)
    content_type = db.Column(db.String(50), default="post")
    platform = db.Column(db.String(50), default="instagram")
    title = db.Column(db.String(300))
    body = db.Column(db.Text)
    hashtags = db.Column(db.Text)
    call_to_action = db.Column(db.String(200))
    variant = db.Column(db.String(10), default="A")
    personalized = db.Column(db.Boolean, default=False)
    performance_score = db.Column(db.Float, default=0.0)
    image_url = db.Column(db.String(1000))
    image_prompt = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "product_id": self.product_id,
            "product_name": self.product.name if self.product else None,
            "affiliate_id": self.affiliate_id,
            "affiliate_name": self.affiliate.name if self.affiliate else None,
            "content_type": self.content_type,
            "platform": self.platform,
            "title": self.title,
            "body": self.body,
            "hashtags": self.hashtags,
            "call_to_action": self.call_to_action,
            "variant": self.variant,
            "personalized": self.personalized,
            "performance_score": self.performance_score,
            "image_url": self.image_url,
            "image_prompt": self.image_prompt,
            "created_at": self.created_at.isoformat(),
        }


class Reward(db.Model):
    __tablename__ = "rewards"
    id = db.Column(db.Integer, primary_key=True)
    affiliate_id = db.Column(db.Integer, db.ForeignKey("affiliates.id"), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    reward_type = db.Column(db.String(50), default="commission")
    status = db.Column(db.String(20), default="pending")
    period_start = db.Column(db.DateTime)
    period_end = db.Column(db.DateTime)
    description = db.Column(db.Text)
    paid_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "affiliate_id": self.affiliate_id,
            "affiliate_name": self.affiliate.name if self.affiliate else None,
            "amount": self.amount,
            "reward_type": self.reward_type,
            "status": self.status,
            "period_start": self.period_start.isoformat() if self.period_start else None,
            "period_end": self.period_end.isoformat() if self.period_end else None,
            "description": self.description,
            "paid_at": self.paid_at.isoformat() if self.paid_at else None,
            "created_at": self.created_at.isoformat(),
        }
