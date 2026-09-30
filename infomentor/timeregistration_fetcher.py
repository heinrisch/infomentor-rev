from datetime import datetime, timezone

import requests


class TimeRegistrationFetcher:
    def __init__(self, session: requests.Session, storage_manager, notifier):
        self.session = session
        self.storage_manager = storage_manager
        self.notifier = notifier
        self.web_base_url = None
        self.pupil_name = None
        self.pupil_id = None

    @staticmethod
    def day_summary(day):
        return {
            "onLeave": day.get("onLeave", False),
            "start": (day.get("startDateTime") or "")[11:16],
            "end": (day.get("endDateTime") or "")[11:16],
            "unreadComments": day.get("hasUnreadComments", False),
        }

    def fetch_registrations(self):
        """Fetch fritids time registrations from InfoMentor web endpoint"""
        print("\n[TimeRegistration] Fetching time registrations...")

        if not self.web_base_url:
            print("  ✗ ERROR: No web session established")
            return None

        url = f"{self.web_base_url}/TimeRegistration/TimeRegistration/GetTimeRegistrations/"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": f"{self.web_base_url}/",
        }
        today_utc = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        body = {
            "date": today_utc.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "showNextWeekIfNoMoreSchoolDays": True,
        }

        try:
            response = self.session.post(url, headers=headers, json=body, timeout=30)
        except Exception as e:
            print(f"  ✗ ERROR: Error fetching time registrations: {e}")
            return None

        if response.status_code != 200:
            print("  ✗ ERROR: TimeRegistration endpoint returned status "
                  f"{response.status_code}")
            return None

        try:
            data = response.json()
        except ValueError:
            print("  ✗ ERROR: Invalid JSON in time registrations response")
            return None

        self.storage_manager.save_raw(
            "timeregistration", data, pupil_id=self.pupil_id
        )
        days = data.get("days", []) if isinstance(data, dict) else []
        print(f"  ✓ Successfully fetched {len(days)} registration days")
        return {
            str(d.get("date", "")[:10]): self.day_summary(d)
            for d in days
            if d.get("date")
        }

    def process_registrations(self):
        """Fetch, compare, and notify about registration changes"""
        current = self.fetch_registrations()
        if current is None:
            return

        previous = self.storage_manager.load_state(
            "timeregistration", pupil_id=self.pupil_id
        )
        if previous is None:
            print(f"  → First run for {self.pupil_name}, saving baseline.")
            self.storage_manager.save_state(
                "timeregistration", current, pupil_id=self.pupil_id
            )
            return

        lines = []
        for day, summary in sorted(current.items()):
            old = previous.get(day)
            if old is None:
                continue
            if summary["unreadComments"] and not old.get("unreadComments"):
                lines.append(f"New fritids comment on {day}")
            if summary["onLeave"] != old.get("onLeave"):
                lines.append(
                    f"{day}: marked on leave"
                    if summary["onLeave"]
                    else f"{day}: leave removed"
                )
            if (summary["start"], summary["end"]) != (
                old.get("start"),
                old.get("end"),
            ):
                lines.append(
                    f"{day}: {summary['start']}–{summary['end']}"
                )

        if lines:
            print(f"  → Found {len(lines)} registration changes")
            self.notifier.send_changes(
                "🏫 Fritids Update", lines, pupil_name=self.pupil_name
            )
        else:
            print("  → No registration changes")

        self.storage_manager.save_state(
            "timeregistration", current, pupil_id=self.pupil_id
        )
