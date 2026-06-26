"""
============================================================
KAIT — Market Profile Engine V2
Part 1 : Foundation + Indicator Scoring
============================================================
"""

import json
import os
from dataclasses import dataclass, asdict


# ==========================================================
# Banner
# ==========================================================

print("=" * 60)
print("KAIT — Market Profile Engine V2")
print("=" * 60)


# ==========================================================
# Files
# ==========================================================

FEATURES_FILE = "features.json"
OUTPUT_FILE = "market_profile.json"


# ==========================================================
# Load Features
# ==========================================================

if not os.path.exists(FEATURES_FILE):
    raise FileNotFoundError(
        "features.json not found.\nRun features.py first."
    )

with open(FEATURES_FILE, "r") as f:
    features = json.load(f)


# ==========================================================
# Indicator Score Object
# ==========================================================

@dataclass
class IndicatorScore:
    name: str
    score: float
    weight: float
    contribution: float
    reason: str


# ==========================================================
# Helper
# ==========================================================

def clamp(value, low=0, high=100):
    return max(low, min(high, value))


# ==========================================================
# Indicator Weights
# (Can be tuned later)
# ==========================================================

WEIGHTS = {

    "PCR": 0.15,

    "Open Interest": 0.20,

    "Max Pain": 0.10,

    "Support": 0.10,

    "Resistance": 0.10,

    "Volatility": 0.15,

    "Historical ML": 0.10,

    "LLM": 0.10

}


# ==========================================================
# PCR Score
# ==========================================================

def score_pcr(features):

    pcr = features["pcr"]

    if pcr >= 1.30:
        score = 90
        reason = "Strong bullish Put-Call Ratio."

    elif pcr >= 1.10:
        score = 75
        reason = "Moderately bullish Put-Call Ratio."

    elif pcr >= 0.90:
        score = 50
        reason = "Neutral Put-Call Ratio."

    elif pcr >= 0.70:
        score = 25
        reason = "Moderately bearish Put-Call Ratio."

    else:
        score = 10
        reason = "Strong bearish Put-Call Ratio."

    return IndicatorScore(
        name="PCR",
        score=score,
        weight=WEIGHTS["PCR"],
        contribution=0,
        reason=reason
    )


# ==========================================================
# Open Interest Score
# ==========================================================

def score_open_interest(features):

    diff = features["oi_difference_pct"]

    if diff >= 10:
        score = 85
        reason = "Put Open Interest dominates."

    elif diff >= 5:
        score = 70
        reason = "Put writers slightly stronger."

    elif diff >= -5:
        score = 50
        reason = "Open Interest is balanced."

    elif diff >= -10:
        score = 30
        reason = "Call writers slightly stronger."

    else:
        score = 15
        reason = "Call Open Interest dominates."

    return IndicatorScore(
        name="Open Interest",
        score=score,
        weight=WEIGHTS["Open Interest"],
        contribution=0,
        reason=reason
    )


# ==========================================================
# Max Pain Score
# ==========================================================

def score_max_pain(features):

    distance = abs(features["max_pain_distance_pct"])

    if distance <= 0.10:
        score = 40
        reason = "Price is pinned near Max Pain."

    elif distance <= 0.30:
        score = 60
        reason = "Price moving away from Max Pain."

    else:
        score = 80
        reason = "Price far from Max Pain."

    return IndicatorScore(
        name="Max Pain",
        score=score,
        weight=WEIGHTS["Max Pain"],
        contribution=0,
        reason=reason
    )


# ==========================================================
# Support Score
# ==========================================================

def score_support(features):

    distance = features["support_distance_pct"]

    if distance <= 0.20:
        score = 85
        reason = "Price trading near strong support."

    elif distance <= 0.60:
        score = 65
        reason = "Price moderately above support."

    else:
        score = 35
        reason = "Support is relatively far away."

    return IndicatorScore(
        name="Support",
        score=score,
        weight=WEIGHTS["Support"],
        contribution=0,
        reason=reason
    )


# ==========================================================
# Resistance Score
# ==========================================================

def score_resistance(features):

    distance = features["resistance_distance_pct"]

    if distance <= 0.20:
        score = 25
        reason = "Price is close to resistance."

    elif distance <= 0.60:
        score = 55
        reason = "Some room before resistance."

    else:
        score = 85
        reason = "Resistance is far away."

    return IndicatorScore(
        name="Resistance",
        score=score,
        weight=WEIGHTS["Resistance"],
        contribution=0,
        reason=reason
    )


# ==========================================================
# Volatility Score
# ==========================================================

def score_volatility(features):

    iv = features["iv_average"]

    if iv < 12:
        score = 80
        reason = "Low implied volatility."

    elif iv < 18:
        score = 60
        reason = "Moderate implied volatility."

    elif iv < 25:
        score = 40
        reason = "High implied volatility."

    else:
        score = 20
        reason = "Extremely high implied volatility."

    return IndicatorScore(
        name="Volatility",
        score=score,
        weight=WEIGHTS["Volatility"],
        contribution=0,
        reason=reason
    )


# ==========================================================
# Save Helper
# ==========================================================

