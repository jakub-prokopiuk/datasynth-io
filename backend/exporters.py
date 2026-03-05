import sqlite3
import csv
import zipfile
import json
import os
from typing import List, Dict, Any

class DataExporter:
    @staticmethod
    def export_all(db_path: str, format_type: str, job_name: str, export_path: str):
        format_type = format_type.lower()
        
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
            tables = [r[0] for r in cursor.fetchall()]
            
            if format_type == "json":
                with open(export_path, 'w') as f:
                    f.write("{\n")
                    for i, table_name in enumerate(tables):
                        f.write(f'  "{table_name}": [\n')
                        cursor.execute(f'SELECT * FROM "{table_name}"')
                        headers = [d[0] for d in cursor.description] if cursor.description else []
                        headers = [h for h in headers if h != "_row_id"]
                        
                        first_row = True
                        while True:
                            rows = cursor.fetchmany(1000)
                            if not rows: break
                            for row in rows:
                                if not first_row: f.write(",\n")
                                first_row = False
                                row_dict = {h: row[h] for h in headers}
                                parsed_dict = {}
                                for k, v in row_dict.items():
                                    try: parsed_dict[k] = json.loads(v) if v and isinstance(v, str) and (v.startswith('{') or v.startswith('[')) else v
                                    except: parsed_dict[k] = v
                                f.write("    " + json.dumps(parsed_dict))
                        f.write("\n  ]")
                        if i < len(tables) - 1: f.write(",\n")
                        else: f.write("\n")
                    f.write("}\n")
                    
            elif format_type == "csv":
                with zipfile.ZipFile(export_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                    for table_name in tables:
                        cursor.execute(f'SELECT * FROM "{table_name}"')
                        headers = [d[0] for d in cursor.description] if cursor.description else []
                        headers = [h for h in headers if h != "_row_id"]
                        
                        csv_file_path = f"outputs/temp_{table_name}.csv"
                        with open(csv_file_path, "w", newline="") as f:
                            writer = csv.DictWriter(f, fieldnames=headers)
                            writer.writeheader()
                            while True:
                                rows = cursor.fetchmany(1000)
                                if not rows: break
                                for row in rows:
                                    writer.writerow({h: row[h] for h in headers})
                        
                        zipf.write(csv_file_path, f"{table_name}.csv")
                        os.remove(csv_file_path)

            elif format_type == "sql":
                with open(export_path, "w") as f:
                    for table_name in tables:
                        f.write(f"-- Table: {table_name}\n")
                        cursor.execute(f'SELECT * FROM "{table_name}"')
                        headers = [d[0] for d in cursor.description] if cursor.description else []
                        headers = [h for h in headers if h != "_row_id"]
                        columns = ", ".join([f'"{h}"' for h in headers])
                        
                        while True:
                            rows = cursor.fetchmany(1000)
                            if not rows: break
                            for row in rows:
                                values = []
                                for h in headers:
                                    val = row[h]
                                    if val is None:
                                        values.append("NULL")
                                    else:
                                        clean_val = str(val).replace("'", "''")
                                        values.append(f"'{clean_val}'")
                                value_str = ", ".join(values)
                                f.write(f'INSERT INTO "{table_name}" ({columns}) VALUES ({value_str});\n')
                        f.write("\n")