# KAIT_ARCHITECTURE_DOCUMENT.md

# KAIT — Knowledge Augmented Intelligent Trader

Version: Phase 9F Complete (Unified ML Architecture)

Author: Sourabh Hirve

---

# 1. PROJECT VISION

KAIT (Knowledge Augmented Intelligent Trader) is an AI-powered market intelligence and trading research platform built for Indian index options trading using Zerodha Kite.

KAIT is not designed to be a simple indicator-based trading strategy.

The vision is to build a continuously learning market intelligence system capable of:

* Collecting historical market data
* Collecting option-chain data
* Engineering market structure features
* Building proprietary datasets
* Training machine learning models
* Producing AI-assisted market analysis
* Generating trading signals
* Managing risk
* Evolving into a semi-autonomous trading assistant

The most valuable asset of KAIT is not the code.

The most valuable asset is the growing historical intelligence database.

---

# 2. PROJECT GOAL

Build a proprietary trading intelligence platform that combines:

1. Statistical Learning
2. Options Analytics
3. Market Structure Analysis
4. Large Language Model Reasoning

The objective is to eventually create:

Market Data
↓
Market Intelligence
↓
Probabilistic Predictions
↓
Trade Recommendations
↓
Autonomous Trading Assistant

---

# 3. CURRENT STATUS

Current Phase:

Phase 9F Complete

Completed Systems:

✓ Zerodha Authentication

✓ Historical Data Collection

✓ SQLite Data Warehouse

✓ Option Chain Collection

✓ Feature Engineering Engine

✓ Feature Logger

✓ Historical Feature Builder

✓ Dataset Builder

✓ Unified ML Engine

✓ Signal Engine

✓ Risk Engine

✓ AI Analyst

✓ Database Explorer

---

# 4. HIGH LEVEL SYSTEM ARCHITECTURE

```
                Zerodha Kite
                       │
                       ▼
            historical_data.py
                       │
      ┌────────────────┴────────────────┐
      │                                 │
      ▼                                 ▼
```

nifty_candles                 option_chain_snapshots
│                                 │
└──────────────┬──────────────────┘
▼
features.py
│
▼
features.json
│
▼
feature_logger.py
│
▼
kait.db
│
┌──────────────────┼──────────────────┐
│                  │                  │
▼                  ▼                  ▼
historical_feature   AI Analysis      Future Models
│
▼
historical_features.csv
│
▼
dataset_builder.py
│
▼
training_dataset.csv
│
▼
unified_ml_engine.py
│
▼
kait_model.pkl

---

# 5. DATABASE ARCHITECTURE

Database:

kait.db

Primary Tables:

1. nifty_candles
2. features_log
3. option_chain_snapshots
4. paper_trades

---

# 6. TABLE: nifty_candles

Purpose:

Stores historical NIFTY daily candles.

Columns:

date
open
high
low
close
volume

Current Records:

244+

Used By:

* historical_feature.py
* future backtesting
* future ML models

---

# 7. TABLE: features_log

Purpose:

Stores daily market intelligence snapshots generated from option-chain analytics.

This is the most important table for future options-based machine learning.

Stored Features:

timestamp
spot_price
atm_strike
expiry
dte

pcr
sentiment

max_pain
distance_from_max_pain

support
resistance

atm_ce_iv
atm_pe_iv
iv_skew

ce_delta
ce_gamma
ce_theta
ce_vega

pe_delta
pe_gamma
pe_theta
pe_vega

total_ce_oi
total_pe_oi

ce_oi_concentration_pct
pe_oi_concentration_pct

support_distance_pct
resistance_distance_pct
max_pain_distance_pct

oi_ratio_top3
oi_difference_pct

iv_average
iv_regime

total_ce_volume
total_pe_volume

Purpose:

Future options-driven machine learning models.

---

# 8. TABLE: option_chain_snapshots

Purpose:

Stores raw option chain observations.

Current Data:

* Strike
* Option Type
* LTP
* OI
* Volume
* Bid
* Ask
* Expiry

Future Use Cases:

* OI Flow Analysis
* IV Surface Analysis
* Institutional Positioning
* Market Microstructure Research

---

# 9. TABLE: paper_trades

Purpose:

Stores simulated trades.

Future Uses:

* Backtesting
* Paper Trading
* Performance Analytics

Current Status:

Reserved for future phases.

---

# 10. FEATURE ENGINE

File:

features.py

Purpose:

Convert raw option chain data into structured market intelligence.

Generated Features:

Sentiment:

* PCR
* Bullish/Bearish/Neutral

Support & Resistance:

* Highest CE OI
* Highest PE OI

Max Pain:

* Writer Equilibrium Level

Volatility:

* ATM CE IV
* ATM PE IV
* IV Skew
* IV Average
* IV Regime

Greeks:

* Delta
* Gamma
* Theta
* Vega

Open Interest Analytics:

* Total CE OI
* Total PE OI
* OI Concentration
* OI Difference %

Distance Analytics:

* Support Distance %
* Resistance Distance %
* Max Pain Distance %

---

# 11. FEATURE LOGGER

File:

feature_logger.py

Purpose:

Automatically save features.json into SQLite.

Flow:

features.py
↓
features.json
↓
feature_logger.py
↓
features_log

Result:

Every market snapshot becomes permanent training data.

---

# 12. HISTORICAL FEATURE BUILDER

File:

historical_feature.py

Purpose:

Convert historical candle data into ML-ready features.

Generated Features:

