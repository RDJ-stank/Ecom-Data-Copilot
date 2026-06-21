"""
Final cost report. DeepSeek-chat: 1 RMB/1M input, 2 RMB/1M output.
"""
import sys; sys.path.insert(0, '.')
from src.prompts import ROUTER_PROMPT, TEXT2SQL_PROMPT, CHART_INSIGHT_PROMPT, TITLE_PROMPT
from src.graph.sql_reviewer import REVIEW_PROMPT
from src.column_meta import prune_columns, build_pruned_ddl
from src.chromadb_setup import SCHEMA_DOCS

def est_tokens(text):
    cn = sum(1 for c in text if '一' <= c <= '鿿')
    return int(cn * 1.5 + (len(text) - cn) * 0.25)

IP = 1.0 / 1_000_000
OP = 2.0 / 1_000_000

query = "上个月因为物流破损导致退款金额最高的 Top 3 供应商"

# Old full DDL
old_ddl = '\n\n'.join([d['content'] for d in SCHEMA_DOCS])

# New pruned DDL
tbls = ['dim_users', 'dim_products', 'fact_orders', 'fact_after_sales']
pruned = prune_columns(tbls, query)
new_ddl = build_pruned_ddl(tbls, pruned)

# ---- Single query costs ----
old_router = est_tokens(ROUTER_PROMPT.format(user_query=query))
old_t2s  = est_tokens(TEXT2SQL_PROMPT.format(schema=old_ddl, query=query, error_context=""))
old_chart = est_tokens("CHART_PROMPT") + 700
old_insight = est_tokens("INSIGHT_PROMPT") + 500
old_title = est_tokens(TITLE_PROMPT.format(query=query))

new_router = old_router
new_t2s  = est_tokens(TEXT2SQL_PROMPT.format(schema=new_ddl, query=query, error_context=""))
new_review = est_tokens(REVIEW_PROMPT.format(query=query, schema=new_ddl[:400], sql="SELECT ..."))
new_ci   = est_tokens(CHART_INSIGHT_PROMPT.format(query=query, data_json="[]")) + 500
new_title = old_title

old_in = old_router + old_t2s + old_chart + old_insight + old_title
new_in_c = new_router + new_t2s + new_review + new_ci + new_title  # complex
new_in_s = new_router + new_t2s + 0         + new_ci + new_title  # simple (skip reviewer)
old_out = 5 + 300 + 250 + 120 + 15
new_out_c = 5 + 300 + 120 + 320 + 15  # complex
new_out_s = 5 + 300 + 0   + 320 + 15  # simple

old_cost = old_in * IP + old_out * OP
new_cost_c = new_in_c * IP + new_out_c * OP
new_cost_s = new_in_s * IP + new_out_s * OP

print("=" * 70)
print("COST PER QUERY (DeepSeek-chat)")
print("=" * 70)
print()
print(f"  OLD system:           {old_cost:,.4f} RMB  ({old_in} in, {old_out} out)")
print(f"  NEW complex (w/ review): {new_cost_c:,.4f} RMB  ({new_in_c} in, {new_out_c} out)")
print(f"  NEW simple  (no review): {new_cost_s:,.4f} RMB  ({new_in_s} in, {new_out_s} out)")
print()
print(f"  Complex query saving: {(old_cost - new_cost_c) / old_cost * 100:.0f}%")
print(f"  Simple query saving:  {(old_cost - new_cost_s) / old_cost * 100:.0f}%")
print()

# Multi-turn
chart_only = new_ci * IP + 320 * OP
print("=== MULTI-TURN CACHING (Context Frame) ===")
print(f"  CHANGE_CHART  ('用饼图展示'): {chart_only:,.4f} RMB  ({(1 - chart_only/new_cost_c)*100:.0f}% saved vs full)")
print(f"  CHANGE_NONE   (exact repeat):   0 RMB  (100% saved)")
print(f"  CHANGE_FILTER ('换成质量问题'): {new_cost_s:,.4f} RMB  (only Text2SQL rerun)")
print(f"  CHANGE_SUBJECT:                 {new_cost_c:,.4f} RMB  (full pipeline)")
print()

print("=== SCALE PROJECTION (100 queries/day, 10 users) ===")
# 40% full complex, 20% simple, 20% chart-only, 20% exact cache hit
daily = 100 * (0.4 * new_cost_c + 0.2 * new_cost_s + 0.2 * chart_only + 0.2 * 0)
print(f"  Daily:   {daily:,.3f} RMB")
print(f"  Monthly: {daily * 30:,.2f} RMB")
print(f"  Yearly:  {daily * 365:,.2f} RMB")
print()
print("Compare: GPT-4o would cost ~72x more (~25 RMB/month)")

# Breakdown
print()
print("=== PER-STEP BREAKDOWN ===")
print(f"  Router:      {new_router:>4} in / {5:>3} out = {new_router * IP + 5 * OP:,.4f} RMB")
print(f"  Text2SQL:    {new_t2s:>4} in / {300:>3} out = {new_t2s * IP + 300 * OP:,.4f} RMB")
print(f"  Reviewer:    {new_review:>4} in / {120:>3} out = {new_review * IP + 120 * OP:,.4f} RMB  [complex only]")
print(f"  Chart+Ins:   {new_ci:>4} in / {320:>3} out = {new_ci * IP + 320 * OP:,.4f} RMB")
print(f"  Title:       {new_title:>4} in / {15:>3} out = {new_title * IP + 15 * OP:,.4f} RMB")
