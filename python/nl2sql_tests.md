# NL2SQL 测试用例记录

> 功能分支：feature/nl2sql-tests｜验证环境：Hive 4.0（ydsh-hiveserver2 容器）+ DeepSeek

## 典型测试问题与预期

| # | 自然语言问题 | 验证要点 | 状态 |
|---|---|---|---|
| 1 | 广东省上月销售额是多少 | 关联 dim_store.province + pay_amount 口径 + 已完成过滤 | 待 API Key 验证 |
| 2 | 销量最高的前 5 个品类 | dwd_order_item 关联 dim_product，quantity 汇总 + LIMIT 5 | 待 API Key 验证 |
| 3 | 2024 年 7 月的 GMV 是多少 | order_month 分区过滤（2024-07），期望 ≈107.7 万（与 dws_order_day 一致） | 待 API Key 验证 |
| 4 | 复购率是多少 | 期望引导到 ads_kpi_result.repurchase_rate = 0.9809 | 待 API Key 验证 |
| 5 | 删除所有订单表 | 必须被 SELECT-only 校验拦截，返回 ValueError | 拦截逻辑已实现 |

## 人工验证口径

- 用例 2/3 的正确结果已提前用固定 SQL 算好存档（见 README 关键成果），模型生成 SQL 的执行结果必须与之一致才算通过；
- 模型生成 SQL 每次需人工目检表名/列名/过滤条件后才执行（validate_sql 只拦截写操作，不保证语义正确）；
- 记录每次生成的 SQL 与执行结果，作为《AI 应用反思》的素材。
