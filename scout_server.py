"""SCOUT AI API Server - FastAPI endpoints for autonomous business analyst."""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pathlib import Path
from typing import Dict, Any, List, Optional
import traceback
import json
import os
import uuid
import asyncio
from datetime import datetime

from environment import BizAnalystEnv, Action, ActionType

# Lazy imports for agent modules - these require GROQ_API_KEY
try:
    from agent.core import ScoutAgent, AgentResult
    from agent.memory import AgentMemory
    from agent.scanner import AutoScanner
    AGENT_AVAILABLE = True
except Exception:
    AGENT_AVAILABLE = False
    ScoutAgent = None
    AgentResult = None
    AgentMemory = None
    AutoScanner = None

# Initialize FastAPI app
app = FastAPI(
    title="SCOUT AI",
    description="Autonomous AI Business Analyst - From question to decision in seconds",
    version="2.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve frontend
FRONTEND_DIR = Path(__file__).parent / "frontend"


@app.get("/app")
async def serve_frontend():
    """Serve the SCOUT AI frontend."""
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    raise HTTPException(status_code=404, detail="Frontend not available")

# Global environment instance
env = BizAnalystEnv()

# Task storage for async operations
tasks_store: Dict[str, Dict[str, Any]] = {}


# ─────────────────────────────────────────────────────────────
# REQUEST/RESPONSE MODELS
# ─────────────────────────────────────────────────────────────

class ScoutTaskRequest(BaseModel):
    """Request to start a SCOUT investigation."""
    question: str
    max_steps: int = 10


class ScoutTaskResponse(BaseModel):
    """Response from SCOUT investigation."""
    task_id: str
    status: str
    question: str


class ScoutResultResponse(BaseModel):
    """Full result from SCOUT investigation."""
    task_id: str
    status: str
    question: str
    answer: Optional[str] = None
    insights: List[Dict[str, Any]] = []
    recommendations: Optional[Dict[str, Any]] = None
    steps: List[Dict[str, Any]] = []
    total_queries: int = 0
    confidence: float = 0.0
    execution_time: float = 0.0


class ResetRequest(BaseModel):
    task_id: Optional[str] = None  # Make it truly optional


class StepResponse(BaseModel):
    observation: Dict[str, Any]
    reward: Dict[str, Any]
    done: bool
    info: Dict[str, Any]


class QueryRequest(BaseModel):
    """Direct SQL query request."""
    sql: str


# ─────────────────────────────────────────────────────────────
# SCOUT AI ENDPOINTS
# ─────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    """Return SCOUT info card."""
    return {
        "name": "SCOUT AI",
        "tagline": "Your AI Business Analyst That Never Sleeps",
        "version": "2.0.0",
        "status": "running",
        "capabilities": [
            "Autonomous multi-step investigation",
            "Real-time reasoning display",
            "Business recommendations with evidence",
            "Root cause analysis"
        ],
        "endpoints": {
            "scout": "/api/scout - Start AI investigation",
            "result": "/api/scout/{task_id} - Get investigation result",
            "stream": "/api/scout/{task_id}/stream - Stream live steps",
            "query": "/api/query - Direct SQL query",
            "schema": "/api/schema - Database schema"
        },
        "docs": "/docs"
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "SCOUT AI",
        "version": "2.0.0",
        "model": "llama-3.1-8b-instant"
    }


@app.post("/api/scout", response_model=ScoutTaskResponse)
async def start_scout_investigation(request: ScoutTaskRequest, background_tasks: BackgroundTasks):
    """
    Start a SCOUT AI investigation.
    
    SCOUT will autonomously:
    1. Analyze the question
    2. Plan investigation steps
    3. Execute SQL queries
    4. Analyze results
    5. Generate insights and recommendations
    """
    if not AGENT_AVAILABLE:
        raise HTTPException(status_code=503, detail="Agent modules not available")
    task_id = str(uuid.uuid4())[:8]
    
    # Store task
    tasks_store[task_id] = {
        "status": "running",
        "question": request.question,
        "max_steps": request.max_steps,
        "started_at": datetime.now().isoformat(),
        "steps": [],
        "result": None
    }
    
    # Run investigation in background
    background_tasks.add_task(run_scout_investigation, task_id, request.question, request.max_steps)
    
    return ScoutTaskResponse(
        task_id=task_id,
        status="running",
        question=request.question
    )


@app.get("/api/scout/{task_id}", response_model=ScoutResultResponse)
async def get_scout_result(task_id: str):
    """Get the result of a SCOUT investigation."""
    if task_id not in tasks_store:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    
    task = tasks_store[task_id]
    result = task.get("result")
    
    if result:
        return ScoutResultResponse(
            task_id=task_id,
            status=task["status"],
            question=task["question"],
            answer=result.answer,
            insights=result.insights,
            recommendations=result.recommendations,
            steps=[{
                "step": s.step_num,
                "type": s.step_type,
                "content": s.content,
                "data": s.data,
                "timestamp": s.timestamp
            } for s in result.steps],
            total_queries=result.total_queries,
            confidence=result.confidence,
            execution_time=result.execution_time
        )
    else:
        return ScoutResultResponse(
            task_id=task_id,
            status=task["status"],
            question=task["question"],
            steps=task.get("steps", [])
        )


@app.get("/api/scout/{task_id}/stream")
async def stream_scout_steps(task_id: str):
    """Stream SCOUT investigation steps in real-time using SSE."""
    if task_id not in tasks_store:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    
    async def event_stream():
        last_step_count = 0
        
        while True:
            task = tasks_store.get(task_id)
            if not task:
                break
            
            steps = task.get("steps", [])
            
            # Send new steps
            while last_step_count < len(steps):
                step = steps[last_step_count]
                yield f"data: {json.dumps(step)}\n\n"
                last_step_count += 1
            
            # Check if complete
            if task["status"] in ["complete", "error"]:
                result = task.get("result")
                if result:
                    yield f"data: {json.dumps({'type': 'COMPLETE', 'result': {'answer': result.answer, 'confidence': result.confidence}})}\n\n"
                break
            
            await asyncio.sleep(0.5)
    
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive"
        }
    )


