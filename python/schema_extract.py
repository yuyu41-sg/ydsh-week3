# -*- coding: utf-8 -*-
"""
子任务4（前置）：自动抽取 Hive 表 Schema，生成供大模型理解的元信息
实现：调用容器内 beeline 执行 `desc <table>`，解析列名/类型/分区，输出 JSON 与提示词用文本
用法：python schema_extract.py
"""
import json
import os
import subprocess

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "data", "schema.json")

TABLES = {
    "ydsh_dwd.dwd_order":       "订单事实表（已完成订单去重，按 order_month 分区）",
    "ydsh_dwd.dim_product":     "商品维度表",
    "ydsh_dwd.dim_store":       "门店维度表",
    "ydsh_dwd.dim_user":        "用户维度表",
    "ydsh_dwd.dwd_order_item":  "订单明细表（一行=一个订单中的一个商品）",
    "ydsh_dws.dws_order_day":   "DWS 日汇总表（全渠道）",
    "ydsh_ads.ads_sales_daily": "ADS 销售日报（含环比）",
    "ydsh_ads.ads_kpi_result":  "ADS 全期核心 KPI 单行表",
    "ydsh_ads.ads_category_top10": "ADS 品类销售 Top10",
    "ydsh_ads.ads_user_value":  "ADS 用户价值分层",
}

MSYS_ENV = os.environ.copy()
MSYS_ENV["MSYS_NO_PATHCONV"] = "1"

def desc_table(table):
    """执行 beeline desc，返回 [(列名, 类型), ...] 与分区列"""
    cmd = ["docker", "exec", "ydsh-hiveserver2", "bash", "-c",
           f"beeline -u jdbc:hive2://localhost:10000 --outputformat=tsv2 -e 'desc {table}' 2>/dev/null"]
    out = subprocess.run(cmd, capture_output=True, text=True, env=MSYS_ENV).stdout
    cols, parts, in_part = [], [], False
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("# Partition Information"):
            in_part = True
            continue
        if line.startswith("#") or not line:
            continue
        cells = [c.strip() for c in line.split("\t") if c.strip()]
        if not cells or cells[0] == "col_name" or cells[0] == "NULL":
            continue
        if not in_part and len(cells) >= 2:
            cols.append((cells[0], cells[1]))
        elif in_part and len(cells) >= 1:
            parts.append(cells[0])
    return cols, parts

def build_schema_desc():
    schema = {}
    for t, note in TABLES.items():
        cols, parts = desc_table(t)
        schema[t] = {"comment": note,
                     "columns": [f"{c} {ty}" for c, ty in cols],
                     "partitions": parts}
        print(f"{t}: {len(cols)} 列, 分区 {parts}")
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(schema, f, ensure_ascii=False, indent=2)
    print("\n已写出", OUT)
    return schema

def schema_as_prompt(schema):
    """转成注入 Prompt 的紧凑文本"""
    lines = []
    for t, info in schema.items():
        lines.append(f"{t} -- {info['comment']}")
        lines.append("  " + ", ".join(info["columns"]))
        if info["partitions"]:
            lines.append(f"  分区字段: {', '.join(info['partitions'])}")
    return "\n".join(lines)

if __name__ == "__main__":
    schema = build_schema_desc()
    with open(os.path.join(BASE, "data", "schema_prompt.txt"), "w", encoding="utf-8") as f:
        f.write(schema_as_prompt(schema))
    print("提示词文本已写出 data/schema_prompt.txt")
