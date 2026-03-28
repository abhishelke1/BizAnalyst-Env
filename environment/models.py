from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum


class ActionType(str, Enum):
    """Types of actions the agent can take in the environment."""
    RUN_QUERY = "run_query"
    DESCRIBE_TABLE = "describe_table"
    LIST_TABLES = "list_tables"
    SUBMIT_ANSWER = "submit_answer"


class Action(BaseModel):
    """Action taken by the agent."""
    action_type: ActionType
    sql_query: Optional[str] = None
    table_name: Optional[str] = None
    answer: Optional[str] = None
    reasoning: Optional[str] = None


class QueryResult(BaseModel):
    """Result from executing a SQL query."""
    success: bool
    columns: List[str]
    rows: List[Dict[str, Any]]
    row_count: int
    execution_time_ms: float = 0.0
    error: Optional[str] = None


class Observation(BaseModel):
    """Observation returned after each step."""
    task_id: str
    task_description: str
    step_number: int
    max_steps: int
    query_result: Optional[QueryResult] = None
    available_tables: List[str]
    schema_info: Optional[Dict[str, Any]] = None
    message: str
    queries_used: int
    answer_submitted: bool


class Reward(BaseModel):
    """Reward signal with breakdown and feedback."""
    value: float = Field(ge=-1.0, le=1.0)
    components: Dict[str, float]
    feedback: str
    is_terminal: bool
