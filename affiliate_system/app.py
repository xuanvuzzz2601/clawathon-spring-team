#!/usr/bin/env python3
"""Affiliate Media Generation & Referral Tracking System — Flask Backend"""
import os
import sys
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, render_template, request, session
from flask_login import LoginManager, current_user, login_required, login_user, logout_user

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from database import db, init_db
from models import Affiliate, AffiliateLink, Click, Conversion, MediaContent, Product, Reward, User
from agents import AffiliateLinkAgent, MediaGeneratorAgent, PersonalizationAgent, RewardsTrackerAgent

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///affiliate.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["JSON_SORT_KEYS"] = False
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-in-prod")

login_manager = LoginManager(app)
login_manager.login_view = "login_page"

init_db(app)

media_agent = MediaGeneratorAgent()
persona_agent = PersonalizationAgent()
link_agent = AffiliateLinkAgent()
rewards_agent = RewardsTrackerAgent()


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# ─── Auth decorators ─────────────────────────────────────────────────────────

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({"error": "Authentication required"}), 401
        if current_user.role != "admin":
            return jsonify({"error": "Admin access required"}), 403
        return f(*args, **kwargs)
    return decorated


def affiliate_or_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({"error": "Authentication required"}), 401
        return f(*args, **kwargs)
    return decorated


def _scoped_affiliate_id():
    """Return the affiliate_id filter: admin sees all (None), affiliate sees only themselves."""
    if current_user.role == "affiliate":
        return current_user.affiliate_id
    return request.args.get("affiliate_id", type=int) or None


# ─── Pages ───────────────────────────────────────────────────────────────────

@app.route("/login")
def login_page():
    if current_user.is_authenticated:
        return redirect("/")
    return render_template("login.html")


@app.route("/")
def index():
    if not current_user.is_authenticated:
        return redirect("/login")
    return render_template("index.html")


@app.route("/track/<tracking_code>")
def track_click(tracking_code):
    validation = link_agent.validate_link(tracking_code)
    if not validation["valid"]:
        return jsonify({"error": validation["error"]}), 404

    link = AffiliateLink.query.filter_by(tracking_code=tracking_code).first()
    click = Click(
        link_id=link.id,
        ip_address=request.remote_addr,
        user_agent=request.headers.get("User-Agent", "")[:499],
        referer=request.headers.get("Referer", "")[:499],
    )
    db.session.add(click)
    link.clicks += 1
    link.affiliate.total_clicks += 1
    db.session.commit()

    product = db.session.get(Product, link.product_id)
    return redirect(f"/?product={product.id}&ref={tracking_code}")


# ─── Auth API ─────────────────────────────────────────────────────────────────

@app.route("/api/auth/login", methods=["POST"])
def api_login():
    data = request.json or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")
    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400

    user = User.query.filter_by(username=username).first()
    if not user or not user.check_password(password) or not user.is_active:
        return jsonify({"error": "Invalid credentials"}), 401

    login_user(user, remember=True)
    result = user.to_dict()
    if user.role == "affiliate" and user.affiliate:
        result["affiliate_name"] = user.affiliate.name
    return jsonify(result)


@app.route("/api/auth/logout", methods=["POST"])
@login_required
def api_logout():
    logout_user()
    return jsonify({"message": "Logged out"})


@app.route("/api/auth/me")
def api_me():
    if not current_user.is_authenticated:
        return jsonify({"authenticated": False}), 401
    result = current_user.to_dict()
    result["authenticated"] = True
    if current_user.role == "affiliate" and current_user.affiliate:
        result["affiliate_name"] = current_user.affiliate.name
    return jsonify(result)


# ─── Dashboard ───────────────────────────────────────────────────────────────

