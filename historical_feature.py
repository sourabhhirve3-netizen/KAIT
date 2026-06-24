import sqlite3
import pandas as pd
import numpy as np

print("=" * 60)
print("KAIT — Historical Feature Builder")
print("=" * 60)

# ============================================================
# LOAD CANDLES
# ============================================================

conn = sqlite3.connect("kait.db")

df = pd.read_sql(
    """
    SELECT *
    FROM nifty_candles
    ORDER BY date
    """,
    conn
)

conn.close()

print(f"\nCandles Loaded: {len(df)}")

# ============================================================
# CLEAN
# ============================================================

df["date"] = pd.to_datetime(df["date"])

numeric_cols = [
    "open",
    "high",
    "low",
    "close"
]

for col in numeric_cols:
    df[col] = pd.to_numeric(df[col])

# ============================================================
# RETURNS
# ============================================================

df["return_1d"] = (
    df["close"].pct_change() * 100
)

df["return_5d"] = (
    df["close"].pct_change(5) * 100
)

df["return_10d"] = (
    df["close"].pct_change(10) * 100
)

df["return_20d"] = (
    df["close"].pct_change(20) * 100
)

# ============================================================
# ATR(14)
# ============================================================

df["prev_close"] = df["close"].shift(1)

df["tr1"] = df["high"] - df["low"]

df["tr2"] = (
    df["high"] - df["prev_close"]
).abs()

df["tr3"] = (
    df["low"] - df["prev_close"]
).abs()

df["true_range"] = df[
    ["tr1", "tr2", "tr3"]
].max(axis=1)

df["atr14"] = (
    df["true_range"]
    .rolling(14)
    .mean()
)

# ============================================================
# RSI(14)
# ============================================================

delta = df["close"].diff()

gain = delta.clip(lower=0)
loss = -delta.clip(upper=0)

avg_gain = gain.rolling(14).mean()
avg_loss = loss.rolling(14).mean()

rs = avg_gain / avg_loss

df["rsi14"] = (
    100 - (100 / (1 + rs))
)

# ============================================================
# VOLATILITY
# ============================================================

daily_returns = (
    df["close"].pct_change()
)

df["volatility20"] = (
    daily_returns
    .rolling(20)
    .std()
    * np.sqrt(252)
    * 100
)

# ============================================================
# MOMENTUM
# ============================================================

df["momentum20"] = (
    df["close"]
    - df["close"].shift(20)
)

# ============================================================
# TREND
# ============================================================

df["sma20"] = (
    df["close"]
    .rolling(20)
    .mean()
)

df["sma50"] = (
    df["close"]
    .rolling(50)
    .mean()
)

df["trend"] = np.where(
    df["sma20"] > df["sma50"],
    "UP",
    "DOWN"
)

# ============================================================
# TARGETS
# ============================================================

df["next_day_return"] = (
    df["close"]
    .shift(-1)
    / df["close"]
    - 1
) * 100

df["direction"] = np.where(
    df["next_day_return"] > 0,
    1,
    0
)

# ============================================================
# FINAL DATASET
# ============================================================

final_df = df[
    [
        "date",
        "close",

        "return_1d",
        "return_5d",
        "return_10d",
        "return_20d",

        "atr14",
        "rsi14",
        "volatility20",
        "momentum20",

        "sma20",
        "sma50",
        "trend",

        "next_day_return",
        "direction"
    ]
]

final_df = final_df.dropna()

# ============================================================
# SAVE
# ============================================================

final_df.to_csv(
    "historical_features.csv",
    index=False
)

print("\nHistorical Features Created")

print(f"Rows: {len(final_df)}")
print(f"Columns: {len(final_df.columns)}")

print("\nSaved:")
print("historical_features.csv")

print("\nSample:")
print(final_df.head())

print("\n✅ Historical Feature Builder Complete")