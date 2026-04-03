"""
OpenAI-compatible inference script for Carbon-Aware Scheduler.

The LLM agent receives:
  - A list of jobs (id, duration, deadline, priority)
  - Carbon intensity per time slot (gCO2/kWh)
  - Capacity limit and time horizon

The LLM agent must output:
  - A JSON schedule: {"schedule": [{"job_id": int, "start_time": int}, ...]}

Logging format: [START] → [STEP] → [END]
"""
import os
import json
import yaml
import time
from openai import OpenAI
from env.scheduler_env import SchedulerEnv
from env.models import Action, ScheduleItem
from optimizer.greedy import GreedyOptimizer
from metrics.analytics import SchedulerMetrics, compute_score
from grader import grade_task


# ─────────────────────────────────────────────
# Prompt construction
# ─────────────────────────────────────────────

def create_system_prompt() -> str:
    return """\
You are a carbon-aware cloud workload scheduler.

Your job is to assign compute jobs to time slots to:
  1. Minimize total carbon emissions (carbon_intensity × duration)
  2. Meet every job's deadline  (start_time + duration <= deadline)
  3. Never exceed the capacity limit at any time slot
  4. Schedule every job exactly once

OUTPUT FORMAT — return ONLY valid JSON, nothing else:
{
  "schedule": [
    {"job_id": <int>, "start_time": <int>},
    ...
  ]
}

Rules:
- start_time >= 0
- start_time + duration <= deadline
- At any time slot t, the number of jobs running must not exceed capacity
- Every job must appear exactly once in the schedule
- Choose start times that fall in low carbon_intensity windows"""


def create_user_prompt(obs) -> str:
    lines = []
    lines.append("=== SCHEDULING PROBLEM ===\n")

    lines.append(f"TIME HORIZON : {obs.time_horizon} slots (0 – {obs.time_horizon - 1})")
    lines.append(f"CAPACITY     : {obs.capacity} concurrent jobs max\n")

    lines.append("JOBS:")
    lines.append(f"  {'id':>3}  {'duration':>8}  {'deadline':>8}  {'priority':>8}")
    lines.append(f"  {'--':>3}  {'--------':>8}  {'--------':>8}  {'--------':>8}")
    for job in obs.jobs:
        lines.append(
            f"  {job.id:>3}  {job.duration:>8}  {job.deadline:>8}  {job.priority:>8}"
        )

    lines.append("\nCARBON INTENSITY (gCO2/kWh) per time slot:")
    for i in range(0, len(obs.carbon_intensity), 8):
        chunk = obs.carbon_intensity[i:i + 8]
        slot_labels = "  ".join(f"[{i+j:02d}]={v}" for j, v in enumerate(chunk))
        lines.append(f"  {slot_labels}")

    lines.append("\nLow-carbon windows (top 6 cheapest single slots):")
    sorted_slots = sorted(enumerate(obs.carbon_intensity), key=lambda x: x[1])
    for slot, val in sorted_slots[:6]:
        lines.append(f"  slot {slot:02d} → {val} gCO2/kWh")

    lines.append("\nReturn ONLY the JSON schedule.")
    return "\n".join(lines)


# ─────────────────────────────────────────────
# Response parsing  (with retry on bad JSON)
# ─────────────────────────────────────────────

def parse_response(text: str) -> Action:
    """Extract JSON from LLM response and build Action."""
    # Strip markdown code fences if present
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]

    start = text.find("{")
    end   = text.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError("No JSON object found in response")

    data = json.loads(text[start:end])
    items = []
    for entry in data.get("schedule", []):
        items.append(ScheduleItem(job_id=entry["job_id"], start_time=entry["start_time"]))
    return Action(schedule=items)


def greedy_fallback(obs) -> Action:
    """Use greedy optimizer as fallback when LLM fails."""
    return GreedyOptimizer(obs).solve()


# ─────────────────────────────────────────────
# Main inference
# ─────────────────────────────────────────────

