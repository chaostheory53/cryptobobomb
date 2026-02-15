from flask import Flask, request, jsonify
import requests
import os
from google import genai
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

app = Flask(__name__)

# Load our Secrets
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
NEWS_API_KEY = os.environ.get("NEWS_API_KEY")

# Initialize Supabase
supabase: Client = None
try:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_ANON_KEY")
    if url and key:
        supabase = create_client(url, key)
    else:
        print("Warning: SUPABASE_URL or SUPABASE_KEY is missing.")
except Exception as e:
    print(f"Warning: Supabase Client failed to initialize: {e}")

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
            model='gemini-3.0-pro', 
            contents=prompt
        )
        
        return response.text.strip()
        
    except Exception as e:
        return f"Error analyzing sentiment: {str(e)}"

def get_crypto_prices(coins):
    """
    Fetches current price and 24h change for a list of coins.
    Uses CoinGecko API (Free Tier).
    """
    if not coins:
        return {}
    
    # join coins with comma
    ids = ",".join(coins)
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd&include_24hr_change=true"
    
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()
        return {}
    except Exception:
        return {}

@app.route('/api/webhook', methods=['POST'])
def webhook():
    update = request.get_json()
    
    if not update:
        return jsonify({'status': 'no data'}), 400

    if 'message' in update and 'text' in update['message']:
        chat_id = update['message']['chat']['id']
        text = update['message']['text'].lower()
        
        # Command Handlers
        if text.startswith('/start') or text.startswith('/help'):
            reply_text = (
                "💣 **Welcome to CryptoBobomb!**\n\n"
                "I can analyze crypto sentiment and track prices for you.\n\n"
                "**Commands:**\n"
                "• `/sentiment [coin]` - AI analysis of news\n"
                "• `/track [coin]` - Add to watchlist\n"
                "• `/untrack [coin]` - Remove from watchlist\n"
                "• `/watchlist` - View your list\n\n"
                "Or just chat with me! I use Gemini 2.5 Pro. 🧠"
            )
            if TELEGRAM_TOKEN:
                requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={'chat_id': chat_id, 'text': reply_text, 'parse_mode': 'Markdown'})

        # New AI Sentiment Skill
        elif text.startswith('/sentiment'):
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
            if len(parts) > 1 and supabase:
                coin = parts[1].lower()
                try:
                    # Insert into Supabase table 'watchlist'
                    # Assuming table structure: id (auto), chat_id, coin, (unique constraint on chat_id, coin)
                    data, count = supabase.table('watchlist').insert({
                        "chat_id": chat_id,
                        "coin": coin
                    }).execute()
                    reply_text = f"Added {coin} to your watchlist."
                except Exception as e:
                    # Check for unique constraint violation (duplicate entry)
                    if "duplicate key" in str(e) or "23505" in str(e): # PG error code for unique violation
                        reply_text = f"{coin} is already in your watchlist."
                    else:
                        reply_text = f"Error adding coin: {str(e)}"
                        print(f"Supabase error: {e}")
            elif not supabase:
                reply_text = "Database not configured."
            else:
                reply_text = "Usage: /track [coin]"
            
            if TELEGRAM_TOKEN:
                requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={'chat_id': chat_id, 'text': reply_text})

        elif text.startswith('/untrack'):
            parts = text.split(' ')
            if len(parts) > 1 and supabase:
                coin = parts[1].lower()
                try:
                     # Delete from Supabase
                    data, count = supabase.table('watchlist').delete().match({
                        "chat_id": chat_id, 
                        "coin": coin
                    }).execute()
                    
                    # data[1] usually contains the deleted rows list in python client v2
                    # But checking if list is empty is enough
                    if data and len(data[1]) > 0:
                         reply_text = f"Removed {coin} from your watchlist."
                    else:
                         reply_text = f"{coin} was not in your watchlist."
                except Exception as e:
                    reply_text = f"Error removing coin: {str(e)}"
            elif not supabase:
                reply_text = "Database not configured."
            else:
                reply_text = "Usage: /untrack [coin]"

            if TELEGRAM_TOKEN:
                requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={'chat_id': chat_id, 'text': reply_text})

        elif text.startswith('/watchlist'):
            if supabase:
                try:
                    response = supabase.table('watchlist').select('coin').eq('chat_id', chat_id).execute()
                    coins = [row['coin'] for row in response.data]
                    
                    if coins:
                        # 1. Fetch Prices in Batch
                        prices = get_crypto_prices(coins)
                        
                        message_lines = ["📊 **Your Watchlist:**\n"]
                        
                        for coin in sorted(coins):
                            # 2. Get Sentiment (this is still slow per coin, maybe cache later?)
                            # For now, we do it live as requested.
                            sentiment = analyze_sentiment(coin)
                            
                            # Determine Emoji
                            if "BULLISH" in sentiment.upper():
                                emoji = "🟢"
                            elif "BEARISH" in sentiment.upper():
                                emoji = "🔴"
                            else:
                                emoji = "⚪" # Neutral
                            
                            # Format Price Data
                            coin_data = prices.get(coin, {})
                            price = coin_data.get('usd', 'N/A')
                            change_24h = coin_data.get('usd_24h_change', 0)
                            
                            # Format change with arrow
                            change_str = ""
                            if isinstance(change_24h, (int, float)):
                                arrow = "⬆️" if change_24h >= 0 else "⬇️"
                                change_str = f" ({arrow} {change_24h:.2f}%)"
                            
                            line = f"{emoji} **{coin.title()}**: ${price}{change_str}\n_{sentiment}_"
                            message_lines.append(line)
                        
                        reply_text = "\n\n".join(message_lines)
                    else:
                        reply_text = "Your watchlist is empty. Use /track [coin] to add one."
                except Exception as e:
                    reply_text = f"Error fetching watchlist: {str(e)}"
            else:
                reply_text = "Database not configured."

            if TELEGRAM_TOKEN:
                requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={'chat_id': chat_id, 'text': reply_text, 'parse_mode': 'Markdown'})

        # Natural Language Conversation Fallback
        elif not text.startswith('/'):
            try:
                # Use Gemini for general conversation
                chat_prompt = f"You are a helpful and witty crypto assistant named CryptoBobomb. The user said: '{text}'. Reply directly to them, keeping it concise and fun, but still technical."
                
                response = client.models.generate_content(
                    model='gemini-3.0-pro', 
                    contents=chat_prompt
                )
                reply_text = response.text.strip()
                
                url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
                requests.post(url, json={'chat_id': chat_id, 'text': reply_text})
            except Exception as e:
                print(f"Error in chat: {e}")
                error_text = f"⚠️ Sorry, I ran into an error: {str(e)}"
                if TELEGRAM_TOKEN:
                    requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={'chat_id': chat_id, 'text': error_text})

    return jsonify({'status': 'ok'}), 200

