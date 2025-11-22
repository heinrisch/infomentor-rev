import random
import time
from datetime import datetime

import requests

from .auth import SessionManager, TokenManager
from .config import Config
from .discord_notifier import DiscordNotifier
from .llm_client import LLMClient
from .news_fetcher import NewsFetcher
from .notification_fetcher import NotificationFetcher
from .schedule_fetcher import ScheduleFetcher
from .storage import StorageManager


class InfoMentorFetcher:
    def __init__(self):
        self.config = Config()
        self.session = requests.Session()

        self.token_manager = TokenManager(
            self.config.token_file, self.config.auth_base_url
        )
        self.session_manager = SessionManager(
            self.token_manager, self.session, self.config.api_base_url
        )
        self.storage_manager = StorageManager(
            self.config.output_dir, self.config.files_dir
        )
        self.llm_client = LLMClient(self.config.perplexity_api_key)
        self.discord_notifier = DiscordNotifier(self.config.discord_webhook_url)

        self.news_fetcher = NewsFetcher(
            self.session,
            self.storage_manager,
            self.discord_notifier,
            self.llm_client,
            self.config.files_dir,
        )
        self.schedule_fetcher = ScheduleFetcher(
            self.session, self.storage_manager, self.discord_notifier
        )
        self.notification_fetcher = NotificationFetcher(
            self.session, self.storage_manager, self.discord_notifier
        )

    def fetch_and_process(self):
        """Fetch and save all data (news, schedule, notifications)"""
        print(f"\n{'='*60}")
        print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Starting fetch cycle")
        print(f"{'='*60}")

        # Validate and refresh token if needed
        if not self.token_manager.validate_and_refresh_token():
            print("\n✗ ABORTING: Token validation failed")
            return

        # Establish web session using SSO
        if not self.session_manager.establish_web_session():
            print("\n✗ ABORTING: Could not establish web session")
            return

        # Update components with web base url
        self.news_fetcher.set_web_base_url(self.session_manager.web_base_url)
        self.news_fetcher.use_bearer_token = self.session_manager.use_bearer_token
        self.schedule_fetcher.web_base_url = self.session_manager.web_base_url
        self.notification_fetcher.web_base_url = self.session_manager.web_base_url

        # Process News
        try:
            self.news_fetcher.process_news(
                access_token=self.token_manager.get_access_token()
            )
        except Exception as e:
            print(f"  ✗ ERROR processing news: {e}")
            self.discord_notifier.send_error("Processing News", e)

        # Process Schedule
        try:
            self.schedule_fetcher.process_schedule()
        except Exception as e:
            print(f"  ✗ ERROR processing schedule: {e}")
            self.discord_notifier.send_error("Processing Schedule", e)

        # Process Notifications
        try:
            self.notification_fetcher.process_notifications()
        except Exception as e:
            print(f"  ✗ ERROR processing notifications: {e}")
            self.discord_notifier.send_error("Processing Notifications", e)

        print(f"\n{'='*60}\n")

    def run(self, base_interval=1800):
        """
        Run fetcher on schedule
        base_interval: 1800 seconds (30 minutes), with ±120s variation
        """
        print(f"Starting InfoMentor fetcher (every ~{base_interval//60} min)\n")

        while True:
            try:
                self.fetch_and_process()
            except Exception as e:
                print(f"  ✗ CRITICAL ERROR in run loop: {e}")
                self.discord_notifier.send_error("Main Run Loop", e)

            # Add 1/15 variation converted to int
            vari = base_interval // 15
            variation = random.randint(-vari, vari)
            sleep_time = base_interval + variation

            next_run = datetime.now().timestamp() + sleep_time
            next_time = datetime.fromtimestamp(next_run).strftime("%H:%M:%S")
            print(f"Next fetch at {next_time} ({sleep_time}s)\n")

            time.sleep(sleep_time)
