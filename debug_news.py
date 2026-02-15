import requests
import os
from dotenv import load_dotenv
import json

load_dotenv()

NEWS_API_KEY = os.environ.get("NEWS_API_KEY")
coin = "bitcoin"

def debug_news():
    print(f"Checking NewsAPI for '{coin}'...")
    if not NEWS_API_KEY:
        print("❌ Error: NEWS_API_KEY is missing.")
        return

    url = f"https://newsapi.org/v2/everything?q={coin}&searchIn=title&language=en&sortBy=publishedAt&pageSize=5&apiKey={NEWS_API_KEY}"
    print(f"Request URL: {url.replace(NEWS_API_KEY, 'HIDDEN_KEY')}")
    
    try:
        response = requests.get(url)
        print(f"Status Code: {response.status_code}")
        
        data = response.json()
        print("\nResponse Body:")
        print(json.dumps(data, indent=2))
        
        if response.status_code != 200:
             print(f"❌ Error: {data.get('message', 'Unknown error')}")
             
    except Exception as e:
        print(f"❌ Exception: {e}")

if __name__ == "__main__":
    # Redirect stdout to a file for better inspection
    import sys
    original_stdout = sys.stdout
    with open('news_output.txt', 'w', encoding='utf-8') as f:
        sys.stdout = f
        debug_news()
    sys.stdout = original_stdout
    print("Output written to news_output.txt")
