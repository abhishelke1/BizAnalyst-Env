from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import traceback
import json
import os
from environment import BizAnalystEnv, Action, ActionType

# Initialize FastAPI app
app = FastAPI(
    title="BizAnalyst-Env",
    description="Business Intelligence Environment for AI Agents",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global environment instance
env = BizAnalystEnv()


# Request/Response models
class ResetRequest(BaseModel):
    task_id: str


class StepResponse(BaseModel):
    observation: Dict[str, Any]
    reward: Dict[str, Any]
    done: bool
    info: Dict[str, Any]


class GraderRequest(BaseModel):
    task_id: str
    answer: str


class GraderResponse(BaseModel):
    score: float
    breakdown: Dict[str, float]
    feedback: str


class BaselineRequest(BaseModel):
    task_ids: List[str]


class BaselineResponse(BaseModel):
    scores: Dict[str, float]
    total: float
    details: Dict[str, Any]


# Endpoints

@app.get("/")
async def root():
    """Return environment info card."""
    return {
        "name": "BizAnalyst-Env",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "endpoints": ["/reset", "/step", "/state", "/tasks", "/grader", "/baseline", "/health"]
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "env": "BizAnalyst-Env",
        "version": "1.0.0"
    }


@app.post("/reset")
async def reset(request: ResetRequest):
    """Reset environment with a task.
    
    Args:
        request: Contains task_id
        
    Returns:
        Initial observation
    """
    try:
        observation = env.reset(request.task_id)
        return observation.model_dump()
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@app.post("/step")
async def step(action: Action) -> StepResponse:
    """Execute an action in the environment.
    
    Args:
        action: Action to execute
        
    Returns:
        Step response with observation, reward, done, info
    """
    try:
        observation, reward, done, info = env.step(action)
        
        return StepResponse(
            observation=observation.model_dump(),
            reward=reward.model_dump(),
            done=done,
            info=info
        )
    except RuntimeError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}\n{traceback.format_exc()}")


@app.get("/state")
async def get_state():
    """Get current environment state.
    
    Returns:
        State dictionary
    """
    try:
        return env.state()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@app.get("/tasks")
