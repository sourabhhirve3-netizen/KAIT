import sqlite3
import json
import os
import joblib

import pandas as pd

from datetime import datetime

from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error

DB_PATH = "kait.db"
MODEL_PATH = "models/market_predictor.pkl"
OUTPUT_FILE = "prediction.json"


# ─────────────────────────────────────────────────────────────
# LOAD CANDLE DATA
# ─────────────────────────────────────────────────────────────

def load_candles():

    conn = sqlite3.connect(DB_PATH)

    df = pd.read_sql(
        """
        SELECT
            date,
            open,
            high,
            low,
            close
        FROM nifty_candles
        ORDER BY date
        """,
        conn
    )

    conn.close()

    return df


# ─────────────────────────────────────────────────────────────
# FEATURE ENGINEERING
# ─────────────────────────────────────────────────────────────

def build_features(df):

    df = df.copy()

    df["ret_5"] = df["close"].pct_change(5)
    df["ret_10"] = df["close"].pct_change(10)
    df["ret_20"] = df["close"].pct_change(20)

    df["vol_5"] = (
        df["close"]
        .pct_change()
        .rolling(5)
        .std()
    )

    df["vol_10"] = (
        df["close"]
        .pct_change()
        .rolling(10)
        .std()
    )

    df["vol_20"] = (
        df["close"]
        .pct_change()
        .rolling(20)
        .std()
    )

    df["range"] = (
        df["high"] - df["low"]
    )

    df["atr_14"] = (
        df["range"]
        .rolling(14)
        .mean()
    )

    # Target Variable
    df["future_move_5d"] = (
        abs(
            df["close"].shift(-5)
            - df["close"]
        )
    )

    return df.dropna()


# ─────────────────────────────────────────────────────────────
# TRAIN MODEL
# ─────────────────────────────────────────────────────────────

def train_model(df):

    features = [
        "ret_5",
        "ret_10",
        "ret_20",
        "vol_5",
        "vol_10",
        "vol_20",
        "atr_14"
    ]

    print(f"\nRows available: {len(df)}")

    if len(df) < 100:
        print(
            "\n⚠️ WARNING:"
            "\nLess than 100 rows available."
            "\nPredictions may be unreliable."
        )

    X = df[features]
    y = df["future_move_5d"]

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.20,
        shuffle=False
    )

    model = RandomForestRegressor(
        n_estimators=300,
        max_depth=8,
        random_state=42
    )

    model.fit(X_train, y_train)

    preds = model.predict(X_test)

    mae = mean_absolute_error(
        y_test,
        preds
    )

    print(
        f"\nModel MAE: {mae:.2f} points"
    )

    return model, mae


# ─────────────────────────────────────────────────────────────
# SAVE MODEL
# ─────────────────────────────────────────────────────────────

def save_model(model):

    os.makedirs(
        "models",
        exist_ok=True
    )

    joblib.dump(
        model,
        MODEL_PATH
    )

    print(
        f"\n✅ Model saved: {MODEL_PATH}"
    )


# ─────────────────────────────────────────────────────────────
# PREDICT TODAY
# ─────────────────────────────────────────────────────────────

def predict_today(model, df):

    latest = df.iloc[-1]

    print("\nToday's Features")
    print("-" * 35)

    print(f"5D Return  : {latest['ret_5']:.4f}")
    print(f"10D Return : {latest['ret_10']:.4f}")
    print(f"20D Return : {latest['ret_20']:.4f}")
    print(f"ATR(14)    : {latest['atr_14']:.2f}")

    X = pd.DataFrame([{
        "ret_5": latest["ret_5"],
        "ret_10": latest["ret_10"],
        "ret_20": latest["ret_20"],
        "vol_5": latest["vol_5"],
        "vol_10": latest["vol_10"],
        "vol_20": latest["vol_20"],
        "atr_14": latest["atr_14"]
    }])

    predicted_move = float(
        model.predict(X)[0]
    )

    spot = float(
        latest["close"]
    )

    return {
        "spot": spot,
        "predicted_move": round(
            predicted_move,
            2
        ),
        "lower": round(
            spot - predicted_move,
            2
        ),
        "upper": round(
            spot + predicted_move,
            2
        )
    }


# ─────────────────────────────────────────────────────────────
# SAVE OUTPUT
# ─────────────────────────────────────────────────────────────

def save_prediction(result, mae):

    output = {

        "timestamp":
            datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            ),

        "model_metrics": {
            "mae_points": round(
                mae,
                2
            )
        },

        "spot":
            result["spot"],

        "predicted_move":
            result["predicted_move"],

        "expected_range": {

            "low":
                result["lower"],

            "high":
                result["upper"]
        }
    }

    with open(
        OUTPUT_FILE,
        "w"
    ) as f:

        json.dump(
            output,
            f,
            indent=2
        )

    print(
        f"\n✅ Prediction saved: {OUTPUT_FILE}"
    )

    return output


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":

    print("=" * 60)
    print("KAIT — Phase 9A Market Predictor")
    print("=" * 60)

    candles = load_candles()

    dataset = build_features(
        candles
    )

    model, mae = train_model(
        dataset
    )

    save_model(
        model
    )

    result = predict_today(
        model,
        dataset
    )

    save_prediction(
        result,
        mae
    )

    print(
        f"\nExpected Move : ±{result['predicted_move']:.0f} points"
    )

    print(
        f"Expected Range: "
        f"{result['lower']:.0f}"
        f" - "
        f"{result['upper']:.0f}"
    )

    print(
        "\n✅ Phase 9A complete"
    )