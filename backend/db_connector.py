from sqlalchemy import create_engine, text
import pandas as pd
from typing import Dict, List, Any

class DatabaseConnector:
    @staticmethod
    def test_connection(connection_string: str) -> bool:
        try:
            engine = create_engine(connection_string)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception as e:
            raise Exception(f"Connection failed: {str(e)}")

    @staticmethod
    def push_data(connection_string: str, db_path: str):
        engine = create_engine(connection_string)
        import sqlite3
        with sqlite3.connect(db_path) as sqlite_conn:
            cursor = sqlite_conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
            tables = [r[0] for r in cursor.fetchall()]
            
            with engine.begin() as connection:
                for table_name in tables:
                    first_chunk = True
                    for chunk_df in pd.read_sql(f'SELECT * FROM "{table_name}"', sqlite_conn, chunksize=5000):
                        if "_row_id" in chunk_df.columns:
                            chunk_df = chunk_df.drop(columns=["_row_id"])
                            
                        import json
                        for col in chunk_df.columns:
                            def attempt_json(x):
                                if isinstance(x, str) and (x.startswith('{') or x.startswith('[')):
                                    try: return json.loads(x)
                                    except: return x
                                return x
                            chunk_df[col] = chunk_df[col].apply(attempt_json)
                        
                        chunk_df.to_sql(
                            name=table_name,
                            con=connection,
                            if_exists='replace' if first_chunk else 'append', 
                            index=False
                        )
                        first_chunk = False