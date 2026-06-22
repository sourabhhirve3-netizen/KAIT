import os
import json
import sqlite3
from datetime import datetime, date, timedelta
from dotenv import load_dotenv

load_dotenv()

DB_PATH    = 'kait.db'
CONFIG_FILE = 'risk_config.json'

# ─────────────────────────────────────────────────────────────
# RISK CONFIGURATION
# Edit these values to match your account size and risk appetite.
# They are saved to risk_config.json on first run.
# ─────────────────────────────────────────────────────────────

DEFAULT_CONFIG = {
    # Your total trading capital in Rs.
    # Only use money you can afford to lose entirely.
    'total_capital':            100000,

    # Maximum % of capital to risk on a single trade
    # 2% of Rs.1,00,000 = Rs.2,000 max risk per trade
    'max_risk_per_trade_pct':   2.0,

    # Maximum total loss allowed in a single day before halting
    'daily_loss_limit':         2000,

    # Maximum number of open positions at once
    'max_concurrent_positions': 2,

    # Maximum % of capital deployed at any time
    'max_exposure_pct':         20.0,

    # Consecutive losing trades before pausing for 1 hour
    'loss_streak_limit':        3,

    # Nifty lot size (fixed by NSE)
    'lot_size':                 50,

    # Minimum margin required per lot (approx for short straddle)
    # Update this based on your broker's actual margin requirement
    'margin_per_lot':           85000,
}


# ─────────────────────────────────────────────────────────────
# CONFIG — Load or create
# ─────────────────────────────────────────────────────────────

def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            return json.load(f)
    else:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(DEFAULT_CONFIG, f, indent=2)
        print(f"  ✅ Default risk config created: {CONFIG_FILE}")
        print(f"  ⚠️  Edit {CONFIG_FILE} to set your actual capital before trading!")
        return DEFAULT_CONFIG


def save_config(config: dict):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)


# ─────────────────────────────────────────────────────────────
# DAILY STATE — Track today's P&L and trades
# ─────────────────────────────────────────────────────────────

STATE_FILE = 'risk_state.json'

def load_state() -> dict:
    today = date.today().isoformat()
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            state = json.load(f)
        # Reset if it's a new day
        if state.get('date') != today:
            state = _fresh_state(today)
            save_state(state)
    else:
        state = _fresh_state(today)
        save_state(state)
    return state

def _fresh_state(today: str) -> dict:
    return {
        'date':               today,
        'daily_pnl':          0.0,
        'trades_today':       0,
        'open_positions':     0,
        'consecutive_losses': 0,
        'circuit_breaker':    False,
        'circuit_reason':     '',
        'halted_until':       '',
        'capital_deployed':   0.0,
    }

def save_state(state: dict):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)


# ─────────────────────────────────────────────────────────────
# CIRCUIT BREAKER — Check if trading is halted
# ─────────────────────────────────────────────────────────────

def check_circuit_breaker(state: dict) -> tuple:
    """Returns (is_halted: bool, reason: str)"""
    if state.get('circuit_breaker'):
        halted_until = state.get('halted_until', '')
        if halted_until:
            halt_time = datetime.fromisoformat(halted_until)
            if datetime.now() < halt_time:
                mins_left = int((halt_time - datetime.now()).seconds / 60)
                return True, f"Circuit breaker active — resumes in {mins_left} minutes ({halted_until})"
            else:
                # Halt period expired — reset
                state['circuit_breaker'] = False
                state['circuit_reason']  = ''
                state['halted_until']    = ''
                save_state(state)
                return False, ''
        return True, state.get('circuit_reason', 'Circuit breaker active')
    return False, ''


def trigger_circuit_breaker(state: dict, reason: str, pause_minutes: int = 60):
    """Trigger a circuit breaker — halt trading for pause_minutes."""
    resume_time = datetime.now() + timedelta(minutes=pause_minutes)
    state['circuit_breaker'] = True
    state['circuit_reason']  = reason
    state['halted_until']    = resume_time.isoformat()
    save_state(state)
    print(f"\n  🚨 CIRCUIT BREAKER TRIGGERED: {reason}")
    print(f"     Trading halted until: {resume_time.strftime('%H:%M:%S')}")


