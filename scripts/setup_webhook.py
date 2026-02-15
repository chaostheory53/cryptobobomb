import os
import sys
import requests
from dotenv import load_dotenv

# Load environment variables from .env file (if running locally)
load_dotenv()

def setup_webhook(vercel_url):
    """
    Registers the Vercel serverless function URL as the Telegram Webhook.
    """
    token = os.environ.get("TELEGRAM_TOKEN")
    if not token:
        print("Error: TELEGRAM_TOKEN not found in environment variables.")
        return

    # Ensure the URL has the correct scheme and path
    if not vercel_url.startswith("http"):
        vercel_url = f"https://{vercel_url}"
    
    if not vercel_url.endswith("/api/webhook"):
        # Strip trailing slash if present then add path
        webhook_url = f"{vercel_url.rstrip('/')}/api/webhook"
    else:
        webhook_url = vercel_url

    print(f"Setting webhook to: {webhook_url}")

    # Telegram API URL
    tg_url = f"https://api.telegram.org/bot{token}/setWebhook"

    try:
        response = requests.post(tg_url, data={"url": webhook_url})
        response.raise_for_status()
        
        result = response.json()
        if result.get("ok"):
            print("Successfully set webhook!")
            print(result.get("description"))
        else:
            print("Failed to set webhook:")
            print(result)
            
    except Exception as e:
        print(f"Error setting webhook: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        url = sys.argv[1]
    else:
        url = input("Enter your Vercel Project URL (e.g., https://my-project.vercel.app): ")
    
    if url:
        setup_webhook(url)
    else:
        print("No URL provided. Exiting.")
