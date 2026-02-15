PRD: Crypto-Ops Telegram Bot (Vercel Edition) - Powered by Gemini
1. Project Overview & Requirements
Objective: Build and deploy a zero-cost, event-driven Telegram bot that returns real-time cryptocurrency prices and AI-driven market sentiment.

Tech Stack:

Python (Application logic)

Vercel (Serverless hosting)

Telegram API (User interface)

Google Gemini API (AI Sentiment Analysis via the gemini-3-flash-preview model).

2. Architecture & Data Flow
Trigger: A user types /sentiment solana in Telegram.

Webhook Delivery: Telegram sends a POST request to our Vercel URL.

Compute: Vercel wakes up the Python function. It asks NewsAPI for the latest headlines.

AI Processing: The headlines are sent to the Gemini API, which acts as our bot's "brain" to determine if the news is Bullish or Bearish.

Response: The function returns the verdict to Telegram and spins down to save resources.

3. Secret Management 🔐
According to our DevOps roadmap, properly handling API keys falls firmly under Secret Management. You must never hardcode keys into your codebase.

We now need three Environment Variables configured in your Vercel dashboard:

TELEGRAM_TOKEN

NEWS_API_KEY

GEMINI_API_KEY (The new Python SDK will automatically look for this specific variable name!)

4. The Upgraded Code (api/webhook.py)
Note: For this to work in Vercel, you will need to add google-genai, flask, and requests to your requirements.txt file.


code example:
###
Python
from flask import Flask, request, jsonify
import requests
import os
from google import genai

app = Flask(__name__)

# Load our Secrets
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
NEWS_API_KEY = os.environ.get("NEWS_API_KEY")

# Initialize the Gemini Client. 
# It automatically picks up the GEMINI_API_KEY environment variable.
client = genai.Client()

@app.route('/api/webhook', methods=['POST'])
def webhook():
    update = request.get_json()
    
    if 'message' in update and 'text' in update['message']:
        chat_id = update['message']['chat']['id']
        text = update['message']['text'].lower()
        
        # New AI Sentiment Skill
        if text.startswith('/sentiment'):
            # Extract the coin name (e.g., "/sentiment solana")
            parts = text.split(' ')
            if len(parts) > 1:
                coin = parts[1]
                reply_text = analyze_sentiment(coin)
            else:
                reply_text = "Please provide a coin. Example: /sentiment bitcoin"
            
            # Send the reply back to Telegram
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            requests.post(url, json={'chat_id': chat_id, 'text': reply_text})
            
    return jsonify({'status': 'ok'}), 200

def analyze_sentiment(coin):
    """Fetches news and asks Gemini to analyze the sentiment."""
    try:
        # 1. Fetch the latest 5 news headlines
        news_url = f"https://newsapi.org/v2/everything?q={coin}&language=en&sortBy=publishedAt&pageSize=5&apiKey={NEWS_API_KEY}"
        news_data = requests.get(news_url).json()
        
        headlines = [article.get('title') for article in news_data.get('articles', [])[:5]]
        
        if not headlines:
            return f"No recent news found for {coin}."
            
        # 2. Ask Gemini for Sentiment Analysis
        prompt = f"Analyze the overall market sentiment of these recent news headlines for {coin}. Reply with exactly one word (BULLISH, BEARISH, or NEUTRAL), followed by a short 1-sentence summary of why.\nHeadlines: {headlines}"
        
        # We use Gemini 3 Flash as it is optimized for speed and perfect for bots
        response = client.models.generate_content(
            model='gemini-3-flash-preview',
            contents=prompt
        )
        
        return response.text.strip()
        
    except Exception as e:
        return f"Error analyzing sentiment: {str(e)}"
    ###