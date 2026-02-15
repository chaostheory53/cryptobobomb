from flask import Flask, request, jsonify
import requests
import os
from google import genai
from dotenv import load_dotenv
import redis

load_dotenv()

app = Flask(__name__)

# Load our Secrets
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
NEWS_API_KEY = os.environ.get("NEWS_API_KEY")

# Initialize Redis
try:
    kv_url = os.environ.get("KV_URL_REST_API_URL") or os.environ.get("KV_URL")
    kv_token = os.environ.get("KV_REST_API_TOKEN") or os.environ.get("KV_TOKEN")
    
    # Simple Redis direct connection or fallback to REST if needed?
    # For Vercel KV (Upstash), standard redis-py works fine if REDIS_URL is provided
    # but Vercel creates environ vars: KV_URL, KV_REST_API_URL, etc.
    # Let's try standard redis first if connection string is available
    redis_url = os.environ.get("KV_URL") or os.environ.get("REDIS_URL")
    if redis_url:
        # If it's a `redis://` url, use it. Upstash uses `rediss://` (secure)
        if redis_url.startswith("redis"):
            redis_client = redis.from_url(redis_url, decode_responses=True)
        else:
            print(f"Warning: KV_URL doesn't look like a redis url: {redis_url[:10]}...")
            redis_client = None
    else:
        print("Warning: KV_URL or REDIS_URL not set.")
        redis_client = None
except Exception as e:
    print(f"Warning: Redis Client failed to initialize: {e}")
    redis_client = None

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
            model='gemini-2.5-flash', 
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

        # Watchlist Features
        elif text.startswith('/track'):
            parts = text.split(' ')
            if len(parts) > 1 and redis_client:
                coin = parts[1].lower()
                key = f"watchlist:{chat_id}"
                redis_client.sadd(key, coin)
                reply_text = f"Added {coin} to your watchlist."
            elif not redis_client:
                reply_text = "Database not configured."
            else:
                reply_text = "Usage: /track [coin]"
            
            if TELEGRAM_TOKEN:
                requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={'chat_id': chat_id, 'text': reply_text})

        elif text.startswith('/untrack'):
            parts = text.split(' ')
            if len(parts) > 1 and redis_client:
                coin = parts[1].lower()
                key = f"watchlist:{chat_id}"
                result = redis_client.srem(key, coin)
                if result:
                    reply_text = f"Removed {coin} from your watchlist."
                else:
                    reply_text = f"{coin} was not in your watchlist."
            elif not redis_client:
                reply_text = "Database not configured."
            else:
                reply_text = "Usage: /untrack [coin]"

            if TELEGRAM_TOKEN:
                requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={'chat_id': chat_id, 'text': reply_text})

        elif text.startswith('/watchlist'):
            if redis_client:
                key = f"watchlist:{chat_id}"
                coins = redis_client.smembers(key)
                if coins:
                    coin_list = ", ".join(sorted(list(coins)))
                    reply_text = f"Your Watchlist: {coin_list}"
                else:
                    reply_text = "Your watchlist is empty. Use /track [coin] to add one."
            else:
                reply_text = "Database not configured."

            if TELEGRAM_TOKEN:
                requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={'chat_id': chat_id, 'text': reply_text})

        # Natural Language Conversation Fallback
        elif not text.startswith('/'):
            try:
                # Use Gemini for general conversation
                chat_prompt = f"You are a helpful and witty crypto assistant named CryptoBobomb. The user said: '{text}'. Reply directly to them, keeping it concise and fun, but still technical."
                
                response = client.models.generate_content(
                    model='gemini-2.5-flash', 
                    contents=chat_prompt
                )
                reply_text = response.text.strip()
                
                url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
                requests.post(url, json={'chat_id': chat_id, 'text': reply_text})
            except Exception as e:
                print(f"Error in chat: {e}")

    return jsonify({'status': 'ok'}), 200

@app.route('/api/cron', methods=['GET'])
def cron_job():
    """
    Cron job triggered every 30 minutes.
    Iterates through all users' watchlists and sends updates.
    """
    # Verify the request is from Vercel Cron (optional security check for header)
    # if request.headers.get('Authorization') != ...: pass

    if not redis_client or not TELEGRAM_TOKEN:
        return jsonify({'error': 'Config missing'}), 500

    # 1. Get all watchlist keys: "watchlist:*"
    # Note: In production with millions of keys, use SCAN. For a bot, KEYS is okay-ish but SCAN is safer.
    watchlist_keys = []
    cursor = '0'
    while cursor != 0:
        cursor, keys = redis_client.scan(cursor=cursor, match='watchlist:*', count=100)
        watchlist_keys.extend(keys)

    processed_users = 0
    
    for key in watchlist_keys:
        # key format: watchlist:{chat_id}
        parts = key.split(':')
        if len(parts) == 2:
            chat_id = parts[1]
            coins = redis_client.smembers(key)
            
            if not coins:
                continue

            # For each user, analyze their coins
            messages = []
            for coin in coins:
                # We reuse the analyze_sentiment function
                sentiment = analyze_sentiment(coin)
                messages.append(f"**{coin.upper()}**: {sentiment}")

            if messages:
                full_message = "⏰ **30-Minute Update**\n\n" + "\n\n".join(messages)
                
                # Send to user
                url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
                try:
                    requests.post(url, json={'chat_id': chat_id, 'text': full_message, 'parse_mode': 'Markdown'})
                    processed_users += 1
                except Exception as e:
                    print(f"Failed to send to {chat_id}: {e}")

    return jsonify({'status': 'ok', 'users_notified': processed_users}), 200

# Vercel requires a handler for serverless functions, often `app` is enough if using Flask with Vercel adapter or WSGI
# But for `vercel.json` rewrites to work with standard Flask in some setups, we might need:
# from werkzeug.middleware.proxy_fix import ProxyFix
# app.wsgi_app = ProxyFix(app.wsgi_app)
# However, the simple `app` object is usually detected by Vercel python runtime.
