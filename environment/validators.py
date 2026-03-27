import re
from typing import Tuple


def validate_sql_query(query: str) -> Tuple[bool, str]:
    """
    Validate that a SQL query is safe to execute.
    Only SELECT queries are allowed.
    
    Args:
        query: The SQL query to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not query or not query.strip():
        return False, "Query cannot be empty"
    
    query_upper = query.upper()
    
    # List of disallowed SQL keywords
    disallowed_keywords = [
        'DROP', 'DELETE', 'INSERT', 'UPDATE', 'CREATE', 
        'ALTER', 'EXEC', 'EXECUTE', 'TRUNCATE', 'GRANT',
        'REVOKE', 'COMMIT', 'ROLLBACK', 'SAVEPOINT'
    ]
    
    # Check for disallowed keywords
    for keyword in disallowed_keywords:
        # Use word boundary to avoid false positives
        pattern = r'\b' + keyword + r'\b'
        if re.search(pattern, query_upper):
            return False, "Only SELECT queries are allowed."
    
    # Check for SQL comments which could be used to bypass security
    if '--' in query or '/*' in query or '*/' in query:
        return False, "Only SELECT queries are allowed."
    
    # Check if query contains SELECT
    if 'SELECT' not in query_upper:
        return False, "Only SELECT queries are allowed."
    
    return True, ""
