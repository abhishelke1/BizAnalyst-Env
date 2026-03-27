import sqlite3
import random
from datetime import datetime, timedelta
from faker import Faker
from typing import List, Tuple


class DatabaseManager:
    """Manages SQLite database initialization and seeding."""
    
    def __init__(self, db_path: str = ":memory:"):
        """Initialize database manager.
        
        Args:
            db_path: Path to SQLite database (default: in-memory)
        """
        self.db_path = db_path
        self.conn = None
        
    def connect(self):
        """Create database connection."""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        
    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            
    def create_schema(self):
        """Create all database tables."""
        cursor = self.conn.cursor()
        
        # Customers table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                customer_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                region TEXT NOT NULL,
                segment TEXT NOT NULL,
                signup_date TEXT NOT NULL,
                last_order_date TEXT,
                total_spent REAL DEFAULT 0.0,
                order_count INTEGER DEFAULT 0
            )
        """)
        
        # Products table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS products (
                product_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                unit_price REAL NOT NULL,
                cost_price REAL NOT NULL,
                stock_quantity INTEGER DEFAULT 0
            )
        """)
        
        # Orders table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                order_id INTEGER PRIMARY KEY,
                customer_id INTEGER NOT NULL,
                order_date TEXT NOT NULL,
                status TEXT NOT NULL,
                total_amount REAL NOT NULL,
                discount_pct REAL DEFAULT 0.0,
                FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
            )
        """)
        
        # Order items table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS order_items (
                item_id INTEGER PRIMARY KEY,
                order_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL,
                unit_price REAL NOT NULL,
                FOREIGN KEY (order_id) REFERENCES orders(order_id),
                FOREIGN KEY (product_id) REFERENCES products(product_id)
            )
        """)
        
        # Monthly revenue table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS monthly_revenue (
                id INTEGER PRIMARY KEY,
                month INTEGER NOT NULL,
                year INTEGER NOT NULL,
                revenue REAL NOT NULL,
                expenses REAL NOT NULL,
                profit REAL NOT NULL,
                region TEXT NOT NULL,
                category TEXT NOT NULL
            )
        """)
        
        self.conn.commit()
        
    def seed_data(self):
        """Seed database with deterministic fake data."""
        # Set random seed for reproducibility
        random.seed(42)
        fake = Faker()
        Faker.seed(42)
        
        cursor = self.conn.cursor()
        
        # Define constants
        regions = ['North', 'South', 'East', 'West']
        segments = ['Enterprise', 'SMB', 'Consumer']
        categories = ['Electronics', 'Office Supplies', 'Furniture', 'Software', 'Accessories']
        
        # 1. Seed customers (200 customers)
        customers_data = []
        for i in range(1, 201):
            customer_id = i
            name = fake.company()
            region = regions[i % len(regions)]
            segment = segments[i % len(segments)]
            signup_date = fake.date_between(start_date='-3y', end_date='-1y')
            
            customers_data.append((
                customer_id, name, region, segment, 
                signup_date.strftime('%Y-%m-%d'), None, 0.0, 0
            ))
        
        cursor.executemany("""
            INSERT INTO customers (customer_id, name, region, segment, signup_date, 
                                  last_order_date, total_spent, order_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, customers_data)
        
        # 2. Seed products (50 products)
        products_data = []
        product_names = [
            "Wireless Mouse", "Mechanical Keyboard", "USB Cable", "HDMI Adapter", "Laptop Stand",
            "Monitor 24inch", "Webcam HD", "Headphones", "Desk Lamp", "Office Chair",
            "Standing Desk", "Cable Organizer", "Mouse Pad", "Laptop Bag", "Power Bank",
            "USB Hub", "Ethernet Cable", "Wireless Charger", "Screen Protector", "Phone Holder",
            "Notebook Set", "Pen Pack", "Stapler", "Paper Clips", "Sticky Notes",
            "Whiteboard", "Markers Set", "File Organizer", "Desk Drawer", "Bookshelf",
            "Printer", "Scanner", "Shredder", "Label Maker", "Calculator",
            "Desk Calendar", "Wall Clock", "Trash Bin", "Water Bottle", "Coffee Mug",
            "Desk Mat", "Keyboard Tray", "Monitor Arm", "Footrest", "Lumbar Support",
            "Premium Wireless Keyboard", "Gaming Mouse", "USB Microphone", "Ring Light", "Document Camera"
        ]
        
        for i in range(50):
            product_id = i + 1
            name = product_names[i]
            category = categories[i % len(categories)]
            
            # Normal pricing
            unit_price = round(random.uniform(10, 200), 2)
            cost_price = round(unit_price * random.uniform(0.4, 0.7), 2)
            
            # Plant negative margin product
            if name == "Premium Wireless Keyboard":
                unit_price = 45.0
                cost_price = 52.0
            
            stock_quantity = random.randint(0, 500)
            
            products_data.append((
                product_id, name, category, unit_price, cost_price, stock_quantity
            ))
        
        cursor.executemany("""
            INSERT INTO products (product_id, name, category, unit_price, cost_price, stock_quantity)
            VALUES (?, ?, ?, ?, ?, ?)
        """, products_data)
        
        # 3. Seed orders (1000+ orders spanning 2022-2024)
        orders_data = []
        order_items_data = []
        order_statuses = ['completed', 'completed', 'completed', 'completed', 'pending', 'cancelled']
        
        order_id = 1
        item_id = 1
        
        start_date = datetime(2022, 1, 1)
        end_date = datetime(2024, 12, 31)
        
        for i in range(1200):
            customer_id = random.randint(1, 200)
            order_date = fake.date_between(start_date=start_date, end_date=end_date)
            status = random.choice(order_statuses)
            discount_pct = round(random.choice([0, 0, 0, 5, 10, 15]), 2)
            
            # Create order items
            num_items = random.randint(1, 5)
            total_amount = 0.0
            
            for _ in range(num_items):
                product_id = random.randint(1, 50)
                quantity = random.randint(1, 10)
                
                # Get product price
                cursor.execute("SELECT unit_price FROM products WHERE product_id = ?", (product_id,))
                result = cursor.fetchone()
                unit_price = result[0] if result else 50.0
                
                item_total = unit_price * quantity
                total_amount += item_total
                
                order_items_data.append((
                    item_id, order_id, product_id, quantity, unit_price
                ))
                item_id += 1
            
            # Apply discount
            total_amount = round(total_amount * (1 - discount_pct / 100), 2)
            
            orders_data.append((
                order_id, customer_id, order_date.strftime('%Y-%m-%d'), 
                status, total_amount, discount_pct
            ))
            order_id += 1
        
        cursor.executemany("""
            INSERT INTO orders (order_id, customer_id, order_date, status, total_amount, discount_pct)
            VALUES (?, ?, ?, ?, ?, ?)
        """, orders_data)
        
        cursor.executemany("""
            INSERT INTO order_items (item_id, order_id, product_id, quantity, unit_price)
            VALUES (?, ?, ?, ?, ?)
        """, order_items_data)
        
        # Plant duplicate orders for customers 15 and 67
        duplicate_date = '2024-01-15'
        duplicate_amount = 299.99
        
        cursor.execute("""
            INSERT INTO orders (order_id, customer_id, order_date, status, total_amount, discount_pct)
            VALUES (?, 15, ?, 'completed', ?, 0.0)
        """, (order_id, duplicate_date, duplicate_amount))
        order_id += 1
        
        cursor.execute("""
            INSERT INTO orders (order_id, customer_id, order_date, status, total_amount, discount_pct)
            VALUES (?, 15, ?, 'completed', ?, 0.0)
        """, (order_id, duplicate_date, duplicate_amount))
        order_id += 1
        
        cursor.execute("""
            INSERT INTO orders (order_id, customer_id, order_date, status, total_amount, discount_pct)
            VALUES (?, 67, ?, 'completed', ?, 0.0)
        """, (order_id, duplicate_date, duplicate_amount))
        order_id += 1
        
        cursor.execute("""
            INSERT INTO orders (order_id, customer_id, order_date, status, total_amount, discount_pct)
            VALUES (?, 67, ?, 'completed', ?, 0.0)
        """, (order_id, duplicate_date, duplicate_amount))
        
        # 4. Update customer aggregates
        cursor.execute("""
            UPDATE customers
            SET total_spent = (
                SELECT COALESCE(SUM(total_amount), 0)
                FROM orders
                WHERE orders.customer_id = customers.customer_id
                AND orders.status = 'completed'
            ),
            order_count = (
                SELECT COUNT(*)
                FROM orders
                WHERE orders.customer_id = customers.customer_id
                AND orders.status = 'completed'
            ),
            last_order_date = (
                SELECT MAX(order_date)
                FROM orders
                WHERE orders.customer_id = customers.customer_id
                AND orders.status = 'completed'
            )
        """)
        
        # Plant churn risk customers (IDs ending in 07, 23, 89)
        # Set their last_order_date to > 120 days ago
        churn_date = (datetime.now() - timedelta(days=130)).strftime('%Y-%m-%d')
        churn_customer_ids = [7, 23, 89, 107]
        
        for cid in churn_customer_ids:
            if cid <= 200:
                cursor.execute("""
                    UPDATE customers
                    SET last_order_date = ?
                    WHERE customer_id = ?
                """, (churn_date, cid))
        
        # 5. Seed monthly_revenue (2022-2024, with March 2024 spike)
        monthly_revenue_data = []
        revenue_id = 1
        
        for year in [2022, 2023, 2024]:
            for month in range(1, 13):
                if year == 2024 and month > 3:
                    break
                    
                for region in regions:
                    for category in categories:
                        base_revenue = random.uniform(10000, 50000)
                        
                        # Plant revenue spike in March 2024
                        if year == 2024 and month == 3:
                            # Calculate 6-month average (Sep 2023 - Feb 2024)
                            six_month_avg = 30000  # Approximate average
                            base_revenue = six_month_avg * 1.43  # 43% spike
                        
                        revenue = round(base_revenue, 2)
                        expenses = round(revenue * random.uniform(0.6, 0.8), 2)
                        profit = round(revenue - expenses, 2)
                        
                        monthly_revenue_data.append((
                            revenue_id, month, year, revenue, expenses, 
                            profit, region, category
                        ))
                        revenue_id += 1
        
        cursor.executemany("""
            INSERT INTO monthly_revenue (id, month, year, revenue, expenses, profit, region, category)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, monthly_revenue_data)
        
        self.conn.commit()
        
    def execute_query(self, query: str) -> List[sqlite3.Row]:
        """Execute a SELECT query and return results.
        
        Args:
            query: SQL query to execute
            
        Returns:
            List of result rows
        """
        cursor = self.conn.cursor()
        cursor.execute(query)
        return cursor.fetchall()
        
    def get_table_names(self) -> List[str]:
        """Get list of all table names in the database.
        
        Returns:
            List of table names
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' 
            ORDER BY name
        """)
        return [row[0] for row in cursor.fetchall()]
        
    def get_table_schema(self, table_name: str) -> List[Tuple[str, str]]:
        """Get schema information for a table.
        
        Args:
            table_name: Name of the table
            
        Returns:
            List of (column_name, data_type) tuples
        """
        cursor = self.conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name})")
        return [(row[1], row[2]) for row in cursor.fetchall()]
