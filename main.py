"""
Main entry point for Carbon-Aware Cloud Workload Scheduler.
Demonstrates environment usage with different optimizers.
"""
import math
import yaml
from env.scheduler_env import SchedulerEnv
from optimizer.greedy import GreedyOptimizer, PriorityGreedyOptimizer, CarbonFirstOptimizer
from optimizer.ilp_solver import ILPOptimizer, WeightedILPOptimizer
from metrics.analytics import SchedulerMetrics, compute_score
from explain.reasoning import ScheduleExplainer


def load_config(task_name: str = "medium") -> dict:
    """Load task configuration from openenv.yaml."""
    with open("openenv.yaml", "r") as f:
        config = yaml.safe_load(f)
    
    return config["tasks"][task_name]["config"]


# ----------------------------------------------------------------------
# Score formatting - matches grader.py behavior
# ----------------------------------------------------------------------
_EPS = 1e-6  # keeps scores strictly inside (0, 1)


def _clamp(value) -> float:
    """
    Return a float strictly between 0 and 1.
    Handles: None, NaN, -inf, +inf, negative, >1, non-numeric.
    """
    try:
        v = float(value)
    except (TypeError, ValueError):
        return _EPS
    if math.isnan(v) or math.isinf(v):
        return _EPS
    return max(_EPS, min(1.0 - _EPS, v))


def _fmt(value: float) -> float:
    """
    Strip trailing zeros from a float's string representation.
    e.g. 0.7000 → 0.7,  0.75000 → 0.75,  0.123456 → 0.123456
    Returns a float whose repr has no unnecessary trailing zeros.
    """
    return float(f"{value:.10f}".rstrip("0").rstrip("."))


def run_optimizer(env: SchedulerEnv, optimizer_class, optimizer_name: str):
    """Run a single optimizer and display results."""
    print(f"\n{'=' * 70}")
    print(f"Running: {optimizer_name}")
    print(f"{'=' * 70}")
    
    # Reset environment
    obs = env.reset()
    
    # Create optimizer and solve
    optimizer = optimizer_class(obs)
    action = optimizer.solve()
    
    # Execute action
    obs, reward, done, info = env.step(action)
    
    # Compute metrics
    metrics_analyzer = SchedulerMetrics(obs, action)
    metrics = metrics_analyzer.compute_all_metrics()
    raw_score = compute_score(metrics)
    score = _clamp(raw_score)  # Ensure score is strictly in (0, 1)
    
    # Generate explanations
    explainer = ScheduleExplainer(obs, action)
    
    # Display results with clean formatting
    print(f"\nReward: {_fmt(reward.total)}")
    print(f"Score: {_fmt(score)}")
    print(f"\nReward Breakdown:")
    print(f"  Carbon Penalty: {_fmt(reward.carbon_penalty)}")
    print(f"  Deadline Penalty: {_fmt(reward.deadline_penalty)}")
    print(f"  Capacity Penalty: {_fmt(reward.capacity_penalty)}")
    print(f"  Unscheduled Penalty: {_fmt(reward.unscheduled_penalty)}")
    print(f"  Completion Bonus: {_fmt(reward.completion_bonus)}")
    
    print(f"\n{metrics_analyzer.generate_report()}")
    
    print(f"\nSchedule Explanations:")
    print(f"{'-' * 70}")
    explanations = explainer.explain_all()
    for job_id in sorted(explanations.keys())[:3]:  # Show first 3
        print(explanations[job_id])
        print()
    
    return score, metrics


def main():
    """Main demonstration of the scheduler environment."""
    print("=" * 70)
    print("CARBON-AWARE CLOUD WORKLOAD SCHEDULER")
    print("=" * 70)
    
    # Test different difficulty levels
    for task_name in ["easy", "medium", "hard"]:
        print(f"\n\n{'#' * 70}")
        print(f"# TASK: {task_name.upper()}")
        print(f"{'#' * 70}")
        
        # Load configuration
        config = load_config(task_name)
        env = SchedulerEnv(config, seed=42)
        
        # Test different optimizers
        optimizers = [
            (GreedyOptimizer, "Greedy (Deadline Priority)"),
            (PriorityGreedyOptimizer, "Greedy (Priority First)"),
            (CarbonFirstOptimizer, "Greedy (Carbon First)"),
        ]
        
        # Add ILP for easier tasks (too slow for hard)
        if task_name != "hard":
            optimizers.append((ILPOptimizer, "ILP (Optimal)"))
        
        results = {}
        for optimizer_class, name in optimizers:
            try:
                score, metrics = run_optimizer(env, optimizer_class, name)
                results[name] = score
            except Exception as e:
                print(f"Error running {name}: {e}")
                results[name] = 0.0
        
        # Summary
        print(f"\n{'=' * 70}")
        print(f"TASK {task_name.upper()} SUMMARY")
        print(f"{'=' * 70}")
        for name, score in sorted(results.items(), key=lambda x: -x[1]):
            print(f"{name:40s}: {_fmt(score)}")


if __name__ == "__main__":
    main()
