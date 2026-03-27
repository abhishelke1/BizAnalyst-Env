import time
from typing import Tuple, Dict, Any, List
from .models import Action, ActionType, Observation, QueryResult, Reward
from .database import DatabaseManager
from .tasks import TaskManager, Task
from .validators import validate_sql_query


class BizAnalystEnv:
    """Business Analyst environment for AI agents."""
    
    def __init__(self):
        """Initialize the environment."""
        self.db_manager = None
        self.task_manager = None
        self.current_task = None
        self.step_count = 0
        self.queries_executed = []
        self.query_history = []
        self.tables_explored = set()
        self.answer_submitted = False
        self.accumulated_reward = 0.0
        
    def reset(self, task_id: str) -> Observation:
        """Reset environment with a new task.
        
        Args:
            task_id: ID of the task to load
            
        Returns:
            Initial observation
        """
        # Initialize database
        if self.db_manager:
            self.db_manager.close()
        
        self.db_manager = DatabaseManager()
        self.db_manager.connect()
        self.db_manager.create_schema()
        self.db_manager.seed_data()
        
        # Initialize task manager
        self.task_manager = TaskManager(self.db_manager)
        
        # Load task
        self.current_task = self.task_manager.get_task(task_id)
        if not self.current_task:
            raise ValueError(f"Task '{task_id}' not found")
        
        # Reset state
        self.step_count = 0
        self.queries_executed = []
        self.query_history = []
        self.tables_explored = set()
        self.answer_submitted = False
        self.accumulated_reward = 0.0
        
        # Return initial observation
        return Observation(
            task_id=self.current_task.task_id,
            task_description=self.current_task.description,
            step_number=0,
            max_steps=self.current_task.max_steps,
            query_result=None,
            available_tables=self.db_manager.get_table_names(),
            schema_info=None,
            message="Environment initialized. Use LIST_TABLES or DESCRIBE_TABLE to explore the database, or RUN_QUERY to execute SQL queries.",
            queries_used=0,
            answer_submitted=False
        )
    
    def step(self, action: Action) -> Tuple[Observation, Reward, bool, Dict[str, Any]]:
        """Execute an action and return the result.
        
        Args:
            action: Action to execute
            
        Returns:
            Tuple of (observation, reward, done, info)
        """
        if not self.current_task:
            raise RuntimeError("Environment not initialized. Call reset() first.")
        
        self.step_count += 1
        done = False
        info = {}
        
        # Handle different action types
        if action.action_type == ActionType.LIST_TABLES:
            observation, reward = self._handle_list_tables(action)
            
        elif action.action_type == ActionType.DESCRIBE_TABLE:
            observation, reward = self._handle_describe_table(action)
            
        elif action.action_type == ActionType.RUN_QUERY:
            observation, reward = self._handle_run_query(action)
            
        elif action.action_type == ActionType.SUBMIT_ANSWER:
            observation, reward, done = self._handle_submit_answer(action)
            
        else:
            observation = self._create_observation(
                message=f"Unknown action type: {action.action_type}",
                query_result=None
            )
            reward = Reward(
                value=0.0,
                components={'error': -0.01},
                feedback="Invalid action type",
                is_terminal=False
            )
        
        # Check if max steps reached
        if self.step_count >= self.current_task.max_steps and not done:
            done = True
            # Partial credit for progress
            final_score = min(1.0, self.accumulated_reward * 0.1)
            observation.message = f"Max steps reached. Episode terminated. Partial score: {final_score:.2f}"
            reward = Reward(
                value=final_score,
                components={'partial_progress': final_score},
                feedback="Max steps reached without submitting answer",
                is_terminal=True
            )
        
        info['step_count'] = self.step_count
        info['queries_executed'] = len(self.queries_executed)
        
        return observation, reward, done, info
    
    def _handle_list_tables(self, action: Action) -> Tuple[Observation, Reward]:
        """Handle LIST_TABLES action."""
        tables = self.db_manager.get_table_names()
        
        observation = self._create_observation(
            message=f"Available tables: {', '.join(tables)}",
            query_result=None
        )
        
        reward = Reward(
            value=0.01,
            components={'list_tables': 0.01},
            feedback="Listed available tables",
            is_terminal=False
        )
        
        return observation, reward
    
    def _handle_describe_table(self, action: Action) -> Tuple[Observation, Reward]:
        """Handle DESCRIBE_TABLE action."""
        if not action.table_name:
            observation = self._create_observation(
                message="Error: table_name is required for DESCRIBE_TABLE action",
                query_result=None
            )
            reward = Reward(
                value=-0.01,
                components={'error': -0.01},
                feedback="Missing table_name",
                is_terminal=False
            )
            return observation, reward
        
        try:
            schema = self.db_manager.get_table_schema(action.table_name)
            schema_dict = {col[0]: col[1] for col in schema}
            
            # Track table exploration
            if action.table_name not in self.tables_explored:
                self.tables_explored.add(action.table_name)
                exploration_bonus = 0.02
            else:
                exploration_bonus = 0.0
            
            observation = self._create_observation(
                message=f"Schema for table '{action.table_name}': {len(schema)} columns",
                query_result=None,
                schema_info={action.table_name: schema_dict}
            )
            
            reward_value = 0.01 + exploration_bonus
            reward = Reward(
                value=reward_value,
                components={
                    'describe_table': 0.01,
                    'exploration_bonus': exploration_bonus
                },
                feedback=f"Retrieved schema for {action.table_name}",
                is_terminal=False
            )
            
            self.accumulated_reward += exploration_bonus
            
        except Exception as e:
            observation = self._create_observation(
                message=f"Error describing table: {str(e)}",
                query_result=None
            )
            reward = Reward(
                value=-0.01,
                components={'error': -0.01},
                feedback=f"Failed to describe table: {str(e)}",
                is_terminal=False
            )
        
        return observation, reward
    
    def _handle_run_query(self, action: Action) -> Tuple[Observation, Reward]:
        """Handle RUN_QUERY action."""
        if not action.sql_query:
            observation = self._create_observation(
                message="Error: sql_query is required for RUN_QUERY action",
                query_result=None
            )
            reward = Reward(
                value=-0.01,
                components={'error': -0.01},
                feedback="Missing sql_query",
                is_terminal=False
            )
            return observation, reward
        
        # Validate query
        is_valid, error_message = validate_sql_query(action.sql_query)
        if not is_valid:
            observation = self._create_observation(
                message=f"Query validation failed: {error_message}",
                query_result=QueryResult(
                    columns=[],
                    rows=[],
                    row_count=0,
                    execution_time_ms=0.0,
                    error=error_message
                )
            )
            reward = Reward(
                value=-0.02,
                components={'failed_query': -0.02},
                feedback="Query validation failed",
                is_terminal=False
            )
            return observation, reward
        
        # Execute query
        try:
            start_time = time.time()
            results = self.db_manager.execute_query(action.sql_query)
            execution_time = (time.time() - start_time) * 1000  # Convert to ms
            
            # Convert results to list format
            if results:
                columns = list(results[0].keys())
                rows = [list(row) for row in results]
            else:
                columns = []
                rows = []
            
            query_result = QueryResult(
                columns=columns,
                rows=rows,
                row_count=len(rows),
                execution_time_ms=round(execution_time, 2),
                error=None
            )
            
            # Track query
            self.queries_executed.append(action.sql_query)
            self.query_history.append(action.sql_query)
            
            # Compute reward
            reward_components = {'successful_query': 0.01}
            reward_value = 0.01
            
            if len(rows) > 0:
                reward_components['query_with_results'] = 0.01
                reward_value += 0.01
            
            # Check for new table exploration
            query_upper = action.sql_query.upper()
            for table in self.db_manager.get_table_names():
                if table.upper() in query_upper and table not in self.tables_explored:
                    self.tables_explored.add(table)
                    reward_components['new_table_explored'] = 0.02
                    reward_value += 0.02
                    self.accumulated_reward += 0.02
                    break
            
            # Task-specific intermediate rewards
            reward_value += self._compute_task_specific_reward(action.sql_query, query_result, reward_components)
            
            observation = self._create_observation(
                message=f"Query executed successfully. Returned {len(rows)} row(s).",
                query_result=query_result
            )
            
            reward = Reward(
                value=reward_value,
                components=reward_components,
                feedback=f"Query successful, {len(rows)} rows returned",
                is_terminal=False
            )
            
        except Exception as e:
            query_result = QueryResult(
                columns=[],
                rows=[],
                row_count=0,
                execution_time_ms=0.0,
                error=str(e)
            )
            
            observation = self._create_observation(
                message=f"Query execution failed: {str(e)}",
                query_result=query_result
            )
            
            reward = Reward(
                value=-0.02,
                components={'failed_query': -0.02},
                feedback=f"Query failed: {str(e)}",
                is_terminal=False
            )
        
        return observation, reward
    
    def _handle_submit_answer(self, action: Action) -> Tuple[Observation, Reward, bool]:
        """Handle SUBMIT_ANSWER action."""
        if not action.answer:
            observation = self._create_observation(
                message="Error: answer is required for SUBMIT_ANSWER action",
                query_result=None
            )
            reward = Reward(
                value=0.0,
                components={'error': -0.01},
                feedback="Missing answer",
                is_terminal=False
            )
            return observation, reward, False
        
        self.answer_submitted = True
        
        # Grade the answer
        if self.current_task.task_id == 'anomaly_investigation':
            # Pass query history for window function bonus
            score, components, feedback = self.current_task.grader_func(
                action.answer,
                self.current_task.correct_answers,
                self.step_count,
                self.query_history
            )
        elif self.current_task.task_id == 'revenue_summary':
            # Pass steps for efficiency penalty
            score, components, feedback = self.current_task.grader_func(
                action.answer,
                self.current_task.correct_answers,
                self.step_count
            )
        else:
            score, components, feedback = self.current_task.grader_func(
                action.answer,
                self.current_task.correct_answers,
                self.step_count
            )
        
        observation = self._create_observation(
            message=f"Answer submitted. Final score: {score:.2f}. {feedback}",
            query_result=None
        )
        observation.answer_submitted = True
        
        reward = Reward(
            value=score,
            components=components,
            feedback=feedback,
            is_terminal=True
        )
        
        return observation, reward, True
    
    def _compute_task_specific_reward(self, query: str, result: QueryResult, components: Dict[str, float]) -> float:
        """Compute task-specific intermediate rewards.
        
        Args:
            query: SQL query executed
            result: Query result
            components: Dictionary to add reward components to
            
        Returns:
            Additional reward value
        """
        additional_reward = 0.0
        query_upper = query.upper()
        
        if self.current_task.task_id == 'revenue_summary':
            # Reward for querying monthly_revenue table
            if 'MONTHLY_REVENUE' in query_upper and 'monthly_revenue' not in [q.upper() for q in self.queries_executed[:-1]]:
                components['first_revenue_query'] = 0.1
                additional_reward += 0.1
                self.accumulated_reward += 0.1
            
            # Reward for filtering by year 2023
            if '2023' in query and result.row_count > 0:
                components['year_filter'] = 0.05
                additional_reward += 0.05
                self.accumulated_reward += 0.05
        
        return additional_reward
    
    def _create_observation(self, message: str, query_result: QueryResult = None, schema_info: Dict[str, Any] = None) -> Observation:
        """Create an observation object.
        
        Args:
            message: Message to include in observation
            query_result: Optional query result
            schema_info: Optional schema information
            
        Returns:
            Observation object
        """
        return Observation(
            task_id=self.current_task.task_id,
            task_description=self.current_task.description,
            step_number=self.step_count,
            max_steps=self.current_task.max_steps,
            query_result=query_result,
            available_tables=self.db_manager.get_table_names(),
            schema_info=schema_info,
            message=message,
            queries_used=len(self.queries_executed),
            answer_submitted=self.answer_submitted
        )
    
    def state(self) -> Dict[str, Any]:
        """Get current environment state.
        
        Returns:
            Dictionary with complete state information
        """
        return {
            'task_id': self.current_task.task_id if self.current_task else None,
            'step': self.step_count,
            'max_steps': self.current_task.max_steps if self.current_task else 0,
            'queries_run': len(self.queries_executed),
            'query_history': self.queries_executed.copy(),
            'tables_explored': list(self.tables_explored),
            'answer_submitted': self.answer_submitted,
            'accumulated_reward': self.accumulated_reward
        }