@app.route("/api/dashboard")
@affiliate_or_admin
def dashboard():
    aff_id = _scoped_affiliate_id()

    if aff_id:
        links = AffiliateLink.query.filter_by(affiliate_id=aff_id).all()
        total_clicks = sum(l.clicks for l in links)
        total_conversions = sum(l.conversions for l in links)
        total_revenue = sum(l.revenue_generated for l in links)
        total_links = len(links)
    else:
        total_clicks = db.session.query(db.func.sum(AffiliateLink.clicks)).scalar() or 0
        total_conversions = db.session.query(db.func.sum(AffiliateLink.conversions)).scalar() or 0
        total_revenue = db.session.query(db.func.sum(AffiliateLink.revenue_generated)).scalar() or 0
        total_links = AffiliateLink.query.count()

    total_products = Product.query.count()
    total_affiliates = Affiliate.query.count()
    total_media = MediaContent.query.count()
    pending_rewards = db.session.query(db.func.sum(Reward.amount)).filter_by(status="pending").scalar() or 0
    conversion_rate = round(total_conversions / total_clicks * 100, 2) if total_clicks > 0 else 0

    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    conv_q = Conversion.query.join(AffiliateLink)
    if aff_id:
        conv_q = conv_q.filter(AffiliateLink.affiliate_id == aff_id)
    recent_conversions = conv_q.filter(Conversion.timestamp >= thirty_days_ago).count()

    top_affiliates = (
        Affiliate.query.filter_by(status="active")
        .order_by(Affiliate.total_earnings.desc()).limit(5).all()
    )
    top_products = (
        db.session.query(Product, db.func.sum(AffiliateLink.conversions).label("total_conv"))
        .join(AffiliateLink, AffiliateLink.product_id == Product.id)
        .group_by(Product.id).order_by(db.text("total_conv DESC")).limit(5).all()
    )

    return jsonify({
        "stats": {
            "total_products": total_products,
            "total_affiliates": total_affiliates,
            "total_links": int(total_links),
            "total_clicks": int(total_clicks),
            "total_conversions": int(total_conversions),
            "total_revenue": round(float(total_revenue), 2),
            "total_media": total_media,
            "pending_rewards": round(float(pending_rewards), 2),
            "conversion_rate": conversion_rate,
            "recent_conversions_30d": recent_conversions,
        },
        "top_affiliates": [a.to_dict() for a in top_affiliates],
        "top_products": [
            {**p.to_dict(), "total_conversions": int(conv or 0)}
            for p, conv in top_products
        ],
        "leaderboard": rewards_agent.get_leaderboard(5),
    })


# ─── Products ─────────────────────────────────────────────────────────────────

@app.route("/api/products", methods=["GET"])
@affiliate_or_admin
def list_products():
    products = Product.query.order_by(Product.created_at.desc()).all()
    return jsonify([p.to_dict() for p in products])


@app.route("/api/products", methods=["POST"])
@admin_required
def create_product():
    data = request.json
    for field in ["name", "price"]:
        if not data.get(field):
            return jsonify({"error": f"Field '{field}' is required"}), 400
    product = Product(
        name=data["name"],
        description=data.get("description", ""),
        price=float(data["price"]),
        category=data.get("category", "general"),
        image_url=data.get("image_url", ""),
        commission_rate=float(data.get("commission_rate", 10.0)),
    )
    db.session.add(product)
    db.session.commit()
    return jsonify(product.to_dict()), 201


@app.route("/api/products/<int:pid>", methods=["PUT"])
@admin_required
def update_product(pid):
    product = db.session.get(Product, pid)
    if not product:
        return jsonify({"error": "Not found"}), 404
    data = request.json
    for field in ["name", "description", "price", "category", "image_url", "commission_rate", "status"]:
        if field in data:
            setattr(product, field, data[field])
    db.session.commit()
    return jsonify(product.to_dict())


@app.route("/api/products/<int:pid>", methods=["DELETE"])
@admin_required
def delete_product(pid):
    product = db.session.get(Product, pid)
    if not product:
        return jsonify({"error": "Not found"}), 404
    db.session.delete(product)
    db.session.commit()
    return jsonify({"message": "Product deleted"})


# ─── Affiliates ───────────────────────────────────────────────────────────────

@app.route("/api/affiliates", methods=["GET"])
@affiliate_or_admin
def list_affiliates():
    if current_user.role == "affiliate":
        affiliates = Affiliate.query.filter_by(id=current_user.affiliate_id).all()
    else:
        affiliates = Affiliate.query.order_by(Affiliate.total_earnings.desc()).all()
    result = []
    for a in affiliates:
        d = a.to_dict()
        d["tier"] = rewards_agent._get_tier(a.total_conversions)
        result.append(d)
    return jsonify(result)


