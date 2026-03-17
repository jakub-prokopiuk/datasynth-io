import asyncio
import argparse
import json
import os
import aiosqlite
import csv
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
    
    # Optional: If running on Kaggle with HuggingFace instead of Ollama,
    # you could override the base URL here if needed. By default, it looks for Ollama on localhost.
    
    print("Starting generation...")
    # This will create outputs/{job_id}.db
    db_path = await engine.generate(request, job_id=args.job_id)
    print(f"Generation complete! Database saved to {db_path}")

    if args.export_csv:
        output_dir = f"outputs/{args.job_id}_csv"
        await export_sqlite_to_csv(db_path, output_dir)
        print(f"All CSVs exported to {output_dir}")

if __name__ == "__main__":
    asyncio.run(main())
