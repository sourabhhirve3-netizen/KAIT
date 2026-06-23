import os
import json
import sqlite3
import pandas as pd
from datetime import datetime, date, timedelta
from dotenv import load_dotenv
from config import DTE_MIN, DTE_MAX

load_dotenv()

DB_PATH = 'kait.db'

# ─────────────────────────────────────────────────────────────
# KNOWN HIGH-VOLATILITY EVENT DATES
# Add new dates here before each event.
# On these weeks the signal engine will return NO_TRADE.
# Format: 'YYYY-MM-DD' = the Monday of that week
# ─────────────────────────────────────────────────────────────

HIGH_VOLATILITY_WEEKS = [
    # RBI Monetary Policy Committee meetings (approx)
    '2026-06-02', '2026-08-03', '2026-10-05', '2026-12-07',
    # Union Budget week
    '2026-01-26', '2027-01-25',
    # US Fed meetings (approx Wednesdays — avoid that week)
    '2026-07-27', '2026-09-14', '2026-11-02', '2026-12-14',
    # Add more as you learn them
]

# ─────────────────────────────────────────────────────────────
# SIGNAL RULES — THRESHOLDS
# These are the tunable parameters of the strategy.
# Adjust based on backtest performance over time.
# ─────────────────────────────────────────────────────────────

RULES = {
    # PCR range for neutral market (best for straddle selling)
    'pcr_min':              0.7,    # Below this = too bearish, avoid
    'pcr_max':              1.4,    # Above this = too bullish, avoid

    # IV filter — don't sell if IV is too low (not enough premium)
    # or too high (market is panicking, too risky)
    'iv_min':               8.0,    # Minimum ATM CE IV % to sell
    'iv_max':               22.0,   # Maximum ATM CE IV % to sell

    # Stop loss — exit if combined straddle value exceeds this
    # multiple of the premium collected at entry
    'straddle_sl_multiple': 2.0,    # Exit if straddle value = 2x entry premium

    # Days to expiry — only enter when DTE is in this range
    'dte_min': DTE_MIN,
    'dte_max': DTE_MAX,

    # OI concentration — avoid if too concentrated (manipulation risk)
    'oi_concentration_max': 80.0,   # % of OI in top 3 strikes

    # Theta filter — minimum daily decay to make trade worthwhile
    'theta_min':            10.0,   # ATM CE theta must be at least Rs.10/day

    # Max Nifty move in last 5 days — avoid if market is already trending
    'max_recent_move_pct':  2.5,    # If Nifty moved >2.5% last week, avoid
}


# ─────────────────────────────────────────────────────────────
# HELPER — Load recent candles for trend check
# ─────────────────────────────────────────────────────────────

def get_recent_candles(days=10) -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    since = (date.today() - timedelta(days=days)).isoformat()
    df = pd.read_sql_query(
        'SELECT * FROM nifty_candles WHERE date >= ? ORDER BY date ASC',
        conn, params=(since,)
    )
    conn.close()
    df['close'] = df['close'].astype(float)
    return df


def get_recent_move_pct(candles_df) -> float:
    """Calculate % move of Nifty over last 5 trading days."""

    if len(candles_df) < 5:
        return 0.0

    recent = candles_df.tail(5)

    start = recent.iloc[0]['close']
    end = recent.iloc[-1]['close']

    return round(abs((end - start) / start * 100), 2)


# ─────────────────────────────────────────────────────────────
# HELPER — Check if this week is a high-volatility event week
# ─────────────────────────────────────────────────────────────

def is_event_week(check_date=None) -> tuple:
    """
    Returns (True, reason) if this is a known high-volatility week,
    else (False, '').
    """
    if check_date is None:
        check_date = date.today()

    # Find Monday of current week
    monday = check_date - timedelta(days=check_date.weekday())
    monday_str = monday.strftime('%Y-%m-%d')

    if monday_str in HIGH_VOLATILITY_WEEKS:
        return True, f"High-volatility event week ({monday_str})"

    return False, ''


# ─────────────────────────────────────────────────────────────
# CORE SIGNAL ENGINE
# ─────────────────────────────────────────────────────────────

