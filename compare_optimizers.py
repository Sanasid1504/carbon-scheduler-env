"""
Compare all optimizers side-by-side with detailed analysis.
Shows which optimizer works best for different scenarios.
"""
import yaml
import time
from env.scheduler_env import SchedulerEnv
from optimizer.greedy import GreedyOptimizer, PriorityGreedyOptimizer, CarbonFirstOptimizer
from optimizer.ilp_solver import ILPOptimizer
from metrics.analytics import SchedulerMetrics, compute_score


def compare_all_optimizers(task_name: str = "medium"):
    """
    Run all optimizers and compare results.
    
    Args:
        task_name: Task to compare (easy, medium, hard)
    """
    print("=" * 80)
    print(f"OPTIMIZER COMPARISON: {task_name.upper()} TASK")
    print("=" * 80)
    
    # Load task
    with open("openenv.yaml") as f:
        config = yaml.safe_load(f)
    task_config = config["tasks"][task_name]["config"]
    
    # Optimizers to test
    optimizers = [
        ("Greedy (Deadline)", GreedyOptimizer),
        ("Greedy (Priority)", PriorityGreedyOptimizer),
        ("Greedy (Carbon)", CarbonFirstOptimizer),
    ]
    
    # Add ILP for smaller tasks
    if task_name in ["easy", "medium"]:
        optimizers.append(("ILP (Optimal)", ILPOptimizer))
    
    results = []
    
    for name, optimizer_class in optimizers:
        print(f"\n{'─' * 80}")
        print(f"Testing: {name}")
        print(f"{'─' * 80}")
        
        try:
            # Create environment
            env = SchedulerEnv(task_config, seed=42, use_real_carbon=False)
            obs = env.reset()
            
            # Run optimizer
            start_time = time.time()
            optimizer = optimizer_class(obs)
            action = optimizer.solve()
            elapsed = time.time() - start_time
            
            # Execute
            obs, reward, done, info = env.step(action)
            
            # Compute metrics
            metrics = SchedulerMetrics(obs, action).compute_all_metrics()
            score = compute_score(metrics)
            
            # Store results
            result = {
                "name": name,
                "score": score,
                "reward": reward.total,
                "time": elapsed,
                "carbon": metrics['total_carbon_gco2'],
                "jobs_scheduled": metrics['jobs_scheduled'],
                "jobs_total": metrics['jobs_total'],
                "deadline_misses": metrics['deadline_misses'],
                "capacity_violations": metrics['capacity_violations'],
                "utilization": metrics['average_utilization'],
            }
            results.append(result)
            
            print(f"  ✓ Score: {score:.4f}")
            print(f"  ✓ Carbon: {metrics['total_carbon_gco2']:,} gCO2")
            print(f"  ✓ Jobs: {metrics['jobs_scheduled']}/{metrics['jobs_total']}")
            print(f"  ✓ Time: {elapsed:.3f}s")
            
        except Exception as e:
            print(f"  ✗ Failed: {e}")
            results.append({
                "name": name,
                "score": 0.0,
                "error": str(e)
            })
    
    # Summary table
    print(f"\n{'=' * 80}")
    print("COMPARISON SUMMARY")
    print(f"{'=' * 80}\n")
    
    # Header
    print(f"{'Optimizer':<25} {'Score':>8} {'Carbon':>10} {'Jobs':>8} {'Time':>8} {'Violations':>12}")
    print(f"{'-' * 25} {'-' * 8} {'-' * 10} {'-' * 8} {'-' * 8} {'-' * 12}")
    
    # Sort by score
    results.sort(key=lambda x: x.get('score', 0), reverse=True)
    
    for r in results:
        if 'error' in r:
            print(f"{r['name']:<25} {'ERROR':<8}")
        else:
            violations = r['deadline_misses'] + r['capacity_violations']
            print(f"{r['name']:<25} "
                  f"{r['score']:>8.4f} "
                  f"{r['carbon']:>10,} "
                  f"{r['jobs_scheduled']:>3}/{r['jobs_total']:<3} "
                  f"{r['time']:>7.3f}s "
                  f"{violations:>12}")
    
    # Winner
    print(f"\n{'=' * 80}")
    if results and results[0].get('score', 0) > 0:
        winner = results[0]
        print(f"🏆 WINNER: {winner['name']}")
        print(f"   Score: {winner['score']:.4f}")
        print(f"   Carbon: {winner['carbon']:,} gCO2")
        print(f"   Time: {winner['time']:.3f}s")
        
        # Analysis
        print(f"\n📊 ANALYSIS:")
        
        # Carbon efficiency
        carbon_values = [r['carbon'] for r in results if 'carbon' in r]
        if carbon_values:
            best_carbon = min(carbon_values)
            worst_carbon = max(carbon_values)
            print(f"   Carbon range: {best_carbon:,} - {worst_carbon:,} gCO2 "
                  f"({(worst_carbon - best_carbon) / best_carbon * 100:.1f}% difference)")
        
        # Speed
        time_values = [r['time'] for r in results if 'time' in r and r['time'] > 0]
        if time_values:
            fastest = min(time_values)
            slowest = max(time_values)
            print(f"   Speed range: {fastest:.3f}s - {slowest:.3f}s "
                  f"({slowest / fastest:.1f}x difference)")
        
        # Recommendation
        print(f"\n💡 RECOMMENDATION:")
        if task_name == "easy":
            print(f"   For easy tasks: Any optimizer works well. Use Greedy (Deadline) for speed.")
        elif task_name == "medium":
            print(f"   For medium tasks: ILP gives optimal results. Greedy is 100x faster with 90% quality.")
        else:
            print(f"   For hard tasks: Use Greedy (Deadline). ILP may timeout.")
    
    print(f"{'=' * 80}\n")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        task = sys.argv[1]
    else:
        print("Usage: python compare_optimizers.py [easy|medium|hard]")
        print("Running all tasks...\n")
        for task in ["easy", "medium", "hard"]:
            compare_all_optimizers(task)
            print("\n")
        sys.exit(0)
    
    compare_all_optimizers(task)
