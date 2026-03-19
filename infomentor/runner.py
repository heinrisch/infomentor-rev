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
from .notifier import CompositeNotifier
from .pupil_fetcher import PupilFetcher
from .schedule_fetcher import ScheduleFetcher
from .storage import StorageManager
from .telegram_notifier import TelegramNotifier


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
        self.llm_client = LLMClient(
            self.config.perplexity_api_key, self.config.gemini_api_key
        )

        notifiers = []
        if self.config.discord_webhook_url:
            notifiers.append(DiscordNotifier(self.config.discord_webhook_url))
        if self.config.telegram_bot_token and self.config.telegram_chat_id:
            notifiers.append(
                TelegramNotifier(
                    self.config.telegram_bot_token, self.config.telegram_chat_id
                )
            )

        self.notifier = CompositeNotifier(notifiers)
        print(f"Initialized {len(notifiers)} notification channels: " + 
              ", ".join([n.__class__.__name__ for n in notifiers]))

        self.news_fetcher = NewsFetcher(
            self.session,
            self.storage_manager,
            self.notifier,
            self.llm_client,
            self.config.files_dir,
        )
        self.schedule_fetcher = ScheduleFetcher(
            self.session, self.storage_manager, self.notifier
        )
        self.notification_fetcher = NotificationFetcher(
            self.session,
            self.storage_manager,
            self.notifier,
            self.llm_client,
            self.news_fetcher,
        )
        self.pupil_fetcher = PupilFetcher(
            self.session, self.storage_manager
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
        self.pupil_fetcher.web_base_url = self.session_manager.web_base_url

        # 1. Fetch pupils initially to know who we're dealing with
        try:
            pupils = self.pupil_fetcher.process_pupils()
            if not pupils:
                print("  ⚠ No pupils found, nothing to process.")
                return
        except Exception as e:
            print(f"  ✗ ERROR processing pupil list: {e}")
            self.notifier.send_error("Initial Pupil List Fetch", e)
            return

        # 2. Iterate over each pupil
        for i, pupil in enumerate(pupils):
            pupil_name = pupil.get("name", f"Pupil {i+1}")
            pupil_id = pupil.get("id")
            switch_url = pupil.get("switchPupilUrl")

            print(f"\n--- Processing Pupil: {pupil_name} (ID: {pupil_id}) ---")

            # Update fetchers with current pupil name and ID
            self.news_fetcher.pupil_name = pupil_name
            self.news_fetcher.pupil_id = pupil_id
            self.schedule_fetcher.pupil_name = pupil_name
            self.schedule_fetcher.pupil_id = pupil_id
            self.notification_fetcher.pupil_name = pupil_name
            self.notification_fetcher.pupil_id = pupil_id

            # Switch context if needed
            if switch_url:
                if not self.session_manager.switch_pupil(switch_url):
                    print(f"  ✗ Skipping {pupil_name} due to switch failure")
                    continue
            else:
                print(f"  ⚠ No switch URL for {pupil_name}, proceeding with current context")

            # Process News
            try:
                self.news_fetcher.process_news(
                    access_token=self.token_manager.get_access_token()
                )
            except Exception as e:
                print(f"  ✗ ERROR processing news for {pupil_name}: {e}")
                self.notifier.send_error(f"Processing News ({pupil_name})", e)

            # Process Schedule
            try:
                self.schedule_fetcher.process_schedule()
            except Exception as e:
                print(f"  ✗ ERROR processing schedule for {pupil_name}: {e}")
                self.notifier.send_error(f"Processing Schedule ({pupil_name})", e)

            # Process Notifications
            try:
                self.notification_fetcher.process_notifications()
            except Exception as e:
                print(f"  ✗ ERROR processing notifications for {pupil_name}: {e}")
                self.notifier.send_error(f"Processing Notifications ({pupil_name})", e)

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
                self.notifier.send_error("Main Run Loop", e)

            # Add 1/15 variation converted to int
            vari = base_interval // 15
            variation = random.randint(-vari, vari)
            sleep_time = base_interval + variation

            next_run = datetime.now().timestamp() + sleep_time
            next_time = datetime.fromtimestamp(next_run).strftime("%H:%M:%S")
            print(f"Next fetch at {next_time} ({sleep_time}s)\n")

            time.sleep(sleep_time)
