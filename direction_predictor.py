import os
import json
import sqlite3
import pandas as pd
import numpy as np

from datetime import datetime

from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

import joblib

# -----------------------------------------------------
# CONFIG
# -----------------------------------------------------

DB_PATH = "kait.db"

MODEL_DIR = "models"

MODEL_FILE = os.path.join(
    MODEL_DIR,
    "direction_predictor.pkl"
)

OUTPUT_FILE = "direction_prediction.json"

# -----------------------------------------------------
# DATABASE
# -----------------------------------------------------

def load_candles():

    conn = sqlite3.connect(DB_PATH)

    df = pd.read_sql(
        """
        SELECT *
        FROM nifty_candles
        ORDER BY date
        """,
        conn
    )

    conn.close()

    return df

# -----------------------------------------------------
# ATR
# -----------------------------------------------------

def calculate_atr(df, period=14):

    high_low = df["high"] - df["low"]

    high_close = (
        df["high"]
        - df["close"].shift(1)
    ).abs()

    low_close = (
        df["low"]
        - df["close"].shift(1)
    ).abs()

    tr = pd.concat(
        [
            high_low,
            high_close,
            low_close
        ],
        axis=1
    ).max(axis=1)

    atr = tr.rolling(period).mean()

    return atr

# -----------------------------------------------------
# FEATURES
# -----------------------------------------------------

def build_dataset(df):

    df = df.copy()

    df["return_5d"] = (
        df["close"] /
        df["close"].shift(5)
    ) - 1

    df["return_10d"] = (
        df["close"] /
        df["close"].shift(10)
    ) - 1

    df["return_20d"] = (
        df["close"] /
        df["close"].shift(20)
    ) - 1

    df["atr_14"] = calculate_atr(df)

    df["future_close"] = (
        df["close"]
        .shift(-5)
    )

    df["target"] = np.where(
        df["future_close"] > df["close"],
        1,
        0
    )

    df = df.dropna()

    return df

# -----------------------------------------------------
# TRAIN MODEL
# -----------------------------------------------------

def train_model(df):

    features = [
        "return_5d",
        "return_10d",
        "return_20d",
        "atr_14"
    ]

    X = df[features]

    y = df["target"]

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        shuffle=False
    )

    model = RandomForestClassifier(
        n_estimators=300,
        max_depth=5,
        random_state=42
    )

    model.fit(
        X_train,
        y_train
    )

    preds = model.predict(
        X_test
    )

    accuracy = accuracy_score(
        y_test,
        preds
    )

    return model, accuracy

# -----------------------------------------------------
# SAVE MODEL
# -----------------------------------------------------

def save_model(model):

    os.makedirs(
        MODEL_DIR,
        exist_ok=True
    )

    joblib.dump(
        model,
        MODEL_FILE
    )

# -----------------------------------------------------
# PREDICT TODAY
# -----------------------------------------------------

def predict_today(model, df):

    latest = df.iloc[-1]

    X = pd.DataFrame([{
        "return_5d":
            latest["return_5d"],

        "return_10d":
            latest["return_10d"],

        "return_20d":
            latest["return_20d"],

        "atr_14":
            latest["atr_14"]
    }])

    probability = model.predict_proba(X)[0]

    down_prob = float(probability[0])

    up_prob = float(probability[1])

    if up_prob > down_prob:

        direction = "UP"

        confidence = up_prob

    else:

        direction = "DOWN"

        confidence = down_prob

    return {
        "prediction_date":
            datetime.now().strftime(
                "%Y-%m-%d"
            ),

        "direction":
            direction,

        "probability":
            round(confidence, 4),

        "return_5d":
            round(
                latest["return_5d"],
                4
            ),

        "return_10d":
            round(
                latest["return_10d"],
                4
            ),

        "return_20d":
            round(
                latest["return_20d"],
                4
            ),

        "atr_14":
            round(
                latest["atr_14"],
                2
            )
    }

# -----------------------------------------------------
# MAIN
# -----------------------------------------------------

if __name__ == "__main__":

    print("=" * 60)
    print("KAIT — Phase 9B Direction Predictor")
    print("=" * 60)

    df = load_candles()

    print(
        f"\nRows available: {len(df)}"
    )

    dataset = build_dataset(df)

    model, accuracy = train_model(
        dataset
    )

    print(
        f"\nModel Accuracy: "
        f"{accuracy:.2%}"
    )

    save_model(model)

    print(
        f"\n✅ Model saved: "
        f"{MODEL_FILE}"
    )

    prediction = predict_today(
        model,
        dataset
    )

    with open(
        OUTPUT_FILE,
        "w"
    ) as f:

        json.dump(
            prediction,
            f,
            indent=2
        )

    print(
        f"\nDirection : "
        f"{prediction['direction']}"
    )

    print(
        f"Probability: "
        f"{prediction['probability']:.2%}"
    )

    print(
        f"\n✅ Prediction saved: "
        f"{OUTPUT_FILE}"
    )

    print(
        "\n✅ Phase 9B complete"
    )