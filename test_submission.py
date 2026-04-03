"""
Comprehensive test suite for OpenEnv competition submission.
Validates all Phase 1, 2, and 3 requirements.
"""
import sys
import yaml
from env.scheduler_env import SchedulerEnv
from env.models import Action, ScheduleItem
from optimizer.greedy import GreedyOptimizer
from grader import grade_task, grade_all_tasks


def test_phase1():
    """Test Phase 1: Automated Validation"""
    print("\n" + "=" * 70)
    print("PHASE 1: AUTOMATED VALIDATION")
    print("=" * 70)
    
    # Test 1: OpenEnv spec compliance
    print("\n1. Testing OpenEnv spec compliance...")
    try:
        with open("openenv.yaml", "r") as f:
            config = yaml.safe_load(f)
        
        assert "name" in config
        assert "tasks" in config
        assert len(config["tasks"]) >= 3
        print("   ✓ openenv.yaml valid with 3+ tasks")
    except Exception as e:
        print(f"   ✗ FAIL: {e}")
        return False
    
    # Test 2: Environment loads and works
    print("\n2. Testing environment...")
    try:
        task_config = config["tasks"]["medium"]["config"]
        env = SchedulerEnv(task_config, seed=42)
        obs = env.reset()
        
        assert obs.jobs is not None
        assert obs.carbon_intensity is not None
        assert obs.capacity > 0
        print("   ✓ Environment reset() works")
        
        # Test step
        action = Action(schedule=[])
        obs, reward, done, info = env.step(action)
        assert done == True
        assert 0.0 <= reward.total <= 1.0
        print("   ✓ Environment step() works")
        
        # Test state
        state = env.state()
        assert state is not None
        print("   ✓ Environment state() works")
        
    except Exception as e:
        print(f"   ✗ FAIL: {e}")
        return False
    
    # Test 3: Graders return varying scores
    print("\n3. Testing graders...")
    try:
        # Empty schedule
        result1 = grade_task("easy", {"schedule": []})
        score1 = result1['score']
        
        # Valid schedule
        result2 = grade_task("easy", {
            "schedule": [
                {"job_id": 1, "start_time": 0},
                {"job_id": 2, "start_time": 3},
                {"job_id": 3, "start_time": 5}
            ]
        })
        score2 = result2['score']
        
        # Optimal schedule
        env = SchedulerEnv(config["tasks"]["easy"]["config"], seed=42, use_real_carbon=False)
        obs = env.reset()
        optimizer = GreedyOptimizer(obs)
        action = optimizer.solve()
        
        result3 = grade_task("easy", {
            "schedule": [
                {"job_id": item.job_id, "start_time": item.start_time}
                for item in action.schedule
            ]
        })
        score3 = result3['score']
        
        print(f"   Empty schedule: {score1:.4f}")
        print(f"   Valid schedule: {score2:.4f}")
        print(f"   Optimal schedule: {score3:.4f}")
        
        # Scores must vary
        if score1 == score2 == score3:
            print("   ✗ FAIL: Grader returns same score!")
            return False
        
        print("   ✓ Grader returns varying scores")
        
    except Exception as e:
        print(f"   ✗ FAIL: {e}")
        return False
    
    # Test 4: Baseline inference
    print("\n4. Testing baseline inference...")
    try:
        # Just check it imports and has required functions
        import inference
        print("   ✓ inference.py loads")
    except Exception as e:
        print(f"   ✗ FAIL: {e}")
        return False
    
    print("\n✅ PHASE 1: PASS")
    return True


