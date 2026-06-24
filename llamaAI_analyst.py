import os
import json
import requests
from datetime import datetime
import time

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3.1:8b"
OUTPUT_FILE       = "ai_analysis.json"
RAW_RESPONSE_FILE = "raw_llama_response.txt"
VERSION = "1.1"

# ─────────────────────────────────────────────────────────────
# CALL Llama3 API
# ─────────────────────────────────────────────────────────────

def call_llama(prompt: str, system: str) -> dict:
    """
    Send prompt to local Ollama Llama model.
    """

    full_prompt = f"""
{system}

{prompt}
"""

    response = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL,
            "prompt": full_prompt,
            "stream": False,
            "format": "json"
        },
        timeout=180
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"Ollama error {response.status_code}: "
            f"{response.text}"
        )

    data = response.json()

    return {
        "text": data["response"],
        "usage": {
            "prompt_eval_count":
                data.get("prompt_eval_count"),

            "eval_count":
                data.get("eval_count")
        }
    }

# ─────────────────────────────────────────────────────────────
# CHECK OLLAMA CONNECTION
# ─────────────────────────────────────────────────────────────

def check_ollama() -> bool:

    try:
        requests.get(
            "http://localhost:11434",
            timeout=5
        )
        return True

    except Exception:
        return False


# ─────────────────────────────────────────────────────────────
# PARSE STRUCTURED JSON FROM Llama3 RESPONSE
# ─────────────────────────────────────────────────────────────

