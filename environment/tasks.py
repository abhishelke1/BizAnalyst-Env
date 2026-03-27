from dataclasses import dataclass
from typing import Dict, Callable, Any, List
import json
import re
from datetime import datetime, timedelta


@dataclass
class Task:
    """Task definition with metadata and grading logic."""
    task_id: str
    description: str
    difficulty: str
    max_steps: int
    grader_func: Callable[[str, Any], tuple[float, Dict[str, float], str]]
    correct_answers: Dict[str, Any] = None


class TaskManager:
    """Manages all tasks and grading logic."""
    
    def __init__(self, db_manager):
        """Initialize task manager with database connection.
        
        Args:
            db_manager: DatabaseManager instance for pre-computing answers
        """
        self.db_manager = db_manager
        self.tasks = self._initialize_tasks()
        
    def _initialize_tasks(self) -> Dict[str, Task]:
        """Initialize all task definitions and pre-compute correct answers."""
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
                "A customer is at churn risk if their days_since_last_order > 90 AND "
                "their order_count has declined. For each at-risk customer, provide: "
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
                "(1) The month/year with an unusual revenue spike (>30%% above the 6-month rolling average), explain likely cause, "
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
    
    def _precompute_revenue_summary(self) -> Dict[str, Any]:
        """Pre-compute correct answers for revenue summary task."""
        query = """
            SELECT 
                SUM(revenue) as total_revenue,
                SUM(expenses) as total_expenses,
                SUM(profit) as total_profit
            FROM monthly_revenue
            WHERE year = 2023
        """
        result = self.db_manager.execute_query(query)
        row = result[0]
        
        # Get top region
        query_region = """
            SELECT region, SUM(revenue) as total
            FROM monthly_revenue
            WHERE year = 2023
            GROUP BY region
            ORDER BY total DESC
            LIMIT 1
        """
        region_result = self.db_manager.execute_query(query_region)
        top_region = region_result[0][0] if region_result else "Unknown"
        
        return {
            'total_revenue': float(row[0]) if row[0] else 0.0,
            'total_expenses': float(row[1]) if row[1] else 0.0,
            'total_profit': float(row[2]) if row[2] else 0.0,
            'top_region': top_region
        }
    
    def _precompute_churn_risk(self) -> Dict[str, Any]:
        """Pre-compute correct answers for churn risk task."""
        today = datetime.now()
        
        query = """
            SELECT customer_id, name, last_order_date, order_count
            FROM customers
            WHERE last_order_date IS NOT NULL
            ORDER BY customer_id
        """
        results = self.db_manager.execute_query(query)
        
        churn_customers = []
        for row in results:
            customer_id = row[0]
            name = row[1]
            last_order_date_str = row[2]
            order_count = row[3]
            
            if last_order_date_str:
                last_order_date = datetime.strptime(last_order_date_str, '%Y-%m-%d')
                days_since = (today - last_order_date).days
                
                if days_since > 90:
                    churn_customers.append({
                        'customer_id': customer_id,
                        'name': name,
                        'days_since_last_order': days_since
                    })
        
        # Sort by days_since and take top 3
        churn_customers.sort(key=lambda x: x['days_since_last_order'], reverse=True)
        top_3 = churn_customers[:3]
        
        return {
            'churn_customer_ids': [c['customer_id'] for c in top_3],
            'churn_customers': top_3
        }
    
    def _precompute_anomaly_investigation(self) -> Dict[str, Any]:
        """Pre-compute correct answers for anomaly investigation task."""
        # 1. Find revenue spike
        spike_month = 3
        spike_year = 2024
        
        # 2. Find negative margin product
        query_margin = """
            SELECT name, unit_price, cost_price,
                   ((unit_price - cost_price) / unit_price * 100) as margin_pct
            FROM products
            WHERE cost_price > unit_price
            ORDER BY margin_pct ASC
            LIMIT 1
        """
        margin_result = self.db_manager.execute_query(query_margin)
        if margin_result:
            negative_product = margin_result[0][0]
            margin_pct = float(margin_result[0][3])
        else:
            negative_product = "Premium Wireless Keyboard"
            margin_pct = -15.56  # (45-52)/45 * 100
        
        # 3. Find duplicate orders
        query_duplicates = """
            SELECT customer_id, order_date, total_amount, COUNT(*) as cnt
            FROM orders
            GROUP BY customer_id, order_date, total_amount
            HAVING cnt > 1
        """
        dup_result = self.db_manager.execute_query(query_duplicates)
        duplicate_customer_ids = sorted(list(set([row[0] for row in dup_result])))
        
        return {
            'spike_month': spike_month,
            'spike_year': spike_year,
            'negative_margin_product': negative_product,
            'margin_pct': margin_pct,
            'duplicate_customer_ids': duplicate_customer_ids
        }
    
    def _grade_revenue_summary(self, answer: str, correct: Dict[str, Any], steps_used: int) -> tuple[float, Dict[str, float], str]:
        """Grade the revenue summary task.
        
        Args:
            answer: Submitted answer string
            correct: Pre-computed correct answers
            steps_used: Number of steps used
            
        Returns:
            Tuple of (total_score, component_scores, feedback)
        """
        components = {}
        
        # Parse answer using regex
        revenue_match = re.search(r'Total Revenue:\s*\$?([\d,]+\.?\d*)', answer, re.IGNORECASE)
        expenses_match = re.search(r'Total Expenses:\s*\$?([\d,]+\.?\d*)', answer, re.IGNORECASE)
        profit_match = re.search(r'Net Profit:\s*\$?([\d,]+\.?\d*)', answer, re.IGNORECASE)
        region_match = re.search(r'Top Region:\s*(\w+)', answer, re.IGNORECASE)
        
        # Score revenue
        if revenue_match:
            submitted_revenue = float(revenue_match.group(1).replace(',', ''))
            correct_revenue = correct['total_revenue']
            error_pct = abs(submitted_revenue - correct_revenue) / correct_revenue * 100 if correct_revenue != 0 else 100
            
            if error_pct <= 1:
                components['revenue_score'] = 1.0
            elif error_pct <= 5:
                components['revenue_score'] = 0.5
            else:
                components['revenue_score'] = 0.0
        else:
            components['revenue_score'] = 0.0
        
        # Score expenses
        if expenses_match:
            submitted_expenses = float(expenses_match.group(1).replace(',', ''))
            correct_expenses = correct['total_expenses']
            error_pct = abs(submitted_expenses - correct_expenses) / correct_expenses * 100 if correct_expenses != 0 else 100
            
            if error_pct <= 1:
                components['expenses_score'] = 1.0
            elif error_pct <= 5:
                components['expenses_score'] = 0.5
            else:
                components['expenses_score'] = 0.0
        else:
            components['expenses_score'] = 0.0
        
        # Score profit
        if profit_match:
            submitted_profit = float(profit_match.group(1).replace(',', ''))
            correct_profit = correct['total_profit']
            error_pct = abs(submitted_profit - correct_profit) / correct_profit * 100 if correct_profit != 0 else 100
            
            if error_pct <= 1:
                components['profit_score'] = 1.0
            elif error_pct <= 5:
                components['profit_score'] = 0.5
            else:
                components['profit_score'] = 0.0
        else:
            components['profit_score'] = 0.0
        
        # Score region
        if region_match:
            submitted_region = region_match.group(1).strip()
            correct_region = correct['top_region']
            components['region_score'] = 1.0 if submitted_region.lower() == correct_region.lower() else 0.0
        else:
            components['region_score'] = 0.0
        
        # Calculate base score
        base_score = sum(components.values()) / len(components)
        
        # Apply efficiency penalty
        if steps_used > 3:
            penalty = (steps_used - 3) * 0.05
            efficiency_penalty = min(penalty, base_score)
            components['efficiency_penalty'] = -efficiency_penalty
            final_score = max(0.0, base_score - efficiency_penalty)
        else:
            components['efficiency_penalty'] = 0.0
            final_score = base_score
        
        feedback = f"Revenue: {components['revenue_score']:.2f}, Expenses: {components['expenses_score']:.2f}, Profit: {components['profit_score']:.2f}, Region: {components['region_score']:.2f}"
        
        return final_score, components, feedback
    
    def _grade_churn_risk(self, answer: str, correct: Dict[str, Any], steps_used: int) -> tuple[float, Dict[str, float], str]:
        """Grade the churn risk task.
        
        Args:
            answer: Submitted answer (JSON string)
            correct: Pre-computed correct answers
            steps_used: Number of steps used
            
        Returns:
            Tuple of (total_score, component_scores, feedback)
        """
        components = {}
        
        try:
            # Parse JSON answer
            submitted = json.loads(answer)
            if not isinstance(submitted, list):
                return 0.0, {'error': 1.0}, "Answer must be a JSON array"
            
            # Extract submitted customer IDs
            submitted_ids = set()
            total_days_error = 0
            days_count = 0
            
            for item in submitted:
                if isinstance(item, dict) and 'customer_id' in item:
                    submitted_ids.add(item['customer_id'])
                    
                    # Check days accuracy
                    if 'days_since_last_order' in item:
                        submitted_days = item['days_since_last_order']
                        # Find correct days for this customer
                        for correct_cust in correct['churn_customers']:
                            if correct_cust['customer_id'] == item['customer_id']:
                                correct_days = correct_cust['days_since_last_order']
                                error = abs(submitted_days - correct_days)
                                total_days_error += error
                                days_count += 1
                                break
            
            # Customer ID score (proportion correct)
            correct_ids = set(correct['churn_customer_ids'])
            intersection = submitted_ids & correct_ids
            components['customer_id_score'] = len(intersection) / len(correct_ids) if correct_ids else 0.0
            
            # Days accuracy score
            if days_count > 0:
                avg_error = total_days_error / days_count
                # Score based on error (lower is better)
                if avg_error <= 5:
                    components['days_accuracy_score'] = 1.0
                elif avg_error <= 15:
                    components['days_accuracy_score'] = 0.5
                else:
                    components['days_accuracy_score'] = 0.0
            else:
                components['days_accuracy_score'] = 0.0
            
            # Recommendation score (keyword matching)
            recommendation_keywords = ['discount', 'email', 'offer', 'follow-up', 'contact', 'call', 'promotion', 'incentive']
            answer_lower = answer.lower()
            keyword_count = sum(1 for keyword in recommendation_keywords if keyword in answer_lower)
            
            if keyword_count == 0:
                components['recommendation_score'] = 0.0
            elif keyword_count == 1:
                components['recommendation_score'] = 0.3
            else:
                components['recommendation_score'] = 1.0
            
            # Final weighted score
            final_score = (
                0.5 * components['customer_id_score'] +
                0.3 * components['days_accuracy_score'] +
                0.2 * components['recommendation_score']
            )
            
            feedback = f"Customer IDs: {components['customer_id_score']:.2f}, Days Accuracy: {components['days_accuracy_score']:.2f}, Recommendations: {components['recommendation_score']:.2f}"
            
        except json.JSONDecodeError:
            return 0.0, {'parse_error': 1.0}, "Failed to parse JSON answer"
        except Exception as e:
            return 0.0, {'error': 1.0}, f"Error grading answer: {str(e)}"
        
        return final_score, components, feedback
    
    def _grade_anomaly_investigation(self, answer: str, correct: Dict[str, Any], steps_used: int, query_history: List[str]) -> tuple[float, Dict[str, float], str]:
        """Grade the anomaly investigation task.
        
        Args:
            answer: Submitted answer (JSON string)
            correct: Pre-computed correct answers
            steps_used: Number of steps used
            query_history: List of queries executed
            
        Returns:
            Tuple of (total_score, component_scores, feedback)
        """
        components = {}
        
        try:
            # Parse JSON answer
            submitted = json.loads(answer)
            if not isinstance(submitted, dict):
                return 0.0, {'error': 1.0}, "Answer must be a JSON object"
            
            # 1. Spike month/year
            spike_month_correct = submitted.get('spike_month') == correct['spike_month']
            spike_year_correct = submitted.get('spike_year') == correct['spike_year']
            components['spike_month_year_score'] = 1.0 if (spike_month_correct and spike_year_correct) else 0.0
            
            # 2. Spike explanation (keyword matching)
            explanation = str(submitted.get('spike_explanation', '')).lower()
            explanation_keywords = ['spike', 'increase', 'growth', 'surge', 'high', 'unusual', 'anomaly']
            explanation_score = sum(1 for keyword in explanation_keywords if keyword in explanation)
            components['spike_explanation_score'] = min(1.0, explanation_score / 3)
            
            # 3. Negative margin product
            submitted_product = str(submitted.get('negative_margin_product', '')).strip()
            correct_product = correct['negative_margin_product']
            components['negative_margin_product_score'] = 1.0 if submitted_product.lower() == correct_product.lower() else 0.0
            
            # 4. Margin percentage
            if 'margin_pct' in submitted:
                submitted_margin = float(submitted['margin_pct'])
                correct_margin = correct['margin_pct']
                margin_error = abs(submitted_margin - correct_margin)
                
                if margin_error <= 0.5:
                    components['margin_pct_score'] = 1.0
                elif margin_error <= 2.0:
                    components['margin_pct_score'] = 0.5
                else:
                    components['margin_pct_score'] = 0.0
            else:
                components['margin_pct_score'] = 0.0
            
            # 5. Duplicate customer IDs (Jaccard similarity)
            submitted_dups = set(submitted.get('duplicate_customer_ids', []))
            correct_dups = set(correct['duplicate_customer_ids'])
            
            if len(submitted_dups) == 0 and len(correct_dups) == 0:
                components['duplicate_ids_score'] = 1.0
            elif len(submitted_dups) == 0 or len(correct_dups) == 0:
                components['duplicate_ids_score'] = 0.0
            else:
                intersection = len(submitted_dups & correct_dups)
                union = len(submitted_dups | correct_dups)
                components['duplicate_ids_score'] = intersection / union if union > 0 else 0.0
            
            # 6. Bonus for using window functions
            window_function_used = any(
                'over' in query.lower() or 'window' in query.lower() 
                for query in query_history
            )
            components['window_function_bonus'] = 0.1 if window_function_used else 0.0
            
            # Calculate weighted average
            base_score = (
                0.2 * components['spike_month_year_score'] +
                0.1 * components['spike_explanation_score'] +
                0.2 * components['negative_margin_product_score'] +
                0.2 * components['margin_pct_score'] +
                0.3 * components['duplicate_ids_score']
            )
            
            final_score = min(1.0, base_score + components['window_function_bonus'])
            
            feedback = f"Spike: {components['spike_month_year_score']:.2f}, Product: {components['negative_margin_product_score']:.2f}, Margin: {components['margin_pct_score']:.2f}, Duplicates: {components['duplicate_ids_score']:.2f}"
            
        except json.JSONDecodeError:
            return 0.0, {'parse_error': 1.0}, "Failed to parse JSON answer"
        except Exception as e:
            return 0.0, {'error': 1.0}, f"Error grading answer: {str(e)}"
        
        return final_score, components, feedback
    
    def get_task(self, task_id: str) -> Task:
        """Get task by ID.
        
        Args:
            task_id: Task identifier
            
        Returns:
            Task instance
        """
        return self.tasks.get(task_id)
    
    def get_all_tasks(self) -> List[Task]:
        """Get all tasks.
        
        Returns:
            List of all tasks
        """
        return list(self.tasks.values())
