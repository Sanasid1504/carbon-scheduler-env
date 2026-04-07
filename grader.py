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


# ── Score bounds ─────────────────────────────────────────────────────────────
# Validator requires scores STRICTLY between 0 and 1 (not 0.0, not 1.0).
_SCORE_MIN = 1e-6
_SCORE_MAX = 1.0 - 1e-6


def _clamp(score: float) -> float:
    """Clamp a score to strictly (0, 1) as required by the validator."""
    return max(_SCORE_MIN, min(_SCORE_MAX, float(score)))


# ── Task registry ─────────────────────────────────────────────────────────────
# All three tasks must be present so the validator finds >= 3 graders.
TASKS = ["easy", "medium", "hard"]


def grade_task(task_name: str, action_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Grade an agent's performance on a specific task.

    Args:
        task_name:   Name of task — one of "easy", "medium", "hard"
        action_dict: Agent's action as dict with 'schedule' key

    Returns:
        Dict with score (strictly in (0,1)), metrics, and feedback
    """
    # ── Load config ───────────────────────────────────────────────────────────
    with open("openenv.yaml", "r") as f:
        config = yaml.safe_load(f)

    if task_name not in config["tasks"]:
        return {
            "score": _SCORE_MIN,          # never 0.0
            "error": f"Unknown task: {task_name}",
            "feedback": "Task not found",
            "task": task_name,
            "difficulty": 0,
        }

    task_config = config["tasks"][task_name]["config"]

    # ── Create environment ────────────────────────────────────────────────────
    env = SchedulerEnv(task_config, seed=42, use_real_carbon=False)
    obs = env.reset()

    # ── Parse action ──────────────────────────────────────────────────────────
    try:
        schedule_items = [
            ScheduleItem(job_id=item["job_id"], start_time=item["start_time"])
            for item in action_dict.get("schedule", [])
        ]
        action = Action(schedule=schedule_items)
    except Exception as e:
        return {
            "score": _SCORE_MIN,
            "error": f"Invalid action format: {e}",
            "feedback": "Action must be a dict with a 'schedule' list of {job_id, start_time} items.",
            "task": task_name,
            "difficulty": config["tasks"][task_name]["difficulty"],
        }

    # ── Execute action ────────────────────────────────────────────────────────
    try:
        obs, reward, done, info = env.step(action)
    except Exception as e:
        return {
            "score": _SCORE_MIN,
            "error": f"Execution error: {e}",
            "feedback": "Action caused an environment error.",
            "task": task_name,
            "difficulty": config["tasks"][task_name]["difficulty"],
        }

    # ── Compute metrics ───────────────────────────────────────────────────────
    metrics_analyzer = SchedulerMetrics(obs, action)
    metrics = metrics_analyzer.compute_all_metrics()

    # compute_score may return exactly 0.0 or 1.0 — clamp both ends.
    raw_score = compute_score(metrics)
    score     = _clamp(raw_score)

    # ── Generate feedback ─────────────────────────────────────────────────────
    feedback = []

    if metrics["completion_rate"] < 1.0:
        unscheduled = metrics["jobs_total"] - metrics["jobs_scheduled"]
        feedback.append(f"⚠ {unscheduled} jobs unscheduled")
    else:
        feedback.append("✓ All jobs scheduled")

    if metrics["deadline_misses"] > 0:
        feedback.append(f"⚠ {metrics['deadline_misses']} deadline misses")
    else:
        feedback.append("✓ No deadline misses")

    if metrics["capacity_violations"] > 0:
        feedback.append(f"⚠ {metrics['capacity_violations']} capacity violations")
    else:
        feedback.append("✓ No capacity violations")

    avg_carbon = metrics["average_carbon_per_job"]
    if avg_carbon < 500:
        feedback.append("✓ Excellent carbon efficiency")
    elif avg_carbon < 800:
        feedback.append("○ Good carbon efficiency")
    elif avg_carbon < 1200:
        feedback.append("○ Moderate carbon efficiency")
    else:
        feedback.append("⚠ High carbon emissions")

    return {
        "score": score,                  # strictly in (0, 1)
        "reward": reward.total,
        "metrics": {
            "total_carbon_gco2":    metrics["total_carbon_gco2"],
            "completion_rate":      metrics["completion_rate"],
            "deadline_misses":      metrics["deadline_misses"],
            "capacity_violations":  metrics["capacity_violations"],
            "average_utilization":  metrics["average_utilization"],
            "jobs_scheduled":       metrics["jobs_scheduled"],
            "jobs_total":           metrics["jobs_total"],
        },
        "feedback": " | ".join(feedback),
        "task":       task_name,
        "difficulty": config["tasks"][task_name]["difficulty"],
    }


def grade_all_tasks(actions: Dict[str, Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Grade agent performance across ALL three tasks.

    The validator requires at least 3 tasks with graders.  This function
    always grades all three — if an action isn't provided for a task it
    uses an empty schedule (which gets a low-but-valid score).

    Args:
        actions: Optional dict mapping task_name → action_dict.
                 Missing tasks receive an empty schedule.

    Returns:
        Dict with overall score and per-task results.
    """
    if actions is None:
        actions = {}

    results      = {}
    total_score  = 0.0

    for task_name in TASKS:                          # always iterates all 3
        action_dict = actions.get(task_name, {"schedule": []})
        result      = grade_task(task_name, action_dict)
        results[task_name] = result
        total_score += result["score"]

    overall_score = _clamp(total_score / len(TASKS))

    return {
        "overall_score":    overall_score,           # strictly in (0, 1)
        "tasks_completed":  len(TASKS),              # always 3
        "task_results":     results,
        "summary": (
            f"Completed {len(TASKS)}/3 tasks with "
            f"average score {overall_score:.4f}"
        ),
    }


# ── Self-test ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 70)
    print("GRADER SELF-TEST")
    print("=" * 70)

    # 1. Empty schedule — should give low-but-valid score (not 0.0)
    print("\n1. Empty schedule (score must be > 0.0) ...")
    r = grade_task("easy", {"schedule": []})
    assert 0 < r["score"] < 1, f"Score out of range: {r['score']}"
    print(f"   Score: {r['score']:.6f}  ✓")

    # 2. All three tasks via grade_all_tasks — must find 3 graders
    print("\n2. grade_all_tasks with no actions (3 tasks, all scores in (0,1)) ...")
    all_r = grade_all_tasks()
    assert all_r["tasks_completed"] == 3, "Expected 3 tasks"
    for tn, tr in all_r["task_results"].items():
        assert 0 < tr["score"] < 1, f"{tn} score out of range: {tr['score']}"
        print(f"   {tn:8s}  score={tr['score']:.6f}  ✓")
    print(f"   overall  score={all_r['overall_score']:.6f}  ✓")

    # 3. Greedy optimizer on medium — score should be meaningfully high
    print("\n3. Greedy optimizer on medium task ...")
    from optimizer.greedy import GreedyOptimizer

    with open("openenv.yaml") as f:
        cfg = yaml.safe_load(f)

    env = SchedulerEnv(cfg["tasks"]["medium"]["config"], seed=42, use_real_carbon=False)
    obs = env.reset()
    action = GreedyOptimizer(obs).solve()
    adict  = {"schedule": [{"job_id": i.job_id, "start_time": i.start_time}
                            for i in action.schedule]}

    r = grade_task("medium", adict)
    assert 0 < r["score"] < 1, f"Score out of range: {r['score']}"
    print(f"   Score:    {r['score']:.6f}  ✓")
    print(f"   Feedback: {r['feedback']}")
    print(f"   Carbon:   {r['metrics']['total_carbon_gco2']:,} gCO₂")

    # 4. Score boundary guard — artificially trigger edge values
    print("\n4. Boundary clamp guard ...")
    assert _clamp(0.0)   > 0.0,  "0.0 not clamped up"
    assert _clamp(1.0)   < 1.0,  "1.0 not clamped down"
    assert _clamp(-5.0)  > 0.0,  "negative not clamped"
    assert _clamp(99.0)  < 1.0,  "oversize not clamped"
    print("   All edge cases clamped correctly  ✓")

    print("\n" + "=" * 70)
    print("ALL CHECKS PASSED — safe to resubmit.")
    print("=" * 70)