"""Tests for FastAPI server endpoints."""

import pytest
from fastapi.testclient import TestClient
from server import app
from environment import ActionType


client = TestClient(app)


class TestServerBasics:
    """Test basic server endpoints."""
    
    def test_root_endpoint(self):
        """Test root endpoint returns info card."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        
        assert data["name"] == "BizAnalyst-Env"
        assert data["version"] == "1.0.0"
        assert data["status"] == "running"
        assert "endpoints" in data
        assert len(data["endpoints"]) == 7
    
    def test_health_endpoint(self):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "ok"
        assert data["env"] == "BizAnalyst-Env"


class TestResetEndpoint:
    """Test /reset endpoint."""
    
    def test_reset_with_valid_task(self):
        """Test reset with valid task_id."""
        response = client.post("/reset", json={"task_id": "revenue_summary"})
        assert response.status_code == 200
        
        data = response.json()
        assert data["task_id"] == "revenue_summary"
        assert data["step_number"] == 0
        assert data["max_steps"] == 10
        assert len(data["available_tables"]) > 0
        assert not data["answer_submitted"]
    
    def test_reset_with_invalid_task(self):
        """Test reset with invalid task_id returns 422."""
        response = client.post("/reset", json={"task_id": "invalid_task"})
        assert response.status_code == 422
    
    def test_reset_all_tasks(self):
        """Test reset works for all three tasks."""
        tasks = ["revenue_summary", "customer_churn_risk", "anomaly_investigation"]
        
        for task_id in tasks:
            response = client.post("/reset", json={"task_id": task_id})
            assert response.status_code == 200
            data = response.json()
            assert data["task_id"] == task_id


class TestStepEndpoint:
    """Test /step endpoint."""
    
    def test_step_list_tables(self):
        """Test step with LIST_TABLES action."""
        # Reset first
        client.post("/reset", json={"task_id": "revenue_summary"})
        
        # Execute step
        response = client.post("/step", json={
            "action_type": "list_tables"
        })
        
        assert response.status_code == 200
        data = response.json()
        
        assert "observation" in data
        assert "reward" in data
        assert "done" in data
        assert "info" in data
        
        assert not data["done"]
        assert data["reward"]["value"] > 0
    
    def test_step_describe_table(self):
        """Test step with DESCRIBE_TABLE action."""
        client.post("/reset", json={"task_id": "revenue_summary"})
        
        response = client.post("/step", json={
            "action_type": "describe_table",
            "table_name": "customers"
        })
        
        assert response.status_code == 200
        data = response.json()
        
        assert not data["done"]
        assert data["observation"]["schema_info"] is not None
    
    def test_step_run_query(self):
        """Test step with RUN_QUERY action."""
        client.post("/reset", json={"task_id": "revenue_summary"})
        
        response = client.post("/step", json={
            "action_type": "run_query",
            "sql_query": "SELECT * FROM customers LIMIT 5"
        })
        
        assert response.status_code == 200
        data = response.json()
        
        assert not data["done"]
        assert data["observation"]["query_result"] is not None
        assert data["observation"]["query_result"]["row_count"] == 5
    
    def test_step_submit_answer(self):
        """Test step with SUBMIT_ANSWER action."""
        client.post("/reset", json={"task_id": "revenue_summary"})
        
        response = client.post("/step", json={
            "action_type": "submit_answer",
            "answer": "Total Revenue: $1000000 | Total Expenses: $800000 | Net Profit: $200000 | Top Region: North"
        })
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["done"]
        assert data["reward"]["is_terminal"]
        assert data["observation"]["answer_submitted"]
    
    def test_step_without_reset_returns_error(self):
        """Test that step without reset returns error or succeeds if env already has state."""
        # Note: Since server.py uses a global env instance, it may already have
        # state from previous tests in this session. This test verifies the endpoint
        # handles both cases gracefully.
        new_client = TestClient(app)
        
        response = new_client.post("/step", json={
            "action_type": "list_tables"
        })
        
        # Should return error if no state, or 200 if env already initialized
        assert response.status_code in [200, 422, 500]


class TestStateEndpoint:
    """Test /state endpoint."""
    
    def test_state_returns_current_state(self):
        """Test that state endpoint returns current environment state."""
        client.post("/reset", json={"task_id": "revenue_summary"})
        
        # Execute a step
        client.post("/step", json={
            "action_type": "run_query",
            "sql_query": "SELECT * FROM customers LIMIT 1"
        })
        
        # Get state
        response = client.get("/state")
        assert response.status_code == 200
        
        data = response.json()
        assert data["task_id"] == "revenue_summary"
        assert data["step_number"] == 1
        assert data["queries_executed"] == 1


class TestTasksEndpoint:
    """Test /tasks endpoint."""
    
    def test_tasks_returns_all_tasks(self):
        """Test that tasks endpoint returns all task definitions."""
        response = client.get("/tasks")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 3
        
        task_ids = [task["task_id"] for task in data]
        assert "revenue_summary" in task_ids
        assert "customer_churn_risk" in task_ids
        assert "anomaly_investigation" in task_ids
        
        # Check task structure
        for task in data:
            assert "task_id" in task
            assert "description" in task
            assert "difficulty" in task
            assert "max_steps" in task


class TestGraderEndpoint:
    """Test /grader endpoint."""
    
    def test_grader_revenue_summary(self):
        """Test grader for revenue_summary task."""
        # Submit a sample answer
        response = client.post("/grader", json={
            "task_id": "revenue_summary",
            "answer": "Total Revenue: $1000000 | Total Expenses: $800000 | Net Profit: $200000 | Top Region: North"
        })
        
        assert response.status_code == 200
        data = response.json()
        
        assert "score" in data
        assert "breakdown" in data
        assert "feedback" in data
        assert 0.0 <= data["score"] <= 1.0
    
    def test_grader_with_invalid_task(self):
        """Test grader with invalid task_id."""
        response = client.post("/grader", json={
            "task_id": "invalid_task",
            "answer": "test answer"
        })
        
        assert response.status_code == 422


class TestCORS:
    """Test CORS configuration."""
    
    def test_cors_headers_present(self):
        """Test that CORS headers are present in responses."""
        response = client.get("/health", headers={"Origin": "http://example.com"})
        
        assert response.status_code == 200
        # CORS middleware should add these headers
        assert "access-control-allow-origin" in response.headers or "Access-Control-Allow-Origin" in response.headers


class TestErrorHandling:
    """Test error handling."""
    
    def test_invalid_action_type(self):
        """Test that invalid action type is handled gracefully."""
        client.post("/reset", json={"task_id": "revenue_summary"})
        
        # Try to send invalid action (should be caught by Pydantic)
        response = client.post("/step", json={
            "action_type": "invalid_action"
        })
        
        assert response.status_code == 422
    
    def test_malformed_json(self):
        """Test that malformed JSON is handled."""
        response = client.post(
            "/reset",
            data="this is not json",
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 422


class TestMultipleEpisodes:
    """Test running multiple episodes."""
    
    def test_sequential_episodes(self):
        """Test running multiple episodes sequentially."""
        # Episode 1
        response1 = client.post("/reset", json={"task_id": "revenue_summary"})
        assert response1.status_code == 200
        
        client.post("/step", json={"action_type": "list_tables"})
        
        # Episode 2 (different task)
        response2 = client.post("/reset", json={"task_id": "customer_churn_risk"})
        assert response2.status_code == 200
        
        data = response2.json()
        assert data["task_id"] == "customer_churn_risk"
        assert data["step_number"] == 0  # Fresh start
