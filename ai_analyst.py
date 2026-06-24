import os
import json
import requests
from datetime import datetime
import time
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
MODEL             = "claude-sonnet-4-6"
OUTPUT_FILE       = "ai_analysis.json"
RAW_RESPONSE_FILE = "raw_claude_response.txt"
VERSION = "1.1"

# ─────────────────────────────────────────────────────────────
# CALL CLAUDE API
# ─────────────────────────────────────────────────────────────

def call_claude(prompt: str, system: str) -> dict:
    """Send a prompt to Claude and return the response text."""

    if not ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY not found in .env file")

    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key":         ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type":      "application/json",
        },
        json={
            "model":      MODEL,
            "max_tokens": 1500,
            "system":     system,
            "messages":   [{"role": "user", "content": prompt}],
        },
        timeout=30,
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"Claude API error {response.status_code}: {response.text}"
        )

    data = response.json()

    return {
        "text": data["content"][0]["text"],
        "usage": data.get("usage", {})
    }


# ─────────────────────────────────────────────────────────────
# PARSE STRUCTURED JSON FROM CLAUDE RESPONSE
# ─────────────────────────────────────────────────────────────

def parse_json_response(text: str) -> dict:
    """
    Extract JSON from Claude's response.
    Claude is instructed to return only JSON — but we strip
    markdown fences defensively in case they appear.
    """
    # Strip markdown code fences if present
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        # Remove first and last fence lines
        lines = [l for l in lines if not l.startswith("```")]
        cleaned = "\n".join(lines).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        print(f"  ⚠️  Could not parse JSON from Claude response: {e}")
        print(f"  Raw response:\n{text[:500]}")
        return {}

# ─────────────────────────────────────────────────────────────
# VALIDATE AI RESPONSE SCHEMA
# ─────────────────────────────────────────────────────────────

def validate_analysis_schema(data: dict) -> bool:

    required_fields = [
        "market_regime",
        "analysis_strength",
        "key_observations",
        "volatility_assessment",
        "theta_assessment",
        "oi_assessment",
        "trade_context",
        "risk_factors",
        "invalidation",
        "anomalies",
        "analyst_note"
    ]

    missing = [
        field
        for field in required_fields
        if field not in data
    ]

    if missing:
        print(
            f"\n⚠️ Missing fields: "
            f"{', '.join(missing)}"
        )
        return False

    return True

# ─────────────────────────────────────────────────────────────
# SYSTEM PROMPT
# Claude's role: analyst, not decision maker.
# It explains what the data means — never says "buy" or "sell".
# ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a senior quantitative analyst specialising in Nifty 50 index options.

Your role is to EXPLAIN and INTERPRET market data — not to make buy/sell decisions.
The trading decision has already been made by a deterministic signal engine.
Your job is to explain WHY the data supports or contradicts that decision,
identify risks the rules may have missed, and flag any anomalies.

Rules you must follow:
- Never say "buy", "sell", "enter", or "exit" — you are an analyst, not a trader
- Be specific and quantitative — reference actual numbers from the data
- Be concise — each observation should be one clear sentence
- Analysis strength must be between 0.0 and 1.0
- Analysis strength is not statistical confidence
- It represents how strongly the market data supports your interpretation
- Respond ONLY with valid JSON — no preamble, no markdown, no explanation outside the JSON
"""


# ─────────────────────────────────────────────────────────────
# BUILD ANALYSIS PROMPT
# ─────────────────────────────────────────────────────────────

def build_prompt(features: dict, signal: dict, risk_result: dict) -> str:
    """
    Build a structured prompt from features, signal, and risk data.
    Only sends what Claude needs — avoids token waste.
    """

    trade      = signal.get("trade", {})
    passed     = signal.get("passed", [])
    failed     = signal.get("failed", [])
    sizing     = risk_result.get("sizing", {})
    risk_state = risk_result.get("state", {})

    prompt = f"""
Analyse the following Nifty 50 options market data and return a JSON response.

=== MARKET SNAPSHOT ===
Timestamp           : {features.get('timestamp')}
Nifty Spot          : {features.get('spot_price')}
ATM Strike          : {features.get('atm_strike')}
Expiry              : {features.get('expiry')}
Days to Expiry (DTE): {features.get('dte')}

=== SENTIMENT ===
PCR                 : {features.get('pcr')}  (>1.2 Bullish, <0.8 Bearish, else Neutral)
Sentiment Label     : {features.get('sentiment')}

=== KEY LEVELS ===
Max Pain            : {features.get('max_pain')}
Distance from Max Pain: {features.get('distance_from_max_pain')} pts
Support (max PE OI) : {features.get('support')}
Resistance (max CE OI): {features.get('resistance')}

=== LIVE ATM OPTIONS ===
ATM CE Symbol       : {features.get('atm_ce_symbol')}
ATM PE Symbol       : {features.get('atm_pe_symbol')}
ATM CE LTP          : {features.get('atm_ce_ltp')}
ATM PE LTP          : {features.get('atm_pe_ltp')}

