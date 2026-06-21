"""Column-level metadata for DDL pruning.
Kinds: pk, fk:<target>, measure (money/count), dimension (category/status/time)
"""
COLUMN_META = {
    "dim_users": {
        "user_id":       "pk",
        "register_time": "dimension",
        "user_level":    "dimension",
        "channel":       "dimension",
    },
    "dim_products": {
        "product_id":    "pk",
        "category":      "dimension",
        "price":         "measure",
        "cost":          "measure",
        "supplier_name": "dimension",
    },
    "fact_orders": {
        "order_id":      "pk",
        "user_id":       "fk:dim_users.user_id",
        "product_id":    "fk:dim_products.product_id",
        "actual_amount": "measure",
        "order_status":  "dimension",
        "pay_time":      "dimension",
    },
    "fact_after_sales": {
        "after_sales_id": "pk",
        "order_id":       "fk:fact_orders.order_id",
        "damage_type":    "dimension",
        "handle_result":  "dimension",
        "created_at":     "dimension",
    },
}

TABLE_DESCRIPTIONS = {
    "dim_users": "用户维度表，存储用户基本信息、等级和渠道",
    "dim_products": "商品维度表，存储商品品类、价格、成本和供应商",
    "fact_orders": "订单事实表，存储每笔订单的交易金额、状态和支付时间",
    "fact_after_sales": "售后事实表，存储售后问题类型和处理结果",
}

COLUMN_DESCRIPTIONS = {
    "dim_users.user_id":       "用户唯一标识",
    "dim_users.register_time": "用户注册时间",
    "dim_users.user_level":    "用户等级：普通会员/银卡会员/金卡会员/钻石会员",
    "dim_users.channel":       "注册渠道：微信小程序/APP/网页端/线下扫码",
    "dim_products.product_id":    "商品唯一标识",
    "dim_products.category":      "商品品类：服装鞋包/美妆个护/数码家电/食品饮料/母婴用品/家居日用/运动户外",
    "dim_products.price":         "商品销售价格（元）",
    "dim_products.cost":          "商品进货成本（元）",
    "dim_products.supplier_name": "供应商公司名称",
    "fact_orders.order_id":      "订单唯一标识",
    "fact_orders.user_id":       "下单用户ID，关联dim_users",
    "fact_orders.product_id":    "购买商品ID，关联dim_products",
    "fact_orders.actual_amount": "实际支付金额（元）",
    "fact_orders.order_status":  "订单状态：已完成/已取消/已退款",
    "fact_orders.pay_time":      "支付时间",
    "fact_after_sales.after_sales_id": "售后记录唯一标识",
    "fact_after_sales.order_id":       "关联订单ID，关联fact_orders",
    "fact_after_sales.damage_type":    "问题类型：物流破损/质量问题/商品错发/漏发商品",
    "fact_after_sales.handle_result":  "处理结果：退款/换货/退货退款",
    "fact_after_sales.created_at":     "售后创建时间",
}


def prune_columns(tables: list[str], user_query: str) -> dict[str, list[str]]:
    """Return only relevant columns per table. PK and FK are always preserved."""
    # For now: keyword-based relevance. Embedding-based would be a later optimization.
    # The key invariant: PK + FK are NEVER pruned.
    q_lower = user_query.lower()
    result = {}
    for tbl in tables:
        meta = COLUMN_META.get(tbl, {})
        keep = []
        for col, kind in meta.items():
            if kind == "pk" or kind.startswith("fk:"):
                keep.append(col)
                continue
            # Check if column or its description matches query keywords
            desc = COLUMN_DESCRIPTIONS.get(f"{tbl}.{col}", col)
            if _col_matches(col, desc, q_lower):
                keep.append(col)
        # If pruning removed everything non-key, keep all columns as fallback
        if len(keep) <= sum(1 for v in meta.values() if v == "pk" or v.startswith("fk:")):
            keep = list(meta.keys())
        result[tbl] = keep
    return result


def _col_matches(col: str, desc: str, q_lower: str) -> bool:
    keywords = q_lower.replace("？", " ").replace("？", " ").replace("，", " ").replace(",", " ").split()
    for kw in keywords:
        if len(kw) <= 1:
            continue
        if kw in col.lower() or kw in desc.lower():
            return True
    return False


def build_pruned_ddl(tables: list[str], pruned: dict[str, list[str]]) -> str:
    """Build a compact DDL string using only the pruned columns."""
    lines = []
    for tbl in tables:
        meta = COLUMN_META.get(tbl, {})
        cols = pruned.get(tbl, list(meta.keys()))
        lines.append(f"Table: {tbl}")
        lines.append(f"  ({TABLE_DESCRIPTIONS.get(tbl, '')})")
        for col in cols:
            kind = meta.get(col, "")
            desc = COLUMN_DESCRIPTIONS.get(f"{tbl}.{col}", "")
            fk_note = ""
            if kind.startswith("fk:"):
                fk_note = f"  → JOIN KEY to {kind[3:]}"
            lines.append(f"  - {col}: {desc}{fk_note}")
        lines.append("")
    return "\n".join(lines)
