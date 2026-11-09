# 云购生活新零售数仓 · 第 3 周（数据分析 · 预测建模 · AI 协同）

ydsh-team · 张宇（20230308059）｜前置仓库：[ydsh-week1](https://github.com/yuyu41-sg/ydsh-week1)（环境与 ODS/DWD）、[ydsh-week2](https://github.com/yuyu41-sg/ydsh-week2)（清洗进阶与 DWD 建模）

## 本周内容

| 子任务 | 交付物 | 位置 |
|---|---|---|
| 1. DWS/ADS 建模与 KPI | 汇总/应用层脚本 + 指标口径 | `sql/dws/` `sql/ads/` |
| 2. 时间序列预测 | 预测脚本 + 报告 | `python/predict_gmv.py`、`预测建模分析报告.md` |
| 3. 大模型 API 接入 | 密钥管理 + 最小化调用 | `.env.example`、`python/llm_client.py` |
| 4. NL2SQL | Schema 抽取 + LangChain 链路 | `python/schema_extract.py`、`python/nl2sql.py` |
| 5. AI 智能洞察 | 异常归因 + 自动摘要 + 反思 | `python/ai_insight.py`、`AI经营分析摘要.md` |
| 6. Git 协同 | 分支/PR/Code Review/Issue/Tag | GitHub 仓库留痕 |

## 指标口径（统一约定）

- **有效订单** = `order_status = '已完成'`
- **GMV** = 有效订单 `pay_amount` 之和；**订单量** = 去重订单数
- **客单价 AOV** = GMV ÷ 订单量；**活跃用户数** = 有下单行为的去重用户数
- **复购率** = 下单≥2 次用户数 ÷ 下单用户数
- 品类销售额为明细口径 `unit_price × quantity × (1-discount)`，与订单实付 GMV 存在口径差异（已在报告中注明）

## 快速开始

```bash
# 1. DWS/ADS 建表（容器内已挂载或 docker cp 后执行）
docker cp sql/dws/create_dws.sql ydsh-hiveserver2:/tmp/
docker cp sql/ads/create_ads.sql ydsh-hiveserver2:/tmp/
docker exec ydsh-hiveserver2 beeline -u jdbc:hive2://localhost:10000 -f /tmp/create_dws.sql
docker exec ydsh-hiveserver2 beeline -u jdbc:hive2://localhost:10000 -f /tmp/create_ads.sql

# 2. Python 依赖
pip install -r python/requirements.txt

# 3. 预测建模（数据经 data/daily_gmv.csv，由 dws_order_day 导出）
python python/predict_gmv.py

# 4. AI 任务：复制 .env.example 为 .env 并填入 DEEPSEEK_API_KEY
python python/llm_client.py          # 最小化连通验证
python python/schema_extract.py      # Schema 抽取
python python/nl2sql.py "销量最高的前5个品类"
python python/ai_insight.py          # 异常归因 + 自动摘要
```

## 关键成果

- ADS 全期 KPI：GMV 1415.12 万 / 订单 5642 / 客单价 2508.19 / 活跃用户 997 / 复购率 98.09%
- 用户分层：高价值 201 / 潜力 379 / 一般 309 / 低价值 108
- 预测建模：线性回归 MAPE 31.7% ≈ 均值基线 31.5% ≈ 序列 CV 31.2%，经基线对比证实数据无趋势/周期信号，模型实为均值外推——边界分析详见报告
- NL2SQL：Schema 自动注入 Prompt + SELECT-only 拦截 + few-shot 示例，支持自然语言问答闭环

## 密钥安全规范

- API Key 仅存 `.env`（已被 `.gitignore` 排除），代码经 `os.environ` 读取，禁止硬编码
- `.env.example` 提供模板，真实 Key 永不入库
