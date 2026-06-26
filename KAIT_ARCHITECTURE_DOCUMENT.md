# KAIT — Knowledge Augmented Intelligent Trader (KAIT)

Version: Phase 10 Architecture

Author: Sourabh Hirve

---

# 1. PROJECT OVERVIEW

KAIT (Knowledge Augmented Intelligent Trader) is an AI-powered options trading intelligence platform built for the Indian stock market using Zerodha Kite APIs.

The objective is **not** to create another indicator-based trading bot.

The objective is to build an intelligent trading assistant capable of:

• Understanding the market
• Learning from historical data
• Understanding option chain positioning
• Predicting future market behaviour
• Ranking multiple trading strategies
• Explaining WHY a trade should be taken
• Recommending WHEN to exit
• Continuously improving through data collection

Eventually KAIT should behave like an experienced derivatives trader rather than a rule-based script.

---

# 2. LONG TERM GOAL

Current Trading Bots

↓

Rule Based

↓

Fixed Strategy

↓

Binary Decision

↓

BUY / SELL

KAIT Goal

↓

Market Intelligence Engine

↓

AI Reasoning

↓

Machine Learning

↓

Strategy Ranking

↓

Trade Planning

↓

Exit Planning

↓

Continuous Learning

↓

Autonomous Trading Assistant

---

# 3. PROJECT PHILOSOPHY

KAIT has two independent brains.

Brain 1

Machine Learning

Learns only from collected historical data.

Brain 2

LLM (Llama)

Uses knowledge learned from millions of examples worldwide.

The final recommendation should combine BOTH.

Example

ML Confidence

68%

LLM Confidence

82%

Final Confidence

76%

This creates a much stronger decision engine.

---

# 4. CURRENT PROJECT STATUS

Completed

✓ Zerodha Login
✓ Historical Data Collection
✓ Live Option Chain Collection
✓ Feature Engineering
✓ Feature Logging
✓ Signal Engine
✓ Risk Engine
✓ AI Analyst (Llama)
✓ Historical Feature Builder
✓ Dataset Builder
✓ Unified ML Engine
✓ Database Explorer

---

# 5. DATABASE

Database

kait.db

Tables

nifty_candles

Historical OHLC

features_log

Daily market intelligence snapshots

option_chain_snapshots

Raw option chain

paper_trades

Future trade simulator

---

# 6. FILE STRUCTURE

## login.py

Purpose

Authenticate with Zerodha.

Creates

access_token.txt

Used By

All live market scripts.

---

## option_chain.py

Reads

Live Zerodha API

Produces

option_chain.csv

Contains

ATM strikes

CE

PE

LTP

OI

Volume

Bid

Ask

Expiry

Spot Price

Purpose

Raw market structure.

---

## features.py

Reads

option_chain.csv

Calculates

PCR

Support

Resistance

Max Pain

Implied Volatility

Greeks

IV Skew

OI Concentration

OI Difference

Distance Metrics

Outputs

features.json

Automatically launches

feature_logger.py

---

## feature_logger.py

Reads

features.json

Writes

features_log

inside

kait.db

Purpose

Build historical feature database.

---

## historical_data.py

Downloads

Historical NIFTY OHLC

Stores

nifty_candles

Purpose

Historical market database.

---

## signal_engine.py

Reads

features.json

Current Strategy

Rule Based

Checks

PCR

IV

Theta

DTE

OI

Max Pain

Produces

signal.json

Possible Outputs

BUY CALL

BUY PUT

NO TRADE

Future

Will become Strategy Ranking Engine.

---

## risk_engine.py

Reads

signal.json

Checks

Capital

Risk

Position Size

Loss Limits

Produces

risk_result.json

Purpose

Trade validation.

---

## llamaAI_analyst.py

Reads

features.json

signal.json

risk_result.json

Uses

Local Llama Model

Produces

ai_analysis.json

Provides

Market Bias

Trade Context

Risk Commentary

Plain English Explanation

Educational Notes

Future Role

Independent AI Market Expert.

---

## historical_feature.py

Reads

Historical OHLC

Calculates

ATR

RSI

Returns

Momentum

Moving Averages

Trend

Volatility

Produces

historical_features.csv

Purpose

Historical ML features.

---

## dataset_builder.py

Reads

historical_features.csv

Produces

training_dataset.csv

Purpose

ML training dataset.

---

## unified_ml_engine.py

