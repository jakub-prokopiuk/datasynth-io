from fastapi import FastAPI, HTTPException, Response, Depends, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import List, Union, Any
import uvicorn
import asyncio
import json
import uuid
import os
from dotenv import load_dotenv

from models import GeneratorRequest, ProjectCreate, ProjectSummary, PushToDbRequest
from db_connector import DatabaseConnector
from engine import DataEngine
from exporters import DataExporter
from database import init_db, get_db, ProjectDB, UserDB
from job_manager import job_manager
from tasks import generate_dataset_task

from auth import get_current_user, create_access_token, verify_password, get_password_hash

load_dotenv()


def create_default_user():
    db = next(get_db())
    user = db.query(UserDB).filter(UserDB.username == "admin").first()
    if not user:
        print("Creating default admin user...")
        hashed = get_password_hash("admin")
        db_user = UserDB(username="admin", hashed_password=hashed)
        db.add(db_user)
        db.commit()
    else:
        print("Admin user already exists.")

try:
    init_db()
    create_default_user()
except Exception as e:
    print(f"Warning: DB init failed: {e}")

app = FastAPI(title="LLM Data Generator API", version="0.6.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

data_engine = DataEngine()

@app.post("/token")
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(UserDB).filter(UserDB.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/")
def read_root():
    return {"status": "ok", "message": "API Running (Protected)"}


@app.post("/generate")
async def generate_data_sync(request: GeneratorRequest, user: dict = Depends(get_current_user)):
    raise HTTPException(status_code=400, detail="Synchronous dataset generation is deprecated. Use /generate/async.")

@app.post("/generate/async")
async def start_generation_job(request: GeneratorRequest, user: dict = Depends(get_current_user)):
    job_id = str(uuid.uuid4())
    job_manager.create_job(job_id, request.model_dump())
    task = generate_dataset_task.delay(job_id, request.model_dump_json())
    job_manager.set_celery_task_id(job_id, task.id)
    return {"job_id": job_id, "status": "queued"}


@app.websocket("/ws/jobs/{job_id}")
async def websocket_job_status(websocket: WebSocket, job_id: str):
    await websocket.accept()
    try:
        last_progress = -1
        last_status = ""
        while True:
            job = job_manager.get_job(job_id)
            if not job:
                await websocket.send_json({"status": "error", "message": "Job not found"})
                break
            status = job.get("status")
            progress = job.get("progress", 0)
            if progress != last_progress or status != last_status:
                response = {"job_id": job_id, "status": status, "progress": progress, "total_rows": job.get("total_rows", 0)}
                if status == "failed": response["error"] = job.get("error")
                await websocket.send_json(response)
                last_progress = progress
                last_status = status
            if status in ["completed", "failed"]: await websocket.close(); break
            await asyncio.sleep(0.5)
    except WebSocketDisconnect: pass
    except Exception as e:
        print(f"WS Error: {e}")
        try: await websocket.close() 
        except: pass

@app.get("/jobs/{job_id}/result")
def get_job_result(job_id: str, user: dict = Depends(get_current_user)):
    job = job_manager.get_job(job_id)
    if not job or job["status"] != "completed": raise HTTPException(status_code=400, detail="Job not ready")
    
    data_str = job["data"]
    try: result_info = json.loads(data_str)
    except: result_info = data_str if isinstance(data_str, dict) else {}
    
    db_path = result_info.get("db_path")
    if not db_path or not os.path.exists(db_path):
        raise HTTPException(status_code=404, detail="Database file missing")
        
    config = job.get("config", {})
    if "config" in config: config = config["config"]
    format_type = config.get("output_format", "json")
    
    preview_data = {}
    import sqlite3
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        tables = [r[0] for r in cursor.fetchall()]
        
        for t in tables:
            cursor.execute(f'SELECT * FROM "{t}" LIMIT 50')
            headers = [d[0] for d in cursor.description] if cursor.description else []
            headers = [h for h in headers if h != "_row_id"]
            rows = cursor.fetchall()
            parsed_rows = []
            for row in rows:
                r_dict = {}
                for h in headers:
                    v = row[h]
                    try: r_dict[h] = json.loads(v) if v and isinstance(v, str) and (v.startswith('{') or v.startswith('[')) else v
                    except: r_dict[h] = v
                parsed_rows.append(r_dict)
            preview_data[t] = parsed_rows

    total_rows = job.get("total_rows", 0)
    return {
        "status": "success", 
        "job_name": config.get("job_name", "dataset"),
        "tables_count": len(tables),
        "total_rows": total_rows,
        "data": preview_data,
        "preview": True
    }

from fastapi.responses import FileResponse

@app.get("/jobs/{job_id}/download")
def download_job_result(job_id: str, user: dict = Depends(get_current_user)):
    job = job_manager.get_job(job_id)
    if not job or job["status"] != "completed": raise HTTPException(status_code=400, detail="Job not ready")
    
    data_str = job["data"]
    try: result_info = json.loads(data_str)
    except: result_info = data_str if isinstance(data_str, dict) else {}
    
    export_path = result_info.get("export_path")
    if not export_path or not os.path.exists(export_path):
        raise HTTPException(status_code=404, detail="Export file missing")
        
    config = job.get("config", {})
    if "config" in config: config = config["config"]
    format_type = config.get("output_format", "json")
    job_name = config.get("job_name", "dataset").replace(" ", "_").lower()
    
    ext = "zip" if format_type == "csv" else format_type
    
    media_type = "application/json"
    if ext == "zip": media_type = "application/zip"
    elif ext == "sql": media_type = "application/sql"
    
    return FileResponse(
        path=export_path, 
        media_type=media_type, 
        filename=f"{job_name}.{ext}"
    )

@app.delete("/jobs/{job_id}")
def cancel_job_endpoint(job_id: str, user: dict = Depends(get_current_user)):
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    celery_task_id = job.get("celery_task_id")
    if celery_task_id:
        from celery_worker import celery_app
        celery_app.control.revoke(celery_task_id, terminate=True, signal='SIGTERM')
            
    job_manager.cancel_job(job_id)
    return {"status": "success", "message": "Job cancelled"}

@app.post("/projects", response_model=ProjectSummary)
def create_project(project: ProjectCreate, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    schema_json = project.schema_data.model_dump()
    db_project = ProjectDB(name=project.name, description=project.description, schema_data=schema_json)
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    return db_project

@app.get("/projects", response_model=List[ProjectSummary])
def list_projects(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    return db.query(ProjectDB).order_by(ProjectDB.updated_at.desc()).offset(skip).limit(limit).all()

@app.get("/projects/{project_id}", response_model=GeneratorRequest)
def get_project(project_id: int, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    db_project = db.query(ProjectDB).filter(ProjectDB.id == project_id).first()
    if not db_project: raise HTTPException(status_code=404, detail="Project not found")
    return db_project.schema_data

@app.delete("/projects/{project_id}")
def delete_project(project_id: int, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    db_project = db.query(ProjectDB).filter(ProjectDB.id == project_id).first()
    if not db_project: raise HTTPException(status_code=404, detail="Project not found")
    db.delete(db_project)
    db.commit()
    return {"status": "success", "message": "Project deleted"}

@app.post("/connectors/test")
def test_db_connection(payload: dict, user: dict = Depends(get_current_user)):
    conn_str = payload.get("connection_string")
    try: DatabaseConnector.test_connection(conn_str); return {"status": "success", "message": "OK"}
    except Exception as e: raise HTTPException(status_code=400, detail=str(e))

@app.post("/connectors/push")
async def push_to_database(payload: PushToDbRequest, user: dict = Depends(get_current_user)):
    job = job_manager.get_job(payload.job_id)
    if not job or job["status"] != "completed": raise HTTPException(status_code=400, detail="Job not completed")
    
    data_str = job["data"]
    try: result_info = json.loads(data_str)
    except: result_info = data_str if isinstance(data_str, dict) else {}
    db_path = result_info.get("db_path")
    
    if not db_path or not os.path.exists(db_path):
        raise HTTPException(status_code=404, detail="Database file missing. Cannot push.")
        
    try:
        await asyncio.to_thread(DatabaseConnector.push_data, payload.connection_string, db_path)
        return {"status": "success", "message": "Pushed"}
    except Exception as e: raise HTTPException(status_code=500, detail=f"Push failed: {str(e)}")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8001)