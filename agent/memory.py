"""Agent memory for tracking queries, results, and insights."""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
import json


@dataclass
class QueryRecord:
    """Record of a single query execution."""
    step: int
    sql: str
    purpose: str
    row_count: int
    columns: List[str]
    rows: List[Dict[str, Any]]
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class Insight:
    """A discovered insight from data analysis."""
    finding: str
    evidence: str
    confidence: float
    source_step: int


class AgentMemory:
    """Short-term memory for the agent's investigation."""
    
    def __init__(self):
        self.queries: List[QueryRecord] = []
        self.insights: List[Insight] = []
        self.thought_log: List[Dict[str, str]] = []
        self.tables_examined: set = set()
        
    def add_query(self, step: int, sql: str, purpose: str, result: Dict[str, Any]):
        """Store an executed query and its results."""
        record = QueryRecord(
            step=step,
            sql=sql,
            purpose=purpose,
            row_count=result.get('row_count', 0),
            columns=result.get('columns', []),
            rows=result.get('rows', [])[:20]  # Keep first 20 rows
        )
        self.queries.append(record)
        
        # Track tables from query
        sql_upper = sql.upper()
        for table in ['CUSTOMERS', 'PRODUCTS', 'ORDERS', 'ORDER_ITEMS', 'MONTHLY_REVENUE']:
            if table in sql_upper:
                self.tables_examined.add(table.lower())
    
    def add_insight(self, finding: str, evidence: str, confidence: float, source_step: int):
        """Store a discovered insight."""
        self.insights.append(Insight(
            finding=finding,
            evidence=evidence,
            confidence=confidence,
            source_step=source_step
        ))
    
    def add_thought(self, thought_type: str, content: str):
        """Log a thought for display."""
        self.thought_log.append({
            'type': thought_type,
            'content': content,
            'timestamp': datetime.now().isoformat()
        })
    
    def get_context(self, last_n: int = 5) -> str:
        """Get recent context for LLM prompt."""
        context_parts = []
        
        # Recent queries
        recent_queries = self.queries[-last_n:] if self.queries else []
        if recent_queries:
            context_parts.append("RECENT QUERIES:")
            for q in recent_queries:
                context_parts.append(f"  Step {q.step}: {q.purpose}")
                context_parts.append(f"    SQL: {q.sql[:100]}...")
                context_parts.append(f"    Returned: {q.row_count} rows")
                if q.rows and q.row_count <= 5:
                    context_parts.append(f"    Data: {json.dumps(q.rows[:3], default=str)}")
        
        # Current insights
        if self.insights:
            context_parts.append("\nCURRENT INSIGHTS:")
            for insight in self.insights:
                context_parts.append(f"  - {insight.finding} (confidence: {insight.confidence:.0%})")
        
        # Tables examined
        if self.tables_examined:
            context_parts.append(f"\nTABLES EXAMINED: {', '.join(self.tables_examined)}")
        
        return '\n'.join(context_parts)
    
    def get_all_results(self) -> List[Dict[str, Any]]:
        """Get all query results for analysis."""
        all_data = []
        for q in self.queries:
            all_data.extend(q.rows)
        return all_data
    
    def has_data_for(self, topic: str) -> bool:
        """Check if we have data related to a topic."""
        topic_lower = topic.lower()
        for q in self.queries:
            if topic_lower in q.purpose.lower() or topic_lower in q.sql.lower():
                return True
        return False
    
    def clear(self):
        """Clear all memory."""
        self.queries = []
        self.insights = []
        self.thought_log = []
        self.tables_examined = set()
    
    def get_step_log(self) -> List[Dict[str, Any]]:
        """Get full step log for frontend display."""
        steps = []
        for thought in self.thought_log:
            steps.append({
                'type': thought['type'],
                'content': thought['content'],
                'timestamp': thought['timestamp']
            })
        return steps
