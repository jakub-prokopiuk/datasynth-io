import json
import redis
import os
from datetime import datetime

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

class RedisJobManager:
    def __init__(self):
        self.redis = redis.from_url(REDIS_URL, decode_responses=True)
        self.TTL = 3600 * 24

    def _get_key(self, job_id):
        return f"job:{job_id}"

    def create_job(self, job_id, config):
        job_data = {
            "id": job_id,
            "status": "pending",
            "progress": 0,
            "total_rows": 0,
            "created_at": datetime.now().isoformat(),
            "config": json.dumps(config),
            "data": "",
            "error": ""
        }
        
        self.redis.hset(self._get_key(job_id), mapping=job_data)
        self.redis.expire(self._get_key(job_id), self.TTL)
        return job_data

    def get_job(self, job_id):
        data = self.redis.hgetall(self._get_key(job_id))
        if not data:
            return None
        
        try:
            if "config" in data and data["config"]: 
                data["config"] = json.loads(data["config"])
            
            if "data" in data and data["data"]:
                data["data"] = json.loads(data["data"])
            else:
                data["data"] = None

            if "progress" in data: data["progress"] = int(data["progress"])
            if "total_rows" in data: data["total_rows"] = int(data["total_rows"])
        except Exception as e:
            print(f"Error decoding job data: {e}")
            
        return data

    def update_progress(self, job_id, progress):
        self.redis.hset(self._get_key(job_id), key="progress", value=progress)

    def set_total(self, job_id, total):
        self.redis.hset(self._get_key(job_id), key="total_rows", value=total)

    def complete_job(self, job_id, result_data):
        self.redis.hset(self._get_key(job_id), mapping={
            "status": "completed",
            "progress": 100,
            "data": json.dumps(result_data)
        })

    def cancel_job(self, job_id):
        self.redis.hset(self._get_key(job_id), mapping={
            "status": "cancelled"
        })

    def fail_job(self, job_id, error_msg):
        status = self.redis.hget(self._get_key(job_id), "status")
        if status == "cancelled":
            return
            
        self.redis.hset(self._get_key(job_id), mapping={
            "status": "failed",
            "error": str(error_msg)
        })
        
    async def check_cancellation(self, job_id):
        status = self.redis.hget(self._get_key(job_id), "status")
        if status == "cancelled":
            raise Exception("Job was cancelled by the user.")

job_manager = RedisJobManager()