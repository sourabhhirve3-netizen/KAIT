import os
import json
import time
import sqlite3
import pandas as pd
from datetime import datetime, date, timedelta
from kiteconnect import KiteConnect
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────────────────────
# DATABASE SETUP
# All data is stored in a single file: kait.db
# Think of it like an Excel workbook with multiple sheets
# ─────────────────────────────────────────────────────────────

DB_PATH = 'kait.db'

def get_connection():
    """Open a connection to the SQLite database."""
    return sqlite3.connect(DB_PATH)


def create_tables():
    """
    Create all tables if they don't exist yet.
    Safe to run multiple times — won't overwrite existing data.
    """
    conn = get_connection()
    c = conn.cursor()

    # Table 1: Nifty daily candles (OHLC)
    c.execute('''
        CREATE TABLE IF NOT EXISTS nifty_candles (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            date        TEXT NOT NULL,
            open        REAL,
            high        REAL,
            low         REAL,
            close       REAL,
            volume      INTEGER,
            UNIQUE(date)
        )
    ''')

    # Table 2: Option chain snapshots (saved every time you run option_chain.py)
    c.execute('''
        CREATE TABLE IF NOT EXISTS option_chain_snapshots (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp       TEXT NOT NULL,
            expiry          TEXT NOT NULL,
            strike          REAL NOT NULL,
            option_type     TEXT NOT NULL,
            ltp             REAL,
            oi              INTEGER,
            volume          INTEGER,
            bid             REAL,
            ask             REAL
        )
    ''')

    # Table 3: Calculated features (saved every time you run features.py)
    c.execute('''
        CREATE TABLE IF NOT EXISTS features_log (
            id                          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp                   TEXT NOT NULL,
            spot_price                  REAL,
            atm_strike                  REAL,
            expiry                      TEXT,
            dte                         INTEGER,
            pcr                         REAL,
            sentiment                   TEXT,
            max_pain                    REAL,
            distance_from_max_pain      REAL,
            support                     REAL,
            resistance                  REAL,
            atm_ce_iv                   REAL,
            atm_pe_iv                   REAL,
            iv_skew                     REAL,
            ce_delta                    REAL,
            ce_gamma                    REAL,
            ce_theta                    REAL,
            ce_vega                     REAL,
            pe_delta                    REAL,
            pe_gamma                    REAL,
            pe_theta                    REAL,
            pe_vega                     REAL,
            total_ce_oi                 INTEGER,
            total_pe_oi                 INTEGER,
            ce_oi_concentration_pct     REAL,
            pe_oi_concentration_pct     REAL,
            total_ce_volume             INTEGER,
            total_pe_volume             INTEGER
        )
    ''')

    # Table 4: Paper trades log (used in Phase 7)
    c.execute('''
        CREATE TABLE IF NOT EXISTS paper_trades (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp       TEXT NOT NULL,
            action          TEXT,
            symbol          TEXT,
            strike          REAL,
            option_type     TEXT,
            expiry          TEXT,
            entry_price     REAL,
            exit_price      REAL,
            quantity        INTEGER,
            pnl             REAL,
            status          TEXT,
            reason          TEXT
        )
    ''')

    conn.commit()
    conn.close()
    print("✅ Database tables ready — kait.db")


# ─────────────────────────────────────────────────────────────
# SAVE FUNCTIONS
# ─────────────────────────────────────────────────────────────

def save_features(features: dict):
    """Save a features snapshot to the database."""
    conn = get_connection()
    c = conn.cursor()

    cols = [
        'timestamp', 'spot_price', 'atm_strike', 'expiry', 'dte',
        'pcr', 'sentiment', 'max_pain', 'distance_from_max_pain',
        'support', 'resistance', 'atm_ce_iv', 'atm_pe_iv', 'iv_skew',
        'ce_delta', 'ce_gamma', 'ce_theta', 'ce_vega',
        'pe_delta', 'pe_gamma', 'pe_theta', 'pe_vega',
        'total_ce_oi', 'total_pe_oi',
        'ce_oi_concentration_pct', 'pe_oi_concentration_pct',
        'total_ce_volume', 'total_pe_volume'
    ]

    values = [features.get(col) for col in cols]
    placeholders = ', '.join(['?' for _ in cols])
    col_names = ', '.join(cols)

    c.execute(f'INSERT INTO features_log ({col_names}) VALUES ({placeholders})', values)
    conn.commit()
    conn.close()
    print(f"  ✅ Features saved to database ({features.get('timestamp')})")


