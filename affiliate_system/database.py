from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def init_db(app):
    db.init_app(app)
    with app.app_context():
        db.create_all()
        _seed_demo_data()


def _seed_demo_data():
    from models import Product, Affiliate, User
    if Product.query.count() > 0:
        return

    products = [
        Product(name="ZaloPay Premium Wallet", description="Ví điện tử cao cấp với nhiều tính năng độc quyền: cashback 5%, bảo hiểm giao dịch, ưu tiên hỗ trợ 24/7.", price=199000, category="fintech", commission_rate=15.0, image_url="https://picsum.photos/seed/zalopay1/400/300"),
        Product(name="ZaloPay Business Account", description="Tài khoản doanh nghiệp với công cụ quản lý tài chính chuyên nghiệp, tích hợp kế toán và báo cáo thuế.", price=499000, category="business", commission_rate=20.0, image_url="https://picsum.photos/seed/zalopay2/400/300"),
        Product(name="ZaloPay Investment Fund", description="Quỹ đầu tư linh hoạt với lãi suất hấp dẫn, quản lý bởi các chuyên gia tài chính hàng đầu.", price=1000000, category="investment", commission_rate=12.0, image_url="https://picsum.photos/seed/zalopay3/400/300"),
        Product(name="ZaloPay Insurance Bundle", description="Gói bảo hiểm toàn diện: sức khỏe, tai nạn, và tài sản. Đăng ký online trong 5 phút.", price=350000, category="insurance", commission_rate=18.0, image_url="https://picsum.photos/seed/zalopay4/400/300"),
        Product(name="ZaloPay Merchant Plus", description="Giải pháp thanh toán cho merchant: QR code, cổng thanh toán, tích hợp POS và quản lý đơn hàng.", price=299000, category="merchant", commission_rate=10.0, image_url="https://picsum.photos/seed/zalopay5/400/300"),
    ]

    affiliates = [
        Affiliate(name="Nguyen Van An", email="an.nguyen@gmail.com", username="annguyen_fin", demographics="millennial", interests="fintech,investment,tech", platform="facebook", total_clicks=1250, total_conversions=89, total_earnings=2340000),
        Affiliate(name="Tran Thi Bich", email="bich.tran@gmail.com", username="bichtran_style", demographics="gen_z", interests="shopping,lifestyle,beauty", platform="tiktok", total_clicks=3400, total_conversions=210, total_earnings=5670000),
        Affiliate(name="Le Minh Duc", email="duc.le@gmail.com", username="duchminh_biz", demographics="professional", interests="business,finance,startup", platform="linkedin", total_clicks=890, total_conversions=67, total_earnings=1890000),
        Affiliate(name="Pham Thi Hoa", email="hoa.pham@gmail.com", username="hoablooms", demographics="millennial", interests="travel,food,lifestyle", platform="instagram", total_clicks=2100, total_conversions=145, total_earnings=3450000),
    ]

    for p in products:
        db.session.add(p)
    for a in affiliates:
        db.session.add(a)
    db.session.flush()  # get affiliate IDs before creating users

    admin = User(username="admin", email="admin@zalopay.vn", role="admin")
    admin.set_password("admin123")
    db.session.add(admin)

    affiliate_accounts = [
        ("annguyen_fin", "an.nguyen@gmail.com", affiliates[0]),
        ("bichtran_style", "bich.tran@gmail.com", affiliates[1]),
        ("duchminh_biz", "duc.le@gmail.com", affiliates[2]),
        ("hoablooms", "hoa.pham@gmail.com", affiliates[3]),
    ]
    for username, email, aff in affiliate_accounts:
        u = User(username=username, email=email, role="affiliate", affiliate_id=aff.id)
        u.set_password("affiliate123")
        db.session.add(u)

    db.session.commit()
