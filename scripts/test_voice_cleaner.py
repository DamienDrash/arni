import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from app.voice.text_cleaner import clean_text_for_tts

def test_cleaning():
    print("🧹 Testing Text Cleaner...")
    
    # Case 1: Emojis
    input_1 = "Hallo! 👋 Wie geht's? 🧘‍♂️"
    expected_1 = "Hallo! Wie geht's?"
    result_1 = clean_text_for_tts(input_1)
    print(f"1. Emojis: '{input_1}' -> '{result_1}'")
    assert result_1 == expected_1, f"Expected '{expected_1}', got '{result_1}'"

    # Case 2: Time (German)
    input_2 = "Der Kurs ist um 14:00."
    expected_2 = "Der Kurs ist um 14 Uhr."
    result_2 = clean_text_for_tts(input_2, lang="de")
    print(f"2. Time 00: '{input_2}' -> '{result_2}'")
    assert result_2 == expected_2, f"Expected '{expected_2}', got '{result_2}'"

    # Case 3: Time (Minutes)
    input_3 = "Oder vielleicht 14:30?"
    expected_3 = "Oder vielleicht 14 Uhr 30?"
    result_3 = clean_text_for_tts(input_3, lang="de")
    print(f"3. Time MM: '{input_3}' -> '{result_3}'")
    assert result_3 == expected_3, f"Expected '{expected_3}', got '{result_3}'"

    # Case 4: Markdown
    input_4 = "Das ist *fett* und _kursiv_."
    expected_4 = "Das ist fett und kursiv."
    result_4 = clean_text_for_tts(input_4)
    print(f"4. Markdown: '{input_4}' -> '{result_4}'")
    assert result_4 == expected_4, f"Expected '{expected_4}', got '{result_4}'"

    print("✅ All tests passed!")

if __name__ == "__main__":
    try:
        test_cleaning()
    except AssertionError as e:
        print(f"❌ Test Failed: {e}")
        sys.exit(1)
