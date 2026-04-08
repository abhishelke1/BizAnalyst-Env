#!/usr/bin/env python3
"""
SCOUT AI - Inference Script for OpenEnv Hackathon
==================================================
MANDATORY ENVIRONMENT VARIABLES:
    API_BASE_URL   The API endpoint for the LLM
    MODEL_NAME     The model identifier to use for inference
    HF_TOKEN       Your Hugging Face / API key
    ENV_URL        Environment server URL (default: http://localhost:7860)

STDOUT FORMAT (required by evaluation):
    [START] task=<task_name> env=<benchmark> model=<model_name>
    [STEP]  step=<n> action=<action_str> reward=<0.00> done=<true|false> error=<msg|null>
    [END]   success=<true|false> steps=<n> score=<score> rewards=<r1,r2,...,rn>
"""

import os
import json
import sys
import time
import traceback
from typing import Dict, Any, List, Optional

from openai import OpenAI
import httpx

# ============================================================================
# CONFIGURATION - Using required environment variables
# ============================================================================
API_BASE_URL = os.getenv("API_BASE_URL", "")
MODEL_NAME = os.getenv("MODEL_NAME", "")
API_KEY = os.getenv("HF_TOKEN") or os.getenv("OPENAI_API_KEY") or os.getenv("GROQ_API_KEY") or os.getenv("API_KEY")
ENV_URL = os.getenv("ENV_URL", "http://localhost:7860")

# Auto-detect API base URL and model if not explicitly set
if not API_BASE_URL:
    if os.getenv("GROQ_API_KEY"):
        API_BASE_URL = "https://api.groq.com/openai/v1"
    else:
        API_BASE_URL = "https://router.huggingface.co/v1"

if not MODEL_NAME:
    if os.getenv("GROQ_API_KEY"):
        MODEL_NAME = "llama-3.1-8b-instant"
    else:
        MODEL_NAME = "Qwen/Qwen2.5-72B-Instruct"
BENCHMARK = "scout-ai-bizanalyst"
TASK_IDS = ["revenue_summary", "customer_churn_risk", "anomaly_investigation"]


# ============================================================================
# SYSTEM PROMPT FOR LLM
# ============================================================================
SYSTEM_PROMPT = """You are a business analyst agent with access to a SQLite database.

RULES:
1. You MUST run at least one run_query action before EVER using submit_answer.
2. Never guess values. Always query the database first.
3. Respond with a SINGLE JSON object only. No explanation text. No markdown. No backticks.

SQLite syntax rules:
- Date difference: CAST(julianday('2024-06-01') - julianday(date_col) AS INTEGER)
- No DATEDIFF, no DUAL table, use || for string concatenation
- Keep queries simple - single table SELECT preferred

Database schema:
  customers:       customer_id, name, region, segment, signup_date, last_order_date, total_spent, order_count
  products:        product_id, name, category, unit_price, cost_price, stock_quantity
  orders:          order_id, customer_id, order_date, status, total_amount, discount_pct
  order_items:     item_id, order_id, product_id, quantity, unit_price
  monthly_revenue: month, year, revenue, expenses, profit, region, category

ACTION FORMAT:
  Run query:     {"action_type": "run_query", "sql_query": "SELECT ...", "reasoning": "..."}
  Submit answer: {"action_type": "submit_answer", "answer": "<your answer>", "reasoning": "..."}

For revenue_summary: Return format "Total Revenue: $X | Total Expenses: $Y | Net Profit: $Z | Top Region: R"
For customer_churn_risk: Return JSON array of at-risk customers with days_since_last_order > 90
For anomaly_investigation: Return JSON with spike_month, spike_year, negative_margin_product, duplicate findings

CRITICAL: Never use submit_answer as your first action. Always query first."""


def extract_action(text: str) -> Optional[Dict]:
    """Extract the first valid action JSON from model response."""
    start = text.find('{')
    if start == -1:
        return None
    
    brace_count = 0
    in_string = False
    escape_next = False
    
    for i in range(start, len(text)):
        char = text[i]
        if escape_next:
            escape_next = False
            continue
        if char == '\\':
            escape_next = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == '{':
            brace_count += 1
        elif char == '}':
            brace_count -= 1
            if brace_count == 0:
                try:
                    json_str = text[start:i+1]
                    parsed = json.loads(json_str)
                    if 'action_type' in parsed:
                        return parsed
                except Exception:
                    pass
                next_start = text.find('{', start + 1)
                if next_start == -1:
                    return None
                start = next_start
                brace_count = 0
                in_string = False
    return None


def format_action_str(action: Dict) -> str:
    """Format action dict as a compact string for logging."""
    action_type = action.get("action_type", "unknown")
    if action_type == "run_query":
        sql = action.get("sql_query", "")[:50]
        return f"run_query('{sql}...')"
    elif action_type == "submit_answer":
        answer = str(action.get("answer", ""))[:30]
        return f"submit_answer('{answer}...')"
    else:
        return f"{action_type}()"


