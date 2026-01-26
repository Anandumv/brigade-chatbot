import os
import subprocess
import json
import time

def run_test(test_file, env):
    print(f"Running {test_file}...")
    try:
        # Add backend and vendor to PYTHONPATH
        my_env = os.environ.copy()
        my_env.update(env)
        backend_dir = os.path.abspath("backend")
        vendor_dir = os.path.abspath("backend/vendor")
        my_env["PYTHONPATH"] = f"{my_env.get('PYTHONPATH', '')}:{backend_dir}:{vendor_dir}"
        
        start = time.time()
        result = subprocess.run(
            ["backend/venv/bin/python3", test_file],
            capture_output=True,
            text=True,
            env=my_env,
            timeout=180 # 3 min timeout per test
        )
        duration = time.time() - start
        
        return {
            "file": test_file,
            "passed": result.returncode == 0,
            "duration": round(duration, 2),
            "stdout": result.stdout[-1000:], # Last 1000 chars
            "stderr": result.stderr[-1000:]
        }
    except subprocess.TimeoutExpired:
        return {"file": test_file, "passed": False, "error": "Timeout", "duration": 180}
    except Exception as e:
        return {"file": test_file, "passed": False, "error": str(e), "duration": 0}

def main():
    # Load env
    env_vars = {
        "PIXELTABLE_DB_URL": "sqlite:///./test_pixeltable.db",
        "USE_PIXELTABLE": "true",
        "ENVIRONMENT": "testing"
    }
    if os.path.exists("backend/.env"):
        with open("backend/.env", "r") as f:
            for line in f:
                if "=" in line and not line.startswith("#"):
                    k, v = line.strip().split("=", 1)
                    env_vars[k] = v
    
    # Start background server
    print("Starting background server on port 8000...")
    backend_dir = os.path.abspath("backend")
    server_log = open("test_server.log", "w")
    server_process = subprocess.Popen(
        ["venv/bin/python3", "-m", "uvicorn", "main:app", "--port", "8000", "--host", "0.0.0.0"],
        cwd=backend_dir,
        env={**os.environ, **env_vars, "PYTHONPATH": f"{backend_dir}:{os.path.join(backend_dir, 'vendor')}"},
        stdout=server_log,
        stderr=server_log
    )
    
    # Wait for server to be ready and log output
    print("Waiting for server to start (20s)...")
    time.sleep(20)
    
    # Simple check if port is open
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    is_open = sock.connect_ex(('127.0.0.1', 8000)) == 0
    sock.close()
    if is_open:
        print("Server is listening on port 8000.")
    else:
        print("WARNING: Server does not appear to be listening on 8000!")
        with open("test_server.log", "r") as f:
            print("--- Server Log Start ---")
            print(f.read())
            print("--- Server Log End ---")
    
    test_files = [
        "backend/test_2bhk_consistency.py",
        "backend/test_arman_fixes.py",
        "backend/test_calendar_reminders.py",
        "backend/test_comprehensive_suite.py",
        "backend/test_continuous_conversation.py",
        "backend/test_conversation_coaching.py",
        "backend/test_conversation_flows.py",
        "backend/test_conversational_flows.py",
        "backend/test_corner_cases.py",
        "backend/test_dynamic_chips.py",
        "backend/test_filters_explicit.py",
        "backend/test_flow_output.py",
        "backend/test_flows.py",
        "backend/test_full_lifecycle.py",
        "backend/test_full_spectrum.py",
        "backend/test_intelligent_fallback.py",
        "backend/test_proactive_nudger.py",
        "backend/test_project_selection.py",
        "backend/test_radius_pivot.py",
        "backend/test_redis_assist.py",
        "backend/test_routing_fix.py",
        "backend/test_scheduling.py",
        "backend/test_sentiment_analysis.py",
        "backend/test_sentiment_simple.py",
        "backend/test_user_profiles.py",
        "backend/tests/test_production_readiness.py",
        "backend/tests/test_sales_copilot.py"
    ]
    
    results = []
    try:
        for tf in test_files:
            if os.path.exists(tf):
                res = run_test(tf, env_vars)
                results.append(res)
    finally:
        print("Stopping background server...")
        server_process.terminate()
        try:
            server_process.wait(timeout=5)
        except:
            server_process.kill()
        server_log.close()
            
    with open("all_test_results.json", "w") as f:
        json.dump(results, f, indent=2)
        
    print(f"\nCompleted {len(results)} tests.")
    passed = sum(1 for r in results if r["passed"])
    print(f"PASSED: {passed}/{len(results)}")

if __name__ == "__main__":
    main()