def save_profile(profile):

    with open(OUTPUT_FILE, "w") as f:
        json.dump(profile, f, indent=4)


print("\n✅ Part 1 Loaded Successfully")
print("Next: Part 2 will calculate weighted scores.")

# ==========================================================
# Part 2 : Weighted Scoring Engine
# ==========================================================

def calculate_market_score():

    indicators = [

        score_pcr(features),

        score_open_interest(features),

        score_max_pain(features),

        score_support(features),

        score_resistance(features),

        score_volatility(features)

    ]

    total_score = 0

    for indicator in indicators:

        indicator.contribution = round(
            indicator.score * indicator.weight,
            2
        )

        total_score += indicator.contribution

    total_score = round(total_score, 2)

    return total_score, indicators


# ==========================================================
# Build Evidence Table
# ==========================================================

market_score, indicators = calculate_market_score()

print("\n" + "=" * 60)
print("KAIT — MARKET PROFILE V2")
print("=" * 60)

print("\nIndicator Scores")
print("-" * 60)

for ind in indicators:

    print(
        f"{ind.name:<18}"
        f"Score: {ind.score:>3}   "
        f"Weight: {int(ind.weight*100):>2}%   "
        f"Contribution: {ind.contribution:>5}"
    )

print("-" * 60)

print(f"Overall Market Score : {market_score}")


# ==========================================================
# Profile Dictionary
# ==========================================================

profile = {

    "market_score": market_score,

    "indicators": [

        asdict(ind)

        for ind in indicators

    ]

}


print("\nEvidence Summary")
print("-" * 60)

for ind in indicators:

    print(f"• {ind.reason}")

print("-" * 60)

print("\n✅ Part 2 Complete")
print("Next: Part 3 will interpret the market score.")

# ==========================================================
# Part 3 : Decision Engine
# ==========================================================

def determine_trend(score):
    """
    Determines the overall market trend based on
    the weighted market score.
    """

    if score >= 70:
        return "STRONGLY_BULLISH"

    elif score >= 60:
        return "BULLISH"

    elif score >= 45:
        return "RANGEBOUND"

    elif score >= 30:
        return "BEARISH"

    return "STRONGLY_BEARISH"


# ==========================================================
# Confidence Engine
# ==========================================================

def calculate_confidence(indicators):

    scores = [i.score for i in indicators]

    spread = max(scores) - min(scores)

    average = sum(scores) / len(scores)

    # If indicators agree with each other,
    # spread will be small.

    confidence = average - (spread * 0.30)

    confidence = clamp(confidence)

    return round(confidence, 1)


# ==========================================================
# Conviction Engine
# ==========================================================

def determine_conviction(confidence):

    if confidence >= 80:
        return "VERY_HIGH"

    elif confidence >= 70:
        return "HIGH"

    elif confidence >= 55:
        return "MEDIUM"

    elif confidence >= 40:
        return "LOW"

    return "VERY_LOW"


# ==========================================================
# Market State Engine
# ==========================================================

def determine_market_state(trend, volatility):

    if trend in ["STRONGLY_BULLISH", "BULLISH"]:

        if volatility == "LOW":
            return "TRENDING_BULL"

        elif volatility == "MEDIUM":
            return "HEALTHY_BULL"

        else:
            return "VOLATILE_BULL"

    elif trend in ["STRONGLY_BEARISH", "BEARISH"]:

        if volatility == "LOW":
            return "TRENDING_BEAR"

        elif volatility == "MEDIUM":
            return "HEALTHY_BEAR"

        else:
            return "PANIC_SELLING"

    else:

        if volatility == "LOW":
            return "LOW_VOL_RANGE"

        elif volatility == "MEDIUM":
            return "NORMAL_RANGE"

        else:
            return "VOLATILE_RANGE"


# ==========================================================
# Volatility Label
# ==========================================================

iv = features["iv_average"]

if iv < 12:
    volatility = "LOW"

elif iv < 18:
    volatility = "MEDIUM"

else:
    volatility = "HIGH"


# ==========================================================
# Build Decision
# ==========================================================

trend = determine_trend(market_score)

confidence = calculate_confidence(indicators)

conviction = determine_conviction(confidence)

market_state = determine_market_state(
    trend,
    volatility
)


# ==========================================================
# Update Profile
# ==========================================================

profile["trend"] = trend

profile["confidence"] = confidence

profile["conviction"] = conviction

profile["volatility"] = volatility

profile["market_state"] = market_state


# ==========================================================
# Display
# ==========================================================

print("\n")
print("=" * 60)
print("MARKET DECISION")
print("=" * 60)

print(f"Trend        : {trend}")

print(f"Volatility   : {volatility}")

print(f"Confidence   : {confidence}%")

print(f"Conviction   : {conviction}")

print(f"Market State : {market_state}")

print("=" * 60)

print("\n✅ Part 3 Complete")
print("Next: Part 4 will calculate probabilities using the weighted score.")

# ==========================================================
# Part 4 : Probability Engine
# ==========================================================

