import requests


class NotificationFetcher:
    def __init__(self, session: requests.Session, storage_manager, discord_notifier):
        self.session = session
        self.storage_manager = storage_manager
        self.discord_notifier = discord_notifier
        self.web_base_url: str | None = None

    def fetch_notifications(self):
        """Fetch notifications from InfoMentor"""
        print("\n[Notifications] Fetching notifications...")

        if not self.web_base_url:
            print("  ✗ ERROR: No web session established")
            return []

        url = f"{self.web_base_url}/NotificationApp/NotificationApp/appData"

        headers = {
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.8",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "application/json; charset=utf-8",
            "Origin": "https://hub.infomentor.se",
            "Pragma": "no-cache",
            "Referer": "https://hub.infomentor.se/",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "Sec-GPC": "1",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
            "sec-ch-ua": '"Chromium";v="142", "Brave";v="142", "Not_A Brand";v="99"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Linux"',
        }

        try:
            response = self.session.post(url, headers=headers, json={}, timeout=30)

            if response.status_code == 200:
                data = response.json()
                notifications = data.get("notifications", [])
                print(f"  ✓ Successfully fetched {len(notifications)} notifications")
                return notifications
            else:
                print(
                    f"  ✗ ERROR: Notification endpoint returned status {response.status_code}"
                )
                return []
        except Exception as e:
            print(f"  ✗ ERROR: Error fetching notifications: {e}")
            self.discord_notifier.send_error("Fetching Notifications", e)
            return []

    def process_notifications(self):
        """Fetch, save, and notify about new notifications"""
        notifications = self.fetch_notifications()

        if not notifications:
            return

        existing_ids = self.storage_manager.get_existing_notification_ids()

        new_notifications = [
            n for n in notifications if n.get("id") not in existing_ids
        ]

        if new_notifications:
            print(f"  → Found {len(new_notifications)} new notifications")
            for notification in new_notifications:
                filename = self.storage_manager.save_notification(notification)
                if filename:
                    title = notification.get("title", "No title")
                    print(f"  ✓ NEW: {filename.name} - {title}")

                    self.discord_notifier.send_notification(notification)
        else:
            print("  → No new notifications")
