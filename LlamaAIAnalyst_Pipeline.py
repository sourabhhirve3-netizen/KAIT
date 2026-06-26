import subprocess
import sys
import os

from kiteconnect import KiteConnect
from dotenv import load_dotenv

load_dotenv()

print("=" * 60)
print("KAIT — Daily Analysis Pipeline")
print("=" * 60)


def kite_connected():

    try:
        if not os.path.exists("access_token.txt"):
            return False

        with open("access_token.txt") as f:
            access_token = f.read().strip()

        kite = KiteConnect(
            api_key=os.getenv("KITE_API_KEY")
        )

        kite.set_access_token(access_token)

        # Simple API call to validate token
        kite.profile()

        return True

    except Exception:
        return False


# --------------------------------------------------
# LOGIN CHECK
# --------------------------------------------------

if kite_connected():

    print("\n✅ Kite already connected")
    print("Skipping login.py")

else:

    print("\n⚠ Session expired")
    print("Running login.py")

    result = subprocess.run(
        [sys.executable, "login.py"]
    )

    if result.returncode != 0:
        print("\n❌ Login failed")
        sys.exit()


# --------------------------------------------------
# MAIN PIPELINE
# --------------------------------------------------

pipeline = [
    "option_chain.py",
    "features.py",
    "signal_engine.py",
    "risk_engine.py",
    "llamaAI_analyst.py"
]

for script in pipeline:

    print(f"\n▶ Running: {script}")

    result = subprocess.run(
        [sys.executable, script]
    )

    if result.returncode != 0:
        print(f"\n❌ Error in {script}")
        print("Pipeline stopped.")
        break

else:

    print("\n" + "=" * 60)
    print("✅ DAILY ANALYSIS COMPLETE")
    print("=" * 60)