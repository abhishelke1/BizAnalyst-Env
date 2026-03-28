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
        assert components['revenue'] == 1.0
        assert components['expenses'] == 1.0
        assert components['profit'] == 1.0
        assert components['region'] == 1.0
    
    def test_partial_credit_for_close_values(self):
        """Test partial credit for values within 10% tolerance but outside 2%."""
        env = BizAnalystEnv()
        env.reset("revenue_summary")
        
        task = env.task_manager.get_task("revenue_summary")
        correct = task.correct_answers
        
        # Answer with 3% error (within 10% but not 2%)
        answer = (
            f"Total Revenue: ${correct['total_revenue'] * 1.03:.2f} | "
            f"Total Expenses: ${correct['total_expenses'] * 1.03:.2f} | "
            f"Net Profit: ${correct['total_profit'] * 1.03:.2f} | "
            f"Top Region: {correct['top_region']}"
        )
        
        score, components, feedback = task.grader_func(answer, correct, 3)
        
        # Should get 0.5 for each value component (within 10% but not 2%)
        assert components['revenue'] == 0.5
        assert components['expenses'] == 0.5
        assert components['profit'] == 0.5
        assert components['region'] == 1.0
    
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
        
        assert components['region'] == 0.0
        assert score < 1.0
    
    def test_invalid_format_returns_zero(self):
        """Test that badly formatted answer returns zero."""
        env = BizAnalystEnv()
        env.reset("revenue_summary")
        
        task = env.task_manager.get_task("revenue_summary")
        correct = task.correct_answers
        
        answer = "This is not a valid answer format"
        score, components, feedback = task.grader_func(answer, correct, 3)
        
        assert score == 0.0


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
                "recommendation": "Send discount offer and follow-up email"
            })
        
        answer = json.dumps(answer_list)
        score, components, feedback = task.grader_func(answer, correct, 5)
        
        assert components['customer_ids'] == 1.0
        assert components['recommendation'] == 1.0
        assert score == 1.0  # 0.6*1.0 + 0.4*1.0
    
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
                "recommendation": "Contact customer"
            },
            {
                "customer_id": correct['churn_customer_ids'][1],
                "name": "Customer B",
                "days_since_last_order": 100,
                "recommendation": "Send offer"
            },
            {
                "customer_id": 999,  # Wrong customer
                "name": "Customer C",
                "days_since_last_order": 100,
                "recommendation": "Call"
            }
        ]
        
        answer = json.dumps(answer_list)
        score, components, feedback = task.grader_func(answer, correct, 5)
        
        # Should get 2/3 = 0.667 for customer IDs
        assert components['customer_ids'] == pytest.approx(0.667, abs=0.01)
    
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
                "recommendation": "Send promotional discount offer via email and follow-up call"
            })
        
        answer = json.dumps(answer_list)
        score, components, feedback = task.grader_func(answer, correct, 5)
        
        # Should get full recommendation score (keywords: discount, offer, email, follow)
        assert components['recommendation'] == 1.0
    
    def test_invalid_json_returns_zero(self):
        """Test that invalid JSON returns zero score."""
        env = BizAnalystEnv()
        env.reset("customer_churn_risk")
        
        task = env.task_manager.get_task("customer_churn_risk")
        correct = task.correct_answers
        
        answer = "This is not JSON"
        score, components, feedback = task.grader_func(answer, correct, 5)
        
        assert score == 0.0


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
        
        score, components, feedback = task.grader_func(
            json.dumps(answer), 
            correct, 
            5
        )
        
        assert components['spike_month'] == 1.0
        assert components['negative_margin_product'] == 1.0
        assert components['margin_pct'] >= 0.5
        assert components['duplicate_customer_ids'] == 1.0
        assert score >= 0.9
    
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
            json.dumps(answer), correct, 5
        )
        
        # Jaccard = intersection / union
        # If correct has [15, 67] and submitted has [15, 999]
        # intersection = 1, union = 3, score = 1/3 = 0.333
        assert 0.0 < components['duplicate_customer_ids'] < 1.0
    
    def test_margin_percentage_tolerance(self):
        """Test margin percentage scoring with different tolerances."""
        env = BizAnalystEnv()
        env.reset("anomaly_investigation")
        
        task = env.task_manager.get_task("anomaly_investigation")
        correct = task.correct_answers
        
        # Within [-14.0, -13.0] range -> full score
        answer1 = {
            "spike_month": correct['spike_month'],
            "spike_year": correct['spike_year'],
            "spike_explanation": "spike",
            "negative_margin_product": correct['negative_margin_product'],
            "margin_pct": -13.5,
            "duplicate_customer_ids": correct['duplicate_customer_ids']
        }
        
        score1, components1, _ = task.grader_func(json.dumps(answer1), correct, 5)
        assert components1['margin_pct'] == 1.0
        
        # Within [-20.0, -10.0] but outside [-14.0, -13.0] -> 0.5
        answer2 = {
            "spike_month": correct['spike_month'],
            "spike_year": correct['spike_year'],
            "spike_explanation": "spike",
            "negative_margin_product": correct['negative_margin_product'],
            "margin_pct": -15.0,
            "duplicate_customer_ids": correct['duplicate_customer_ids']
        }
        
        score2, components2, _ = task.grader_func(json.dumps(answer2), correct, 5)
        assert components2['margin_pct'] == 0.5
        
        # Beyond [-20.0, -10.0] -> 0.0
        answer3 = {
            "spike_month": correct['spike_month'],
            "spike_year": correct['spike_year'],
            "spike_explanation": "spike",
            "negative_margin_product": correct['negative_margin_product'],
            "margin_pct": -25.0,
            "duplicate_customer_ids": correct['duplicate_customer_ids']
        }
        
        score3, components3, _ = task.grader_func(json.dumps(answer3), correct, 5)
        assert components3['margin_pct'] == 0.0


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
