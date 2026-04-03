"""
Analytics and metrics computation for scheduler performance.
Tracks carbon usage, completion rates, and resource utilization.
"""
from typing import Dict, List, Any
from env.models import Job, Action, Observation
from env.constraints import ConstraintValidator


class SchedulerMetrics:
    """Compute comprehensive metrics for schedule evaluation."""
    
    def __init__(self, observation: Observation, action: Action):
        self.obs = observation
        self.action = action
        self.validator = ConstraintValidator(
            jobs=observation.jobs,
            capacity=observation.capacity,
            time_horizon=observation.time_horizon
        )
    
    def compute_all_metrics(self) -> Dict[str, Any]:
        """
        Compute all metrics for the schedule.
        
        Returns:
            Dictionary with comprehensive metrics
        """
        validation = self.validator.validate_schedule(self.action)
        total_carbon, job_carbon = self.validator.compute_carbon_cost(
            self.action,
            self.obs.carbon_intensity
        )
        occupancy = self.validator.get_time_slot_occupancy(self.action)
        
        metrics = {
            # Carbon metrics
            'total_carbon_gco2': total_carbon,
            'average_carbon_per_job': (
                total_carbon / len(self.action.schedule) 
                if self.action.schedule else 0
            ),
            'carbon_by_job': job_carbon,
            
            # Completion metrics
            'jobs_scheduled': len(validation['scheduled_jobs']),
            'jobs_total': len(self.obs.jobs),
            'completion_rate': (
                len(validation['scheduled_jobs']) / len(self.obs.jobs)
                if self.obs.jobs else 0
            ),
            'jobs_unscheduled': len(validation['unscheduled_jobs']),
            'unscheduled_job_ids': list(validation['unscheduled_jobs']),
            
            # Constraint violations
            'deadline_misses': validation['deadline_misses'],
            'capacity_violations': validation['capacity_violations'],
            'schedule_valid': validation['valid'],
            
            # Resource utilization
            'average_utilization': sum(occupancy) / len(occupancy) / self.obs.capacity,
            'peak_utilization': max(occupancy) / self.obs.capacity,
            'utilization_by_slot': [u / self.obs.capacity for u in occupancy],
            'idle_slots': sum(1 for u in occupancy if u == 0),
            
            # Priority metrics
            'high_priority_scheduled': self._count_priority_scheduled(4, 5),
            'low_priority_scheduled': self._count_priority_scheduled(1, 2),
            
            # Timing metrics
            'average_job_start_time': self._compute_average_start_time(),
            'schedule_makespan': self._compute_makespan(),
        }
        
        return metrics
    
    def _count_priority_scheduled(self, min_priority: int, max_priority: int) -> int:
        """Count scheduled jobs within priority range."""
        scheduled_ids = {
            item.job_id for item in self.action.schedule
        }
        
        count = 0
        for job in self.obs.jobs:
            if job.id in scheduled_ids and min_priority <= job.priority <= max_priority:
                count += 1
        
        return count
    
    def _compute_average_start_time(self) -> float:
        """Compute average start time of scheduled jobs."""
        if not self.action.schedule:
            return 0.0
        
        total_start = sum(item.start_time for item in self.action.schedule)
        return total_start / len(self.action.schedule)
    
    def _compute_makespan(self) -> int:
        """Compute makespan (latest completion time)."""
        if not self.action.schedule:
            return 0
        
        job_map = {job.id: job for job in self.obs.jobs}
        max_end = 0
        
        for item in self.action.schedule:
            if item.job_id in job_map:
                job = job_map[item.job_id]
                end_time = item.start_time + job.duration
                max_end = max(max_end, end_time)
        
        return max_end
    
    def generate_report(self) -> str:
        """Generate human-readable metrics report."""
        metrics = self.compute_all_metrics()
        
        lines = []
        lines.append("=" * 70)
        lines.append("SCHEDULER PERFORMANCE REPORT")
        lines.append("=" * 70)
        lines.append("")
        
        lines.append("CARBON EMISSIONS")
        lines.append(f"  Total Carbon: {metrics['total_carbon_gco2']:,} gCO2")
        lines.append(f"  Average per Job: {metrics['average_carbon_per_job']:.1f} gCO2")
        lines.append("")
        
        lines.append("JOB COMPLETION")
        lines.append(f"  Scheduled: {metrics['jobs_scheduled']} / {metrics['jobs_total']}")
        lines.append(f"  Completion Rate: {metrics['completion_rate']:.1%}")
        if metrics['jobs_unscheduled'] > 0:
            lines.append(f"  Unscheduled Jobs: {metrics['unscheduled_job_ids']}")
        lines.append("")
        
        lines.append("CONSTRAINT VIOLATIONS")
        lines.append(f"  Deadline Misses: {metrics['deadline_misses']}")
        lines.append(f"  Capacity Violations: {metrics['capacity_violations']}")
        lines.append(f"  Schedule Valid: {metrics['schedule_valid']}")
        lines.append("")
        
        lines.append("RESOURCE UTILIZATION")
        lines.append(f"  Average: {metrics['average_utilization']:.1%}")
        lines.append(f"  Peak: {metrics['peak_utilization']:.1%}")
        lines.append(f"  Idle Slots: {metrics['idle_slots']} / {self.obs.time_horizon}")
        lines.append("")
        
        lines.append("PRIORITY DISTRIBUTION")
        lines.append(f"  High Priority (4-5): {metrics['high_priority_scheduled']} scheduled")
        lines.append(f"  Low Priority (1-2): {metrics['low_priority_scheduled']} scheduled")
        lines.append("")
        
        lines.append("TIMING")
        lines.append(f"  Average Start Time: {metrics['average_job_start_time']:.1f}")
        lines.append(f"  Makespan: {metrics['schedule_makespan']} slots")
        lines.append("")
        
        lines.append("=" * 70)
        
        return "\n".join(lines)


def compute_score(metrics: Dict[str, Any]) -> float:
    """
    Compute deterministic score from metrics.
    
    Score components:
    - Start at 1.0
    - Subtract for deadline misses
    - Subtract for capacity violations
    - Subtract for high carbon (normalized)
    - Subtract for unscheduled jobs
    
    Returns:
        Score in [0.0, 1.0]
    """
    score = 1.0
    
    # Penalty for deadline misses (0.1 per miss)
    score -= 0.1 * metrics['deadline_misses']
    
    # Penalty for capacity violations (0.15 per violation)
    score -= 0.15 * metrics['capacity_violations']
    
    # Penalty for unscheduled jobs (0.2 per job)
    score -= 0.2 * metrics['jobs_unscheduled']
    
    # Penalty for carbon (normalized by job count)
    if metrics['jobs_total'] > 0:
        carbon_per_job = metrics['total_carbon_gco2'] / metrics['jobs_total']
        # Assume 500 gCO2 per job is baseline, penalize above that
        if carbon_per_job > 500:
            score -= min(0.3, (carbon_per_job - 500) / 1000)
    
    # Clamp to [0.0, 1.0]
    return max(0.0, min(1.0, score))