# @app.route('/api/cron', methods=['GET'])
# def cron_job():
#     """
#     Cron job triggered every 30 minutes.
#     Iterates through all users' watchlists and sends updates.
#     """
#     # Verify the request is from Vercel Cron (optional security check for header)
#     # if request.headers.get('Authorization') != ...: pass
#
#     if not supabase or not TELEGRAM_TOKEN:
#         return jsonify({'error': 'Config missing'}), 500
#
#     processed_users = 0
#     
#     try:
#         # Fetch ALL watchlist items
#         # In production with large data, paginate this or process in batches
#         response = supabase.table('watchlist').select('*').execute()
#         all_rows = response.data
#         
#         # Group by chat_id: { chat_id: [coin1, coin2] }
#         user_coins = {}
#         for row in all_rows:
#             cid = row['chat_id']
#             coin = row['coin']
#             if cid not in user_coins:
#                 user_coins[cid] = []
#             user_coins[cid].append(coin)
#             
#         for cid, coins in user_coins.items():
#             if not coins:
#                 continue
#
#             messages = []
#             for coin in coins:
#                 # We reuse the analyze_sentiment function
#                 sentiment = analyze_sentiment(coin)
#                 messages.append(f"**{coin.upper()}**: {sentiment}")
#
#             if messages:
#                 full_message = "⏰ **30-Minute Update**\n\n" + "\n\n".join(messages)
#                 
#                 # Send to user
#                 url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
#                 try:
#                     requests.post(url, json={'chat_id': cid, 'text': full_message, 'parse_mode': 'Markdown'})
#                     processed_users += 1
#                 except Exception as e:
#                     print(f"Failed to send to {cid}: {e}")
#
#     except Exception as e:
#         print(f"Cron job error: {e}")
#         return jsonify({'error': str(e)}), 500
#
#     return jsonify({'status': 'ok', 'users_notified': processed_users}), 200

# Vercel requires a handler for serverless functions, often `app` is enough if using Flask with Vercel adapter or WSGI
# But for `vercel.json` rewrites to work with standard Flask in some setups, we might need:
# from werkzeug.middleware.proxy_fix import ProxyFix
# app.wsgi_app = ProxyFix(app.wsgi_app)
# However, the simple `app` object is usually detected by Vercel python runtime.
