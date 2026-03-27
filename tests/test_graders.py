"""Tests for task graders."""

import pytest
import json
from environment import BizAnalystEnv


class TestRevenueGrader:
    """Test revenue_summary task grader."""
    
    def test_perfect_answer(self):
        """Test grading a perfect answer."""
        env = BizAnalystEnv()
        env.reset("revenue_summary")
        
        task = env.task_manager.get_task("revenue_summary")
        correct = task.correct_answers
        
        # Construct perfect answer
        answer = (
            f"Total Revenue: ${correct['total_revenue']:.2f} | "
            f"Total Expenses: ${correct['total_expenses']:.2f} | "
            f"Net Profit: ${correct['total_profit']:.2f} | "
            f"Top Region: {correct['top_region']}"
        )
        
        score, components, feedback = task.grader_func(answer, correct, 3)
        
        assert score == 1.0
        assert components['revenue_score'] == 1.0
        assert components['expenses_score'] == 1.0
        assert components['profit_score'] == 1.0
        assert components['region_score'] == 1.0
        assert components['efficiency_penalty'] == 0.0
    
    def test_answer_with_efficiency_penalty(self):
        """Test that using more than 3 steps incurs penalty."""
        env = BizAnalystEnv()
        env.reset("revenue_summary")
        
        task = env.task_manager.get_task("revenue_summary")
        correct = task.correct_answers
        
        answer = (
            f"Total Revenue: ${correct['total_revenue']:.2f} | "
            f"Total Expenses: ${correct['total_expenses']:.2f} | "
            f"Net Profit: ${correct['total_profit']:.2f} | "
            f"Top Region: {correct['top_region']}"
        )
        
        # Use 5 steps (2 extra)
        score, components, feedback = task.grader_func(answer, correct, 5)
        
        assert score < 1.0
        assert components['efficiency_penalty'] < 0.0
        assert abs(components['efficiency_penalty']) == pytest.approx(0.1, abs=0.01)  # 2 * 0.05
    
    def test_partial_credit_for_close_values(self):
        """Test partial credit for values within 5% tolerance."""
        env = BizAnalystEnv()
        env.reset("revenue_summary")
        
        task = env.task_manager.get_task("revenue_summary")
        correct = task.correct_answers
        
        # Answer with 3% error
        answer = (
            f"Total Revenue: ${correct['total_revenue'] * 1.03:.2f} | "
            f"Total Expenses: ${correct['total_expenses'] * 1.03:.2f} | "
            f"Net Profit: ${correct['total_profit'] * 1.03:.2f} | "
            f"Top Region: {correct['top_region']}"
        )
        
        score, components, feedback = task.grader_func(answer, correct, 3)
        
        # Should get 0.5 for each value component (within 5% but not 1%)
        assert components['revenue_score'] == 0.5
        assert components['expenses_score'] == 0.5
        assert components['profit_score'] == 0.5
        assert components['region_score'] == 1.0
    
    def test_wrong_region(self):
        """Test that wrong region gets zero score."""
        env = BizAnalystEnv()
        env.reset("revenue_summary")
        
        task = env.task_manager.get_task("revenue_summary")
        correct = task.correct_answers
        
        wrong_region = "WrongRegion"
        answer = (
            f"Total Revenue: ${correct['total_revenue']:.2f} | "
            f"Total Expenses: ${correct['total_expenses']:.2f} | "
            f"Net Profit: ${correct['total_profit']:.2f} | "
            f"Top Region: {wrong_region}"
        )
        
        score, components, feedback = task.grader_func(answer, correct, 3)
        
        assert components['region_score'] == 0.0
        assert score < 1.0


