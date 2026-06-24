# unified_ml_engine.py

import pandas as pd
import joblib

from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier

print("=" * 60)
print("KAIT — Unified ML Engine")
print("=" * 60)

# ==========================================================
# LOAD DATASET
# ==========================================================

df = pd.read_csv("training_dataset.csv")

print(f"\nRows Loaded : {len(df)}")

# ==========================================================
# PREPARE FEATURES
# ==========================================================

feature_columns = [
    "return_1d",
    "return_5d",
    "return_10d",
    "return_20d",
    "atr14",
    "rsi14",
    "volatility20",
    "momentum20",
    "sma20",
    "sma50"
]

X = df[feature_columns]

y = df["direction"]

print(f"Features : {len(feature_columns)}")
print(f"Target   : direction")

# ==========================================================
# TRAIN TEST SPLIT
# ==========================================================

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.2,
    shuffle=False
)

print(f"\nTrain Rows : {len(X_train)}")
print(f"Test Rows  : {len(X_test)}")

# ==========================================================
# MODEL 1
# ==========================================================

print("\nTraining Logistic Regression...")

lr = LogisticRegression(max_iter=1000)

lr.fit(X_train, y_train)

lr_pred = lr.predict(X_test)

lr_acc = accuracy_score(y_test, lr_pred)

print(
    f"Logistic Regression Accuracy: "
    f"{round(lr_acc * 100,2)}%"
)

# ==========================================================
# MODEL 2
# ==========================================================

print("\nTraining Random Forest...")

rf = RandomForestClassifier(
    n_estimators=200,
    max_depth=6,
    random_state=42
)

rf.fit(X_train, y_train)

rf_pred = rf.predict(X_test)

rf_acc = accuracy_score(y_test, rf_pred)

print(
    f"Random Forest Accuracy: "
    f"{round(rf_acc * 100,2)}%"
)

# ==========================================================
# SELECT BEST MODEL
# ==========================================================

if rf_acc > lr_acc:
    best_model = rf
    best_name = "Random Forest"
    best_acc = rf_acc
else:
    best_model = lr
    best_name = "Logistic Regression"
    best_acc = lr_acc

print("\n" + "=" * 60)
print("BEST MODEL")
print("=" * 60)

print(f"Model    : {best_name}")
print(f"Accuracy : {round(best_acc*100,2)}%")

# ==========================================================
# SAVE MODEL
# ==========================================================

joblib.dump(
    best_model,
    "kait_model.pkl"
)

print("\nSaved:")
print("kait_model.pkl")

# ==========================================================
# FEATURE IMPORTANCE
# ==========================================================

print("\nFeature Importance")

if best_name == "Random Forest":

    importance = pd.DataFrame({
        "feature": feature_columns,
        "importance": best_model.feature_importances_
    })

    importance = importance.sort_values(
        by="importance",
        ascending=False
    )

    print(importance)

# ==========================================================
# TODAY PREDICTION
# ==========================================================

latest = df[feature_columns].iloc[-1:]

prediction = best_model.predict(latest)[0]

probability = best_model.predict_proba(latest)[0]

confidence = round(
    max(probability) * 100,
    2
)

signal = (
    "BULLISH"
    if prediction == 1
    else "BEARISH"
)

print("\n" + "=" * 60)
print("TODAY PREDICTION")
print("=" * 60)

print(f"Signal     : {signal}")
print(f"Confidence : {confidence}%")

print("\n✅ Unified ML Engine Complete")