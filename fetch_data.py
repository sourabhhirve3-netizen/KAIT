import os
from kiteconnect import KiteConnect
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("KITE_API_KEY")

# Read the saved access token
with open("access_token.txt", "r") as f:
    access_token = f.read().strip()

# Connect to Kite
kite = KiteConnect(api_key=api_key)
kite.set_access_token(access_token)

# ✅ Fetch live Nifty 50 price
nifty_data = kite.quote("NSE:NIFTY 50")
nifty_price = nifty_data["NSE:NIFTY 50"]["last_price"]

print(f"📈 Nifty 50 Live Price: ₹{nifty_price}")

# ✅ Fetch your profile (just to confirm connection works)
profile = kite.profile()
print(f"👤 Logged in as: {profile['user_name']}")