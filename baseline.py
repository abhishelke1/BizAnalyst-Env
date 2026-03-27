#!/usr/bin/env python3
"""Baseline inference script using Groq API."""

import os
import json
import sys
from openai import OpenAI
import httpx
from typing import Dict, Any, List


def run_baseline(base_url: str = "http://localhost:7860", task_ids: List[str] = None):
    """Run baseline agent on all tasks.
    
    Args:
        base_url: Base URL of the environment server
        task_ids: List of task IDs to run (default: all tasks)
    """
    # Check for API key
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("Error: GROQ_API_KEY environment variable not set")
        print("Please set it with: $env:GROQ_API_KEY='your-key-here'")
        sys.exit(1)
    
    client = OpenAI(
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1"
    )
    
    # Default task list
    if task_ids is None:
        task_ids = ["revenue_summary", "customer_churn_risk", "anomaly_investigation"]
    
    system_prompt = """You are a business analyst agent. You have access to a SQLite database. To query it, respond with JSON in this exact format:
{"action_type": "run_query", "sql_query": "SELECT ...", "reasoning": "I want to find..."}

You can also use these actions:
- {"action_type": "list_tables"} - to see all available tables
- {"action_type": "describe_table", "table_name": "table_name"} - to see schema of a table

When ready to submit your final answer, use:
{"action_type": "submit_answer", "answer": "...", "reasoning": "Based on my analysis..."}

Be concise and focus on accuracy."""
    
    results = {}
    
    print("\n" + "="*80)
    print("BizAnalyst-Env Baseline Evaluation")
    print("Model: Llama-3.1-8B-Instant (via Groq)")
    print("="*80 + "\n")
    
    for task_id in task_ids:
        print(f"\n[Task: {task_id}]")
        print("-" * 80)
        
        # Reset environment
        try:
            response = httpx.post(f"{base_url}/reset", json={"task_id": task_id}, timeout=30.0)
            response.raise_for_status()
            obs = response.json()
        except Exception as e:
            print(f"Error resetting environment: {e}")
            results[task_id] = {"score": 0.0, "error": str(e)}
            continue
        
        # Initialize conversation
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": obs["task_description"]}
        ]
        
        print(f"Task Description: {obs['task_description'][:100]}...")
        print(f"Max Steps: {obs['max_steps']}")
        print()
        
        done = False
        step_count = 0
        max_steps = obs["max_steps"]
        final_score = 0.0
        
        while not done and step_count < max_steps:
            # Call Groq API
            try:
                completion = client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=messages,
                    temperature=0.0,
                    max_tokens=1000
                )
                
                assistant_message = completion.choices[0].message.content
                messages.append({"role": "assistant", "content": assistant_message})
                
                print(f"Step {step_count + 1}: ", end="")
                
                # Parse JSON action
                try:
                    # Extract JSON from response
                    json_start = assistant_message.find('{')
                    json_end = assistant_message.rfind('}') + 1
                    
                    if json_start >= 0 and json_end > json_start:
                        json_str = assistant_message[json_start:json_end]
                        action_dict = json.loads(json_str)
                        
                        # Show action type
                        action_type = action_dict.get("action_type", "unknown")
                        print(f"{action_type}", end="")
                        
                        # Execute step
                        response = httpx.post(f"{base_url}/step", json=action_dict, timeout=30.0)
                        response.raise_for_status()
                        step_result = response.json()
                        
                        observation = step_result["observation"]
                        reward = step_result["reward"]
                        done = step_result["done"]
                        
                        step_count += 1
                        
                        # Show result
                        if observation.get("query_result") and observation["query_result"].get("error") is None:
                            row_count = observation["query_result"].get("row_count", 0)
                            print(f" -> {row_count} rows")
                        elif observation.get("query_result") and observation["query_result"].get("error"):
                            print(f" -> Error: {observation['query_result']['error']}")
                        else:
                            print(f" -> {observation.get('message', '')[:50]}")
                        
                        # Add observation to conversation
                        obs_message = f"Step {step_count}: {observation['message']}"
                        
                        if observation.get("query_result") and observation["query_result"].get("error") is None:
                            row_count = observation["query_result"]["row_count"]
                            obs_message += f"\nQuery returned {row_count} rows."
                            
                            if row_count > 0 and row_count <= 10:
                                obs_message += f"\nResults: {json.dumps(observation['query_result']['rows'])}"
                            elif row_count > 10:
                                obs_message += f"\nShowing first 5 rows: {json.dumps(observation['query_result']['rows'][:5])}"
                                
                        elif observation.get("query_result") and observation["query_result"].get("error"):
                            obs_message += f"\nError: {observation['query_result']['error']}"
                        
                        messages.append({"role": "user", "content": obs_message})
                        
                        if done:
                            final_score = reward["value"]
                            print(f"\n✓ Task completed! Score: {final_score:.3f}")
                            print(f"  Feedback: {reward['feedback']}")
                            break
                    else:
                        # Could not find JSON in response
                        print("Error: No JSON found in response")
                        messages.append({
                            "role": "user",
                            "content": "Error: Could not parse your response. Please respond with valid JSON."
                        })
                        step_count += 1
                        
                except json.JSONDecodeError as e:
                    print(f"JSON parse error: {e}")
                    messages.append({
                        "role": "user",
                        "content": f"Error parsing JSON: {str(e)}. Please respond with valid JSON."
                    })
                    step_count += 1
                    
            except Exception as e:
                print(f"API error: {e}")
                break
        
        if not done:
            print(f"\n✗ Max steps reached without completing task")
        
        results[task_id] = {
            "score": final_score,
            "steps": step_count,
            "completed": done
        }
    
    # Print summary
    print("\n" + "="*80)
    print("Results Summary")
    print("="*80)
    print()
    print(f"{'Task':<30} {'Score':<10} {'Steps':<10} {'Completed':<10}")
    print("-" * 80)
    
    total_score = 0.0
    for task_id, result in results.items():
        score = result.get("score", 0.0)
        steps = result.get("steps", 0)
        completed = "✓" if result.get("completed", False) else "✗"
        
        print(f"{task_id:<30} {score:<10.3f} {steps:<10} {completed:<10}")
        total_score += score
    
    avg_score = total_score / len(results) if results else 0.0
    print("-" * 80)
    print(f"{'Average Score':<30} {avg_score:<10.3f}")
    print("="*80)
    print()
    
    # Save results to JSON
    output = {
        "model": "llama-3.1-8b-instant",
        "results": results,
        "average_score": avg_score,
        "total_tasks": len(results)
    }
    
    with open("baseline_results.json", "w") as f:
        json.dump(output, f, indent=2)
    
    print(f"Results saved to baseline_results.json\n")
    
    return results


if __name__ == "__main__":
    # Check if server is running
    try:
        response = httpx.get("http://localhost:7860/health", timeout=5.0)
        response.raise_for_status()
    except Exception as e:
        print("Error: Could not connect to environment server at http://localhost:7860")
        print("Please start the server first with: uvicorn server:app --host 0.0.0.0 --port 7860")
        print(f"Error details: {e}")
        sys.exit(1)
    
    run_baseline()