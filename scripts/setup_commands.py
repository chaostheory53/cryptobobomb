import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def setup_commands():
    """
    Registers the bot's commands with Telegram so they appear in the menu.
    """
    token = os.environ.get("TELEGRAM_TOKEN")
    if not token:
        print("Error: TELEGRAM_TOKEN not found.")
        return

    commands = [
        {"command": "sentiment", "description": "Get AI sentiment for a coin"},
        {"command": "track", "description": "Add coin to watchlist"},
        {"command": "untrack", "description": "Remove coin from watchlist"},
        {"command": "watchlist", "description": "View your watchlist"},
        {"command": "help", "description": "Show available commands"}
    ]

    url = f"https://api.telegram.org/bot{token}/setMyCommands"
    
    try:
        response = requests.post(url, json={"commands": commands})
        response.raise_for_status()
        
        result = response.json()
        if result.get("ok"):
            print("Successfully registered commands with Telegram Menu!")
        else:
            print("Failed to register commands:")
            print(result)
            
    except Exception as e:
        print(f"Error setting commands: {e}")

if __name__ == "__main__":
    setup_commands()
