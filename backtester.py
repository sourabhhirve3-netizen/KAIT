import os
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
from dotenv import load_dotenv

load_dotenv()

DB_PATH = 'kait.db'

# ─────────────────────────────────────────────────────────────
# HELPER — Load candles from database
# ─────────────────────────────────────────────────────────────

def load_candles() -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query('SELECT * FROM nifty_candles ORDER BY date ASC', conn)
    conn.close()
    df['date']  = pd.to_datetime(df['date'])
    df['open']  = df['open'].astype(float)
    df['high']  = df['high'].astype(float)
    df['low']   = df['low'].astype(float)
    df['close'] = df['close'].astype(float)
    return df


# ─────────────────────────────────────────────────────────────
# HELPER — Estimate option premium (simplified Black-Scholes)
# We don't have historical option prices in our DB yet,
# so we approximate using spot price and a fixed IV assumption.
# ─────────────────────────────────────────────────────────────

import math
from scipy.stats import norm

def bs_price(S, K, T, r, sigma, opt_type='CE'):
    if T <= 0 or sigma <= 0:
        return max(0, S - K) if opt_type == 'CE' else max(0, K - S)
    d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    if opt_type == 'CE':
        return S * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)
    else:
        return K * math.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)

def atm_strike(spot):
    return round(spot / 50) * 50


# ─────────────────────────────────────────────────────────────
# STRATEGY 1 — ATM SHORT STRADDLE
#
# Logic:
#   Entry  : Monday open — SELL ATM CE + SELL ATM PE
#   Exit   : Thursday close (expiry day)
#   Profit : Both premiums collected if Nifty stays near ATM
#   Loss   : If Nifty moves far from ATM strike
#
# This is a market-neutral strategy that profits from
# low volatility and time decay (Theta).
# ─────────────────────────────────────────────────────────────

def backtest_short_straddle(candles_df, iv_assumption=0.12, lot_size=50, risk_free=0.065):
    """
    Backtest a weekly ATM short straddle on Nifty.

    Parameters:
        candles_df    : DataFrame with date, open, high, low, close
        iv_assumption : Assumed IV for option pricing (12% = typical Nifty weekly IV)
        lot_size      : Nifty lot size (50 units per lot)
        risk_free     : Risk-free rate

    Returns:
        trades list, summary dict
    """

    trades   = []
    df       = candles_df.copy()
    df['dow'] = df['date'].dt.dayofweek  # 0=Mon, 3=Thu, 4=Fri

    # Find all Mondays
    mondays = df[df['dow'] == 0].copy()

    for _, monday in mondays.iterrows():
        entry_date  = monday['date']
        entry_spot  = monday['open']
        strike      = atm_strike(entry_spot)

        # Days to expiry from Monday to Thursday = 3 trading days
        T_entry = 4 / 365  # 4 calendar days approx

        # Calculate entry premiums (we SELL these — we collect the premium)
        ce_entry = bs_price(entry_spot, strike, T_entry, risk_free, iv_assumption, 'CE')
        pe_entry = bs_price(entry_spot, strike, T_entry, risk_free, iv_assumption, 'PE')
        total_premium_collected = round(ce_entry + pe_entry, 2)

        # Find the Thursday of the same week (expiry)
        thursday = df[
            (df['date'] > entry_date) &
            (df['date'] <= entry_date + timedelta(days=6)) &
            (df['dow'] == 3)
        ]

        if thursday.empty:
            # Try Friday if Thursday is a holiday
            friday = df[
                (df['date'] > entry_date) &
                (df['date'] <= entry_date + timedelta(days=7)) &
                (df['dow'] == 4)
            ]
            if friday.empty:
                continue
            exit_row = friday.iloc[0]
        else:
            exit_row = thursday.iloc[0]

        exit_date  = exit_row['date']
        exit_spot  = exit_row['close']

        # At expiry, option value = intrinsic value only (no time value left)
        ce_exit = max(0, exit_spot - strike)  # CE value at expiry
        pe_exit = max(0, strike - exit_spot)  # PE value at expiry

        # P&L for short straddle:
        # We collected premium at entry, we pay intrinsic value at exit
        pnl_per_unit = total_premium_collected - (ce_exit + pe_exit)
        pnl_lot      = round(pnl_per_unit * lot_size, 2)

        # Movement of Nifty during the week
        nifty_move     = round(exit_spot - entry_spot, 2)
        nifty_move_pct = round((exit_spot - entry_spot) / entry_spot * 100, 2)

        # Breakeven range
        breakeven_upper = strike + total_premium_collected
        breakeven_lower = strike - total_premium_collected

        outcome = 'WIN' if pnl_lot > 0 else 'LOSS'

        trades.append({
            'entry_date':           entry_date.strftime('%Y-%m-%d'),
            'exit_date':            exit_date.strftime('%Y-%m-%d'),
            'entry_spot':           entry_spot,
            'exit_spot':            exit_spot,
            'strike':               strike,
            'ce_premium':           round(ce_entry, 2),
            'pe_premium':           round(pe_entry, 2),
            'total_premium':        total_premium_collected,
            'breakeven_upper':      round(breakeven_upper, 2),
            'breakeven_lower':      round(breakeven_lower, 2),
            'nifty_move':           nifty_move,
            'nifty_move_pct':       nifty_move_pct,
            'ce_exit_value':        round(ce_exit, 2),
            'pe_exit_value':        round(pe_exit, 2),
            'pnl_per_unit':         round(pnl_per_unit, 2),
            'pnl_1_lot':            pnl_lot,
            'outcome':              outcome,
        })

    return trades