def generate_signal(features: dict, check_date=None) -> dict:
    """
    Takes the calculated features dict and applies all rules.
    Returns a signal dict with:
      - signal:     'SELL_STRADDLE' | 'NO_TRADE'
      - confidence: 0.0 to 1.0 (how many rules passed)
      - reasons:    list of why each rule passed or failed
      - trade:      trade details if signal is SELL_STRADDLE
      - filters:    each rule's individual result
    """

    if check_date is None:
        check_date = date.today()

    reasons  = []
    passed   = []
    failed   = []
    filters  = {}

    spot       = features.get('spot_price', 0)
    atm        = features.get('atm_strike', 0)
    pcr        = features.get('pcr', 0)
    dte        = features.get('dte', 0)
    ce_iv      = features.get('atm_ce_iv', 0)
    pe_iv      = features.get('atm_pe_iv', 0)
    ce_theta   = abs(features.get('ce_theta', 0))
    ce_conc    = features.get('ce_oi_concentration_pct', 0)
    pe_conc    = features.get('pe_oi_concentration_pct', 0)
    max_pain   = features.get('max_pain', 0)
    resistance = features.get('resistance', 0)
    support    = features.get('support', 0)

    # ── FILTER 1: Event Week ──────────────────────────────────
    event, event_reason = is_event_week(check_date)
    if event:
        failed.append(f"❌ EVENT WEEK — {event_reason}")
        filters['event_week'] = False
    else:
        passed.append("✅ No high-volatility event this week")
        filters['event_week'] = True

    # ── FILTER 2: DTE Range ───────────────────────────────────
    dte_ok = RULES['dte_min'] <= dte <= RULES['dte_max']
    if dte_ok:
        passed.append(f"✅ DTE {dte} is within range ({RULES['dte_min']}-{RULES['dte_max']} days)")
        filters['dte'] = True
    else:
        failed.append(f"❌ DTE {dte} is outside range ({RULES['dte_min']}-{RULES['dte_max']} days)")
        filters['dte'] = False

    # ── FILTER 3: PCR Range ───────────────────────────────────
    pcr_ok = RULES['pcr_min'] <= pcr <= RULES['pcr_max']
    if pcr_ok:
        passed.append(f"✅ PCR {pcr} is within neutral range ({RULES['pcr_min']}-{RULES['pcr_max']})")
        filters['pcr'] = True
    else:
        failed.append(f"❌ PCR {pcr} is outside neutral range ({RULES['pcr_min']}-{RULES['pcr_max']})")
        filters['pcr'] = False

    # ── FILTER 4: IV Range ────────────────────────────────────
    iv_ok = RULES['iv_min'] <= ce_iv <= RULES['iv_max']
    if iv_ok:
        passed.append(f"✅ ATM CE IV {ce_iv}% is within range ({RULES['iv_min']}%-{RULES['iv_max']}%)")
        filters['iv'] = True
    else:
        failed.append(f"❌ ATM CE IV {ce_iv}% is outside range ({RULES['iv_min']}%-{RULES['iv_max']}%)")
        filters['iv'] = False

    # ── FILTER 5: Theta Filter ────────────────────────────────
    theta_ok = ce_theta >= RULES['theta_min']
    if theta_ok:
        passed.append(f"✅ CE Theta Rs.{ce_theta:.1f}/day is sufficient (min Rs.{RULES['theta_min']})")
        filters['theta'] = True
    else:
        failed.append(f"❌ CE Theta Rs.{ce_theta:.1f}/day is too low (min Rs.{RULES['theta_min']})")
        filters['theta'] = False

    # ── FILTER 6: OI Concentration ────────────────────────────
    conc_ok = ce_conc <= RULES['oi_concentration_max'] and pe_conc <= RULES['oi_concentration_max']
    if conc_ok:
        passed.append(f"✅ OI concentration CE:{ce_conc}% PE:{pe_conc}% is normal")
        filters['oi_concentration'] = True
    else:
        failed.append(f"❌ OI too concentrated — CE:{ce_conc}% PE:{pe_conc}% (max {RULES['oi_concentration_max']}%)")
        filters['oi_concentration'] = False

    # ── FILTER 7: Recent Market Move ─────────────────────────
    try:
        candles = get_recent_candles(days=10)
        recent_move = get_recent_move_pct(candles)
        move_ok = recent_move <= RULES['max_recent_move_pct']
        if move_ok:
            passed.append(f"✅ Recent 5-day Nifty move {recent_move}% is within limit ({RULES['max_recent_move_pct']}%)")
            filters['recent_move'] = True
        else:
            failed.append(f"❌ Recent 5-day Nifty move {recent_move}% exceeds limit ({RULES['max_recent_move_pct']}%)")
            filters['recent_move'] = False
    except Exception:
        recent_move = 0
        passed.append("✅ Recent move check skipped (no DB data)")
        filters['recent_move'] = True

    # ── FILTER 8: Max Pain Proximity ─────────────────────────
    # Spot should be within 100 points of Max Pain for straddle
    pain_distance = abs(spot - max_pain)
    pain_ok = pain_distance <= 150
    if pain_ok:
        passed.append(f"✅ Spot Rs.{spot} is {pain_distance:.0f} pts from Max Pain Rs.{max_pain} (within 150)")
        filters['max_pain_proximity'] = True
    else:
        failed.append(f"❌ Spot Rs.{spot} is {pain_distance:.0f} pts from Max Pain Rs.{max_pain} (limit 150)")
        filters['max_pain_proximity'] = False

    # ── CALCULATE CONFIDENCE ─────────────────────────────────
    total_filters = len(passed) + len(failed)
    confidence    = round(len(passed) / total_filters, 2) if total_filters > 0 else 0

    # ── GENERATE SIGNAL ───────────────────────────────────────
    # All filters must pass for a SELL_STRADDLE signal
    critical_filters = [
        'event_week',
        'dte',
        'iv',
        'recent_move',
        'max_pain_proximity'
    ]
    critical_pass    = all(filters.get(f, False) for f in critical_filters)
    all_pass         = len(failed) == 0

    if all_pass:
        signal = 'SELL_STRADDLE'
    elif critical_pass and len(failed) <= 1:
        signal = 'SELL_STRADDLE'  # Allow 1 non-critical failure
    else:
        signal = 'NO_TRADE'

    # ── TRADE DETAILS ─────────────────────────────────────────
    trade = {}

    if signal == 'SELL_STRADDLE':

        ce_premium = round(features.get('atm_ce_ltp', 0), 2)
        pe_premium = round(features.get('atm_pe_ltp', 0), 2)

        # Safety check
        if ce_premium <= 0 or pe_premium <= 0:
            signal = 'NO_TRADE'

        # Fallback to Black-Scholes if LTPs are unavailable
        if ce_premium == 0 or pe_premium == 0:

            import math
            from scipy.stats import norm

            T = max(dte / 365, 0.0001)
            r = 0.065

            sigma_ce = ce_iv / 100
            sigma_pe = pe_iv / 100

            def bs(S, K, T, r, sig, option_type):

                if T <= 0 or sig <= 0:
                    return 0

                d1 = (
                             math.log(S / K)
                             + (r + 0.5 * sig ** 2) * T
                     ) / (sig * math.sqrt(T))

                d2 = d1 - sig * math.sqrt(T)

                if option_type == 'CE':
                    return (
                            S * norm.cdf(d1)
                            - K * math.exp(-r * T) * norm.cdf(d2)
                    )

                return (
                        K * math.exp(-r * T) * norm.cdf(-d2)
                        - S * norm.cdf(-d1)
                )

            ce_premium = round(
                bs(spot, atm, T, r, sigma_ce, 'CE'),
                2
            )

            pe_premium = round(
                bs(spot, atm, T, r, sigma_pe, 'PE'),
                2
            )

        total_prem = round(ce_premium + pe_premium, 2)

        stop_loss = round(
            total_prem * RULES['straddle_sl_multiple'],
            2
        )

        lot_size = int(features.get('lot_size', 75))

        max_profit = round(total_prem * lot_size, 2)
        max_loss_sl = round(stop_loss * lot_size, 2)

        trade = {
            'action': 'SELL STRADDLE',
            'instrument': 'NIFTY',
            'expiry': features.get('expiry', ''),
            'atm_strike': atm,
            'lot_size': features.get('lot_size', 65),

            'ce_symbol': features.get('atm_ce_symbol', ''),
            'pe_symbol': features.get('atm_pe_symbol', ''),

            'sell_ce_at': f"Rs. {ce_premium} (live LTP)",
            'sell_pe_at': f"Rs. {pe_premium} (live LTP)",

            'total_premium': total_prem,

            'stop_loss_value': stop_loss,

            'stop_loss_rule': (
                f"Exit if combined straddle value exceeds "
                f"Rs. {stop_loss}"
            ),

            'max_profit_1lot': (
                f"Rs. {max_profit:,.0f} "
                f"(if Nifty closes at {atm} on expiry)"
            ),

            'max_loss_1lot': (
                f"Rs. {max_loss_sl:,.0f} "
                f"(if SL is hit)"
            ),

            'breakeven_upper': round(atm + total_prem, 2),
            'breakeven_lower': round(atm - total_prem, 2),

            'quantity': (
                f'1 lot ({lot_size} units) — adjust per risk engine'
            ),

            'exit_rule': (
                'Close both legs on expiry Thursday, or on SL hit'
            ),
        }

    # ── FINAL SIGNAL DICT ─────────────────────────────────────
    result = {
        'timestamp':   datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'signal':      signal,
        'confidence':  confidence,
        'filters':     filters,
        'passed':      passed,
        'failed':      failed,
        'trade':       trade,
        'rules_used':  RULES,
    }

    return result


