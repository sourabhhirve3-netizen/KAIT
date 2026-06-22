import os
import json
import requests
from kiteconnect import KiteConnect
from dotenv import load_dotenv
import pandas as pd

load_dotenv()

api_key = os.getenv("KITE_API_KEY")

# ─────────────────────────────────────────
# STEP 1 — Load Kite & fetch fresh data
# ─────────────────────────────────────────
with open("access_token.txt", "r") as f:
    access_token = f.read().strip()

kite = KiteConnect(api_key=api_key)
kite.set_access_token(access_token)

# Fetch live Nifty price
nifty_data = kite.quote("NSE:NIFTY 50")
spot_price = nifty_data["NSE:NIFTY 50"]["last_price"]
atm_strike = round(spot_price / 50) * 50

# Load the option chain CSV we saved earlier
# (or re-fetch it fresh if you prefer)
chain = pd.read_csv("option_chain.csv")

# ─────────────────────────────────────────
# STEP 2 — Prepare a summary for the AI
# ─────────────────────────────────────────
ce_chain = chain[chain["Type"] == "CE"].sort_values("Strike")
pe_chain = chain[chain["Type"] == "PE"].sort_values("Strike")

# Find max OI strikes (support/resistance)
max_ce_oi_strike = ce_chain.loc[ce_chain["OI"].idxmax(), "Strike"]
max_pe_oi_strike = pe_chain.loc[pe_chain["OI"].idxmax(), "Strike"]

# PCR = Put-Call Ratio (market sentiment indicator)
total_ce_oi = ce_chain["OI"].sum()
total_pe_oi = pe_chain["OI"].sum()
pcr = round(total_pe_oi / total_ce_oi, 2)

# Build a compact summary to send to AI
option_summary = {
    "nifty_spot": spot_price,
    "atm_strike": atm_strike,
    "expiry": "2026-06-23",
    "pcr": pcr,
    "max_call_oi_strike": max_ce_oi_strike,
    "max_put_oi_strike": max_pe_oi_strike,
    "top_ce_strikes": ce_chain[["Strike","LTP","OI","Volume"]].to_dict(orient="records"),
    "top_pe_strikes": pe_chain[["Strike","LTP","OI","Volume"]].to_dict(orient="records"),
}

print(f"📊 PCR: {pcr} ({'Bullish' if pcr > 1 else 'Bearish'})")
print(f"🔴 Max CE OI (Resistance): {max_ce_oi_strike}")
print(f"🟢 Max PE OI (Support): {max_pe_oi_strike}")

# ─────────────────────────────────────────
# STEP 3 — Send to Claude AI for analysis
# ─────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

prompt = f"""
You are an expert Nifty options trader with 15 years of experience.
Analyze this real-time Nifty option chain data and give me:

1. MARKET SENTIMENT (Bullish / Bearish / Sideways)
2. KEY SUPPORT level (where big PUT OI is sitting)
3. KEY RESISTANCE level (where big CALL OI is sitting)
4. MAX PAIN strike (where most option buyers will lose)
5. TRADING SIGNAL — one specific trade recommendation with:
   - What to buy/sell (CE or PE, which strike)
   - Entry price range
   - Target
   - Stop Loss
   - Reason in simple words
6. RISK WARNING

Here is the live data:
{json.dumps(option_summary, indent=2)}

Be specific, concise, and practical. Format clearly with headers.
"""

print("\n🤖 Sending data to Claude AI for analysis...")

response = requests.post(
    "https://api.anthropic.com/v1/messages",
    headers={
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    },
    json={
        "model": "claude-sonnet-4-6",
        "max_tokens": 1000,
        "messages": [{"role": "user", "content": prompt}]
    }
)

ai_response = response.json()
analysis = ai_response["content"][0]["text"]

print("\n" + "="*60)
print("        🤖 AI TRADING ANALYSIS")
print("="*60)
print(analysis)
print("="*60)

# Save analysis to file
with open("ai_analysis.txt", "w") as f:
    f.write(f"Nifty Spot: {spot_price}\n\n")
    f.write(analysis)

print("\n✅ Analysis saved to ai_analysis.txt")