import json
import requests

# Guard against runaway paging if the server misbehaves.
MAX_ATTENDANCE_PAGES = 20
ATTENDANCE_PAGE_SIZE = 20


class AttendanceFetcher:
    def __init__(self, session: requests.Session, storage_manager, notifier):
        self.session = session
        self.storage_manager = storage_manager
        self.notifier = notifier
        self.web_base_url = None
        self.pupil_name = None
        self.pupil_id = None

    @staticmethod
    def record_key(record):
        """Stable identity for an attendance record.

        Uses the fields the API actually returns. The numeric id alone
        is not enough: grouped rows carry negative placeholder ids.
        """
        return (
            record.get("id"),
            record.get("shortDate"),
            record.get("time"),
            record.get("subject"),
            record.get("reason"),
        )

    def fetch_attendance(self):
        """Fetch attendance from InfoMentor web endpoint"""
        print("\n[Attendance] Fetching attendance...")

        if not self.web_base_url:
            print("  ✗ ERROR: No web session established")
            return []

        url = f"{self.web_base_url}/Attendance/attendance/GetAttendanceList"

        headers = {
            "Accept": "application/json, text/javascript, */*; q=0.01",
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
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "X-Requested-With": "XMLHttpRequest",
        }

        # The endpoint might expect some parameters in the POST body,
        # but often InfoMentor's 'List' endpoints can take an empty object for defaults.
        records = []
        seen_keys = set()
        page = 1

        while page <= MAX_ATTENDANCE_PAGES:
            # The first request keeps the known-good empty body; later
            # pages ask explicitly. If the server ignores the paging
            # params the page number won't advance and we stop.
            body = (
                {}
                if page == 1
                else {"page": page, "pageSize": ATTENDANCE_PAGE_SIZE}
            )

            try:
                response = self.session.post(
                    url, headers=headers, json=body, timeout=30
                )
            except Exception as e:
                print(f"  ✗ ERROR: Error fetching attendance: {e}")
                return records

            if response.status_code != 200:
                print(
                    f"  ✗ ERROR: Attendance endpoint returned status {response.status_code}"
                )
                return records

            try:
                result = response.json()
            except json.JSONDecodeError:
                print("  ✗ ERROR: Invalid JSON in attendance response")
                return records

            kind = "attendance" if page == 1 else f"attendance_p{page}"
            self.storage_manager.save_raw(
                kind, result, pupil_id=self.pupil_id
            )

            # InfoMentor often returns a list directly or in a 'data' field
            if isinstance(result, list):
                items, more, got_page, total = result, False, page, None
            elif isinstance(result, dict):
                items = result.get("items") or result.get("data") or []
                more = bool(result.get("more"))
                got_page = result.get("page", page)
                total = result.get("totalItems")
            else:
                items, more, got_page, total = [], False, page, None

            for item in items:
                key = self.record_key(item)
                if key not in seen_keys:
                    seen_keys.add(key)
                    records.append(item)

            if not items or not more:
                break
            if total is not None and len(records) >= total:
                break
            if str(got_page) != str(page):
                print(
                    f"  ⚠ Attendance paging not honored "
                    f"(asked page {page}, got {got_page}), stopping"
                )
                break
            page += 1
        else:
            print(
                f"  ⚠ Attendance paging stopped after {MAX_ATTENDANCE_PAGES} pages"
            )

        print(f"  ✓ Successfully fetched {len(records)} attendance records")
        return records

    def process_attendance(self):
        """Fetch, save, and notify about new attendance records"""
        current_attendance = self.fetch_attendance()
        if not current_attendance:
            # If it's an empty list, it might just be no records, 
            # but we only process if we actually got a response.
            if current_attendance == []:
                # Save empty list if it's the first time
                previous_attendance = self.storage_manager.load_attendance(pupil_id=self.pupil_id)
                if previous_attendance is None:
                     self.storage_manager.save_attendance([], pupil_id=self.pupil_id)
            return

        previous_attendance = self.storage_manager.load_attendance(pupil_id=self.pupil_id)
        
        if previous_attendance is None:
            # First time fetching attendance for this pupil
            print(f"  → First run for {self.pupil_name}, saving baseline.")
            self.storage_manager.save_attendance(current_attendance, pupil_id=self.pupil_id)
            return

        # Find new records
        previous_keys = {self.record_key(r) for r in previous_attendance}
        new_records = [
            r for r in current_attendance if self.record_key(r) not in previous_keys
        ]

        if new_records:
            print(f"  → Found {len(new_records)} new attendance records")
            self.notifier.send_attendance_update(new_records, pupil_name=self.pupil_name)
            self.storage_manager.save_attendance(current_attendance, pupil_id=self.pupil_id)
        else:
            print("  → No new attendance records")