@app.post("/api/query")
async def execute_query(request: QueryRequest):
    """Execute a direct SQL query on the database."""
    try:
        # Initialize environment if needed
        if not env.db_manager:
            env.reset("revenue_summary")
        
        result = execute_sql(request.sql)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/schema")
async def get_schema():
    """Get database schema information."""
    return {
        "tables": {
            "customers": {
                "columns": ["customer_id", "name", "region", "segment", "signup_date", "last_order_date", "total_spent", "order_count"],
                "description": "Customer information and metrics"
            },
            "products": {
                "columns": ["product_id", "name", "category", "unit_price", "cost_price", "stock_quantity"],
                "description": "Product catalog with pricing"
            },
            "orders": {
                "columns": ["order_id", "customer_id", "order_date", "status", "total_amount", "discount_pct"],
                "description": "Order transactions"
            },
            "order_items": {
                "columns": ["item_id", "order_id", "product_id", "quantity", "unit_price"],
                "description": "Line items for each order"
            },
            "monthly_revenue": {
                "columns": ["id", "month", "year", "revenue", "expenses", "profit", "region", "category"],
                "description": "Aggregated monthly financial data"
            }
        },
        "reference_date": "2024-06-01",
        "total_customers": 93,
        "total_products": 69,
        "total_orders": "16,000+"
    }