def calculate_probabilities(
        market_score,
        confidence,
        trend
):

    # ----------------------------------------------
    # Strong Bullish
    # ----------------------------------------------

    if trend == "STRONGLY_BULLISH":

        bullish = min(95, market_score + 15)

        bearish = max(2, 100 - bullish - 5)

        neutral = 100 - bullish - bearish

    # ----------------------------------------------
    # Bullish
    # ----------------------------------------------

    elif trend == "BULLISH":

        bullish = market_score

        bearish = max(5, 100 - bullish - 20)

        neutral = 100 - bullish - bearish

    # ----------------------------------------------
    # Rangebound
    # ----------------------------------------------

    elif trend == "RANGEBOUND":

        neutral = confidence

        remaining = 100 - neutral

        bullish = round(remaining / 2)

        bearish = 100 - bullish - neutral

    # ----------------------------------------------
    # Bearish
    # ----------------------------------------------

    elif trend == "BEARISH":

        bearish = 100 - market_score

        bullish = max(5, 100 - bearish - 20)

        neutral = 100 - bullish - bearish

    # ----------------------------------------------
    # Strong Bearish
    # ----------------------------------------------

    else:

        bearish = min(95, (100 - market_score) + 15)

        bullish = max(2, 100 - bearish - 5)

        neutral = 100 - bullish - bearish

    return (
        round(bullish),
        round(bearish),
        round(neutral)
    )


# ==========================================================
# Reliability Engine
# ==========================================================

def calculate_reliability(
        confidence,
        indicators
):

    scores = [i.score for i in indicators]

    spread = max(scores) - min(scores)

    reliability = confidence - (spread * 0.15)

    reliability = clamp(reliability)

    return round(reliability, 1)


# ==========================================================
# Calculate
# ==========================================================

bullish_probability, \
bearish_probability, \
neutral_probability = calculate_probabilities(

    market_score,

    confidence,

    trend

)

reliability = calculate_reliability(

    confidence,

    indicators

)


# ==========================================================
# Update Profile
# ==========================================================

profile["bullish_probability"] = bullish_probability

profile["bearish_probability"] = bearish_probability

profile["neutral_probability"] = neutral_probability

profile["reliability"] = reliability


# ==========================================================
# Display
# ==========================================================

print()

print("=" * 60)

print("PROBABILITY ENGINE")

print("=" * 60)

print(f"Bullish Probability : {bullish_probability}%")

print(f"Bearish Probability : {bearish_probability}%")

print(f"Neutral Probability : {neutral_probability}%")

print()

print(f"Reliability         : {reliability}%")

print("=" * 60)

print("\n✅ Part 4 Complete")

print("Next: Part 5 will generate the final professional report.")

# ==========================================================
# Part 5 : Final Report & Save
# ==========================================================

profile["timestamp"] = features["timestamp"]
profile["spot_price"] = features["spot_price"]
profile["atm_strike"] = features["atm_strike"]
profile["expiry"] = features["expiry"]
profile["dte"] = features["dte"]

profile["support"] = features["support"]
profile["resistance"] = features["resistance"]
profile["max_pain"] = features["max_pain"]

profile["pcr"] = features["pcr"]
profile["iv_average"] = features["iv_average"]
profile["oi_difference_pct"] = features["oi_difference_pct"]


# ==========================================================
# Save JSON
# ==========================================================

save_profile(profile)


# ==========================================================
# Professional Report
# ==========================================================

print()
print("=" * 70)
print("KAIT — MARKET PROFILE V2")
print("=" * 70)

print()
print("MARKET SUMMARY")
print("-" * 70)

print(f"Spot Price       : {profile['spot_price']}")
print(f"ATM Strike       : {profile['atm_strike']}")
print(f"Expiry           : {profile['expiry']}")
print(f"DTE              : {profile['dte']}")

print()

print(f"Trend            : {profile['trend']}")
print(f"Volatility       : {profile['volatility']}")
print(f"Confidence       : {profile['confidence']}%")
print(f"Conviction       : {profile['conviction']}")
print(f"Market State     : {profile['market_state']}")

print()

print(f"Market Score     : {profile['market_score']}")

print()
print("PROBABILITIES")
print("-" * 70)

print(f"Bullish          : {profile['bullish_probability']}%")
print(f"Bearish          : {profile['bearish_probability']}%")
print(f"Neutral          : {profile['neutral_probability']}%")
print(f"Reliability      : {profile['reliability']}%")

print()

print("KEY MARKET LEVELS")
print("-" * 70)

print(f"Support          : {profile['support']}")
print(f"Resistance       : {profile['resistance']}")
print(f"Max Pain         : {profile['max_pain']}")

print()

print("INDICATOR BREAKDOWN")
print("-" * 70)

for indicator in profile["indicators"]:

    print()

    print(f"{indicator['name']}")

    print(f"  Score        : {indicator['score']}")

    print(f"  Weight       : {indicator['weight']*100:.0f}%")

    print(f"  Contribution : {indicator['contribution']}")

    print(f"  Reason       : {indicator['reason']}")

print()
print("=" * 70)

print("✅ Market Profile saved to market_profile.json")

print("✅ Market Profile Engine V2 Complete")

print("=" * 70)