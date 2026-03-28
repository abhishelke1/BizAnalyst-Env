from environment.database import DatabaseManager, get_reference_date

db = DatabaseManager()
db.connect()
db.create_schema()
db.seed_data()

# Check the planted churn customers
query = """
SELECT customer_id, name, last_order_date,
       CAST(julianday('2024-06-01') - julianday(last_order_date) AS INTEGER) as days
FROM customers
WHERE customer_id IN (7, 23, 89)
"""
results = db.execute_query(query)
print('Planted churn customers (should be 150, 135, 120 days):')
for r in results:
    print(f'  ID {r[0]}: {r[1]} - Last order: {r[2]} - Days since: {r[3]}')

db.close()
