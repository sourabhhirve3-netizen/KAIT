import os
import webbrowser
from kiteconnect import KiteConnect
from dotenv import load_dotenv

# Load your secret keys from .env file
load_dotenv()

api_key = os.getenv("KITE_API_KEY")
api_secret = os.getenv("KITE_API_SECRET")

# Create Kite connection
kite = KiteConnect(api_key=api_key)

# Step 1 — Open Zerodha login page in your browser
login_url = kite.login_url()
print("Opening Zerodha login page...")
print(f"If browser doesn't open, go to this URL manually:\n{login_url}\n")
webbrowser.open(login_url)

# Step 2 — After login, Zerodha will redirect you to a URL like:
# http://127.0.0.1:5000/callback?request_token=XXXXXXXX&action=login&status=success
# Copy the 'request_token' value from that URL and paste it below

request_token = input("Paste the request_token from the URL here: ")

# Step 3 — Generate access token
data = kite.generate_session(request_token, api_secret=api_secret)
access_token = data["access_token"]

# Save access token to a file for reuse
with open("access_token.txt", "w") as f:
    f.write(access_token)

print(f"\n✅ Login successful!")
print(f"Access token saved to access_token.txt")