class TestChurnRiskGrader:
    """Test customer_churn_risk task grader."""
    
    def test_perfect_answer(self):
        """Test grading a perfect answer with all correct customers."""
        env = BizAnalystEnv()
        env.reset("customer_churn_risk")
        
        task = env.task_manager.get_task("customer_churn_risk")
        correct = task.correct_answers
        
        # Construct perfect answer
        answer_list = []
        for cust in correct['churn_customers'][:3]:
            answer_list.append({
                "customer_id": cust['customer_id'],
                "name": cust['name'],
                "days_since_last_order": cust['days_since_last_order'],
                "recommended_action": "Send discount offer and follow-up email"
            })
        
        answer = json.dumps(answer_list)
        score, components, feedback = task.grader_func(answer, correct, 5)
        
        assert components['customer_id_score'] == 1.0
        assert components['days_accuracy_score'] >= 0.5
        assert components['recommendation_score'] >= 0.3
        assert score > 0.8
    
    def test_partial_customer_ids(self):
        """Test partial credit for identifying some correct customers."""
        env = BizAnalystEnv()
        env.reset("customer_churn_risk")
        
        task = env.task_manager.get_task("customer_churn_risk")
        correct = task.correct_answers
        
        # Only include 2 out of 3 correct customers, plus 1 wrong
        answer_list = [
            {
                "customer_id": correct['churn_customer_ids'][0],
                "name": "Customer A",
                "days_since_last_order": 100,
                "recommended_action": "Contact customer"
            },
            {
                "customer_id": correct['churn_customer_ids'][1],
                "name": "Customer B",
                "days_since_last_order": 100,
                "recommended_action": "Send offer"
            },
            {
                "customer_id": 999,  # Wrong customer
                "name": "Customer C",
                "days_since_last_order": 100,
                "recommended_action": "Call"
            }
        ]
        
        answer = json.dumps(answer_list)
        score, components, feedback = task.grader_func(answer, correct, 5)
        
        # Should get 2/3 = 0.667 for customer IDs
        assert components['customer_id_score'] == pytest.approx(0.667, abs=0.01)
    
    def test_recommendation_keyword_scoring(self):
        """Test that recommendations with keywords score higher."""
        env = BizAnalystEnv()
        env.reset("customer_churn_risk")
        
        task = env.task_manager.get_task("customer_churn_risk")
        correct = task.correct_answers
        
        # Answer with multiple recommendation keywords
        answer_list = []
        for cust in correct['churn_customers'][:3]:
            answer_list.append({
                "customer_id": cust['customer_id'],
                "name": cust['name'],
                "days_since_last_order": cust['days_since_last_order'],
                "recommended_action": "Send promotional discount offer via email and follow-up call"
            })
        
        answer = json.dumps(answer_list)
        score, components, feedback = task.grader_func(answer, correct, 5)
        
        # Should get full recommendation score (keywords: discount, offer, email, call, follow-up)
        assert components['recommendation_score'] == 1.0
    
    def test_invalid_json_returns_zero(self):
        """Test that invalid JSON returns zero score."""
        env = BizAnalystEnv()
        env.reset("customer_churn_risk")
        
        task = env.task_manager.get_task("customer_churn_risk")
        correct = task.correct_answers
        
        answer = "This is not JSON"
        score, components, feedback = task.grader_func(answer, correct, 5)
        
        assert score == 0.0
        assert 'parse_error' in components or 'error' in components