def save_option_chain(chain_df: pd.DataFrame, expiry: str):
    """Save an option chain snapshot to the database."""
    conn = get_connection()
    c = conn.cursor()
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    rows = []
    for _, row in chain_df.iterrows():
        rows.append((
            timestamp,
            expiry,
            row.get('Strike', 0),
            row.get('Type', ''),
            row.get('LTP', 0),
            row.get('OI', 0),
            row.get('Volume', 0),
            row.get('Bid', 0),
            row.get('Ask', 0),
        ))

    c.executemany('''
        INSERT INTO option_chain_snapshots
        (timestamp, expiry, strike, option_type, ltp, oi, volume, bid, ask)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', rows)

    conn.commit()
    conn.close()
    print(f"  ✅ Option chain snapshot saved ({len(rows)} rows)")


def save_candles(candles_df: pd.DataFrame):
    """Save OHLC candles to the database. Skips duplicates."""
    conn = get_connection()
    c = conn.cursor()
    saved, skipped = 0, 0

    for _, row in candles_df.iterrows():
        try:
            c.execute('''
                INSERT OR IGNORE INTO nifty_candles (date, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (str(row['date']), row['open'], row['high'], row['low'], row['close'], row.get('volume', 0)))
            saved += 1
        except Exception:
            skipped += 1

    conn.commit()
    conn.close()
    print(f"  ✅ Candles saved: {saved} new, {skipped} skipped (duplicates)")


# ─────────────────────────────────────────────────────────────
# FETCH HISTORICAL CANDLES FROM KITE
# ─────────────────────────────────────────────────────────────

def fetch_and_store_candles(kite, months_back=12):
    """
    Fetch up to 12 months of daily Nifty candles from Kite.
    Kite allows max 400 days of daily data per call.
    We split into chunks of 90 days to be safe.
    """
    print(f"\n⏳ Fetching {months_back} months of Nifty daily candles...")

    end_date   = date.today()
    start_date = end_date - timedelta(days=months_back * 30)

    # Kite instrument token for Nifty 50 index
    instrument_token = 256265

    all_candles = []
    chunk_start = start_date

    while chunk_start < end_date:
        chunk_end = min(chunk_start + timedelta(days=90), end_date)

        try:
            data = kite.historical_data(
                instrument_token,
                from_date=chunk_start,
                to_date=chunk_end,
                interval='day'
            )

            for candle in data:
                all_candles.append({
                    'date':   str(candle['date'])[:10],
                    'open':   candle['open'],
                    'high':   candle['high'],
                    'low':    candle['low'],
                    'close':  candle['close'],
                    'volume': candle.get('volume', 0)
                })

            print(f"  Fetched {len(data)} candles: {chunk_start} to {chunk_end}")
            time.sleep(0.4)  # Respect rate limits

        except Exception as e:
            print(f"  ⚠️  Error fetching {chunk_start} to {chunk_end}: {e}")

        chunk_start = chunk_end + timedelta(days=1)

    if all_candles:
        df = pd.DataFrame(all_candles)
        save_candles(df)
        print(f"\n  Total candles fetched: {len(all_candles)}")
    else:
        print("  ⚠️  No candle data returned")

    return all_candles


# ─────────────────────────────────────────────────────────────
# READ FUNCTIONS
# ─────────────────────────────────────────────────────────────

def get_candles(days_back=365) -> pd.DataFrame:
    """Retrieve candles from the database as a DataFrame."""
    conn = get_connection()
    since = (date.today() - timedelta(days=days_back)).isoformat()
    df = pd.read_sql_query(
        'SELECT * FROM nifty_candles WHERE date >= ? ORDER BY date ASC',
        conn, params=(since,)
    )
    conn.close()
    return df


def get_features_history(days_back=30) -> pd.DataFrame:
    """Retrieve feature log history as a DataFrame."""
    conn = get_connection()
    since = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
    df = pd.read_sql_query(
        'SELECT * FROM features_log WHERE timestamp >= ? ORDER BY timestamp ASC',
        conn, params=(since,)
    )
    conn.close()
    return df


def get_database_summary():
    """Print a summary of what's in the database."""
    conn = get_connection()
    c = conn.cursor()

    tables = {
        'nifty_candles':            'SELECT COUNT(*), MIN(date), MAX(date) FROM nifty_candles',
        'option_chain_snapshots':   'SELECT COUNT(*), MIN(timestamp), MAX(timestamp) FROM option_chain_snapshots',
        'features_log':             'SELECT COUNT(*), MIN(timestamp), MAX(timestamp) FROM features_log',
        'paper_trades':             'SELECT COUNT(*), MIN(timestamp), MAX(timestamp) FROM paper_trades',
    }

    print("\n" + "=" * 58)
    print("       KAIT DATABASE SUMMARY")
    print("=" * 58)

    for table, query in tables.items():
        try:
            c.execute(query)
            row = c.fetchone()
            count = row[0]
            earliest = str(row[1])[:16] if row[1] else 'empty'
            latest   = str(row[2])[:16] if row[2] else 'empty'
            print(f"\n  [{table}]")
            print(f"    Rows    : {count}")
            if count > 0:
                print(f"    Earliest: {earliest}")
                print(f"    Latest  : {latest}")
        except Exception as e:
            print(f"  [{table}] Error: {e}")

    print("\n" + "=" * 58)
    conn.close()


# ─────────────────────────────────────────────────────────────
# MAIN — RUN FULL SETUP
# ─────────────────────────────────────────────────────────────

if __name__ == '__main__':

    print("=" * 58)
    print("  KAIT — Phase 3: Historical Database Setup")
    print("=" * 58)

    # Step 1: Create all tables
    print("\n[1/4] Creating database tables...")
    create_tables()

    # Step 2: Connect to Kite
    print("\n[2/4] Connecting to Kite...")
    with open('access_token.txt') as f:
        token = f.read().strip()

    kite = KiteConnect(api_key=os.getenv('KITE_API_KEY'))
    kite.set_access_token(token)
    print("  ✅ Kite connected")

    # Step 3: Fetch and store 12 months of candles
    print("\n[3/4] Fetching historical candles...")
    fetch_and_store_candles(kite, months_back=12)

    # Step 4: Save today's features if available
    print("\n[4/4] Saving today's features snapshot...")
    if os.path.exists('features.json'):
        with open('features.json') as f:
            features = json.load(f)
        save_features(features)
    else:
        print("  ⚠️  features.json not found — run features.py first")

    # Step 5: Save today's option chain if available
    if os.path.exists('option_chain.csv'):
        chain = pd.read_csv('option_chain.csv')
        expiry = '2026-06-23'
        if 'expiry' in chain.columns:
            expiry = str(chain['expiry'].iloc[0])[:10]
        save_option_chain(chain, expiry)

    # Final summary
    get_database_summary()

    print("\n✅ Phase 3 complete — kait.db is ready")
    print("   Next step: backtester.py (Phase 4)")