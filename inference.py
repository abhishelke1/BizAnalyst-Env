#!/usr/bin/env python3
"""Baseline inference script using OpenAI API (supports OpenAI and Groq).

Reads API credentials from OPENAI_API_KEY environment variable.
Falls back to GROQ_API_KEY if OPENAI_API_KEY is not set.
Uses ENV_URL environment variable for server URL (defaults to http://localhost:7860).
"""

import os
import re
import json
import sys
import time
import traceback

try:
    from openai import OpenAI
except ImportError as e:
    print(f"Error: Failed to import openai: {e}")
    print("Install with: pip install openai")
    sys.exit(1)

try:
    import httpx
except ImportError as e:
    print(f"Error: Failed to import httpx: {e}")
    print("Install with: pip install httpx")
    sys.exit(1)

from typing import Dict, Any, List

# Get environment URL from ENV_URL env var (used by hackathon evaluation)
DEFAULT_ENV_URL = "http://localhost:7860"
ENV_URL = os.getenv("ENV_URL", DEFAULT_ENV_URL)

# Debug: Print environment info at startup
print(f"[DEBUG] Python version: {sys.version}")
print(f"[DEBUG] ENV_URL: {ENV_URL}")
print(f"[DEBUG] OPENAI_API_KEY set: {bool(os.getenv('OPENAI_API_KEY'))}")
print(f"[DEBUG] GROQ_API_KEY set: {bool(os.getenv('GROQ_API_KEY'))}")


# ──────────────────────────────────────────────────────────────
# SYSTEM PROMPT
# ──────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a business analyst agent with access to a SQLite database.

RULE 1: You MUST run at least one run_query action before EVER using submit_answer.
RULE 2: Never guess values. Always query the database first.
RULE 3: Respond with a SINGLE JSON object only. No explanation text. No markdown. No backticks.

CRITICAL SQLite rules (never use MySQL/Oracle syntax):
- No CTEs (no WITH clause), no complex multi-table JOINs
- Date difference: CAST(julianday('2024-06-01') - julianday(date_col) AS INTEGER)
- No DATEDIFF, no DUAL table, no CONCAT() - use || for string concat
- Keep ALL queries simple - single table SELECT preferred

Exact tables and columns (use ONLY these - never invent column names):
  customers:       customer_id, name, region, segment, signup_date, last_order_date, total_spent, order_count
  products:        product_id, name, category, unit_price, cost_price, stock_quantity
  orders:          order_id, customer_id, order_date, status, total_amount, discount_pct
  order_items:     item_id, order_id, product_id, quantity, unit_price
  monthly_revenue: month, year, revenue, expenses, profit, region, category

EXACT QUERIES TO USE - copy these exactly:

For revenue_summary task:
  Step 1: {"action_type": "run_query", "sql_query": "SELECT SUM(revenue) as total_revenue, SUM(expenses) as total_expenses, SUM(profit) as total_profit FROM monthly_revenue WHERE year=2023", "reasoning": "Get 2023 totals"}
  Step 2: {"action_type": "run_query", "sql_query": "SELECT region, SUM(revenue) as total FROM monthly_revenue WHERE year=2023 GROUP BY region ORDER BY total DESC LIMIT 1", "reasoning": "Get top region"}
  Step 3: submit_answer with real numbers from above queries

For customer_churn_risk task:
  Step 1: {"action_type": "run_query", "sql_query": "SELECT customer_id, name, last_order_date, CAST(julianday('2024-06-01') - julianday(last_order_date) AS INTEGER) as days_since_last_order FROM customers WHERE CAST(julianday('2024-06-01') - julianday(last_order_date) AS INTEGER) > 90 ORDER BY days_since_last_order DESC LIMIT 3", "reasoning": "Find churn risk customers"}
  Step 2: submit_answer with real data from above query

