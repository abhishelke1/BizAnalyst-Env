import sqlite3
from datetime import datetime, timedelta
from typing import List, Tuple
import os


def get_northwind_path() -> str:
    """Find the northwind.db file in multiple possible locations.
    
    Returns:
        Path to northwind.db
        
    Raises:
        FileNotFoundError: If database not found in any location
    """
    # Possible locations to check
    current_dir = os.path.dirname(os.path.abspath(__file__))
    possible_paths = [
        os.path.join(os.path.dirname(current_dir), 'northwind.db'),  # ../northwind.db (relative to environment/)
        '/app/northwind.db',  # Docker container path
        os.path.join(current_dir, '..', 'northwind.db'),  # Alternative relative
        'northwind.db',  # Current working directory
        os.path.join(os.getcwd(), 'northwind.db'),  # Explicit cwd
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return os.path.abspath(path)
    
    # If not found, raise with helpful message
    raise FileNotFoundError(
        f"Northwind database not found. Searched: {possible_paths}. "
        f"Current dir: {current_dir}, CWD: {os.getcwd()}"
    )


def get_reference_date() -> str:
    """Return the fixed reference date used for all date calculations.
    
    Returns:
        Fixed reference date string in 'YYYY-MM-DD' format
    """
    return '2024-06-01'


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
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
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
        """Seed database with real data from Northwind database."""
        from .northwind_adapter import NorthwindAdapter
        from .anomaly_planter import AnomalyPlanter
        
        cursor = self.conn.cursor()
        
        # Find Northwind database using robust path detection
        northwind_path = get_northwind_path()
        
        # Initialize adapter
        adapter = NorthwindAdapter(northwind_path)
        
        # 1. Load customers from Northwind
        print("Loading customers from Northwind...")
        customers_data = adapter.load_customers()
        
        cursor.executemany("""
            INSERT INTO customers (customer_id, name, region, segment, signup_date, 
                                  last_order_date, total_spent, order_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, customers_data)
        print(f"Loaded {len(customers_data)} customers")
        
        # 2. Load products from Northwind
        print("Loading products from Northwind...")
        products_data = adapter.load_products()
        
        cursor.executemany("""
            INSERT INTO products (product_id, name, category, unit_price, cost_price, stock_quantity)
            VALUES (?, ?, ?, ?, ?, ?)
        """, products_data)
        print(f"Loaded {len(products_data)} products")
        
        # 3. Load orders and order items from Northwind
        print("Loading orders and order items from Northwind...")
        orders_data, order_items_data, customer_id_map = adapter.load_orders_and_items()
        
        cursor.executemany("""
            INSERT INTO orders (order_id, customer_id, order_date, status, total_amount, discount_pct)
            VALUES (?, ?, ?, ?, ?, ?)
        """, orders_data)
        print(f"Loaded {len(orders_data)} orders")
        
        cursor.executemany("""
            INSERT INTO order_items (item_id, order_id, product_id, quantity, unit_price)
            VALUES (?, ?, ?, ?, ?)
        """, order_items_data)
        print(f"Loaded {len(order_items_data)} order items")
        
        # 4. Update customer aggregates from orders
        print("Calculating customer aggregates...")
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
        
        # 5. Calculate monthly revenue aggregations
        print("Calculating monthly revenue aggregations...")
        monthly_revenue_data = adapter.calculate_monthly_revenue(
            orders_data, customers_data, order_items_data, products_data
        )
        
        if monthly_revenue_data:
            cursor.executemany("""
                INSERT INTO monthly_revenue (id, month, year, revenue, expenses, profit, region, category)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, monthly_revenue_data)
            print(f"Loaded {len(monthly_revenue_data)} monthly revenue records")
        
        self.conn.commit()
        
        # 6. Plant anomalies for testing
        print("\nPlanting anomalies for testing tasks...")
        planter = AnomalyPlanter(self.conn)
        planter.plant_all_anomalies()
        
        # 7. Verify anomalies
        planter.verify_anomalies()
        
        print("[SUCCESS] Data seeding complete!")
        
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
