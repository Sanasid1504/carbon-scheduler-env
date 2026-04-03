"""
Main entry point for Carbon-Aware Cloud Workload Scheduler.
Demonstrates environment usage with different optimizers.
"""
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
    score = compute_score(metrics)
    
    # Generate explanations
    explainer = ScheduleExplainer(obs, action)
    
    # Display results
    print(f"\nReward: {reward.total:.4f}")
    print(f"Score: {score:.4f}")
    print(f"\nReward Breakdown:")
    print(f"  Carbon Penalty: {reward.carbon_penalty:.4f}")
    print(f"  Deadline Penalty: {reward.deadline_penalty:.4f}")
    print(f"  Capacity Penalty: {reward.capacity_penalty:.4f}")
    print(f"  Unscheduled Penalty: {reward.unscheduled_penalty:.4f}")
    print(f"  Completion Bonus: {reward.completion_bonus:.4f}")
    
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
            print(f"{name:40s}: {score:.4f}")


if __name__ == "__main__":
    main()
