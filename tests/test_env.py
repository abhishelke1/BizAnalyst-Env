"""Tests for the BizAnalystEnv environment."""

import pytest
from environment import BizAnalystEnv, Action, ActionType


class TestEnvironmentBasics:
    """Test basic environment operations."""
    
    def test_reset_initializes_environment(self):
        """Test that reset properly initializes the environment."""
        env = BizAnalystEnv()
        obs = env.reset("revenue_summary")
        
        assert obs.task_id == "revenue_summary"
        assert obs.step_number == 0
        assert obs.max_steps == 10
        assert len(obs.available_tables) > 0
        assert not obs.answer_submitted
        assert obs.queries_used == 0
    
    def test_reset_with_invalid_task_raises_error(self):
        """Test that reset with invalid task_id raises ValueError."""
        env = BizAnalystEnv()
        
        with pytest.raises(ValueError):
            env.reset("invalid_task")
    
    def test_step_without_reset_raises_error(self):
        """Test that calling step before reset raises RuntimeError."""
        env = BizAnalystEnv()
        action = Action(action_type=ActionType.LIST_TABLES)
        
        with pytest.raises(RuntimeError):
            env.step(action)
    
    def test_list_tables_action(self):
        """Test LIST_TABLES action returns available tables."""
        env = BizAnalystEnv()
        env.reset("revenue_summary")
        
        action = Action(action_type=ActionType.LIST_TABLES)
        obs, reward, done, info = env.step(action)
        
        assert not done
        assert "tables" in obs.message.lower()
        assert reward.value > 0
        assert info['step_count'] == 1
    
    def test_describe_table_action(self):
        """Test DESCRIBE_TABLE action returns schema information."""
        env = BizAnalystEnv()
        env.reset("revenue_summary")
        
        action = Action(action_type=ActionType.DESCRIBE_TABLE, table_name="customers")
        obs, reward, done, info = env.step(action)
        
        assert not done
        assert obs.schema_info is not None
        assert "customers" in obs.schema_info
        assert reward.value > 0
    
    def test_describe_table_without_name_returns_error(self):
        """Test DESCRIBE_TABLE without table_name returns error."""
        env = BizAnalystEnv()
        env.reset("revenue_summary")
        
        action = Action(action_type=ActionType.DESCRIBE_TABLE)
        obs, reward, done, info = env.step(action)
        
        assert not done
        assert "error" in obs.message.lower()
        assert reward.value < 0
    
    def test_run_query_action_success(self):
        """Test successful RUN_QUERY action."""
        env = BizAnalystEnv()
        env.reset("revenue_summary")
        
        action = Action(
            action_type=ActionType.RUN_QUERY,
            sql_query="SELECT * FROM customers LIMIT 5"
        )
        obs, reward, done, info = env.step(action)
        
        assert not done
        assert obs.query_result is not None
        assert obs.query_result.error is None
        assert obs.query_result.row_count == 5
        assert len(obs.query_result.columns) > 0
        assert reward.value > 0
    
    def test_run_query_blocks_dangerous_sql(self):
        """Test that dangerous SQL queries are blocked."""
        env = BizAnalystEnv()
        env.reset("revenue_summary")
        
        dangerous_queries = [
            "DROP TABLE customers",
            "DELETE FROM customers",
            "INSERT INTO customers VALUES (1, 'test')",
            "UPDATE customers SET name='test'",
            "CREATE TABLE test (id INT)"
        ]
        
        for query in dangerous_queries:
            action = Action(action_type=ActionType.RUN_QUERY, sql_query=query)
            obs, reward, done, info = env.step(action)
            
            assert obs.query_result.error is not None
            assert "not allowed" in obs.query_result.error.lower()
            assert reward.value < 0
    
    def test_run_query_with_sql_error(self):
        """Test RUN_QUERY with invalid SQL syntax."""
        env = BizAnalystEnv()
        env.reset("revenue_summary")
        
        action = Action(
            action_type=ActionType.RUN_QUERY,
            sql_query="SELECT * FROM nonexistent_table"
        )
        obs, reward, done, info = env.step(action)
        
        assert obs.query_result.error is not None
        assert reward.value < 0
    
    def test_submit_answer_ends_episode(self):
        """Test that SUBMIT_ANSWER ends the episode."""
        env = BizAnalystEnv()
        env.reset("revenue_summary")
        
        action = Action(
            action_type=ActionType.SUBMIT_ANSWER,
            answer="Total Revenue: $100000 | Total Expenses: $80000 | Net Profit: $20000 | Top Region: North"
        )
        obs, reward, done, info = env.step(action)
        
        assert done
        assert obs.answer_submitted
        assert reward.is_terminal
    
    def test_max_steps_terminates_episode(self):
        """Test that reaching max_steps terminates the episode."""
        env = BizAnalystEnv()
        env.reset("revenue_summary")
        
        # Execute steps until max_steps
        for i in range(10):
            action = Action(action_type=ActionType.LIST_TABLES)
            obs, reward, done, info = env.step(action)
            
            if i < 9:
                assert not done
            else:
                assert done
                assert reward.is_terminal
    
    def test_state_returns_complete_info(self):
        """Test that state() returns complete environment state."""
        env = BizAnalystEnv()
        env.reset("revenue_summary")
        
        # Execute a query
        action = Action(
            action_type=ActionType.RUN_QUERY,
            sql_query="SELECT * FROM customers LIMIT 1"
        )
        env.step(action)
        
        state = env.state()
        
        assert state['task_id'] == "revenue_summary"
        assert state['step_number'] == 1
        assert state['max_steps'] == 10
        assert state['queries_executed'] == 1
        assert not state['answer_submitted']
    
    def test_table_exploration_bonus(self):
        """Test that exploring new tables via DESCRIBE_TABLE gives bonus reward."""
        env = BizAnalystEnv()
        env.reset("revenue_summary")
        
        # First describe of a table (exploration bonus)
        action1 = Action(
            action_type=ActionType.DESCRIBE_TABLE,
            table_name="customers"
        )
        obs1, reward1, _, _ = env.step(action1)
        
        # Second describe of same table (no bonus)
        action2 = Action(
            action_type=ActionType.DESCRIBE_TABLE,
            table_name="customers"
        )
        obs2, reward2, _, _ = env.step(action2)
        
        # First describe should have exploration bonus
        assert reward1.value > reward2.value
    
    def test_intermediate_rewards_for_query(self):
        """Test intermediate rewards for successful queries."""
        env = BizAnalystEnv()
        env.reset("revenue_summary")
        
        # Query with results -> +0.02
        action = Action(
            action_type=ActionType.RUN_QUERY,
            sql_query="SELECT * FROM monthly_revenue WHERE year = 2023 LIMIT 1"
        )
        obs, reward, _, _ = env.step(action)
        
        assert reward.value == 0.02


