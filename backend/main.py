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

def format_generation_output(data: dict, config) -> Any:
    format_type = config.output_format.lower()
    if format_type == "json":
        total_rows = sum(len(rows) for rows in data.values())
        return {"status": "success", "job_name": config.job_name, "tables_count": len(data), "total_rows": total_rows, "data": data}
    elif format_type == "csv": return DataExporter.to_csv_zip(data)
    elif format_type == "sql": return DataExporter.to_sql(data)
    else: raise ValueError("Unsupported output format")

def create_file_response(content: Union[str, bytes], config) -> Response:
    format_type = config.output_format.lower()
    if format_type == "csv":
        return Response(content=content, media_type="application/zip", headers={"Content-Disposition": f"attachment; filename={config.job_name}.zip"})
    elif format_type == "sql":
        file_name = config.job_name.replace(" ", "_").lower()
        return Response(content=content, media_type="application/sql", headers={"Content-Disposition": f"attachment; filename={file_name}.sql"})
    return content

@app.post("/generate")
async def generate_data_sync(request: GeneratorRequest, user: dict = Depends(get_current_user)):
    try:
        raw_data = await data_engine.generate(request)
        formatted_output = format_generation_output(raw_data, request.config)
        if request.config.output_format.lower() == "json": return formatted_output
        else: return create_file_response(formatted_output, request.config)
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate/async")
async def start_generation_job(request: GeneratorRequest, user: dict = Depends(get_current_user)):
    job_id = str(uuid.uuid4())
    job_manager.create_job(job_id, request.model_dump())
    generate_dataset_task.delay(job_id, request.model_dump_json())
    return {"job_id": job_id, "status": "queued"}


@app.websocket("/ws/jobs/{job_id}")
async def websocket_job_status(websocket: WebSocket, job_id: str):
    await websocket.accept()
    try:
        last_progress = -1
        while True:
            job = job_manager.get_job(job_id)
            if not job:
                await websocket.send_json({"status": "error", "message": "Job not found"})
                break
            status = job.get("status")
            progress = job.get("progress", 0)
            if progress != last_progress or status in ["completed", "failed"]:
                response = {"job_id": job_id, "status": status, "progress": progress, "total_rows": job.get("total_rows", 0)}
                if status == "failed": response["error"] = job.get("error")
                await websocket.send_json(response)
                last_progress = progress
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
    raw_data = job["data"]
    config_dict = job.get("config", {})
    if "config" in config_dict: config_dict = config_dict["config"]
    class ConfigShim:
        def __init__(self, d):
            self.output_format = d.get("output_format", "json")
            self.job_name = d.get("job_name", "dataset")
    config = ConfigShim(config_dict)
    formatted_output = format_generation_output(raw_data, config)
    if config.output_format == "json": return formatted_output
    else: return create_file_response(formatted_output, config)

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
    raw_data = job["data"]
    try:
        await asyncio.to_thread(DatabaseConnector.push_data, payload.connection_string, raw_data)
        return {"status": "success", "message": "Pushed"}
    except Exception as e: raise HTTPException(status_code=500, detail=f"Push failed: {str(e)}")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8001)