Reads

training_dataset.csv

Trains

Logistic Regression

Random Forest

Chooses

Best Model

Outputs

kait_model.pkl

Purpose

Market prediction.

---

## check_db.py

Database explorer.

Displays

All tables

All rows

Purpose

Easy database inspection.

---

# 7. CURRENT EXECUTION FLOWS

## A. Daily Analysis Flow

Runs before entering the market.

login.py

↓

option_chain.py

↓

features.py

↓

feature_logger.py (automatic)

↓

signal_engine.py

↓

risk_engine.py

↓

llamaAI_analyst.py

Purpose

Generate today's market analysis.

---

## B. Daily Data Collection Flow

Runs after market close.

login.py

↓

option_chain.py

↓

features.py

↓

feature_logger.py

↓

historical_data.py

Purpose

Grow KAIT's historical database.

---

## C. Weekend ML Preparation

historical_feature.py

↓

dataset_builder.py

Purpose

Prepare fresh ML dataset.

---

## D. ML Training

training_dataset.csv

↓

unified_ml_engine.py

↓

kait_model.pkl

Purpose

Update prediction model.

---

# 8. CURRENT LIMITATION

Current ML only learns from OHLC derived indicators.

Examples

ATR

RSI

Momentum

Returns

Trend

It does NOT yet learn from option chain.

Therefore accuracy is limited.

---

# 9. FUTURE MACHINE LEARNING

Eventually the dataset should include

PCR

IV

IV Skew

OI Difference

OI Concentration

Greeks

Max Pain

Support

Resistance

Distance Metrics

Volume

Historical Returns

Momentum

Volatility

ATR

RSI

Trend

This will significantly improve prediction quality.

---

# 10. FUTURE SIGNAL ENGINE

Current

One recommendation.

Future

Rank multiple strategies.

Example

Today's Best Trades

1.

BUY CALL

Probability

82%

Risk

Medium

Reward

High

------------------

2.

Bull Call Spread

Probability

74%

Risk

Low

Reward

Medium

------------------

3.

Iron Condor

Probability

61%

Risk

Low

Reward

Medium

------------------

4.

BUY PUT

Probability

39%

Not Recommended

Instead of saying YES or NO, KAIT should explain WHY one strategy is superior.

---

# 11. TRADE PLANNER

Every recommendation should include

Entry

Stop Loss

Target 1

Target 2

Target 3

Expected Holding Time

Expected Move

Probability

Risk

Reward

Example

BUY CALL

Entry

₹120

Stop

₹90

Target 1

₹155

Target 2

₹180

Target 3

₹205

Exit

Tomorrow 2:45 PM

Probability

81%

---

# 12. EXIT ENGINE

KAIT should continuously monitor

Theta

IV

OI Shift

Price

Greeks

Support

Resistance

It should tell the user

Hold

Book Profit

Trail Stop

Exit Immediately

Instead of fixed exits.

---

# 13. AI + ML DECISION ENGINE

Final recommendation should combine

Machine Learning

+

LLM Reasoning

+

Rule Engine

Example

ML

BUY CALL

72%

LLM

Bull Call Spread

81%

Rules

BUY CALL

75%

Final Recommendation

Bull Call Spread

Confidence

79%

Reason

Lower risk

Better reward

Theta advantage

Support holding

IV favourable

---

# 14. LONG TERM ROADMAP

Phase 10

Improve data collection

Phase 11

Option Chain ML

Phase 12

Strategy Ranking

Phase 13

Trade Planner

Phase 14

Exit Engine

Phase 15

Paper Trading

Phase 16

Backtesting

Phase 17

Performance Analytics

Phase 18

Self Learning AI

Phase 19

Autonomous Trading Assistant

---

# 15. FINAL OBJECTIVE

KAIT should eventually behave like an experienced options trader.

Instead of answering

"Buy Call"

KAIT should answer

The market is mildly bullish.

Best strategy today is Bull Call Spread.

Expected probability: 81%

Expected move: +180 points.

Maximum risk: ₹2,450

Expected reward: ₹5,200

Recommended exit before tomorrow 2:45 PM unless IV expands beyond 18%.

Reason:

• Strong support at 24000

• PCR improving

• Max Pain shifting upward

• Positive OI build-up

• Low IV

• ML agrees

• LLM agrees

This transforms KAIT from a signal generator into an AI-powered trading intelligence platform.