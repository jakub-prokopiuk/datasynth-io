import asyncio
import argparse
import json
import os
import aiosqlite
import csv
import time
from engine import DataEngine
from models import GeneratorRequest

async def export_sqlite_to_csv(db_path: str, output_dir: str):
    """Exports all tables from the given SQLite databse to CSV files."""
    print(f"Exporting data from {db_path} to CSV...")
    os.makedirs(output_dir, exist_ok=True)
    
    async with aiosqlite.connect(db_path) as db:
        async with db.execute("SELECT name FROM sqlite_master WHERE type='table'") as cursor:
            tables = [row[0] for row in await cursor.fetchall() if not row[0].startswith('sqlite_')]
            
        for table in tables:
            csv_path = os.path.join(output_dir, f"{table}.csv")
            async with db.execute(f'SELECT * FROM "{table}"') as cursor:
                columns = [description[0] for description in cursor.description]
                rows = await cursor.fetchall()
                
                with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(columns)
                    writer.writerows(rows)
            print(f" -> Exported {len(rows)} rows to {csv_path}")

async def main():
    parser = argparse.ArgumentParser(description="Run DataSynth LLM Generation standalone (useful for Kaggle)")
    parser.add_argument("schema_file", help="Path to the JSON schema file")
    parser.add_argument("--job-id", default=None, help="Optional job ID used for output files. Leave empty to skip Redis logging.")
    parser.add_argument("--export-csv", action="store_true", help="Export SQLite DB to CSV files after generation")
    args = parser.parse_args()

    print(f"Loading schema from {args.schema_file}...")
    with open(args.schema_file, "r", encoding="utf-8") as f:
        schema_data = json.load(f)
    
    request = GeneratorRequest(**schema_data)
    engine = DataEngine()
    
    print("Starting generation...")
    start_time = time.time()
    db_path = await engine.generate(request, job_id=args.job_id)
    total_time = time.time() - start_time
    
    print(f"Generation complete in {total_time:.2f} seconds! Database saved to {db_path}")

    time_log_path = f"outputs/generation_times_{args.job_id or 'kaggle'}.txt"
    with open(time_log_path, "w", encoding="utf-8") as f:
        f.write(f"Total Generation Time: {total_time:.2f} seconds\n")
        
        total_rows = sum(t.rows_count for t in request.tables)
        f.write(f"Total Rows Generated (all tables): {total_rows}\n")
        
        # Calculate time per LLM row (rough estimate if there's only one LLM table)
        llm_rows = 0
        for table in request.tables:
            if any(field.type == 'llm' for field in table.fields):
                llm_rows += table.rows_count
        
        if llm_rows > 0:
            f.write(f"LLM Rows: {llm_rows}\n")
            f.write(f"Average Time per LLM Row: {total_time / llm_rows:.2f} seconds\n")
            f.write(f"SUB_BATCH_SIZE used: {os.environ.get('OLLAMA_SUB_BATCH_SIZE', '25 (default)')}\n")
            f.write(f"MAX_CONCURRENT used: {os.environ.get('OLLAMA_MAX_CONCURRENT', '8 (default)')}\n")
            
    print(f"Timing results saved to {time_log_path}")

    if args.export_csv:
        output_dir = f"outputs/{args.job_id or 'kaggle'}_csv"
        await export_sqlite_to_csv(db_path, output_dir)
        print(f"All CSVs exported to {output_dir}")

if __name__ == "__main__":
    asyncio.run(main())