class TestAnomalyInvestigationGrader:
    """Test anomaly_investigation task grader."""
    
    def test_perfect_answer(self):
        """Test grading a perfect answer."""
        env = BizAnalystEnv()
        env.reset("anomaly_investigation")
        
        task = env.task_manager.get_task("anomaly_investigation")
        correct = task.correct_answers
        
        answer = {
            "spike_month": correct['spike_month'],
            "spike_year": correct['spike_year'],
            "spike_explanation": "Revenue spike increase detected in the data showing unusual growth",
            "negative_margin_product": correct['negative_margin_product'],
            "margin_pct": correct['margin_pct'],
            "duplicate_customer_ids": correct['duplicate_customer_ids']
        }
        
        # With window function query
        query_history = ["SELECT *, AVG(revenue) OVER (ORDER BY month) FROM monthly_revenue"]
        
        score, components, feedback = task.grader_func(
            json.dumps(answer), 
            correct, 
            5,
            query_history
        )
        
        assert components['spike_month_year_score'] == 1.0
        assert components['negative_margin_product_score'] == 1.0
        assert components['margin_pct_score'] >= 0.5
        assert components['duplicate_ids_score'] == 1.0
        assert components['window_function_bonus'] == 0.1
        assert score >= 0.9
    
    def test_window_function_bonus(self):
        """Test that using window functions gives bonus."""
        env = BizAnalystEnv()
        env.reset("anomaly_investigation")
        
        task = env.task_manager.get_task("anomaly_investigation")
        correct = task.correct_answers
        
        answer = {
            "spike_month": correct['spike_month'],
            "spike_year": correct['spike_year'],
            "spike_explanation": "spike",
            "negative_margin_product": correct['negative_margin_product'],
            "margin_pct": correct['margin_pct'],
            "duplicate_customer_ids": correct['duplicate_customer_ids']
        }
        
        # Without window function
        query_history1 = ["SELECT * FROM monthly_revenue"]
        score1, components1, _ = task.grader_func(
            json.dumps(answer), correct, 5, query_history1
        )
        
        # With window function
        query_history2 = ["SELECT *, ROW_NUMBER() OVER (PARTITION BY region ORDER BY revenue DESC) FROM monthly_revenue"]
        score2, components2, _ = task.grader_func(
            json.dumps(answer), correct, 5, query_history2
        )
        
        assert components1['window_function_bonus'] == 0.0
        assert components2['window_function_bonus'] == 0.1
        assert score2 > score1
    
    def test_duplicate_customer_jaccard_similarity(self):
        """Test Jaccard similarity for duplicate customer IDs."""
        env = BizAnalystEnv()
        env.reset("anomaly_investigation")
        
        task = env.task_manager.get_task("anomaly_investigation")
        correct = task.correct_answers
        
        # Partial overlap
        submitted_dups = [correct['duplicate_customer_ids'][0], 999]
        
        answer = {
            "spike_month": correct['spike_month'],
            "spike_year": correct['spike_year'],
            "spike_explanation": "spike",
            "negative_margin_product": correct['negative_margin_product'],
            "margin_pct": correct['margin_pct'],
            "duplicate_customer_ids": submitted_dups
        }
        
        score, components, feedback = task.grader_func(
            json.dumps(answer), correct, 5, []
        )
        
        # Jaccard = intersection / union
        # If correct has [15, 67] and submitted has [15, 999]
        # intersection = 1, union = 3, score = 1/3 = 0.333
        assert 0.0 < components['duplicate_ids_score'] < 1.0
    
    def test_margin_percentage_tolerance(self):
        """Test margin percentage scoring with different tolerances."""
        env = BizAnalystEnv()
        env.reset("anomaly_investigation")
        
        task = env.task_manager.get_task("anomaly_investigation")
        correct = task.correct_answers
        
        # Within 0.5%
        answer1 = {
            "spike_month": correct['spike_month'],
            "spike_year": correct['spike_year'],
            "spike_explanation": "spike",
            "negative_margin_product": correct['negative_margin_product'],
            "margin_pct": correct['margin_pct'] + 0.3,
            "duplicate_customer_ids": correct['duplicate_customer_ids']
        }
        
        score1, components1, _ = task.grader_func(json.dumps(answer1), correct, 5, [])
        assert components1['margin_pct_score'] == 1.0
        
        # Within 2%
        answer2 = {
            "spike_month": correct['spike_month'],
            "spike_year": correct['spike_year'],
            "spike_explanation": "spike",
            "negative_margin_product": correct['negative_margin_product'],
            "margin_pct": correct['margin_pct'] + 1.5,
            "duplicate_customer_ids": correct['duplicate_customer_ids']
        }
        
        score2, components2, _ = task.grader_func(json.dumps(answer2), correct, 5, [])
        assert components2['margin_pct_score'] == 0.5
        
        # Beyond 2%
        answer3 = {
            "spike_month": correct['spike_month'],
            "spike_year": correct['spike_year'],
            "spike_explanation": "spike",
            "negative_margin_product": correct['negative_margin_product'],
            "margin_pct": correct['margin_pct'] + 3.0,
            "duplicate_customer_ids": correct['duplicate_customer_ids']
        }
        
        score3, components3, _ = task.grader_func(json.dumps(answer3), correct, 5, [])
        assert components3['margin_pct_score'] == 0.0


class TestGraderDeterminism:
    """Test that graders are deterministic."""
    
    def test_same_answer_same_score(self):
        """Test that grading the same answer twice gives the same score."""
        env = BizAnalystEnv()
        env.reset("revenue_summary")
        
        task = env.task_manager.get_task("revenue_summary")
        correct = task.correct_answers
        
        answer = (
            f"Total Revenue: ${correct['total_revenue']:.2f} | "
            f"Total Expenses: ${correct['total_expenses']:.2f} | "
            f"Net Profit: ${correct['total_profit']:.2f} | "
            f"Top Region: {correct['top_region']}"
        )
        
        score1, components1, feedback1 = task.grader_func(answer, correct, 3)
        score2, components2, feedback2 = task.grader_func(answer, correct, 3)
        
        assert score1 == score2
        assert components1 == components2
