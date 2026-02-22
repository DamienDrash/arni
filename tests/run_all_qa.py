
import sys
import subprocess
from pathlib import Path

def run_script(path: Path):
    print(f"\n🚀 Running {path.name}...")
    try:
        # Run in separate process to isolate sys.path logic
        subprocess.run(
            [sys.executable, str(path)],
            cwd=path.parent.parent, # Run from project root
            check=True,
            env={**sys.modules['os'].environ, "PYTHONPATH": str(path.parent.parent)}
        )
        print(f"✅ {path.name} PASSED")
        return True
    except subprocess.CalledProcessError:
        print(f"❌ {path.name} FAILED")
        return False

def main():
    root = Path(__file__).resolve().parents[1]
    
    scripts = [
        root / "tests" / "test_guardrails.py",
        root / "tests" / "run_evals.py",
        root / "tests" / "test_hybrid_search.py"
    ]
    
    failures = []
    for script in scripts:
        if script.exists():
            if not run_script(script):
                failures.append(script.name)
        else:
            print(f"⚠️ Script not found: {script}")
            
    print("\n" + "="*40)
    if failures:
        print(f"❌ QA FAILED: The following tests failed: {', '.join(failures)}")
        sys.exit(1)
    else:
        print("✅ QA SUCCESS: All Enterprise Verification scripts passed.")
        sys.exit(0)

if __name__ == "__main__":
    main()
