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
    if T <= 0 or sigma <= 0:
        return 0

    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)

    if option_type == 'CE':
        return S * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)
    else:
        return K * math.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)


# ─────────────────────────────────────────────────────────────
# IMPLIED VOLATILITY CALCULATOR
# ─────────────────────────────────────────────────────────────

def calculate_iv(market_price, S, K, T, r=0.065, option_type='CE'):
    if market_price <= 0 or T <= 0:
        return 0.0

    low, high = 0.01, 3.0
    mid = 0.15

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
    if T <= 0 or iv_percent <= 0:
        return {'delta': 0, 'gamma': 0, 'theta': 0, 'vega': 0}

    sigma = iv_percent / 100

    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)

    if option_type == 'CE':
        delta = norm.cdf(d1)
    else:
        delta = norm.cdf(d1) - 1

    gamma = norm.pdf(d1) / (S * sigma * math.sqrt(T))

    if option_type == 'CE':
        theta = (
            -(S * norm.pdf(d1) * sigma) / (2 * math.sqrt(T))
            - r * K * math.exp(-r * T) * norm.cdf(d2)
        ) / 365
    else:
        theta = (
            -(S * norm.pdf(d1) * sigma) / (2 * math.sqrt(T))
            + r * K * math.exp(-r * T) * norm.cdf(-d2)
        ) / 365

    vega = S * norm.pdf(d1) * math.sqrt(T) / 100

    return {
        'delta': round(delta, 4),
        'gamma': round(gamma, 6),
        'theta': round(theta, 2),
        'vega': round(vega, 2)
    }


# ─────────────────────────────────────────────────────────────
# MAX PAIN CALCULATOR
# ─────────────────────────────────────────────────────────────

def calculate_max_pain(chain_df):
    strikes = sorted(chain_df['Strike'].unique())
    pain = {}

    for expiry_price in strikes:
        total_loss = 0

        for _, row in chain_df.iterrows():

            if row['Type'] == 'CE':
                loss = max(0, expiry_price - row['Strike']) * row['OI']
            else:
                loss = max(0, row['Strike'] - expiry_price) * row['OI']

            total_loss += loss

        pain[expiry_price] = total_loss

    return min(pain, key=pain.get)


# ─────────────────────────────────────────────────────────────
# MAIN FEATURE ENGINE
# ─────────────────────────────────────────────────────────────

