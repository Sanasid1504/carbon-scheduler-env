"""
Pydantic models for Carbon-Aware Cloud Workload Scheduler.
Defines the core data structures for jobs, observations, actions, and rewards.
"""
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional


class Job(BaseModel):
    """Represents a compute job to be scheduled."""
    id: int = Field(..., description="Unique job identifier")
    duration: int = Field(..., ge=1, description="Number of time slots required")
    deadline: int = Field(..., ge=1, description="Time slot by which job must complete")
    priority: int = Field(default=1, ge=1, le=5, description="Job priority (1=low, 5=high)")
    
    @field_validator('deadline')
    @classmethod
    def deadline_must_allow_completion(cls, v, info):
        if 'duration' in info.data and v < info.data['duration']:
            raise ValueError(f"Deadline {v} must be >= duration {info.data['duration']}")
        return v


class ScheduleItem(BaseModel):
    """Represents a single job scheduling decision."""
    job_id: int = Field(..., description="ID of job to schedule")
    start_time: int = Field(..., ge=0, description="Time slot when job starts")


class Action(BaseModel):
    """Agent's scheduling action."""
    schedule: List[ScheduleItem] = Field(
        default_factory=list,
        description="List of job scheduling decisions"
    )


class Observation(BaseModel):
    """Environment observation provided to the agent."""
    jobs: List[Job] = Field(..., description="List of jobs to schedule")
    carbon_intensity: List[int] = Field(
        ..., 
        description="Carbon intensity for each time slot (gCO2/kWh)"
    )
    capacity: int = Field(..., ge=1, description="Max concurrent jobs per time slot")
    time_horizon: int = Field(default=24, description="Total time slots available")
    
    @field_validator('carbon_intensity')
    @classmethod
    def carbon_must_match_horizon(cls, v, info):
        if 'time_horizon' in info.data and len(v) != info.data['time_horizon']:
            raise ValueError(
                f"Carbon intensity length {len(v)} must match time_horizon {info.data['time_horizon']}"
            )
        return v


class Reward(BaseModel):
    """Reward signal with detailed breakdown."""
    total: float = Field(..., description="Total normalized reward [0.0, 1.0]")
    carbon_penalty: float = Field(default=0.0, description="Penalty for carbon emissions")
    deadline_penalty: float = Field(default=0.0, description="Penalty for missed deadlines")
    capacity_penalty: float = Field(default=0.0, description="Penalty for capacity violations")
    unscheduled_penalty: float = Field(default=0.0, description="Penalty for unscheduled jobs")
    completion_bonus: float = Field(default=0.0, description="Bonus for scheduling all jobs")
    
    def __float__(self):
        return self.total


class EnvironmentState(BaseModel):
    """Internal state of the scheduling environment."""
    jobs: List[Job]
    carbon_intensity: List[int]
    capacity: int
    time_horizon: int
    current_schedule: Optional[Action] = None
    episode_step: int = 0
    done: bool = False
