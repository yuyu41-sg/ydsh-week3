# -*- coding: utf-8 -*-
"""
子任务5：AI 智能洞察与报告生成
流程：
  1) 从 Hive 拉取核心 KPI + 月度 GMV + 品类占比（beeline → csv）
  2) 调用智谱 GLM 大模型做异常归因（找 GMV 环比降幅最大的月份并分析原因）
  3) 生成自动化经营分析摘要
  4) 输出《AI 经营分析摘要》与人工验证要点
前置：.env 已配置 ZHIPU_API_KEY
用法：python ai_insight.py
"""
import json
import os
import subprocess
from datetime import datetime

from dotenv import load_dotenv
from openai import OpenAI

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE, ".env"))

api_key = os.environ.get("ZHIPU_API_KEY")
if not api_key or "xxxx" in api_key:
    raise SystemExit("未配置 API Key：请复制 .env.example 为 .env 并填入真实 ZHIPU_API_KEY")

client = OpenAI(api_key=api_key,
                base_url=os.environ.get("ZHIPU_BASE_URL", "https://open.bigmodel.cn/api/paas/v4/"))

def hql_query(sql):
    cmd = ["docker", "exec", "ydsh-hiveserver2", "bash", "-c",
           f"beeline -u jdbc:hive2://localhost:10000 --outputformat=tsv2 -e \"{sql}\" 2>/dev/null"]
    env = os.environ.copy(); env["MSYS_NO_PATHCONV"] = "1"
    out = subprocess.run(cmd, capture_output=True, text=True, env=env).stdout
    return [l for l in out.splitlines() if l.strip() and not l.startswith(("INFO", "WARN", "SLF4J"))]

# ---------- 1. 拉取事实数据 ----------
kpi = hql_query("SELECT * FROM ydsh_ads.ads_kpi_result")
monthly = hql_query("SELECT SUBSTR(dt,1,7) m, ROUND(SUM(gmv)/10000,1) gmv_wan, SUM(orders) orders "
                    "FROM ydsh_dws.dws_order_day GROUP BY SUBSTR(dt,1,7) ORDER BY m")
cat = hql_query("SELECT category, sales, share FROM ydsh_ads.ads_category_share ORDER BY share DESC LIMIT 5")
user_level = hql_query("SELECT value_level, COUNT(*) users, ROUND(SUM(total_amount)/10000,1) amount_wan "
                       "FROM ydsh_ads.ads_user_value GROUP BY value_level ORDER BY amount_wan DESC")

facts = (f"全期KPI: {kpi}\n月度GMV(万元): {monthly}\n品类Top5(销售额,占比): {cat}\n用户分层: {user_level}")
print("=== 注入大模型的事实数据 ===")
print(facts)

# ---------- 2. 异常归因 ----------
attribution_prompt = f"""你是零售行业数据分析师。以下是某新零售企业 2024 年的真实经营数据（已完成订单口径）：

{facts}

任务：
1. 找出月度 GMV 环比降幅最大的月份，结合订单量变化判断是"客单下降"还是"客流下降"；
2. 给出 2~3 个可能的业务归因（标注哪些是数据可验证的、哪些是推测）；
3. 每个结论必须引用上面的具体数字，禁止编造数据。

用简洁的编号列表回答。"""

resp1 = client.chat.completions.create(
    model=os.environ.get("ZHIPU_MODEL", "glm-4-flash"),
    messages=[{"role": "user", "content": attribution_prompt}], temperature=0.3)
attribution = resp1.choices[0].message.content

# ---------- 3. 经营分析摘要 ----------
summary_prompt = f"""基于以下 2024 年真实经营数据，写一份 300 字以内的经营分析摘要（面向管理层），
结构：总体表现 → 亮点 → 风险 → 一条可执行建议。所有数字必须来自提供的数据，不得虚构。

{facts}"""

resp2 = client.chat.completions.create(
    model=os.environ.get("ZHIPU_MODEL", "glm-4-flash"),
    messages=[{"role": "user", "content": summary_prompt}], temperature=0.5)
summary = resp2.choices[0].message.content

# ---------- 4. 落盘 ----------
report = f"""# AI 经营分析摘要（自动生成）

> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}
> 模型：智谱 GLM（glm-4-flash）｜ 事实数据来源：ydsh_ads / ydsh_dws 层 Hive 实查
> ⚠️ AI 生成内容，业务结论需人工验证后采用（见文末验证要点）

## 一、异常归因分析

{attribution}

## 二、经营分析摘要

{summary}

## 三、人工验证要点（AI 局限性说明）

1. 核对归因引用的数字是否与 Hive 实查一致（防幻觉）；
2. AI 的业务归因（如促销、季节因素）在当前模拟数据中无营销事件表支撑，属推测，不能直接采信；
3. 本数据集为模拟数据，"异常"多为随机波动，归因结论仅作方法演示；
4. 建议人工复核后再进入管理层汇报。
"""
out_path = os.path.join(BASE, "AI经营分析摘要.md")
with open(out_path, "w", encoding="utf-8") as f:
    f.write(report)
print("\n=== 异常归因 ===\n", attribution)
print("\n=== 经营摘要 ===\n", summary)
print("\n已写出", out_path)