class TestDeterministicSeeding:
    """Test that database seeding is deterministic."""
    
    def test_same_data_across_resets(self):
        """Test that resetting produces the same data."""
        env1 = BizAnalystEnv()
        obs1 = env1.reset("revenue_summary")
        
        query = "SELECT COUNT(*) as cnt FROM customers"
        action = Action(action_type=ActionType.RUN_QUERY, sql_query=query)
        result1, _, _, _ = env1.step(action)
        count1 = result1.query_result.rows[0]['cnt']
        
        env2 = BizAnalystEnv()
        obs2 = env2.reset("revenue_summary")
        result2, _, _, _ = env2.step(action)
        count2 = result2.query_result.rows[0]['cnt']
        
        assert count1 == count2
        assert count1 == 200  # Expected customer count


class TestAllTasks:
    """Test all three tasks can be initialized."""
    
    def test_revenue_summary_task(self):
        """Test revenue_summary task initialization."""
        env = BizAnalystEnv()
        obs = env.reset("revenue_summary")
        
        assert obs.task_id == "revenue_summary"
        assert obs.max_steps == 10
        assert "2023" in obs.task_description
    
    def test_customer_churn_risk_task(self):
        """Test customer_churn_risk task initialization."""
        env = BizAnalystEnv()
        obs = env.reset("customer_churn_risk")
        
        assert obs.task_id == "customer_churn_risk"
        assert obs.max_steps == 15
        assert "churn" in obs.task_description.lower()
    
    def test_anomaly_investigation_task(self):
        """Test anomaly_investigation task initialization."""
        env = BizAnalystEnv()
        obs = env.reset("anomaly_investigation")
        
        assert obs.task_id == "anomaly_investigation"
        assert obs.max_steps == 20
        assert "anomaly" in obs.task_description.lower() or "anomalies" in obs.task_description.lower()
