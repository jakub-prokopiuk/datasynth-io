import asyncio
from celery_worker import celery_app
from engine import DataEngine
from models import GeneratorRequest
from job_manager import job_manager
import json
from exporters import DataExporter

@celery_app.task(bind=True, name="generate_dataset_task")
def generate_dataset_task(self, job_id: str, request_json: str):
    try:
        req_dict = json.loads(request_json)
        request = GeneratorRequest(**req_dict)
        
        engine = DataEngine()
        
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        db_path = loop.run_until_complete(engine.generate(request, job_id))
        
        config = req_dict.get("config", {})
        format_type = config.get("output_format", "json")
        job_name = config.get("job_name", "dataset").replace(" ", "_").lower()
        
        ext = "zip" if format_type == "csv" else format_type
        export_path = f"outputs/{job_id}_export.{ext}"
        
        DataExporter.export_all(db_path, format_type, job_name, export_path)
        
        job_manager.complete_job(job_id, {"db_path": db_path, "export_path": export_path})
        
        return {"status": "success", "job_id": job_id}

    except Exception as e:
        print(f"CRITICAL WORKER ERROR: {e}")
        job_manager.fail_job(job_id, str(e))
        raise e