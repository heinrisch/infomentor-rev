import json
import requests


class AttendanceFetcher:
    def __init__(self, session: requests.Session, storage_manager, notifier):
        self.session = session
        self.storage_manager = storage_manager
        self.notifier = notifier
        self.web_base_url = None
        self.pupil_name = None
        self.pupil_id = None

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
        data = {}

        try:
            response = self.session.post(
                url, headers=headers, json=data, timeout=30
            )

            if response.status_code == 200:
                try:
                    # InfoMentor often returns a list directly or in a 'data' field
                    result = response.json()
                    if isinstance(result, list):
                        attendance_list = result
                    elif isinstance(result, dict):
                        attendance_list = result.get("items") or result.get("data") or []
                    else:
                        attendance_list = []
                        
                    print(f"  ✓ Successfully fetched {len(attendance_list)} attendance records")
                    return attendance_list
                except json.JSONDecodeError:
                    print("  ✗ ERROR: Invalid JSON in attendance response")
                    return []
            else:
                print(
                    f"  ✗ ERROR: Attendance endpoint returned status {response.status_code}"
                )
                return []
        except Exception as e:
            print(f"  ✗ ERROR: Error fetching attendance: {e}")
            return []

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
        # Use a combination of fields as a unique key since InfoMentor items don't always have IDs
        def get_record_key(r):
            return f"{r.get('dateString')}_{r.get('lessonName')}_{r.get('registrationTypeName')}_{r.get('startTime')}"

        previous_keys = {get_record_key(r) for r in previous_attendance}
        new_records = [r for r in current_attendance if get_record_key(r) not in previous_keys]

        if new_records:
            print(f"  → Found {len(new_records)} new attendance records")
            self.notifier.send_attendance_update(new_records, pupil_name=self.pupil_name)
            self.storage_manager.save_attendance(current_attendance, pupil_id=self.pupil_id)
        else:
            print("  → No new attendance records")