# ─────────────────────────────────────────────────────────────
# PRINT SIGNAL REPORT
# ─────────────────────────────────────────────────────────────

def print_signal(result: dict):
    signal     = result['signal']
    confidence = result['confidence']
    trade      = result.get('trade', {})

    print("\n" + "=" * 60)
    print("   KAIT — SIGNAL ENGINE REPORT")
    print(f"   {result['timestamp']}")
    print("=" * 60)

    # Filter results
    print("\n  [FILTER CHECKS]")
    for r in result['passed']:
        print(f"    {r}")
    for r in result['failed']:
        print(f"    {r}")

    # Signal
    print(f"\n  [SIGNAL]")
    print(f"    Signal     : {'🟢 ' + signal if signal == 'SELL_STRADDLE' else '🔴 ' + signal}")
    print(f"    Confidence : {int(confidence * 100)}%  ({len(result['passed'])}/{len(result['passed'])+len(result['failed'])} filters passed)")

    # Trade details
    if signal == 'SELL_STRADDLE' and trade:
        print(f"\n  [TRADE DETAILS]")
        print(f"    Action          : {trade['action']}")
        print(f"    Strike          : {trade['atm_strike']}")
        print(f"    Sell CE at      : {trade['sell_ce_at']}")
        print(f"    Sell PE at      : {trade['sell_pe_at']}")
        print(f"    Total Premium   : Rs. {trade['total_premium']} per unit")
        print(f"    Breakeven Upper : {trade['breakeven_upper']}")
        print(f"    Breakeven Lower : {trade['breakeven_lower']}")
        print(f"    Stop Loss Rule  : {trade['stop_loss_rule']}")
        print(f"    Max Profit      : {trade['max_profit_1lot']}")
        print(f"    Max Loss (SL)   : {trade['max_loss_1lot']}")
        print(f"    Exit Rule       : {trade['exit_rule']}")

    elif signal == 'NO_TRADE':
        print(f"\n  [REASON]")
        print(f"    {len(result['failed'])} filter(s) failed — staying out of market today")
        for f in result['failed']:
            print(f"    {f}")

    print("\n" + "=" * 60)


