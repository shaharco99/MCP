"""
Database query tools for the LLM agent.
Allows the agent to generate and execute SQL queries based on user questions.
"""
from __future__ import annotations

import json
import os
from typing import Dict, List, Optional, Any, Tuple

from langchain.tools import tool

# Database connection pooling and management
_db_connection = None
_db_config = None


def load_db_config(config_file: Optional[str] = None) -> Dict[str, Any]:
    """
    Load database configuration from JSON file or environment variables.
    
    Args:
        config_file: Path to database config JSON file
        
    Returns:
        Dictionary with database configuration
    """
    global _db_config
    
    if _db_config:
        return _db_config
    
    # Try to load from file first
    if config_file is None:
        config_file = os.getenv('DB_CONFIG_FILE', 'db_config.json')
    
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                _db_config = json.load(f)
                return _db_config
        except Exception as e:
            print(f"Warning: Could not load db_config from file: {e}")
    
    # Fall back to environment variables
    db_type = os.getenv('DB_TYPE', 'sqlite').lower()
    
    if db_type == 'sqlite':
        _db_config = {
            'type': 'sqlite',
            'database': os.getenv('DB_PATH', 'sample_database.db')
        }
    elif db_type == 'postgresql':
        _db_config = {
            'type': 'postgresql',
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': int(os.getenv('DB_PORT', 5432)),
            'user': os.getenv('DB_USER', 'postgres'),
            'password': os.getenv('DB_PASSWORD', ''),
            'database': os.getenv('DB_NAME', 'postgres')
        }
    elif db_type == 'mysql':
        _db_config = {
            'type': 'mysql',
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': int(os.getenv('DB_PORT', 3306)),
            'user': os.getenv('DB_USER', 'root'),
            'password': os.getenv('DB_PASSWORD', ''),
            'database': os.getenv('DB_NAME', 'mysql')
        }
    elif db_type == 'mssql':
        _db_config = {
            'type': 'mssql',
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': int(os.getenv('DB_PORT', 1433)),
            'user': os.getenv('DB_USER', 'sa'),
            'password': os.getenv('DB_PASSWORD', ''),
            'database': os.getenv('DB_NAME', 'master'),
            'driver': os.getenv('DB_DRIVER', 'ODBC Driver 17 for SQL Server')
        }
    else:
        raise ValueError(f"Unsupported database type: {db_type}")
    
    return _db_config


def get_db_connection():
    """
    Get or create a database connection.
    For SQLite, creates a fresh connection each time (thread-safe).
    For other databases, reuses the cached connection.
    
    Returns:
        Database connection object
    """
    global _db_connection
    
    config = load_db_config()
    db_type = config.get('type', 'sqlite').lower()
    
    # For SQLite, create a fresh connection each time to handle threading
    if db_type == 'sqlite':
        import sqlite3
        try:
            conn = sqlite3.connect(config['database'], check_same_thread=False)
            conn.row_factory = sqlite3.Row
            return conn
        except Exception as e:
            raise ConnectionError(f"Failed to connect to SQLite database: {e}")
    
    # For other databases, use connection pooling
    if _db_connection is not None:
        return _db_connection
    
    try:
        if db_type == 'postgresql':
            import psycopg2
            _db_connection = psycopg2.connect(
                host=config['host'],
                port=config['port'],
                user=config['user'],
                password=config['password'],
                database=config['database']
            )
        elif db_type == 'mysql':
            import mysql.connector
            _db_connection = mysql.connector.connect(
                host=config['host'],
                port=config['port'],
                user=config['user'],
                password=config['password'],
                database=config['database']
            )
        elif db_type == 'mssql':
            import pyodbc
            connection_string = (
                f"Driver={{{config['driver']}}};"
                f"Server={config['host']},{config['port']};"
                f"Database={config['database']};"
                f"UID={config['user']};"
                f"PWD={config['password']};"
            )
            _db_connection = pyodbc.connect(connection_string, autocommit=False)
    except ImportError as e:
        raise ImportError(f"Database driver not installed: {e}. Please install the appropriate Python package.")
    except Exception as e:
        raise ConnectionError(f"Failed to connect to {db_type} database: {e}")
    
    return _db_connection


