import random
from datetime import datetime, timedelta
from faker import Faker
from sqlalchemy.orm import Session
from src.database import init_db, get_session, DimUser, DimProduct, FactOrder, FactAfterSales

fake = Faker("zh_CN")

CATEGORIES = ["服装鞋包", "美妆个护", "数码家电", "食品饮料", "母婴用品", "家居日用", "运动户外"]
USER_LEVELS = ["普通会员", "银卡会员", "金卡会员", "钻石会员"]
CHANNELS = ["微信小程序", "APP", "网页端", "线下扫码"]
DAMAGE_TYPES = ["物流破损", "质量问题", "商品错发", "漏发商品"]
HANDLE_RESULTS = ["退款", "换货", "退货退款"]
ORDER_STATUSES = ["已完成", "已取消", "已退款"]

SUPPLIERS = [
    "深圳华强电子科技有限公司", "广州白云服装批发有限公司", "杭州西湖美妆贸易公司",
    "北京中关村数码产品有限公司", "上海浦东母婴用品供应商", "成都天府食品加工厂",
    "东莞虎门运动器材有限公司", "义乌小商品批发城", "泉州晋江鞋业有限公司",
    "苏州工业园区家电制造厂", "武汉光谷电子商贸公司", "南京建邺家居用品有限公司",
]

CATEGORY_PRICE_RANGE = {
    "服装鞋包": (50, 500, 0.30, 0.50),
    "美妆个护": (30, 300, 0.20, 0.40),
    "数码家电": (200, 5000, 0.60, 0.80),
    "食品饮料": (5, 100, 0.30, 0.50),
    "母婴用品": (50, 800, 0.30, 0.50),
    "家居日用": (20, 500, 0.30, 0.50),
    "运动户外": (100, 2000, 0.40, 0.60),
}

START_DATE = datetime(2025, 1, 1)
END_DATE = datetime(2026, 6, 19, 23, 59, 59)


def _random_date(start, end):
    delta = (end - start).days
    if delta <= 0:
        return start
    return start + timedelta(days=random.randint(0, delta))


def _random_datetime(start, end):
    delta = (end - start)
    total_seconds = int(delta.total_seconds())
    if total_seconds <= 0:
        return start
    return start + timedelta(seconds=random.randint(0, total_seconds))


def generate_users(session: Session, count=200):
    users = []
    for _ in range(count):
        u = DimUser(
            register_time=_random_datetime(START_DATE, END_DATE),
            user_level=random.choices(USER_LEVELS, weights=[0.45, 0.30, 0.18, 0.07])[0],
            channel=random.choices(CHANNELS, weights=[0.35, 0.30, 0.25, 0.10])[0],
        )
        session.add(u)
        users.append(u)
    session.flush()
    return users


def generate_products(session: Session, count=60):
    products = []
    for _ in range(count):
        cat = random.choice(CATEGORIES)
        p_min, p_max, cost_ratio_min, cost_ratio_max = CATEGORY_PRICE_RANGE[cat]
        price = round(random.uniform(p_min, p_max), 2)
        cost_ratio = random.uniform(cost_ratio_min, cost_ratio_max)
        cost = round(price * cost_ratio, 2)
        p = DimProduct(
            category=cat,
            price=price,
            cost=cost,
            supplier_name=random.choice(SUPPLIERS),
        )
        session.add(p)
        products.append(p)
    session.flush()
    return products


def generate_orders(session: Session, users, products, count=3000):
    orders = []
    for _ in range(count):
        user = random.choice(users)
        product = random.choice(products)
        status = random.choices(ORDER_STATUSES, weights=[0.75, 0.15, 0.10])[0]
        o = FactOrder(
            user_id=user.user_id,
            product_id=product.product_id,
            actual_amount=round(product.price * random.uniform(0.85, 1.0), 2),
            order_status=status,
            pay_time=_random_datetime(START_DATE, END_DATE),
        )
        session.add(o)
        orders.append(o)
    session.flush()
    return orders


def generate_after_sales(session: Session, orders, count=400):
    afters = []
    # bias: pick completed/refunded orders more often
    eligible = [o for o in orders if o.order_status in ("已完成", "已退款")]
    for _ in range(count):
        order = random.choice(eligible)
        dt = random.choices(DAMAGE_TYPES, weights=[0.30, 0.35, 0.20, 0.15])[0]
        hr = random.choices(HANDLE_RESULTS, weights=[0.55, 0.30, 0.15])[0]
        a = FactAfterSales(
            order_id=order.order_id,
            damage_type=dt,
            handle_result=hr,
            created_at=_random_datetime(order.pay_time, END_DATE),
        )
        session.add(a)
        afters.append(a)
    session.flush()
    return afters


def seed_all():
    print("Initializing database and seeding mock data...")
    init_db()
    session = get_session()
    try:
        existing = session.query(DimUser).count()
        if existing > 0:
            print(f"Database already has {existing} users, skipping seed.")
            return
        print("Generating users...")
        users = generate_users(session, 200)
        print("Generating products...")
        products = generate_products(session, 60)
        print("Generating orders...")
        orders = generate_orders(session, users, products, 3000)
        print("Generating after-sales records...")
        generate_after_sales(session, orders, 400)
        session.commit()
        print("Mock data seeded successfully.")
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


if __name__ == "__main__":
    seed_all()
