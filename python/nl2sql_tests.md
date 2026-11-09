# NL2SQL 测试用例记录

> 功能分支：feature/nl2sql-tests｜验证环境：Hive 4.0（ydsh-hiveserver2 容器）+ 智谱 GLM（glm-4-flash, temperature=0）

## 典型测试问题与实测结果（2026-11-09 实测）

| # | 自然语言问题 | 验证要点 | 实测结果 |
|---|---|---|---|
| 1 | 销量最高的前5个品类 | dwd_order_item 关联 dim_product，quantity 汇总 + LIMIT 5 | ✅ 一次通过（运动户外 7382 等，与人工口径一致） |
| 2 | 2024年6月广东省的销售额是多少 | 关联 dim_store.province + 已完成过滤 + 分区裁剪 | ✅ 一次通过（16443.04） |
| 3 | 2024年每月的GMV和订单量趋势 | 12 个月分组聚合 | ⚠️→✅ 首版 GROUP BY 用了别名，Hive 报 10004；**错误回传自修复 1 次后通过** |
| 4 | 删除所有订单数据 | 必须被 SELECT-only 校验拦截 | ✅ 生成 DELETE 被 validate_sql 拦截，未触达 Hive |

## 关键实测细节

### 用例 3：Hive 方言错误与自修复

模型首版 SQL（glm-4-flash 常见问题）：

```sql
SELECT SUBSTR(o.order_month, 1, 7) AS month, ... GROUP BY month
```

Hive 报错：`SemanticException [Error 10004]: Invalid table alias or column reference 'month'`
（Hive 不允许 GROUP BY 使用 SELECT 别名，MySQL 语法在 Hive 上不通用）

处理措施（两层）：

1. 系统提示词追加规则：GROUP BY/HAVING 必须重复完整表达式，禁止别名分组；
2. `nl2sql.py` 新增 `repair_sql()` 错误反馈自修复：捕获 beeline 报错回传大模型重写 SQL，最多重试 2 次。实测 1 次重试即收敛为 `GROUP BY SUBSTR(o.order_month, 1, 7)`，返回 12 个月完整数据。

### 用例 2 实测执行结果

```sql
SELECT ROUND(SUM(o.pay_amount), 2) AS sales
FROM ydsh_dwd.dwd_order o
JOIN ydsh_dwd.dim_store s ON o.store_id = s.store_id
WHERE s.province = '广东省' AND o.order_status = '已完成'
AND SUBSTR(o.order_month, 1, 7) = '2024-06' LIMIT 50;
```
结果：sales = 16443.04（与 dws_order_day 月度 GMV 114.1 万的全渠道口径量级一致，差异来自省份过滤）

### 用例 4 拦截实录

```
【生成 SQL】DELETE FROM ydsh_dwd.dwd_order;
ValueError: 模型生成了被禁止的语句: ['DELETE']，已拦截
```

## 调试记录

- beeline 结果曾被 Tez "Status: Running" 日志污染：加 `--silent=true` 并完善行过滤规则后输出干净；
- 行过滤规则保留 `Error:`/`FAILED:` 行用于自修复识别。

## 人工验证口径

- 模型生成 SQL 的执行结果须与人工固定 SQL 的存档结果一致才算通过；
- validate_sql 只拦截写操作，不保证语义正确，SQL 执行前仍需人工目检表名/列名/过滤条件；
- 每次生成的 SQL 与执行结果均已记录，作为《AI 应用反思》素材。

## 测试结论

4/4 通过。glm-4-flash 对 Hive 方言细节掌握不足，但"提示词约束 + 报错回传自修复"两道机制可稳定收敛到正确 SQL，SELECT-only 安全拦截在负例中验证有效。
