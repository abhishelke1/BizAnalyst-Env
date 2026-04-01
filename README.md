# 🔍 BizAnalyst-Env (SCOUT AI)

### *OpenEnv Business Intelligence Training Environment*

[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111.0-green.svg)](https://fastapi.tiangolo.com)
[![OpenEnv](https://img.shields.io/badge/OpenEnv-1.0-orange.svg)](https://openenv.dev)

> **Train AI agents to be autonomous business analysts.**

BizAnalyst-Env is an OpenEnv-compliant training environment where AI agents learn to act as business analysts. Agents query a realistic SQL database to solve business problems: revenue analysis, churn prediction, and anomaly detection.

---

## 🎯 Environment Description & Motivation

**Real-World Task**: Business Intelligence Analysis

Business analysts spend hours querying databases, finding patterns, and making recommendations. This environment simulates that workflow:

1. Agent receives a business question
2. Agent explores database schema
3. Agent runs SQL queries to gather data
4. Agent synthesizes findings into actionable insights
5. Agent submits a structured answer

**Why This Matters**: Trains agents for real enterprise workflows that currently require expensive human analysts.

---

## 📋 OpenEnv Specification

This environment implements the full OpenEnv spec:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/reset` | POST | Reset environment with task_id |
| `/step` | POST | Execute action, get observation |
| `/state` | GET | Get current environment state |
| `/tasks` | GET | List all tasks with action schemas |
| `/grader` | POST | Grade an answer (0.0-1.0) |
| `/baseline` | POST | Run baseline agent on all tasks |

---

## 🎮 Action Space

**Type**: `discrete_structured`

| Action | Parameters | Description |
|--------|------------|-------------|
| `run_query` | `sql_query: str`, `reasoning: str` | Execute SQL query |
| `describe_table` | `table_name: str` | Get table schema |
| `list_tables` | - | List available tables |
| `submit_answer` | `answer: str`, `reasoning: str` | Submit final answer |

**Action Schema (Pydantic)**:
```python
class Action(BaseModel):
    action_type: ActionType  # run_query, describe_table, list_tables, submit_answer
    sql_query: Optional[str] = None
    table_name: Optional[str] = None
    answer: Optional[str] = None
    reasoning: Optional[str] = None
```

---

## 👁️ Observation Space

**Type**: `structured_text`

| Field | Type | Description |
|-------|------|-------------|
| `task_id` | str | Current task identifier |
| `task_description` | str | What the agent must accomplish |
| `step_number` | int | Current step (1-indexed) |
| `max_steps` | int | Maximum allowed steps |
| `query_result` | QueryResult | Results from last SQL query |
| `available_tables` | List[str] | Tables in database |
| `schema_info` | Dict | Table schemas if requested |
| `message` | str | Feedback message |
| `queries_used` | int | Queries executed so far |
| `answer_submitted` | bool | Whether answer was submitted |

**Observation Schema (Pydantic)**:
```python
class Observation(BaseModel):
    task_id: str
    task_description: str
    step_number: int
    max_steps: int
    query_result: Optional[QueryResult] = None
    available_tables: List[str]
    schema_info: Optional[Dict[str, Any]] = None
    message: str
    queries_used: int
    answer_submitted: bool
```

---

## 🏆 Tasks & Difficulty

| Task ID | Difficulty | Max Steps | Description |
|---------|------------|-----------|-------------|
| `revenue_summary` | 🟢 Easy | 10 | Calculate 2023 revenue, expenses, profit, and top region |
| `customer_churn_risk` | 🟡 Medium | 15 | Identify top 3 customers at churn risk (>90 days inactive) |
| `anomaly_investigation` | 🔴 Hard | 20 | Find revenue spike, negative margin product, duplicate orders |

### Task Details

**Easy - Revenue Summary**
- Query `monthly_revenue` table for 2023 totals
- Find which region had highest revenue
- Submit formatted string answer

**Medium - Customer Churn Risk**
- Calculate days since last order for each customer
- Filter customers with >90 days inactive
- Recommend re-engagement actions
- Submit JSON array answer

**Hard - Anomaly Investigation**
- Find month/year with >30% revenue spike
- Find product with negative profit margin
- Find customers with duplicate orders
- Submit JSON object with all findings

---

## 📊 Reward Function

**Type**: Continuous, shaped (0.0 to 1.0)

| Component | Weight | Description |
|-----------|--------|-------------|
| Answer Accuracy | 60% | Correct values in answer |
| Completeness | 25% | All required fields present |
| Efficiency | 15% | Fewer steps = higher reward |

**Partial Progress Signals**:
- +0.1 for each successful query
- +0.05 for exploring relevant tables
- -0.1 for syntax errors
- -0.2 for exceeding step limit

---

## 📈 Baseline Scores

Baseline agent using `gpt-4o-mini` (or `llama-3.1-8b-instant` via Groq):

| Task | Score | Steps Used |
|------|-------|------------|
| `revenue_summary` | **0.85** | 3 |
| `customer_churn_risk` | **0.72** | 4 |
| `anomaly_investigation` | **0.58** | 7 |
| **Average** | **0.72** | - |

*Scores may vary slightly due to LLM non-determinism.*

---

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set API Key

```bash
# Using OpenAI (recommended)
export OPENAI_API_KEY="sk-..."

# Or using Groq (free alternative)
export GROQ_API_KEY="gsk_..."
```

### 3. Start Server

```bash
python scout_server.py
```

Server runs at: **http://localhost:7860**

### 4. Run Baseline

```bash
python baseline.py
```

---

## 🔌 API Endpoints

### OpenEnv Standard Endpoints

```bash
# Reset environment with a task
POST /reset
{"task_id": "revenue_summary"}

# Execute an action
POST /step
{"action_type": "run_query", "sql_query": "SELECT * FROM customers LIMIT 5"}

# Get current state
GET /state

# List all tasks
GET /tasks

# Grade an answer
POST /grader
{"task_id": "revenue_summary", "answer": "Total Revenue: $4821540.23 | ..."}

# Run baseline on all tasks
POST /baseline
```

### SCOUT AI Endpoints (Bonus Features)

```bash
# Start autonomous investigation
POST /api/scout
{"question": "Why did revenue drop?", "max_steps": 10}

# Get investigation results
GET /api/scout/{task_id}

# Stream live reasoning steps
GET /api/scout/{task_id}/stream
```

### Interactive Dashboard

Navigate to: **http://localhost:7860/app**

---

## 🏗️ Project Structure

```
bizanalyst-env/
├── environment/
│   ├── env.py           # BizAnalystEnv (step/reset/state)
│   ├── models.py        # Pydantic models (Action, Observation, Reward)
│   ├── database.py      # SQLite database manager
│   └── tasks.py         # Task definitions & graders
├── agent/
│   ├── core.py          # SCOUT autonomous agent
│   ├── memory.py        # Agent memory system
│   └── analyzer.py      # Business insight analyzer
├── frontend/
│   └── index.html       # Interactive dashboard
├── tests/
│   └── test_env.py      # Environment tests
├── scout_server.py      # FastAPI server
├── baseline.py          # Baseline inference script
├── openenv.yaml         # OpenEnv metadata
├── Dockerfile           # Container configuration
└── requirements.txt     # Dependencies
```

---

## 📈 Database Schema

**Northwind-based** business database with planted scenarios:

| Table | Columns | Records |
|-------|---------|---------|
| `customers` | customer_id, name, region, segment, signup_date, last_order_date, total_spent, order_count | 93 |
| `products` | product_id, name, category, unit_price, cost_price, stock_quantity | 69 |
| `orders` | order_id, customer_id, order_date, status, total_amount, discount_pct | 16,000+ |
| `order_items` | item_id, order_id, product_id, quantity, unit_price | 600,000+ |
| `monthly_revenue` | id, month, year, revenue, expenses, profit, region, category | 48 |

### Planted Scenarios (for evaluation)

- 📈 **Revenue Spike**: March 2024 shows >30% anomaly
- 💸 **Negative Margin**: One product has cost > price
- ⚠️ **Churn Risk**: Several customers inactive >90 days
- 🔁 **Duplicate Orders**: Data quality issues present

---

## 🔧 Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | - | OpenAI API key (primary) |
| `GROQ_API_KEY` | - | Groq API key (fallback) |
| `PORT` | 7860 | Server port |

---

## 🐳 Docker

```bash
# Build
docker build -t bizanalyst-env .

# Run with OpenAI
docker run -p 7860:7860 -e OPENAI_API_KEY=sk-... bizanalyst-env

# Run with Groq
docker run -p 7860:7860 -e GROQ_API_KEY=gsk_... bizanalyst-env
```

---

## 🧪 Validation

```bash
# Run tests
pytest tests/ -v

# Validate OpenEnv spec
openenv validate
```

---

## 📄 License

MIT License

---

## 🏆 OpenEnv Hackathon

**Domain**: Business Intelligence  
**Real-world task**: ✅ Yes - simulates actual BI analyst workflows  
**Difficulty range**: Easy → Medium → Hard  
**Graders**: Deterministic, 0.0-1.0 scores  
**Baseline**: Reproducible with OpenAI/Groq

---

**Built for the OpenEnv Hackathon** 🚀
