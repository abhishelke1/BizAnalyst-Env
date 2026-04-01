"""Anomaly Planter - Inserts calculated anomalies into real data for testing."""
import sqlite3
from datetime import datetime, timedelta
from typing import List, Tuple


def get_reference_date() -> str:
    """Return the fixed reference date used for all date calculations."""
    return '2024-06-01'


class AnomalyPlanter:
    """Plants deterministic anomalies in the database for testing tasks."""
    
    def __init__(self, conn: sqlite3.Connection):
        """Initialize with database connection."""
        self.conn = conn
        self.reference_date = datetime.strptime(get_reference_date(), '%Y-%m-%d')
    
    def plant_revenue_spike(self):
        """Plant revenue spike in March 2024 (43% above average).
        
        Strategy: Create March 2024 entries with boosted revenue if they don't exist,
                 or boost existing entries by 43%
        """
        cursor = self.conn.cursor()
        
        # Check if March 2024 data exists
        cursor.execute("""
            SELECT COUNT(*) FROM monthly_revenue WHERE year = 2024 AND month = 3
        """)
        count = cursor.fetchone()[0]
        
        if count == 0:
            # Create synthetic March 2024 data based on other 2024 months or 2023 data
            print("Creating synthetic March 2024 data for revenue spike...")
            
            # Get average revenue from 2023 data as baseline
            cursor.execute("""
                SELECT AVG(revenue) as avg_revenue, region, category
                FROM monthly_revenue
                WHERE year = 2023
                GROUP BY region, category
            """)
            baseline_data = cursor.fetchall()
            
            if not baseline_data:
                # Fallback: use any available data
                cursor.execute("""
                    SELECT AVG(revenue), region, category
                    FROM monthly_revenue
                    GROUP BY region, category
                    LIMIT 20
                """)
                baseline_data = cursor.fetchall()
            
            if baseline_data:
                # Get max ID
                cursor.execute("SELECT MAX(id) FROM monthly_revenue")
                max_id = cursor.fetchone()[0] or 0
                revenue_id = max_id + 1
                
                # Create March 2024 entries with 43% boost
                for row in baseline_data:
                    avg_revenue = row[0] if row[0] else 50000
                    region = row[1]
                    category = row[2]
                    
                    # Apply 43% boost
                    revenue = round(avg_revenue * 1.43, 2)
                    expenses = round(revenue * 0.65, 2)
                    profit = round(revenue - expenses, 2)
                    
                    cursor.execute("""
                        INSERT INTO monthly_revenue (id, month, year, revenue, expenses, profit, region, category)
                        VALUES (?, 3, 2024, ?, ?, ?, ?, ?)
                    """, (revenue_id, revenue, expenses, profit, region, category))
                    revenue_id += 1
                
                self.conn.commit()
                print(f"[OK] Created {len(baseline_data)} March 2024 records with 43% revenue boost")
            else:
                print("[WARNING] Warning: No baseline data found, cannot plant revenue spike")
                return
        else:
            # Boost existing March 2024 entries
            cursor.execute("""
                SELECT AVG(revenue) as avg_revenue
                FROM monthly_revenue
                WHERE year = 2024 AND month NOT IN (3)
            """)
            result = cursor.fetchone()
            avg_revenue = result[0] if result and result[0] else 50000.0
            
            # Calculate target spike revenue (43% above average)
            target_spike = avg_revenue * 1.43
            
            # Update March 2024 entries
            cursor.execute("""
                UPDATE monthly_revenue
                SET revenue = ?,
                    profit = revenue - expenses
                WHERE year = 2024 AND month = 3
            """, (target_spike,))
            
            self.conn.commit()
            print(f"[OK] Planted revenue spike: March 2024 = ${target_spike:.2f} (43% above avg ${avg_revenue:.2f})")
    
    def plant_negative_margin_product(self):
        """Plant one product with negative margin (cost_price > unit_price).
        
        Strategy: Select a specific product and set cost_price higher than unit_price
        """
        cursor = self.conn.cursor()
        
        # Find a product to modify (preferably something with "Premium" or "Wireless" in name)
        cursor.execute("""
            SELECT product_id, name, unit_price
            FROM products
            WHERE name LIKE '%Wireless%' OR name LIKE '%Premium%'
            ORDER BY product_id
            LIMIT 1
        """)
        result = cursor.fetchone()
        
        if result:
            product_id = result[0]
            name = result[1]
            unit_price = result[2]
        else:
            # Fallback: use first product
            cursor.execute("SELECT product_id, name, unit_price FROM products ORDER BY product_id LIMIT 1")
            result = cursor.fetchone()
            product_id = result[0]
            name = result[1]
            unit_price = result[2]
        
        # Set cost_price to create negative margin (-13.46% similar to original)
        cost_price = round(unit_price * 1.15, 2)  # 15% higher than unit price
        margin_pct = round((unit_price - cost_price) * 100.0 / cost_price, 2)
        
        cursor.execute("""
            UPDATE products
            SET cost_price = ?
            WHERE product_id = ?
        """, (cost_price, product_id))
        
        self.conn.commit()
        print(f"[OK] Planted negative margin: Product '{name}' (ID: {product_id}) - "
              f"UnitPrice: ${unit_price}, CostPrice: ${cost_price}, Margin: {margin_pct}%")
    
    def plant_churn_customers(self) -> List[int]:
        """Plant 3 customers with churn risk (120-150 days since last order).
        
        Strategy: Select 3 customers and set their last_order_date to 120, 135, 150 days ago
        
        Returns:
            List of customer IDs that were marked as churn risk
        """
        cursor = self.conn.cursor()
        
        # Find customers with recent orders to modify
        cursor.execute("""
            SELECT customer_id, name, last_order_date
            FROM customers
            WHERE last_order_date IS NOT NULL
            ORDER BY customer_id
            LIMIT 10
        """)
        
        candidates = cursor.fetchall()
        
        if len(candidates) < 3:
            print("[WARNING] Warning: Not enough customers to plant churn anomaly")
            return []
        
        # Select 3 customers deterministically (e.g., IDs ending with specific patterns)
        churn_customers = []
        days_offsets = [150, 135, 120]  # Days since last order
        
        for i, days in enumerate(days_offsets):
            if i < len(candidates):
                customer_id = candidates[i][0]
                name = candidates[i][1]
                
                # Calculate new last_order_date
                last_order_date = (self.reference_date - timedelta(days=days)).strftime('%Y-%m-%d')
                
                cursor.execute("""
                    UPDATE customers
                    SET last_order_date = ?
                    WHERE customer_id = ?
                """, (last_order_date, customer_id))
                
                churn_customers.append(customer_id)
                print(f"[OK] Planted churn risk: Customer '{name}' (ID: {customer_id}) - "
                      f"Last order: {days} days ago")
        
        self.conn.commit()
        return churn_customers
    
    def plant_duplicate_orders(self) -> List[int]:
        """Plant duplicate orders for 2 customers (same date, same amount).
        
        Strategy: Find 2 customers with existing orders, create duplicate order records
        
        Returns:
            List of customer IDs that have duplicate orders
        """
        cursor = self.conn.cursor()
        
        # Find 2 customers with multiple completed orders
        cursor.execute("""
            SELECT customer_id, name
            FROM customers
            WHERE order_count >= 2
            ORDER BY customer_id
            LIMIT 5
        """)
        
        candidates = cursor.fetchall()
        
        if len(candidates) < 2:
            print("[WARNING] Warning: Not enough customers to plant duplicate orders")
            return []
        
        duplicate_customers = []
        duplicate_date = '2024-01-15'
        duplicate_amount = 299.99
        
        # Get max order_id to avoid conflicts
        cursor.execute("SELECT MAX(order_id) FROM orders")
        max_order_id = cursor.fetchone()[0] or 0
        new_order_id = max_order_id + 1
        
        for i in range(min(2, len(candidates))):
            customer_id = candidates[i][0]
            name = candidates[i][1]
            
            # Create two identical orders for this customer
            for j in range(2):
                cursor.execute("""
                    INSERT INTO orders (order_id, customer_id, order_date, status, total_amount, discount_pct)
                    VALUES (?, ?, ?, 'completed', ?, 0.0)
                """, (new_order_id, customer_id, duplicate_date, duplicate_amount))
                
                new_order_id += 1
            
            duplicate_customers.append(customer_id)
            print(f"[OK] Planted duplicate orders: Customer '{name}' (ID: {customer_id}) - "
                  f"2 orders on {duplicate_date} for ${duplicate_amount}")
        
        self.conn.commit()
        return duplicate_customers
    
    def plant_all_anomalies(self):
        """Plant all anomalies for testing.
        
        Returns:
            Dict with information about planted anomalies
        """
        print("\n=== Planting Anomalies ===")
        
        self.plant_revenue_spike()
        self.plant_negative_margin_product()
        churn_customers = self.plant_churn_customers()
        duplicate_customers = self.plant_duplicate_orders()
        
        print("=== Anomalies Planted Successfully ===\n")
        
        return {
            'revenue_spike': {'month': 3, 'year': 2024},
            'churn_customers': churn_customers,
            'duplicate_customers': duplicate_customers
        }
    
    def verify_anomalies(self):
        """Verify that all anomalies are present in the database.
        
        Returns:
            Dict with verification results
        """
        cursor = self.conn.cursor()
        results = {}
        
        print("\n=== Verifying Anomalies ===")
        
        # 1. Check revenue spike
        cursor.execute("""
            SELECT month, year, AVG(revenue) as avg_revenue
            FROM monthly_revenue
            WHERE year = 2024 AND month = 3
        """)
        spike = cursor.fetchone()
        if spike and spike[2]:
            cursor.execute("""
                SELECT AVG(revenue)
                FROM monthly_revenue
                WHERE year = 2024 AND month != 3
            """)
            avg_row = cursor.fetchone()
            avg_other = avg_row[0] if avg_row and avg_row[0] else 0
            spike_pct = ((spike[2] - avg_other) / avg_other * 100) if avg_other else 0
            results['revenue_spike'] = {
                'found': True,
                'month': spike[0],
                'year': spike[1],
                'spike_percentage': round(spike_pct, 2)
            }
            print(f"[OK] Revenue spike found: {spike[0]}/{spike[1]} - {spike_pct:.2f}% above average")
        else:
            results['revenue_spike'] = {'found': False}
            print("[X] Revenue spike not found")
        
        # 2. Check negative margin product
        cursor.execute("""
            SELECT product_id, name, unit_price, cost_price,
                   ROUND((unit_price - cost_price) * 100.0 / cost_price, 2) as margin_pct
            FROM products
            WHERE cost_price > unit_price
        """)
        neg_margin = cursor.fetchone()
        if neg_margin:
            results['negative_margin'] = {
                'found': True,
                'product_id': neg_margin[0],
                'name': neg_margin[1],
                'margin_pct': neg_margin[4]
            }
            print(f"[OK] Negative margin product found: '{neg_margin[1]}' - Margin: {neg_margin[4]}%")
        
        # 3. Check churn customers
        reference_date_str = get_reference_date()
        cursor.execute(f"""
            SELECT customer_id, name,
                   CAST(julianday('{reference_date_str}') - julianday(last_order_date) AS INTEGER) as days_since
            FROM customers
            WHERE last_order_date IS NOT NULL
              AND CAST(julianday('{reference_date_str}') - julianday(last_order_date) AS INTEGER) > 90
            ORDER BY days_since DESC
            LIMIT 5
        """)
        churn = cursor.fetchall()
        results['churn_customers'] = {
            'found': len(churn) >= 3,
            'count': len(churn),
            'customers': [(c[0], c[1], c[2]) for c in churn[:3]]
        }
        print(f"[OK] Churn customers found: {len(churn)} customers with >90 days since last order")
        
        # 4. Check duplicate orders
        cursor.execute("""
            SELECT customer_id, order_date, total_amount, COUNT(*) as cnt
            FROM orders
            GROUP BY customer_id, order_date, total_amount
            HAVING cnt > 1
        """)
        duplicates = cursor.fetchall()
        dup_customers = list(set([d[0] for d in duplicates]))
        results['duplicate_orders'] = {
            'found': len(dup_customers) >= 2,
            'customer_count': len(dup_customers),
            'customers': dup_customers
        }
        print(f"[OK] Duplicate orders found: {len(dup_customers)} customers with duplicate orders")
        
        print("=== Verification Complete ===\n")
        
        return results
