"""
Carbon-Aware Cloud Workload Scheduler Environment.

This module implements an OpenEnv-compliant environment for carbon-aware job scheduling,
based on research from Google, Microsoft, and academic papers (Wiesner et al. 2021,
Acun et al. 2023).

The environment simulates a cloud data center where jobs must be scheduled to minimize
carbon emissions while meeting deadlines and capacity constraints. This reflects real-world
systems deployed by major cloud providers.

Key Features:
- Real-world carbon intensity data integration (ElectricityMap, UK Carbon API)
- Multiple optimization objectives (carbon, deadlines, priorities)
- Constraint validation (capacity, deadlines)
- Comprehensive metrics and explainability

References:
    Wiesner, P., et al. (2021). "Let's Wait Awhile: How Temporal Workload Shifting
    Can Reduce Carbon Emissions in the Cloud." ACM SoCC.
    
    Acun, B., et al. (2023). "Carbon Explorer: A Holistic Framework for Designing
    Carbon Aware Datacenters." ASPLOS.
"""
import os
import random
from typing import Dict, Tuple, Any, List, Optional
from env.models import Job, Observation, Action, Reward, EnvironmentState
from env.constraints import ConstraintValidator


class SchedulerEnv:
    """
    OpenEnv-compliant environment for carbon-aware job scheduling.
    
    The agent must schedule compute jobs across time slots to minimize
    carbon emissions while meeting deadlines and capacity constraints.
    """
    
    def __init__(self, task_config: Dict[str, Any], seed: int = 42, use_real_carbon: bool = True):
        """
        Initialize the scheduler environment.
        
        Args:
            task_config: Configuration dict with 'jobs', 'capacity', 'time_horizon'
            seed: Random seed for reproducibility
            use_real_carbon: If True, try to fetch real carbon data from APIs
        """
        self.task_config = task_config
        self.seed = seed
        self.rng = random.Random(seed)
        self.use_real_carbon = use_real_carbon
        
        self.time_horizon = task_config.get('time_horizon', 24)
        self.capacity = task_config['capacity']
        self.job_configs = task_config['jobs']
        
        self._state: EnvironmentState = None
        self._validator: ConstraintValidator = None
    
    def reset(self) -> Observation:
        """
        Reset environment to initial state.
        
        Returns:
            Initial observation
        """
        # Create jobs from config
        jobs = [Job(**job_config) for job_config in self.job_configs]
        
        # Generate carbon intensity profile (realistic daily pattern)
        carbon_intensity = self._generate_carbon_profile()
        
        # Initialize state
        self._state = EnvironmentState(
            jobs=jobs,
            carbon_intensity=carbon_intensity,
            capacity=self.capacity,
            time_horizon=self.time_horizon,
            current_schedule=None,
            episode_step=0,
            done=False
        )
        
        # Initialize validator
        self._validator = ConstraintValidator(
            jobs=jobs,
            capacity=self.capacity,
            time_horizon=self.time_horizon
        )
        
        return Observation(
            jobs=jobs,
            carbon_intensity=carbon_intensity,
            capacity=self.capacity,
            time_horizon=self.time_horizon
        )
    
    def step(self, action: Action) -> Tuple[Observation, Reward, bool, Dict[str, Any]]:
        """
        Execute one step with the given action.
        
        Args:
            action: Scheduling action from agent
            
        Returns:
            (observation, reward, done, info)
        """
        if self._state is None:
            raise RuntimeError("Environment not initialized. Call reset() first.")
        
        if self._state.done:
            raise RuntimeError("Episode already done. Call reset() to start new episode.")
        
        # Store action
        self._state.current_schedule = action
        self._state.episode_step += 1
        
        # Validate schedule
        validation = self._validator.validate_schedule(action)
        
        # Compute carbon cost
        total_carbon, job_carbon = self._validator.compute_carbon_cost(
            action, 
            self._state.carbon_intensity
        )
        
        # Compute reward
        reward = self._compute_reward(validation, total_carbon)
        
        # Mark episode as done
        self._state.done = True
        
        # Build info dict
        info = {
            'validation': validation,
            'total_carbon': total_carbon,
            'job_carbon': job_carbon,
            'scheduled_jobs': len(validation['scheduled_jobs']),
            'total_jobs': len(self._state.jobs),
            'deadline_misses': validation['deadline_misses'],
            'capacity_violations': validation['capacity_violations'],
            'occupancy': self._validator.get_time_slot_occupancy(action)
        }
        
        # Return current observation (unchanged in single-step environment)
        obs = Observation(
            jobs=self._state.jobs,
            carbon_intensity=self._state.carbon_intensity,
            capacity=self._state.capacity,
            time_horizon=self._state.time_horizon
        )
        
        return obs, reward, True, info
    
    def state(self) -> EnvironmentState:
        """Return current internal state."""
        if self._state is None:
            raise RuntimeError("Environment not initialized. Call reset() first.")
        return self._state
    
    def _compute_reward(self, validation: Dict, total_carbon: int) -> Reward:
        """
        Compute reward based on schedule quality.
        
        Reward function design based on multi-objective optimization literature
        (Deb 2001) and industry practices. Balances carbon minimization with
        operational constraints.
        
        Reward components:
        - Carbon penalty: -total_carbon / 1000
          Normalized by 1000 to keep in reasonable range. Based on typical
          data center emissions (Google reports ~500-1000 gCO2 per job).
          
        - Deadline penalty: -1.0 per missed deadline
          Strong penalty reflects SLA importance in production systems.
          Based on AWS/Azure SLA structures.
          
        - Capacity penalty: -0.5 per violation
          Moderate penalty as capacity violations may be tolerable short-term.
          
        - Unscheduled penalty: -0.5 per unscheduled job
          Encourages complete schedules while allowing partial solutions.
          
        - Completion bonus: +1.0 if all jobs scheduled
          Incentivizes finding feasible complete schedules.
        
        Final reward normalized to [0.0, 1.0] for consistency with OpenEnv standards.
        
        Args:
            validation: Constraint validation results
            total_carbon: Total carbon emissions in gCO2
            
        Returns:
            Reward object with total and component breakdown
        """
        reward_components = Reward(total=0.0)
        
        # Carbon penalty
        if total_carbon > 0:
            reward_components.carbon_penalty = -total_carbon / 1000.0
        
        # Deadline penalty
        if validation['deadline_misses'] > 0:
            reward_components.deadline_penalty = -1.0 * validation['deadline_misses']
        
        # Capacity penalty
        if validation['capacity_violations'] > 0:
            reward_components.capacity_penalty = -0.5 * validation['capacity_violations']
        
        # Unscheduled penalty
        num_unscheduled = len(validation['unscheduled_jobs'])
        if num_unscheduled > 0:
            reward_components.unscheduled_penalty = -0.5 * num_unscheduled
        
        # Completion bonus
        if num_unscheduled == 0:
            reward_components.completion_bonus = 1.0
        
        # Sum all components
        raw_reward = (
            reward_components.carbon_penalty +
            reward_components.deadline_penalty +
            reward_components.capacity_penalty +
            reward_components.unscheduled_penalty +
            reward_components.completion_bonus
        )
        
        # Normalize to [0.0, 1.0]
        # Worst case: all jobs unscheduled with max penalties
        # Best case: all scheduled with minimal carbon
        max_penalty = len(self._state.jobs) * 2.0  # Rough estimate
        normalized = max(0.0, min(1.0, (raw_reward + max_penalty) / (max_penalty + 1.0)))
        
        reward_components.total = normalized
        
        return reward_components
    
    def _generate_carbon_profile(self) -> List[int]:
        """
        Generate carbon intensity profile.
        
        Tries to fetch real-world data if use_real_carbon=True,
        otherwise generates realistic synthetic pattern.
        """
        if self.use_real_carbon:
            # Try to fetch real carbon data
            try:
                from env.carbon_api import CarbonIntensityAPI
                
                api = CarbonIntensityAPI()
                
                # Try different regions in order of preference
                regions = [
                    os.getenv("CARBON_REGION", "UK"),  # Default to UK (free, no key)
                    "UK",
                    "US-CAL-CISO"
                ]
                
                for region in regions:
                    carbon_data = api.get_carbon_intensity(region, self.time_horizon)
                    if carbon_data:
                        print(f"[ENV] Using real carbon data from {region}")
                        return carbon_data
                
                print("[ENV] Failed to fetch real carbon data, using synthetic")
            
            except Exception as e:
                print(f"[ENV] Error fetching real carbon data: {e}")
                print("[ENV] Falling back to synthetic data")
        
        # Generate synthetic pattern (realistic daily pattern)
        profile = []
        for hour in range(self.time_horizon):
            # Base pattern: sine wave with peak at hour 14 (2 PM)
            base = 300 + 200 * ((hour - 14) ** 2) / 100
            # Add randomness
            noise = self.rng.randint(-50, 50)
            intensity = max(100, min(800, int(base + noise)))
            profile.append(intensity)
        
        return profile
    
    def render(self) -> str:
        """Render current state as text."""
        if self._state is None:
            return "Environment not initialized"
        
        lines = ["=" * 60]
        lines.append("Carbon-Aware Cloud Workload Scheduler")
        lines.append("=" * 60)
        lines.append(f"Time Horizon: {self.time_horizon} slots")
        lines.append(f"Capacity: {self.capacity} concurrent jobs")
        lines.append(f"Jobs: {len(self._state.jobs)}")
        lines.append("")
        
        if self._state.current_schedule:
            lines.append("Current Schedule:")
            for item in self._state.current_schedule.schedule:
                job = next((j for j in self._state.jobs if j.id == item.job_id), None)
                if job:
                    lines.append(
                        f"  Job {job.id}: start={item.start_time}, "
                        f"duration={job.duration}, deadline={job.deadline}, "
                        f"priority={job.priority}"
                    )
        else:
            lines.append("No schedule yet")
        
        lines.append("=" * 60)
        return "\n".join(lines)
