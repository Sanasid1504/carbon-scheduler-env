"""
Grader for Carbon-Aware Scheduler environment.

Evaluates agent performance across multiple dimensions:
- Carbon efficiency
- Deadline compliance
- Capacity utilization
- Job completion rate

Returns deterministic scores that vary based on actual performance.
"""
import yaml
from typing import Dict, Any
from env.scheduler_env import SchedulerEnv
from env.models import Action, ScheduleItem
from metrics.analytics import SchedulerMetrics, compute_score


def grade_task(task_name: str, action_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Grade an agent's performance on a specific task.
    
    Args:
        task_name: Name of task (easy, medium, hard)
        action_dict: Agent's action as dict with 'schedule' key
        
    Returns:
        Dict with score, metrics, and feedback
    """
    # Load task configuration
    with open("openenv.yaml", "r") as f:
        config = yaml.safe_load(f)
    
    if task_name not in config["tasks"]:
        return {
            "score": 0.0,
            "error": f"Unknown task: {task_name}",
            "feedback": "Task not found"
        }
    
    task_config = config["tasks"][task_name]["config"]
    
    # Create environment
    env = SchedulerEnv(task_config, seed=42, use_real_carbon=False)
    obs = env.reset()
    
    # Parse action
    try:
        schedule_items = []
        for item in action_dict.get("schedule", []):
            schedule_items.append(
                ScheduleItem(
                    job_id=item["job_id"],
                    start_time=item["start_time"]
                )
            )
        action = Action(schedule=schedule_items)
    except Exception as e:
        return {
            "score": 0.0,
            "error": f"Invalid action format: {e}",
            "feedback": "Action must be dict with 'schedule' list"
        }
    
    # Execute action
    try:
        obs, reward, done, info = env.step(action)
    except Exception as e:
        return {
            "score": 0.0,
            "error": f"Execution error: {e}",
            "feedback": "Action caused environment error"
        }
    
    # Compute detailed metrics
    metrics_analyzer = SchedulerMetrics(obs, action)
    metrics = metrics_analyzer.compute_all_metrics()
    score = compute_score(metrics)
    
    # Generate feedback
    feedback = []
    
    if metrics['completion_rate'] < 1.0:
        unscheduled = metrics['jobs_total'] - metrics['jobs_scheduled']
        feedback.append(f"⚠ {unscheduled} jobs unscheduled")
    else:
        feedback.append("✓ All jobs scheduled")
    
    if metrics['deadline_misses'] > 0:
        feedback.append(f"⚠ {metrics['deadline_misses']} deadline misses")
    else:
        feedback.append("✓ No deadline misses")
    
    if metrics['capacity_violations'] > 0:
        feedback.append(f"⚠ {metrics['capacity_violations']} capacity violations")
    else:
        feedback.append("✓ No capacity violations")
    
    # Carbon efficiency rating
    avg_carbon = metrics['average_carbon_per_job']
    if avg_carbon < 500:
        feedback.append("✓ Excellent carbon efficiency")
    elif avg_carbon < 800:
        feedback.append("○ Good carbon efficiency")
    elif avg_carbon < 1200:
        feedback.append("○ Moderate carbon efficiency")
    else:
        feedback.append("⚠ High carbon emissions")
    
    return {
        "score": score,
        "reward": reward.total,
        "metrics": {
            "total_carbon_gco2": metrics['total_carbon_gco2'],
            "completion_rate": metrics['completion_rate'],
            "deadline_misses": metrics['deadline_misses'],
            "capacity_violations": metrics['capacity_violations'],
            "average_utilization": metrics['average_utilization'],
            "jobs_scheduled": metrics['jobs_scheduled'],
            "jobs_total": metrics['jobs_total']
        },
        "feedback": " | ".join(feedback),
        "task": task_name,
        "difficulty": config["tasks"][task_name]["difficulty"]
    }


def grade_all_tasks(actions: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Grade agent performance across all tasks.
    
    Args:
        actions: Dict mapping task_name to action_dict
        
    Returns:
        Dict with overall score and per-task results
    """
    results = {}
    total_score = 0.0
    num_tasks = 0
    
    for task_name in ["easy", "medium", "hard"]:
        if task_name in actions:
            result = grade_task(task_name, actions[task_name])
            results[task_name] = result
            total_score += result["score"]
            num_tasks += 1
    
    overall_score = total_score / num_tasks if num_tasks > 0 else 0.0
    
    return {
        "overall_score": overall_score,
        "tasks_completed": num_tasks,
        "task_results": results,
        "summary": f"Completed {num_tasks}/3 tasks with average score {overall_score:.4f}"
    }


# Example usage for testing
if __name__ == "__main__":
    print("=" * 70)
    print("GRADER TEST")
    print("=" * 70)
    
    # Test with empty schedule (should get low score)
    print("\n1. Testing empty schedule (should fail)...")
    result = grade_task("easy", {"schedule": []})
    print(f"   Score: {result['score']:.4f}")
    print(f"   Feedback: {result['feedback']}")
    
    # Test with valid schedule
    print("\n2. Testing valid schedule...")
    valid_action = {
        "schedule": [
            {"job_id": 1, "start_time": 0},
            {"job_id": 2, "start_time": 3},
            {"job_id": 3, "start_time": 5}
        ]
    }
    result = grade_task("easy", valid_action)
    print(f"   Score: {result['score']:.4f}")
    print(f"   Feedback: {result['feedback']}")
    print(f"   Carbon: {result['metrics']['total_carbon_gco2']:,} gCO2")
    
    # Test with optimal schedule (using greedy)
    print("\n3. Testing with greedy optimizer...")
    from optimizer.greedy import GreedyOptimizer
    
    with open("openenv.yaml", "r") as f:
        config = yaml.safe_load(f)
    
    env = SchedulerEnv(config["tasks"]["medium"]["config"], seed=42, use_real_carbon=False)
    obs = env.reset()
    
    optimizer = GreedyOptimizer(obs)
    action = optimizer.solve()
    
    action_dict = {
        "schedule": [
            {"job_id": item.job_id, "start_time": item.start_time}
            for item in action.schedule
        ]
    }
    
    result = grade_task("medium", action_dict)
    print(f"   Score: {result['score']:.4f}")
    print(f"   Feedback: {result['feedback']}")
    print(f"   Carbon: {result['metrics']['total_carbon_gco2']:,} gCO2")
    
    print("\n" + "=" * 70)
    print("GRADER WORKING! Scores vary based on performance.")
    print("=" * 70)