return_1d
return_5d
return_10d
return_20d

ATR14

RSI14

Volatility20

Momentum20

SMA20

SMA50

Trend

Target Variables:

next_day_return

direction

Output:

historical_features.csv

Rows:

194+

---

# 13. DATASET BUILDER

File:

dataset_builder.py

Purpose:

Build final ML training dataset.

Input:

historical_features.csv

Output:

training_dataset.csv

Features:

return_5d
return_10d
ATR14
RSI14
Volatility20
Momentum20
Trend

Target:

direction

Purpose:

Feed Unified ML Engine.

---

# 14. UNIFIED ML ENGINE

File:

unified_ml_engine.py

Purpose:

Single machine learning engine replacing:

* market_predictor.py
* direction_predictor.py

Models:

1. Logistic Regression
2. Random Forest

Process:

Load Dataset
↓
Train Models
↓
Evaluate Accuracy
↓
Select Best Model
↓
Save Model

Output:

BULLISH / BEARISH

Confidence %

Current Accuracy:

≈ 51%

Current Limitation:

Only 194 historical observations available.

Expected Improvement:

Accuracy should increase as more data accumulates.

---

# 15. AI ANALYST

Files:

ai_analyst.py
llamaAI_analyst.py

Purpose:

Provide human-readable market interpretation.

Inputs:

features.json

signal_engine output

risk_engine output

Output:

Market Narrative

Trade Explanation

Risk Commentary

Reasoning

Example:

PCR neutral.
Max Pain near spot.
Low IV environment.
Range-bound conditions likely.

---

# 16. WHY AI ANALYST IS IMPORTANT

Current ML Dataset:

~194 observations

Current ML Accuracy:

~51%

Therefore:

The AI Analyst currently provides more reliable market interpretation than the ML model.

Reason:

The LLM has been trained on massive amounts of market-related information.

Current Recommended Decision Hierarchy:

1. AI Analyst
2. Signal Engine
3. Unified ML Engine

As KAIT collects more proprietary data, this ranking is expected to reverse.

---

# 17. SIGNAL ENGINE

Purpose:

Generate actionable trade signals.

Possible Outputs:

BUY CALL

BUY PUT

NO TRADE

Uses:

PCR

Support

Resistance

Max Pain

IV

OI Analysis

---

# 18. RISK ENGINE

Purpose:

Validate trade risk.

Controls:

Capital Allocation

Position Size

Daily Risk Limit

Example:

Capital = ₹100,000

Daily Risk = ₹2,000

Output:

APPROVED

REDUCE SIZE

NO TRADE

---

# 19. CURRENT DAILY EXECUTION FLOW

Morning / Market Preparation

1. historical_data.py

Creates:

* nifty_candles
* option_chain_snapshots
* feature snapshot

2. features.py

Creates:

features.json

3. feature_logger.py

Stores:

features_log

4. signal_engine.py

Generates signal

5. risk_engine.py

Validates risk

6. ai_analyst.py

Explains market

7. llamaAI_analyst.py

Provides advanced reasoning

8. unified_ml_engine.py

Provides statistical prediction

---

# 20. TRAINING PIPELINE FLOW

historical_data.py
↓
kait.db
↓
historical_feature.py
↓
historical_features.csv
↓
dataset_builder.py
↓
training_dataset.csv
↓
unified_ml_engine.py
↓
kait_model.pkl

---

# 21. DUAL INTELLIGENCE ARCHITECTURE

KAIT currently operates with two independent intelligence engines.

INTELLIGENCE ENGINE #1

Unified ML Engine

Answers:

"What happened historically when conditions looked like this?"

Strength:

Statistical pattern recognition.

---

INTELLIGENCE ENGINE #2

Llama AI Analyst

Answers:

"What does the current market structure imply?"

Strength:

Market reasoning and contextual analysis.

---

Future Goal:

Combine both engines.

ML Prediction
+
AI Reasoning
+
Signal Engine
+
Risk Engine

↓

Final Trade Decision

---

# 22. LONG TERM ROADMAP

Phase 10

Backtesting Framework

Phase 11

Paper Trading Engine

Phase 12

Live Trade Execution

Phase 13

AI Trade Journal

Phase 14

Self-Learning Feedback Loop

Phase 15

Autonomous Trading Assistant

---

# 23. LONG TERM OBJECTIVE

KAIT is evolving through four stages:

Stage 1

Rule-Based Trading Assistant

↓

Stage 2

Market Intelligence Platform

↓

Stage 3

Machine Learning Trading System

↓

Stage 4

AI-Powered Autonomous Trading Intelligence Platform

The core asset remains:

kait.db

Every feature snapshot collected increases the value of the system.

The database becomes smarter every day.

End of Document.


                  Zerodha
                     │
                     ▼
              option_chain.py
                     │
                     ▼
               option_chain.csv
                     │
                     ▼
                 features.py
                     │
                     ▼
               features.json
                     │
                     ▼
            feature_logger.py
                     │
                     ▼
                  kait.db
                     │
      ┌──────────────┼──────────────┐
      ▼              ▼              ▼
 historical     training       analytics
  features      dataset          tables
      │              │
      ▼              ▼
 historical_   unified_ml_
 feature.py     engine.py
                     │
                     ▼
                kait_model.pkl
                     │
                     ▼
             ML Prediction Layer
                     │
      ┌──────────────┼──────────────┐
      ▼              ▼              ▼
 signal_engine   risk_engine   ai_analyst
                     │
                     ▼
                Final Decision