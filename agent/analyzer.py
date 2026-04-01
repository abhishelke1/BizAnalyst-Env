"""Insight analyzer - converts SQL results into business insights and recommendations."""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import statistics


@dataclass
class BusinessInsight:
    """A business insight with actionable recommendation."""
    finding: str
    evidence: str
    impact: str  # "High", "Medium", "Low"
    recommendation: str
    confidence: float
    chart_type: Optional[str] = None  # "bar", "line", "pie"
    chart_data: Optional[Dict] = None


@dataclass
class Anomaly:
    """Detected anomaly in the data."""
    anomaly_type: str  # "spike", "drop", "outlier", "missing"
    description: str
    value: Any
    expected: Any
    severity: str  # "critical", "warning", "info"


class InsightAnalyzer:
    """Analyzes query results and generates business insights."""
    
    def __init__(self):
        self.insights: List[BusinessInsight] = []
        self.anomalies: List[Anomaly] = []
    
    def analyze_revenue_data(self, rows: List[Dict], context: str = "") -> List[BusinessInsight]:
        """Analyze revenue data and generate insights."""
        insights = []
        
        if not rows:
            return insights
        
        # Check for revenue by region
        if 'region' in rows[0]:
            regions = {}
            for row in rows:
                region = row.get('region', 'Unknown')
                revenue = float(row.get('revenue', 0) or row.get('total', 0) or 0)
                regions[region] = regions.get(region, 0) + revenue
            
            if regions:
                top_region = max(regions, key=regions.get)
                total = sum(regions.values())
                top_pct = (regions[top_region] / total * 100) if total > 0 else 0
                
                insights.append(BusinessInsight(
                    finding=f"{top_region} leads with {top_pct:.1f}% of total revenue",
                    evidence=f"Total: ${total:,.2f}, {top_region}: ${regions[top_region]:,.2f}",
                    impact="High" if top_pct > 40 else "Medium",
                    recommendation=f"Focus expansion efforts on {top_region} market",
                    confidence=0.95,
                    chart_type="pie",
                    chart_data={"labels": list(regions.keys()), "values": list(regions.values())}
                ))
        
        # Check for trends over time
        if 'month' in rows[0] or 'year' in rows[0]:
            monthly_data = {}
            for row in rows:
                key = f"{row.get('year', '')}-{row.get('month', ''):02d}" if 'month' in row else str(row.get('year', ''))
                monthly_data[key] = float(row.get('revenue', 0) or row.get('total', 0) or 0)
            
            if len(monthly_data) >= 3:
                values = list(monthly_data.values())
                avg = statistics.mean(values)
                
                # Find spikes
                for period, value in monthly_data.items():
                    if value > avg * 1.3:  # 30% above average
                        insights.append(BusinessInsight(
                            finding=f"Revenue spike detected in {period}",
                            evidence=f"${value:,.2f} vs average ${avg:,.2f} (+{((value/avg)-1)*100:.1f}%)",
                            impact="High",
                            recommendation="Investigate what drove this increase and replicate",
                            confidence=0.9,
                            chart_type="line",
                            chart_data={"labels": list(monthly_data.keys()), "values": values}
                        ))
                    elif value < avg * 0.7:  # 30% below average
                        insights.append(BusinessInsight(
                            finding=f"Revenue drop detected in {period}",
                            evidence=f"${value:,.2f} vs average ${avg:,.2f} ({((value/avg)-1)*100:.1f}%)",
                            impact="Critical",
                            recommendation="Urgent: Investigate root cause of revenue decline",
                            confidence=0.9
                        ))
        
        return insights
    
    def analyze_customer_data(self, rows: List[Dict], context: str = "") -> List[BusinessInsight]:
        """Analyze customer data for churn and engagement insights."""
        insights = []
        
        if not rows:
            return insights
        
        # Churn risk analysis
        churn_risk = [r for r in rows if r.get('days_since_last_order', 0) > 90]
        if churn_risk:
            high_value_churning = [c for c in churn_risk if float(c.get('total_spent', 0)) > 1000]
            
            insights.append(BusinessInsight(
                finding=f"{len(churn_risk)} customers at churn risk (>90 days inactive)",
                evidence=f"Including {len(high_value_churning)} high-value customers",
                impact="Critical" if high_value_churning else "High",
                recommendation="Launch re-engagement campaign with personalized offers",
                confidence=0.85
            ))
        
        # Segment analysis
        if 'segment' in rows[0]:
            segments = {}
            for row in rows:
                seg = row.get('segment', 'Unknown')
                segments[seg] = segments.get(seg, 0) + 1
            
            if segments:
                insights.append(BusinessInsight(
                    finding=f"Customer distribution across segments",
                    evidence=str(segments),
                    impact="Medium",
                    recommendation="Tailor marketing strategies per segment",
                    confidence=0.95,
                    chart_type="pie",
                    chart_data={"labels": list(segments.keys()), "values": list(segments.values())}
                ))
        
        return insights
    
    def analyze_product_data(self, rows: List[Dict], context: str = "") -> List[BusinessInsight]:
        """Analyze product data for margin and performance insights."""
        insights = []
        
        if not rows:
            return insights
        
        # Negative margin products
        negative_margin = []
        for row in rows:
            unit_price = float(row.get('unit_price', 0))
            cost_price = float(row.get('cost_price', 0))
            if cost_price > 0:
                margin = ((unit_price - cost_price) / cost_price) * 100
                if margin < 0:
                    negative_margin.append({
                        'name': row.get('name', 'Unknown'),
                        'margin': margin
                    })
        
        if negative_margin:
            worst = min(negative_margin, key=lambda x: x['margin'])
            insights.append(BusinessInsight(
                finding=f"Product with negative margin: {worst['name']}",
                evidence=f"Margin: {worst['margin']:.2f}% (selling below cost)",
                impact="Critical",
                recommendation=f"Immediately review pricing for {worst['name']} - either increase price or discontinue",
                confidence=0.99
            ))
        
        return insights
    
    def detect_anomalies(self, rows: List[Dict], value_column: str) -> List[Anomaly]:
        """Detect statistical anomalies in data."""
        anomalies = []
        
        if not rows or len(rows) < 3:
            return anomalies
        
        try:
            values = [float(r.get(value_column, 0)) for r in rows]
            avg = statistics.mean(values)
            stdev = statistics.stdev(values) if len(values) > 1 else 0
            
            for i, row in enumerate(rows):
                val = float(row.get(value_column, 0))
                if stdev > 0 and abs(val - avg) > 2 * stdev:
                    anomalies.append(Anomaly(
                        anomaly_type="outlier",
                        description=f"Value {val} is {abs(val-avg)/stdev:.1f} standard deviations from mean",
                        value=val,
                        expected=avg,
                        severity="warning" if abs(val - avg) < 3 * stdev else "critical"
                    ))
        except (ValueError, TypeError):
            pass
        
        return anomalies
    
    def generate_recommendation(self, insights: List[BusinessInsight], task_context: str) -> Dict[str, Any]:
        """Generate final recommendation based on all insights."""
        if not insights:
            return {
                "summary": "Insufficient data to generate recommendations",
                "actions": [],
                "confidence": 0.0
            }
        
        # Sort by impact
        impact_order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
        sorted_insights = sorted(insights, key=lambda x: impact_order.get(x.impact, 4))
        
        actions = []
        for insight in sorted_insights[:3]:  # Top 3 actions
            actions.append({
                "action": insight.recommendation,
                "priority": insight.impact,
                "reason": insight.finding
            })
        
        return {
            "summary": sorted_insights[0].finding if sorted_insights else "No insights",
            "root_cause": sorted_insights[0].evidence if sorted_insights else "Unknown",
            "actions": actions,
            "confidence": max(i.confidence for i in insights) if insights else 0.0,
            "projected_impact": self._estimate_impact(sorted_insights)
        }
    
    def _estimate_impact(self, insights: List[BusinessInsight]) -> str:
        """Estimate projected impact of recommendations."""
        critical_count = sum(1 for i in insights if i.impact == "Critical")
        if critical_count > 0:
            return f"Addressing {critical_count} critical issue(s) could recover significant revenue"
        return "Implementing recommendations expected to improve performance"
    
    def format_for_display(self, insights: List[BusinessInsight]) -> List[Dict[str, Any]]:
        """Format insights for frontend display."""
        return [
            {
                "finding": i.finding,
                "evidence": i.evidence,
                "impact": i.impact,
                "recommendation": i.recommendation,
                "confidence": f"{i.confidence:.0%}",
                "chart": {"type": i.chart_type, "data": i.chart_data} if i.chart_type else None
            }
            for i in insights
        ]