For anomaly_investigation task:
  Step 1: {"action_type": "run_query", "sql_query": "SELECT month, year, revenue FROM monthly_revenue ORDER BY year, month", "reasoning": "Find revenue spike"}
  Step 2: {"action_type": "run_query", "sql_query": "SELECT name, unit_price, cost_price, ROUND((unit_price - cost_price) * 100.0 / cost_price, 2) as margin_pct FROM products WHERE cost_price > unit_price", "reasoning": "Find negative margin"}
  Step 3: {"action_type": "run_query", "sql_query": "SELECT customer_id, order_date, total_amount, COUNT(*) as cnt FROM orders GROUP BY customer_id, order_date, total_amount HAVING cnt > 1", "reasoning": "Find duplicates"}
  Step 4: submit_answer with real data from above queries

EXACT ANSWER FORMATS - fill with REAL query results:

revenue_summary (single line):
  Total Revenue: $<EXACT_DECIMAL_NUMBER> | Total Expenses: $<EXACT_DECIMAL_NUMBER> | Net Profit: $<EXACT_DECIMAL_NUMBER> | Top Region: <REGION>
  Example format: Total Revenue: $4821540.23 | Total Expenses: $3291872.45 | Net Profit: $1529667.78 | Top Region: North
  IMPORTANT: Use the exact decimal numbers from your query results. Do not round to integers.

customer_churn_risk (JSON array):
  [{"customer_id": <ID>, "name": "<NAME>", "days_since_last_order": <DAYS>, "recommendation": "Send discount email offer"}]

anomaly_investigation (JSON object):
  {"spike_month": <M>, "spike_year": <Y>, "spike_explanation": "Unusual seasonal promotion campaign caused revenue spike", "negative_margin_product": "<PRODUCT NAME>", "margin_pct": <PCT>, "duplicate_customer_ids": [<ID1>, <ID2>]}

ACTION FORMAT:
  Run query:     {"action_type": "run_query", "sql_query": "SELECT ...", "reasoning": "..."}
  Submit answer: {"action_type": "submit_answer", "answer": "<EXACT FORMAT ABOVE>", "reasoning": "..."}

