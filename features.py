import pandas as pd
import numpy as np
from scipy.stats import norm
from datetime import datetime, date
import math
import json
import os
from kiteconnect import KiteConnect
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────────────────────
# BLACK-SCHOLES OPTION PRICE
# ─────────────────────────────────────────────────────────────
def black_scholes_price(S, K, T, r, sigma, option_type='CE'):
    """Calculate theoretical option price using Black-Scholes."""
    if T <= 0 or sigma <= 0:
        return 0
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    if option_type == 'CE':
        return S * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)
    else:
        return K * math.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)


# ─────────────────────────────────────────────────────────────
# IMPLIED VOLATILITY CALCULATOR (Binary Search)
# ─────────────────────────────────────────────────────────────
def calculate_iv(market_price, S, K, T, r=0.065, option_type='CE'):
    """
    Find the IV that makes Black-Scholes price match market price.
    Uses binary search between 1% and 300%.
    Returns IV as a percentage (e.g. 14.5 means 14.5%).
    """
    if market_price <= 0 or T <= 0:
        return 0.0

    low, high = 0.01, 3.0
    mid = 0.15  # starting guess

    for _ in range(200):
        mid = (low + high) / 2
        price = black_scholes_price(S, K, T, r, mid, option_type)
        diff = price - market_price
        if abs(diff) < 0.01:
            break
        if diff < 0:
            low = mid
        else:
            high = mid

    return round(mid * 100, 2)


# ─────────────────────────────────────────────────────────────
# GREEKS CALCULATOR
# ─────────────────────────────────────────────────────────────
def calculate_greeks(S, K, T, r, iv_percent, option_type='CE'):
    """
    Calculate Delta, Gamma, Theta, Vega for an option.
    iv_percent: IV as percentage (e.g. 14.5)
    """
    if T <= 0 or iv_percent <= 0:
        return {'delta': 0, 'gamma': 0, 'theta': 0, 'vega': 0}

    sigma = iv_percent / 100  # convert to decimal
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)

    # Delta: how much option moves per Re.1 move in Nifty
    if option_type == 'CE':
        delta = norm.cdf(d1)
    else:
        delta = norm.cdf(d1) - 1

    # Gamma: rate of change of delta
    gamma = norm.pdf(d1) / (S * sigma * math.sqrt(T))

    # Theta: daily time decay (divided by 365)
    if option_type == 'CE':
        theta = (-(S * norm.pdf(d1) * sigma) / (2 * math.sqrt(T))
                 - r * K * math.exp(-r * T) * norm.cdf(d2)) / 365
    else:
        theta = (-(S * norm.pdf(d1) * sigma) / (2 * math.sqrt(T))
                 + r * K * math.exp(-r * T) * norm.cdf(-d2)) / 365

    # Vega: sensitivity to 1% change in IV
    vega = S * norm.pdf(d1) * math.sqrt(T) / 100

    return {
        'delta': round(delta, 4),
        'gamma': round(gamma, 6),
        'theta': round(theta, 2),
        'vega':  round(vega, 2)
    }


# ─────────────────────────────────────────────────────────────
# MAX PAIN CALCULATOR
# ─────────────────────────────────────────────────────────────
def calculate_max_pain(chain_df):
    """
    Max Pain = strike price where total monetary loss for option buyers is highest.
    This is where the market tends to close on expiry.
    """
    strikes = sorted(chain_df['Strike'].unique())
    pain = {}

    for expiry_price in strikes:
        total_loss = 0
        for _, row in chain_df.iterrows():
            if row['Type'] == 'CE':
                # CE buyer loses if expiry price < strike
                loss = max(0, expiry_price - row['Strike']) * row['OI']
            else:
                # PE buyer loses if expiry price > strike
                loss = max(0, row['Strike'] - expiry_price) * row['OI']
            total_loss += loss
        pain[expiry_price] = total_loss

    return min(pain, key=pain.get)


