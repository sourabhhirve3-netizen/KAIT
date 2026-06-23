import os
import json
import time
import sqlite3
import pandas as pd
from datetime import datetime, date, timedelta
from kiteconnect import KiteConnect
from dotenv import load_dotenv

# Import risk engine functions directly — keeps state in sync
from risk_engine import (
    load_config,
    record_trade_entry,
    record_trade_exit,
)

load_dotenv()

DB_PATH        = 'kait.db'
TRADE_LOG_FILE = 'paper_trades.csv'
ACTIVE_TRADE   = 'active_paper_trade.json'


# ─────────────────────────────────────────────────────────────
# MARKET HOURS (IST)
# ─────────────────────────────────────────────────────────────

MARKET_OPEN  = (9,  15)
MARKET_CLOSE = (15, 30)
EXPIRY_EXIT  = (15, 20)   # Close positions at 3:20 PM on expiry day


def is_market_open() -> bool:
    now = datetime.now()
    t   = (now.hour, now.minute)
    return MARKET_OPEN <= t <= MARKET_CLOSE and now.weekday() < 5


def is_expiry_exit_time(expiry: str) -> bool:
    """True if today is expiry day and time >= 3:20 PM."""
    expiry_date = date.fromisoformat(str(expiry)[:10])
    now = datetime.now()
    return date.today() == expiry_date and (now.hour, now.minute) >= EXPIRY_EXIT


# ─────────────────────────────────────────────────────────────
# KITE CONNECTION
# ─────────────────────────────────────────────────────────────

def get_kite() -> KiteConnect:
    api_key = os.getenv("KITE_API_KEY")
    with open("access_token.txt") as f:
        token = f.read().strip()
    kite = KiteConnect(api_key=api_key)
    kite.set_access_token(token)

    try:
        kite.profile()
    except Exception as e:
        print(f"\n❌ Kite authentication failed")
        print(e)
        raise

    return kite


# ─────────────────────────────────────────────────────────────
# FETCH LIVE OPTION PRICES
# ─────────────────────────────────────────────────────────────