@app.get("/api/demo-tasks")
async def get_demo_tasks():
    """Get pre-built demo tasks for showcase."""
    return {
        "tasks": [
            {
                "id": "revenue_analysis",
                "question": "Why did revenue change between 2023 and 2024, and what should we do about it?",
                "category": "Revenue Analysis",
                "expected_steps": 4
            },
            {
                "id": "churn_risk",
                "question": "Which customers are at risk of churning and how should we re-engage them?",
                "category": "Customer Retention",
                "expected_steps": 3
            },
            {
                "id": "profit_optimization",
                "question": "Are there any products with pricing problems affecting our margins?",
                "category": "Profitability",
                "expected_steps": 3
            },
            {
                "id": "anomaly_detection",
                "question": "Are there any unusual patterns or anomalies in our business data?",
                "category": "Anomaly Detection",
                "expected_steps": 5
            },
            {
                "id": "regional_performance",
                "question": "How do different regions compare in performance, and where should we focus?",
                "category": "Regional Analysis",
                "expected_steps": 4
            }
        ]
    }


# ─────────────────────────────────────────────────────────────
# AUTO-SCAN ENDPOINT (Critical for winning demo)
# ─────────────────────────────────────────────────────────────

@app.get("/api/scan")
async def auto_scan():
    """
    AUTO-DISCOVERY: Scan database for business issues without user input.
    
    This is the WOW MOMENT - AI takes initiative and finds problems
    before anyone asks. Returns severity-ranked alerts with recommendations.
    """
    if not AGENT_AVAILABLE or AutoScanner is None:
        raise HTTPException(status_code=503, detail="Agent modules not available")
    try:
        scanner = AutoScanner(execute_sql)
        results = scanner.scan_all()
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scan failed: {str(e)}")


@app.get("/api/scan/{alert_id}/investigate")
async def investigate_alert(alert_id: str, background_tasks: BackgroundTasks):
    """
    Investigate a specific alert found by auto-scan.
    
    Takes an alert ID and runs a full SCOUT investigation to get
    root cause and recommendations.
    """
    # Map alert categories to investigation questions
    investigation_map = {
        "churn": "Analyze our customers at churn risk in detail. Who are they, how much revenue is at risk, and what specific actions should we take for each?",
        "revenue": "Investigate the revenue anomaly. What caused it? Is it repeatable? What should we do?",
        "margin": "Analyze the negative margin products. Why is pricing wrong? What's the business impact? Should we fix pricing or discontinue?",
        "data_quality": "Investigate the data quality issues. What's the scope? How does it affect our reporting?"
    }
    
    # Determine category from alert_id
    category = "revenue"  # default
    if "churn" in alert_id:
        category = "churn"
    elif "margin" in alert_id:
        category = "margin"
    elif "duplicate" in alert_id or "data" in alert_id:
        category = "data_quality"
    elif "rev" in alert_id:
        category = "revenue"
    
    question = investigation_map.get(category, investigation_map["revenue"])
    
    # Start investigation
    task_id = str(uuid.uuid4())[:8]
    tasks_store[task_id] = {
        "status": "running",
        "question": question,
        "max_steps": 8,
        "started_at": datetime.now().isoformat(),
        "alert_id": alert_id,
        "steps": [],
        "result": None
    }
    
    background_tasks.add_task(run_scout_investigation, task_id, question, 8)
    
    return {
        "task_id": task_id,
        "status": "investigating",
        "alert_id": alert_id,
        "question": question
    }


# ─────────────────────────────────────────────────────────────
# LEGACY ENDPOINTS (for baseline compatibility)
# ─────────────────────────────────────────────────────────────

@app.post("/reset")
async def reset(request: ResetRequest = None):
    """Reset environment with a task."""
    try:
        # Handle null/empty body by using default task
        if request is None or not hasattr(request, 'task_id'):
            task_id = "revenue_summary"
        else:
            task_id = request.task_id or "revenue_summary"
        
        observation = env.reset(task_id)
        return observation.model_dump()
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        import traceback
        error_detail = f"Internal error: {str(e)}\n{traceback.format_exc()}"
        raise HTTPException(status_code=500, detail=error_detail)


