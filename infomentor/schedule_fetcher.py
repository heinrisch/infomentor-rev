from datetime import datetime, timedelta

import requests


class ScheduleFetcher:
    def __init__(self, session: requests.Session, storage_manager, discord_notifier):
        self.session = session
        self.storage_manager = storage_manager
        self.discord_notifier = discord_notifier
        self.web_base_url: str | None = "https://hub.infomentor.se"

    def get_current_week_dates(self):
        """Get start (Sunday) and end (Saturday) dates for the current week"""
        today = datetime.now().date()
        # In Python, Monday is 0, Sunday is 6.
        # We want Sunday to be the start of the week.
        # If today is Sunday (6), start is today.
        # If today is Monday (0), start is today - 1.
        days_since_sunday = (today.weekday() + 1) % 7
        start_date = today - timedelta(days=days_since_sunday)
        end_date = start_date + timedelta(days=6)
        return start_date, end_date

    def fetch_schedule(self):
        """Fetch the schedule for the current week"""
        print("\n[Schedule] Fetching schedule...")

        start_date, end_date = self.get_current_week_dates()
        start_str = start_date.strftime("%Y/%m/%d")
        end_str = end_date.strftime("%Y/%m/%d")

        url = f"{self.web_base_url}/calendarv2/calendarv2/getentries"

        headers = {
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.8",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "application/json; charset=UTF-8",
            "Origin": "https://hub.infomentor.se",
            "Pragma": "no-cache",
            "Referer": "https://hub.infomentor.se/",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "Sec-GPC": "1",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
            "X-Requested-With": "XMLHttpRequest",
            "sec-ch-ua": '"Chromium";v="142", "Brave";v="142", "Not_A Brand";v="99"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Linux"',
        }

        data = {"startDate": start_str, "endDate": end_str}

        try:
            response = self.session.post(url, headers=headers, json=data, timeout=30)

            if response.status_code == 200:
                schedule_data = response.json()
                print(f"  ✓ Successfully fetched {len(schedule_data)} schedule entries")
                return schedule_data
            else:
                print(
                    f"  ✗ ERROR: Schedule endpoint returned status {response.status_code}"
                )
                return None
        except Exception as e:
            print(f"  ✗ ERROR: Error fetching schedule: {e}")
            self.discord_notifier.send_error("Fetching Schedule", e)
            return None

    def process_schedule(self):
        """Fetch, compare, and notify about schedule"""
        current_schedule = self.fetch_schedule()
        if current_schedule is None:
            return

        start_date, _ = self.get_current_week_dates()
        week_str = start_date.strftime("%Y-%m-%d")

        # Load previous schedule for this week
        previous_schedule = self.storage_manager.load_schedule(week_str)

        today = datetime.now().date()
        is_sunday = today.weekday() == 6

        # If it's Sunday, we always post the full schedule
        if is_sunday:
            # Check if we already posted today to avoid spamming if script restarts
            last_sunday_post = self.storage_manager.get_last_sunday_post()
            if last_sunday_post != today.strftime("%Y-%m-%d"):
                print("  → It's Sunday, posting full schedule...")
                self.discord_notifier.send_schedule_update(
                    current_schedule, week_str, is_new_week=True
                )
                self.storage_manager.save_schedule(week_str, current_schedule)
                self.storage_manager.set_last_sunday_post(today.strftime("%Y-%m-%d"))
                return

        # If we have a previous schedule, check for changes
        if previous_schedule:
            changes = self.detect_changes(previous_schedule, current_schedule)
            if changes:
                print(f"  → Found {len(changes)} changes in schedule")
                self.discord_notifier.send_schedule_update(
                    current_schedule, week_str, changes=changes
                )
                self.storage_manager.save_schedule(week_str, current_schedule)
            else:
                print("  → No changes in schedule")
        else:
            # First time seeing this week's schedule (and not Sunday), save it
            print("  → New week detected (or first run), saving baseline.")
            self.storage_manager.save_schedule(week_str, current_schedule)

    def detect_changes(self, old_schedule, new_schedule):
        """Compare two schedules and return list of changes"""
        # Convert to dicts keyed by ID for easier comparison
        old_map = {entry["id"]: entry for entry in old_schedule}
        new_map = {entry["id"]: entry for entry in new_schedule}

        changes = []

        # Check for modified or new entries
        for id, new_entry in new_map.items():
            if id not in old_map:
                changes.append({"type": "added", "entry": new_entry})
            else:
                old_entry = old_map[id]
                # Compare relevant fields
                diffs = []
                if old_entry.get("title") != new_entry.get("title"):
                    diffs.append(
                        f"Title: {old_entry.get('title')} -> {new_entry.get('title')}"
                    )
                if old_entry.get("startDateFull") != new_entry.get("startDateFull"):
                    diffs.append(
                        f"Start: {old_entry.get('formattedStartDate')} {old_entry.get('startTime')} -> {new_entry.get('formattedStartDate')} {new_entry.get('startTime')}"
                    )
                if old_entry.get("endDateFull") != new_entry.get("endDateFull"):
                    diffs.append(
                        f"End: {old_entry.get('formattedEndDate')} {old_entry.get('endTime')} -> {new_entry.get('formattedEndDate')} {new_entry.get('endTime')}"
                    )
                if old_entry.get("description") != new_entry.get("description"):
                    diffs.append("Description changed")

                if diffs:
                    changes.append(
                        {"type": "modified", "entry": new_entry, "diffs": diffs}
                    )

        # Check for removed entries
        for id, old_entry in old_map.items():
            if id not in new_map:
                changes.append({"type": "removed", "entry": old_entry})

        return changes