def calculate_features(chain_df, spot_price, expiry_date):

    today = date.today()

    if isinstance(expiry_date, str):
        expiry_date = date.fromisoformat(str(expiry_date)[:10])

    dte = max((expiry_date - today).days, 0)
    T = max(dte / 365, 0.0001)
    r = 0.065

    lot_size = int(chain_df['LotSize'].iloc[0]) if 'LotSize' in chain_df.columns else 75

    ce = chain_df[chain_df['Type'] == 'CE'].copy()
    pe = chain_df[chain_df['Type'] == 'PE'].copy()

    total_ce_oi = ce['OI'].sum()
    total_pe_oi = pe['OI'].sum()

    pcr = round(total_pe_oi / total_ce_oi, 3) if total_ce_oi > 0 else 0

    if pcr >= 1.2:
        sentiment = 'Bullish'
    elif pcr <= 0.8:
        sentiment = 'Bearish'
    else:
        sentiment = 'Neutral'

    resistance = float(ce.loc[ce['OI'].idxmax(), 'Strike'])
    support = float(pe.loc[pe['OI'].idxmax(), 'Strike'])

    max_pain = calculate_max_pain(chain_df)

    atm = round(spot_price / 50) * 50

    # Filter ATM options for the selected expiry only

    if 'expiry' in ce.columns:
        atm_ce_row = ce[
            (ce['Strike'] == atm)
            & (ce['expiry'].astype(str).str[:10] == str(expiry_date))
            ]
    else:
        atm_ce_row = ce[ce['Strike'] == atm]

    if 'expiry' in pe.columns:
        atm_pe_row = pe[
            (pe['Strike'] == atm)
            & (pe['expiry'].astype(str).str[:10] == str(expiry_date))
            ]
    else:
        atm_pe_row = pe[pe['Strike'] == atm]

    atm_ce_iv = 0.0
    atm_pe_iv = 0.0

    atm_ce_ltp = 0.0
    atm_pe_ltp = 0.0

    atm_ce_symbol = ''
    atm_pe_symbol = ''

    ce_greeks = {'delta': 0, 'gamma': 0, 'theta': 0, 'vega': 0}
    pe_greeks = {'delta': 0, 'gamma': 0, 'theta': 0, 'vega': 0}

    if not atm_ce_row.empty:

        ce_row = atm_ce_row.iloc[0]
        print(
            f"Selected ATM CE: "
            f"{ce_row.get('TradingSymbol', '')} "
            f"| Expiry: {ce_row.get('expiry', '')}"
        )

        atm_ce_ltp = float(ce_row.get('LTP', 0))

        if 'TradingSymbol' in ce_row.index:
            atm_ce_symbol = str(ce_row['TradingSymbol'])
        elif 'tradingsymbol' in ce_row.index:
            atm_ce_symbol = str(ce_row['tradingsymbol'])
        elif 'Symbol' in ce_row.index:
            atm_ce_symbol = str(ce_row['Symbol'])

        if atm_ce_ltp > 0:
            atm_ce_iv = calculate_iv(
                atm_ce_ltp,
                spot_price,
                atm,
                T,
                r,
                'CE'
            )

            ce_greeks = calculate_greeks(
                spot_price,
                atm,
                T,
                r,
                atm_ce_iv,
                'CE'
            )

    if not atm_pe_row.empty:

        pe_row = atm_pe_row.iloc[0]
        print(
            f"Selected ATM PE: "
            f"{pe_row.get('TradingSymbol', '')} "
            f"| Expiry: {pe_row.get('expiry', '')}"
        )

        atm_pe_ltp = float(pe_row.get('LTP', 0))

        if 'TradingSymbol' in pe_row.index:
            atm_pe_symbol = str(pe_row['TradingSymbol'])
        elif 'tradingsymbol' in pe_row.index:
            atm_pe_symbol = str(pe_row['tradingsymbol'])
        elif 'Symbol' in pe_row.index:
            atm_pe_symbol = str(pe_row['Symbol'])

        if atm_pe_ltp > 0:
            atm_pe_iv = calculate_iv(
                atm_pe_ltp,
                spot_price,
                atm,
                T,
                r,
                'PE'
            )

            pe_greeks = calculate_greeks(
                spot_price,
                atm,
                T,
                r,
                atm_pe_iv,
                'PE'
            )

    iv_skew = round(atm_pe_iv - atm_ce_iv, 2)

    top3_ce_oi = ce.nlargest(3, 'OI')['OI'].sum()
    top3_pe_oi = pe.nlargest(3, 'OI')['OI'].sum()

    ce_conc = round(top3_ce_oi / total_ce_oi * 100, 1) if total_ce_oi > 0 else 0
    pe_conc = round(top3_pe_oi / total_pe_oi * 100, 1) if total_pe_oi > 0 else 0

    total_ce_vol = int(ce['Volume'].sum()) if 'Volume' in ce.columns else 0
    total_pe_vol = int(pe['Volume'].sum()) if 'Volume' in pe.columns else 0

    distance_from_max_pain = round(spot_price - max_pain, 2)

    # =====================================================
    # PREDICTIVE FEATURES FOR ML MODELS
    # =====================================================

    support_distance = round(
        ((spot_price - support) / spot_price) * 100,
        2
    )

    resistance_distance = round(
        ((resistance - spot_price) / spot_price) * 100,
        2
    )

    max_pain_distance_pct = round(
        abs(distance_from_max_pain) / spot_price * 100,
        2
    )

    oi_ratio_top3 = round(
        ce_conc / pe_conc,
        2
    ) if pe_conc > 0 else 1

    iv_average = round(
        (atm_ce_iv + atm_pe_iv) / 2,
        2
    )

    oi_difference_pct = round(
        ((total_pe_oi - total_ce_oi) / total_ce_oi) * 100,
        2
    ) if total_ce_oi > 0 else 0

    iv_regime = (
        "LOW"
        if iv_average < 12
        else "MODERATE"
        if iv_average <= 18
        else "HIGH"
    )

    features = {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'spot_price': spot_price,
        'atm_strike': atm,
        'expiry': str(expiry_date),
        'dte': dte,
        'lot_size': lot_size,

        'pcr': pcr,
        'sentiment': sentiment,

        'max_pain': float(max_pain),
        'distance_from_max_pain': distance_from_max_pain,
        'support': support,
        'resistance': resistance,

        'atm_ce_iv': atm_ce_iv,
        'atm_pe_iv': atm_pe_iv,

        'atm_ce_ltp': atm_ce_ltp,
        'atm_pe_ltp': atm_pe_ltp,

        'atm_ce_symbol': atm_ce_symbol,
        'atm_pe_symbol': atm_pe_symbol,

        'iv_skew': iv_skew,
        'iv_skew_interpretation': (
            'Downside fear'
            if iv_skew > 2
            else 'Upside demand'
            if iv_skew < -2
            else 'Balanced'
        ),

        'ce_delta': ce_greeks['delta'],
        'ce_gamma': ce_greeks['gamma'],
        'ce_theta': ce_greeks['theta'],
        'ce_vega': ce_greeks['vega'],

        'pe_delta': pe_greeks['delta'],
        'pe_gamma': pe_greeks['gamma'],
        'pe_theta': pe_greeks['theta'],
        'pe_vega': pe_greeks['vega'],

        'total_ce_oi': int(total_ce_oi),
        'total_pe_oi': int(total_pe_oi),

        'ce_oi_concentration_pct': ce_conc,
        'pe_oi_concentration_pct': pe_conc,

        'total_ce_volume': total_ce_vol,
        'total_pe_volume': total_pe_vol,
        # ML FEATURES

        'support_distance_pct': support_distance,
        'resistance_distance_pct': resistance_distance,
        'max_pain_distance_pct': max_pain_distance_pct,

        'oi_ratio_top3': oi_ratio_top3,

        'iv_average': iv_average,
        'iv_regime': iv_regime,
        'oi_difference_pct': oi_difference_pct
    }

    return features


