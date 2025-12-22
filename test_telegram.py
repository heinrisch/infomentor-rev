import sys

from infomentor.config import Config
from infomentor.telegram_notifier import TelegramNotifier


def test_telegram():
    print("Testing Telegram Notifier...")
    config = Config()
    
    if not config.telegram_bot_token or not config.telegram_chat_id:
        print("✗ Telegram credentials not found in .env")
        print("Please add TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID to your .env file.")
        return

    print(f"✓ Found credentials (Chat ID: {config.telegram_chat_id})")
    
    notifier = TelegramNotifier(config.telegram_bot_token, config.telegram_chat_id)
    
    print("→ Sending test message...")
    success = notifier.send_message("🔔 This is a test notification from InfoMentor!")
    
    if success:
        print("✓ Test message sent successfully!")
        
        # Test error message formatting
        print("→ Sending test error...")
        notifier.send_error("Test Context", "This is a simulated error message to verify formatting.")
        print("✓ Test error sent!")

        # Test full content
        print("→ Sending test full content...")
        full_item = {
            "title": "Test Full Content",
            "publishedDateString": "2023-10-27",
            "publishedBy": "Test Author",
            "content": "<p>This is a <b>test</b> content with <i>html</i>.</p>"
        }
        notifier.send_webhook("Summary text", [], [], "News Title", full_item=full_item)
        print("✓ Test full content sent!")
    else:
        print("✗ Failed to send test message.")

if __name__ == "__main__":
    test_telegram()
