"""
Visualization tools for schedule analysis.
Creates ASCII Gantt charts and carbon intensity plots.
"""
import yaml
from typing import List
from env.scheduler_env import SchedulerEnv
from env.models import Action
from optimizer.greedy import GreedyOptimizer


def create_gantt_chart(obs, action: Action, width: int = 70) -> str:
    """
    Create ASCII Gantt chart of the schedule.
    
    Args:
        obs: Environment observation
        action: Schedule action
        width: Chart width in characters
        
    Returns:
        ASCII art Gantt chart
    """
    lines = []
    lines.append("=" * width)
    lines.append("SCHEDULE GANTT CHART")
    lines.append("=" * width)
    
    # Time axis
    time_scale = width - 20
    slot_width = time_scale / obs.time_horizon
    
    # Header
    header = "Job | "
    for t in range(0, obs.time_horizon, max(1, obs.time_horizon // 10)):
        header += f"{t:2d}"
        header += " " * (int(slot_width * (obs.time_horizon // 10)) - 2)
    lines.append(header[:width])
    lines.append("-" * width)
    
    # Job map
    job_map = {job.id: job for job in obs.jobs}
    schedule_map = {item.job_id: item for item in action.schedule}
    
    # Draw each job
    for job in sorted(obs.jobs, key=lambda j: j.id):
        if job.id in schedule_map:
            item = schedule_map[job.id]
            start = item.start_time
            end = start + job.duration
            
            # Build timeline
            timeline = [" "] * obs.time_horizon
            for t in range(start, end):
                timeline[t] = "█"
            
            # Mark deadline
            if job.deadline < obs.time_horizon:
                timeline[job.deadline] = "|"
            
            # Convert to string
            timeline_str = "".join(timeline)
            
            # Add carbon info
            carbon = sum(obs.carbon_intensity[start:end])
            status = "✓" if end <= job.deadline else "✗"
            
            line = f" {job.id:2d} {status} | {timeline_str} | {carbon:4d} gCO2"
            lines.append(line[:width])
        else:
            lines.append(f" {job.id:2d} ✗ | {'─' * obs.time_horizon} | NOT SCHEDULED")
    
    lines.append("-" * width)
    lines.append("Legend: █ = running, | = deadline, ✓ = met, ✗ = missed/unscheduled")
    lines.append("=" * width)
    
    return "\n".join(lines)


def create_carbon_plot(carbon_intensity: List[int], width: int = 70) -> str:
    """
    Create ASCII plot of carbon intensity over time.
    
    Args:
        carbon_intensity: List of carbon values
        width: Chart width
        
    Returns:
        ASCII art plot
    """
    lines = []
    lines.append("=" * width)
    lines.append("CARBON INTENSITY PROFILE")
    lines.append("=" * width)
    
    max_val = max(carbon_intensity)
    min_val = min(carbon_intensity)
    height = 10
    
    # Normalize to height
    def normalize(val):
        if max_val == min_val:
            return height // 2
        return int((val - min_val) / (max_val - min_val) * (height - 1))
    
    # Draw plot
    for row in range(height - 1, -1, -1):
        line = f"{min_val + (max_val - min_val) * row // (height - 1):4d} |"
        for val in carbon_intensity:
            norm_val = normalize(val)
            if norm_val == row:
                line += "█"
            elif norm_val > row:
                line += "│"
            else:
                line += " "
        lines.append(line)
    
    # X-axis
    lines.append("     +" + "─" * len(carbon_intensity))
    
    # Time labels
    time_labels = "      "
    for i in range(0, len(carbon_intensity), max(1, len(carbon_intensity) // 10)):
        time_labels += f"{i:2d}"
        time_labels += " " * (len(carbon_intensity) // 10 - 2)
    lines.append(time_labels[:width])
    
    lines.append(f"\nMin: {min_val} gCO2/kWh  |  Max: {max_val} gCO2/kWh  |  Avg: {sum(carbon_intensity)//len(carbon_intensity)} gCO2/kWh")
    lines.append("=" * width)
    
    return "\n".join(lines)


def create_utilization_plot(obs, action: Action, width: int = 70) -> str:
    """
    Create ASCII plot of capacity utilization over time.
    
    Args:
        obs: Environment observation
        action: Schedule action
        width: Chart width
        
    Returns:
        ASCII art plot
    """
    lines = []
    lines.append("=" * width)
    lines.append("CAPACITY UTILIZATION")
    lines.append("=" * width)
    
    # Compute utilization per slot
    utilization = [0] * obs.time_horizon
    job_map = {job.id: job for job in obs.jobs}
    
    for item in action.schedule:
        if item.job_id in job_map:
            job = job_map[item.job_id]
            for t in range(item.start_time, min(item.start_time + job.duration, obs.time_horizon)):
                utilization[t] += 1
    
    # Draw bar chart
    max_height = 10
    for row in range(max_height, 0, -1):
        threshold = obs.capacity * row / max_height
        line = f"{int(threshold):2d} |"
        for u in utilization:
            if u >= threshold:
                line += "█"
            elif u >= threshold - obs.capacity / max_height / 2:
                line += "▄"
            else:
                line += " "
        lines.append(line)
    
    # X-axis
    lines.append(" 0 +" + "─" * len(utilization))
    
    # Time labels
    time_labels = "    "
    for i in range(0, len(utilization), max(1, len(utilization) // 10)):
        time_labels += f"{i:2d}"
        time_labels += " " * (len(utilization) // 10 - 2)
    lines.append(time_labels[:width])
    
    # Stats
    avg_util = sum(utilization) / len(utilization)
    max_util = max(utilization)
    lines.append(f"\nCapacity: {obs.capacity}  |  Peak: {max_util}  |  Avg: {avg_util:.1f}  |  Utilization: {avg_util/obs.capacity:.1%}")
    
    if max_util > obs.capacity:
        lines.append("⚠ WARNING: Capacity exceeded!")
    
    lines.append("=" * width)
    
    return "\n".join(lines)


def visualize_schedule(task_name: str = "medium"):
    """
    Create comprehensive visualization of a schedule.
    
    Args:
        task_name: Task to visualize (easy, medium, hard)
    """
    # Load task
    with open("openenv.yaml") as f:
        config = yaml.safe_load(f)
    
    task_config = config["tasks"][task_name]["config"]
    
    # Create environment and solve
    env = SchedulerEnv(task_config, seed=42, use_real_carbon=False)
    obs = env.reset()
    
    optimizer = GreedyOptimizer(obs)
    action = optimizer.solve()
    
    # Execute
    obs, reward, done, info = env.step(action)
    
    # Generate visualizations
    print(f"\n{'=' * 70}")
    print(f"VISUALIZATION: {task_name.upper()} TASK")
    print(f"{'=' * 70}\n")
    
    print(create_carbon_plot(obs.carbon_intensity))
    print()
    print(create_gantt_chart(obs, action))
    print()
    print(create_utilization_plot(obs, action))
    
    print(f"\nRESULTS:")
    print(f"  Reward: {reward.total:.4f}")
    print(f"  Carbon: {info['total_carbon']:,} gCO2")
    print(f"  Jobs: {info['scheduled_jobs']}/{info['total_jobs']}")
    print(f"  Deadline misses: {info['deadline_misses']}")
    print(f"  Capacity violations: {info['capacity_violations']}")


if __name__ == "__main__":
    import sys
    task = sys.argv[1] if len(sys.argv) > 1 else "medium"
    visualize_schedule(task)