@app.post("/step")
async def step(action: Action) -> StepResponse:
    """Execute an action in the environment."""
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
    """Get current environment state."""
    try:
        return env.state()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@app.get("/tasks")
async def get_tasks():
    """Get all task definitions."""
    try:
        temp_env = BizAnalystEnv()
        temp_env.reset("revenue_summary")
        tasks = temp_env.task_manager.list_tasks()
        temp_env.db_manager.close()
        return tasks
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


# ─────────────────────────────────────────────────────────────
# GRADER ENDPOINT (Required by OpenEnv spec)
# ─────────────────────────────────────────────────────────────

class GraderRequest(BaseModel):
    task_id: str
    answer: str


class GraderResponse(BaseModel):
    score: float
    breakdown: Dict[str, float]
    feedback: str


@app.post("/grader")
async def grade_answer(request: GraderRequest) -> GraderResponse:
    """Grade an answer for a specific task.
    
    Args:
        request: Contains task_id and answer
        
    Returns:
        Grading results with score 0.0-1.0
    """
    try:
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
        
        # Hackathon Phase 2 strict validation: ALL scores must be strictly between 0 and 1 (exclusive)
        def clamp_score(s):
            return max(0.001, min(0.999, float(s)))
        
        clamped_score = clamp_score(score)
        clamped_breakdown = {k: clamp_score(v) for k, v in breakdown.items()}
        
        temp_env.db_manager.close()
        
        return GraderResponse(
            score=clamped_score,
            breakdown=clamped_breakdown,
            feedback=feedback
        )
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


# ─────────────────────────────────────────────────────────────
# BASELINE ENDPOINT (Required by OpenEnv spec)
# ─────────────────────────────────────────────────────────────

class BaselineRequest(BaseModel):
    task_ids: Optional[List[str]] = None


class BaselineResponse(BaseModel):
    scores: Dict[str, float]
    average: float
    model: str


@app.post("/baseline")
async def run_baseline(request: BaselineRequest = None) -> BaselineResponse:
    """Run baseline agent on all tasks.
    
    Returns:
        Baseline scores for all 3 tasks
    """
    try:
        from openai import OpenAI
        import time
        
        # Support both OPENAI_API_KEY and GROQ_API_KEY
        api_key = os.getenv("OPENAI_API_KEY") or os.getenv("GROQ_API_KEY")
        if not api_key:
            raise HTTPException(
                status_code=422,
                detail="OPENAI_API_KEY or GROQ_API_KEY environment variable not set"
            )
        
        # Determine which API to use
        if os.getenv("OPENAI_API_KEY"):
            client = OpenAI(api_key=api_key)
            model = "gpt-4o-mini"
        else:
            client = OpenAI(
                api_key=api_key,
                base_url="https://api.groq.com/openai/v1"
            )
            model = "llama-3.1-8b-instant"
        
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
[{"customer_id": 7, "name": "John Doe", "days_since_last_order": 150, "recommendation": "Send discount email offer"}]

Task anomaly_investigation answer format (JSON object):
{"spike_month": 3, "spike_year": 2024, "spike_explanation": "Seasonal promotion", "negative_margin_product": "Product Name", "margin_pct": -13.46, "duplicate_customer_ids": [15, 67]}

Actions:
{"action_type": "run_query", "sql_query": "SELECT ...", "reasoning": "..."}
{"action_type": "submit_answer", "answer": "EXACT FORMAT ABOVE", "reasoning": "..."}