@app.route("/api/affiliates", methods=["POST"])
@admin_required
def create_affiliate():
    data = request.json
    for field in ["name", "email", "username"]:
        if not data.get(field):
            return jsonify({"error": f"Field '{field}' is required"}), 400
    if Affiliate.query.filter_by(email=data["email"]).first():
        return jsonify({"error": "Email already exists"}), 409
    if Affiliate.query.filter_by(username=data["username"]).first():
        return jsonify({"error": "Username already exists"}), 409
    affiliate = Affiliate(
        name=data["name"], email=data["email"], username=data["username"],
        demographics=data.get("demographics", "general"),
        interests=data.get("interests", ""),
        platform=data.get("platform", "social_media"),
    )
    db.session.add(affiliate)
    db.session.commit()
    return jsonify(affiliate.to_dict()), 201


@app.route("/api/affiliates/<int:aid>", methods=["GET"])
@affiliate_or_admin
def get_affiliate(aid):
    if current_user.role == "affiliate" and current_user.affiliate_id != aid:
        return jsonify({"error": "Access denied"}), 403
    affiliate = db.session.get(Affiliate, aid)
    if not affiliate:
        return jsonify({"error": "Not found"}), 404
    d = affiliate.to_dict()
    d["tier"] = rewards_agent._get_tier(affiliate.total_conversions)
    d["metrics"] = rewards_agent.get_performance_metrics(aid)
    return jsonify(d)


@app.route("/api/affiliates/<int:aid>", methods=["PUT"])
@admin_required
def update_affiliate(aid):
    affiliate = db.session.get(Affiliate, aid)
    if not affiliate:
        return jsonify({"error": "Not found"}), 404
    data = request.json
    for field in ["name", "demographics", "interests", "platform", "status"]:
        if field in data:
            setattr(affiliate, field, data[field])
    db.session.commit()
    return jsonify(affiliate.to_dict())


# ─── Affiliate Links ──────────────────────────────────────────────────────────

@app.route("/api/links", methods=["GET"])
@affiliate_or_admin
def list_links():
    affiliate_id = _scoped_affiliate_id()
    product_id = request.args.get("product_id", type=int)
    query = AffiliateLink.query
    if affiliate_id:
        query = query.filter_by(affiliate_id=affiliate_id)
    if product_id:
        query = query.filter_by(product_id=product_id)
    links = query.order_by(AffiliateLink.created_at.desc()).all()
    return jsonify([l.to_dict() for l in links])


@app.route("/api/links/generate", methods=["POST"])
@affiliate_or_admin
def generate_link():
    data = request.json
    req_affiliate_id = data.get("affiliate_id")
    if current_user.role == "affiliate":
        req_affiliate_id = current_user.affiliate_id
    affiliate = db.session.get(Affiliate, req_affiliate_id)
    if not affiliate:
        return jsonify({"error": "Affiliate not found"}), 404
    product = db.session.get(Product, data.get("product_id"))
    if not product:
        return jsonify({"error": "Product not found"}), 404
    campaign = data.get("campaign", "default")

    code = link_agent.generate_tracking_code(affiliate.id, product.id, campaign)
    commission = link_agent.get_commission_rate(product.to_dict(), affiliate.to_dict())
    link = AffiliateLink(
        affiliate_id=affiliate.id, product_id=product.id,
        tracking_code=code, campaign=campaign, commission_rate=commission,
    )
    db.session.add(link)
    db.session.commit()

    result = link.to_dict()
    result["full_url"] = link_agent.build_affiliate_url(code)
    result["tier"] = link_agent.get_affiliate_tier(affiliate.total_conversions)
    return jsonify(result), 201


@app.route("/api/links/bulk-generate", methods=["POST"])
@affiliate_or_admin
def bulk_generate_links():
    data = request.json
    aff_id = current_user.affiliate_id if current_user.role == "affiliate" else data.get("affiliate_id")
    affiliate = db.session.get(Affiliate, aff_id)
    if not affiliate:
        return jsonify({"error": "Affiliate not found"}), 404
    product_ids = data.get("product_ids", [])
    campaign = data.get("campaign", "default")

    created = []
    for pid in product_ids:
        product = db.session.get(Product, pid)
        if not product:
            continue
        code = link_agent.generate_tracking_code(affiliate.id, product.id, campaign)
        commission = link_agent.get_commission_rate(product.to_dict(), affiliate.to_dict())
        link = AffiliateLink(
            affiliate_id=affiliate.id, product_id=product.id,
            tracking_code=code, campaign=campaign, commission_rate=commission,
        )
        db.session.add(link)
        db.session.flush()
        result = link.to_dict()
        result["full_url"] = link_agent.build_affiliate_url(code)
        created.append(result)
    db.session.commit()
    return jsonify({"created": len(created), "links": created}), 201


