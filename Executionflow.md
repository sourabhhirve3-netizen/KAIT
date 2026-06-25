------------------------------------------------Flows and Information of each files----------------------------------------------------

----------------------------------------------------Flows-------------------------------------------------------

(Daily Analysis Flow, Execution Time: Around 10 or 11 in the morning): Login.py ---> option_chain.py ---> features.py ---> signal_engine.py ---> risk_engine.py ---> llamaAI_analyst.py

(Daily Data Collection Flow, Execution Time: After Market Close) : Login.py ---> option_chain.py ---> features.py (auto-runs feature_logger.py) ---> feature_logger.py ---> historical_data.py ---> check_db.py 

(Weekend Flow to align data): historical_feature.py ---> dataset_builder.py

(ML Training Flow, After collection of Enough Records): training_dataset.csv ---> unified_ml_engine.py

----------------------------------------------------Info---------------------------------------------------------

option_chain.py : Live NIFTY Option Chain --> option_chain.csv (Raw market structure data)

features.py : reads: option_chain.csv --> calculates parameters --> features.json(Convert raw option chain into structured intelligence)

feature_logger.py : reads: features.json --> writes: features_log inside : kait.db

historical_data.py : fetches : NIFTY Daily OHLC --> stores: nifty_candles and option_chain_snapshots

signal_engine.py : reads: features.json (BUY CALL, BUY PUT, NO TRADE) 

risk_engine.py : validates: Position sizing, Capital limits, Risk limits

llamaAI_analyst.py : reads: features.json, signal output, risk output --> analyze parameters --> Market Bias, Confidence, Trade Setup, Risk Commentary, AI Opinion.

historical_feature.py : --> historical_features.csv(containing parameters)

dataset_builder.py : --> Historical Indicators + Feature Log --> training_dataset.csv  

unified_ml_engine.py : --> training_dataset.csv --> kait_model.pkl


-----------------------------------------------------------RAW INFO------------------------------------------------------
option_chain.py
Creates:
option_chain.csv
Contains:
Strike
CE/PE
LTP
OI
Volume
Bid
Ask
Expiry
Purpose:
Raw market structure collection
--------------------------------
features.py
Reads:
option_chain.csv
Creates:
features.json
Calculates:
PCR
Sentiment
Support
Resistance
Max Pain
IV
IV Skew
IV Regime
Greeks
OI Concentration
OI Difference %
Distance Metrics
Also:
Automatically launches
feature_logger.py
feature_logger.py
Reads:
features.json
Writes:
features_log
inside:
kait.db
Purpose:
Daily feature history
--------------------------------
historical_data.py
Fetches:
NIFTY Daily OHLC
Stores:
nifty_candles
Also stores:
option_chain_snapshots
Purpose:
Historical database growth
--------------------------------
signal_engine.py
Reads:
features.json
Produces:
BUY CALL
BUY PUT
NO TRADE
Based on:
PCR
Support
Resistance
Max Pain
IV
risk_engine.py
Reads:
Signal
Capital
Risk Rules
Produces:
Position Size
Risk Validation
Trade Allowed?
--------------------------------
llamaAI_analyst.py
Reads:
features.json
signal output
risk output
Produces:
Market Bias
Confidence
Trade Setup
Risk Commentary
AI Opinion
Important
Today this is actually your strongest intelligence layer.
Why?
Because:
Unified ML Model
194 rows of training data
vs
LLM
Trained on millions of market discussions,
trading concepts,
options concepts,
risk management patterns.
So currently:
LLM Opinion > Unified ML Model
for discretionary analysis.
The ML model will become stronger only after:
100+
feature snapshots
200+
feature snapshots
500+
feature snapshots
1000+
feature snapshots
have accumulated.
--------------------------------
historical_feature.py
Creates:
historical_features.csv
Features:
Returns
ATR
RSI
Volatility
Momentum
Trend
SMA
Purpose:
Historical market behaviour dataset
--------------------------------
dataset_builder.py
Reads:
historical_features.csv
Creates:
training_dataset.csv
Purpose:
Master ML training dataset
--------------------------------
unified_ml_engine.py
Reads:
training_dataset.csv
Produces:
kait_model.pkl
Current accuracy:
~50-55%
which is normal because:
Only 194 rows
No historical options data yet