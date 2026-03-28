#!/usr/bin/env python3
"""Check actual answers in the database - see what the AI should find."""

import sys
sys.path.insert(0, '.')

from environment.database import DatabaseManager, get_reference_date

def main():
    # Initialize database with same seed as environment
    db = DatabaseManager()
    db.connect()
    db.create_schema()
    db.seed_data()
    
    print("=" * 80)
    print("BizAnalyst-Env - Database Answer Verification")
    print(f"Reference Date: {get_reference_date()}")
    print("=" * 80)
    print()
    
    # TASK 1: Revenue Summary
    print("=" * 80)
    print("TASK 1: revenue_summary (Easy)")
    print("Question: Calculate total revenue, expenses, and profit for 2023.")
    print("          Also find which region had the highest revenue.")
    print("=" * 80)
    
    query = """
        SELECT 
            SUM(revenue) as total_revenue,
            SUM(expenses) as total_expenses,
            SUM(profit) as total_profit
        FROM monthly_revenue 
        WHERE year = 2023
    """
    result = db.execute_query(query)
    row = result[0]
    
    print(f"\n📊 2023 Financial Summary:")
    print(f"   Total Revenue  : ${row['total_revenue']:,.2f}")
    print(f"   Total Expenses : ${row['total_expenses']:,.2f}")
    print(f"   Net Profit     : ${row['total_profit']:,.2f}")
    
    query_region = """
        SELECT region, SUM(revenue) as total
        FROM monthly_revenue
        WHERE year = 2023
        GROUP BY region
        ORDER BY total DESC
        LIMIT 1
    """
    result = db.execute_query(query_region)
    row = result[0]
    print(f"   Top Region     : {row['region']} (${row['total']:,.2f})")
    
    # Show all regions for comparison
    query_all = """
        SELECT region, SUM(revenue) as total
        FROM monthly_revenue
        WHERE year = 2023
        GROUP BY region
        ORDER BY total DESC
    """
    results = db.execute_query(query_all)
    print(f"\n   All Regions:")
    for r in results:
        print(f"     {r['region']:<10} ${r['total']:,.2f}")
    
    print(f"\n✅ Expected Answer Format:")
    result_first = db.execute_query(query)
    row_first = result_first[0]
    result_region = db.execute_query(query_region)
    top_region = result_region[0]
    print(f"   Total Revenue: ${row_first['total_revenue']:,.2f} | Total Expenses: ${row_first['total_expenses']:,.2f} | Net Profit: ${row_first['total_profit']:,.2f} | Top Region: {top_region['region']}")
    print()
    
    # TASK 2: Customer Churn Risk
    print("=" * 80)
    print("TASK 2: customer_churn_risk (Medium)")
    print(f"Question: Find top 3 customers at churn risk (>90 days since last order)")
    print(f"          Reference date: {get_reference_date()}")
    print("=" * 80)
    
    query = """
        SELECT 
            customer_id,
            name,
            region,
            segment,
            last_order_date,
            CAST(julianday('2024-06-01') - julianday(last_order_date) AS INTEGER) as days_since_order,
            order_count,
            total_spent
        FROM customers
        WHERE CAST(julianday('2024-06-01') - julianday(last_order_date) AS INTEGER) > 90
        ORDER BY days_since_order DESC
        LIMIT 10
    """
    results = db.execute_query(query)
    
    print(f"\n🚨 Top {min(10, len(results))} Customers at Churn Risk:")
    print(f"{'ID':<6} {'Name':<30} {'Last Order':<12} {'Days':<6} {'Orders':<8} {'Total Spent'}")
    print("-" * 95)
    
    for i, r in enumerate(results):
        marker = "⭐" if i < 3 else "  "
        print(f"{marker} {r['customer_id']:<4} {r['name']:<30} {r['last_order_date']:<12} {r['days_since_order']:<6} {r['order_count']:<8} ${r['total_spent']:>10,.2f}")
    
    print(f"\n✅ Expected Answer (Top 3 with recommendations):")
    top3 = results[:3]
    print(f'   [')
    for i, r in enumerate(top3):
        comma = "," if i < 2 else ""
        print(f'     {{"customer_id": {r["customer_id"]}, "name": "{r["name"]}", "days_since_last_order": {r["days_since_order"]}, "recommendation": "Send discount email offer"}}{comma}')
    print(f'   ]')
    print()
    
    # TASK 3: Anomaly Investigation
    print("=" * 80)
    print("TASK 3: anomaly_investigation (Hard)")
    print("Question: Find (1) revenue spike, (2) negative margin product, (3) duplicates")
    print("=" * 80)
    
    # 1. Revenue Spike
    print(f"\n🔍 Part 1: Revenue Spike Detection")
    query = """
        SELECT month, year, revenue
        FROM monthly_revenue
        WHERE year IN (2022, 2023, 2024)
        GROUP BY month, year
        HAVING revenue > 100000
        ORDER BY revenue DESC
        LIMIT 5
    """
    results = db.execute_query(query)
    print(f"   Months with revenue > $100,000:")
    for r in results:
        print(f"     {r['month']:02d}/{r['year']} - ${r['revenue']:,.2f}")
    
    # Check March 2024 specifically
    query_spike = """
        SELECT month, year, SUM(revenue) as total_revenue
        FROM monthly_revenue
        WHERE year = 2024 AND month = 3
        GROUP BY month, year
    """
    spike = db.execute_query(query_spike)[0]
    print(f"\n   ⚡ SPIKE FOUND: March 2024 = ${spike['total_revenue']:,.2f}")
    
    # Average for comparison
    query_avg = """
        SELECT AVG(revenue) as avg_rev
        FROM monthly_revenue
        WHERE year IN (2022, 2023, 2024) AND NOT (year = 2024 AND month = 3)
    """
    avg = db.execute_query(query_avg)[0]
    spike_pct = ((spike['total_revenue'] - avg['avg_rev']) / avg['avg_rev']) * 100
    print(f"   Average other months: ${avg['avg_rev']:,.2f}")
    print(f"   Spike percentage: {spike_pct:.1f}% above average")
    
    # 2. Negative Margin Product
    print(f"\n🔍 Part 2: Negative Margin Product")
    query = """
        SELECT 
            name, 
            unit_price, 
            cost_price,
            ROUND((unit_price - cost_price) * 100.0 / unit_price, 2) as margin_pct
        FROM products
        WHERE cost_price > unit_price
    """
    results = db.execute_query(query)
    
    if results:
        print(f"   Products with NEGATIVE profit margin:")
        for r in results:
            print(f"     Product: {r['name']}")
            print(f"     Sell Price: ${r['unit_price']:.2f} | Cost: ${r['cost_price']:.2f}")
            print(f"     Margin: {r['margin_pct']:.2f}% (LOSING ${r['cost_price'] - r['unit_price']:.2f} per unit!)")
    else:
        print(f"   No negative margin products found.")
    
    # 3. Duplicate Orders
    print(f"\n🔍 Part 3: Duplicate Orders")
    query = """
        SELECT 
            customer_id, 
            order_date, 
            total_amount, 
            COUNT(*) as duplicate_count
        FROM orders
        GROUP BY customer_id, order_date, total_amount
        HAVING COUNT(*) > 1
        ORDER BY customer_id
    """
    results = db.execute_query(query)
    
    print(f"   Duplicate orders found: {len(results)}")
    duplicate_customer_ids = sorted(list(set([r['customer_id'] for r in results])))
    
    for r in results:
        # Get customer name
        query_name = f"SELECT name FROM customers WHERE customer_id = {r['customer_id']}"
        cust = db.execute_query(query_name)[0]
        print(f"     Customer ID: {r['customer_id']} ({cust['name']})")
        print(f"     Date: {r['order_date']} | Amount: ${r['total_amount']:.2f} | Duplicates: {r['duplicate_count']}")
    
    print(f"\n   Unique customer IDs with duplicates: {duplicate_customer_ids}")
    
    # Expected Answer
    print(f"\n✅ Expected Answer:")
    if results:
        neg_margin = db.execute_query("""
            SELECT name, ROUND((unit_price - cost_price) * 100.0 / unit_price, 2) as margin_pct
            FROM products WHERE cost_price > unit_price LIMIT 1
        """)[0]
        
        answer = {
            "spike_month": spike['month'],
            "spike_year": spike['year'],
            "spike_explanation": "Unusual seasonal promotion campaign caused revenue spike",
            "negative_margin_product": neg_margin['name'],
            "margin_pct": neg_margin['margin_pct'],
            "duplicate_customer_ids": duplicate_customer_ids
        }
        import json
        print(f"   {json.dumps(answer, indent=2)}")
    
    print()
    print("=" * 80)
    print("Database Verification Complete!")
    print("=" * 80)
    print(f"\n💡 Tips:")
    print(f"   - These are the EXACT answers the AI should find")
    print(f"   - The grader compares AI responses to these values")
    print(f"   - All data is deterministic (seed=42)")
    print(f"   - Reference date is fixed: {get_reference_date()}")
    print()
    
    db.close()

if __name__ == "__main__":
    main()
