# BizAnalyst-Env

[![OpenEnv](https://img.shields.io/badge/OpenEnv-Compatible-blue)](https://openenv.dev)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111.0-green.svg)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg)](https://www.docker.com/)

> A production-ready OpenEnv environment for training AI agents as business analysts

## Motivation

Every company employs data analysts who query databases, identify trends, detect anomalies, and generate business insights. **BizAnalyst-Env** simulates this real-world workflow, creating a valuable training ground for AI agents to develop commercial BI automation capabilities.

By mastering this environment, agents learn to:
- Query multi-table relational databases with SQL
- Analyze business metrics (revenue, expenses, profit)
- Identify at-risk customers and churn patterns
- Detect financial anomalies and duplicate records
- Provide actionable business recommendations

This directly models tasks performed daily by analysts in enterprise settings, making it a highly practical and commercially valuable benchmark.

---

## Environment Description

**BizAnalyst-Env** is a business intelligence environment where AI agents act as data analysts. Agents interact with a realistic SQLite database containing sales, customer, product, and revenue data to complete three analytical tasks of varying difficulty.

### Database Schema

The environment includes 5 interconnected tables with 200+ customers, 50 products, and 1000+ orders:

```
┌─────────────────────────────────────────────────────────────────────────┐
│  CUSTOMERS                         PRODUCTS                             │
│  ├─ customer_id (PK)               ├─ product_id (PK)                   │
│  ├─ name                           ├─ name                              │
│  ├─ region (North/South/East/West) ├─ category (5 categories)           │
│  ├─ segment (Enterprise/SMB/       ├─ unit_price                        │
│  │   Consumer)                     ├─ cost_price                        │
│  ├─ signup_date                    └─ stock_quantity                    │
│  ├─ last_order_date                                                     │
│  ├─ total_spent                         ▲                               │
│  └─ order_count                         │                               │
│           │                             │                               │
│           ▼                             │                               │
│  ORDERS                                 │                               │
│  ├─ order_id (PK)                       │                               │
│  ├─ customer_id (FK) ───────────────────┘                               │
│  ├─ order_date                                                          │
│  ├─ status                         ORDER_ITEMS                          │
│  ├─ total_amount                   ├─ item_id (PK)                      │
│  └─ discount_pct                   ├─ order_id (FK) ─────────┐          │
│           │                        ├─ product_id (FK) ────────┼─────┐   │
│           └────────────────────────┤ quantity                │     │   │
│                                    └─ unit_price             │     │   │
│                                                              │     │   │
│  MONTHLY_REVENUE                                            │     │   │
│  ├─ id (PK)                                                 │     │   │
│  ├─ month, year                                             │     │   │
│  ├─ revenue                                                 │     │   │
│  ├─ expenses                                                │     │   │
│  ├─ profit                                                  │     │   │
│  ├─ region                                                  │     │   │
│  └─ category                                                │     │   │
└─────────────────────────────────────────────────────────────┴─────┴───┘
```

**Planted Anomalies** (deterministic, seed=42):
- 📈 **Revenue Spike**: March 2024 shows 43% increase vs 6-month average
- 💸 **Negative Margin**: "Premium Wireless Keyboard" (unit_price=$45, cost=$52)
- ⚠️ **Churn Risk**: Customers with IDs ending in 07, 23, 89 (last order >120 days ago)
- 🔁 **Duplicate Orders**: Customers 15 and 67 have duplicate entries (same date, same amount)

---

## Action Space

Agents can take 4 discrete structured actions:

| Action Type | Fields | Description |
|------------|--------|-------------|
| `run_query` | `sql_query` (str) | Execute a SELECT query on the database |
| `describe_table` | `table_name` (str) | Get schema information for a specific table |
| `list_tables` | - | List all available tables in the database |
| `submit_answer` | `answer` (str) | Submit the final analytical answer |

**Additional Fields** (optional for all actions):
- `reasoning` (str): Agent's internal reasoning (logged but not graded)

**SQL Security**: Only `SELECT` queries are allowed. `INSERT`, `UPDATE`, `DELETE`, `DROP`, and other modifying operations are blocked.

---

## Observation Space

Agents receive structured observations after each action:

| Field | Type | Description |
|-------|------|-------------|
| `task_id` | str | Identifier of the current task |
| `task_description` | str | Full task description and requirements |
| `step_number` | int | Current step count |
| `max_steps` | int | Maximum allowed steps for this task |
| `query_result` | QueryResult | Results from the last SQL query (if applicable) |
| `available_tables` | List[str] | List of all database tables |
| `schema_info` | Dict | Schema information (if DESCRIBE_TABLE was used) |
| `message` | str | Feedback message from the environment |
| `queries_used` | int | Total number of queries executed so far |
| `answer_submitted` | bool | Whether the final answer has been submitted |

**QueryResult Structure**:
- `columns`: List of column names
- `rows`: List of result rows (each row is a list)
- `row_count`: Number of rows returned
- `execution_time_ms`: Query execution time in milliseconds
- `error`: Error message (if query failed)

---

## Reward Function

The environment uses a **shaped reward** system with both intermediate and terminal rewards.

### Intermediate Rewards (during episode)
- **Table Exploration**: +0.02 for first query to a new table
- **Successful Query**: +0.01 for valid query execution
- **Query with Results**: +0.01 additional if query returns data
- **Failed Query**: -0.02 for SQL errors or validation failures

### Task-Specific Intermediate Rewards
- **Revenue Summary**: +0.1 for first query to `monthly_revenue`, +0.05 for filtering by year 2023
- *More task-specific bonuses available during execution*

### Terminal Rewards (at episode end)
Graded based on accuracy of the submitted answer:

**Revenue Summary (Easy)**:
- Revenue accuracy: 1.0 (within 1%), 0.5 (within 5%), 0.0 (otherwise)
- Expenses accuracy: Same scoring
- Profit accuracy: Same scoring
- Region correctness: 1.0 (exact match), 0.0 (wrong)
- **Efficiency penalty**: -0.05 per step beyond 3 steps
- **Final score**: Mean of component scores minus efficiency penalty

**Customer Churn Risk (Medium)**:
- Customer ID accuracy: 50% weight (proportion of correct IDs identified)
- Days-since-order accuracy: 30% weight
- Recommendation quality: 20% weight (keyword matching)

**Anomaly Investigation (Hard)**:
- Spike month/year: 20% weight
- Spike explanation: 10% weight (keyword matching)
- Negative margin product: 20% weight
- Margin percentage: 20% weight (with tolerance)
- Duplicate customer IDs: 30% weight (Jaccard similarity)
- **Bonus**: +0.1 if agent used window functions

All grading is **deterministic** (no LLM calls) for reproducibility.

---

## Tasks

| Task ID | Difficulty | Max Steps | Objective | Grading Criteria |
|---------|-----------|-----------|-----------|------------------|
| `revenue_summary` | Easy | 10 | Calculate total revenue, expenses, and profit for 2023; identify top revenue region | 4 numerical accuracy scores + region match - efficiency penalty |
| `customer_churn_risk` | Medium | 15 | Identify top 3 customers at churn risk (>90 days since last order); provide re-engagement recommendations | Customer ID accuracy (50%) + days accuracy (30%) + recommendation keywords (20%) |
| `anomaly_investigation` | Hard | 20 | Find revenue spike month, negative margin product with exact %, and duplicate order customers | Multi-component weighted scoring + window function bonus |

---

## Setup Instructions

### Option 1: Docker (Recommended)

Build and run with Docker:

```bash
# Build the image
docker build -t bizanalyst-env .

# Run the container
docker run -p 7860:7860 bizanalyst-env
```

The server will be available at `http://localhost:7860`

### Option 2: Local Installation

Install dependencies and run locally:

```bash
# Install dependencies
pip install -r requirements.txt

# Start the server
uvicorn server:app --host 0.0.0.0 --port 8000
```

The server will be available at `http://localhost:8000`

### Option 3: Run Baseline Agent

To evaluate the baseline Llama-3.1-8B agent:

```bash
# Set your Groq API key (or use the embedded default)
export GROQ_API_KEY='your-api-key-here'

# Start the server (in separate terminal)
uvicorn server:app --host 0.0.0.0 --port 8000

# Run the baseline script
python baseline.py
```

Results will be saved to `baseline_results.json`

---

## API Reference

### `GET /`
Returns environment information card.

```bash
curl http://localhost:8000/
```

### `GET /health`
Health check endpoint.

```bash
curl http://localhost:8000/health
```

**Response**:
```json
{
  "status": "ok",
  "env": "BizAnalyst-Env",
  "version": "1.0.0"
}
```

### `POST /reset`
Initialize environment with a task.

```bash
curl -X POST http://localhost:8000/reset \
  -H "Content-Type: application/json" \
  -d '{"task_id": "revenue_summary"}'
```

**Response**: Initial `Observation` object

### `POST /step`
Execute an action in the environment.

```bash
# List tables
curl -X POST http://localhost:8000/step \
  -H "Content-Type: application/json" \
  -d '{"action_type": "list_tables"}'

# Run query
curl -X POST http://localhost:8000/step \
  -H "Content-Type: application/json" \
  -d '{
    "action_type": "run_query",
    "sql_query": "SELECT * FROM customers LIMIT 5"
  }'

# Submit answer
curl -X POST http://localhost:8000/step \
  -H "Content-Type: application/json" \
  -d '{
    "action_type": "submit_answer",
    "answer": "Total Revenue: $X | Total Expenses: $Y | Net Profit: $Z | Top Region: ABC"
  }'
```

**Response**:
```json
{
  "observation": { ... },
  "reward": { "value": 0.85, "components": {...}, "feedback": "...", "is_terminal": true },
  "done": true,
  "info": { "step_count": 5, "queries_executed": 3 }
}
```

### `GET /state`
Get current environment state.

```bash
curl http://localhost:8000/state
```

### `GET /tasks`
List all available tasks with schemas.

```bash
curl http://localhost:8000/tasks
```

### `POST /grader`
Test answer grading without running full episode.

```bash
curl -X POST http://localhost:8000/grader \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "revenue_summary",
    "answer": "Total Revenue: $1000000 | Total Expenses: $800000 | Net Profit: $200000 | Top Region: North"
  }'
```

**Response**:
```json
{
  "score": 0.75,
  "breakdown": {"revenue_score": 1.0, "expenses_score": 0.5, ...},
  "feedback": "Revenue: 1.00, Expenses: 0.50, ..."
}
```

### `POST /baseline`
Run baseline agent internally on specified tasks.

```bash
curl -X POST http://localhost:8000/baseline \
  -H "Content-Type: application/json" \
  -d '{
    "task_ids": ["revenue_summary", "customer_churn_risk", "anomaly_investigation"]
  }'
```

**Note**: Requires `GROQ_API_KEY` environment variable (or uses embedded default).

---

## Baseline Scores

Expected scores for different model tiers:

| Task | Llama-3.1-8B Score | Expected Frontier Score |
|------|-------------------|------------------------|
| Revenue Summary | 0.75 - 0.90 | 0.95 - 1.00 |
| Customer Churn Risk | 0.50 - 0.70 | 0.85 - 0.95 |
| Anomaly Investigation | 0.40 - 0.65 | 0.80 - 0.95 |
| **Average** | **0.55 - 0.75** | **0.87 - 0.97** |

*Actual scores depend on model capabilities, prompting strategy, and query efficiency*

---

## Testing

Run the test suite with pytest:

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_env.py

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov=environment --cov=server
```

---

## OpenEnv Validation

Validate the environment configuration:

```bash
# Install OpenEnv CLI (if not already installed)
pip install openenv

# Validate the environment
openenv validate openenv.yaml
```

---

## Project Structure

```
bizanalyst-env/
├── Dockerfile                  # Docker container configuration
├── requirements.txt            # Python dependencies
├── openenv.yaml               # OpenEnv specification
├── README.md                  # This file
├── server.py                  # FastAPI server with all endpoints
├── baseline.py                # Baseline inference script
├── environment/
│   ├── __init__.py           # Package exports
│   ├── models.py             # Pydantic models (Action, Observation, Reward)
│   ├── env.py                # BizAnalystEnv class (reset, step, state)
│   ├── database.py           # Database manager (schema, seeding)
│   ├── tasks.py              # Task definitions and graders
│   └── validators.py         # SQL query validation
└── tests/
    ├── test_env.py           # Environment unit tests
    ├── test_graders.py       # Grader accuracy tests
    └── test_api.py           # API endpoint tests
```

---

## License

MIT License - see LICENSE file for details

---

## Contributing

Contributions welcome! Please open an issue or submit a pull request.

---

## Citation

If you use BizAnalyst-Env in your research, please cite:

```bibtex
@software{bizanalyst_env_2024,
  title={BizAnalyst-Env: A Business Intelligence Environment for AI Agents},
  author={Your Name},
  year={2024},
  url={https://github.com/yourusername/bizanalyst-env}
}
```

---

## Acknowledgments

Built with:
- [FastAPI](https://fastapi.tiangolo.com/) - Modern web framework
- [Pydantic](https://pydantic-docs.helpmanual.io/) - Data validation
- [Faker](https://faker.readthedocs.io/) - Fake data generation
- [Groq API](https://groq.com/) - Baseline agent inference (Llama-3.1-8B)
- [OpenEnv](https://openenv.dev) - Environment specification standard

---

**Questions?** Open an issue or contact the maintainers.

**Ready to train agents?** Start the server and begin exploring! 🚀
