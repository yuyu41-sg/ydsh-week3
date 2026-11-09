# -*- coding: utf-8 -*-
"""
子任务4：NL2SQL 构建（自然语言 → 生成 SQL → 执行 → 返回结果）
链路：
  1) data/schema.json 注入系统提示词（含表注释、列清单、few-shot 示例）
  2) 智谱 GLM 生成只读 SELECT SQL（代码块提取，非法语句拦截）
  3) 经 beeline 在 Hive 实际执行，返回结果
前置：.env 已配置 ZHIPU_API_KEY；data/schema.json 已由 schema_extract.py 生成
用法：python nl2sql.py "广东省上月销售额是多少？"
"""
import json
import os
import re
import subprocess
import sys

from dotenv import load_dotenv
from openai import OpenAI

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE, ".env"))

api_key = os.environ.get("ZHIPU_API_KEY")
if not api_key or "xxxx" in api_key:
    raise SystemExit("未配置 API Key：请复制 .env.example 为 .env 并填入真实 ZHIPU_API_KEY")

# ---------- 1. 载入 Schema ----------
with open(os.path.join(BASE, "data", "schema.json"), encoding="utf-8") as f:
    schema = json.load(f)
schema_lines = []
for t, info in schema.items():
    schema_lines.append(f"{t} -- {info['comment']}")
    schema_lines.append("  " + ", ".join(info["columns"]))
    if info["partitions"]:
        schema_lines.append(f"  分区字段: {', '.join(info['partitions'])}")
schema_desc = "\n".join(schema_lines)

# ---------- 2. 系统提示词（含 few-shot 与规范约束） ----------
SYSTEM_PROMPT = f"""你是 Hive SQL 专家。根据用户的自然语言问题，生成一条可在 Hive 4.0 上执行的查询 SQL。

可用表（ Schema 如下）：
{schema_desc}

硬性规范：
1. 只生成 SELECT 语句，禁止 INSERT / UPDATE / DELETE / DROP / CREATE。
2. 只允许使用上面列出的表和列，禁止编造表名或列名。
3. 表名必须带库名前缀（如 ydsh_dwd.dwd_order）。
4. 时间字段 order_timestamp/dt 为 string 类型，格式 yyyy-MM-dd 或 yyyy-MM-dd HH:mm:ss，日期比较用 SUBSTR() 或字符串比较。
5. "销售额/GMV"默认口径为已完成订单的 pay_amount 之和（order_status = '已完成'）；涉及品类销量时用 dwd_order_item 关联 dim_product。
6. 省份/城市等维度在 dim_store / dim_user 表中，注意关联键。
7. 结果限制在 50 行以内（必要时加 LIMIT）。
8. GROUP BY / HAVING 中必须重复完整表达式，禁止使用 SELECT 别名（Hive 不支持别名分组）；ORDER BY 中可用别名但优先写表达式。

示例（few-shot）：
问："广东省的销售额是多少"
答：SELECT ROUND(SUM(o.pay_amount),2) AS sales FROM ydsh_dwd.dwd_order o JOIN ydsh_dwd.dim_store s ON o.store_id=s.store_id WHERE s.province='广东省' AND o.order_status='已完成';
问："销量最高的前5个品类"
答：SELECT p.category, SUM(i.quantity) AS total_qty FROM ydsh_dwd.dwd_order_item i JOIN ydsh_dwd.dim_product p ON i.product_id=p.product_id JOIN ydsh_dwd.dwd_order o ON i.order_id=o.order_id AND o.order_status='已完成' GROUP BY p.category ORDER BY total_qty DESC LIMIT 5;

只输出 SQL 本身，不要任何解释。"""

client = OpenAI(api_key=api_key,
                base_url=os.environ.get("ZHIPU_BASE_URL", "https://open.bigmodel.cn/api/paas/v4/"))

def generate_sql(question: str) -> str:
    resp = client.chat.completions.create(
        model=os.environ.get("ZHIPU_MODEL", "glm-4-flash"),
        messages=[{"role": "system", "content": SYSTEM_PROMPT},
                  {"role": "user", "content": question}],
        temperature=0,
    )
    text = resp.choices[0].message.content.strip()
    # 提取 ```sql ... ``` 或裸 SQL
    m = re.search(r"```(?:sql)?\s*(.+?)\s*```", text, re.S)
    sql = m.group(1).strip() if m else text.strip().rstrip(";") + ";"
    return sql

def validate_sql(sql: str):
    """只读校验：拦截任何写操作"""
    banned = re.findall(r"\b(insert|update|delete|drop|create|alter|truncate)\b", sql, re.I)
    if banned:
        raise ValueError(f"模型生成了被禁止的语句: {banned}，已拦截")
    if not sql.lower().lstrip().startswith("select"):
        raise ValueError("非 SELECT 语句，已拦截")

def run_sql(sql: str):
    """在 Hive 上执行并返回 (结果行, 错误信息)"""
    sql = sql.rstrip(";")
    cmd = ["docker", "exec", "ydsh-hiveserver2", "bash", "-c",
           f"beeline -u jdbc:hive2://localhost:10000 --outputformat=tsv2 --silent=true -e \"{sql}\" 2>&1"]
    env = os.environ.copy(); env["MSYS_NO_PATHCONV"] = "1"
    out = subprocess.run(cmd, capture_output=True, text=True, env=env).stdout
    rows, err = [], None
    for l in out.splitlines():
        ls = l.strip()
        if not ls or ls.startswith(("INFO", "WARN", "[WARN]", "SLF4J", "Connecting", "Connected",
                                    "Driver", "Transaction", "0:", "Beeline version",
                                    "Closing", "No such file")):
            continue
        if "Error:" in ls or "FAILED:" in ls:
            err = ls
        elif not ls.startswith("---"):
            rows.append(l)
    return rows, err

def repair_sql(sql: str, error: str) -> str:
    """把 Hive 报错回传给大模型，让它自行修正 SQL（自修复重试）"""
    resp = client.chat.completions.create(
        model=os.environ.get("ZHIPU_MODEL", "glm-4-flash"),
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"你生成的 SQL 在 Hive 上执行报错，请修正后只输出修正后的 SQL，不要解释。\n\n原SQL：\n{sql}\n\nHive报错：\n{error}"},
        ],
        temperature=0,
    )
    text = resp.choices[0].message.content.strip()
    m = re.search(r"```(?:sql)?\s*(.+?)\s*```", text, re.S)
    return (m.group(1).strip() if m else text).rstrip(";") + ";"

if __name__ == "__main__":
    question = sys.argv[1] if len(sys.argv) > 1 else "销量最高的前5个品类"
    print(f"【问题】{question}")
    sql = generate_sql(question)
    print(f"【生成 SQL】\n{sql}")
    validate_sql(sql)
    rows, err = run_sql(sql)
    retries = 0
    while err and retries < 2:
        retries += 1
        print(f"【执行报错，第{retries}次自修复】{err}")
        sql = repair_sql(sql, err)
        validate_sql(sql)
        print(f"【修正后 SQL】\n{sql}")
        rows, err = run_sql(sql)
    if err:
        raise SystemExit(f"重试 {retries} 次后仍执行失败：{err}")
    print(f"【执行结果】(共{len(rows)}行)" + (f"，经{retries}次自修复" if retries else ""))
    for r in rows[:12]:
        print(" ", r)
