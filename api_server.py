#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
FastAPI server for OpenEnv API compliance.
Exposes /reset, /step, /state endpoints for the competition platform.
"""
import os
import yaml
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Dict, Any, Optional

from env.scheduler_env import SchedulerEnv
from env.models import Action, Observation, EnvironmentState
from optimizer.greedy import GreedyOptimizer

# ─────────────────────────────────────────────
# FastAPI app
# ─────────────────────────────────────────────
app = FastAPI(
    title="Carbon-Aware Cloud Workload Scheduler",
    description="OpenEnv-compliant API for carbon-aware job scheduling",
    version="1.0.0"
)

# Global environment instance
env_instance: Optional[SchedulerEnv] = None
current_task: str = "medium"

# ─────────────────────────────────────────────
# Request/Response models
# ─────────────────────────────────────────────
class ResetRequest(BaseModel):
    task: Optional[str] = "medium"
    seed: Optional[int] = None
    config: Optional[Dict[str, Any]] = None

class StepRequest(BaseModel):
    action: Dict[str, Any]

# ─────────────────────────────────────────────
# Helper functions
# ─────────────────────────────────────────────
def load_task_config(task_name: str) -> Dict[str, Any]:
    """Load task configuration from openenv.yaml"""
    with open("openenv.yaml") as f:
        cfg = yaml.safe_load(f)
    if task_name not in cfg["tasks"]:
        raise ValueError(f"Task '{task_name}' not found in openenv.yaml")
    return cfg["tasks"][task_name]["config"]

def observation_to_dict(obs: Observation) -> Dict[str, Any]:
    """Convert Observation to JSON-serializable dict"""
    return {
        "jobs": [
            {
                "id": job.id,
                "duration": job.duration,
                "deadline": job.deadline,
                "priority": job.priority
            }
            for job in obs.jobs
        ],
        "carbon_intensity": obs.carbon_intensity,
        "capacity": obs.capacity,
        "time_horizon": obs.time_horizon
    }

def state_to_dict(state: EnvironmentState) -> Dict[str, Any]:
    """Convert EnvironmentState to JSON-serializable dict"""
    return {
        "jobs": [
            {
                "id": job.id,
                "duration": job.duration,
                "deadline": job.deadline,
                "priority": job.priority
            }
            for job in state.jobs
        ],
        "carbon_intensity": state.carbon_intensity,
        "capacity": state.capacity,
        "time_horizon": state.time_horizon,
        "current_schedule": {
            "schedule": [
                {"job_id": item.job_id, "start_time": item.start_time}
                for item in state.current_schedule.schedule
            ]
        } if state.current_schedule else None,
        "episode_step": state.episode_step,
        "done": state.done
    }

# ─────────────────────────────────────────────
# API Endpoints
# ─────────────────────────────────────────────
@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "running",
        "environment": "Carbon-Aware Cloud Workload Scheduler",
        "version": "1.0.0",
        "openenv_compliant": True
    }

@app.post("/reset")
async def reset(request: ResetRequest = None):
    """
    Reset the environment and return initial observation.
    
    POST /reset
    Body: {"task": "easy|medium|hard", "seed": 42, "config": {...}}
    """
    global env_instance, current_task
    
    try:
        # Parse request
        if request is None:
            request = ResetRequest()
        
        task_name = request.task or "medium"
        seed = request.seed
        config = request.config
        
        # Load config if not provided
        if config is None:
            config = load_task_config(task_name)
        
        # Create environment
        env_instance = SchedulerEnv(
            config=config,
            seed=seed,
            use_real_carbon=False  # Use synthetic for determinism
        )
        current_task = task_name
        
        # Reset and get observation
        obs = env_instance.reset()
        
        return JSONResponse(
            status_code=200,
            content={
                "observation": observation_to_dict(obs),
                "task": task_name,
                "seed": seed
            }
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/step")
async def step(request: StepRequest):
    """
    Execute an action and return observation, reward, done, info.
    
    POST /step
    Body: {"action": {"schedule": [{"job_id": 1, "start_time": 5}, ...]}}
    """
    global env_instance
    
    if env_instance is None:
        raise HTTPException(
            status_code=400,
            detail="Environment not initialized. Call /reset first."
        )
    
    try:
        # Parse action
        action = Action(**request.action)
        
        # Execute step
        obs, reward, done, info = env_instance.step(action)
        
        return JSONResponse(
            status_code=200,
            content={
                "observation": observation_to_dict(obs),
                "reward": reward.total,
                "reward_breakdown": {
                    "total": reward.total,
                    "carbon_penalty": reward.carbon_penalty,
                    "deadline_penalty": reward.deadline_penalty,
                    "capacity_penalty": reward.capacity_penalty,
                    "unscheduled_penalty": reward.unscheduled_penalty,
                    "completion_bonus": reward.completion_bonus
                },
                "done": done,
                "info": info
            }
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/state")
async def get_state():
    """
    Get current environment state.
    
    GET /state
    """
    global env_instance
    
    if env_instance is None:
        raise HTTPException(
            status_code=400,
            detail="Environment not initialized. Call /reset first."
        )
    
    try:
        state = env_instance.state()
        
        return JSONResponse(
            status_code=200,
            content={"state": state_to_dict(state)}
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/tasks")
async def list_tasks():
    """List available tasks"""
    try:
        with open("openenv.yaml") as f:
            cfg = yaml.safe_load(f)
        
        return JSONResponse(
            status_code=200,
            content={
                "tasks": list(cfg["tasks"].keys()),
                "default": "medium"
            }
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ─────────────────────────────────────────────
# Run server
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 7860))
    uvicorn.run(app, host="0.0.0.0", port=port)
