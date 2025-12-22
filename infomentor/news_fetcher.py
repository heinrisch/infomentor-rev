import json
from datetime import datetime

import requests


class NewsFetcher:
    def __init__(
        self,
        session: requests.Session,
        storage_manager,
        notifier,
        llm_client,
        files_dir,
    ):
        self.session = session
        self.storage_manager = storage_manager
        self.notifier = notifier
        self.llm_client = llm_client
        self.files_dir = files_dir
        self.web_base_url = None
        self.use_bearer_token = False

    def set_web_base_url(self, url):
        self.web_base_url = url

    def fetch_news(self, access_token=None):
        """Fetch news list from InfoMentor web endpoint"""
        print("\n[News] Fetching news...")

        if not self.web_base_url:
            print("  ✗ ERROR: No web session established")
            return []

        headers = {
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "en-US,en;q=0.6",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Origin": "https://hub.infomentor.se",
            "Pragma": "no-cache",
            "Referer": "https://hub.infomentor.se/",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "X-Requested-With": "XMLHttpRequest",
        }

        # If we're using Bearer token auth, add it to headers
        if self.use_bearer_token or "Authorization" in self.session.headers:
            if access_token:
                headers["Authorization"] = f"Bearer {access_token}"

        url = f"{self.web_base_url}/Communication/News/GetNewsList"

        try:
            response = self.session.get(
                url, headers=headers, timeout=30, allow_redirects=False
            )

            if response.status_code == 200:
                try:
                    data = response.json()
                    items = data.get("items", [])
                    print(f"  ✓ Successfully fetched {len(items)} news items")
                    return items
                except json.JSONDecodeError:
                    print("  ✗ ERROR: Invalid JSON in news response")
                    return []
            else:
                print(
                    f"  ✗ ERROR: News endpoint returned status {response.status_code}"
                )
                return []
        except Exception as e:
            print(f"  ✗ ERROR: Error fetching news: {e}")
            return []

    def download_attachment(self, url, title):
        """Download a single attachment"""
        try:
            full_url = (
                f"{self.web_base_url}/{url}" if not url.startswith("http") else url
            )
            response = self.session.get(full_url, stream=True, timeout=60)

            if response.status_code == 200:
                # Sanitize filename
                safe_title = "".join(
                    c for c in title if c.isalnum() or c in (" ", ".", "_", "-")
                ).strip()
                if not safe_title:
                    safe_title = url.split("/")[-1] or "attachment"

                filepath = self.files_dir / safe_title

                # Check if file already exists and has content
                if filepath.exists() and filepath.stat().st_size > 0:
                    return filepath

                with open(filepath, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)

                if filepath.exists() and filepath.stat().st_size > 0:
                    return filepath
            return None
        except Exception as e:
            print(f"    ✗ Error downloading {title}: {e}")
            return None

    def download_attachments(self, item, existing_attachments):
        """Download all attachments for a news item"""
        attachments = item.get("attachments", [])
        downloaded_paths = []
        if not attachments:
            return 0, []

        downloaded = 0
        for attachment in attachments:
            url = attachment.get("url")
            title = attachment.get("title", "untitled")

            safe_title = "".join(
                c for c in title if c.isalnum() or c in (" ", ".", "_", "-")
            ).strip()
            if not safe_title:
                safe_title = url.split("/")[-1] if url else "untitled"

            if safe_title in existing_attachments:
                filepath = self.files_dir / safe_title
                downloaded_paths.append(filepath)
                continue

            if url:
                downloaded_path = self.download_attachment(url, title)
                if downloaded_path:
                    print(f"    ✓ Downloaded: {downloaded_path.name}")
                    existing_attachments.add(safe_title)
                    downloaded += 1
                    downloaded_paths.append(downloaded_path)

        return downloaded, downloaded_paths

    def process_new_item(self, item, attachment_paths=None):
        """Process a new news item with LLM and Discord"""
        content = item.get("content", "")
        title = item.get("title", "No Title")
        published_date = item.get(
            "publishedDateString", datetime.now().strftime("%Y-%m-%d")
        )

        if not content:
            return

        try:
            analysis = self.llm_client.summarize_news_entry(content, published_date)

            if analysis:
                summary = analysis.get("summary", "No summary available.")
                events = analysis.get("events", [])
                highlights = analysis.get("highlights", [])

                print(f"    ✓ Generated summary ({len(summary)} chars)")
                self.notifier.send_webhook(
                    summary, events, highlights, title, attachment_paths, item
                )
        except Exception as e:
            print(f"    ✗ ERROR processing LLM analysis: {e}")
            self.notifier.send_error(f"LLM Analysis for '{title}'", e)

    def process_news(self, access_token):
        """Fetch, save, and process news items"""
        # Get existing IDs and attachments before fetching
        existing_ids = self.storage_manager.get_existing_ids()
        existing_attachments = self.storage_manager.get_existing_attachments()

        items = self.fetch_news(access_token=access_token)

        if items:
            new_items = [item for item in items if item.get("id") not in existing_ids]

            if new_items:
                print(f"  → Found {len(new_items)} new news items")
                for item in new_items:
                    filename = self.storage_manager.save_news_item(item)
                    if filename:
                        title = item.get("title", "No title")
                        published = item.get("publishedDateString", "Unknown date")
                        print(f"  ✓ NEW: {filename.name} - {title} ({published})")

                        # Download attachments
                        _, attachment_paths = self.download_attachments(
                            item, existing_attachments
                        )

                        # Process with LLM and send to Discord
                        self.process_new_item(item, attachment_paths)
            else:
                print("  → No new news items")
            return len(new_items)
        return 0
