"""
Grader for Carbon-Aware Scheduler environment.
Production-safe: always grades all 3 tasks, scores strictly in (0, 1).
"""
import math
import yaml
from typing import Dict, Any

from env.scheduler_env import SchedulerEnv
from env.models import Action, ScheduleItem
from metrics.analytics import SchedulerMetrics, compute_score

# ── Constants ─────────────────────────────────────────────────────────────────
TASKS = ["easy", "medium", "hard"]
_EPS  = 1e-6   # keeps scores strictly inside (0, 1)


# ── Safe clamp ────────────────────────────────────────────────────────────────
def _clamp(value: Any) -> float:
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


# ── Config loader ─────────────────────────────────────────────────────────────
def _load_config() -> Dict:
    with open("openenv.yaml", "r") as f:
        return yaml.safe_load(f)


# ── Single-task grader ────────────────────────────────────────────────────────
def grade_task(task_name: str, action_dict: Any = None) -> Dict[str, Any]:
    """
    Grade one task. Always returns a valid dict with a clamped score.
    """
    # Defensive normalisation
    if not isinstance(action_dict, dict):
        action_dict = {}
    raw_schedule = action_dict.get("schedule", [])
    if not isinstance(raw_schedule, list):
        raw_schedule = []

    # Load config
    try:
        config     = _load_config()
        task_cfg   = config["tasks"][task_name]["config"]
        difficulty = config["tasks"][task_name]["difficulty"]
    except Exception as e:
        return {
            "score": _fmt(_EPS), "reward": 0, "metrics": {},
            "feedback": f"Config error: {e}",
            "task": task_name, "difficulty": 0,
        }

    # Build environment
    try:
        env = SchedulerEnv(task_cfg, seed=42, use_real_carbon=False)
        obs = env.reset()
    except Exception as e:
        return {
            "score": _fmt(_EPS), "reward": 0, "metrics": {},
            "feedback": f"Env init error: {e}",
            "task": task_name, "difficulty": difficulty,
        }

    # Parse schedule items — skip any malformed entry silently
    schedule_items = []
    for item in raw_schedule:
        try:
            schedule_items.append(
                ScheduleItem(
                    job_id=int(item["job_id"]),
                    start_time=int(item["start_time"]),
                )
            )
        except Exception:
            continue

    # Execute action
    try:
        action = Action(schedule=schedule_items)
        obs, reward, done, info = env.step(action)
        reward_total = float(getattr(reward, "total", 0.0))
    except Exception as e:
        return {
            "score": _fmt(_EPS), "reward": 0, "metrics": {},
            "feedback": f"Execution error: {e}",
            "task": task_name, "difficulty": difficulty,
        }

    # Compute metrics & score
    try:
        metrics = SchedulerMetrics(obs, action).compute_all_metrics()
        score   = _clamp(compute_score(metrics))
    except Exception as e:
        return {
            "score": _fmt(_EPS), "reward": _fmt(reward_total), "metrics": {},
            "feedback": f"Metrics error: {e}",
            "task": task_name, "difficulty": difficulty,
        }

    # Build feedback
    parts = []
    total     = metrics.get("jobs_total", 0)
    completed = metrics.get("jobs_scheduled", 0)
    parts.append("✓ All jobs scheduled" if completed == total
                 else f"⚠ {total - completed} jobs unscheduled")

    misses = metrics.get("deadline_misses", 0)
    parts.append("✓ No deadline misses" if misses == 0
                 else f"⚠ {misses} deadline misses")

    viols = metrics.get("capacity_violations", 0)
    parts.append("✓ No capacity violations" if viols == 0
                 else f"⚠ {viols} capacity violations")

    avg_c = metrics.get("average_carbon_per_job", 0)
    if avg_c < 500:   parts.append("✓ Excellent carbon efficiency")
    elif avg_c < 800: parts.append("○ Good carbon efficiency")
    elif avg_c < 1200:parts.append("○ Moderate carbon efficiency")
    else:             parts.append("⚠ High carbon emissions")

    return {
        "score":   _fmt(score),
        "reward":  _fmt(reward_total),
        "metrics": {
            "total_carbon_gco2":   metrics.get("total_carbon_gco2", 0),
            "completion_rate":     _fmt(metrics.get("completion_rate", 0.0)),
            "deadline_misses":     metrics.get("deadline_misses", 0),
            "capacity_violations": metrics.get("capacity_violations", 0),
            "average_utilization": _fmt(metrics.get("average_utilization", 0.0)),
            "jobs_scheduled":      metrics.get("jobs_scheduled", 0),
            "jobs_total":          metrics.get("jobs_total", 0),
        },
        "feedback":   " | ".join(parts),
        "task":       task_name,
        "difficulty": difficulty,
    }