# ─────────────────────────────────────────────────────────────
# PERFORMANCE METRICS
# ─────────────────────────────────────────────────────────────

def calculate_metrics(trades: list) -> dict:
    if not trades:
        return {}

    df = pd.DataFrame(trades)
    pnls = df['pnl_1_lot'].values

    wins   = df[df['outcome'] == 'WIN']
    losses = df[df['outcome'] == 'LOSS']

    total_trades  = len(df)
    win_count     = len(wins)
    loss_count    = len(losses)
    win_rate      = round(win_count / total_trades * 100, 1)

    total_pnl     = round(pnls.sum(), 2)
    avg_win       = round(wins['pnl_1_lot'].mean(), 2)  if win_count  > 0 else 0
    avg_loss      = round(losses['pnl_1_lot'].mean(), 2) if loss_count > 0 else 0
    best_trade    = round(pnls.max(), 2)
    worst_trade   = round(pnls.min(), 2)

    # Profit factor = total profit / total loss (absolute)
    total_profit = wins['pnl_1_lot'].sum()   if win_count  > 0 else 0
    total_loss   = abs(losses['pnl_1_lot'].sum()) if loss_count > 0 else 1
    profit_factor = round(total_profit / total_loss, 2) if total_loss > 0 else 999

    # Cumulative P&L
    df['cumulative_pnl'] = pnls.cumsum()

    # Max drawdown
    rolling_max = df['cumulative_pnl'].cummax()
    drawdown    = df['cumulative_pnl'] - rolling_max
    max_drawdown = round(drawdown.min(), 2)

    # Sharpe ratio (weekly returns)
    avg_return = pnls.mean()
    std_return = pnls.std()
    sharpe = round(avg_return / std_return * math.sqrt(52), 2) if std_return > 0 else 0

    # Consecutive wins/losses
    streak, max_win_streak, max_loss_streak = 0, 0, 0
    current_streak_type = None
    for outcome in df['outcome']:
        if outcome == current_streak_type:
            streak += 1
        else:
            streak = 1
            current_streak_type = outcome
        if outcome == 'WIN':
            max_win_streak = max(max_win_streak, streak)
        else:
            max_loss_streak = max(max_loss_streak, streak)

    return {
        'total_trades':     total_trades,
        'wins':             win_count,
        'losses':           loss_count,
        'win_rate_pct':     win_rate,
        'total_pnl':        total_pnl,
        'avg_win':          avg_win,
        'avg_loss':         avg_loss,
        'best_trade':       best_trade,
        'worst_trade':      worst_trade,
        'profit_factor':    profit_factor,
        'max_drawdown':     max_drawdown,
        'sharpe_ratio':     sharpe,
        'max_win_streak':   max_win_streak,
        'max_loss_streak':  max_loss_streak,
    }


# ─────────────────────────────────────────────────────────────
# PRINT RESULTS
# ─────────────────────────────────────────────────────────────

