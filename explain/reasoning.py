"""
Explainability module for schedule decisions.
Provides human-readable explanations for why jobs were scheduled at specific times.
"""
from typing import Dict, List
from env.models import Job, Action, Observation, ScheduleItem


class ScheduleExplainer:
    """Generate natural language explanations for scheduling decisions."""
    
    def __init__(self, observation: Observation, action: Action):
        self.obs = observation
        self.action = action
        self.job_map = {job.id: job for job in observation.jobs}
    
    def explain_all(self) -> Dict[int, str]:
        """
        Generate explanations for all scheduled jobs.
        
        Returns:
            Dict mapping job_id to explanation string
        """
        explanations = {}
        
        # Build schedule map
        schedule_map = {item.job_id: item for item in self.action.schedule}
        
        # Track slot usage for capacity reasoning
        slot_usage = self._compute_slot_usage()
        
        for job in self.obs.jobs:
            if job.id in schedule_map:
                item = schedule_map[job.id]
                explanation = self._explain_job(job, item, slot_usage)
            else:
                explanation = self._explain_unscheduled(job)
            
            explanations[job.id] = explanation
        
        return explanations
    
    def _explain_job(
        self, 
        job: Job, 
        item: ScheduleItem, 
        slot_usage: Dict[int, int]
    ) -> str:
        """Generate explanation for a scheduled job."""
        reasons = []
        
        start = item.start_time
        end = start + job.duration
        
        # Carbon reasoning
        carbon_cost = sum(self.obs.carbon_intensity[start:end])
        avg_carbon = sum(self.obs.carbon_intensity) / len(self.obs.carbon_intensity)
        
        if carbon_cost < avg_carbon * job.duration * 0.8:
            reasons.append("low carbon intensity period")
        elif carbon_cost > avg_carbon * job.duration * 1.2:
            reasons.append("high carbon period (constrained by other factors)")
        else:
            reasons.append("moderate carbon intensity")
        
        # Deadline reasoning
        slack = job.deadline - end
        if slack == 0:
            reasons.append("tight deadline (must finish exactly at deadline)")
        elif slack < job.duration:
            reasons.append(f"approaching deadline (only {slack} slots of slack)")
        else:
            reasons.append("meets deadline comfortably")
        
        # Capacity reasoning
        max_usage = max(slot_usage[t] for t in range(start, end))
        if max_usage >= self.obs.capacity:
            reasons.append("at capacity limit")
        elif max_usage >= self.obs.capacity * 0.8:
            reasons.append("high resource utilization")
        else:
            reasons.append("sufficient capacity available")
        
        # Priority reasoning
        if job.priority >= 4:
            reasons.append("high priority job")
        elif job.priority <= 2:
            reasons.append("low priority job")
        
        # Build explanation
        explanation = (
            f"Job {job.id} scheduled at time {start} "
            f"(duration {job.duration}, ends at {end}) because:\n"
        )
        for i, reason in enumerate(reasons, 1):
            explanation += f"  {i}. {reason}\n"
        
        return explanation.strip()
    
    def _explain_unscheduled(self, job: Job) -> str:
        """Generate explanation for why a job was not scheduled."""
        reasons = []
        
        # Check if deadline is too tight
        if job.deadline < job.duration:
            reasons.append("impossible deadline (deadline < duration)")
        elif job.deadline <= job.duration + 2:
            reasons.append("very tight deadline with limited scheduling options")
        
        # Check capacity constraints
        if self.obs.capacity == 1:
            reasons.append("limited capacity (only 1 concurrent job allowed)")
        
        # Check if other jobs consumed all slots
        slot_usage = self._compute_slot_usage()
        available_windows = self._find_available_windows(job, slot_usage)
        
        if not available_windows:
            reasons.append("no available time windows meeting all constraints")
        else:
            reasons.append(
                f"could not fit within {len(available_windows)} available windows "
                "due to optimization priorities"
            )
        
        # Priority reasoning
        if job.priority <= 2:
            reasons.append("low priority (may be deprioritized in favor of higher priority jobs)")
        
        explanation = f"Job {job.id} was NOT scheduled because:\n"
        for i, reason in enumerate(reasons, 1):
            explanation += f"  {i}. {reason}\n"
        
        return explanation.strip()
    
    def _compute_slot_usage(self) -> Dict[int, int]:
        """Compute number of jobs running in each time slot."""
        usage = {t: 0 for t in range(self.obs.time_horizon)}
        
        for item in self.action.schedule:
            if item.job_id in self.job_map:
                job = self.job_map[item.job_id]
                for t in range(item.start_time, item.start_time + job.duration):
                    if t < self.obs.time_horizon:
                        usage[t] += 1
        
        return usage
    
    def _find_available_windows(
        self, 
        job: Job, 
        slot_usage: Dict[int, int]
    ) -> List[int]:
        """Find time slots where job could potentially start."""
        available = []
        
        for start in range(self.obs.time_horizon - job.duration + 1):
            end = start + job.duration
            
            # Check deadline
            if end > job.deadline:
                continue
            
            # Check capacity
            can_fit = all(
                slot_usage[t] < self.obs.capacity 
                for t in range(start, end)
            )
            
            if can_fit:
                available.append(start)
        
        return available
    
    def generate_summary(self) -> str:
        """Generate overall summary of scheduling decisions."""
        scheduled_count = len(self.action.schedule)
        total_count = len(self.obs.jobs)
        
        total_carbon = 0
        for item in self.action.schedule:
            if item.job_id in self.job_map:
                job = self.job_map[item.job_id]
                start = item.start_time
                end = start + job.duration
                total_carbon += sum(self.obs.carbon_intensity[start:end])
        
        summary = f"""
SCHEDULING SUMMARY
==================
Jobs Scheduled: {scheduled_count} / {total_count}
Total Carbon Emissions: {total_carbon:,} gCO2
Average Carbon per Job: {total_carbon / scheduled_count if scheduled_count > 0 else 0:.1f} gCO2

Strategy: The scheduler prioritized jobs based on deadlines and carbon intensity,
attempting to minimize emissions while meeting constraints. High-priority jobs
were given preference in low-carbon time slots when possible.
"""
        return summary.strip()
