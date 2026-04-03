"""
Demo inference script using built-in optimizers instead of OpenAI API.
Shows how the inference pipeline works without requiring API keys.
"""
import json
import yaml
import time
from env.scheduler_env import SchedulerEnv
from env.models import Action, ScheduleItem
from optimizer.greedy import GreedyOptimizer
from optimizer.ilp_solver import ILPOptimizer
from metrics.analytics import SchedulerMetrics, compute_score


def load_task_config(task_name: str) -> dict:
    """Load task configuration from openenv.yaml."""
    with open("openenv.yaml", "r") as f:
        config = yaml.safe_load(f)
    return config["tasks"][task_name]["config"]


def run_inference_demo(task_name: str = "medium", optimizer_type: str = "greedy"):
    """
    Run inference demo with built-in optimizer.
    
    Args:
        task_name: Task difficulty (easy, medium, hard)
        optimizer_type: Optimizer to use (greedy, ilp)
    """
    print("[START] Carbon-Aware Scheduler Inference Demo")
    print(f"Task: {task_name}")
    print(f"Optimizer: {optimizer_type}")
    
    # Load task and create environment
    print(f"\n[STEP] Loading task configuration: {task_name}")
    config = load_task_config(task_name)
    env = SchedulerEnv(config, seed=42)
    
    # Reset environment
    print("[STEP] Resetting environment")
    obs = env.reset()
    print(f"  Jobs: {len(obs.jobs)}")
    print(f"  Capacity: {obs.capacity}")
    print(f"  Time Horizon: {obs.time_horizon}")
    
    # Display job details
    print("\n[STEP] Job Details:")
    for job in obs.jobs:
        print(f"  Job {job.id}: duration={job.duration}, deadline={job.deadline}, priority={job.priority}")
    
    # Display carbon intensity
    print(f"\n[STEP] Carbon Intensity Profile:")
    print(f"  Min: {min(obs.carbon_intensity)} gCO2/kWh")
    print(f"  Max: {max(obs.carbon_intensity)} gCO2/kWh")
    print(f"  Avg: {sum(obs.carbon_intensity) / len(obs.carbon_intensity):.1f} gCO2/kWh")
    
    # Run optimizer
    print(f"\n[STEP] Running {optimizer_type} optimizer")
    start_time = time.time()
    
    if optimizer_type == "greedy":
        optimizer = GreedyOptimizer(obs)
    elif optimizer_type == "ilp":
        optimizer = ILPOptimizer(obs, time_limit=30)
    else:
        raise ValueError(f"Unknown optimizer: {optimizer_type}")
    
    action = optimizer.solve()
    inference_time = time.time() - start_time
    
    print(f"  Optimization time: {inference_time:.2f}s")
    print(f"  Scheduled jobs: {len(action.schedule)}")
    
    # Display schedule
    print("\n[STEP] Generated Schedule:")
    for item in action.schedule:
        job = next((j for j in obs.jobs if j.id == item.job_id), None)
        if job:
            end_time = item.start_time + job.duration
            carbon = sum(obs.carbon_intensity[item.start_time:end_time])
            print(f"  Job {job.id}: start={item.start_time:2d}, end={end_time:2d}, "
                  f"carbon={carbon:4d} gCO2, priority={job.priority}")
    
    # Execute action in environment
    print("\n[STEP] Executing action in environment")
    obs, reward, done, info = env.step(action)
    
    print(f"  Reward: {reward.total:.4f}")
    print(f"  Done: {done}")
    
    # Compute metrics
    print("\n[STEP] Computing metrics")
    metrics_analyzer = SchedulerMetrics(obs, action)
    metrics = metrics_analyzer.compute_all_metrics()
    score = compute_score(metrics)
    
    print(f"  Score: {score:.4f}")
    print(f"  Total Carbon: {metrics['total_carbon_gco2']:,} gCO2")
    print(f"  Completion Rate: {metrics['completion_rate']:.1%}")
    print(f"  Deadline Misses: {metrics['deadline_misses']}")
    print(f"  Capacity Violations: {metrics['capacity_violations']}")
    print(f"  Average Utilization: {metrics['average_utilization']:.1%}")
    print(f"  Peak Utilization: {metrics['peak_utilization']:.1%}")
    
    # Final results
    print("\n[END] Inference Complete")
    print("=" * 70)
    print("FINAL RESULTS")
    print("=" * 70)
    print(f"Task: {task_name}")
    print(f"Optimizer: {optimizer_type}")
    print(f"Score: {score:.4f}")
    print(f"Reward: {reward.total:.4f}")
    print(f"Inference Time: {inference_time:.2f}s")
    print(f"Jobs Scheduled: {metrics['jobs_scheduled']} / {metrics['jobs_total']}")
    print(f"Total Carbon: {metrics['total_carbon_gco2']:,} gCO2")
    print(f"Avg Carbon/Job: {metrics['average_carbon_per_job']:.1f} gCO2")
    print(f"Deadline Misses: {metrics['deadline_misses']}")
    print(f"Capacity Violations: {metrics['capacity_violations']}")
    print(f"Resource Utilization: {metrics['average_utilization']:.1%}")
    print("=" * 70)
    
    # Save results
    results = {
        "task": task_name,
        "optimizer": optimizer_type,
        "score": score,
        "reward": reward.total,
        "inference_time_seconds": inference_time,
        "metrics": metrics,
        "schedule": [
            {"job_id": item.job_id, "start_time": item.start_time}
            for item in action.schedule
        ]
    }
    
    output_file = f"results_{task_name}_{optimizer_type}.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\nResults saved to: {output_file}")
    
    return score


if __name__ == "__main__":
    import sys
    
    # Parse arguments
    task = sys.argv[1] if len(sys.argv) > 1 else "medium"
    optimizer = sys.argv[2] if len(sys.argv) > 2 else "greedy"
    
    if task not in ["easy", "medium", "hard"]:
        print(f"Invalid task: {task}")
        print("Valid tasks: easy, medium, hard")
        sys.exit(1)
    
    if optimizer not in ["greedy", "ilp"]:
        print(f"Invalid optimizer: {optimizer}")
        print("Valid optimizers: greedy, ilp")
        sys.exit(1)
    
    print("\n" + "=" * 70)
    print("CARBON-AWARE SCHEDULER - INFERENCE DEMO")
    print("=" * 70)
    print("\nThis demo shows the inference pipeline using built-in optimizers.")
    print("For AI agent inference, use inference.py with OPENAI_API_KEY set.")
    print("=" * 70 + "\n")
    
    score = run_inference_demo(task, optimizer)
    
    print("\n" + "=" * 70)
    print("DEMO COMPLETE!")
    print("=" * 70)
    print(f"\nTry different configurations:")
    print(f"  python inference_demo.py easy greedy")
    print(f"  python inference_demo.py medium ilp")
    print(f"  python inference_demo.py hard greedy")
    
    sys.exit(0 if score > 0.5 else 1)
