"""SCOUT Auto-Scanner - Autonomous database anomaly detection."""

from typing import Dict, Any, List
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Alert:
    """A discovered business issue."""
    id: str
    severity: str  # critical, warning, info
    category: str  # revenue, churn, margin, data_quality
    title: str
    description: str
    metric: str
    impact: str  # dollar amount or percentage
    recommendation: str
    data: Dict[str, Any]


class AutoScanner:
    """Automatically scans database for business anomalies."""
    
    def __init__(self, db_executor):
        self.db = db_executor
        
    def scan_all(self) -> Dict[str, Any]:
        """Run all scans and return findings."""
        alerts = []
        
        # 1. Revenue anomaly scan
        alerts.extend(self._scan_revenue_anomalies())
        
        # 2. Churn risk scan
        alerts.extend(self._scan_churn_risk())
        
        # 3. Negative margin scan
        alerts.extend(self._scan_negative_margins())
        
        # 4. Data quality scan
        alerts.extend(self._scan_data_quality())
        
        # Sort by severity
        severity_order = {'critical': 0, 'warning': 1, 'info': 2}
        alerts.sort(key=lambda x: severity_order.get(x.severity, 3))
        
        # Generate summary
        summary = self._generate_summary(alerts)
        
        return {
            "scan_time": datetime.now().isoformat(),
            "total_alerts": len(alerts),
            "critical": len([a for a in alerts if a.severity == 'critical']),
            "warning": len([a for a in alerts if a.severity == 'warning']),
            "info": len([a for a in alerts if a.severity == 'info']),
            "summary": summary,
            "alerts": [self._alert_to_dict(a) for a in alerts]
        }
    
    def _scan_revenue_anomalies(self) -> List[Alert]:
        """Find revenue spikes or drops > 30%."""
        alerts = []
        
        try:
            # Aggregate by month/year first
            result = self.db("""
                SELECT month, year, SUM(revenue) as revenue 
                FROM monthly_revenue 
                GROUP BY year, month 
                ORDER BY year, month
            """)
            
            if not result.get('rows'):
                return alerts
            
            rows = result['rows']
            
            # Calculate average and find anomalies
            revenues = [r['revenue'] for r in rows if r['revenue']]
            if not revenues:
                return alerts
                
            avg_revenue = sum(revenues) / len(revenues)
            
            for row in rows:
                if row['revenue'] and row['revenue'] > avg_revenue * 1.3:
                    # Found spike > 30%
                    pct_above = ((row['revenue'] - avg_revenue) / avg_revenue) * 100
                    alerts.append(Alert(
                        id=f"rev-spike-{row['year']}-{row['month']}",
                        severity="critical",
                        category="revenue",
                        title=f"Revenue Spike: {row['month']}/{row['year']}",
                        description=f"Revenue was {pct_above:.0f}% above average in {row['month']}/{row['year']}",
                        metric=f"${row['revenue']:,.0f}",
                        impact=f"+${row['revenue'] - avg_revenue:,.0f} vs average",
                        recommendation="Investigate cause - replicate if positive, address if one-time",
                        data={"month": row['month'], "year": row['year'], "revenue": row['revenue'], "average": avg_revenue}
                    ))
                elif row['revenue'] and row['revenue'] < avg_revenue * 0.7:
                    # Found drop > 30%
                    pct_below = ((avg_revenue - row['revenue']) / avg_revenue) * 100
                    alerts.append(Alert(
                        id=f"rev-drop-{row['year']}-{row['month']}",
                        severity="warning",
                        category="revenue",
                        title=f"Revenue Drop: {row['month']}/{row['year']}",
                        description=f"Revenue was {pct_below:.0f}% below average in {row['month']}/{row['year']}",
                        metric=f"${row['revenue']:,.0f}",
                        impact=f"-${avg_revenue - row['revenue']:,.0f} vs average",
                        recommendation="Identify root cause and implement recovery plan",
                        data={"month": row['month'], "year": row['year'], "revenue": row['revenue'], "average": avg_revenue}
                    ))
        except Exception as e:
            pass
            
        return alerts
    
    def _scan_churn_risk(self) -> List[Alert]:
        """Find customers at risk of churning (inactive > 90 days)."""
        alerts = []
        
        try:
            result = self.db("""
                SELECT customer_id, name, total_spent, 
                       CAST(julianday('2024-06-01') - julianday(last_order_date) AS INTEGER) as days_inactive
                FROM customers 
                WHERE CAST(julianday('2024-06-01') - julianday(last_order_date) AS INTEGER) > 90
                ORDER BY total_spent DESC
                LIMIT 10
            """)
            
            if not result.get('rows'):
                return alerts
            
            rows = result['rows']
            total_at_risk = sum(r['total_spent'] for r in rows if r['total_spent'])
            
            if rows:
                alerts.append(Alert(
                    id="churn-risk-summary",
                    severity="critical",
                    category="churn",
                    title=f"{len(rows)} Customers at Churn Risk",
                    description=f"High-value customers inactive for 90+ days",
                    metric=f"{len(rows)} customers",
                    impact=f"${total_at_risk:,.0f} ARR at risk",
                    recommendation="Launch re-engagement campaign immediately",
                    data={"customers": rows, "total_at_risk": total_at_risk}
                ))
        except Exception as e:
            pass
            
        return alerts
    
    def _scan_negative_margins(self) -> List[Alert]:
        """Find products with cost > price."""
        alerts = []
        
        try:
            result = self.db("""
                SELECT name, unit_price, cost_price,
                       ROUND((unit_price - cost_price) * 100.0 / cost_price, 2) as margin_pct
                FROM products 
                WHERE cost_price > unit_price
            """)
            
            if not result.get('rows'):
                return alerts
            
            for row in result['rows']:
                alerts.append(Alert(
                    id=f"neg-margin-{row['name'][:20]}",
                    severity="critical",
                    category="margin",
                    title=f"Negative Margin: {row['name']}",
                    description=f"Product is selling below cost (margin: {row['margin_pct']}%)",
                    metric=f"{row['margin_pct']}% margin",
                    impact=f"Losing ${row['cost_price'] - row['unit_price']:.2f} per unit",
                    recommendation="Increase price or discontinue product immediately",
                    data=row
                ))
        except Exception as e:
            pass
            
        return alerts
    
    def _scan_data_quality(self) -> List[Alert]:
        """Find duplicate orders and data issues."""
        alerts = []
        
        try:
            result = self.db("""
                SELECT customer_id, order_date, total_amount, COUNT(*) as cnt
                FROM orders
                GROUP BY customer_id, order_date, total_amount
                HAVING cnt > 1
            """)
            
            if result.get('rows'):
                alerts.append(Alert(
                    id="duplicate-orders",
                    severity="warning",
                    category="data_quality",
                    title=f"{len(result['rows'])} Duplicate Orders Found",
                    description="Orders with same customer, date, and amount detected",
                    metric=f"{len(result['rows'])} duplicates",
                    impact="Data integrity issue - may affect reporting",
                    recommendation="Audit order processing system",
                    data={"duplicates": result['rows'][:5]}
                ))
        except Exception as e:
            pass
            
        return alerts
    
    def _generate_summary(self, alerts: List[Alert]) -> str:
        """Generate executive summary of findings."""
        if not alerts:
            return "No issues detected. All metrics within normal ranges."
        
        critical = [a for a in alerts if a.severity == 'critical']
        
        if critical:
            top = critical[0]
            return f"⚠️ {len(critical)} critical issue(s) require immediate attention. Priority: {top.title}"
        
        return f"Found {len(alerts)} item(s) to review. No critical issues."
    
    def _alert_to_dict(self, alert: Alert) -> Dict[str, Any]:
        """Convert Alert to dictionary."""
        return {
            "id": alert.id,
            "severity": alert.severity,
            "category": alert.category,
            "title": alert.title,
            "description": alert.description,
            "metric": alert.metric,
            "impact": alert.impact,
            "recommendation": alert.recommendation,
            "data": alert.data
        }