# ─── Media Generation ─────────────────────────────────────────────────────────

@app.route("/api/media", methods=["GET"])
@affiliate_or_admin
def list_media():
    product_id = request.args.get("product_id", type=int)
    affiliate_id = _scoped_affiliate_id()
    query = MediaContent.query
    if product_id:
        query = query.filter_by(product_id=product_id)
    if affiliate_id:
        query = query.filter_by(affiliate_id=affiliate_id)
    media = query.order_by(MediaContent.created_at.desc()).all()
    return jsonify([m.to_dict() for m in media])


@app.route("/api/media/generate", methods=["POST"])
@affiliate_or_admin
def generate_media():
    data = request.json
    product = db.session.get(Product, data.get("product_id"))
    if not product:
        return jsonify({"error": "Product not found"}), 404
    platform = data.get("platform", "instagram")
    content_type = data.get("content_type", "post")
    affiliate_id = current_user.affiliate_id if current_user.role == "affiliate" else data.get("affiliate_id")
    personalize = data.get("personalize", False)

    content = media_agent.generate(product.to_dict(), platform, content_type)

    score = 75.0
    if personalize and affiliate_id:
        affiliate = db.session.get(Affiliate, affiliate_id)
        if affiliate:
            content = persona_agent.personalize(content, affiliate.to_dict())
            score = persona_agent.score_content(content, affiliate.to_dict())

    media = MediaContent(
        product_id=product.id, affiliate_id=affiliate_id,
        content_type=content_type, platform=platform,
        title=content.get("title", ""), body=content.get("body", ""),
        hashtags=content.get("hashtags", ""), call_to_action=content.get("call_to_action", ""),
        personalized=bool(personalize and affiliate_id), performance_score=score,
    )
    db.session.add(media)
    db.session.commit()
    return jsonify({**media.to_dict(), "personalization_notes": content.get("personalization_notes")}), 201