# ── Top-level entry point ─────────────────────────────────────────────────────
def grade(actions: Any = None) -> Dict[str, Any]:
    """
    Primary entry point — validator calls this function.
    Always grades all 3 tasks regardless of what is passed in.

    Args:
        actions: dict mapping task_name → action_dict, or None / malformed.

    Returns:
        {
            "overall_score":   float,   # strictly in (0, 1)
            "tasks_completed": 3,
            "task_results":    {"easy": {...}, "medium": {...}, "hard": {...}},
            "summary":         str,
        }
    """
    if not isinstance(actions, dict):
        actions = {}

    task_results = {}
    score_sum    = 0.0

    for task_name in TASKS:                           # always all 3
        result                  = grade_task(task_name, actions.get(task_name, {}))
        task_results[task_name] = result
        score_sum              += result["score"]

    overall = _clamp(score_sum / len(TASKS))

    return {
        "overall_score":   _fmt(overall),
        "tasks_completed": len(TASKS),                # always 3
        "task_results":    task_results,
        "summary":         f"Graded {len(TASKS)}/3 tasks — overall score {_fmt(overall)}",
    }


# ── Backward-compat alias ─────────────────────────────────────────────────────
def grade_all_tasks(actions: Any = None) -> Dict[str, Any]:
    return grade(actions)


# ── Task-specific grader wrappers for openenv.yaml ───────────────────────────
def grade_easy(action_dict: Any = None) -> Dict[str, Any]:
    """Grader for easy task - called by validator."""
    return grade_task("easy", action_dict)


def grade_medium(action_dict: Any = None) -> Dict[str, Any]:
    """Grader for medium task - called by validator."""
    return grade_task("medium", action_dict)


def grade_hard(action_dict: Any = None) -> Dict[str, Any]:
    """Grader for hard task - called by validator."""
    return grade_task("hard", action_dict)


# ── Self-test ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    print("=" * 60)
    print("GRADER SELF-TEST")
    print("=" * 60)

    failures = []

    def check(label: str, ok: bool) -> None:
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
        if not ok:
            failures.append(label)

    # 1. _clamp
    print("\n1. _clamp edge cases")
    check("clamp(0.0) > 0",          _clamp(0.0)            > 0)
    check("clamp(1.0) < 1",          _clamp(1.0)            < 1)
    check("clamp(None) > 0",         _clamp(None)           > 0)
    check("clamp(NaN) > 0",          _clamp(float("nan"))   > 0)
    check("clamp(-1) > 0",           _clamp(-1)             > 0)
    check("clamp(99) < 1",           _clamp(99)             < 1)

    # 2. grade() — no args
    print("\n2. grade() with no arguments")
    r = grade()
    check("tasks_completed == 3",    r["tasks_completed"] == 3)
    check("all 3 keys present",      all(t in r["task_results"] for t in TASKS))
    check("overall_score in (0,1)",  0 < r["overall_score"] < 1)
    for t in TASKS:
        s = r["task_results"][t]["score"]
        check(f"{t}: score in (0,1)", 0 < s < 1)

    # 3. grade() — empty dict
    print("\n3. grade({}) empty dict")
    r = grade({})
    check("tasks_completed == 3",    r["tasks_completed"] == 3)
    check("overall_score in (0,1)",  0 < r["overall_score"] < 1)

    # 4. grade() — malformed inputs
    print("\n4. grade() with malformed inputs")
    for bad in [None, "string", 42, [], False]:
        r = grade(bad)
        check(f"input={repr(bad)!s:10} → tasks_completed==3",
              r["tasks_completed"] == 3)

    # 5. Malformed schedule items
    print("\n5. Malformed schedule items")
    r = grade({
        "easy":   {"schedule": [{"bad": 1}, None, "oops", {"job_id": "x", "start_time": "y"}]},
        "medium": {"schedule": None},
        "hard":   None,
    })
    check("tasks_completed == 3",    r["tasks_completed"] == 3)
    for t in TASKS:
        s = r["task_results"][t]["score"]
        check(f"{t}: score in (0,1)", 0 < s < 1)

    # 6. Greedy optimizer
    print("\n6. Greedy optimizer on all tasks")
    try:
        from optimizer.greedy import GreedyOptimizer
        cfg = _load_config()
        for t in TASKS:
            env = SchedulerEnv(cfg["tasks"][t]["config"], seed=42, use_real_carbon=False)
            obs = env.reset()
            act = GreedyOptimizer(obs).solve()
            adict = {"schedule": [{"job_id": i.job_id, "start_time": i.start_time}
                                   for i in act.schedule]}
            res = grade_task(t, adict)
            check(f"{t}: score in (0,1)  [{res['score']}]", 0 < res["score"] < 1)
    except ImportError:
        print("  [SKIP] GreedyOptimizer not available in test env")

    print("\n" + "=" * 60)
    if failures:
        print(f"FAILED — {len(failures)} check(s):")
        for f in failures:
            print(f"  ✗ {f}")
        sys.exit(1)
    else:
        print("ALL CHECKS PASSED — safe to resubmit.")
    print("=" * 60)