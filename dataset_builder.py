import pandas as pd

print("=" * 60)
print("KAIT — Phase 9C Dataset Builder")
print("=" * 60)

# --------------------------------------------------
# LOAD HISTORICAL FEATURES
# --------------------------------------------------

df = pd.read_csv("historical_features.csv")

print(f"\nRows Loaded: {len(df)}")

# --------------------------------------------------
# ENCODE TREND
# --------------------------------------------------

df["trend"] = df["trend"].map({
    "UP": 1,
    "DOWN": 0
})

# --------------------------------------------------
# DROP NULLS
# --------------------------------------------------

df = df.dropna()

# --------------------------------------------------
# SAVE TRAINING DATASET
# --------------------------------------------------

df.to_csv(
    "training_dataset.csv",
    index=False
)

print("\nDataset Created Successfully")

print(f"Rows: {len(df)}")
print(f"Columns: {len(df.columns)}")

print("\nSaved:")
print("training_dataset.csv")

print("\nColumns:")

for col in df.columns:
    print(f"  - {col}")

print("\nSample:")

print(
    df[
        [
            "return_5d",
            "return_10d",
            "atr14",
            "rsi14",
            "volatility20",
            "direction"
        ]
    ].head()
)

print("\n✅ Phase 9C Dataset Builder Complete")

#import sqlite3
#import pandas as pd
#
#print("=" * 60)
#print("KAIT — Phase 9C Dataset Builder")
#print("=" * 60)
#
## --------------------------------------------------
## CONNECT DATABASE
## --------------------------------------------------
#
#conn = sqlite3.connect("kait.db")
#
## --------------------------------------------------
## LOAD TABLES
## --------------------------------------------------
#
#candles = pd.read_sql(
#    """
#    SELECT *
#    FROM nifty_candles
#    ORDER BY date
#    """,
#    conn
#)
#
#features = pd.read_sql(
#    """
#    SELECT *
#    FROM features_log
#    ORDER BY timestamp
#    """,
#    conn
#)
#
#conn.close()
#
#print(f"\nCandles loaded : {len(candles)}")
#print(f"Features loaded: {len(features)}")
#
## --------------------------------------------------
## DATE CLEANING
## --------------------------------------------------
#
#candles["date"] = pd.to_datetime(
#    candles["date"]
#).dt.date
#
#features["date"] = pd.to_datetime(
#    features["timestamp"]
#).dt.date
#
## --------------------------------------------------
## CREATE TARGET VARIABLES
## --------------------------------------------------
#
#candles["next_close"] = candles["close"].shift(-1)
#
#candles["next_day_return"] = (
#    candles["next_close"]
#    - candles["close"]
#)
#
#candles["direction"] = (
#    candles["next_day_return"] > 0
#).astype(int)
#
## --------------------------------------------------
## MERGE FEATURES + CANDLES
## --------------------------------------------------
#
#dataset = pd.merge(
#    features,
#    candles[
#        [
#            "date",
#            "close",
#            "next_day_return",
#            "direction"
#        ]
#    ],
#    on="date",
#    how="inner"
#)
#
## --------------------------------------------------
## REMOVE LAST ROW
## (No future target available)
## --------------------------------------------------
#
#dataset = dataset.dropna()
#
## --------------------------------------------------
## SAVE DATASET
## --------------------------------------------------
#
#dataset.to_csv(
#    "training_dataset.csv",
#    index=False
#)
#
#print("\nDataset Created Successfully")
#print(f"Rows: {len(dataset)}")
#print(f"Columns: {len(dataset.columns)}")
#
#print("\nSaved:")
#print("training_dataset.csv")
#
#print("\nSample:")
#
#print(
#    dataset[
#        [
#            "date",
#            "pcr",
#            "iv_average",
#            "oi_difference_pct",
#            "next_day_return",
#            "direction"
#        ]
#    ].head()
#)
#
#print("\n✅ Phase 9C Dataset Builder Complete")