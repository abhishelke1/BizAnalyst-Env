"""Northwind Database Adapter - Transforms Northwind data to BizAnalyst schema."""
import sqlite3
from datetime import datetime, timedelta
from typing import List, Tuple, Dict
import os


def get_reference_date() -> str:
    """Return the fixed reference date used for all date calculations."""
    return '2024-06-01'


class NorthwindAdapter:
    """Adapter to load and transform Northwind database to current schema."""
    
    def __init__(self, northwind_db_path: str = "northwind.db"):
        """Initialize adapter with path to Northwind database."""
        self.northwind_db_path = northwind_db_path
        self.reference_date = datetime.strptime(get_reference_date(), '%Y-%m-%d')
        
    def _transform_date(self, old_date_str: str, days_offset: int = 0) -> str:
        """Transform old Northwind dates to 2022-2024 timeframe.
        
        Args:
            old_date_str: Original date string from Northwind
            days_offset: Additional days to offset (for spreading dates)
            
        Returns:
            Transformed date string in YYYY-MM-DD format
        """
        try:
            # Parse the old date (handle various formats)
            old_date = datetime.strptime(old_date_str.split()[0], '%Y-%m-%d')
        except:
            # Fallback to reference date if parsing fails
            return (self.reference_date - timedelta(days=180)).strftime('%Y-%m-%d')
        
        # Northwind dates range from 1996-07-04 to 1998-05-06
        # We want to map them to 2022-01-01 to 2024-05-31
        northwind_start = datetime(1996, 7, 4)
        northwind_end = datetime(1998, 5, 6)
        target_start = datetime(2022, 1, 1)
        target_end = datetime(2024, 5, 31)
        
        # Calculate position in original range (0.0 to 1.0)
        if old_date < northwind_start:
            old_date = northwind_start
        if old_date > northwind_end:
            old_date = northwind_end
            
        original_range = (northwind_end - northwind_start).days
        position = (old_date - northwind_start).days / original_range if original_range > 0 else 0
        
        # Map to new range
        new_range = (target_end - target_start).days
        new_date = target_start + timedelta(days=int(position * new_range))
        
        # Add offset for variation
        if days_offset != 0:
            new_date = new_date + timedelta(days=days_offset % 30)
        
        # Ensure within bounds
        if new_date < target_start:
            new_date = target_start
        if new_date > target_end:
            new_date = target_end
            
        return new_date.strftime('%Y-%m-%d')
    
    def load_customers(self) -> List[Tuple]:
        """Load and transform Northwind customers to current schema.
        
        Returns:
            List of tuples: (customer_id, name, region, segment, signup_date, 
                           last_order_date, total_spent, order_count)
        """
        conn = sqlite3.connect(self.northwind_db_path)
        cursor = conn.cursor()
        
        # Fetch Northwind customers
        cursor.execute("""
            SELECT CustomerID, CompanyName, ContactName, Region, Country, City
            FROM Customers
            ORDER BY CustomerID
        """)
        
        customers_data = []
        regions_map = {
            'WA': 'West', 'OR': 'West', 'CA': 'West', 'ID': 'West', 'MT': 'West',
            'WY': 'West', 'AK': 'West', 'NV': 'West', 'UT': 'West', 'CO': 'West',
            'NM': 'West', 'AZ': 'West', 'HI': 'West',
            'NY': 'East', 'PA': 'East', 'NJ': 'East', 'CT': 'East', 'MA': 'East',
            'VT': 'East', 'NH': 'East', 'ME': 'East', 'RI': 'East', 'DE': 'East',
            'MD': 'East', 'VA': 'East', 'WV': 'East', 'NC': 'East', 'SC': 'East',
            'GA': 'East', 'FL': 'East',
            'IL': 'North', 'IN': 'North', 'MI': 'North', 'OH': 'North', 'WI': 'North',
            'MN': 'North', 'IA': 'North', 'MO': 'North', 'ND': 'North', 'SD': 'North',
            'NE': 'North', 'KS': 'North',
            'TX': 'South', 'OK': 'South', 'AR': 'South', 'LA': 'South', 'MS': 'South',
            'AL': 'South', 'TN': 'South', 'KY': 'South'
        }
        
        segments = ['Enterprise', 'SMB', 'Consumer']
        
        for i, row in enumerate(cursor.fetchall(), start=1):
            customer_id = i  # Use numeric IDs
            orig_id = row[0]
            name = row[1]  # CompanyName
            
            # Map region - use Region field if available, otherwise map from Country
            region_raw = row[3] if row[3] else ''
            region = regions_map.get(region_raw, '')
            if not region:
                # Map by country or use hash for deterministic assignment
                region = ['North', 'South', 'East', 'West'][hash(orig_id) % 4]
            
            # Assign segment deterministically
            segment = segments[i % len(segments)]
            
            # Generate signup date (1-3 years before reference)
            signup_offset = 365 + (hash(orig_id + 'signup') % 730)  # 1-3 years
            signup_date = (self.reference_date - timedelta(days=signup_offset)).strftime('%Y-%m-%d')
            
            # last_order_date, total_spent, order_count will be updated later from orders
            customers_data.append((
                customer_id,
                name,
                region,
                segment,
                signup_date,
                None,  # last_order_date - set from orders
                0.0,   # total_spent - calculated from orders
                0      # order_count - calculated from orders
            ))
        
        conn.close()
        return customers_data
    
    def load_products(self) -> List[Tuple]:
        """Load and transform Northwind products to current schema.
        
        Returns:
            List of tuples: (product_id, name, category, unit_price, cost_price, stock_quantity)
        """
        conn = sqlite3.connect(self.northwind_db_path)
        cursor = conn.cursor()
        
        # Fetch Northwind products with category names
        cursor.execute("""
            SELECT p.ProductID, p.ProductName, c.CategoryName, p.UnitPrice, 
                   p.UnitsInStock, p.UnitsOnOrder, p.ReorderLevel
            FROM Products p
            JOIN Categories c ON p.CategoryID = c.CategoryID
            WHERE p.Discontinued = '0'
            ORDER BY p.ProductID
        """)
        
        products_data = []
        
        for row in cursor.fetchall():
            product_id = row[0]
            name = row[1]
            category = row[2]
            unit_price = float(row[3]) if row[3] else 50.0
            units_in_stock = row[4] if row[4] else 0
            
            # Calculate cost_price as 55-70% of unit_price (normal margin)
            cost_price = round(unit_price * (0.55 + (hash(name) % 15) / 100), 2)
            
            # Stock quantity
            stock_quantity = units_in_stock
            
            products_data.append((
                product_id,
                name,
                category,
                unit_price,
                cost_price,
                stock_quantity
            ))
        
        conn.close()
        return products_data
    
    def load_orders_and_items(self) -> Tuple[List[Tuple], List[Tuple], Dict[int, int]]:
        """Load and transform Northwind orders and order items.
        
        Returns:
            Tuple of:
            - orders_data: List of tuples (order_id, customer_id, order_date, status, total_amount, discount_pct)
            - order_items_data: List of tuples (item_id, order_id, product_id, quantity, unit_price)
            - customer_id_map: Dict mapping original CustomerID to new numeric customer_id
        """
        conn = sqlite3.connect(self.northwind_db_path)
        cursor = conn.cursor()
        
        # First, create customer ID mapping
        cursor.execute("SELECT CustomerID FROM Customers ORDER BY CustomerID")
        customer_id_map = {}
        for i, row in enumerate(cursor.fetchall(), start=1):
            customer_id_map[row[0]] = i
        
        # Fetch orders with customer mapping
        cursor.execute("""
            SELECT o.OrderID, o.CustomerID, o.OrderDate, o.ShippedDate, o.Freight
            FROM Orders o
            WHERE o.OrderDate IS NOT NULL
            ORDER BY o.OrderDate
        """)
        
        orders_data = []
        order_items_data = []
        item_id_counter = 1
        
        statuses = ['completed', 'completed', 'completed', 'completed', 'pending', 'cancelled']
        
        for i, order_row in enumerate(cursor.fetchall()):
            order_id = order_row[0]
            orig_customer_id = order_row[1]
            customer_id = customer_id_map.get(orig_customer_id, 1)
            order_date_str = order_row[2]
            shipped_date_str = order_row[3]
            
            # Transform date to 2022-2024 timeframe
            order_date = self._transform_date(order_date_str, days_offset=i % 100)
            
            # Determine status based on shipped date
            if shipped_date_str:
                status = 'completed'
            else:
                status = statuses[i % len(statuses)]
            
            # Fetch order items for this order
            cursor.execute("""
                SELECT ProductID, UnitPrice, Quantity, Discount
                FROM `Order Details`
                WHERE OrderID = ?
            """, (order_id,))
            
            order_items = cursor.fetchall()
            total_amount = 0.0
            avg_discount = 0.0
            
            for item_row in order_items:
                product_id = item_row[0]
                unit_price = float(item_row[1])
                quantity = item_row[2]
                discount = float(item_row[3]) if item_row[3] else 0.0
                
                # Calculate item total (discount is per item in Northwind)
                item_total = unit_price * quantity * (1 - discount)
                total_amount += item_total
                avg_discount += discount
                
                order_items_data.append((
                    item_id_counter,
                    order_id,
                    product_id,
                    quantity,
                    unit_price
                ))
                item_id_counter += 1
            
            # Calculate average discount percentage
            discount_pct = round((avg_discount / len(order_items) * 100) if order_items else 0.0, 2)
            total_amount = round(total_amount, 2)
            
            orders_data.append((
                order_id,
                customer_id,
                order_date,
                status,
                total_amount,
                discount_pct
            ))
        
        conn.close()
        return orders_data, order_items_data, customer_id_map
    
    def calculate_monthly_revenue(self, orders_data: List[Tuple], 
                                  customers_data: List[Tuple],
                                  order_items_data: List[Tuple],
                                  products_data: List[Tuple]) -> List[Tuple]:
        """Calculate monthly revenue aggregations from orders.
        
        Args:
            orders_data: List of order tuples
            customers_data: List of customer tuples
            order_items_data: List of order item tuples
            products_data: List of product tuples
            
        Returns:
            List of tuples: (id, month, year, revenue, expenses, profit, region, category)
        """
        # Create lookup dictionaries
        customer_map = {c[0]: {'region': c[2]} for c in customers_data}
        product_map = {p[0]: {'category': p[2], 'cost_price': p[4]} for p in products_data}
        
        # Create order items lookup
        order_items_map = {}
        for item in order_items_data:
            order_id = item[1]
            product_id = item[2]
            quantity = item[3]
            unit_price = item[4]
            
            if order_id not in order_items_map:
                order_items_map[order_id] = []
            order_items_map[order_id].append({
                'product_id': product_id,
                'quantity': quantity,
                'unit_price': unit_price
            })
        
        # Aggregate by month/year/region/category
        aggregations = {}
        
        for order in orders_data:
            order_id = order[0]
            customer_id = order[1]
            order_date = order[2]
            status = order[3]
            total_amount = order[4]
            
            # Only count completed orders
            if status != 'completed':
                continue
            
            # Parse date
            date_obj = datetime.strptime(order_date, '%Y-%m-%d')
            month = date_obj.month
            year = date_obj.year
            
            # Get customer region
            region = customer_map.get(customer_id, {}).get('region', 'North')
            
            # Calculate expenses from order items
            items = order_items_map.get(order_id, [])
            for item in items:
                product_id = item['product_id']
                quantity = item['quantity']
                unit_price = item['unit_price']
                
                product_info = product_map.get(product_id, {'category': 'Electronics', 'cost_price': unit_price * 0.6})
                category = product_info['category']
                cost_price = product_info['cost_price']
                
                revenue = unit_price * quantity
                expense = cost_price * quantity
                profit = revenue - expense
                
                key = (month, year, region, category)
                if key not in aggregations:
                    aggregations[key] = {'revenue': 0.0, 'expenses': 0.0, 'profit': 0.0}
                
                aggregations[key]['revenue'] += revenue
                aggregations[key]['expenses'] += expense
                aggregations[key]['profit'] += profit
        
        # Convert to list of tuples
        monthly_revenue_data = []
        revenue_id = 1
        
        for (month, year, region, category), values in sorted(aggregations.items()):
            monthly_revenue_data.append((
                revenue_id,
                month,
                year,
                round(values['revenue'], 2),
                round(values['expenses'], 2),
                round(values['profit'], 2),
                region,
                category
            ))
            revenue_id += 1
        
        return monthly_revenue_data