# ─────────────────────────────────────────────────────────────
# SAVE SIGNAL TO FILE
# ─────────────────────────────────────────────────────────────

def save_signal(result: dict):
    with open('signal.json', 'w') as f:
        json.dump(result, f, indent=2)
    print(f"\n✅ Signal saved to signal.json")
    print(f"   Next step: risk_engine.py will validate this signal")


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

if __name__ == '__main__':

    print("=" * 60)
    print("  KAIT — Phase 5: Signal Engine")
    print("=" * 60)

    # Load today's features
    if not os.path.exists('features.json'):
        print("\n❌ features.json not found — run features.py first")
        exit()

    with open('features.json') as f:
        features = json.load(f)

    print(f"\n  Spot Price : Rs. {features.get('spot_price')}")
    print(f"  ATM Strike : {features.get('atm_strike')}")
    print(f"  PCR        : {features.get('pcr')} ({features.get('sentiment')})")
    print(f"  DTE        : {features.get('dte')} days")
    print(f"  ATM CE IV  : {features.get('atm_ce_iv')}%")
    print(f"  Max Pain   : {features.get('max_pain')}")

    # Generate signal
    print("\n⏳ Running signal engine...")
    result = generate_signal(features)

    # Print and save
    print_signal(result)
    save_signal(result)