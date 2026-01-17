"""
Database Initialization
Runs all schema files to set up tables on Railway PostgreSQL
"""

import os
import logging
import psycopg2
from pathlib import Path

logger = logging.getLogger(__name__)


def get_database_url():
    """Get database URL from environment"""
    return os.getenv('DATABASE_URL') or os.getenv('POSTGRES_URL')


def init_database():
    """
    Initialize database by running all schema files
    
    This is idempotent - safe to run multiple times
    All tables use CREATE TABLE IF NOT EXISTS
    """
    db_url = get_database_url()
    
    if not db_url:
        logger.warning("No DATABASE_URL found - skipping database initialization")
        return False
    
    try:
        logger.info("Initializing Railway PostgreSQL database...")
        
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor()
        
        # Get directory where this script is located
        db_dir = Path(__file__).parent
        
        # Schema files in order
        schema_files = [
            'user_profiles_schema.sql',
            'scheduling_schema.sql',
            'reminders_schema.sql'
        ]
        
        for schema_file in schema_files:
            schema_path = db_dir / schema_file
            
            if not schema_path.exists():
                logger.warning(f"Schema file not found: {schema_file}")
                continue
            
            logger.info(f"Running schema: {schema_file}")
            
            with open(schema_path, 'r') as f:
                schema_sql = f.read()
            
            try:
                cursor.execute(schema_sql)
                conn.commit()
                logger.info(f"✓ {schema_file} executed successfully")
            except Exception as e:
                logger.error(f"Error executing {schema_file}: {e}")
                conn.rollback()
                # Continue with other schemas even if one fails
                continue
        
        cursor.close()
        conn.close()
        
        logger.info("✓ Database initialization complete")
        return True
    
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        return False


if __name__ == "__main__":
    # Can be run standalone for testing
    logging.basicConfig(level=logging.INFO)
    success = init_database()
    exit(0 if success else 1)
