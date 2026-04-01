"""SCOUT AI Core Agent - Autonomous reasoning loop."""

import os
import json
import time
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Generator
from datetime import datetime
from openai import OpenAI

from .memory import AgentMemory
from .analyzer import InsightAnalyzer, BusinessInsight


@dataclass
class AgentStep:
    """A single step in the agent's reasoning process."""
    step_num: int
    step_type: str  # THINK, PLAN, QUERY, OBSERVE, DECIDE
    content: str
    data: Optional[Dict[str, Any]] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass 
class AgentResult:
    """Final result from agent investigation."""
    success: bool
    answer: str
    insights: List[Dict[str, Any]]
    recommendations: Dict[str, Any]
    steps: List[AgentStep]
    total_queries: int
    confidence: float
    execution_time: float


class ScoutAgent:
    """SCOUT - Autonomous Business Analyst Agent."""
    
    # Database schema for context - VERY EXPLICIT
    SCHEMA = """
DATABASE SCHEMA (USE ONLY THESE EXACT COLUMNS):

TABLE: customers
  - customer_id (INTEGER, PRIMARY KEY)
  - name (TEXT)
  - region (TEXT: North, South, East, West)
  - segment (TEXT: Enterprise, SMB, Consumer)
  - signup_date (DATE)
  - last_order_date (DATE)
  - total_spent (REAL)
  - order_count (INTEGER)

TABLE: products
  - product_id (INTEGER, PRIMARY KEY)
  - name (TEXT)
  - category (TEXT)
  - unit_price (REAL)
  - cost_price (REAL)
  - stock_quantity (INTEGER)

TABLE: orders
  - order_id (INTEGER, PRIMARY KEY)
  - customer_id (INTEGER, FK to customers)
  - order_date (DATE)
  - status (TEXT)
  - total_amount (REAL)
  - discount_pct (REAL)

TABLE: order_items
  - item_id (INTEGER, PRIMARY KEY)
  - order_id (INTEGER, FK to orders)
  - product_id (INTEGER, FK to products)
  - quantity (INTEGER)
  - unit_price (REAL)

TABLE: monthly_revenue (AGGREGATED DATA - USE THIS FOR REVENUE ANALYSIS)
  - id (INTEGER, PRIMARY KEY)
  - month (INTEGER: 1-12)
  - year (INTEGER: 2023, 2024)
  - revenue (REAL)
  - expenses (REAL)
  - profit (REAL)
  - region (TEXT)
  - category (TEXT)

CRITICAL RULES:
- monthly_revenue has year/month columns - USE IT for yearly comparisons
- orders/order_items do NOT have year column - use strftime('%Y', order_date)
- customers does NOT have year/category - don't use those columns
- For date math: CAST(julianday('2024-06-01') - julianday(date_col) AS INTEGER)
"""
    
    PLANNER_PROMPT = """You are SCOUT, an autonomous AI business analyst.

{schema}

TASK: {task}

PREVIOUS FINDINGS:
{memory_context}

Step {step_num} of {max_steps}. {force_answer}

RESPOND WITH ONLY JSON:
{{
    "thinking": "Brief reasoning (1-2 sentences)",
    "action": "query" or "answer",
    "sql": "SELECT ... (if action=query, use ONLY columns from schema above)",
    "purpose": "Why this query helps (if action=query)",
    "answer": "Complete answer with specific numbers and recommendations (if action=answer)",
    "confidence": 0.8
}}

RULES:
1. ONLY use columns that exist in the schema above
2. For revenue by year: SELECT year, SUM(revenue) FROM monthly_revenue GROUP BY year
3. After 3+ successful queries with data, you MUST provide an answer
4. Include specific numbers in your answer
5. End with actionable recommendations"""

    ANSWER_PROMPT = """Based on ALL the data collected, provide a comprehensive business answer.

TASK: {task}

DATA COLLECTED:
{all_data}

Provide a complete answer that:
1. Directly answers the question with specific numbers
2. Identifies the root cause or key finding
3. Provides 2-3 actionable recommendations

Format your answer as a clear business summary."""

    def __init__(self, api_key: str = None, model: str = "llama-3.1-8b-instant", base_url: str = None):
        """Initialize SCOUT agent."""
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        self.model = model
        self.base_url = base_url or "https://api.groq.com/openai/v1"
        
        if not self.api_key:
            raise ValueError("API key required. Set GROQ_API_KEY environment variable.")
        
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        self.memory = AgentMemory()
        self.analyzer = InsightAnalyzer()
        self.steps: List[AgentStep] = []
        self.max_steps = 10
        self.db_executor = None  # Set by run()
        self.successful_queries = 0  # Track successful queries
        
    def run(self, task: str, db_executor, max_steps: int = 10, stream: bool = False) -> AgentResult:
        """
        Run autonomous investigation on a task.
        """
        start_time = time.time()
        self.memory.clear()
        self.steps = []
        self.max_steps = max_steps
        self.db_executor = db_executor
        self.successful_queries = 0
        
        step_num = 0
        final_answer = None
        all_insights = []
        consecutive_errors = 0
        
        while step_num < max_steps:
            step_num += 1
            
            # Force answer after enough successful queries
            force_answer = ""
            if self.successful_queries >= 3:
                force_answer = "YOU HAVE ENOUGH DATA. You MUST provide an answer now with action='answer'."
            elif self.successful_queries >= 2 and step_num >= 5:
                force_answer = "You have collected data. Provide your answer now."
            
            # 1. THINK & PLAN
            self._log_step(step_num, "THINK", "Analyzing situation and planning next action...")
            
            try:
                action = self._get_next_action(task, step_num, force_answer)
            except Exception as e:
                self._log_step(step_num, "ERROR", f"Planning failed: {str(e)}")
                consecutive_errors += 1
                if consecutive_errors >= 3:
                    break
                continue
            
            if not action:
                consecutive_errors += 1
                if consecutive_errors >= 3:
                    break
                continue
            
            consecutive_errors = 0
            thinking = action.get('thinking', '')
            self._log_step(step_num, "THINK", thinking)
            
            action_type = action.get('action', 'query')
            
            # 2. EXECUTE ACTION
            if action_type == 'query':
                sql = action.get('sql', '')
                purpose = action.get('purpose', 'Investigating')
                
                if not sql:
                    continue
                
                self._log_step(step_num, "QUERY", f"{purpose}\n```sql\n{sql}\n```")
                
                # Execute query
                try:
                    result = self.db_executor(sql)
                    
                    if result.get('error'):
                        self._log_step(step_num, "ERROR", f"Query failed: {result['error']}")
                    else:
                        row_count = result.get('row_count', 0)
                        rows = result.get('rows', [])
                        
                        self._log_step(step_num, "RESULT", f"Returned {row_count} rows", 
                                      data={'rows': rows[:5], 'total': row_count})
                        
                        # Store in memory
                        self.memory.add_query(step_num, sql, purpose, result)
                        self.successful_queries += 1
                        
                        # Analyze results
                        if rows:
                            insights = self._analyze_results(task, purpose, rows)
                            all_insights.extend(insights)
                            
                            for insight in insights:
                                self._log_step(step_num, "INSIGHT", insight.finding)
                                self.memory.add_insight(
                                    insight.finding, 
                                    insight.evidence, 
                                    insight.confidence, 
                                    step_num
                                )
                                
                except Exception as e:
                    self._log_step(step_num, "ERROR", f"Execution failed: {str(e)}")
                    
            elif action_type == 'answer':
                final_answer = action.get('answer', '')
                
                if final_answer:
                    self._log_step(step_num, "ANSWER", final_answer)
                    break
            
            # Rate limit delay
            time.sleep(0.5)
        
        # If no answer yet, generate one from collected data
        if not final_answer and self.memory.queries:
            self._log_step(step_num + 1, "ANSWER", "Generating answer from collected data...")
            final_answer = self._generate_answer_from_data(task)
            self._log_step(step_num + 1, "ANSWER", final_answer)
        
        # Generate recommendations
        recommendations = self.analyzer.generate_recommendation(all_insights, task)
        
        execution_time = time.time() - start_time
        confidence = 0.85 if self.successful_queries >= 3 else 0.6 if self.successful_queries >= 2 else 0.4
        
        return AgentResult(
            success=final_answer is not None and len(final_answer) > 50,
            answer=final_answer or "Unable to gather sufficient data to answer the question.",
            insights=self.analyzer.format_for_display(all_insights),
            recommendations=recommendations,
            steps=self.steps,
            total_queries=self.successful_queries,
            confidence=confidence,
            execution_time=execution_time
        )
    
    def run_streaming(self, task: str, db_executor, max_steps: int = 10) -> Generator[AgentStep, None, AgentResult]:
        """Run investigation with streaming steps."""
        start_time = time.time()
        self.memory.clear()
        self.steps = []
        self.max_steps = max_steps
        self.db_executor = db_executor
        
        step_num = 0
        final_answer = None
        all_insights = []
        
        while step_num < max_steps:
            step_num += 1
            
            # THINK
            step = self._log_step(step_num, "THINK", "Planning next action...")
            yield step
            
            try:
                action = self._get_next_action(task, step_num)
            except Exception as e:
                step = self._log_step(step_num, "ERROR", str(e))
                yield step
                continue
            
            if not action:
                continue
            
            thinking = action.get('thinking', '')
            step = self._log_step(step_num, "THINK", thinking)
            yield step
            
            action_type = action.get('action', 'query')
            
            if action_type == 'query':
                sql = action.get('sql', '')
                purpose = action.get('purpose', '')
                
                step = self._log_step(step_num, "QUERY", f"{purpose}\n```sql\n{sql}\n```")
                yield step
                
                try:
                    result = self.db_executor(sql)
                    
                    if result.get('error'):
                        step = self._log_step(step_num, "ERROR", result['error'])
                        yield step
                    else:
                        row_count = result.get('row_count', 0)
                        rows = result.get('rows', [])
                        
                        step = self._log_step(step_num, "RESULT", f"{row_count} rows returned", 
                                             data={'rows': rows[:5], 'total': row_count})
                        yield step
                        
                        self.memory.add_query(step_num, sql, purpose, result)
                        
                        if rows:
                            insights = self._analyze_results(task, purpose, rows)
                            all_insights.extend(insights)
                            
                            for insight in insights:
                                step = self._log_step(step_num, "INSIGHT", insight.finding)
                                yield step
                                
                except Exception as e:
                    step = self._log_step(step_num, "ERROR", str(e))
                    yield step
                    
            elif action_type == 'answer':
                final_answer = action.get('answer', '')
                
                if final_answer and step_num >= 2:
                    step = self._log_step(step_num, "ANSWER", final_answer)
                    yield step
                    break
            
            time.sleep(0.5)
        
        recommendations = self.analyzer.generate_recommendation(all_insights, task)
        execution_time = time.time() - start_time
        
        return AgentResult(
            success=final_answer is not None,
            answer=final_answer or self._generate_fallback_answer(task),
            insights=self.analyzer.format_for_display(all_insights),
            recommendations=recommendations,
            steps=self.steps,
            total_queries=len(self.memory.queries),
            confidence=recommendations.get('confidence', 0.5),
            execution_time=execution_time
        )
    
    def _get_next_action(self, task: str, step_num: int, force_answer: str = "") -> Optional[Dict[str, Any]]:
        """Get next action from LLM."""
        prompt = self.PLANNER_PROMPT.format(
            schema=self.SCHEMA,
            task=task,
            memory_context=self.memory.get_context(),
            step_num=step_num,
            max_steps=self.max_steps,
            force_answer=force_answer
        )
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are SCOUT, an autonomous business analyst AI. Always respond with valid JSON only. No markdown, no explanation."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=1000
        )
        
        content = response.choices[0].message.content
        
        # Parse JSON from response
        try:
            # Find JSON in response
            start = content.find('{')
            end = content.rfind('}') + 1
            if start >= 0 and end > start:
                return json.loads(content[start:end])
        except json.JSONDecodeError:
            pass
        
        return None
    
    def _generate_answer_from_data(self, task: str) -> str:
        """Generate answer from all collected data using LLM."""
        # Format all collected data
        all_data_parts = []
        for q in self.memory.queries:
            all_data_parts.append(f"Query: {q.purpose}")
            all_data_parts.append(f"SQL: {q.sql}")
            all_data_parts.append(f"Results ({q.row_count} rows):")
            if q.rows:
                all_data_parts.append(json.dumps(q.rows[:10], indent=2, default=str))
            all_data_parts.append("")
        
        all_data = "\n".join(all_data_parts)
        
        prompt = self.ANSWER_PROMPT.format(task=task, all_data=all_data)
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a business analyst. Provide a clear, data-driven answer with specific numbers and actionable recommendations."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=800
            )
            return response.choices[0].message.content
        except Exception as e:
            return self._generate_fallback_answer(task)
    
    def _analyze_results(self, task: str, purpose: str, rows: List[Dict]) -> List[BusinessInsight]:
        """Analyze query results for insights."""
        insights = []
        
        # Use built-in analyzers based on data type
        if rows and len(rows) > 0:
            sample = rows[0]
            
            if 'revenue' in sample or 'profit' in sample or 'expenses' in sample:
                insights.extend(self.analyzer.analyze_revenue_data(rows, task))
            
            if 'customer_id' in sample or 'name' in sample:
                if 'days_since' in str(sample) or 'last_order' in str(sample):
                    insights.extend(self.analyzer.analyze_customer_data(rows, task))
            
            if 'unit_price' in sample and 'cost_price' in sample:
                insights.extend(self.analyzer.analyze_product_data(rows, task))
        
        return insights
    
    def _generate_fallback_answer(self, task: str) -> str:
        """Generate answer from accumulated insights when LLM doesn't provide one."""
        if not self.memory.insights:
            return "Unable to gather sufficient data to answer the question."
        
        parts = ["Based on my investigation:\n"]
        for insight in self.memory.insights:
            parts.append(f"• {insight.finding}")
        
        return '\n'.join(parts)
    
    def _log_step(self, step_num: int, step_type: str, content: str, 
                  data: Optional[Dict] = None) -> AgentStep:
        """Log a step in the investigation."""
        step = AgentStep(
            step_num=step_num,
            step_type=step_type,
            content=content,
            data=data
        )
        self.steps.append(step)
        self.memory.add_thought(step_type, content)
        return step
