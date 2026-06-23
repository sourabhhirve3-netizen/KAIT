import os
from datetime import date

import pandas as pd
from kiteconnect import KiteConnect
from dotenv import load_dotenv
from config import DTE_MIN, DTE_MAX

load_dotenv()

# ─────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────

api_key = os.getenv("KITE_API_KEY")

with open("access_token.txt", "r") as f:
    access_token = f.read().strip()

kite = KiteConnect(api_key=api_key)
kite.set_access_token(access_token)

# ─────────────────────────────────────────
# STEP 1 — Get all Nifty option instruments
# ─────────────────────────────────────────

print("⏳ Fetching instruments list (this takes a few seconds)...")

instruments = kite.instruments("NFO")
df = pd.DataFrame(instruments)

nifty_options = df[
    (df["name"] == "NIFTY") &
    (df["instrument_type"].isin(["CE", "PE"]))
].copy()

if nifty_options.empty:
    print("❌ No NIFTY option instruments found.")
    exit()

# ─────────────────────────────────────────
# STEP 2 — Select  with DTE >= 3
# ─────────────────────────────────────────

today = date.today()
selected_expiry = None

print(f"\nToday's date: {today}")
print("\nAvailable expiries:")

for exp in sorted(nifty_options["expiry"].unique()):
    expiry_date = pd.to_datetime(exp).date()
    dte = (expiry_date - today).days
    print(f"  {expiry_date} → DTE: {dte}")

for exp in sorted(nifty_options["expiry"].unique()):

    expiry_date = pd.to_datetime(exp).date()
    dte = (expiry_date - today).days

    if DTE_MIN <= dte <= DTE_MAX:
        selected_expiry = exp
        break

if selected_expiry is None:

    available = sorted(nifty_options["expiry"].unique())

    selected_expiry = available[0]

    print(
        f"⚠️ No expiry found between {DTE_MIN} and {DTE_MAX} days."
    )
    print(f"⚠️ Falling back to nearest expiry: {selected_expiry}")

dte = (pd.to_datetime(selected_expiry).date() - today).days

print(f"\n📅 Selected Expiry : {selected_expiry} (DTE: {dte} days)")

nifty_options = nifty_options[
    nifty_options["expiry"] == selected_expiry
]

# ─────────────────────────────────────────
# STEP 3 — Get live Nifty price
# ─────────────────────────────────────────

nifty_data = kite.quote("NSE:NIFTY 50")
spot_price = nifty_data["NSE:NIFTY 50"]["last_price"]

print(f"📈 Nifty Spot Price : ₹{spot_price:,.2f}")

# ─────────────────────────────────────────
# STEP 4 — ATM strike + nearby range
# ─────────────────────────────────────────

atm_strike = round(spot_price / 50) * 50

print(f"🎯 ATM Strike       : {atm_strike}")

strike_range = [
    atm_strike + (i * 50)
    for i in range(-5, 6)
]

chain = nifty_options[
    nifty_options["strike"].isin(strike_range)
].copy()

if chain.empty:
    print("❌ No option contracts found around ATM strike.")
    exit()

# ─────────────────────────────────────────
# STEP 5 — Fetch live quotes (batched)
# ─────────────────────────────────────────

symbols = ["NFO:" + s for s in chain["tradingsymbol"].tolist()]

print("\n⏳ Fetching live option prices...")

quotes = {}
batch_size = 100

for i in range(0, len(symbols), batch_size):
    batch = symbols[i:i + batch_size]
    quotes.update(kite.quote(batch))

# ─────────────────────────────────────────
# STEP 6 — Build option chain
# ─────────────────────────────────────────

rows = []

for _, row in chain.iterrows():

    symbol = "NFO:" + row["tradingsymbol"]

    if symbol not in quotes:
        continue

    q = quotes[symbol]

    depth = q.get("depth", {})
    buy_depth = depth.get("buy", [])
    sell_depth = depth.get("sell", [])

    rows.append({
        "Strike": row["strike"],
        "Type": row["instrument_type"],

        # Metadata
        "expiry": str(selected_expiry),
        "SpotPrice": spot_price,
        "DTE": dte,
        "LotSize": row["lot_size"],

        # Real Zerodha trading symbol
        "TradingSymbol": row["tradingsymbol"],

        # Market data
        "LTP": q.get("last_price", 0) or 0,
        "OI": q.get("oi", 0) or 0,
        "Volume": q.get("volume", 0) or 0,

        # Bid / Ask
        "Bid": buy_depth[0]["price"] if buy_depth else 0,
        "Ask": sell_depth[0]["price"] if sell_depth else 0,
    })

result = pd.DataFrame(rows)

if result.empty:
    print("❌ Failed to fetch option quotes.")
    exit()

# ─────────────────────────────────────────
# STEP 7 — Validate ATM contracts exist
# ─────────────────────────────────────────

atm_check = result[result["Strike"] == atm_strike]

if len(atm_check) < 2:
    print("❌ ATM CE/PE data missing.")
    exit()

# ─────────────────────────────────────────
# STEP 8 — Split CE / PE views
# ─────────────────────────────────────────

ce_chain = (
    result[result["Type"] == "CE"]
    .sort_values("Strike")
)

pe_chain = (
    result[result["Type"] == "PE"]
    .sort_values("Strike")
)

# ─────────────────────────────────────────
# STEP 9 — Print output
# ─────────────────────────────────────────

print("\n" + "=" * 70)
print(f"  NIFTY OPTION CHAIN — Expiry: {selected_expiry} (DTE: {dte})")
print(f"  Spot: ₹{spot_price:,.2f} | ATM Strike: {atm_strike}")
print("=" * 70)

print("\n📗 CALL OPTIONS (CE):")
print(ce_chain.to_string(index=False))

print("\n📕 PUT OPTIONS (PE):")
print(pe_chain.to_string(index=False))

# ─────────────────────────────────────────
# STEP 10 — Save CSV
# ─────────────────────────────────────────

result.to_csv("option_chain.csv", index=False)

print("\n✅ Option chain saved to option_chain.csv")
print(f"✅ Saved {len(result)} option contracts")