def print_results(trades, metrics):

    df = pd.DataFrame(trades)

    print("\n" + "=" * 68)
    print("   BACKTEST RESULTS — NIFTY ATM SHORT STRADDLE (Weekly)")
    print("   Strategy: Sell ATM CE + PE on Monday, close Thursday")
    print("=" * 68)

    # Trade log
    print(f"\n{'Date':<12} {'Strike':>7} {'Prem':>6} {'BEL':>7} {'BEU':>7} {'Exit':>8} {'Move%':>6} {'P&L':>8} {'Result'}")
    print("-" * 68)

    for t in trades:
        print(
            f"{t['entry_date']:<12}"
            f"{t['strike']:>7.0f}"
            f"{t['total_premium']:>6.1f}"
            f"{t['breakeven_lower']:>7.0f}"
            f"{t['breakeven_upper']:>7.0f}"
            f"{t['exit_spot']:>8.1f}"
            f"{t['nifty_move_pct']:>+6.1f}%"
            f"{t['pnl_1_lot']:>+8.0f}"
            f"  {'✅' if t['outcome']=='WIN' else '❌'}"
        )

    # Summary
    print("\n" + "=" * 68)
    print("   PERFORMANCE SUMMARY (1 Lot = 50 units)")
    print("=" * 68)

    print(f"\n  Total Trades       : {metrics['total_trades']}")
    print(f"  Wins               : {metrics['wins']}  ({metrics['win_rate_pct']}%)")
    print(f"  Losses             : {metrics['losses']}")
    print(f"\n  Total P&L          : Rs. {metrics['total_pnl']:+,.0f}")
    print(f"  Average Win        : Rs. {metrics['avg_win']:+,.0f}")
    print(f"  Average Loss       : Rs. {metrics['avg_loss']:+,.0f}")
    print(f"  Best Trade         : Rs. {metrics['best_trade']:+,.0f}")
    print(f"  Worst Trade        : Rs. {metrics['worst_trade']:+,.0f}")
    print(f"\n  Profit Factor      : {metrics['profit_factor']}  (>1.5 is good)")
    print(f"  Max Drawdown       : Rs. {metrics['max_drawdown']:,.0f}")
    print(f"  Sharpe Ratio       : {metrics['sharpe_ratio']}  (>1.0 is good)")
    print(f"\n  Max Win Streak     : {metrics['max_win_streak']} weeks")
    print(f"  Max Loss Streak    : {metrics['max_loss_streak']} weeks")

    # Verdict
    print("\n" + "=" * 68)
    print("   VERDICT")
    print("=" * 68)

    wr  = metrics['win_rate_pct']
    pf  = metrics['profit_factor']
    dd  = abs(metrics['max_drawdown'])
    sr  = metrics['sharpe_ratio']

    issues = []
    greens = []

    if wr >= 60:  greens.append(f"✅ Win rate {wr}% is strong (target >60%)")
    else:         issues.append(f"⚠️  Win rate {wr}% is below target of 60%")

    if pf >= 1.5: greens.append(f"✅ Profit factor {pf} is good (target >1.5)")
    else:         issues.append(f"⚠️  Profit factor {pf} is below target of 1.5")

    if dd <= 5000: greens.append(f"✅ Max drawdown Rs.{dd:,.0f} is manageable")
    else:          issues.append(f"⚠️  Max drawdown Rs.{dd:,.0f} — review position sizing")

    if sr >= 1.0: greens.append(f"✅ Sharpe ratio {sr} is acceptable (target >1.0)")
    else:         issues.append(f"⚠️  Sharpe ratio {sr} is below 1.0")

    for g in greens: print(f"  {g}")
    for i in issues: print(f"  {i}")

    if not issues:
        print("\n  🟢 Strategy looks viable for paper trading!")
    elif len(issues) <= 2:
        print("\n  🟡 Strategy has potential but needs refinement before live trading")
    else:
        print("\n  🔴 Strategy needs significant improvement — do not trade live yet")

    print("=" * 68)

    # Save to CSV
    df['cumulative_pnl'] = pd.DataFrame(trades)['pnl_1_lot'].cumsum()
    df.to_csv('backtest_results.csv', index=False)
    print("\n✅ Full trade log saved to backtest_results.csv")
    print("   Next step: signal_engine.py (Phase 5)")


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

if __name__ == '__main__':

    print("=" * 68)
    print("  KAIT — Phase 4: Backtesting")
    print("=" * 68)

    # Load candles
    print("\n⏳ Loading historical candles from database...")
    candles = load_candles()
    print(f"  Loaded {len(candles)} daily candles ({candles['date'].min().date()} to {candles['date'].max().date()})")

    if len(candles) < 20:
        print("  ❌ Not enough data. Run historical_data.py first.")
        exit()

    # Run backtest
    print("\n⏳ Running backtest — ATM Short Straddle strategy...")
    trades = backtest_short_straddle(candles, iv_assumption=0.12, lot_size=50)
    print(f"  Found {len(trades)} complete weekly trades")

    if not trades:
        print("  ❌ No trades found. Check that your data has both Mondays and Thursdays.")
        exit()

    # Calculate metrics
    metrics = calculate_metrics(trades)

    # Print full results
    print_results(trades, metrics)