# ─────────────────────────────────────────────────────────────
# MAIN FEATURE ENGINE
# ─────────────────────────────────────────────────────────────
def calculate_features(chain_df, spot_price, expiry_date):
    """
    Takes the option chain dataframe and spot price.
    Returns a dictionary of all calculated features.
    """

    # Time to expiry
    today = date.today()
    if isinstance(expiry_date, str):
        expiry_date = date.fromisoformat(str(expiry_date)[:10])
    dte = max((expiry_date - today).days, 0)
    T = max(dte / 365, 0.0001)
    r = 0.065  # RBI repo rate approx

    ce = chain_df[chain_df['Type'] == 'CE'].copy()
    pe = chain_df[chain_df['Type'] == 'PE'].copy()

    # ── PCR ──────────────────────────────────────────────────
    total_ce_oi = ce['OI'].sum()
    total_pe_oi = pe['OI'].sum()
    pcr = round(total_pe_oi / total_ce_oi, 3) if total_ce_oi > 0 else 0

    if pcr >= 1.2:
        sentiment = 'Bullish'
    elif pcr <= 0.8:
        sentiment = 'Bearish'
    else:
        sentiment = 'Neutral'

    # ── Support & Resistance ─────────────────────────────────
    resistance = float(ce.loc[ce['OI'].idxmax(), 'Strike'])
    support    = float(pe.loc[pe['OI'].idxmax(), 'Strike'])

    # ── Max Pain ─────────────────────────────────────────────
    max_pain = calculate_max_pain(chain_df)

    # ── ATM Strike ───────────────────────────────────────────
    atm = round(spot_price / 50) * 50

    # ── IV and Greeks for ATM CE ─────────────────────────────
    atm_ce_row = ce[ce['Strike'] == atm]
    atm_pe_row = pe[pe['Strike'] == atm]

    atm_ce_iv, atm_pe_iv = 0.0, 0.0
    ce_greeks = {'delta': 0, 'gamma': 0, 'theta': 0, 'vega': 0}
    pe_greeks = {'delta': 0, 'gamma': 0, 'theta': 0, 'vega': 0}

    if not atm_ce_row.empty:
        ltp = atm_ce_row.iloc[0]['LTP']
        if ltp > 0:
            atm_ce_iv = calculate_iv(ltp, spot_price, atm, T, r, 'CE')
            ce_greeks = calculate_greeks(spot_price, atm, T, r, atm_ce_iv, 'CE')

    if not atm_pe_row.empty:
        ltp = atm_pe_row.iloc[0]['LTP']
        if ltp > 0:
            atm_pe_iv = calculate_iv(ltp, spot_price, atm, T, r, 'PE')
            pe_greeks = calculate_greeks(spot_price, atm, T, r, atm_pe_iv, 'PE')

    # ── IV Skew ──────────────────────────────────────────────
    # Positive skew = PE more expensive than CE = market fears downside
    iv_skew = round(atm_pe_iv - atm_ce_iv, 2)

    # ── OI Concentration ─────────────────────────────────────
    top3_ce_oi = ce.nlargest(3, 'OI')['OI'].sum()
    top3_pe_oi = pe.nlargest(3, 'OI')['OI'].sum()
    ce_conc = round(top3_ce_oi / total_ce_oi * 100, 1) if total_ce_oi > 0 else 0
    pe_conc = round(top3_pe_oi / total_pe_oi * 100, 1) if total_pe_oi > 0 else 0

    # ── Total Volume ─────────────────────────────────────────
    total_ce_vol = int(ce['Volume'].sum()) if 'Volume' in ce.columns else 0
    total_pe_vol = int(pe['Volume'].sum()) if 'Volume' in pe.columns else 0

    # ── Distance from Max Pain ───────────────────────────────
    distance_from_max_pain = round(spot_price - max_pain, 2)

    # ── Assemble Feature Dictionary ──────────────────────────
    features = {
        'timestamp':              datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'spot_price':             spot_price,
        'atm_strike':             atm,
        'expiry':                 str(expiry_date),
        'dte':                    dte,

        # Sentiment
        'pcr':                    pcr,
        'sentiment':              sentiment,

        # Levels
        'max_pain':               float(max_pain),
        'distance_from_max_pain': distance_from_max_pain,
        'support':                support,
        'resistance':             resistance,

        # Volatility
        'atm_ce_iv':              atm_ce_iv,
        'atm_pe_iv':              atm_pe_iv,
        'iv_skew':                iv_skew,
        'iv_skew_interpretation': 'Downside fear' if iv_skew > 2 else ('Upside demand' if iv_skew < -2 else 'Balanced'),

        # CE Greeks
        'ce_delta':               ce_greeks['delta'],
        'ce_gamma':               ce_greeks['gamma'],
        'ce_theta':               ce_greeks['theta'],
        'ce_vega':                ce_greeks['vega'],

        # PE Greeks
        'pe_delta':               pe_greeks['delta'],
        'pe_gamma':               pe_greeks['gamma'],
        'pe_theta':               pe_greeks['theta'],
        'pe_vega':                pe_greeks['vega'],

        # OI stats
        'total_ce_oi':            int(total_ce_oi),
        'total_pe_oi':            int(total_pe_oi),
        'ce_oi_concentration_pct': ce_conc,
        'pe_oi_concentration_pct': pe_conc,

        # Volume
        'total_ce_volume':        total_ce_vol,
        'total_pe_volume':        total_pe_vol,
    }

    return features


