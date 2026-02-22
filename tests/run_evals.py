
import sys
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from tests.evals.test_faithfulness import test_answer_quality, load_golden_dataset

def run():
    print("Running Evals Manually...")
    dataset = load_golden_dataset()
    for i, sample in enumerate(dataset):
        print(f"Sample {i+1}: {sample['input']}")
        try:
            test_answer_quality(sample)
            print("  ✅ Passed")
        except Exception as e:
            print(f"  ❌ Failed: {e}")
            
if __name__ == "__main__":
    run()