async def get_tasks():
    """Get all task definitions.
    
    Returns:
        List of task definitions with schemas
    """
    try:
        # Initialize a temporary environment to get task definitions
        temp_env = BizAnalystEnv()
        temp_env.reset("revenue_summary")
        
        tasks = temp_env.task_manager.list_tasks()
        
        temp_env.db_manager.close()
        return tasks
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@app.post("/grader")
async def grade_answer(request: GraderRequest) -> GraderResponse:
    """Grade an answer for a specific task.
    
    Args:
        request: Contains task_id and answer
        
    Returns:
        Grading results
    """
    try:
        # Initialize environment with the task
        temp_env = BizAnalystEnv()
        temp_env.reset(request.task_id)
        
        task = temp_env.task_manager.get_task(request.task_id)
        if not task:
            raise HTTPException(status_code=422, detail=f"Task '{request.task_id}' not found")
        
        # Grade the answer
        score, breakdown, feedback = task.grader_func(
            request.answer,
            task.correct_answers,
            0  # steps_used
        )
        
        temp_env.db_manager.close()
        
        return GraderResponse(
            score=score,
            breakdown=breakdown,
            feedback=feedback
        )
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@app.post("/baseline")
async def run_baseline(request: BaselineRequest) -> BaselineResponse:
    """Run baseline agent on specified tasks.
    
    Args:
        request: Contains list of task_ids
        
    Returns:
        Baseline results
    """
    try:
        from openai import OpenAI
        import time
        
        # Check for API key
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise HTTPException(
                status_code=422,
                detail="GROQ_API_KEY environment variable not set"
            )
        
        client = OpenAI(
            api_key=api_key,
            base_url="https://api.groq.com/openai/v1"
        )
        
        system_prompt = """You are a business analyst agent with access to a SQLite database. 

CRITICAL SQLite rules - never use MySQL or Oracle syntax:
- Date difference: CAST(julianday('2024-06-01') - julianday(date_col) AS INTEGER)
- No DATEDIFF, no DUAL table, no CONCAT() - use || for strings
- No NOW() - use date('2024-06-01') as reference date

Exact tables and columns (use ONLY these):
customers: customer_id, name, region, segment, signup_date, last_order_date, total_spent, order_count
products: product_id, name, category, unit_price, cost_price, stock_quantity
orders: order_id, customer_id, order_date, status, total_amount, discount_pct
order_items: item_id, order_id, product_id, quantity, unit_price
monthly_revenue: month, year, revenue, expenses, profit, region, category

CRITICAL - submit answers in EXACTLY these formats:

Task revenue_summary answer format:
Total Revenue: $123456.78 | Total Expenses: $98765.43 | Net Profit: $24691.35 | Top Region: North

Task customer_churn_risk answer format (JSON array):
[{"customer_id": 7, "name": "John Doe", "days_since_last_order": 150, "recommendation": "Send discount email offer"}, {"customer_id": 23, "name": "Jane Smith", "days_since_last_order": 135, "recommendation": "Follow-up with special offer"}, {"customer_id": 89, "name": "Bob Jones", "days_since_last_order": 120, "recommendation": "Re-engagement discount campaign"}]

Task anomaly_investigation answer format (JSON object):
{"spike_month": 3, "spike_year": 2024, "spike_explanation": "Revenue spike caused by unusual seasonal promotion campaign", "negative_margin_product": "Premium Wireless Keyboard", "margin_pct": -13.46, "duplicate_customer_ids": [15, 67]}

Actions:
{"action_type": "run_query", "sql_query": "SELECT ...", "reasoning": "..."}
{"action_type": "submit_answer", "answer": "EXACT FORMAT ABOVE", "reasoning": "..."}

Respond with a single JSON object only. No extra text."""
        
        scores = {}
        details = {}
        
        for task_id in request.task_ids:
            # Reset environment
            temp_env = BizAnalystEnv()
            obs = temp_env.reset(task_id)
            
            # Initialize conversation
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": obs.task_description}
            ]
            
            done = False
            step_count = 0
            max_steps = obs.max_steps
            
            while not done and step_count < max_steps:
                # Call OpenAI API
                try:
                    # Rate limiting - wait 2 seconds before API call
                    time.sleep(2)
                    
                    response = client.chat.completions.create(
                        model="llama-3.1-8b-instant",
                        messages=messages,
                        temperature=0.0
                    )
                    
                    assistant_message = response.choices[0].message.content
                    messages.append({"role": "assistant", "content": assistant_message})
                    
                    # Parse JSON action
                    try:
                        # Extract JSON from response
                        json_start = assistant_message.find('{')
                        json_end = assistant_message.rfind('}') + 1
                        if json_start >= 0 and json_end > json_start:
                            json_str = assistant_message[json_start:json_end]
                            action_dict = json.loads(json_str)
                            
                            # Create Action object
                            action = Action(**action_dict)
                            
                            # Execute step
                            observation, reward, done, info = temp_env.step(action)
                            step_count += 1
                            
                            # Add observation to conversation
                            obs_message = f"Step {step_count}: {observation.message}"
                            if observation.query_result and observation.query_result.error is None:
                                obs_message += f"\nQuery returned {observation.query_result.row_count} rows."
                                if observation.query_result.row_count > 0 and observation.query_result.row_count <= 10:
                                    obs_message += f"\nResults: {observation.query_result.rows}"
                            elif observation.query_result and observation.query_result.error:
                                obs_message += f"\nError: {observation.query_result.error}"
                            
                            messages.append({"role": "user", "content": obs_message})
                            
                            if done:
                                scores[task_id] = reward.value
                                details[task_id] = {
                                    "steps": step_count,
                                    "score": reward.value,
                                    "feedback": reward.feedback
                                }
                                break
                        else:
                            # Could not parse JSON, skip
                            messages.append({"role": "user", "content": "Your response had invalid JSON. Respond with ONLY a single valid JSON object. No newlines inside strings. No extra text."})
                            # don't increment step_count - give agent another chance
                            
                    except json.JSONDecodeError as e:
                        messages.append({"role": "user", "content": "Your response had invalid JSON. Respond with ONLY a single valid JSON object. No newlines inside strings. No extra text."})
                        # don't increment step_count - give agent another chance
                        
                except Exception as e:
                    # OpenAI API error
                    scores[task_id] = 0.0
                    details[task_id] = {"error": str(e)}
                    break
            
            if task_id not in scores:
                scores[task_id] = 0.0
                details[task_id] = {"error": "Max steps reached"}
            
            temp_env.db_manager.close()
        
        total_score = sum(scores.values()) / len(scores) if scores else 0.0
        
        return {
            "scores": scores,
            "average": total_score,
            "model": "llama-3.1-8b-instant"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}\n{traceback.format_exc()}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860)
