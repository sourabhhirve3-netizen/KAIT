import json

# ============================================================
# LOAD FEATURES
# ============================================================

def load_features():

    with open("features.json", "r") as f:
        return json.load(f)


# ============================================================
# DETERMINE MARKET REGIME
# ============================================================

def build_trend(features):

    score = 0
    reasons = []

    pcr = features["pcr"]
    iv_avg = features["iv_average"]
    max_pain_dist = abs(features["distance_from_max_pain"])
    support_dist = features["support_distance_pct"]
    resistance_dist = features["resistance_distance_pct"]
    iv_skew = features["iv_skew"]
    oi_diff = features["oi_difference_pct"]

    # --------------------------------------------------------
    # PCR
    # --------------------------------------------------------

    if pcr > 1.20:
        score += 2
        reasons.append("High PCR indicates bullish sentiment.")

    elif pcr < 0.80:
        score -= 2
        reasons.append("Low PCR indicates bearish sentiment.")

    else:
        reasons.append("PCR is neutral.")

    # --------------------------------------------------------
    # OI Difference
    # --------------------------------------------------------

    if oi_diff > 15:
        score += 2
        reasons.append("Put Open Interest dominates.")

    elif oi_diff < -15:
        score -= 2
        reasons.append("Call Open Interest dominates.")

    else:
        reasons.append("Open Interest is balanced.")

    # --------------------------------------------------------
    # Max Pain
    # --------------------------------------------------------

    if max_pain_dist < 50:
        reasons.append("Spot is trading near Max Pain.")

    elif features["distance_from_max_pain"] > 0:
        score += 1
        reasons.append("Spot trading above Max Pain.")

    else:
        score -= 1
        reasons.append("Spot trading below Max Pain.")

    # --------------------------------------------------------
    # Support
    # --------------------------------------------------------

    if support_dist < 0.30:
        score += 1
        reasons.append("Spot near support.")

    # --------------------------------------------------------
    # Resistance
    # --------------------------------------------------------

    if resistance_dist < 0.30:
        score -= 1
        reasons.append("Spot near resistance.")

    # --------------------------------------------------------
    # IV Skew
    # --------------------------------------------------------

    if iv_skew > 2:
        score -= 1
        reasons.append("PE IV higher than CE IV (fear).")

    elif iv_skew < -2:
        score += 1
        reasons.append("CE IV higher than PE IV.")

    # --------------------------------------------------------
    # Determine Regime
    # --------------------------------------------------------

    if score >= 3:

        regime = "BULLISH"

    elif score <= -3:

        regime = "BEARISH"

    else:

        regime = "RANGEBOUND"

    return {

        "trend": "RANGEBOUND",
        "trend_score": score,
        "reasons": reasons

    }
# ============================================================
# VOLATILITY ENGINE
# ============================================================

def build_volatility(features):

    iv = features["iv_average"]

    if iv < 12:

        return {
            "volatility": "LOW_VOL",
            "volatility_score": 80
        }

    elif iv < 18:

        return {
            "volatility": "NORMAL_VOL",
            "volatility_score": 60
        }

    elif iv < 25:

        return {
            "volatility": "HIGH_VOL",
            "volatility_score": 40
        }

    else:

        return {
            "volatility": "EXPLOSIVE_VOL",
            "volatility_score": 20
        }
# ============================================================
# CALCULATE CONFIDENCE
# ============================================================

def calculate_confidence(features, regime):

    confidence = 50

    pcr = features["pcr"]
    iv_avg = features["iv_average"]
    max_pain_dist = abs(features["distance_from_max_pain"])
    oi_diff = abs(features["oi_difference_pct"])

    # PCR

    if pcr > 1.20 or pcr < 0.80:
        confidence += 10

    # Strong OI imbalance

    if oi_diff > 20:
        confidence += 10

    elif oi_diff > 10:
        confidence += 5

    # Spot away from Max Pain

    if max_pain_dist > 150:
        confidence += 10

    elif max_pain_dist < 25:
        confidence -= 5

    # Low IV usually means rangebound

    if regime["trend"] == "RANGEBOUND":

        if iv_avg < 12:
            confidence += 10

        elif iv_avg > 18:
            confidence -= 5

    else:

        if iv_avg > 18:
            confidence += 5

    confidence = max(0, min(100, confidence))

    return confidence


# ============================================================
# MARKET SCORE (0-100)
# ============================================================

def calculate_market_score(features):

    score = 50

    score += features["oi_difference_pct"] * 0.50

    score += (features["pcr"] - 1.0) * 30

    score -= abs(features["distance_from_max_pain"]) * 0.05

    score = max(0, min(100, score))

    return round(score, 1)


# ============================================================
# BUILD REASONS
# ============================================================

def build_reasons(features, regime):

    reasons = list(regime["reasons"])

    if features["iv_average"] < 12:

        reasons.append(
            "Low implied volatility suggests a calm market."
        )

    elif features["iv_average"] > 18:

        reasons.append(
            "High implied volatility indicates aggressive positioning."
        )

    if abs(features["distance_from_max_pain"]) < 50:

        reasons.append(
            "Price is very close to Max Pain."
        )

    if features["support_distance_pct"] < 0.30:

        reasons.append(
            "Market is trading close to major support."
        )

    if features["resistance_distance_pct"] < 0.30:

        reasons.append(
            "Market is trading close to major resistance."
        )

    return reasons


# ============================================================
# BUILD SUMMARY
# ============================================================

def build_summary(regime):

    summary = []

    summary.append(
        f"Trend: {regime['trend']}"
    )

    summary.append(
        f"Confidence: {regime['confidence']}%"
    )

    summary.append(
        f"Market Score: {regime['market_score']}/100"
    )

    summary.append("")

    summary.append("Key Reasons:")

    for reason in regime["reasons"]:
        summary.append(f"• {reason}")

    return "\n".join(summary)

# ============================================================
# PRINT REPORT
# ============================================================

def print_report(regime):

    print("\n" + "=" * 60)
    print("KAIT — MARKET REGIME REPORT")
    print("=" * 60)

    print(f"\nTrend : {regime['trend']}")
    print(f"Volatility    : {regime['volatility']}")
    print(f"Confidence    : {regime['confidence']}%")
    print(f"Market Score  : {regime['market_score']}/100")

    print("\nReasons:")

    for reason in regime["reasons"]:
        print(f"  • {reason}")

    print("\nSummary:")
    print("-" * 60)
    print(regime["summary"])

    print("\n" + "=" * 60)


# ============================================================
# SAVE OUTPUT
# ============================================================

def save_regime(regime):

    with open("market_regime.json", "w") as f:
        json.dump(regime, f, indent=4)

    print("\n✅ Market regime saved to market_regime.json")


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    print("=" * 60)
    print("KAIT — Market Regime Engine")
    print("=" * 60)

    # Load today's features
    features = load_features()

    # Build regime
    regime = build_trend(features)

    # Volatility
    volatility = build_volatility(features)

    regime["volatility"] = volatility["volatility"]
    regime["volatility_score"] = volatility["volatility_score"]

    # Confidence
    regime["confidence"] = calculate_confidence(
        features,
        regime
    )

    # Market Score
    regime["market_score"] = calculate_market_score(
        features
    )

    # Reasons
    regime["reasons"] = build_reasons(
        features,
        regime
    )

    # Summary
    regime["summary"] = build_summary(
        regime
    )

    # Print Report
    print_report(regime)

    # Save JSON
    save_regime(regime)

    print("\n✅ Market Regime Analysis Complete")