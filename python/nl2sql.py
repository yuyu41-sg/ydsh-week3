# -*- coding: utf-8 -*-
"""
子任务4：NL2SQL 构建（自然语言 → 生成 SQL → 执行 → 返回结果）
链路：
  1) data/schema.json 注入系统提示词（含表注释、列清单、few-shot 示例）
  2) DeepSeek 生成只读 SELECT SQL（代码块提取，非法语句拦截）
  3) 经 beeline 在 Hive 实际执行，返回结果
前置：.env 已配置 DEEPSEEK_API_KEY；data/schema.json 已由 schema_extract.py 生成
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

api_key = os.environ.get("DEEPSEEK_API_KEY")
if not api_key or api_key.startswith("sk-xxx"):
    raise SystemExit("未配置 API Key：请复制 .env.example 为 .env 并填入真实 DEEPSEEK_API_KEY")

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

示例（few-shot）：
问："广东省的销售额是多少"
答：SELECT ROUND(SUM(o.pay_amount),2) AS sales FROM ydsh_dwd.dwd_order o JOIN ydsh_dwd.dim_store s ON o.store_id=s.store_id WHERE s.province='广东省' AND o.order_status='已完成';
问："销量最高的前5个品类"
答：SELECT p.category, SUM(i.quantity) AS total_qty FROM ydsh_dwd.dwd_order_item i JOIN ydsh_dwd.dim_product p ON i.product_id=p.product_id JOIN ydsh_dwd.dwd_order o ON i.order_id=o.order_id AND o.order_status='已完成' GROUP BY p.category ORDER BY total_qty DESC LIMIT 5;

只输出 SQL 本身，不要任何解释。"""

client = OpenAI(api_key=api_key,
                base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"))

def generate_sql(question: str) -> str:
    resp = client.chat.completions.create(
        model=os.environ.get("DEEPSEEK_MODEL", "deepseek-chat"),
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
    """在 Hive 上执行并返回结果文本"""
    sql = sql.rstrip(";")
    cmd = ["docker", "exec", "ydsh-hiveserver2", "bash", "-c",
           f"beeline -u jdbc:hive2://localhost:10000 --outputformat=tsv2 -e \"{sql}\" 2>/dev/null"]
    env = os.environ.copy(); env["MSYS_NO_PATHCONV"] = "1"
    out = subprocess.run(cmd, capture_output=True, text=True, env=env).stdout
    rows = [l for l in out.splitlines()
            if l.strip() and not l.startswith(("INFO", "WARN", "SLF4J", "Connecting",
                                               "Connected", "Driver", "Transaction", "0:"))]
    return rows

if __name__ == "__main__":
    question = sys.argv[1] if len(sys.argv) > 1 else "销量最高的前5个品类"
    print(f"【问题】{question}")
    sql = generate_sql(question)
    print(f"【生成 SQL】\n{sql}")
    validate_sql(sql)
    rows = run_sql(sql)
    print("【执行结果】")
    for r in rows[:12]:
        print(" ", r)