# ─────────────────────────────────────────────────────────────
# POSITION SIZING
# ─────────────────────────────────────────────────────────────

def calculate_position_size(signal: dict, config: dict) -> dict:
    """
    Calculate how many lots to trade based on:
    - Capital available
    - Max risk per trade
    - Margin requirement
    - Current exposure
    """
    capital       = config['total_capital']
    max_risk_pct  = config['max_risk_per_trade_pct']
    lot_size      = config['lot_size']
    margin_per_lot = config['margin_per_lot']
    max_exp_pct   = config['max_exposure_pct']

    trade = signal.get('trade', {})
    if not trade:
        return {'lots': 0, 'reason': 'No trade details in signal'}

    # Max loss per unit = stop loss value × lot size
    sl_value    = trade.get('stop_loss_value', 0)
    max_risk_rs = capital * max_risk_pct / 100

    # Lots based on risk
    if sl_value > 0:
        lots_by_risk = int(max_risk_rs / (sl_value * lot_size))
    else:
        lots_by_risk = 1

    # Lots based on margin available
    max_exposure = capital * max_exp_pct / 100
    lots_by_margin = int(max_exposure / margin_per_lot)

    # Take the more conservative of the two
    recommended_lots = max(1, min(lots_by_risk, lots_by_margin))

    return {
        'recommended_lots': recommended_lots,
        'lots_by_risk':     lots_by_risk,
        'lots_by_margin':   lots_by_margin,
        'max_risk_per_trade': round(max_risk_rs, 2),
        'margin_required':  recommended_lots * margin_per_lot,
        'capital_required': recommended_lots * margin_per_lot,
        'reasoning':        f"Risk-based: {lots_by_risk} lots | Margin-based: {lots_by_margin} lots → Using {recommended_lots} lot(s)"
    }


# ─────────────────────────────────────────────────────────────
# MAIN RISK VALIDATION
# ─────────────────────────────────────────────────────────────