def get_live_prices(kite, ce_symbol: str, pe_symbol: str) -> dict:
    """Fetch live LTP for CE and PE from Kite. Returns combined value."""
    try:
        quotes = kite.quote([f"NFO:{ce_symbol}", f"NFO:{pe_symbol}"])
        ce_ltp = quotes.get(f"NFO:{ce_symbol}", {}).get("last_price", 0) or 0
        pe_ltp = quotes.get(f"NFO:{pe_symbol}", {}).get("last_price", 0) or 0
        return {
            "ce_ltp":    round(float(ce_ltp), 2),
            "pe_ltp":    round(float(pe_ltp), 2),
            "combined":  round(float(ce_ltp) + float(pe_ltp), 2),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    except Exception as e:
        print(f"  ⚠️  Error fetching live prices: {e}")
        return {"ce_ltp": 0, "pe_ltp": 0, "combined": 0, "timestamp": ""}


# ─────────────────────────────────────────────────────────────
# DATABASE — Save paper trade leg
# Schema matches historical_data.py paper_trades table exactly:
# id, timestamp, action, symbol, strike, option_type,
# expiry, entry_price, exit_price, quantity, pnl, status, reason
# ─────────────────────────────────────────────────────────────

def save_trade_leg(
    action:       str,
    symbol:       str,
    strike:       float,
    option_type:  str,
    expiry:       str,
    entry_price:  float,
    exit_price:   float,
    quantity:     int,
    pnl:          float,
    status:       str,
    reason:       str,
):
    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()
    c.execute('''
        INSERT INTO paper_trades
        (timestamp, action, symbol, strike, option_type, expiry,
         entry_price, exit_price, quantity, pnl, status, reason)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        action, symbol, strike, option_type, expiry,
        entry_price, exit_price, quantity, pnl, status, reason,
    ))
    conn.commit()
    conn.close()


# ─────────────────────────────────────────────────────────────
# ACTIVE TRADE STATE — Save / Load / Clear
# ─────────────────────────────────────────────────────────────

def save_active_trade(state: dict):
    with open(ACTIVE_TRADE, "w") as f:
        json.dump(state, f, indent=2)


def load_active_trade() -> dict:
    if os.path.exists(ACTIVE_TRADE):
        with open(ACTIVE_TRADE) as f:
            return json.load(f)
    return {}


def clear_active_trade():
    if os.path.exists(ACTIVE_TRADE):
        os.remove(ACTIVE_TRADE)


# ─────────────────────────────────────────────────────────────
# ENTER PAPER TRADE
# ─────────────────────────────────────────────────────────────

def enter_trade(signal: dict, risk_result: dict, kite) -> dict:
    """
    Simulate entering a short straddle.
    - Reads lot_size from signal.trade.lot_size (flows from kite instruments)
    - Uses signal.trade.stop_loss_value as sl_trigger (already 2x premium)
    - Fetches live entry prices from Kite
    - Saves both legs to DB and active_paper_trade.json
    - Calls risk_engine.record_trade_entry()
    """
    trade    = signal["trade"]
    sizing   = risk_result["sizing"]

    # lot_size must come from trade dict — flows from kite instruments via
    # option_chain.py -> features.py -> signal_engine.py
    lot_size = int(trade.get("lot_size", 65))
    lots     = sizing["recommended_lots"]
    if lots <= 0:
        print("\n❌ Risk engine approved 0 lots")
        print("   Trade will not be entered")
        return {}
    quantity = lots * lot_size


    ce_symbol  = trade["ce_symbol"]
    pe_symbol  = trade["pe_symbol"]
    expiry     = str(trade["expiry"])[:10]
    strike     = float(trade["atm_strike"])

    # sl_trigger comes directly from signal — already 2x premium
    # Do NOT recalculate here — signal_engine owns this value
    #sl_trigger = float(trade["stop_loss_value"])


    print(f"\n  Fetching live entry prices...")
    prices = get_live_prices(kite, ce_symbol, pe_symbol)

    ce_entry = prices["ce_ltp"]
    pe_entry = prices["pe_ltp"]

    if ce_entry == 0 or pe_entry == 0:
        print(f"  ❌ Could not fetch live prices — aborting entry")
        print(f"     CE LTP: {ce_entry}  |  PE LTP: {pe_entry}")
        print(f"     Check that market is open and symbols are correct:")
        print(f"     CE: {ce_symbol}")
        print(f"     PE: {pe_symbol}")
        return {}

    total_premium = round(ce_entry + pe_entry, 2)
    sl_trigger = round(total_premium * 2, 2)
    max_profit    = round(total_premium * quantity, 2)
    max_loss = max(
        0,
        round((sl_trigger - total_premium) * quantity, 2)
    )

    print(f"\n  {'='*50}")
    print(f"  ✅  PAPER TRADE ENTERED")
    print(f"  {'='*50}")
    print(f"  Strategy        : Short Straddle (SELL CE + SELL PE)")
    print(f"  Strike          : {int(strike)}")
    print(f"  Expiry          : {expiry}")
    print(f"  Lots / Quantity : {lots} lot(s)  ({quantity} units)")
    print(f"  {'─'*50}")
    print(f"  CE Symbol       : {ce_symbol}")
    print(f"  CE Sold At      : Rs.{ce_entry}")
    print(f"  PE Symbol       : {pe_symbol}")
    print(f"  PE Sold At      : Rs.{pe_entry}")
    print(f"  {'─'*50}")
    print(f"  Total Premium   : Rs.{total_premium} per unit")
    print(f"  Max Profit      : Rs.{max_profit:,.0f}  (Nifty stays at {int(strike)})")
    print(f"  SL Trigger      : Rs.{sl_trigger} combined value")
    print(f"  Max Loss (SL)   : Rs.{max_loss:,.0f}")
    print(f"  Breakeven Upper : {round(strike + total_premium, 2)}")
    print(f"  Breakeven Lower : {round(strike - total_premium, 2)}")
    print(f"  {'='*50}")

    trade_state = {
        "entry_time":     datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "ce_symbol":      ce_symbol,
        "pe_symbol":      pe_symbol,
        "strike":         strike,
        "expiry":         expiry,
        "lots":           lots,
        "lot_size":       lot_size,
        "quantity":       quantity,
        "ce_entry":       ce_entry,
        "pe_entry":       pe_entry,
        "total_premium":  total_premium,
        "sl_trigger":     sl_trigger,
        "status":         "OPEN",
    }

    # Save both legs to DB as OPEN (exit fields are 0 until close)
    save_trade_leg("SELL", ce_symbol, strike, "CE", expiry,
                   ce_entry, 0, quantity, 0, "OPEN", "Short straddle entry")
    save_trade_leg("SELL", pe_symbol, strike, "PE", expiry,
                   pe_entry, 0, quantity, 0, "OPEN", "Short straddle entry")

    save_active_trade(trade_state)
    record_trade_entry(lots)

    return trade_state


# ─────────────────────────────────────────────────────────────
# EXIT PAPER TRADE
# ─────────────────────────────────────────────────────────────

def exit_trade(trade_state: dict, kite, reason: str) -> dict:
    """
    Simulate closing the straddle.
    P&L = (entry premium - exit premium) * quantity
    For short straddle: profit when option value decays.
    """
    ce_symbol = trade_state["ce_symbol"]
    pe_symbol = trade_state["pe_symbol"]
    quantity  = trade_state["quantity"]
    lots      = trade_state["lots"]
    ce_entry  = trade_state["ce_entry"]
    pe_entry  = trade_state["pe_entry"]
    strike    = trade_state["strike"]
    expiry    = trade_state["expiry"]

    print(f"\n  Fetching live exit prices...")
    prices = get_live_prices(kite, ce_symbol, pe_symbol)

    ce_exit = prices["ce_ltp"]
    pe_exit = prices["pe_ltp"]

    if ce_exit <= 0 or pe_exit <= 0:
        print("\n❌ Could not fetch valid exit prices")
        print(f"   CE LTP: {ce_exit}")
        print(f"   PE LTP: {pe_exit}")
        print("   Trade remains OPEN")
        return {}

    # Short straddle P&L:
    # Sold CE at ce_entry, buying back at ce_exit → profit if ce_exit < ce_entry
    ce_pnl    = round((ce_entry - ce_exit) * quantity, 2)
    pe_pnl    = round((pe_entry - pe_exit) * quantity, 2)
    total_pnl = round(ce_pnl + pe_pnl, 2)

    status_map = {
        "SL_HIT":  "CLOSED_SL",
        "EXPIRY":  "CLOSED_EXPIRY",
        "MANUAL":  "CLOSED_MANUAL",
    }
    status = status_map.get(reason, "CLOSED_MANUAL")

    print(f"\n  {'='*50}")
    print(f"  ✅  PAPER TRADE CLOSED — {reason}")
    print(f"  {'='*50}")
    print(f"  CE Exit         : {ce_symbol} @ Rs.{ce_exit}")
    print(f"  PE Exit         : {pe_symbol} @ Rs.{pe_exit}")
    print(f"  {'─'*50}")
    print(f"  CE P&L          : Rs.{ce_pnl:+,.0f}")
    print(f"  PE P&L          : Rs.{pe_pnl:+,.0f}")
    print(f"  {'─'*50}")
    print(f"  TOTAL P&L       : Rs.{total_pnl:+,.0f}  "
          f"{'✅ PROFIT' if total_pnl >= 0 else '❌ LOSS'}")
    print(f"  {'='*50}")

    # Save closed legs to DB
    save_trade_leg("BUY_BACK", ce_symbol, strike, "CE", expiry,
                   ce_entry, ce_exit, quantity, ce_pnl, status, reason)
    save_trade_leg("BUY_BACK", pe_symbol, strike, "PE", expiry,
                   pe_entry, pe_exit, quantity, pe_pnl, status, reason)

    # Update risk engine state
    record_trade_exit(total_pnl, lots)

    # Clear active trade file
    clear_active_trade()

    # Append to CSV trade log
    log_row = {
        "date":           date.today().isoformat(),
        "entry_time":     trade_state["entry_time"],
        "exit_time":      datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "strike":         strike,
        "expiry":         expiry,
        "lots":           lots,
        "lot_size":       trade_state["lot_size"],
        "quantity":       quantity,
        "ce_symbol":      ce_symbol,
        "pe_symbol":      pe_symbol,
        "ce_entry":       ce_entry,
        "pe_entry":       pe_entry,
        "total_premium":  trade_state["total_premium"],
        "sl_trigger":     trade_state["sl_trigger"],
        "ce_exit":        ce_exit,
        "pe_exit":        pe_exit,
        "ce_pnl":         ce_pnl,
        "pe_pnl":         pe_pnl,
        "total_pnl":      total_pnl,
        "exit_reason":    reason,
        "outcome":        "WIN" if total_pnl >= 0 else "LOSS",
    }

    df_new = pd.DataFrame([log_row])
    if os.path.exists(TRADE_LOG_FILE):
        df_new.to_csv(TRADE_LOG_FILE, mode="a", header=False, index=False)
    else:
        df_new.to_csv(TRADE_LOG_FILE, index=False)

    print(f"\n  📝 Trade logged to {TRADE_LOG_FILE}")
    return log_row


# ─────────────────────────────────────────────────────────────
# MONITOR LOOP
# Checks live prices every check_interval seconds.
# Exits on: SL hit | expiry day 3:20 PM | market close | Ctrl+C
# ─────────────────────────────────────────────────────────────

def monitor_trade(trade_state: dict, kite, check_interval: int = 60):
    ce_symbol     = trade_state["ce_symbol"]
    pe_symbol     = trade_state["pe_symbol"]
    sl_trigger    = trade_state["sl_trigger"]
    expiry        = trade_state["expiry"]
    total_premium = trade_state["total_premium"]
    quantity      = trade_state["quantity"]

    print(f"\n  👁   Monitoring trade — checking every {check_interval}s")
    print(f"  SL trigger : Rs.{sl_trigger} combined straddle value")
    print(f"  Expiry     : {expiry}")
    print(f"  Press Ctrl+C to exit manually\n")

    try:
        while True:
            if not is_market_open():
                print(f"  ⏸  Market closed — pausing (checking again in 5 min)")
                time.sleep(300)
                continue

            prices = get_live_prices(kite, ce_symbol, pe_symbol)

            combined = prices["combined"]
            ce_ltp = prices["ce_ltp"]
            pe_ltp = prices["pe_ltp"]

            if combined <= 0:
                print("  ⚠️ Invalid quote received from Kite. Skipping cycle.")
                time.sleep(check_interval)
                continue

            # Unrealised P&L = (premium collected - current combined value) * qty
            unrealised = round(
                (total_premium - combined) * quantity,
                2
            )

            pct_capture = round(
                ((total_premium - combined) / total_premium) * 100,
                1
            ) if total_premium > 0 else 0

            print(
                f"  [{prices['timestamp']}]  "
                f"CE: {ce_ltp:.2f}  "
                f"PE: {pe_ltp:.2f}  "
                f"Combined: {combined:.2f}  "
                f"SL: {sl_trigger:.2f}  "
                f"Unrealised P&L: Rs.{unrealised:+,.0f} ({pct_capture}% premium captured)"
            )

            # ── SL CHECK ─────────────────────────────────────
            if combined >= sl_trigger:
                print(f"\n  🚨 STOP LOSS HIT")
                print(f"     Combined Rs.{combined} >= SL trigger Rs.{sl_trigger}")
                return exit_trade(trade_state, kite, "SL_HIT")

            # ── EXPIRY EXIT CHECK ─────────────────────────────
            if is_expiry_exit_time(expiry):
                print(f"\n  🔔 EXPIRY — Closing at 3:20 PM on expiry day")
                return exit_trade(trade_state, kite, "EXPIRY")

            # ── SAFETY: market about to close ────────────────
            now = datetime.now()
            if now.hour == 15 and now.minute >= 25:
                print(f"\n  🔔 Market closing soon — exiting before 3:30 PM")
                return exit_trade(trade_state, kite, "MANUAL")

            time.sleep(check_interval)

    except KeyboardInterrupt:
        print(f"\n\n  ⚠️  Ctrl+C — manual interrupt")
        confirm = input("  Exit the trade now? (yes/no): ").strip().lower()
        if confirm == "yes":
            return exit_trade(trade_state, kite, "MANUAL")
        else:
            print("  Trade still OPEN — run paper_trader.py again to resume")
            return {}


# ─────────────────────────────────────────────────────────────
# PAPER TRADE SUMMARY
# ─────────────────────────────────────────────────────────────

def show_summary():
    if not os.path.exists(TRADE_LOG_FILE):
        print("  No paper trades recorded yet.")
        return

    df = pd.read_csv(TRADE_LOG_FILE)
    if df.empty:
        print("  No paper trades recorded yet.")
        return

    wins   = df[df["outcome"] == "WIN"]
    losses = df[df["outcome"] == "LOSS"]
    total  = len(df)

    print("\n" + "=" * 62)
    print("   PAPER TRADING SUMMARY")
    print("=" * 62)
    print(f"\n  Total Trades    : {total}")
    print(f"  Wins            : {len(wins)}  ({round(len(wins)/total*100,1)}%)")
    print(f"  Losses          : {len(losses)}")
    print(f"\n  Total P&L       : Rs.{df['total_pnl'].sum():+,.0f}")

    if len(wins) > 0:
        print(f"  Avg Win         : Rs.{wins['total_pnl'].mean():+,.0f}")
    if len(losses) > 0:
        print(f"  Avg Loss        : Rs.{losses['total_pnl'].mean():+,.0f}")

    print(f"  Best Trade      : Rs.{df['total_pnl'].max():+,.0f}")
    print(f"  Worst Trade     : Rs.{df['total_pnl'].min():+,.0f}")

    print(f"\n  {'Date':<12} {'Strike':>7} {'Premium':>8} {'SL':>8} {'P&L':>10}  Result")
    print(f"  {'─'*58}")
    for _, row in df.iterrows():
        print(
            f"  {str(row['date']):<12}"
            f"{row['strike']:>7.0f}"
            f"{row['total_premium']:>8.1f}"
            f"{row['sl_trigger']:>8.1f}"
            f"{row['total_pnl']:>+10.0f}"
            f"  {'✅' if row['outcome'] == 'WIN' else '❌'} {row['exit_reason']}"
        )
    print("=" * 62)


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":

    print("=" * 62)
    print("  KAIT — Phase 7: Paper Trader")
    print("=" * 62)

    # ── RESUME: active trade already open? ───────────────────
    active = load_active_trade()
    if active:
        print(f"\n  ⚠️  Active paper trade found!")
        print(f"  Entry      : {active.get('entry_time')}")
        print(f"  CE Symbol  : {active.get('ce_symbol')}")
        print(f"  PE Symbol  : {active.get('pe_symbol')}")
        print(f"  Strike     : {active.get('strike')}")
        print(f"  Expiry     : {active.get('expiry')}")
        print(f"  SL Trigger : Rs.{active.get('sl_trigger')}")
        print(f"\n  [1] Resume monitoring")
        print(f"  [2] Exit trade now (manual)")
        print(f"  [3] Show summary")
        print(f"  [4] Quit")

        choice = input("\n  Choice (1/2/3/4): ").strip()
        kite   = get_kite()

        if choice == "1":
            monitor_trade(active, kite)
            show_summary()
        elif choice == "2":
            exit_trade(active, kite, "MANUAL")
            show_summary()
        elif choice == "3":
            show_summary()
        exit()

    # ── LOAD RISK RESULT ─────────────────────────────────────
    if not os.path.exists("risk_result.json"):
        print("\n❌ risk_result.json not found — run risk_engine.py first")
        exit()

    with open("risk_result.json") as f:
        risk_result = json.load(f)

    if not risk_result.get("approved"):
        print("\n❌ Risk engine rejected this trade:")
        for item in risk_result.get("failed", []):
            print(f"   {item}")
        exit()

    # ── LOAD SIGNAL ──────────────────────────────────────────
    if not os.path.exists("signal.json"):
        print("\n❌ signal.json not found — run signal_engine.py first")
        exit()

    with open("signal.json") as f:
        signal = json.load(f)

    # Handle NO_TRADE — including the new ce_premium<=0 guard in signal_engine
    if signal.get("signal") != "SELL_STRADDLE":
        print(f"\n❌ Signal is '{signal.get('signal')}' — nothing to trade")
        if signal.get("failed"):
            print("   Filters that failed:")
            for item in signal["failed"]:
                print(f"   {item}")
        exit()

    trade = signal.get("trade", {})
    if not trade:
        print("\n❌ Signal has no trade details — LTPs may have been 0")
        print("   Re-run option_chain.py → features.py → signal_engine.py")
        exit()

    # Validate symbols are present
    if not trade.get("ce_symbol") or not trade.get("pe_symbol"):
        print("\n❌ CE or PE symbol missing from signal")
        print("   Re-run option_chain.py → features.py → signal_engine.py")
        exit()

    # ── PRINT TRADE PLAN ─────────────────────────────────────
    sizing = risk_result["sizing"]
    print(f"\n  [TRADE PLAN]")
    print(f"  Signal          : {signal['signal']}  ({int(signal['confidence']*100)}% confidence)")
    print(f"  Strike          : {trade['atm_strike']}")
    print(f"  Expiry          : {trade['expiry']}")
    print(f"  CE Symbol       : {trade['ce_symbol']}")
    print(f"  PE Symbol       : {trade['pe_symbol']}")
    print(f"  Total Premium   : Rs.{trade['total_premium']} per unit")
    print(f"  Stop Loss       : {trade['stop_loss_rule']}")
    print(f"  Recommended Lots: {sizing['recommended_lots']}")
    print(f"  Lot Size        : {trade.get('lot_size', 65)} units")
    print(f"  Margin Required : Rs.{sizing['margin_required']:,.0f}")

    # ── MARKET HOURS CHECK ────────────────────────────────────
    if not is_market_open():
        now = datetime.now()
        print(f"\n  ⚠️  Market is currently closed ({now.strftime('%H:%M')} IST)")
        print(f"  Normal hours: Mon–Fri  9:15 AM – 3:30 PM")
        print(f"\n  [1] Enter anyway (testing / outside market hours)")
        print(f"  [2] Show paper trade summary")
        print(f"  [3] Quit")
        choice = input("\n  Choice (1/2/3): ").strip()
        if choice == "2":
            show_summary()
            exit()
        elif choice != "1":
            exit()

    # ── CONFIRM ENTRY ─────────────────────────────────────────
    print(f"\n  ⚠️  THIS IS A PAPER TRADE — NO REAL MONEY WILL BE USED")
    confirm = input("\n  Confirm paper trade entry? (yes/no): ").strip().lower()
    if confirm != "yes":
        print("  Cancelled.")
        exit()

    # ── CONNECT TO KITE ──────────────────────────────────────
    print("\n  Connecting to Kite...")
    kite = get_kite()
    print("  ✅ Connected")

    # ── ENTER TRADE ──────────────────────────────────────────
    trade_state = enter_trade(signal, risk_result, kite)

    if not trade_state:
        print("\n❌ Trade entry failed — check symbols and market hours")
        exit()

    # ── MONITOR OR EXIT ──────────────────────────────────────
    print(f"\n  [1] Monitor live  (price check every 60 seconds)")
    print(f"  [2] Exit immediately  (test / manual close)")
    print(f"  [3] Leave open and quit  (resume later)")
    choice = input("\n  Choice (1/2/3): ").strip()

    if choice == "1":
        monitor_trade(trade_state, kite, check_interval=60)
        show_summary()
    elif choice == "2":
        exit_trade(trade_state, kite, "MANUAL")
        show_summary()
    elif choice == "3":
        print("  Trade saved — run paper_trader.py again to monitor or exit")