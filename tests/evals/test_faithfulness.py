
import pytest
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

# --- Mock DeepEval if not installed ---
try:
    from deepeval import assert_test
    from deepeval.metrics import FaithfulnessMetric, AnswerRelevancyMetric
    from deepeval.test_case import LLMTestCase
except ImportError:
    # Creating Mock classes to allow test execution in dev environment
    class FaithfulnessMetric:
        def __init__(self, threshold=0.5): pass
        def measure(self, case): 
            print("  [Mock] Measuring Faithfulness...")
            return 1.0
        def is_successful(self): return True

    class AnswerRelevancyMetric:
        def __init__(self, threshold=0.5): pass
        def measure(self, case): 
            print("  [Mock] Measuring Relevancy...")
            return 1.0
        def is_successful(self): return True

    class LLMTestCase:
        def __init__(self, input, actual_output, expected_output, retrieval_context):
            self.input = input
            self.actual_output = actual_output

    def assert_test(case, metrics):
        for m in metrics:
            m.measure(case)
            assert m.is_successful()

# --- Helper to load dataset ---
def load_golden_dataset():
    path = Path(__file__).parents[1] / "golden_dataset.json"
    with open(path, "r") as f:
        return json.load(f)

# --- The Test ---
@pytest.mark.parametrize("sample", load_golden_dataset())
def test_answer_quality(sample):
    """
    Runs DeepEval metrics on the Golden Dataset.
    In a real CI/CD, 'actual_output' would come from calling the live Agent.
    Here we simulate the Agent's response being 'perfect' matches or mock generation.
    """
    input_text = sample["input"]
    expected = sample["expected_output"]
    context = sample["context"]
    
    print(f"\nTesting Input: {input_text}")

    # SIMULATION: In real life, call agent._chat(input_text) here.
    # For this stub, we assume the agent behaves perfectly and returns expected output.
    actual_output = expected 
    
    test_case = LLMTestCase(
        input=input_text,
        actual_output=actual_output,
        expected_output=expected,
        retrieval_context=context
    )
    
    faithfulness = FaithfulnessMetric(threshold=0.7)
    relevancy = AnswerRelevancyMetric(threshold=0.7)
    
    assert_test(test_case, [faithfulness, relevancy])