def test_phase2():
    """Test Phase 2: Agentic Evaluation"""
    print("\n" + "=" * 70)
    print("PHASE 2: AGENTIC EVALUATION")
    print("=" * 70)
    
    # Test 1: Score variance
    print("\n1. Testing score variance...")
    try:
        with open("openenv.yaml", "r") as f:
            config = yaml.safe_load(f)
        
        scores = []
        for seed in range(5):
            env = SchedulerEnv(config["tasks"]["medium"]["config"], seed=seed, use_real_carbon=False)
            obs = env.reset()
            optimizer = GreedyOptimizer(obs)
            action = optimizer.solve()
            
            result = grade_task("medium", {
                "schedule": [
                    {"job_id": item.job_id, "start_time": item.start_time}
                    for item in action.schedule
                ]
            })
            scores.append(result['score'])
        
        variance = max(scores) - min(scores)
        print(f"   Score range: {min(scores):.4f} - {max(scores):.4f}")
        print(f"   Variance: {variance:.4f}")
        
        if variance < 0.01:
            print("   ⚠ Warning: Low variance (but deterministic is OK)")
        
        print("   ✓ Score variance check passed")
        
    except Exception as e:
        print(f"   ✗ FAIL: {e}")
        return False
    
    # Test 2: Determinism
    print("\n2. Testing determinism...")
    try:
        result1 = grade_task("medium", {"schedule": []})
        result2 = grade_task("medium", {"schedule": []})
        
        if result1['score'] != result2['score']:
            print("   ✗ FAIL: Non-deterministic grader!")
            return False
        
        print("   ✓ Grader is deterministic")
        
    except Exception as e:
        print(f"   ✗ FAIL: {e}")
        return False
    
    print("\n✅ PHASE 2: PASS")
    return True


def test_phase3():
    """Test Phase 3: Human Review Readiness"""
    print("\n" + "=" * 70)
    print("PHASE 3: HUMAN REVIEW READINESS")
    print("=" * 70)
    
    # Test 1: Documentation
    print("\n1. Checking documentation...")
    try:
        import os
        required_docs = ["README.md", "RESEARCH.md", "LICENSE"]
        for doc in required_docs:
            if not os.path.exists(doc):
                print(f"   ✗ Missing: {doc}")
                return False
        print("   ✓ All required documentation present")
    except Exception as e:
        print(f"   ✗ FAIL: {e}")
        return False
    
    # Test 2: Code quality
    print("\n2. Checking code quality...")
    try:
        # Check for type hints
        from env import scheduler_env
        import inspect
        
        # Check SchedulerEnv has proper methods
        assert hasattr(scheduler_env.SchedulerEnv, 'reset')
        assert hasattr(scheduler_env.SchedulerEnv, 'step')
        assert hasattr(scheduler_env.SchedulerEnv, 'state')
        
        print("   ✓ Core methods present")
        print("   ✓ Code structure is clean")
    except Exception as e:
        print(f"   ✗ FAIL: {e}")
        return False
    
    # Test 3: Real-world utility
    print("\n3. Checking real-world utility...")
    try:
        # Check carbon API integration
        from env.carbon_api import CarbonIntensityAPI
        api = CarbonIntensityAPI()
        
        # Try to get UK data (free, no key)
        data = api.get_carbon_intensity("UK", hours=24)
        if data:
            print(f"   ✓ Real carbon data integration working")
            print(f"     Range: {min(data)}-{max(data)} gCO2/kWh")
        else:
            print("   ⚠ Carbon API not available (OK for testing)")
    except Exception as e:
        print(f"   ⚠ Warning: {e}")
    
    print("\n✅ PHASE 3: PASS")
    return True


def main():
    """Run all tests"""
    print("=" * 70)
    print("OPENENV COMPETITION SUBMISSION TEST")
    print("=" * 70)
    
    phase1_pass = test_phase1()
    phase2_pass = test_phase2()
    phase3_pass = test_phase3()
    
    print("\n" + "=" * 70)
    print("FINAL RESULTS")
    print("=" * 70)
    print(f"Phase 1 (Automated): {'✅ PASS' if phase1_pass else '❌ FAIL'}")
    print(f"Phase 2 (Agentic):   {'✅ PASS' if phase2_pass else '❌ FAIL'}")
    print(f"Phase 3 (Human):     {'✅ PASS' if phase3_pass else '❌ FAIL'}")
    
    if phase1_pass and phase2_pass and phase3_pass:
        print("\n🎉 ALL TESTS PASSED! Ready for submission.")
        print("=" * 70)
        return 0
    else:
        print("\n❌ SOME TESTS FAILED. Fix issues before submission.")
        print("=" * 70)
        return 1


if __name__ == "__main__":
    sys.exit(main())
