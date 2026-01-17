"""
Database Connection Utility
Provides connection management for Railway PostgreSQL
"""

import os
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from typing import Optional

logger = logging.getLogger(__name__)


def get_database_url() -> Optional[str]:
    """
    Get database URL from environment variables
    
    Railway provides DATABASE_URL or POSTGRES_URL
    Returns None if not configured
    """
    return os.getenv('DATABASE_URL') or os.getenv('POSTGRES_URL')


def has_database() -> bool:
    """Check if database is configured"""
    return get_database_url() is not None


@contextmanager
def get_db_connection():
    """
    Get database connection with automatic cleanup and transaction management
    
    Usage:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM table")
            result = cursor.fetchall()
    
    Automatically commits on success, rollback on exception
    """
    db_url = get_database_url()
    
    if not db_url:
        raise ValueError("DATABASE_URL not configured. Set DATABASE_URL or POSTGRES_URL environment variable.")
    
    conn = None
    try:
        conn = psycopg2.connect(db_url, cursor_factory=RealDictCursor)
        yield conn
        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        if conn:
            conn.close()


@contextmanager
def get_db_cursor():
    """
    Get database cursor directly
    
    Usage:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT * FROM table")
            result = cursor.fetchall()
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            yield cursor
        finally:
            cursor.close()
