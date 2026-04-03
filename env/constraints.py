"""
Constraint validation for job scheduling.
Checks capacity, deadlines, overlaps, and other scheduling rules.
"""
from typing import List, Dict, Tuple, Set
from env.models import Job, Action, ScheduleItem


class ConstraintValidator:
    """Validates scheduling constraints and computes violations."""
    
    def __init__(self, jobs: List[Job], capacity: int, time_horizon: int):
        self.jobs = {job.id: job for job in jobs}
        self.capacity = capacity
        self.time_horizon = time_horizon
    
    def validate_schedule(self, action: Action) -> Dict[str, any]:
        """
        Validate a complete schedule and return violation details.
        
        Returns:
            dict with keys:
                - valid: bool
                - scheduled_jobs: set of job IDs
                - unscheduled_jobs: set of job IDs
                - deadline_misses: int
                - capacity_violations: int
                - overlaps: int
                - details: list of violation messages
        """
        result = {
            'valid': True,
            'scheduled_jobs': set(),
            'unscheduled_jobs': set(self.jobs.keys()),
            'deadline_misses': 0,
            'capacity_violations': 0,
            'overlaps': 0,
            'details': []
        }
        
        # Track time slot usage
        slot_usage: Dict[int, List[int]] = {t: [] for t in range(self.time_horizon)}
        
        # Check each scheduled job
        for item in action.schedule:
            job_id = item.job_id
            start_time = item.start_time
            
            # Check if job exists
            if job_id not in self.jobs:
                result['valid'] = False
                result['details'].append(f"Job {job_id} does not exist")
                continue
            
            job = self.jobs[job_id]
            
            # Mark as scheduled
            if job_id in result['scheduled_jobs']:
                result['valid'] = False
                result['details'].append(f"Job {job_id} scheduled multiple times")
                result['overlaps'] += 1
            else:
                result['scheduled_jobs'].add(job_id)
                result['unscheduled_jobs'].discard(job_id)
            
            # Check time bounds
            end_time = start_time + job.duration
            if start_time < 0 or end_time > self.time_horizon:
                result['valid'] = False
                result['details'].append(
                    f"Job {job_id} exceeds time horizon: [{start_time}, {end_time})"
                )
                continue
            
            # Check deadline
            if end_time > job.deadline:
                result['deadline_misses'] += 1
                result['details'].append(
                    f"Job {job_id} misses deadline: ends at {end_time}, deadline {job.deadline}"
                )
            
            # Track slot usage
            for t in range(start_time, end_time):
                slot_usage[t].append(job_id)
        
        # Check capacity constraints
        for t, jobs_at_t in slot_usage.items():
            if len(jobs_at_t) > self.capacity:
                result['capacity_violations'] += 1
                result['details'].append(
                    f"Time slot {t} exceeds capacity: {len(jobs_at_t)} > {self.capacity}"
                )
        
        return result
    
    def compute_carbon_cost(
        self, 
        action: Action, 
        carbon_intensity: List[int]
    ) -> Tuple[int, Dict[int, int]]:
        """
        Compute total carbon emissions for a schedule.
        
        Returns:
            (total_carbon, job_carbon_map)
        """
        total_carbon = 0
        job_carbon = {}
        
        for item in action.schedule:
            if item.job_id not in self.jobs:
                continue
            
            job = self.jobs[item.job_id]
            start = item.start_time
            end = min(start + job.duration, len(carbon_intensity))
            
            carbon = sum(carbon_intensity[start:end])
            job_carbon[item.job_id] = carbon
            total_carbon += carbon
        
        return total_carbon, job_carbon
    
    def get_time_slot_occupancy(self, action: Action) -> List[int]:
        """Return number of jobs running in each time slot."""
        occupancy = [0] * self.time_horizon
        
        for item in action.schedule:
            if item.job_id not in self.jobs:
                continue
            
            job = self.jobs[item.job_id]
            start = item.start_time
            end = min(start + job.duration, self.time_horizon)
            
            for t in range(start, end):
                occupancy[t] += 1
        
        return occupancy
