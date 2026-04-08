#!/usr/bin/env python3
"""Test individual task grader functions."""
from grader import grade_easy, grade_medium, grade_hard

print("Testing individual task graders...")
print("=" * 60)

# Test empty schedules
print("\n1. Testing with empty schedules:")
for func, name in [(grade_easy, "easy"), (grade_medium, "medium"), (grade_hard, "hard")]:
    result = func({"schedule": []})
    score = result["score"]
    print(f"  {name:8s}: score={score} (valid: {0 < score < 1})")
    assert 0 < score < 1, f"{name} score out of range: {score}"

# Test with None
print("\n2. Testing with None:")
for func, name in [(grade_easy, "easy"), (grade_medium, "medium"), (grade_hard, "hard")]:
    result = func(None)
    score = result["score"]
    print(f"  {name:8s}: score={score} (valid: {0 < score < 1})")
    assert 0 < score < 1, f"{name} score out of range: {score}"

# Test with greedy optimizer
print("\n3. Testing with greedy optimizer:")
try:
    import yaml
    from optimizer.greedy import GreedyOptimizer
    from env.scheduler_env import SchedulerEnv
    
    with open("openenv.yaml") as f:
        config = yaml.safe_load(f)
    
    for task_name, func in [("easy", grade_easy), ("medium", grade_medium), ("hard", grade_hard)]:
        env = SchedulerEnv(config["tasks"][task_name]["config"], seed=42, use_real_carbon=False)
        obs = env.reset()
        action = GreedyOptimizer(obs).solve()
        action_dict = {"schedule": [{"job_id": i.job_id, "start_time": i.start_time}
                                     for i in action.schedule]}
        result = func(action_dict)
        score = result["score"]
        print(f"  {task_name:8s}: score={score} (valid: {0 < score < 1})")
        assert 0 < score < 1, f"{task_name} score out of range: {score}"
except ImportError as e:
    print(f"  [SKIP] {e}")

print("\n" + "=" * 60)
print("ALL TESTS PASSED!")
print("=" * 60)
