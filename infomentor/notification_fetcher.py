import requests


class NotificationFetcher:
    def __init__(
        self, session: requests.Session, storage_manager, notifier, llm_client, news_fetcher
    ):
        self.session = session
        self.storage_manager = storage_manager
        self.notifier = notifier
        self.llm_client = llm_client
        self.news_fetcher = news_fetcher
        self.web_base_url: str | None = None
        self.pupil_name = None
        self.pupil_id = None

    def fetch_communication_content(self, url_route):
        """Fetch content from hub URL (e.g. news or message)"""
        if not self.web_base_url or not url_route:
            return None

        headers = {
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": f"{self.web_base_url}/",
        }

        # News Item
        if "communication/news/" in url_route.lower():
            try:
                news_id = int(url_route.split("/")[-1])
                print(f"  → Notification is for news item {news_id}")
                # Try GetNewsItem
                api_url = f"{self.web_base_url}/Communication/News/GetNewsItem?id={news_id}"
                response = self.session.get(api_url, headers=headers, timeout=30)
                if response.status_code == 200:
                    return response.json()
            except Exception as e:
                print(f"  ✗ Error fetching news item detail: {e}")

        # Message
        elif "message/show/" in url_route.lower():
            try:
                message_id = int(url_route.split("/")[-1])
                print(f"  → Notification is for message {message_id}")
                
                # First get the list of messages to find the one we need
                # GetMessages often takes parameters or returns a list
                list_url = f"{self.web_base_url}/Message/Message/GetMessages"
                list_response = self.session.post(list_url, headers=headers, json={}, timeout=30)
                
                if list_response.status_code == 200:
                    messages_data = list_response.json()
                    # The response might be a list or an object with a list
                    messages = messages_data if isinstance(messages_data, list) else messages_data.get("messages", [])
                    
                    # Find the message in the list
                    target_message = next((m for m in messages if str(m.get("id")) == str(message_id)), None)
                    
                    if target_message:
                        # If the list only has previews, we might still need GetMessage for full body
                        detail_url = f"{self.web_base_url}/Message/Message/GetMessage?id={message_id}"
                        detail_response = self.session.get(detail_url, headers=headers, timeout=30)
                        if detail_response.status_code == 200:
                            return detail_response.json()
                        return target_message
            except Exception as e:
                print(f"  ✗ Error fetching message detail: {e}")

        return None

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
            self.notifier.send_error("Fetching Notifications", e)
            return []

    def process_notifications(self):
        """Fetch, save, and notify about new notifications"""
        notifications = self.fetch_notifications()

        if not notifications:
            return

        existing_ids = self.storage_manager.get_existing_notification_ids(
            pupil_id=self.pupil_id
        )

        new_notifications = [
            n for n in notifications if n.get("id") not in existing_ids
        ]

        if new_notifications:
            print(f"  → Found {len(new_notifications)} new notifications")
            for notification in new_notifications:
                filename = self.storage_manager.save_notification(
                    notification, pupil_id=self.pupil_id
                )
                if filename:
                    title = notification.get("title", "No title")
                    url_route = notification.get("url")
                    print(f"  ✓ NEW: {filename.name} - {title}")

                    # Try to fetch additional communication content
                    comm_content = self.fetch_communication_content(url_route)
                    
                    summarized = False
                    if comm_content:
                        # Process with LLM if possible
                        summary = None
                        events = []
                        highlights = []

                        if self.llm_client.api_key:
                            try:
                                content_to_summarize = comm_content.get("content", "")
                                if not content_to_summarize:
                                    # For messages, the field might be "body" or "text"
                                    content_to_summarize = comm_content.get("body", "") or comm_content.get("text", "")
                                
                                if content_to_summarize:
                                    print(f"    → Summarizing communication content ({len(content_to_summarize)} chars)")
                                    analysis = self.llm_client.summarize_news_entry(content_to_summarize, notification.get("dateSent", ""))
                                    if analysis:
                                        summary = analysis.get("summary")
                                        events = analysis.get("events", [])
                                        highlights = analysis.get("highlights", [])
                            except Exception as e:
                                print(f"    ✗ Error summarizing communication: {e}")

                        # Send as webhook if we have content (even if not summarized)
                        # We use this to send the full message/news item details
                        self.notifier.send_webhook(
                            summary,
                            events,
                            highlights,
                            f"{title}: {comm_content.get('title', '')}",
                            None, # attachment_paths
                            comm_content, # full_item
                            self.pupil_name
                        )
                        summarized = True

                    # Fallback to standard notification if no detailed content was found
                    if not summarized:
                        self.notifier.send_notification(notification, self.pupil_name)
        else:
            print("  → No new notifications")
