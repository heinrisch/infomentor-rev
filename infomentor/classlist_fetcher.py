import requests


class ClassListFetcher:
    def __init__(self, session: requests.Session, storage_manager, notifier):
        self.session = session
        self.storage_manager = storage_manager
        self.notifier = notifier
        self.web_base_url = None
        self.pupil_name = None
        self.pupil_id = None

    def fetch_classlist(self):
        """Fetch class/staff lists from InfoMentor web endpoint"""
        print("\n[ClassList] Fetching class list...")

        if not self.web_base_url:
            print("  ✗ ERROR: No web session established")
            return None

        url = f"{self.web_base_url}/classlist/classlist/appData"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": f"{self.web_base_url}/",
        }

        try:
            response = self.session.post(url, headers=headers, json={}, timeout=30)
        except Exception as e:
            print(f"  ✗ ERROR: Error fetching class list: {e}")
            return None

        if response.status_code != 200:
            print(
                f"  ✗ ERROR: ClassList endpoint returned status {response.status_code}"
            )
            return None

        try:
            data = response.json()
        except ValueError:
            print("  ✗ ERROR: Invalid JSON in class list response")
            return None

        self.storage_manager.save_raw("classlist", data, pupil_id=self.pupil_id)
        groups = data.get("groupConfig", []) if isinstance(data, dict) else []
        total = sum(len(g.get("items", []) or []) for g in groups)
        print(f"  ✓ Successfully fetched {total} contacts "
              f"in {len(groups)} groups")
        return {
            str(g.get("title", "?")): {
                str(i.get("id")): i.get("name", "?")
                for i in (g.get("items", []) or [])
                if i.get("id")
            }
            for g in groups
        }

    def process_classlist(self):
        """Fetch, compare, and notify about membership changes only"""
        current = self.fetch_classlist()
        if current is None:
            return

        previous = self.storage_manager.load_state(
            "classlist", pupil_id=self.pupil_id
        )
        if previous is None:
            print(f"  → First run for {self.pupil_name}, saving baseline.")
            self.storage_manager.save_state(
                "classlist", current, pupil_id=self.pupil_id
            )
            return

        lines = []
        for group, members in current.items():
            old_members = previous.get(group, {})
            for member_id, name in members.items():
                if member_id not in old_members:
                    lines.append(f"{name} joined {group}")
                elif old_members[member_id] != name:
                    lines.append(f"{old_members[member_id]} renamed to {name}")
            for member_id, name in old_members.items():
                if member_id not in members:
                    lines.append(f"{name} left {group}")

        if lines:
            print(f"  → Found {len(lines)} class list changes")
            self.notifier.send_changes(
                "👋 Class List Update", lines, pupil_name=self.pupil_name
            )
        else:
            print("  → No class list changes")

        self.storage_manager.save_state(
            "classlist", current, pupil_id=self.pupil_id
        )
