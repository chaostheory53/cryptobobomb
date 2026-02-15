from flask import Flask, request, jsonify
import requests
import os
from google import genai
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Load our Secrets
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
NEWS_API_KEY = os.environ.get("NEWS_API_KEY")

# Initialize the Gemini Client. 
# It automatically picks up the GEMINI_API_KEY environment variable.
try:
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
except Exception as e:
    print(f"Warning: Gemini Client failed to initialize: {e}")
    client = None

def analyze_sentiment(coin):
    """Fetches news and asks Gemini to analyze the sentiment."""
    if not NEWS_API_KEY:
        return "Error: NEWS_API_KEY not configured."
    if not client:
        return "Error: Gemini Client not initialized (check GEMINI_API_KEY)."

    try:
        # 1. Fetch the latest 5 news headlines
        # properly encoding the coin for url might be needed but simple string usually works for coin names
        news_url = f"https://newsapi.org/v2/everything?q={coin}&searchIn=title&language=en&sortBy=publishedAt&pageSize=5&apiKey={NEWS_API_KEY}"
        news_response = requests.get(news_url)
        news_data = news_response.json()
        
        if news_response.status_code != 200:
             return f"Error fetching news: {news_data.get('message', 'Unknown error')}"

        headlines = [article.get('title') for article in news_data.get('articles', [])[:5]]
        
        if not headlines:
            return f"No recent news found for {coin}."
            
        # 2. Ask Gemini for Sentiment Analysis
        prompt = f"Analyze the overall market sentiment of these recent news headlines for {coin}. Reply with exactly one word (BULLISH, BEARISH, or NEUTRAL), followed by a short 1-sentence summary of why.\nHeadlines: {headlines}"
        
        # We use Gemini 2.0 Flash (or closest available)
        # Using a model name that is generally available or falling back
        response = client.models.generate_content(
            model='gemini-2.0-flash', 
            contents=prompt
        )
        
        return response.text.strip()
        
    except Exception as e:
        return f"Error analyzing sentiment: {str(e)}"

@app.route('/api/webhook', methods=['POST'])
def webhook():
    update = request.get_json()
    
    if not update:
        return jsonify({'status': 'no data'}), 400

    if 'message' in update and 'text' in update['message']:
        chat_id = update['message']['chat']['id']
        text = update['message']['text'].lower()
        
        # New AI Sentiment Skill
        if text.startswith('/sentiment'):
            # Extract the coin name (e.g., "/sentiment solana")
            parts = text.split(' ')
            if len(parts) > 1:
                coin = parts[1]
                # notify user processing? Telegram bots usually just reply.
                reply_text = analyze_sentiment(coin)
            else:
                reply_text = "Please provide a coin. Example: /sentiment bitcoin"
            
            # Send the reply back to Telegram
            if TELEGRAM_TOKEN:
                url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
                requests.post(url, json={'chat_id': chat_id, 'text': reply_text})
            else:
                print("TELEGRAM_TOKEN not set, cannot send reply.")
                print(f"Would have sent: {reply_text}")
            
    return jsonify({'status': 'ok'}), 200

# Vercel requires a handler for serverless functions, often `app` is enough if using Flask with Vercel adapter or WSGI
# But for `vercel.json` rewrites to work with standard Flask in some setups, we might need:
# from werkzeug.middleware.proxy_fix import ProxyFix
# app.wsgi_app = ProxyFix(app.wsgi_app)
# However, the simple `app` object is usually detected by Vercel python runtime.
