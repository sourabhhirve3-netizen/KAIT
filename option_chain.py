import os
from kiteconnect import KiteConnect
from dotenv import load_dotenv
import pandas as pd

load_dotenv()

api_key = os.getenv("KITE_API_KEY")

# Load access token
with open("access_token.txt", "r") as f:
    access_token = f.read().strip()

kite = KiteConnect(api_key=api_key)
kite.set_access_token(access_token)

# ─────────────────────────────────────────
# STEP 1 — Get all Nifty option instruments
# ─────────────────────────────────────────
print("⏳ Fetching instruments list (this takes a few seconds)...")
instruments = kite.instruments("NFO")  # NFO = NSE Futures & Options

# Convert to a pandas dataframe (like an Excel table)
df = pd.DataFrame(instruments)

# Filter only NIFTY options (not BANKNIFTY, not futures)
nifty_options = df[
    (df["name"] == "NIFTY") &
    (df["instrument_type"].isin(["CE", "PE"]))
].copy()

# ─────────────────────────────────────────
# STEP 2 — Pick the nearest expiry
# ─────────────────────────────────────────
nearest_expiry = sorted(nifty_options["expiry"].unique())[0]
print(f"\n📅 Nearest Expiry: {nearest_expiry}")

# Filter for nearest expiry only
nifty_options = nifty_options[nifty_options["expiry"] == nearest_expiry]

# ─────────────────────────────────────────
# STEP 3 — Get live Nifty price
# ─────────────────────────────────────────
nifty_data = kite.quote("NSE:NIFTY 50")
spot_price = nifty_data["NSE:NIFTY 50"]["last_price"]
print(f"📈 Nifty Spot Price: ₹{spot_price}")

# ─────────────────────────────────────────
# STEP 4 — Pick strikes near ATM (At The Money)
# ATM = strike closest to current Nifty price
# ─────────────────────────────────────────
atm_strike = round(spot_price / 50) * 50  # Nifty strikes are in multiples of 50
print(f"🎯 ATM Strike: {atm_strike}")

# Get 5 strikes above and below ATM
strike_range = [atm_strike + (i * 50) for i in range(-5, 6)]

# Filter option chain for those strikes only
chain = nifty_options[nifty_options["strike"].isin(strike_range)]

# ─────────────────────────────────────────
# STEP 5 — Fetch live prices for all strikes
# ─────────────────────────────────────────
# Build list of trading symbols to fetch quotes for
symbols = ["NFO:" + s for s in chain["tradingsymbol"].tolist()]

print(f"\n⏳ Fetching live option prices...")
quotes = kite.quote(symbols)

# ─────────────────────────────────────────
# STEP 6 — Build a clean option chain table
# ─────────────────────────────────────────
rows = []
for _, row in chain.iterrows():
    symbol = "NFO:" + row["tradingsymbol"]
    if symbol in quotes:
        q = quotes[symbol]
        rows.append({
            "Strike":       row["strike"],
            "Type":         row["instrument_type"],  # CE or PE
            "expiry":       str(nearest_expiry),      # ← FIXED: expiry now saved to CSV
            "LTP":          q["last_price"],
            "OI":           q["oi"],
            "Volume":       q["volume"],
            "Bid":          q["depth"]["buy"][0]["price"] if q["depth"]["buy"] else 0,
            "Ask":          q["depth"]["sell"][0]["price"] if q["depth"]["sell"] else 0,
        })

result = pd.DataFrame(rows)

# Separate CE and PE
ce_chain = result[result["Type"] == "CE"].sort_values("Strike")
pe_chain = result[result["Type"] == "PE"].sort_values("Strike")

# ─────────────────────────────────────────
# STEP 7 — Print the option chain
# ─────────────────────────────────────────
print("\n" + "="*60)
print(f"  NIFTY OPTION CHAIN — expiry: {nearest_expiry}")
print(f"  Spot: ₹{spot_price}  |  ATM Strike: {atm_strike}")
print("="*60)

print("\n📗 CALL OPTIONS (CE):")
print(ce_chain.to_string(index=False))

print("\n📕 PUT OPTIONS (PE):")
print(pe_chain.to_string(index=False))

# Save to CSV for later use
result.to_csv("option_chain.csv", index=False)
print("\n✅ Option chain saved to option_chain.csv")