def execute_query(query: str) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """
    Execute a SQL query and return results.
    
    Args:
        query: SQL query string
        
    Returns:
        Tuple of (results list, error message if any)
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(query)
        
        # For SELECT queries
        if query.strip().upper().startswith('SELECT'):
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            rows = cursor.fetchall()
            results = []
            
            # Convert rows to dictionaries
            db_type = load_db_config().get('type', 'sqlite').lower()
            if db_type == 'sqlite':
                results = [dict(row) for row in rows]
            else:
                results = [dict(zip(columns, row)) for row in rows]
            
            return results, None
        else:
            # For INSERT, UPDATE, DELETE queries
            conn.commit()
            return [{'affected_rows': cursor.rowcount}], None
    
    except Exception as e:
        return [], str(e)


def close_db_connection():
    """Close the database connection."""
    global _db_connection
    if _db_connection:
        try:
            _db_connection.close()
        except Exception:
            pass
        _db_connection = None


@tool
def generate_and_preview_query(
    user_question: str,
    database_schema: Optional[str] = None
) -> str:
    """
    Generate a SQL query based on a user's question and preview it without executing.
    The agent will use this to show the user the query before execution.

    Args:
        user_question: The user's natural language question about the database
        database_schema: Optional schema description of available tables

    Returns:
        A suggested SQL query that can be reviewed before execution
    """
    # This tool returns a query for review - the actual execution
    # will be handled by execute_database_query after user confirmation

    if not database_schema:
        # Try to get schema from database (return a short, informative string)
        try:
            config = load_db_config()
            db_type = config.get('type', 'sqlite').lower()
            query = None
            if db_type == 'sqlite':
                query = "SELECT name FROM sqlite_master WHERE type='table';"
            elif db_type == 'postgresql':
                query = "SELECT table_name FROM information_schema.tables WHERE table_schema='public';"
            elif db_type == 'mysql':
                query = f"SELECT table_name FROM information_schema.tables WHERE table_schema='{config['database']}';"
            elif db_type == 'mssql':
                # MSSQL: list user tables from INFORMATION_SCHEMA
                query = (
                    f"SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES "
                    f"WHERE TABLE_TYPE='BASE TABLE' AND TABLE_CATALOG='{config.get('database','')}'"
                )

            if query:
                results, error = execute_query(query)
                if error:
                    database_schema = f"Unable to retrieve schema: {error}"
                elif not results:
                    database_schema = "No tables found in database"
                else:
                    tables = []
                    for r in results:
                        # r may be dict-like or sequence depending on driver
                        if isinstance(r, dict):
                            val = next(iter(r.values()))
                        elif isinstance(r, (list, tuple)):
                            val = r[0]
                        else:
                            try:
                                val = str(r)
                            except Exception:
                                val = "<unknown>"
                        tables.append(str(val))
                    database_schema = "Available tables: " + ", ".join(tables)
            else:
                database_schema = f"Schema not available for database type: {db_type}"
        except Exception as e:
            database_schema = f"Unable to retrieve schema: {e}"

    # Ensure database_schema is at least an informative string
    if database_schema is None :
        database_schema = "Database schema not provided and automatic retrieval failed."

    return (
        f"Based on the question: '{user_question}'\n\n"
        f"Database Schema: {database_schema}\n\n"
        f"Please construct an appropriate SQL query. You should return the complete SQL query "
        f"that would answer this question. The user will review and confirm before execution.\n\n"
        f"IMPORTANT: Always wrap your final SQL query in this format:\n"
        f"<sql_query>\nSELECT ... FROM ... WHERE ...\n</sql_query>"
    )


@tool
def execute_database_query(sql_query: str) -> str:
    """
    Execute a SQL query against the database and return results.
    
    IMPORTANT: This should only be called AFTER the user has reviewed and approved the query.
    The agent should ALWAYS preview the query first using generate_and_preview_query.
    
    Args:
        sql_query: The SQL query to execute
        
    Returns:
        JSON string containing query results or error message
    """
    # Validate query safety - prevent dangerous operations
    dangerous_keywords = ['DROP', 'TRUNCATE', 'DELETE', 'ALTER', 'CREATE', 'MODIFY']
    query_upper = sql_query.strip().upper()
    
    for keyword in dangerous_keywords:
        if query_upper.startswith(keyword):
            return json.dumps({
                'error': f"Query execution blocked: {keyword} operations are not allowed for safety reasons. "
                         f"Please contact an administrator if you need to perform this operation.",
                'query': sql_query
            })
    
    # Basic SQL injection prevention - check for common patterns
    if any(char in sql_query for char in [';--', '/*', '*/', 'xp_', 'sp_']):
        return json.dumps({
            'error': 'Query blocked: Potential SQL injection detected',
            'query': sql_query
        })
    
    try:
        results, error = execute_query(sql_query)
        
        if error:
            return json.dumps({
                'error': error,
                'query': sql_query,
                'results': []
            })
        
        return json.dumps({
            'success': True,
            'query': sql_query,
            'row_count': len(results),
            'results': results
        })
    
    except Exception as e:
        return json.dumps({
            'error': str(e),
            'query': sql_query,
            'results': []
        })


@tool
def get_database_schema() -> str:
    """
    Retrieve the complete schema of the connected database.
    Shows all tables and their column information.
    
    Returns:
        Formatted string containing database schema information
    """
    try:
        config = load_db_config()
        db_type = config.get('type', 'sqlite').lower()
        
        if db_type == 'sqlite':
            results, error = execute_query("SELECT name FROM sqlite_master WHERE type='table';")
            if error:
                return f"Error retrieving tables: {error}"
            
            schema_info = []
            for table in results:
                table_name = table['name']
                cols, _ = execute_query(f"PRAGMA table_info({table_name});")
                col_info = ", ".join([f"{col['name']} ({col['type']})" for col in cols])
                schema_info.append(f"Table '{table_name}': {col_info}")
            
            return "\n".join(schema_info) if schema_info else "No tables found in database"
        
        elif db_type == 'postgresql':
            query = """
            SELECT table_name, column_name, data_type 
            FROM information_schema.columns 
            WHERE table_schema = 'public'
            ORDER BY table_name, ordinal_position;
            """
            results, error = execute_query(query)
            if error:
                return f"Error retrieving schema: {error}"
            
            schema_dict = {}
            for row in results:
                table = row['table_name']
                if table not in schema_dict:
                    schema_dict[table] = []
                schema_dict[table].append(f"{row['column_name']} ({row['data_type']})")
            
            schema_info = [f"Table '{t}': {', '.join(cols)}" for t, cols in schema_dict.items()]
            return "\n".join(schema_info)
        
        elif db_type == 'mysql':
            query = f"SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA = '{config['database']}'"
            results, error = execute_query(query)
            if error:
                return f"Error retrieving tables: {error}"
            
            schema_info = []
            for table in results:
                table_name = table[list(table.keys())[0]]
                cols, _ = execute_query(f"DESCRIBE {table_name}")
                col_info = ", ".join([f"{col['Field']} ({col['Type']})" for col in cols])
                schema_info.append(f"Table '{table_name}': {col_info}")
            
            return "\n".join(schema_info) if schema_info else "No tables found in database"
        
        elif db_type == 'mssql':
            query = """
            SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_CATALOG = ?
            ORDER BY TABLE_NAME, ORDINAL_POSITION;
            """
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(query, (config['database'],))
            
            schema_dict = {}
            for row in cursor.fetchall():
                table = row[0]
                if table not in schema_dict:
                    schema_dict[table] = []
                schema_dict[table].append(f"{row[1]} ({row[2]})")
            
            schema_info = [f"Table '{t}': {', '.join(cols)}" for t, cols in schema_dict.items()]
            return "\n".join(schema_info) if schema_info else "No tables found in database"
    
    except Exception as e:
        return f"Error retrieving database schema: {e}"