# ─────────────────────────────────────────────────────────────
# RUN STANDALONE
# ─────────────────────────────────────────────────────────────

if __name__ == '__main__':

    with open('access_token.txt') as f:
        token = f.read().strip()

    kite = KiteConnect(api_key=os.getenv('KITE_API_KEY'))
    kite.set_access_token(token)

    nifty_data = kite.quote('NSE:NIFTY 50')
    spot = nifty_data['NSE:NIFTY 50']['last_price']

    chain = pd.read_csv('option_chain.csv')

    print("\nAvailable columns:")
    print(chain.columns.tolist())

    print("\nContracts for ATM Strike 24100:")
    print(
        chain[
            chain['Strike'] == 24100
            ][['TradingSymbol', 'Type', 'expiry']]
    )

    if 'expiry' not in chain.columns:
        raise ValueError("expiry column not found in option_chain.csv")

    expiry = min(
        pd.to_datetime(chain['expiry']).dt.date
    ).isoformat()

    print(f"\nSpot Price : Rs. {spot}")
    print(f"Expiry     : {expiry}")
    print("Calculating features...\n")

    features = calculate_features(chain, spot, expiry)

    print("=" * 58)
    print("       NIFTY FEATURE SNAPSHOT")
    print("=" * 58)

    sections = {
        "BASIC INFO": ['timestamp', 'spot_price', 'atm_strike', 'expiry', 'dte', 'lot_size'],
        "SENTIMENT": ['pcr', 'sentiment'],
        "KEY LEVELS": ['max_pain', 'distance_from_max_pain', 'support', 'resistance'],
        "LIVE ATM OPTIONS": ['atm_ce_symbol', 'atm_pe_symbol', 'atm_ce_ltp', 'atm_pe_ltp'],
        "VOLATILITY": ['atm_ce_iv', 'atm_pe_iv', 'iv_skew', 'iv_skew_interpretation'],
        "CE GREEKS (ATM)": ['ce_delta', 'ce_gamma', 'ce_theta', 'ce_vega'],
        "PE GREEKS (ATM)": ['pe_delta', 'pe_gamma', 'pe_theta', 'pe_vega'],
        "OI STATS": ['total_ce_oi', 'total_pe_oi', 'ce_oi_concentration_pct', 'pe_oi_concentration_pct'],
        "VOLUME": ['total_ce_volume', 'total_pe_volume'],
        "ML FEATURES": [
            'support_distance_pct',
            'resistance_distance_pct',
            'max_pain_distance_pct',
            'oi_ratio_top3',
            'iv_average',
            'iv_regime',
            'oi_difference_pct'
        ],
    }

    for section, keys in sections.items():
        print(f"\n  [{section}]")

        for k in keys:
            print(f"    {k:<30} {features.get(k, 'N/A')}")

    print("\n" + "=" * 58)

    with open('features.json', 'w') as f:
        json.dump(features, f, indent=2)

    print("\n✅ Features saved to features.json")

    # --------------------------------------------------
    # Auto-log snapshot to features_log table
    # --------------------------------------------------

    import subprocess

    try:
        subprocess.run(
            ["python", "feature_logger.py"],
            check=True
        )
        print("✅ Features logged to database")
    except Exception as e:
        print(f"❌ Feature logger failed: {e}")

    print("   (This file will be used by signal_engine.py and ai_analyst.py)")