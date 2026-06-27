# src/notifiers/test_telegram.py

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

load_dotenv()

from src.notifiers.telegram import TelegramNotifier


def test_telegram_send():
    """Test actual message sending to Telegram"""
    
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    if not token or not chat_id:
        print("❌ TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set")
        return
    
    notifier = TelegramNotifier(
        token=token,
        chat_id=chat_id,
        enabled=True,
        timeout=10,
        max_retries=3,
        initial_backoff=2.0,
        max_backoff=30.0,
        backoff_multiplier=2.0
    )
    
    result = notifier.send(
        text="🧪 Reddit Job Agent Connection Test\n\n✅ If you see this, the notifier is working."
    )
    
    if result.success:
        print(f"✅ Message sent | message_ref: {result.message_ref}")
    else:
        print(f"❌ Error: {result.error}")


if __name__ == "__main__":
    test_telegram_send()