def parse_json_response(text: str) -> dict:
    """
    Extract JSON from Llama3's response.
    Llama3 is instructed to return only JSON — but we strip
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
        parsed = json.loads(cleaned)

        if isinstance(parsed, str):
            parsed = json.loads(parsed)

        return parsed
    except json.JSONDecodeError as e:
        print(f"  ⚠️  Could not parse JSON from Llama3 response: {e}")
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
        "analyst_note",
        "beginner_explanation",
        "todays_lesson"
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
# Llama3's role: analyst, not decision maker.
# It explains what the data means — never says "buy" or "sell".
# ─────────────────────────────────────────────────────────────

#SYSTEM_PROMPT = """You are a senior quantitative analyst specialising in Nifty 50 index options.
#
#Your role is to EXPLAIN and INTERPRET market data — not to make buy/sell decisions.
#The trading decision has already been made by a deterministic signal engine.
#Your job is to explain WHY the data supports or contradicts that decision,
#identify risks the rules may have missed, and flag any anomalies.
#
#Rules you must follow:
#- Never say "buy", "sell", "enter", or "exit" — you are an analyst, not a trader
#- Be specific and quantitative — reference actual numbers from the data
#- Be concise — each observation should be one clear sentence
#- Analysis strength must be between 0.0 and 1.0
#- Analysis strength is not statistical confidence
#- It represents how strongly the market data supports your interpretation
#- Respond ONLY with valid JSON — no preamble, no markdown, no explanation outside the JSON
#
#IMPORTANT:
#Return ONLY valid JSON.
#
#Do not wrap the JSON in markdown.
#Do not include explanations.
#Do not include code fences.
#Do not include introductory text.
#
#The first character of your response must be {
#The last character of your response must be }
#"""
SYSTEM_PROMPT = """
You are KAIT AI Analyst.

You are an experienced Nifty options trader, analyst and mentor.

Your audience is a retail trader who understands basic trading concepts
but may not understand advanced option-chain metrics.

Your job is to:

1. Explain what the data says.
2. Explain why it matters.
3. Explain the signal engine decision.
4. Highlight risks.
5. Teach the user something useful.

Rules:

* Never say buy, sell, enter or exit.
* Never override the signal engine.
* Use actual numbers from the data.
* Explain technical terms in simple language.
* Write as if teaching a beginner.
* Analysis strength must be between 0.0 and 1.0.
* Do not return percentages for analysis strength.

Market regime must be one of:

bullish
bearish
sideways
volatile
uncertain

────────────────────────────────────────────
INTERPRETATION RULES (MANDATORY)
────────────────────────────────────────────

PCR Classification:

PCR > 1.2 = bullish

PCR < 0.8 = bearish

0.8 <= PCR <= 1.2 = neutral

You MUST classify PCR using these rules.

Do not invent your own interpretation.

When PCR is between 0.8 and 1.2,
state that it is INSIDE the neutral range.

Do not say above the neutral range.

Do not say below the neutral range.

────────────────────────────────────────────
MARKET REGIME RULES
────────────────────────────────────────────

If ALL of the following are true:

* Spot is within 25 points of Max Pain
* PCR is neutral
* IV is moderate

Then market_regime should normally be:

sideways

Do not classify such conditions as bullish.

If market signals conflict,
use uncertain.

────────────────────────────────────────────
MAX PAIN RULES
────────────────────────────────────────────

If Spot is within 50 points of Max Pain,
you MUST mention this in key_observations.

If Spot is within 25 points of Max Pain,
treat it as strong evidence of a balanced market.

Always report Max Pain distance
as a positive absolute number.

Example:

Spot = 23998.6

Max Pain = 24000

Distance = 1.4 points

Never return negative distance values.

────────────────────────────────────────────
IV RULES
────────────────────────────────────────────

Higher IV means traders expect larger future moves.

Lower IV means traders expect smaller future moves.

IV Classification:

IV < 12 = low volatility

12 <= IV <= 18 = moderate volatility

IV > 18 = high volatility

You MUST follow these ranges exactly.

Do not classify IV below 12 as moderate.

────────────────────────────────────────────
IV SKEW RULES
────────────────────────────────────────────

Positive IV skew means traders are paying more
for downside protection.

Negative IV skew means traders are paying more
for upside exposure.

────────────────────────────────────────────
TRADE CONTEXT RULES
────────────────────────────────────────────

You MUST explain:

1. Which filters passed.
2. Which filters failed.
3. Why the signal engine produced its decision.

If exactly one filter failed,
explicitly state that all other filters passed.

Never override the signal engine decision.

────────────────────────────────────────────
ANALYSIS STRENGTH RULES
────────────────────────────────────────────

Analysis strength is NOT the signal engine confidence.

Analysis strength represents how strongly
the current market data supports the analysis.

Consider:

* PCR
* Distance from Max Pain
* IV levels
* IV Skew
* OI concentration

Do not copy the signal engine confidence value.

Analysis strength should be lower when
market signals are mixed or contradictory.

Analysis strength should be higher when
multiple metrics point to the same conclusion.

────────────────────────────────────────────
RISK FACTOR RULES
────────────────────────────────────────────

Risk factors must be based on actual data.

Do not invent risks.

Avoid generic risks such as:

* market may reverse
* trend may change
* volatility may increase

Risk factors must be directly supported
by current data.

────────────────────────────────────────────
FIELD COMPLETION RULES
────────────────────────────────────────────

Every field in the JSON response is mandatory.

Do not leave any field empty.

If uncertain,
provide your best explanation using
the available data.

────────────────────────────────────────────
KEY OBSERVATION RULES
────────────────────────────────────────────

Every observation must contain actual numbers.

Bad:

"PCR is bullish"

Good:

"PCR is 1.35 which is above the bullish threshold of 1.2"

Bad:

"Spot is near Max Pain"

Good:

"Spot is 23998.6 and Max Pain is 24000,
a distance of only 1.4 points"

Each observation must explain:

1. The number
2. What it means
3. Why it matters

Do not simply repeat the metric.

────────────────────────────────────────────
VOLATILITY ASSESSMENT RULES
────────────────────────────────────────────

Reference actual IV values.

Explain whether volatility is low,
moderate or high based on the IV rules.

Explain what that implies about
future market movement expectations.

────────────────────────────────────────────
THETA ASSESSMENT RULES
────────────────────────────────────────────

Explain theta as daily time decay.

State approximately how much option premium
is lost per day.

Use actual theta values.

Do not classify theta as sufficient,
insufficient, good or bad.

────────────────────────────────────────────
OI ASSESSMENT RULES
────────────────────────────────────────────

Reference actual OI concentration percentages.

Explain what concentrated OI means.

Explain whether traders appear focused
around a few strikes or spread across many strikes.

────────────────────────────────────────────
INVALIDATION RULES
────────────────────────────────────────────

Invalidation must describe which future
market conditions would invalidate
the analysis.

Do not use strategy rules such as DTE limits
as invalidation conditions.

────────────────────────────────────────────
ANOMALIES RULES
────────────────────────────────────────────

Never leave anomalies empty.

If no anomaly exists,
return exactly:

"None detected"

────────────────────────────────────────────
ANALYST NOTE RULES
────────────────────────────────────────────

Analyst note must be a one-sentence summary.

Analyst note can never be empty.

Maximum length: 25 words.

────────────────────────────────────────────
BEGINNER EXPLANATION RULES
────────────────────────────────────────────

Explain the market in plain English.

Assume the reader is new to options trading.

If technical terms are used,
briefly explain them.

Use the same interpretation framework
defined in this prompt.

Do not introduce alternative interpretations
for PCR, IV or Max Pain.

Keep explanations consistent with
the classifications used in the analysis.

────────────────────────────────────────────
TODAY'S LESSON RULES
────────────────────────────────────────────

Teach exactly one options concept
using today's data.

Use actual market numbers
from today's data when teaching the concept.

Keep the explanation simple and educational.

────────────────────────────────────────────
IMPORTANT
────────────────────────────────────────────

Every observation must reference actual numbers.

Return ONLY valid JSON.

Do not return markdown.

Do not return explanations outside JSON.

Do not return code fences.

The first character must be {

The last character must be }
"""