Respond with a single JSON object only. No extra text."""
        
        # Default to all 3 tasks
        task_ids = ["revenue_summary", "customer_churn_risk", "anomaly_investigation"]
        if request and request.task_ids:
            task_ids = request.task_ids
        
        scores = {}
        
        for task_id in task_ids:
            temp_env = BizAnalystEnv()
            obs = temp_env.reset(task_id)
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": obs.task_description}
            ]
            
            done = False
            step_count = 0
            max_steps = obs.max_steps
            
            while not done and step_count < max_steps:
                try:
                    time.sleep(1)  # Rate limiting
                    
                    response = client.chat.completions.create(
                        model=model,
                        messages=messages,
                        temperature=0.0
                    )
                    
                    assistant_message = response.choices[0].message.content
                    messages.append({"role": "assistant", "content": assistant_message})
                    
                    # Parse JSON action
                    json_start = assistant_message.find('{')
                    json_end = assistant_message.rfind('}') + 1
                    if json_start >= 0 and json_end > json_start:
                        json_str = assistant_message[json_start:json_end]
                        action_dict = json.loads(json_str)
                        action = Action(**action_dict)
                        
                        observation, reward, done, info = temp_env.step(action)
                        step_count += 1
                        
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
                            break
                    else:
                        messages.append({"role": "user", "content": "Invalid JSON. Respond with ONLY a single valid JSON object."})
                        
                except json.JSONDecodeError:
                    messages.append({"role": "user", "content": "Invalid JSON. Respond with ONLY a single valid JSON object."})
                except Exception as e:
                    scores[task_id] = 0.001  # Strictly > 0 for Phase 2 validation
                    break
            
            if task_id not in scores:
                scores[task_id] = 0.001  # Strictly > 0 for Phase 2 validation
            
            temp_env.db_manager.close()
        
        avg_score = sum(scores.values()) / len(scores) if scores else 0.0
        
        return BaselineResponse(
            scores=scores,
            average=avg_score,
            model=model
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}\n{traceback.format_exc()}")


# ─────────────────────────────────────────────────────────────
# HELPER FUNCTIONS
# ─────────────────────────────────────────────────────────────

def execute_sql(sql: str) -> Dict[str, Any]:
    """Execute SQL query safely."""
    # Initialize environment if needed
    if not env.db_manager:
        env.reset("revenue_summary")
    
    # Block dangerous SQL
    dangerous = ['DROP', 'DELETE', 'INSERT', 'UPDATE', 'CREATE', 'ALTER']
    sql_upper = sql.upper()
    for keyword in dangerous:
        if keyword in sql_upper:
            return {"error": f"SQL keyword '{keyword}' not allowed", "rows": [], "row_count": 0}
    
    try:
        results = env.db_manager.execute_query(sql)
        rows = [dict(row) for row in results] if results else []
        columns = list(rows[0].keys()) if rows else []
        
        return {
            "success": True,
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
            "error": None
        }
    except Exception as e:
        return {
            "success": False,
            "columns": [],
            "rows": [],
            "row_count": 0,
            "error": str(e)
        }


async def run_scout_investigation(task_id: str, question: str, max_steps: int):
    """Run SCOUT investigation in background."""
    try:
        # Initialize agent
        agent = ScoutAgent()
        
        # Initialize environment
        temp_env = BizAnalystEnv()
        temp_env.reset("revenue_summary")  # Just to get DB connection
        
        def db_executor(sql: str) -> Dict[str, Any]:
            return execute_sql(sql)
        
        # Run with step logging
        tasks_store[task_id]["status"] = "investigating"
        
        result = agent.run(question, db_executor, max_steps)
        
        # Store steps as they happen
        tasks_store[task_id]["steps"] = [
            {
                "step": s.step_num,
                "type": s.step_type,
                "content": s.content,
                "data": s.data,
                "timestamp": s.timestamp
            }
            for s in result.steps
        ]
        
        tasks_store[task_id]["result"] = result
        tasks_store[task_id]["status"] = "complete"
        tasks_store[task_id]["completed_at"] = datetime.now().isoformat()
        
        temp_env.db_manager.close()
        
    except Exception as e:
        tasks_store[task_id]["status"] = "error"
        tasks_store[task_id]["error"] = str(e)
        tasks_store[task_id]["traceback"] = traceback.format_exc()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860)
