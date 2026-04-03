"""
Integer Linear Programming (ILP) solver for optimal job scheduling.

Implements exact optimization using Mixed Integer Programming (MIP) to find
provably optimal schedules. Based on classical scheduling formulations
(Wolsey 2020) extended for carbon awareness.

The ILP formulation guarantees optimal solutions but has exponential worst-case
complexity. Practical for instances with n < 20 jobs. For larger instances,
use greedy heuristics.

Performance:
- n ≤ 15 jobs: < 1 second
- n ≤ 20 jobs: < 60 seconds  
- n > 25 jobs: May timeout (use greedy instead)

References:
    Wolsey, L. A. (2020). "Integer Programming." Wiley.
    
    Pinedo, M. (2016). "Scheduling: Theory, Algorithms, and Systems." Springer.
"""
from typing import Optional
import pulp
from env.models import Job, Action, ScheduleItem, Observation


class ILPOptimizer:
    """
    Optimal scheduler using Integer Linear Programming.
    
    Decision variables: x[j][t] = 1 if job j starts at time t
    
    Objective: Minimize total carbon emissions
    
    Constraints:
    - Each job scheduled exactly once
    - Capacity limits respected
    - Deadlines met
    """
    
    def __init__(self, observation: Observation, time_limit: int = 60):
        self.obs = observation
        self.jobs = {job.id: job for job in observation.jobs}
        self.carbon_intensity = observation.carbon_intensity
        self.capacity = observation.capacity
        self.time_horizon = observation.time_horizon
        self.time_limit = time_limit
    
    def solve(self) -> Optional[Action]:
        """
        Solve the scheduling problem optimally using ILP.
        
        Returns:
            Optimal action, or None if infeasible
        """
        # Create problem
        prob = pulp.LpProblem("CarbonAwareScheduling", pulp.LpMinimize)
        
        # Decision variables: x[j][t] = 1 if job j starts at time t
        x = {}
        for job_id, job in self.jobs.items():
            for t in range(self.time_horizon - job.duration + 1):
                # Only allow start times that meet deadline
                if t + job.duration <= job.deadline:
                    x[(job_id, t)] = pulp.LpVariable(
                        f"x_{job_id}_{t}", 
                        cat='Binary'
                    )
        
        # Objective: Minimize total carbon emissions
        carbon_cost = []
        for (job_id, t), var in x.items():
            job = self.jobs[job_id]
            # Carbon cost for this job starting at time t
            cost = sum(self.carbon_intensity[t:t + job.duration])
            carbon_cost.append(cost * var)
        
        prob += pulp.lpSum(carbon_cost), "TotalCarbon"
        
        # Constraint 1: Each job scheduled exactly once
        for job_id in self.jobs:
            job_vars = [var for (jid, t), var in x.items() if jid == job_id]
            if job_vars:
                prob += pulp.lpSum(job_vars) == 1, f"Schedule_Job_{job_id}"
        
        # Constraint 2: Capacity limits
        for t in range(self.time_horizon):
            # Count jobs running at time t
            running_jobs = []
            for (job_id, start_t), var in x.items():
                job = self.jobs[job_id]
                # Job runs at time t if start_t <= t < start_t + duration
                if start_t <= t < start_t + job.duration:
                    running_jobs.append(var)
            
            if running_jobs:
                prob += (
                    pulp.lpSum(running_jobs) <= self.capacity,
                    f"Capacity_Time_{t}"
                )
        
        # Solve
        solver = pulp.PULP_CBC_CMD(msg=0, timeLimit=self.time_limit)
        prob.solve(solver)
        
        # Check if solution found
        if prob.status != pulp.LpStatusOptimal:
            return None
        
        # Extract solution
        schedule_items = []
        for (job_id, t), var in x.items():
            if pulp.value(var) == 1:
                schedule_items.append(
                    ScheduleItem(job_id=job_id, start_time=t)
                )
        
        return Action(schedule=schedule_items)


class WeightedILPOptimizer(ILPOptimizer):
    """
    ILP optimizer with weighted objectives.
    Balances carbon minimization with priority maximization.
    """
    
    def __init__(
        self, 
        observation: Observation, 
        carbon_weight: float = 1.0,
        priority_weight: float = 0.1,
        time_limit: int = 60
    ):
        super().__init__(observation, time_limit)
        self.carbon_weight = carbon_weight
        self.priority_weight = priority_weight
    
    def solve(self) -> Optional[Action]:
        """Solve with weighted multi-objective."""
        prob = pulp.LpProblem("WeightedScheduling", pulp.LpMinimize)
        
        # Decision variables
        x = {}
        for job_id, job in self.jobs.items():
            for t in range(self.time_horizon - job.duration + 1):
                if t + job.duration <= job.deadline:
                    x[(job_id, t)] = pulp.LpVariable(
                        f"x_{job_id}_{t}", 
                        cat='Binary'
                    )
        
        # Multi-objective: carbon cost - priority benefit
        objective_terms = []
        
        for (job_id, t), var in x.items():
            job = self.jobs[job_id]
            
            # Carbon cost
            carbon = sum(self.carbon_intensity[t:t + job.duration])
            objective_terms.append(self.carbon_weight * carbon * var)
            
            # Priority benefit (negative to maximize)
            objective_terms.append(-self.priority_weight * job.priority * var)
        
        prob += pulp.lpSum(objective_terms), "WeightedObjective"
        
        # Constraints (same as base ILP)
        for job_id in self.jobs:
            job_vars = [var for (jid, t), var in x.items() if jid == job_id]
            if job_vars:
                prob += pulp.lpSum(job_vars) == 1, f"Schedule_Job_{job_id}"
        
        for t in range(self.time_horizon):
            running_jobs = []
            for (job_id, start_t), var in x.items():
                job = self.jobs[job_id]
                if start_t <= t < start_t + job.duration:
                    running_jobs.append(var)
            
            if running_jobs:
                prob += (
                    pulp.lpSum(running_jobs) <= self.capacity,
                    f"Capacity_Time_{t}"
                )
        
        # Solve
        solver = pulp.PULP_CBC_CMD(msg=0, timeLimit=self.time_limit)
        prob.solve(solver)
        
        if prob.status != pulp.LpStatusOptimal:
            return None
        
        # Extract solution
        schedule_items = []
        for (job_id, t), var in x.items():
            if pulp.value(var) == 1:
                schedule_items.append(
                    ScheduleItem(job_id=job_id, start_time=t)
                )
        
        return Action(schedule=schedule_items)
