import sys
import os

# Add the project root to sys.path so we can import api
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from api.webhook import analyze_sentiment

def test_sentiment():
    print("Testing sentiment analysis for 'Bitcoin'...")
    result = analyze_sentiment("bitcoin")
    print(f"\nResult:\n{result}")

    if "Error" in result:
        print("\n❌ Test Failed: Logic returned an error.")
        sys.exit(1)
    else:
        print("\n✅ Test Passed: Received a response from Gemini/NewsAPI.")

if __name__ == "__main__":
    test_sentiment()
