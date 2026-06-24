# feature_logger.py

import sqlite3
import json
import os

DB_PATH = "kait.db"


def get_connection():
    return sqlite3.connect(DB_PATH)


def save_feature_snapshot():

    if not os.path.exists("features.json"):
        print("❌ features.json not found")
        return

    with open("features.json", "r") as f:
        features = json.load(f)

    conn = get_connection()
    c = conn.cursor()

    timestamp = features["timestamp"]

    # Prevent duplicate inserts
    c.execute(
        """
        SELECT COUNT(*)
        FROM features_log
        WHERE timestamp = ?
        """,
        (timestamp,)
    )

    exists = c.fetchone()[0]

    if exists:
        print("⚠️ Snapshot already exists")
        conn.close()
        return

    cols = [
        'timestamp',
        'spot_price',
        'atm_strike',
        'expiry',
        'dte',
        'pcr',
        'sentiment',
        'max_pain',
        'distance_from_max_pain',
        'support',
        'resistance',
        'atm_ce_iv',
        'atm_pe_iv',
        'iv_skew',
        'ce_delta',
        'ce_gamma',
        'ce_theta',
        'ce_vega',
        'pe_delta',
        'pe_gamma',
        'pe_theta',
        'pe_vega',
        'total_ce_oi',
        'total_pe_oi',
        'ce_oi_concentration_pct',
        'pe_oi_concentration_pct',
        'support_distance_pct',
        'resistance_distance_pct',
        'max_pain_distance_pct',
        'oi_ratio_top3',
        'iv_average',
        'iv_regime',
        'oi_difference_pct',
        'total_ce_volume',
        'total_pe_volume'
    ]

    values = [features.get(col) for col in cols]

    placeholders = ",".join(["?"] * len(cols))

    c.execute(
        f"""
        INSERT INTO features_log
        ({",".join(cols)})
        VALUES ({placeholders})
        """,
        values
    )

    conn.commit()
    conn.close()

    print("\n✅ Feature snapshot saved")
    print(f"Timestamp: {timestamp}")


if __name__ == "__main__":

    print("=" * 60)
    print("KAIT — Feature Logger")
    print("=" * 60)

    save_feature_snapshot()