def validate_signal(signal: dict) -> dict:
    """
    Takes a signal from signal_engine.py and runs all risk checks.
    Returns an approved or rejected decision with full reasoning.
    """
    config = load_config()
    state  = load_state()

    checks = []
    passed = []
    failed = []

    # ── CHECK 1: Circuit Breaker ──────────────────────────────
    halted, halt_reason = check_circuit_breaker(state)
    if halted:
        failed.append(f"❌ CIRCUIT BREAKER: {halt_reason}")
        checks.append(('circuit_breaker', False))
    else:
        passed.append("✅ No circuit breaker active")
        checks.append(('circuit_breaker', True))

    # ── CHECK 2: Signal must be SELL_STRADDLE ─────────────────
    if signal.get('signal') != 'SELL_STRADDLE':
        failed.append(f"❌ Signal is {signal.get('signal')} — no trade to validate")
        checks.append(('signal_type', False))
    else:
        passed.append(f"✅ Signal is SELL_STRADDLE")
        checks.append(('signal_type', True))

    # ── CHECK 3: Daily Loss Limit ─────────────────────────────
    daily_pnl       = state['daily_pnl']
    daily_limit     = config['daily_loss_limit']
    daily_limit_ok  = daily_pnl > -abs(daily_limit)

    if daily_limit_ok:
        passed.append(f"✅ Daily P&L Rs.{daily_pnl:+,.0f} is within limit (limit: -Rs.{daily_limit:,.0f})")
        checks.append(('daily_loss_limit', True))
    else:
        failed.append(f"❌ Daily loss limit hit — P&L Rs.{daily_pnl:+,.0f} (limit: -Rs.{daily_limit:,.0f})")
        checks.append(('daily_loss_limit', False))
        trigger_circuit_breaker(state, f"Daily loss limit of Rs.{daily_limit} reached", pause_minutes=1440)

    # ── CHECK 4: Max Concurrent Positions ────────────────────
    open_pos     = state['open_positions']
    max_pos      = config['max_concurrent_positions']
    positions_ok = open_pos < max_pos

    if positions_ok:
        passed.append(f"✅ Open positions {open_pos} is below limit ({max_pos})")
        checks.append(('max_positions', True))
    else:
        failed.append(f"❌ Already at max positions ({open_pos}/{max_pos})")
        checks.append(('max_positions', False))

    # ── CHECK 5: Consecutive Loss Streak ─────────────────────
    loss_streak      = state['consecutive_losses']
    streak_limit     = config['loss_streak_limit']
    streak_ok        = loss_streak < streak_limit

    if streak_ok:
        passed.append(f"✅ Loss streak {loss_streak} is below limit ({streak_limit})")
        checks.append(('loss_streak', True))
    else:
        failed.append(f"❌ Loss streak of {loss_streak} — pausing trading for 1 hour")
        checks.append(('loss_streak', False))
        trigger_circuit_breaker(state, f"{loss_streak} consecutive losses — cooling off", pause_minutes=60)

    # ── CHECK 6: Capital Available ────────────────────────────
    deployed       = state['capital_deployed']
    max_exposure   = config['total_capital'] * config['max_exposure_pct'] / 100
    capital_ok     = deployed < max_exposure

    if capital_ok:
        passed.append(f"✅ Capital deployed Rs.{deployed:,.0f} is within exposure limit (Rs.{max_exposure:,.0f})")
        checks.append(('capital_exposure', True))
    else:
        failed.append(f"❌ Capital exposure limit reached (Rs.{deployed:,.0f} / Rs.{max_exposure:,.0f})")
        checks.append(('capital_exposure', False))

    # ── CHECK 7: Stop Loss Present ────────────────────────────
    trade    = signal.get('trade', {})
    sl_value = trade.get('stop_loss_value', 0)
    sl_ok    = sl_value > 0

    if sl_ok:
        passed.append(f"✅ Stop loss defined at Rs.{sl_value} combined straddle value")
        checks.append(('stop_loss', True))
    else:
        failed.append("❌ No stop loss defined in signal — cannot proceed")
        checks.append(('stop_loss', False))

    # ── POSITION SIZING ───────────────────────────────────────
    sizing = calculate_position_size(signal, config)

    # ── FINAL DECISION ────────────────────────────────────────
    approved = len(failed) == 0

    result = {
        'timestamp':   datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'approved':    approved,
        'decision':    'APPROVED' if approved else 'REJECTED',
        'passed':      passed,
        'failed':      failed,
        'sizing':      sizing,
        'config_used': {
            'total_capital':     config['total_capital'],
            'daily_loss_limit':  config['daily_loss_limit'],
            'max_risk_pct':      config['max_risk_per_trade_pct'],
            'max_positions':     config['max_concurrent_positions'],
        },
        'state': {
            'daily_pnl':          state['daily_pnl'],
            'trades_today':       state['trades_today'],
            'open_positions':     state['open_positions'],
            'consecutive_losses': state['consecutive_losses'],
        }
    }

    return result


# ─────────────────────────────────────────────────────────────
# UPDATE STATE AFTER TRADE
# Call this after a trade is executed or closed
# ─────────────────────────────────────────────────────────────

def record_trade_entry(lots: int):
    """Call this when a trade is entered."""
    config = load_config()
    state  = load_state()
    state['open_positions']   += 1
    state['trades_today']     += 1
    state['capital_deployed'] += lots * config['margin_per_lot']
    save_state(state)
    print(f"  📝 Trade entry recorded — open positions: {state['open_positions']}")


