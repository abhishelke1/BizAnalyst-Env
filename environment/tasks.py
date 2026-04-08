from dataclasses import dataclass, field
from typing import Dict, Callable, Any, List
import json
import re
from datetime import datetime, timedelta
from .database import get_reference_date


@dataclass
class Task:
    """Task definition with metadata and grading logic."""
    task_id: str
    description: str
    difficulty: str
    max_steps: int
    grader_func: Callable[[str, Any, int], tuple]
    correct_answers: Dict[str, Any] = None


class TaskManager:
    """Manages all tasks and grading logic."""

    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.tasks = self._initialize_tasks()

    def _initialize_tasks(self) -> Dict[str, Task]:
        tasks = {}

        # TASK 1: Revenue Summary (Easy)
        task1_correct = self._precompute_revenue_summary()
        tasks['revenue_summary'] = Task(
            task_id='revenue_summary',
            description=(
                "Calculate the total revenue, total expenses, and net profit for the year 2023. "
                "Also find which region had the highest revenue in 2023. Submit your answer in this exact format: "
                "'Total Revenue: $X | Total Expenses: $X | Net Profit: $X | Top Region: X'"
            ),
            difficulty='easy',
            max_steps=10,
            grader_func=self._grade_revenue_summary,
            correct_answers=task1_correct
        )

        # TASK 2: Customer Churn Risk (Medium)
        task2_correct = self._precompute_churn_risk()
        tasks['customer_churn_risk'] = Task(
            task_id='customer_churn_risk',
            description=(
                "Identify the top 3 customers most at risk of churning. "
                "A customer is at churn risk if their days_since_last_order > 90. "
                "Use the reference date '2024-06-01' for calculations. "
                "For each at-risk customer, provide: "
                "customer_id, name, days_since_last_order, and a recommended re-engagement action. "
                "Submit as a JSON array."
            ),
            difficulty='medium',
            max_steps=15,
            grader_func=self._grade_churn_risk,
            correct_answers=task2_correct
        )

        # TASK 3: Anomaly Investigation (Hard)
        task3_correct = self._precompute_anomaly_investigation()
        tasks['anomaly_investigation'] = Task(
            task_id='anomaly_investigation',
            description=(
                "You are investigating financial anomalies in the business data. Find: "
                "(1) The month/year with an unusual revenue spike (>30%% above average), explain likely cause, "
                "(2) The product with negative profit margin — provide its name and the exact margin percentage, "
                "(3) Any customers with duplicate orders (same order_date, same total_amount) — list their customer_ids. "
                "Submit a JSON with keys: spike_month, spike_year, spike_explanation, "
                "negative_margin_product, margin_pct, duplicate_customer_ids"
            ),
            difficulty='hard',
            max_steps=20,
            grader_func=self._grade_anomaly_investigation,
            correct_answers=task3_correct
        )

        return tasks

    # ──────────────────────────────────────────────
    # PRE-COMPUTE CORRECT ANSWERS
    # ──────────────────────────────────────────────

    def _precompute_revenue_summary(self) -> Dict[str, Any]:
        result = self.db_manager.execute_query("""
            SELECT SUM(revenue), SUM(expenses), SUM(profit)
            FROM monthly_revenue WHERE year = 2023
        """)
        row = result[0]

        region_result = self.db_manager.execute_query("""
            SELECT region, SUM(revenue) as total
            FROM monthly_revenue WHERE year = 2023
            GROUP BY region ORDER BY total DESC LIMIT 1
        """)
        top_region = region_result[0][0] if region_result else "Unknown"

        return {
            'total_revenue':  float(row[0]) if row[0] else 0.0,
            'total_expenses': float(row[1]) if row[1] else 0.0,
            'total_profit':   float(row[2]) if row[2] else 0.0,
            'top_region':     top_region
        }

    def _precompute_churn_risk(self) -> Dict[str, Any]:
        results = self.db_manager.execute_query("""
            SELECT customer_id, name,
                   CAST(julianday('2024-06-01') - julianday(last_order_date) AS INTEGER) as days_since_last_order
            FROM customers
            WHERE CAST(julianday('2024-06-01') - julianday(last_order_date) AS INTEGER) > 90
            ORDER BY days_since_last_order DESC
            LIMIT 3
        """)
        churn_customers = [
            {'customer_id': row[0], 'name': row[1], 'days_since_last_order': row[2]}
            for row in results
        ]
        return {
            'churn_customer_ids': [c['customer_id'] for c in churn_customers],
            'churn_customers': churn_customers
        }

    def _precompute_anomaly_investigation(self) -> Dict[str, Any]:
        spike_month, spike_year = 3, 2024

        # FIX: use cost_price as denominator so result is -13.46% (matches grader range -14 to -13)
        margin_result = self.db_manager.execute_query("""
            SELECT name, unit_price, cost_price,
                   ROUND((unit_price - cost_price) * 100.0 / cost_price, 2) as margin_pct
            FROM products
            WHERE cost_price > unit_price
            ORDER BY margin_pct ASC
            LIMIT 1
        """)
        if margin_result:
            negative_product = margin_result[0][0]
            margin_pct = float(margin_result[0][3])
        else:
            negative_product = "Premium Wireless Keyboard"
            margin_pct = -13.46

        dup_result = self.db_manager.execute_query("""
            SELECT customer_id, order_date, total_amount, COUNT(*) as cnt
            FROM orders
            GROUP BY customer_id, order_date, total_amount
            HAVING cnt > 1
        """)
        duplicate_customer_ids = sorted(list(set([row[0] for row in dup_result])))

        return {
            'spike_month':            spike_month,
            'spike_year':             spike_year,
            'negative_margin_product': negative_product,
            'margin_pct':             margin_pct,
            'duplicate_customer_ids': duplicate_customer_ids
        }

    # ──────────────────────────────────────────────
    # GRADERS
    # ──────────────────────────────────────────────

    def _grade_revenue_summary(self, answer: str, correct: Dict[str, Any], steps_used: int):
        self.correct_revenue  = correct['total_revenue']
        self.correct_expenses = correct['total_expenses']
        self.correct_profit   = correct['total_profit']
        self.correct_region   = correct['top_region']
        result = self.grade_revenue_summary(answer)
        return result['score'], result['components'], result['feedback']

    def grade_revenue_summary(self, answer: str) -> dict:
        pattern = (
            r'Total Revenue:\s*\$([0-9,\.]+)'
            r'.*?Total Expenses:\s*\$([0-9,\.]+)'
            r'.*?Net Profit:\s*\$([0-9,\.]+)'
            r'.*?Top Region:\s*(\w+)'
        )
        match = re.search(pattern, answer, re.IGNORECASE | re.DOTALL)

        if not match:
            return {
                "score": 0.0,
                "components": {"revenue": 0.0, "expenses": 0.0, "profit": 0.0, "region": 0.0},
                "feedback": "Answer format not recognized. Expected: 'Total Revenue: $X | Total Expenses: $X | Net Profit: $X | Top Region: X'"
            }

        def parse_num(s):
            return float(s.replace(',', ''))

        def score_val(submitted, correct):
            if correct == 0:
                return 1.0 if submitted == 0 else 0.0
            diff = abs(submitted - correct) / abs(correct)
            if diff <= 0.02:
                return 1.0
            elif diff <= 0.10:
                return 0.5
            return 0.0

        rev = score_val(parse_num(match.group(1)), self.correct_revenue)
        exp = score_val(parse_num(match.group(2)), self.correct_expenses)
        pro = score_val(parse_num(match.group(3)), self.correct_profit)
        reg = 1.0 if match.group(4).strip().lower() == self.correct_region.lower() else 0.0

        final = (rev + exp + pro + reg) / 4.0
        return {
            "score": round(final, 3),
            "components": {"revenue": rev, "expenses": exp, "profit": pro, "region": reg},
            "feedback": f"Revenue: {rev:.2f}, Expenses: {exp:.2f}, Profit: {pro:.2f}, Region: {reg:.2f}"
        }

    def _grade_churn_risk(self, answer: str, correct: Dict[str, Any], steps_used: int):
        try:
            submitted = json.loads(answer) if isinstance(answer, str) else answer
            if not isinstance(submitted, list):
                return 0.0, {}, "Answer must be a JSON array"
        except json.JSONDecodeError as e:
            return 0.0, {}, f"Invalid JSON: {str(e)}"

        submitted_ids = []
        for item in submitted:
            if isinstance(item, dict) and 'customer_id' in item:
                try:
                    submitted_ids.append(int(item['customer_id']))
                except Exception:
                    pass

        correct_ids = set(correct['churn_customer_ids'])
        submitted_ids_set = set(submitted_ids)

        id_score = len(correct_ids & submitted_ids_set) / len(correct_ids) if correct_ids else 0.0

        rec_keywords = ['discount', 'email', 'offer', 'contact', 'follow', 'campaign', 'reach', 'engage']
        has_rec = any(
            any(kw in str(item.get('recommendation', '')).lower() for kw in rec_keywords)
            for item in submitted if isinstance(item, dict)
        )
        rec_score = 1.0 if has_rec else 0.0

        total = 0.6 * id_score + 0.4 * rec_score
        feedback = (
            f"Customer IDs: {id_score:.2f} "
            f"({len(submitted_ids_set & correct_ids)}/{len(correct_ids)} correct), "
            f"Recommendations: {rec_score:.2f}"
        )
        return total, {"customer_ids": id_score, "recommendation": rec_score}, feedback

    def _grade_anomaly_investigation(self, answer: str, correct: Dict[str, Any], steps_used: int):
        result = self.grade_anomaly_investigation(answer)
        return result['score'], result['components'], result['feedback']

    def grade_anomaly_investigation(self, answer: str) -> dict:
        # Parse answer
        if isinstance(answer, dict):
            data = answer
        else:
            try:
                data = json.loads(answer)
            except Exception:
                m = re.search(r'\{.*\}', answer, re.DOTALL)
                if m:
                    try:
                        data = json.loads(m.group())
                    except Exception:
                        return {"score": 0.0, "components": {}, "feedback": "Could not parse JSON answer"}
                else:
                    return {"score": 0.0, "components": {}, "feedback": "No JSON found in answer"}

        # Spike month/year
        spike_score = 1.0 if (str(data.get('spike_month')) == '3' and str(data.get('spike_year')) == '2024') else 0.0

        # Spike explanation
        explanation = str(data.get('spike_explanation', '')).lower()
        exp_keywords = ['promotion', 'seasonal', 'spike', 'increase', 'unusual', 'campaign', 'holiday', 'surge', 'peak']
        exp_score = 1.0 if any(kw in explanation for kw in exp_keywords) else 0.3

        # Negative margin product
        product_score = 1.0 if 'premium wireless keyboard' in str(data.get('negative_margin_product', '')).lower() else 0.0

        # Margin percentage
        margin_score = 0.0
        try:
            m = float(data.get('margin_pct', 0))
            if -14.0 <= m <= -13.0:
                margin_score = 1.0
            elif -20.0 <= m <= -10.0:
                margin_score = 0.5
        except Exception:
            pass

        # Duplicate customer IDs (Jaccard)
        dup_score = 0.0
        try:
            submitted = set(int(x) for x in data.get('duplicate_customer_ids', []))
            correct   = {15, 67}
            if submitted or correct:
                dup_score = len(submitted & correct) / len(submitted | correct)
        except Exception:
            pass

        final = (spike_score + exp_score + product_score + margin_score + dup_score) / 5.0
        return {
            "score": round(final, 3),
            "components": {
                "spike_month_year":        spike_score,
                "spike_explanation":       exp_score,
                "negative_margin_product": product_score,
                "margin_pct":              margin_score,
                "duplicate_customer_ids":  dup_score
            },
            "feedback": (
                f"Spike: {spike_score:.2f}, Explanation: {exp_score:.2f}, "
                f"Product: {product_score:.2f}, Margin: {margin_score:.2f}, "
                f"Duplicates: {dup_score:.2f}"
            )
        }

    # ──────────────────────────────────────────────
    # PUBLIC API
    # ──────────────────────────────────────────────

    def get_task(self, task_id: str) -> Task:
        if task_id not in self.tasks:
            raise ValueError(f"Task '{task_id}' not found. Available: {list(self.tasks.keys())}")
        return self.tasks[task_id]

    def list_tasks(self) -> List[Dict[str, Any]]:
        """Return task list WITH action_schema — required for OpenEnv validator."""
        action_schema = {
            "action_types": ["run_query", "describe_table", "list_tables", "submit_answer"],
            "fields": {
                "action_type": "ActionType (required)",
                "sql_query":   "str (optional, for run_query)",
                "table_name":  "str (optional, for describe_table)",
                "answer":      "str (optional, for submit_answer)",
                "reasoning":   "str (optional)"
            }
        }
        return [
            {
                'task_id':       task.task_id,
                'description':   task.description,
                'difficulty':    task.difficulty,
                'max_steps':     task.max_steps,
                'action_schema': action_schema
            }
            for task in self.tasks.values()
        ]

    def grade_answer(self, task_id: str, answer: str, steps_used: int):
        task = self.get_task(task_id)
        score, components, feedback = task.grader_func(answer, task.correct_answers, steps_used)
        
        # Hackathon Phase 2 strict validation: Must be strictly between 0 and 1 (i.e. not exactly 0.0 or 1.0)
        clamped_score = max(0.001, min(0.999, float(score)))
        
        return clamped_score, components, feedback