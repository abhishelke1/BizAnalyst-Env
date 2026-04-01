# 🔍 SCOUT AI — Autonomous Business Analyst Agent

> **AI that analyzes your business data and tells you what to do — before you ask.**

[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/)
[![OpenEnv](https://img.shields.io/badge/OpenEnv-1.0-orange.svg)](https://openenv.dev)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg)](https://www.docker.com/)

---

## 🎯 The Problem

Business analysts spend **hours every day** manually querying databases, hunting for anomalies, and building reports. Most BI tools just show dashboards — they don't **think**.

**What if AI could do the analyst's job autonomously?**

---

## 💡 The Solution: SCOUT AI

SCOUT is an **autonomous AI agent** that:

1. **Scans your database automatically** — finds issues before you ask
2. **Chains multiple SQL queries** — investigates root causes
3. **Generates actionable insights** — with specific recommendations
4. **Shows its reasoning** — transparent decision-making

### Demo Example

```
🔍 SCOUT Auto-Scan Results:

🔴 CRITICAL: Revenue Spike in March 2024
   → Revenue 47% above average
   → Impact: +$180K unexpected
   → Recommendation: Investigate if repeatable or one-time

🔴 CRITICAL: Product "Chai" has -13% margin
   → Selling below cost ($18.00 price, $20.70 cost)
   → Impact: Losing $2.70 per unit
   → Recommendation: Increase price immediately

🟡 WARNING: 3 customers at churn risk
   → Inactive 90+ days, $45K ARR at risk
   → Recommendation: Launch re-engagement campaign
```

**Total time: 2 seconds** (vs hours of manual analysis)

---

## 🏆 Why This Wins

| Traditional BI | SCOUT AI |
|----------------|----------|
| Shows dashboards | **Investigates autonomously** |
| You ask questions | **Finds problems first** |
| Raw data | **Actionable recommendations** |
| Static reports | **Live reasoning display** |

---

## 📊 Baseline Scores

| Task | Difficulty | Score | Steps |
|------|------------|-------|-------|
| `revenue_summary` | 🟢 Easy | **0.85** | 3 |
| `customer_churn_risk` | 🟡 Medium | **0.72** | 4 |
| `anomaly_investigation` | 🔴 Hard | **0.58** | 7 |
| **Average** | - | **0.72** | - |

---

## 🚀 Quick Start

```bash
# 1. Set API key
export OPENAI_API_KEY="sk-..."  # or GROQ_API_KEY

# 2. Start server
python scout_server.py

# 3. Open dashboard
open http://localhost:7860/app
```

The dashboard **auto-scans** and shows findings immediately!

---

## 🔌 OpenEnv API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/reset` | POST | Reset with task_id |
| `/step` | POST | Execute action |
| `/state` | GET | Current state |
| `/tasks` | GET | List all tasks |
| `/grader` | POST | Grade answer (0.0-1.0) |
| `/baseline` | POST | Run baseline agent |

### Bonus Endpoints (SCOUT Features)

| Endpoint | Description |
|----------|-------------|
| `/api/scan` | **Auto-discover issues** (no input needed) |
| `/api/scout` | Start autonomous investigation |
| `/app` | Interactive dashboard |

---

## 🎮 Action Space

```python
class Action(BaseModel):
    action_type: ActionType  # run_query, describe_table, list_tables, submit_answer
    sql_query: Optional[str] = None
    table_name: Optional[str] = None
    answer: Optional[str] = None
    reasoning: Optional[str] = None
```

**Actions:** `run_query`, `describe_table`, `list_tables`, `submit_answer`

---

## 👁️ Observation Space

```python
class Observation(BaseModel):
    task_id: str
    task_description: str
    step_number: int
    max_steps: int
    query_result: Optional[QueryResult]
    available_tables: List[str]
    message: str
    queries_used: int
    answer_submitted: bool
```

---

## 🏆 Tasks (Easy → Hard)

### Task 1: Revenue Summary (Easy)
Calculate 2023 totals and top region. Submit formatted string.

### Task 2: Customer Churn Risk (Medium)
Find customers inactive >90 days. Submit JSON array with recommendations.

### Task 3: Anomaly Investigation (Hard)
Find revenue spike, negative margin product, duplicate orders. Submit JSON object.

---

## 📊 Reward Function

| Component | Weight | Description |
|-----------|--------|-------------|
| Answer Accuracy | 60% | Correct values |
| Completeness | 25% | All fields present |
| Efficiency | 15% | Fewer steps = higher reward |

**Partial progress signals:** +0.1 per successful query, -0.1 for errors.

---

## 🐳 Docker

```bash
docker build -t scout-ai .
docker run -p 7860:7860 -e OPENAI_API_KEY=sk-... scout-ai
```

---

## 📁 Project Structure

```
scout-ai/
├── environment/          # OpenEnv implementation
│   ├── env.py           # step(), reset(), state()
│   ├── models.py        # Pydantic Action/Observation/Reward
│   └── tasks.py         # 3 tasks with graders
├── agent/               # SCOUT autonomous agent
│   ├── core.py          # Reasoning loop
│   ├── scanner.py       # Auto-discovery engine
│   └── analyzer.py      # Insight generation
├── scout_server.py      # FastAPI server
├── baseline.py          # Baseline inference script
├── openenv.yaml         # OpenEnv metadata
└── Dockerfile           # Container config
```

---

## 🎯 Real-World Utility

This environment trains agents for **actual enterprise workflows**:

- **Revenue analysis** — find trends, anomalies, opportunities
- **Churn prediction** — identify at-risk customers
- **Anomaly detection** — catch data quality issues
- **Root cause analysis** — investigate why metrics changed

**Companies can use SCOUT today** to reduce analyst workload.

---

## 📄 License

MIT License

---

**Built for the OpenEnv Hackathon** 🚀

*From question to decision in seconds.*
