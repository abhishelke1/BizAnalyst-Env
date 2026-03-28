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
        # Re-initialize database fresh every reset
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
        
        # Check if max steps reached without answer
        if self.step_count >= self.current_task.max_steps and not done:
            done = True
            observation.message = f"Max steps reached. Episode terminated."
            reward = Reward(
                value=0.05,
                components={'timeout': 0.05},
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
            
            # Track table exploration - bonus for first time
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
                feedback=str(e),
                is_terminal=False
            )
        
        return observation, reward
    
    def _handle_run_query(self, action: Action) -> Tuple[Observation, Reward]:
        """Handle RUN_QUERY action."""
        if not action.sql_query:
            observation = self._create_observation(
                message="Error: sql_query is required for RUN_QUERY action",
                query_result=QueryResult(
                    success=False,
                    rows=[],
                    columns=[],
                    row_count=0,
                    error="Missing sql_query parameter"
                )
            )
            reward = Reward(
                value=-0.01,
                components={'error': -0.01},
                feedback="Missing sql_query",
                is_terminal=False
            )
            return observation, reward
        
        # Block dangerous SQL keywords
        dangerous_keywords = ['DROP', 'DELETE', 'INSERT', 'UPDATE', 'CREATE', 'ALTER', 'EXEC', 'ATTACH', 'DETACH']
        query_upper = action.sql_query.upper()
        
        for keyword in dangerous_keywords:
            if keyword in query_upper:
                observation = self._create_observation(
                    message=f"Error: SQL keyword '{keyword}' is not allowed",
                    query_result=QueryResult(
                        success=False,
                        rows=[],
                        columns=[],
                        row_count=0,
                        error=f"SQL keyword '{keyword}' is not allowed for security reasons. Only SELECT queries are permitted."
                    )
                )
                reward = Reward(
                    value=-0.01,
                    components={'security_error': -0.01},
                    feedback=f"Blocked dangerous SQL keyword: {keyword}",
                    is_terminal=False
                )
                return observation, reward
        
        # Execute query
        try:
            results = self.db_manager.execute_query(action.sql_query)
            
            # Convert results to list of dicts
            rows = []
            columns = []
            if results:
                columns = list(results[0].keys())
                rows = [dict(row) for row in results]
            
            query_result = QueryResult(
                success=True,
                rows=rows,
                columns=columns,
                row_count=len(rows),
                error=None
            )
            
            self.queries_executed.append(action.sql_query)
            self.query_history.append({
                'step': self.step_count,
                'query': action.sql_query,
                'row_count': len(rows)
            })
            
            # Intermediate reward
            reward_value = self._compute_intermediate_reward(query_result, action.sql_query)
            
            observation = self._create_observation(
                message=f"Query executed successfully. Returned {len(rows)} rows.",
                query_result=query_result
            )
            
            reward = Reward(
                value=reward_value,
                components={'successful_query': reward_value},
                feedback=f"Query returned {len(rows)} rows",
                is_terminal=False
            )
            
        except Exception as e:
            query_result = QueryResult(
                success=False,
                rows=[],
                columns=[],
                row_count=0,
                error=str(e)
            )
            
            observation = self._create_observation(
                message=f"Query execution failed: {str(e)}",
                query_result=query_result
            )
            
            reward = Reward(
                value=-0.01,
                components={'failed_query': -0.01},
                feedback=f"SQL error: {str(e)}",
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
                value=-0.01,
                components={'error': -0.01},
                feedback="Missing answer",
                is_terminal=False
            )
            return observation, reward, False
        
        # Grade the answer
        score, component_scores, feedback = self.task_manager.grade_answer(
            self.current_task.task_id,
            action.answer,
            self.step_count
        )
        
        self.answer_submitted = True
        
        observation = self._create_observation(
            message=f"Answer submitted. Final score: {score:.2f}",
            query_result=None
        )
        observation.answer_submitted = True
        
        reward = Reward(
            value=score,
            components=component_scores,
            feedback=feedback,
            is_terminal=True
        )
        
        return observation, reward, True  # done=True
    
    def _compute_intermediate_reward(self, query_result: QueryResult, query: str) -> float:
        """Compute intermediate reward for query execution.
        
        Args:
            query_result: Result of the query
            query: SQL query string
            
        Returns:
            Intermediate reward value
        """
        if query_result.success:
            if query_result.row_count > 0:
                return 0.02  # Successful query with results
            else:
                return 0.01  # Successful query, empty results
        else:
            return -0.01  # Failed query
    
    def _create_observation(
        self,
        message: str,
        query_result: QueryResult = None,
        schema_info: Dict[str, Dict[str, str]] = None
    ) -> Observation:
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
            Dictionary containing current state
        """
        return {
            'task_id': self.current_task.task_id if self.current_task else None,
            'step_number': self.step_count,
            'max_steps': self.current_task.max_steps if self.current_task else 0,
            'queries_executed': len(self.queries_executed),
            'tables_explored': list(self.tables_explored),
            'answer_submitted': self.answer_submitted,
            'accumulated_reward': self.accumulated_reward
        }