def run_task(client: OpenAI, task_id: str, env_url: str, model: str) -> Dict:
    """Run a single task and return results with proper stdout logging."""
    rewards_list: List[float] = []
    step_count = 0
    final_score = 0.0
    success = False
    last_error: Optional[str] = None
    
    # [START] log
    print(f"[START] task={task_id} env={BENCHMARK} model={model}")
    sys.stdout.flush()
    
    try:
        # Reset environment
        resp = httpx.post(f"{env_url}/reset", json={"task_id": task_id}, timeout=60.0)
        resp.raise_for_status()
        obs = resp.json()
        
        max_steps = obs.get("max_steps", 10)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": obs["task_description"]}
        ]
        
        done = False
        queries_run = 0
        
        while not done and step_count < max_steps:
            time.sleep(1)  # Rate limiting
            
            # Get LLM response
            try:
                completion = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0.0,
                    max_tokens=1000
                )
                assistant_msg = completion.choices[0].message.content
                messages.append({"role": "assistant", "content": assistant_msg})
            except Exception as e:
                last_error = str(e)
                step_count += 1
                rewards_list.append(0.0)
                print(f"[STEP] step={step_count} action=llm_error() reward=0.00 done=false error={last_error}")
                sys.stdout.flush()
                if "429" in last_error or "rate" in last_error.lower():
                    time.sleep(30)
                continue
            
            # Parse action
            action_dict = extract_action(assistant_msg)
            if not action_dict:
                step_count += 1
                rewards_list.append(0.0)
                last_error = "No valid JSON action in response"
                print(f"[STEP] step={step_count} action=parse_error() reward=0.00 done=false error={last_error}")
                sys.stdout.flush()
                messages.append({"role": "user", "content": "Respond with ONLY a JSON object. No markdown."})
                continue
            
            action_type = action_dict.get("action_type", "unknown")
            action_str = format_action_str(action_dict)
            
            # Block early submit
            if action_type == "submit_answer" and queries_run == 0:
                step_count += 1
                rewards_list.append(0.0)
                last_error = "Cannot submit before querying"
                print(f"[STEP] step={step_count} action={action_str} reward=0.00 done=false error={last_error}")
                sys.stdout.flush()
                messages.append({"role": "user", "content": "You must run at least one query before submitting."})
                continue
            
            # Execute action
            try:
                step_resp = httpx.post(f"{env_url}/step", json=action_dict, timeout=30.0)
                step_resp.raise_for_status()
                step_result = step_resp.json()
            except Exception as e:
                step_count += 1
                rewards_list.append(0.0)
                last_error = str(e)
                print(f"[STEP] step={step_count} action={action_str} reward=0.00 done=false error={last_error}")
                sys.stdout.flush()
                continue
            
            observation = step_result["observation"]
            reward = step_result["reward"]
            done = step_result["done"]
            step_count += 1
            
            reward_value = reward.get("value", 0.0)
            rewards_list.append(reward_value)
            
            if action_type == "run_query":
                queries_run += 1
            
            # Check for errors in observation
            qr = observation.get("query_result")
            if qr and qr.get("error"):
                last_error = qr["error"]
            else:
                last_error = None
            
            # [STEP] log
            done_str = "true" if done else "false"
            error_str = last_error if last_error else "null"
            print(f"[STEP] step={step_count} action={action_str} reward={reward_value:.2f} done={done_str} error={error_str}")
            sys.stdout.flush()
            
            if done:
                final_score = reward_value
                success = True
            else:
                # Build next message
                obs_msg = f"Step {step_count}: {observation.get('message', '')}"
                if qr and not qr.get("error"):
                    rows = qr.get("rows", [])
                    if rows:
                        obs_msg += f"\nResults: {json.dumps(rows[:10])}"
                elif qr and qr.get("error"):
                    obs_msg += f"\nError: {qr['error']}"
                messages.append({"role": "user", "content": obs_msg})
    
    except Exception as e:
        last_error = str(e)
        if step_count == 0:
            step_count = 1
            rewards_list.append(0.0)
        print(f"[STEP] step={step_count} action=exception() reward=0.00 done=true error={last_error}")
        sys.stdout.flush()
    
    # [END] log
    rewards_str = ",".join(f"{r:.2f}" for r in rewards_list) if rewards_list else "0.00"
    success_str = "true" if success else "false"
    print(f"[END] success={success_str} steps={step_count} score={final_score:.2f} rewards={rewards_str}")
    sys.stdout.flush()
    
    return {
        "task_id": task_id,
        "score": final_score,
        "steps": step_count,
        "success": success,
        "rewards": rewards_list
    }


def main():
    """Main entry point."""
    # Validate API key
    if not API_KEY:
        print("[END] success=false steps=0 score=0.00 rewards=0.00")
        sys.stderr.write("ERROR: No API key found. Set HF_TOKEN, OPENAI_API_KEY, or API_KEY.\n")
        sys.exit(1)
    
    # Initialize OpenAI client with configured base URL
    client = OpenAI(
        api_key=API_KEY,
        base_url=API_BASE_URL
    )
    
    # Health check
    try:
        resp = httpx.get(f"{ENV_URL}/health", timeout=30.0)
        resp.raise_for_status()
    except Exception as e:
        sys.stderr.write(f"ERROR: Cannot connect to environment at {ENV_URL}: {e}\n")
        for task_id in TASK_IDS:
            print(f"[START] task={task_id} env={BENCHMARK} model={MODEL_NAME}")
            print(f"[STEP] step=1 action=health_check() reward=0.00 done=true error=Connection failed")
            print(f"[END] success=false steps=1 score=0.00 rewards=0.00")
        sys.exit(1)
    
    # Run all tasks
    results = []
    for task_id in TASK_IDS:
        result = run_task(client, task_id, ENV_URL, MODEL_NAME)
        results.append(result)
    
    # Summary to stderr (not stdout to avoid format issues)
    total_score = sum(r["score"] for r in results)
    avg_score = total_score / len(results) if results else 0.0
    sys.stderr.write(f"\n=== Summary ===\n")
    sys.stderr.write(f"Average Score: {avg_score:.2f}\n")
    for r in results:
        sys.stderr.write(f"  {r['task_id']}: {r['score']:.2f} ({r['steps']} steps)\n")


if __name__ == "__main__":
    main()