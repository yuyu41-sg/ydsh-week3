# -*- coding: utf-8 -*-
"""
子任务2：时间序列分析与预测建模
数据：ydsh_dws.dws_order_day 导出的每日 GMV（data/daily_gmv.csv，2024 全年 366 天）
方法：趋势分解 / 移动平均 / 同环比 → 滞后特征 + 线性回归（sklearn）预测未来 7 天
评估：留出最后 30 天作为测试集，计算 MAE / MAPE
输出：data/pred_gmv_7d.csv、data/gmv_trend.png、data/gmv_pred.png、控制台评估指标
"""
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei"]
plt.rcParams["axes.unicode_minus"] = False

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")

# ---------- 1. 读取数据 ----------
df = pd.read_csv(os.path.join(DATA, "daily_gmv.csv"),
                 names=["dt", "gmv", "orders", "users"])
df["dt"] = pd.to_datetime(df["dt"])
df = df.set_index("dt").sort_index()
print(f"序列长度: {len(df)} 天，范围: {df.index.min().date()} ~ {df.index.max().date()}")
print(f"GMV 均值: {df['gmv'].mean():.0f} 元/天，标准差: {df['gmv'].std():.0f}")

# ---------- 2. 趋势分解与移动平均 ----------
df["ma7"] = df["gmv"].rolling(7).mean()
df["ma30"] = df["gmv"].rolling(30).mean()
df["mom"] = df["gmv"].pct_change()          # 日环比
monthly = df["gmv"].resample("MS").sum()
print("\n月度 GMV（万元）:")
print((monthly / 10000).round(1).to_string())

# ---------- 3. 特征工程 ----------
def make_features(d):
    d = d.copy()
    d["lag1"] = d["gmv"].shift(1)            # 前一天 GMV
    d["lag7"] = d["gmv"].shift(7)            # 前一周同日 GMV（周周期）
    d["ma7"] = d["gmv"].shift(1).rolling(7).mean()  # 前 7 天均值（不含当天，防泄露）
    d["dow"] = d.index.day_of_week           # 星期几
    return d.dropna()

feat = make_features(df)
FEATURES = ["lag1", "lag7", "ma7", "dow"]

# ---------- 4. 训练/测试划分（最后 30 天为测试集） ----------
X, y = feat[FEATURES], feat["gmv"]
split_date = feat.index[-30]
train, test = feat[feat.index < split_date], feat[feat.index >= split_date]
model = LinearRegression().fit(train[FEATURES], train["gmv"])
test_pred = model.predict(test[FEATURES])
mae = mean_absolute_error(test["gmv"], test_pred)
mape = np.mean(np.abs((test["gmv"] - test_pred) / test["gmv"])) * 100
print(f"\n【模型评估】测试集（最后30天）: MAE={mae:.0f} 元, MAPE={mape:.1f}%")
print("系数:", dict(zip(FEATURES, [round(c, 1) for c in model.coef_])))

# ---------- 4.1 基线对比（证明数据可预测性的关键证据） ----------
naive_mae = mean_absolute_error(test["gmv"], test["lag1"])          # 朴素：昨天=今天
naive_mape = np.mean(np.abs((test["gmv"] - test["lag1"]) / test["gmv"])) * 100
mean_pred = np.full(len(test), train["gmv"].mean())                  # 均值基线
mean_mae = mean_absolute_error(test["gmv"], mean_pred)
mean_mape = np.mean(np.abs((test["gmv"] - mean_pred) / test["gmv"])) * 100
cv = df["gmv"].std() / df["gmv"].mean() * 100
print(f"【基线对比】朴素预测(昨天=今天): MAPE={naive_mape:.1f}%  均值预测: MAPE={mean_mape:.1f}%")
print(f"序列变异系数 CV = {cv:.1f}%（日波动幅度）——若模型 MAPE≈CV，说明数据近乎随机、无可用信号")

# ---------- 5. 全量重训 + 迭代预测未来 7 天 ----------
final_model = LinearRegression().fit(X, y)
hist = df["gmv"].tolist()
dates = df.index
future_dates = pd.date_range(dates[-1] + pd.Timedelta(days=1), periods=7)
future_preds = []
for d in future_dates:
    lag1 = hist[-1]
    lag7 = hist[-7]
    ma7 = np.mean(hist[-7:])
    dow = d.day_of_week
    p = final_model.predict(pd.DataFrame([[lag1, lag7, ma7, dow]], columns=FEATURES))[0]
    future_preds.append(p)
    hist.append(p)

pred_df = pd.DataFrame({"dt": future_dates.date, "pred_gmv": np.round(future_preds, 2)})
pred_df.to_csv(os.path.join(DATA, "pred_gmv_7d.csv"), index=False, encoding="utf-8-sig")
print(f"\n【未来7天GMV预测】（单位：元）")
print(pred_df.to_string(index=False))
print(f"7天预测合计: {sum(future_preds)/10000:.1f} 万元，日均: {np.mean(future_preds):.0f} 元")

# ---------- 6. 可视化 ----------
fig, axes = plt.subplots(2, 1, figsize=(12, 8))
axes[0].plot(df.index, df["gmv"], alpha=0.4, label="每日GMV")
axes[0].plot(df.index, df["ma7"], color="red", lw=1.5, label="7日移动平均")
axes[0].plot(df.index, df["ma30"], color="green", lw=1.5, label="30日移动平均")
axes[0].set_title("2024年每日GMV趋势（订单口径，已完成订单）")
axes[0].legend(); axes[0].set_ylabel("GMV（元）")

last = df["gmv"].tail(60)
axes[1].plot(last.index, last.values, label="真实GMV（近60天）")
axes[1].plot(future_dates, future_preds, "o--", color="orange", label="预测GMV（未来7天）")
axes[1].set_title(f"未来7天GMV预测（线性回归，测试集 MAPE={mape:.1f}%）")
axes[1].legend(); axes[1].set_ylabel("GMV（元）")
plt.tight_layout()
plt.savefig(os.path.join(DATA, "gmv_trend.png"), dpi=130)
plt.savefig(os.path.join(DATA, "gmv_pred.png"), dpi=130)
print("\n图表已保存: data/gmv_trend.png, data/gmv_pred.png")