def run_inference(task_name: str = "medium") -> float:
    print(f"[START] Carbon-Aware Scheduler Inference  |  task={task_name}")

    # ── Config ──────────────────────────────
    api_key    = os.getenv("OPENAI_API_KEY",  "dummy-key")
    api_base   = os.getenv("API_BASE_URL",    "https://api.openai.com/v1")
    model_name = os.getenv("MODEL_NAME",      "gpt-4")

    print(f"[STEP] Model : {model_name}")
    print(f"[STEP] API   : {api_base}")

    # ── Environment ─────────────────────────
    print(f"[STEP] Loading task: {task_name}")
    with open("openenv.yaml") as f:
        cfg = yaml.safe_load(f)
    task_config = cfg["tasks"][task_name]["config"]

    env = SchedulerEnv(task_config, seed=42, use_real_carbon=False)
    obs = env.reset()

    print(f"[STEP] Environment ready")
    print(f"       Jobs     : {len(obs.jobs)}")
    print(f"       Capacity : {obs.capacity}")
    print(f"       Horizon  : {obs.time_horizon} slots")
    print(f"       Carbon   : min={min(obs.carbon_intensity)} "
          f"max={max(obs.carbon_intensity)} "
          f"avg={sum(obs.carbon_intensity)//len(obs.carbon_intensity)} gCO2/kWh")

    # ── Build prompts ────────────────────────
    system_prompt = create_system_prompt()
    user_prompt   = create_user_prompt(obs)

    print(f"\n[STEP] Prompt sent to LLM")
    print("─" * 60)
    print(user_prompt)
    print("─" * 60)

    # ── Call LLM ────────────────────────────
    print(f"\n[STEP] Calling {model_name} ...")
    t0 = time.time()
    llm_raw = None
    action  = None

    try:
        client = OpenAI(api_key=api_key, base_url=api_base)
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            temperature=0.0,      # deterministic
            max_tokens=1024,
            seed=42,              # reproducible (supported by some providers)
        )
        llm_raw = response.choices[0].message.content
        elapsed = time.time() - t0

        print(f"[STEP] LLM responded in {elapsed:.2f}s")
        print(f"\n[STEP] Raw LLM output:")
        print("─" * 60)
        print(llm_raw)
        print("─" * 60)

        action = parse_response(llm_raw)
        print(f"[STEP] Parsed {len(action.schedule)} scheduled jobs from LLM output")

    except Exception as e:
        elapsed = time.time() - t0
        print(f"[STEP] LLM call failed after {elapsed:.2f}s: {e}")
        print(f"[STEP] Falling back to greedy optimizer")
        action = greedy_fallback(obs)
        print(f"[STEP] Greedy fallback scheduled {len(action.schedule)} jobs")

    # ── Execute in environment ───────────────
    print(f"\n[STEP] Executing schedule in environment")
    obs_out, reward, done, info = env.step(action)

    print(f"[STEP] Execution complete")
    print(f"       Reward              : {reward.total:.4f}")
    print(f"       Carbon penalty      : {reward.carbon_penalty:.4f}")
    print(f"       Deadline penalty    : {reward.deadline_penalty:.4f}")
    print(f"       Capacity penalty    : {reward.capacity_penalty:.4f}")
    print(f"       Unscheduled penalty : {reward.unscheduled_penalty:.4f}")
    print(f"       Completion bonus    : {reward.completion_bonus:.4f}")

    # ── Metrics ─────────────────────────────
    print(f"\n[STEP] Computing metrics")
    m = SchedulerMetrics(obs_out, action).compute_all_metrics()
    score = compute_score(m)

    print(f"       Score              : {score:.4f}")
    print(f"       Jobs scheduled     : {m['jobs_scheduled']} / {m['jobs_total']}")
    print(f"       Completion rate    : {m['completion_rate']:.1%}")
    print(f"       Total carbon       : {m['total_carbon_gco2']:,} gCO2")
    print(f"       Avg carbon/job     : {m['average_carbon_per_job']:.1f} gCO2")
    print(f"       Deadline misses    : {m['deadline_misses']}")
    print(f"       Capacity violations: {m['capacity_violations']}")
    print(f"       Avg utilization    : {m['average_utilization']:.1%}")

    # ── Grader ──────────────────────────────
    print(f"\n[STEP] Running grader")
    action_dict = {
        "schedule": [
            {"job_id": item.job_id, "start_time": item.start_time}
            for item in action.schedule
        ]
    }
    grade = grade_task(task_name, action_dict)
    print(f"       Grader score : {grade['score']:.4f}")
    print(f"       Feedback     : {grade['feedback']}")

    # ── Save results ─────────────────────────
    results = {
        "task":                   task_name,
        "model":                  model_name,
        "score":                  score,
        "grader_score":           grade["score"],
        "reward":                 reward.total,
        "inference_time_seconds": elapsed,
        "llm_raw_output":         llm_raw,
        "schedule":               action_dict["schedule"],
        "metrics":                m,
        "grader_feedback":        grade["feedback"],
    }

    out_file = f"results_{task_name}.json"
    with open(out_file, "w") as f:
        json.dump(results, f, indent=2)

    # ── Final summary ────────────────────────
    print(f"\n[END] Inference complete")
    print("=" * 70)
    print(f"  Task            : {task_name}")
    print(f"  Model           : {model_name}")
    print(f"  Score           : {score:.4f}")
    print(f"  Grader score    : {grade['score']:.4f}")
    print(f"  Reward          : {reward.total:.4f}")
    print(f"  Jobs scheduled  : {m['jobs_scheduled']} / {m['jobs_total']}")
    print(f"  Total carbon    : {m['total_carbon_gco2']:,} gCO2")
    print(f"  Deadline misses : {m['deadline_misses']}")
    print(f"  Results saved   : {out_file}")
    print("=" * 70)

    return score


if __name__ == "__main__":
    import sys
    task = sys.argv[1] if len(sys.argv) > 1 else "medium"
    if task not in ["easy", "medium", "hard"]:
        print(f"Usage: python inference.py [easy|medium|hard]")
        sys.exit(1)
    score = run_inference(task)
    sys.exit(0 if score >= 0.5 else 1)
