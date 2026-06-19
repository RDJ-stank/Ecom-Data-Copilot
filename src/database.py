from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker
from src.config import DB_PATH

engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()


class DimUser(Base):
    __tablename__ = "dim_users"

    user_id = Column(Integer, primary_key=True, autoincrement=True)
    register_time = Column(DateTime, nullable=False)
    user_level = Column(String(32), nullable=False)
    channel = Column(String(32), nullable=False)


class DimProduct(Base):
    __tablename__ = "dim_products"

    product_id = Column(Integer, primary_key=True, autoincrement=True)
    category = Column(String(64), nullable=False)
    price = Column(Float, nullable=False)
    cost = Column(Float, nullable=False)
    supplier_name = Column(String(128), nullable=False)


class FactOrder(Base):
    __tablename__ = "fact_orders"

    order_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("dim_users.user_id"), nullable=False)
    product_id = Column(Integer, ForeignKey("dim_products.product_id"), nullable=False)
    actual_amount = Column(Float, nullable=False)
    order_status = Column(String(32), nullable=False)
    pay_time = Column(DateTime, nullable=False)


class FactAfterSales(Base):
    __tablename__ = "fact_after_sales"

    after_sales_id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("fact_orders.order_id"), nullable=False)
    damage_type = Column(String(32), nullable=False)
    handle_result = Column(String(32), nullable=False)
    created_at = Column(DateTime, nullable=False)


def init_db():
    Base.metadata.create_all(engine)


def get_session():
    return SessionLocal()