# ─────────────────────────────────────────────────────────────
# RUN STANDALONE
# ─────────────────────────────────────────────────────────────
if __name__ == '__main__':

    # Load Kite
    with open('access_token.txt') as f:
        token = f.read().strip()

    kite = KiteConnect(api_key=os.getenv('KITE_API_KEY'))
    kite.set_access_token(token)

    # Get live spot price
    nifty_data = kite.quote('NSE:NIFTY 50')
    spot = nifty_data['NSE:NIFTY 50']['last_price']

    # Load option chain
    chain = pd.read_csv('option_chain.csv')

    # Get expiry from chain or use default
    expiry = '2026-06-23'
    if 'expiry' in chain.columns:
        expiry = str(chain['expiry'].iloc[0])[:10]

    print(f"\nSpot Price : Rs. {spot}")
    print(f"Expiry     : {expiry}")
    print(f"Calculating features...\n")

    features = calculate_features(chain, spot, expiry)

    # ── Pretty Print ─────────────────────────────────────────
    print("=" * 58)
    print("       NIFTY FEATURE SNAPSHOT")
    print("=" * 58)

    sections = {
        "BASIC INFO":     ['timestamp', 'spot_price', 'atm_strike', 'expiry', 'dte'],
        "SENTIMENT":      ['pcr', 'sentiment'],
        "KEY LEVELS":     ['max_pain', 'distance_from_max_pain', 'support', 'resistance'],
        "VOLATILITY":     ['atm_ce_iv', 'atm_pe_iv', 'iv_skew', 'iv_skew_interpretation'],
        "CE GREEKS (ATM)":['ce_delta', 'ce_gamma', 'ce_theta', 'ce_vega'],
        "PE GREEKS (ATM)":['pe_delta', 'pe_gamma', 'pe_theta', 'pe_vega'],
        "OI STATS":       ['total_ce_oi', 'total_pe_oi', 'ce_oi_concentration_pct', 'pe_oi_concentration_pct'],
        "VOLUME":         ['total_ce_volume', 'total_pe_volume'],
    }

    for section, keys in sections.items():
        print(f"\n  [{section}]")
        for k in keys:
            print(f"    {k:<30} {features.get(k, 'N/A')}")

    print("\n" + "=" * 58)

    # Save to JSON
    with open('features.json', 'w') as f:
        json.dump(features, f, indent=2)

    print("\n✅ Features saved to features.json")
    print("   (This file will be used by signal_engine.py and ai_analyst.py)")