@app.route("/api/media/generate-image", methods=["POST"])
@affiliate_or_admin
def generate_image():
    data = request.json or {}
    description = data.get("description", "").strip()
    if not description:
        return jsonify({"error": "description is required"}), 400

    size = data.get("size", "1024x1024")
    valid_sizes = ["1024x1024", "1536x1024", "1024x1536"]
    if size not in valid_sizes:
        size = "1024x1024"

    product_id = data.get("product_id")
    product = db.session.get(Product, product_id) if product_id else None
    affiliate_id = current_user.affiliate_id if current_user.role == "affiliate" else data.get("affiliate_id")

    try:
        result = media_agent.generate_image(
            description=description,
            size=size,
            product=product.to_dict() if product else None,
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 503
    except Exception as e:
        return jsonify({"error": f"Image generation failed: {str(e)}"}), 500

    media = MediaContent(
        product_id=product_id or 1,
        affiliate_id=affiliate_id,
        content_type="image",
        platform=data.get("platform", "general"),
        title=description[:300],
        image_url=result.get("image_url"),
        image_prompt=result.get("revised_prompt"),
    )
    db.session.add(media)
    db.session.commit()

    return jsonify({**media.to_dict(), **result}), 201


@app.route("/api/media/ab-test", methods=["POST"])
@affiliate_or_admin
def generate_ab_test():
    data = request.json
    product = db.session.get(Product, data.get("product_id"))
    if not product:
        return jsonify({"error": "Product not found"}), 404
    platform = data.get("platform", "instagram")
    affiliate_id = current_user.affiliate_id if current_user.role == "affiliate" else data.get("affiliate_id")

    variants = media_agent.generate_ab_test(product.to_dict(), platform)
    saved = []
    for v in variants:
        score = 75.0
        if affiliate_id:
            affiliate = db.session.get(Affiliate, affiliate_id)
            if affiliate:
                score = persona_agent.score_content(v, affiliate.to_dict())
        media = MediaContent(
            product_id=product.id, affiliate_id=affiliate_id,
            content_type="post", platform=platform,
            title=v.get("title", ""), body=v.get("body", ""),
            hashtags=v.get("hashtags", ""), call_to_action=v.get("call_to_action", ""),
            variant=v.get("variant", "A"), performance_score=score,
        )
        db.session.add(media)
        db.session.flush()
        saved.append(media.to_dict())
    db.session.commit()

    best = None
    if affiliate_id:
        affiliate = db.session.get(Affiliate, affiliate_id)
        if affiliate and variants:
            best = persona_agent.select_best_variant(variants, affiliate.to_dict()).get("variant")

    return jsonify({"variants": saved, "recommended_variant": best}), 201


@app.route("/api/media/<int:media_id>", methods=["PATCH"])
@affiliate_or_admin
def update_media(media_id):
    media = db.session.get(MediaContent, media_id)
    if not media:
        return jsonify({"error": "Not found"}), 404
    if current_user.role == "affiliate" and media.affiliate_id != current_user.affiliate_id:
        return jsonify({"error": "Forbidden"}), 403
    data = request.json or {}
    for field in ["title", "body", "hashtags", "call_to_action", "affiliate_id"]:
        if field in data:
            setattr(media, field, data[field])
    db.session.commit()
    return jsonify(media.to_dict())


@app.route("/api/media/<int:media_id>", methods=["DELETE"])
@affiliate_or_admin
def delete_media_item(media_id):
    media = db.session.get(MediaContent, media_id)
    if not media:
        return jsonify({"error": "Not found"}), 404
    if current_user.role == "affiliate" and media.affiliate_id != current_user.affiliate_id:
        return jsonify({"error": "Forbidden"}), 403
    db.session.delete(media)
    db.session.commit()
    return jsonify({"ok": True})


# ─── Tracking & Conversions ───────────────────────────────────────────────────

@app.route("/api/convert", methods=["POST"])
def record_conversion():
    data = request.json
    tracking_code = data.get("tracking_code")
    order_value = float(data.get("order_value", 0))
    if not tracking_code or order_value <= 0:
        return jsonify({"error": "tracking_code and order_value required"}), 400
    link = AffiliateLink.query.filter_by(tracking_code=tracking_code).first()
    if not link:
        return jsonify({"error": "Invalid tracking code"}), 404

    commission = order_value * link.commission_rate / 100
    conversion = Conversion(
        link_id=link.id,
        order_id=data.get("order_id", f"ORD-{int(datetime.utcnow().timestamp())}"),
        order_value=order_value, commission_amount=commission, status="approved",
    )
    db.session.add(conversion)
    link.conversions += 1
    link.revenue_generated += order_value
    link.affiliate.total_conversions += 1
    link.affiliate.total_earnings += commission
    db.session.commit()
    return jsonify({"conversion_id": conversion.id, "commission_earned": commission}), 201


@app.route("/api/simulate-traffic", methods=["POST"])
@admin_required
def simulate_traffic():
    import random
    links = AffiliateLink.query.filter_by(status="active").all()
    if not links:
        return jsonify({"error": "No active links"}), 400
    count = min(int(request.json.get("count", 10)), 50)
    generated = {"clicks": 0, "conversions": 0, "revenue": 0}

    for _ in range(count):
        link = random.choice(links)
        db.session.add(Click(link_id=link.id, ip_address=f"192.168.{random.randint(1,255)}.{random.randint(1,255)}"))
        link.clicks += 1
        link.affiliate.total_clicks += 1
        generated["clicks"] += 1
        if random.random() < 0.12:
            product = db.session.get(Product, link.product_id)
            if product:
                order_value = product.price * random.uniform(0.9, 2.5)
                commission = order_value * link.commission_rate / 100
                db.session.add(Conversion(
                    link_id=link.id,
                    order_id=f"SIM-{int(datetime.utcnow().timestamp())}-{random.randint(1000,9999)}",
                    order_value=order_value, commission_amount=commission, status="approved",
                ))
                link.conversions += 1
                link.revenue_generated += order_value
                link.affiliate.total_conversions += 1
                link.affiliate.total_earnings += commission
                generated["conversions"] += 1
                generated["revenue"] += order_value

    db.session.commit()
    generated["revenue"] = round(generated["revenue"], 2)
    return jsonify({"message": f"Simulated {count} events", "stats": generated})


# ─── Rewards ──────────────────────────────────────────────────────────────────

@app.route("/api/rewards", methods=["GET"])
@affiliate_or_admin
def list_rewards():
    affiliate_id = _scoped_affiliate_id()
    query = Reward.query
    if affiliate_id:
        query = query.filter_by(affiliate_id=affiliate_id)
    return jsonify([r.to_dict() for r in query.order_by(Reward.created_at.desc()).all()])


@app.route("/api/rewards/calculate", methods=["POST"])
@affiliate_or_admin
def calculate_rewards():
    data = request.json
    affiliate_id = current_user.affiliate_id if current_user.role == "affiliate" else data.get("affiliate_id")

    if affiliate_id:
        result = rewards_agent.calculate_period_rewards(affiliate_id)
        if result.get("total_reward", 0) > 0:
            reward = Reward(
                affiliate_id=affiliate_id, amount=result["total_reward"],
                reward_type="commission", status="pending",
                period_start=datetime.fromisoformat(result["period_start"]),
                period_end=datetime.fromisoformat(result["period_end"]),
                description=f"Commission for {result['conversion_count']} conversions",
            )
            db.session.add(reward)
            db.session.commit()
            result["reward_id"] = reward.id
        return jsonify(result)
    else:
        results = rewards_agent.process_pending_rewards()
        for r in results:
            db.session.add(Reward(
                affiliate_id=r["affiliate_id"], amount=r["amount"],
                reward_type="commission", status="pending",
                description=f"Batch commission for {r['conversions']} conversions",
            ))
        db.session.commit()
        return jsonify({"processed": len(results), "rewards": results})


@app.route("/api/rewards/<int:rid>/pay", methods=["POST"])
@admin_required
def pay_reward(rid):
    reward = db.session.get(Reward, rid)
    if not reward:
        return jsonify({"error": "Not found"}), 404
    if reward.status == "paid":
        return jsonify({"error": "Already paid"}), 400
    reward.status = "paid"
    reward.paid_at = datetime.utcnow()
    db.session.commit()
    return jsonify(reward.to_dict())


@app.route("/api/rewards/report/<int:aid>")
@affiliate_or_admin
def affiliate_report(aid):
    if current_user.role == "affiliate" and current_user.affiliate_id != aid:
        return jsonify({"error": "Access denied"}), 403
    return jsonify({
        "ai_report": rewards_agent.generate_ai_report(aid),
        "metrics": rewards_agent.get_performance_metrics(aid),
        "rewards": rewards_agent.calculate_period_rewards(aid),
    })


@app.route("/api/leaderboard")
@affiliate_or_admin
def leaderboard():
    return jsonify(rewards_agent.get_leaderboard(request.args.get("limit", 10, type=int)))


# ─── Analytics ────────────────────────────────────────────────────────────────

@app.route("/api/analytics/clicks-over-time")
@affiliate_or_admin
def clicks_over_time():
    days = request.args.get("days", 30, type=int)
    affiliate_id = _scoped_affiliate_id()
    data = []
    for i in range(days - 1, -1, -1):
        day = datetime.utcnow() - timedelta(days=i)
        day_start = day.replace(hour=0, minute=0, second=0)
        day_end = day.replace(hour=23, minute=59, second=59)
        cq = Click.query.join(AffiliateLink)
        if affiliate_id:
            cq = cq.filter(AffiliateLink.affiliate_id == affiliate_id)
        vq = Conversion.query.join(AffiliateLink)
        if affiliate_id:
            vq = vq.filter(AffiliateLink.affiliate_id == affiliate_id)
        data.append({
            "date": day.strftime("%Y-%m-%d"),
            "clicks": cq.filter(Click.timestamp.between(day_start, day_end)).count(),
            "conversions": vq.filter(Conversion.timestamp.between(day_start, day_end)).count(),
        })
    return jsonify(data)


@app.route("/api/analytics/revenue-by-product")
@affiliate_or_admin
def revenue_by_product():
    results = (
        db.session.query(Product.name, db.func.sum(AffiliateLink.revenue_generated).label("revenue"))
        .join(AffiliateLink, AffiliateLink.product_id == Product.id)
        .group_by(Product.id).order_by(db.text("revenue DESC")).all()
    )
    return jsonify([{"product": r[0], "revenue": round(float(r[1] or 0), 2)} for r in results])


@app.route("/health")
def health():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    debug = os.getenv("FLASK_ENV") != "production"
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=debug)