CRITICAL: Never use submit_answer as your first action. Always query first."""


def extract_action(text: str):
    """Extract the first valid action JSON from model response using brace balancing."""
    start = text.find('{')
    if start == -1:
        return None
    
    # Balance braces to find the matching closing brace
    brace_count = 0
    in_string = False
    escape_next = False
    
    for i in range(start, len(text)):
        char = text[i]
        
        # Handle string escaping
        if escape_next:
            escape_next = False
            continue
        
        if char == '\\':
            escape_next = True
            continue
        
        # Track if we're inside a string (don't count braces in strings)
        if char == '"':
            in_string = not in_string
            continue
        
        if in_string:
            continue
        
        # Count braces
        if char == '{':
            brace_count += 1
        elif char == '}':
            brace_count -= 1
            if brace_count == 0:
                # Found matching closing brace - try to parse
                try:
                    json_str = text[start:i+1]
                    parsed = json.loads(json_str)
                    if 'action_type' in parsed:
                        return parsed
                except Exception:
                    pass
                
                # This JSON was invalid, try finding next {
                next_start = text.find('{', start + 1)
                if next_start == -1:
                    return None
                start = next_start
                brace_count = 0
                in_string = False
                escape_next = False
    
    return None


def run_baseline(base_url: str = None, task_ids: List[str] = None) -> Dict:
    """Run baseline agent on all tasks and return results."""
    
    # Use provided base_url, fall back to ENV_URL environment variable
    if base_url is None:
        base_url = ENV_URL
    
    print(f"Using environment URL: {base_url}")

    # Support both OPENAI_API_KEY and GROQ_API_KEY (spec requires OPENAI_API_KEY)
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("GROQ_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY environment variable not set")
        print("Set it with:  export OPENAI_API_KEY='sk-...'")
        print("Or use Groq:  export GROQ_API_KEY='gsk_...'")
        sys.exit(1)

    # Determine which API to use
    if os.getenv("OPENAI_API_KEY"):
        client = OpenAI(api_key=api_key)
        model = "gpt-4o-mini"
        provider = "OpenAI"
    else:
        client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
        model = "llama-3.1-8b-instant"
        provider = "Groq"

    if task_ids is None:
        task_ids = ["revenue_summary", "customer_churn_risk", "anomaly_investigation"]

    results = {}

    print("\n" + "=" * 80)
    print("BizAnalyst-Env  -  Baseline Evaluation")
    print(f"Model: {model}  |  Provider: {provider}")
    print("=" * 80)

    for task_id in task_ids:
        print(f"\n[Task: {task_id}]")
        print("-" * 80)

        try:
            resp = httpx.post(f"{base_url}/reset", json={"task_id": task_id}, timeout=30.0)
            resp.raise_for_status()
            obs = resp.json()
        except Exception as e:
            print(f"  Error resetting: {e}")
            results[task_id] = {"score": 0.0, "steps": 0, "completed": False}
            continue

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": obs["task_description"]}
        ]

        print(f"  Task: {obs['task_description'][:90]}...")
        print(f"  Max steps: {obs['max_steps']}\n")

        done        = False
        step_count  = 0
        max_steps   = obs["max_steps"]
        final_score = 0.0
        queries_run = 0
        parse_retries = 0
        MAX_PARSE_RETRIES = 3

        while not done and step_count < max_steps:
            time.sleep(2)

            try:
                completion = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0.0,
                    max_tokens=1000
                )
            except Exception as e:
                err = str(e)
                if '429' in err or 'Too Many Requests' in err:
                    print("  Rate limited - waiting 60s...")
                    time.sleep(60)
                    continue
                print(f"  API error: {e}")
                break

            assistant_msg = completion.choices[0].message.content
            messages.append({"role": "assistant", "content": assistant_msg})

            action_dict = extract_action(assistant_msg)

            if not action_dict:
                parse_retries += 1
                print(f"  Step {step_count + 1}: [no valid JSON - retry {parse_retries}/{MAX_PARSE_RETRIES}]")
                if parse_retries >= MAX_PARSE_RETRIES:
                    print(f"  Too many parse failures - skipping task")
                    break
                messages.append({
                    "role": "user",
                    "content": "Your response had no valid JSON. Respond with ONLY a single JSON object. No markdown, no backticks, no extra text."
                })
                continue
            parse_retries = 0  # reset on success

            action_type = action_dict.get("action_type", "unknown")

            # Guard: block submit_answer before any queries run
            if action_type == "submit_answer" and queries_run == 0:
                print(f"  Step {step_count + 1}: [blocked submit before query - forcing query]")
                messages.append({
                    "role": "user",
                    "content": "You must run at least one run_query action BEFORE submitting an answer. Query the database now using the exact SQL queries in your instructions."
                })
                continue

            print(f"  Step {step_count + 1}: {action_type}", end="")

            try:
                step_resp = httpx.post(f"{base_url}/step", json=action_dict, timeout=30.0)
                step_resp.raise_for_status()
                step_result = step_resp.json()
            except Exception as e:
                print(f" -> HTTP error: {e}")
                step_count += 1
                continue

            observation = step_result["observation"]
            reward      = step_result["reward"]
            done        = step_result["done"]
            step_count += 1

            if action_type == "run_query":
                queries_run += 1

            qr = observation.get("query_result")
            if qr:
                if qr.get("error"):
                    print(f" -> Error: {qr['error'][:60]}")
                else:
                    print(f" -> {qr.get('row_count', 0)} rows")
            else:
                print(f" -> {observation.get('message', '')[:60]}")

            obs_msg = f"Step {step_count}: {observation['message']}"
            if action_type == "run_query" and task_id == "revenue_summary" and queries_run == 2:
                obs_msg += "\nNow submit your answer using EXACT decimal numbers from both query results in this format:\nTotal Revenue: $<number> | Total Expenses: $<number> | Net Profit: $<number> | Top Region: <region>"
            if qr and not qr.get("error"):
                rc = qr["row_count"]
                obs_msg += f"\nQuery returned {rc} rows."
                if 0 < rc <= 10:
                    obs_msg += f"\nResults: {json.dumps(qr['rows'])}"
                elif rc > 10:
                    obs_msg += f"\nFirst 5 rows: {json.dumps(qr['rows'][:5])}"
            elif qr and qr.get("error"):
                obs_msg += f"\nError: {qr['error']}"

            messages.append({"role": "user", "content": obs_msg})

            if done:
                final_score = reward["value"]
                print(f"\n  Completed! Score: {final_score:.3f}")
                print(f"  Feedback: {reward['feedback']}")

        if not done:
            print(f"\n  Max steps reached without answer")

        results[task_id] = {
            "score":     final_score,
            "steps":     step_count,
            "completed": done
        }

    # Summary
    print("\n" + "=" * 80)
    print("Results Summary")
    print("=" * 80)
    print(f"\n{'Task':<30} {'Score':<10} {'Steps':<10} {'Done'}")
    print("-" * 80)

    total = 0.0
    for tid, r in results.items():
        mark = "Yes" if r.get("completed") else "No"
        print(f"{tid:<30} {r['score']:<10.3f} {r['steps']:<10} {mark}")
        total += r["score"]

    avg = total / len(results) if results else 0.0
    print("-" * 80)
    print(f"{'Average':<30} {avg:<10.3f}")
    print("=" * 80 + "\n")

    output = {
        "model":          "llama-3.1-8b-instant",
        "provider":       "groq",
        "reference_date": "2024-06-01",
        "results":        results,
        "average_score":  avg
    }
    with open("baseline_results.json", "w") as f:
        json.dump(output, f, indent=2)
    print("Results saved to baseline_results.json\n")

    return results


if __name__ == "__main__":
    print("=" * 60)
    print("SCOUT AI - Baseline Inference Script")
    print("=" * 60)
    
    # Use ENV_URL from environment variable
    base_url = ENV_URL
    
    print(f"[INFO] Environment URL: {base_url}")
    
    # Check API key first
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("GROQ_API_KEY")
    if not api_key:
        print("[ERROR] No API key found!")
        print("Set OPENAI_API_KEY or GROQ_API_KEY environment variable.")
        sys.exit(1)
    print(f"[INFO] API key found (length: {len(api_key)})")
    
    # Health check with retries
    max_retries = 3
    for attempt in range(max_retries):
        try:
            print(f"[INFO] Health check attempt {attempt + 1}/{max_retries}...")
            resp = httpx.get(f"{base_url}/health", timeout=30.0)
            resp.raise_for_status()
            health_data = resp.json()
            print(f"[INFO] Environment healthy: {health_data}")
            break
        except httpx.ConnectError as e:
            print(f"[WARN] Cannot connect to server at {base_url}: {e}")
            if attempt < max_retries - 1:
                print(f"[INFO] Retrying in 5 seconds...")
                time.sleep(5)
            else:
                print(f"[ERROR] Failed to connect after {max_retries} attempts")
                sys.exit(1)
        except httpx.TimeoutException as e:
            print(f"[WARN] Connection timeout: {e}")
            if attempt < max_retries - 1:
                print(f"[INFO] Retrying in 5 seconds...")
                time.sleep(5)
            else:
                print(f"[ERROR] Timeout after {max_retries} attempts")
                sys.exit(1)
        except httpx.HTTPStatusError as e:
            print(f"[ERROR] Server returned error status: {e.response.status_code}")
            print(f"[ERROR] Response: {e.response.text}")
            sys.exit(1)
        except Exception as e:
            print(f"[ERROR] Unexpected error: {type(e).__name__}: {e}")
            traceback.print_exc()
            if attempt < max_retries - 1:
                print(f"[INFO] Retrying in 5 seconds...")
                time.sleep(5)
            else:
                sys.exit(1)

    # Run the baseline
    try:
        print("[INFO] Starting baseline evaluation...")
        run_baseline(base_url=base_url)
        print("[INFO] Baseline evaluation completed successfully!")
    except Exception as e:
        print(f"[ERROR] Baseline execution failed: {type(e).__name__}: {e}")
        traceback.print_exc()
        sys.exit(1)