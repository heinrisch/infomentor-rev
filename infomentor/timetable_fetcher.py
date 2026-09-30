from datetime import datetime, timedelta

import requests


def current_week_range():
    """(monday, sunday) dates and the JS-style UTC offset for the week query."""
    today = datetime.now().date()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    offset = datetime.now().astimezone().utcoffset()
    # Browsers send getTimezoneOffset(): minutes behind UTC, negated.
    utc_offset = -int(offset.total_seconds() // 60) if offset else 0
    return monday, sunday, utc_offset


class TimetableFetcher:
    def __init__(self, session: requests.Session, storage_manager, notifier):
        self.session = session
        self.storage_manager = storage_manager
        self.notifier = notifier
        self.web_base_url = None
        self.pupil_name = None
        self.pupil_id = None

    @staticmethod
    def entry_key(entry):
        return (entry.get("start"), entry.get("end"), entry.get("title"))

    @staticmethod
    def format_entry(entry):
        try:
            day = datetime.fromisoformat(entry.get("start", "")).strftime("%a %d/%m")
        except ValueError:
            day = ""
        room = (entry.get("notes") or {}).get("roomInfo") or ""
        text = f"{day} {entry.get('startTime', '')}-{entry.get('endTime', '')} " \
            f"{entry.get('title', '')}".strip()
        if room:
            text += f" ({room})"
        return text

    def fetch_timetable(self):
        """Fetch this week's timetable from InfoMentor web endpoint"""
        print("\n[Timetable] Fetching timetable...")

        if not self.web_base_url:
            print("  ✗ ERROR: No web session established")
            return None

        monday, sunday, utc_offset = current_week_range()
        url = f"{self.web_base_url}/timetable/timetable/gettimetablelist"
        headers = {
            "Accept": "application/json",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": f"{self.web_base_url}/",
        }
        body = {
            "UTCOffset": utc_offset,
            "start": monday.strftime("%Y-%m-%d"),
            "end": sunday.strftime("%Y-%m-%d"),
        }

        try:
            response = self.session.post(url, headers=headers, data=body, timeout=30)
        except Exception as e:
            print(f"  ✗ ERROR: Error fetching timetable: {e}")
            return None

        if response.status_code != 200:
            print(
                f"  ✗ ERROR: Timetable endpoint returned status {response.status_code}"
            )
            return None

        try:
            entries = response.json()
        except ValueError:
            print("  ✗ ERROR: Invalid JSON in timetable response")
            return None

        if not isinstance(entries, list):
            print("  ✗ ERROR: Unexpected timetable response shape")
            return None

        self.storage_manager.save_raw("timetable", entries, pupil_id=self.pupil_id)
        print(f"  ✓ Successfully fetched {len(entries)} timetable lessons")
        return monday.strftime("%Y-%m-%d"), entries

    def process_timetable(self):
        """Fetch, compare, and notify about timetable changes"""
        result = self.fetch_timetable()
        if result is None:
            return
        week_str, entries = result
        kind = f"timetable_{week_str}"

        previous = self.storage_manager.load_state(kind, pupil_id=self.pupil_id)
        if previous is None:
            print(f"  → First run for {self.pupil_name}, saving baseline.")
            self.storage_manager.save_state(kind, entries, pupil_id=self.pupil_id)
            return

        old_map = {self.entry_key(e): e for e in previous}
        new_map = {self.entry_key(e): e for e in entries}
        lines = []
        for key, entry in new_map.items():
            if key not in old_map:
                lines.append(f"Added: {self.format_entry(entry)}")
            elif old_map[key] != entry:
                lines.append(f"Changed: {self.format_entry(entry)}")
        for key, entry in old_map.items():
            if key not in new_map:
                lines.append(f"Removed: {self.format_entry(entry)}")

        if lines:
            print(f"  → Found {len(lines)} timetable changes")
            self.notifier.send_changes(
                f"🗓️ Timetable Update ({week_str})", lines,
                pupil_name=self.pupil_name,
            )
        else:
            print("  → No timetable changes")

        self.storage_manager.save_state(kind, entries, pupil_id=self.pupil_id)