def record_trade_exit(pnl: float, lots: int):
    """Call this when a trade is closed. pnl = positive for profit, negative for loss."""
    config = load_config()
    state  = load_state()
    state['daily_pnl']        += pnl
    state['open_positions']    = max(0, state['open_positions'] - 1)
    state['capital_deployed']  = max(0, state['capital_deployed'] - lots * config['margin_per_lot'])

    if pnl < 0:
        state['consecutive_losses'] += 1
    else:
        state['consecutive_losses'] = 0  # Reset on a win

    # Check if daily loss limit is now breached
    if state['daily_pnl'] <= -abs(config['daily_loss_limit']):
        trigger_circuit_breaker(state, f"Daily loss limit of Rs.{config['daily_loss_limit']} reached", 1440)

    # Check loss streak
    if state['consecutive_losses'] >= config['loss_streak_limit']:
        trigger_circuit_breaker(state, f"{state['consecutive_losses']} consecutive losses", 60)

    save_state(state)
    print(f"  📝 Trade exit recorded — P&L: Rs.{pnl:+,.0f} | Daily P&L: Rs.{state['daily_pnl']:+,.0f}")


# ─────────────────────────────────────────────────────────────
# PRINT RISK REPORT
# ─────────────────────────────────────────────────────────────

def print_risk_report(result: dict):
    approved = result['approved']
    sizing   = result.get('sizing', {})
    state    = result.get('state', {})
    cfg      = result.get('config_used', {})

    print("\n" + "=" * 60)
    print("   KAIT — RISK ENGINE REPORT")
    print(f"   {result['timestamp']}")
    print("=" * 60)

    print(f"\n  [ACCOUNT STATUS]")
    print(f"    Capital         : Rs. {cfg.get('total_capital', 0):,.0f}")
    print(f"    Daily P&L       : Rs. {state.get('daily_pnl', 0):+,.0f}")
    print(f"    Daily Limit     : Rs. {cfg.get('daily_loss_limit', 0):,.0f}")
    print(f"    Open Positions  : {state.get('open_positions', 0)}")
    print(f"    Loss Streak     : {state.get('consecutive_losses', 0)}")

    print(f"\n  [RISK CHECKS]")
    for p in result['passed']:
        print(f"    {p}")
    for f in result['failed']:
        print(f"    {f}")

    print(f"\n  [DECISION]")
    if approved:
        print(f"    Status          : 🟢 APPROVED")
        print(f"    Recommended     : {sizing.get('recommended_lots', 0)} lot(s)")
        print(f"    Sizing Logic    : {sizing.get('reasoning', '')}")
        print(f"    Margin Required : Rs. {sizing.get('margin_required', 0):,.0f}")
        print(f"    Max Risk        : Rs. {sizing.get('max_risk_per_trade', 0):,.0f}")
    else:
        print(f"    Status          : 🔴 REJECTED")
        print(f"    Reason          : {len(result['failed'])} risk check(s) failed")
        for f in result['failed']:
            print(f"    {f}")

    print("=" * 60)


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

if __name__ == '__main__':

    print("=" * 60)
    print("  KAIT — Phase 6: Risk Engine")
    print("=" * 60)

    # Load today's signal
    if not os.path.exists('signal.json'):
        print("\n❌ signal.json not found — run signal_engine.py first")
        exit()

    with open('signal.json') as f:
        signal = json.load(f)

    print(f"\n  Signal     : {signal.get('signal')}")
    print(f"  Confidence : {int(signal.get('confidence', 0) * 100)}%")

    # Load/create config
    print("\n⏳ Loading risk configuration...")
    config = load_config()
    print(f"  Capital    : Rs. {config['total_capital']:,.0f}")
    print(f"  Daily Limit: Rs. {config['daily_loss_limit']:,.0f}")

    # Validate signal
    print("\n⏳ Running risk validation...")
    result = validate_signal(signal)

    # Print report
    print_risk_report(result)

    # Save result
    with open('risk_result.json', 'w') as f:
        json.dump(result, f, indent=2)

    print(f"\n✅ Risk result saved to risk_result.json")
    if result['approved']:
        print(f"   Next step: paper_trader.py (Phase 7) — simulate this trade")
    else:
        print(f"   Trade rejected — review the failed checks above")
        print(f"   Edit risk_config.json to adjust your limits if needed")