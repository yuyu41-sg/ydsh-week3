-- ============================================================
-- 子任务1：ADS 应用层建设 + KPI 结果表
-- 口径统一（依据任务书步骤 2）：
--   GMV        = 所有有效订单（已完成）实付金额之和
--   订单量     = 去重订单数
--   客单价 AOV = GMV ÷ 订单量
--   活跃用户数 = 有下单行为的去重用户数
--   复购率     = 下单>=2 次用户数 ÷ 下单用户数（按已完成订单）
-- ============================================================

CREATE DATABASE IF NOT EXISTS ydsh_ads;

-- ---------- 1. 核心指标结果表（全期 KPI 单行） ----------
DROP TABLE IF EXISTS ydsh_ads.ads_kpi_result;
CREATE TABLE ydsh_ads.ads_kpi_result AS
SELECT
  ROUND(k.total_gmv, 2)                            AS gmv,
  k.total_orders                                   AS orders,
  ROUND(k.total_gmv / k.total_orders, 2)           AS aov,
  k.active_users,
  ROUND(r.repeat_users / r.all_users, 4)           AS repurchase_rate
FROM (
  SELECT
    SUM(pay_amount)               AS total_gmv,
    COUNT(DISTINCT order_id)      AS total_orders,
    COUNT(DISTINCT user_id)       AS active_users
  FROM ydsh_dwd.dwd_order
  WHERE order_status = '已完成'
) k
CROSS JOIN (
  SELECT
    SUM(CASE WHEN cnt >= 2 THEN 1 ELSE 0 END) AS repeat_users,
    COUNT(*)                                  AS all_users
  FROM (
    SELECT user_id, COUNT(DISTINCT order_id) AS cnt
    FROM ydsh_dwd.dwd_order
    WHERE order_status = '已完成'
    GROUP BY user_id
  ) t
) r;

-- ---------- 2. 销售日报 ----------
DROP TABLE IF EXISTS ydsh_ads.ads_sales_daily;
CREATE TABLE ydsh_ads.ads_sales_daily AS
SELECT
  d.dt,
  d.gmv,
  d.orders,
  ROUND(d.gmv / d.orders, 2) AS aov,
  d.users,
  ROUND((d.gmv - lag_gmv.prev_gmv) / lag_gmv.prev_gmv, 4) AS gmv_dod  -- 环比（首日为 NULL）
FROM ydsh_dws.dws_order_day d
JOIN (
  SELECT dt, LAG(gmv) OVER (ORDER BY dt) AS prev_gmv
  FROM ydsh_dws.dws_order_day
) lag_gmv ON d.dt = lag_gmv.dt;

-- ---------- 3. 品类销售 Top10（明细口径） ----------
DROP TABLE IF EXISTS ydsh_ads.ads_category_top10;
CREATE TABLE ydsh_ads.ads_category_top10 AS
SELECT category, ROUND(sales, 2) AS sales, orders
FROM (
  SELECT category, SUM(sales) AS sales, SUM(orders) AS orders
  FROM ydsh_dws.dws_order_category_day
  GROUP BY category
  ORDER BY sales DESC
) t
LIMIT 10;

-- ---------- 4. 用户价值分层（RFM 简化版：按累计消费分层） ----------
DROP TABLE IF EXISTS ydsh_ads.ads_user_value;
CREATE TABLE ydsh_ads.ads_user_value AS
WITH u AS (
  SELECT
    user_id,
    COUNT(DISTINCT order_id)          AS order_cnt,
    ROUND(SUM(pay_amount), 2)         AS total_amount,
    MIN(SUBSTR(order_timestamp, 1, 10)) AS first_order_date,
    MAX(SUBSTR(order_timestamp, 1, 10)) AS last_order_date
  FROM ydsh_dwd.dwd_order
  WHERE order_status = '已完成'
  GROUP BY user_id
)
SELECT
  u.*,
  CASE
    WHEN total_amount >= 20000 THEN '高价值用户'
    WHEN total_amount >= 12000 THEN '潜力用户'
    WHEN total_amount >= 6000  THEN '一般用户'
    ELSE '低价值用户'
  END AS value_level
FROM u;

-- ---------- 5. 品类销售占比（供报告与答辩） ----------
DROP TABLE IF EXISTS ydsh_ads.ads_category_share;
CREATE TABLE ydsh_ads.ads_category_share AS
SELECT
  category,
  ROUND(sales, 2) AS sales,
  ROUND(sales / SUM(sales) OVER (), 4) AS share
FROM (
  SELECT category, SUM(sales) AS sales
  FROM ydsh_dws.dws_order_category_day
  GROUP BY category
) t;

-- ---------- 校验 ----------
SELECT * FROM ydsh_ads.ads_kpi_result;
SELECT * FROM ydsh_ads.ads_category_top10 LIMIT 5;
SELECT value_level, COUNT(*) AS users, ROUND(SUM(total_amount),2) AS amount
FROM ydsh_ads.ads_user_value GROUP BY value_level ORDER BY amount DESC;
