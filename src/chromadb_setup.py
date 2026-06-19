import os
import chromadb
from chromadb.utils import embedding_functions
from src.config import CHROMA_PATH

COLLECTION_NAME = "ecom_schema"

SCHEMA_DOCS = [
    {
        "table": "dim_users",
        "content": """Table: dim_users (用户维度表 - 存储用户基本信息)
Columns:
- user_id (INTEGER, PRIMARY KEY): 用户唯一标识ID
- register_time (DATETIME): 用户注册时间，格式YYYY-MM-DD HH:MI:SS
- user_level (VARCHAR): 用户等级，可选值：普通会员、银卡会员、金卡会员、钻石会员
- channel (VARCHAR): 用户来源注册渠道，可选值：微信小程序、APP、网页端、线下扫码""",
    },
    {
        "table": "dim_products",
        "content": """Table: dim_products (商品维度表 - 存储商品基础信息、价格及供应商)
Columns:
- product_id (INTEGER, PRIMARY KEY): 商品唯一标识ID
- category (VARCHAR): 商品品类，可选值：服装鞋包、美妆个护、数码家电、食品饮料、母婴用品、家居日用、运动户外
- price (FLOAT): 商品销售价格（元）
- cost (FLOAT): 商品进货成本（元）
- supplier_name (VARCHAR): 供应商公司名称""",
    },
    {
        "table": "fact_orders",
        "content": """Table: fact_orders (订单事实表 - 存储每笔订单的交易记录)
Columns:
- order_id (INTEGER, PRIMARY KEY): 订单唯一标识ID
- user_id (INTEGER, FOREIGN KEY -> dim_users.user_id): 下单用户ID，关联用户表
- product_id (INTEGER, FOREIGN KEY -> dim_products.product_id): 购买商品ID，关联商品表
- actual_amount (FLOAT): 实际支付金额（元）
- order_status (VARCHAR): 订单状态，可选值：已完成、已取消、已退款
- pay_time (DATETIME): 支付时间，格式YYYY-MM-DD HH:MI:SS""",
    },
    {
        "table": "fact_after_sales",
        "content": """Table: fact_after_sales (售后事实表 - 存储售后服务与投诉记录)
Columns:
- after_sales_id (INTEGER, PRIMARY KEY): 售后记录唯一标识ID
- order_id (INTEGER, FOREIGN KEY -> fact_orders.order_id): 关联的订单ID
- damage_type (VARCHAR): 售后问题类型，可选值：物流破损、质量问题、商品错发、漏发商品
- handle_result (VARCHAR): 处理结果，可选值：退款、换货、退货退款
- created_at (DATETIME): 售后申请创建时间，格式YYYY-MM-DD HH:MI:SS""",
    },
]


def get_chroma_collection():
    os.makedirs(CHROMA_PATH, exist_ok=True)
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    embedding_fn = embedding_functions.DefaultEmbeddingFunction()
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_fn,
    )
    return collection


def init_chroma_schema():
    collection = get_chroma_collection()
    if collection.count() > 0:
        return
    docs = [d["content"] for d in SCHEMA_DOCS]
    ids = [d["table"] for d in SCHEMA_DOCS]
    metadatas = [{"table": d["table"]} for d in SCHEMA_DOCS]
    collection.add(documents=docs, ids=ids, metadatas=metadatas)
    print(f"ChromaDB indexed {len(docs)} table schemas.")


def query_schema(user_query: str, n_results=3) -> str:
    collection = get_chroma_collection()
    results = collection.query(query_texts=[user_query], n_results=n_results)
    docs = results.get("documents", [[]])[0]
    return "\n\n".join(docs) if docs else ""