# ─────────────────────────────────────────────────────────────
# BUILD ANALYSIS PROMPT
# ─────────────────────────────────────────────────────────────

def build_prompt(features: dict, signal: dict, risk_result: dict) -> str:
    """
    Build a structured prompt from features, signal, and risk data.
    Only sends what Llama3 needs — avoids token waste.
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

Return ONLY valid JSON.

Do not explain.
Do not use markdown.
Do not use code fences.
Do not add commentary before or after the JSON.

Return exactly this structure:

{{
  "market_regime":"bullish | bearish | sideways | volatile | uncertain",

  "analysis_strength": 0.0,

  "key_observations": [
    "Observation 1 with actual numbers",
    "Observation 2 with actual numbers",
    "Observation 3 with actual numbers"
  ],

  "volatility_assessment": "",

  "theta_assessment": "",

  "oi_assessment": "",

  "trade_context": "",

  "risk_factors": [
    "",
    ""
  ],

  "invalidation": "",

  "anomalies": "",

  "analyst_note": "",

  "beginner_explanation":
    "Explain the current market situation in plain English for a new trader. Explain PCR, Max Pain, IV or other technical terms if mentioned.",

  "todays_lesson":
    "Teach one options-market concept using today's data."
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
        "BULLISH": "📈",
        "BEARISH": "📉",
        "SIDEWAYS": "➡️",
        "VOLATILE": "⚡",
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
    print(f"\n  [BEGINNER EXPLANATION]")
    print(
        f"    📘 {analysis.get('beginner_explanation', 'N/A')}"
    )

    print(f"\n  [TODAY'S LESSON]")
    print(
        f"    🎓 {analysis.get('todays_lesson', 'N/A')}"
    )

    print("\n" + "=" * 62)


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":

    print("=" * 62)
    print("  KAIT — Phase 8: AI Analyst")
    print("=" * 62)

    # ── Verify Ollama is running ──────────────────────────
    if not check_ollama():
        print(
            "\n❌ Ollama is not running."
            "\n\nStart it with:"
            "\nollama serve"
        )

        exit()

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

    # ── Build prompt and call Llama3 ─────────────────────────
    print(f"\n⏳ Sending data to Llama3 for analysis...")

    prompt = build_prompt(features, signal, risk_result)

    try:
        start_time = time.perf_counter()

        result = call_llama(
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
        print(f"\n❌ Llama/Ollama call failed: {e}")
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

            retry_result = call_llama(
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

            "prompt_tokens":
                usage.get("prompt_eval_count"),

            "completion_tokens":
                usage.get("eval_count")
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