=== VOLATILITY ===
ATM CE IV           : {features.get('atm_ce_iv')}%
ATM PE IV           : {features.get('atm_pe_iv')}%
IV Skew (PE-CE)     : {features.get('iv_skew')}  (positive = downside fear)
IV Skew Interpretation: {features.get('iv_skew_interpretation')}

=== GREEKS (ATM CE) ===
Delta : {features.get('ce_delta')}
Gamma : {features.get('ce_gamma')}
Theta : {features.get('ce_theta')} Rs/day
Vega  : {features.get('ce_vega')}

=== GREEKS (ATM PE) ===
Delta : {features.get('pe_delta')}
Gamma : {features.get('pe_gamma')}
Theta : {features.get('pe_theta')} Rs/day
Vega  : {features.get('pe_vega')}

=== OI STATS ===
Total CE OI         : {features.get('total_ce_oi'):,}
Total PE OI         : {features.get('total_pe_oi'):,}
CE OI Concentration : {features.get('ce_oi_concentration_pct')}%  (top 3 strikes)
PE OI Concentration : {features.get('pe_oi_concentration_pct')}%  (top 3 strikes)

=== SIGNAL ENGINE RESULT ===
Signal              : {signal.get('signal')}
Confidence          : {int(signal.get('confidence', 0) * 100)}%
Filters passed      : {len(passed)}/{len(passed)+len(failed)}

Passed filters:
{chr(10).join(f"  - {p}" for p in passed)}

Failed filters:
{chr(10).join(f"  - {f}" for f in failed) if failed else "  - None"}

=== TRADE DETAILS ===
Strategy            : {trade.get('action', 'N/A')}
Strike              : {trade.get('atm_strike', 'N/A')}
Total Premium       : Rs.{trade.get('total_premium', 0)} per unit
Stop Loss Trigger   : Rs.{trade.get('stop_loss_value', 0)} combined
Breakeven Upper     : {trade.get('breakeven_upper', 'N/A')}
Breakeven Lower     : {trade.get('breakeven_lower', 'N/A')}

=== RISK ENGINE STATE ===
Daily P&L so far    : Rs.{risk_state.get('daily_pnl', 0):+,.0f}
Open Positions      : {risk_state.get('open_positions', 0)}
Consecutive Losses  : {risk_state.get('consecutive_losses', 0)}
Recommended Lots    : {sizing.get('recommended_lots', 0)}

=== YOUR TASK ===
Return ONLY this JSON structure — no text outside it:

{{
  "market_regime":"bullish | bearish | sideways | volatile | uncertain",
  "analysis_strength": 0.0,
  "key_observations": [
    "Observation 1 with specific numbers",
    "Observation 2 with specific numbers",
    "Observation 3 with specific numbers"
  ],
  "volatility_assessment": "One sentence on IV levels and what they imply",
  "theta_assessment": "One sentence on time decay and how it affects this trade",
  "oi_assessment": "One sentence on OI concentration and what big money is doing",
  "trade_context": "One sentence explaining why the data does or does not support the signal",
  "risk_factors": [
    "Risk 1 — specific to current data",
    "Risk 2 — specific to current data"
  ],
  "invalidation": "What specific market condition would make this analysis wrong",
  "anomalies": "Any unusual pattern in the data, or 'None detected'",
  "analyst_note": "One plain-English sentence summarising the overall situation for a beginner"
}}
"""

    return prompt.strip()


# ─────────────────────────────────────────────────────────────
# PRINT ANALYSIS
# ─────────────────────────────────────────────────────────────

def print_analysis(analysis: dict, features: dict, signal: dict):
    """Print the AI analysis in a clean readable format."""

    print("\n" + "=" * 62)
    print("   KAIT — AI ANALYST REPORT")
    print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 62)

    print(f"\n  [MARKET REGIME]")
    regime     = analysis.get("market_regime", "unknown").upper()
    analysis_strength = float(
        analysis.get("analysis_strength", 0)
    )
    regime_icon = {
        "BULLISH":   "📈",
        "BEARISH":   "📉",
        "SIDEWAYS":  "➡️",
        "UNCERTAIN": "❓",
    }.get(regime, "❓")

    print(f"    {regime_icon} {regime}  —  Analysis strength: {int(analysis_strength * 100)}%")
    print(f"    Signal engine confidence: {int(signal.get('confidence', 0) * 100)}%")

    print(f"\n  [KEY OBSERVATIONS]")
    for obs in analysis.get("key_observations", []):
        print(f"    • {obs}")

    print(f"\n  [ASSESSMENTS]")
    print(f"    Volatility : {analysis.get('volatility_assessment', 'N/A')}")
    print(f"    Theta      : {analysis.get('theta_assessment', 'N/A')}")
    print(f"    OI         : {analysis.get('oi_assessment', 'N/A')}")

    print(f"\n  [TRADE CONTEXT]")
    print(f"    {analysis.get('trade_context', 'N/A')}")

    print(f"\n  [RISK FACTORS]")
    for risk in analysis.get("risk_factors", []):
        print(f"    ⚠️  {risk}")

    print(f"\n  [INVALIDATION]")
    print(f"    {analysis.get('invalidation', 'N/A')}")

    anomalies = analysis.get("anomalies", "None detected")
    if anomalies.lower() != "none detected":
        print(f"\n  [ANOMALIES DETECTED]")
        print(f"    🔍 {anomalies}")

    print(f"\n  [ANALYST NOTE — PLAIN ENGLISH]")
    print(f"    💬 {analysis.get('analyst_note', 'N/A')}")

    print("\n" + "=" * 62)


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":

    print("=" * 62)
    print("  KAIT — Phase 8: AI Analyst")
    print("=" * 62)

    # ── Load features ────────────────────────────────────────
    if not os.path.exists("features.json"):
        print("\n❌ features.json not found — run features.py first")
        exit()

    with open("features.json") as f:
        features = json.load(f)

    # ── Load signal ──────────────────────────────────────────
    if not os.path.exists("signal.json"):
        print("\n❌ signal.json not found — run signal_engine.py first")
        exit()

    with open("signal.json") as f:
        signal = json.load(f)

    # ── Load risk result ─────────────────────────────────────
    if not os.path.exists("risk_result.json"):
        print("\n❌ risk_result.json not found — run risk_engine.py first")
        exit()

    with open("risk_result.json") as f:
        risk_result = json.load(f)

    # ── Print what we're analysing ───────────────────────────
    print(f"\n  Spot Price  : Rs.{features.get('spot_price')}")
    print(f"  ATM Strike  : {features.get('atm_strike')}")
    print(f"  Expiry      : {features.get('expiry')}  (DTE: {features.get('dte')})")
    print(f"  Signal      : {signal.get('signal')}  ({int(signal.get('confidence', 0)*100)}% confidence)")
    print(f"  PCR         : {features.get('pcr')}  ({features.get('sentiment')})")
    print(f"  ATM CE IV   : {features.get('atm_ce_iv')}%")
    print(f"  Max Pain    : {features.get('max_pain')}")

    # ── Build prompt and call Claude ─────────────────────────
    print(f"\n⏳ Sending data to Claude AI for analysis...")

    prompt = build_prompt(features, signal, risk_result)

    try:
        start_time = time.perf_counter()

        result = call_claude(
            prompt,
            SYSTEM_PROMPT
        )

        response_time_ms = round(
            (time.perf_counter() - start_time)
            * 1000,
            2
        )

        raw_response = result["text"]
        with open(
                RAW_RESPONSE_FILE,
                "w",
                encoding="utf-8"
        ) as f:
            f.write(raw_response)

        usage = result.get(
            "usage",
            {}
        )
    except Exception as e:
        print(f"\n❌ Claude API call failed: {e}")
        exit()

    # ── Parse response ───────────────────────────────────────
    analysis = parse_json_response(
        raw_response
    )

    if not analysis:

        print(
            "\n⚠️ First parse failed."
            " Retrying..."
        )

        try:

            retry_result = call_claude(
                prompt,
                SYSTEM_PROMPT
            )

            raw_response = retry_result["text"]

            with open(
                    RAW_RESPONSE_FILE,
                    "w",
                    encoding="utf-8"
            ) as f:
                f.write(raw_response)

            analysis = parse_json_response(
                raw_response
            )

        except Exception as e:

            print(
                f"\n❌ Retry failed: {e}"
            )

            exit()

    #if not analysis:
    #    print("\n❌ Could not parse AI response")
    #    print("Raw response:")
    #    print(raw_response)
    #    exit()

    # ── Validate schema ──────────────────────────────────────
    if not validate_analysis_schema(analysis):
        print("\n❌ Invalid analysis schema")
        print(f"Check {RAW_RESPONSE_FILE}")
        exit()

    # ── Print analysis ───────────────────────────────────────
    print_analysis(analysis, features, signal)

    # ── Save to file ─────────────────────────────────────────
    output = {
        "version": VERSION,

        "timestamp":
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),

        "api_metrics": {
            "response_time_ms": response_time_ms,
            "input_tokens": usage.get("input_tokens"),
            "output_tokens": usage.get("output_tokens")
        },

        "features_snapshot": {
            "spot_price": features.get("spot_price"),
            "atm_strike": features.get("atm_strike"),
            "expiry": features.get("expiry"),
            "dte": features.get("dte"),
            "pcr": features.get("pcr"),
            "sentiment": features.get("sentiment"),
            "atm_ce_iv": features.get("atm_ce_iv"),
            "atm_pe_iv": features.get("atm_pe_iv"),
            "max_pain": features.get("max_pain"),
        },

        "signal": signal.get("signal"),

        "analysis": analysis
    }

    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n✅ AI analysis saved to {OUTPUT_FILE}")
    print(f"   Next step: paper_trader.py (Phase 7) to simulate the trade")