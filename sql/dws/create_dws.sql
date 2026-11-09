-- ============================================================
-- 子任务1：DWS 汇总层建设
-- 口径说明：
--   有效订单 = order_status = '已完成'（与第 2 周 EDA 口径一致）
--   GMV     = 有效订单 pay_amount 之和
--   品类销售额采用明细口径 = sum(unit_price * quantity * (1 - discount))，
--   与订单实付 GMV 存在口径差异（明细为商品原价折后、订单含运费/优惠分摊），
--   在《预测建模分析报告》与答辩中注明。
-- ============================================================

CREATE DATABASE IF NOT EXISTS ydsh_dws;

-- ---------- 1. 按天汇总（全渠道） ----------
DROP TABLE IF EXISTS ydsh_dws.dws_order_day;
CREATE TABLE ydsh_dws.dws_order_day AS
SELECT
  SUBSTR(order_timestamp, 1, 10)              AS dt,
  COUNT(DISTINCT order_id)                    AS orders,
  ROUND(SUM(pay_amount), 2)                   AS gmv,
  COUNT(DISTINCT user_id)                     AS users
FROM ydsh_dwd.dwd_order
WHERE order_status = '已完成'
GROUP BY SUBSTR(order_timestamp, 1, 10);

-- ---------- 2. 按天 + 门店汇总 ----------
DROP TABLE IF EXISTS ydsh_dws.dws_order_store_day;
CREATE TABLE ydsh_dws.dws_order_store_day AS
SELECT
  store_id,
  SUBSTR(order_timestamp, 1, 10)              AS dt,
  COUNT(DISTINCT order_id)                    AS orders,
  ROUND(SUM(pay_amount), 2)                   AS gmv,
  COUNT(DISTINCT user_id)                     AS users
FROM ydsh_dwd.dwd_order
WHERE order_status = '已完成'
GROUP BY store_id, SUBSTR(order_timestamp, 1, 10);

-- ---------- 3. 按天 + 品类汇总（明细口径） ----------
DROP TABLE IF EXISTS ydsh_dws.dws_order_category_day;
CREATE TABLE ydsh_dws.dws_order_category_day AS
SELECT
  p.category,
  SUBSTR(o.order_timestamp, 1, 10)            AS dt,
  COUNT(DISTINCT i.order_id)                  AS orders,
  COUNT(*)                                    AS items,
  ROUND(SUM(i.unit_price * i.quantity * (1 - i.discount)), 2) AS sales
FROM ydsh_dwd.dwd_order_item i
JOIN ydsh_dwd.dwd_order o ON i.order_id = o.order_id AND o.order_status = '已完成'
JOIN ydsh_dwd.dim_product p ON i.product_id = p.product_id
GROUP BY p.category, SUBSTR(o.order_timestamp, 1, 10);

-- ---------- 4. 按天 + 渠道汇总 ----------
DROP TABLE IF EXISTS ydsh_dws.dws_order_channel_day;
CREATE TABLE ydsh_dws.dws_order_channel_day AS
SELECT
  channel,
  SUBSTR(order_timestamp, 1, 10)              AS dt,
  COUNT(DISTINCT order_id)                    AS orders,
  ROUND(SUM(pay_amount), 2)                   AS gmv,
  COUNT(DISTINCT user_id)                     AS users
FROM ydsh_dwd.dwd_order
WHERE order_status = '已完成'
GROUP BY channel, SUBSTR(order_timestamp, 1, 10);

-- ---------- 校验：行数与总额闭环 ----------
SELECT 'dws_order_day' AS tbl, COUNT(*) AS rows_cnt, ROUND(SUM(gmv),2) AS total_gmv FROM ydsh_dws.dws_order_day
UNION ALL
SELECT 'dws_order_store_day', COUNT(*), ROUND(SUM(gmv),2) FROM ydsh_dws.dws_order_store_day
UNION ALL
SELECT 'dws_order_channel_day', COUNT(*), ROUND(SUM(gmv),2) FROM ydsh_dws.dws_order_channel_day;
-- 预期：dws_order_day 约 366 行；store/channel 汇总总额 = dws_order_day 总额 = 订单口径 GMV
