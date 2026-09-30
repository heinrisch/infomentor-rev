import requests


class UolFetcher:
    def __init__(self, session: requests.Session, storage_manager, notifier):
        self.session = session
        self.storage_manager = storage_manager
        self.notifier = notifier
        self.web_base_url = None
        self.pupil_name = None
        self.pupil_id = None

    def fetch_uols(self):
        """Fetch units of learning from InfoMentor web endpoint"""
        print("\n[UOL] Fetching units of learning...")

        if not self.web_base_url:
            print("  ✗ ERROR: No web session established")
            return None

        url = f"{self.web_base_url}/uolv2/uolv2/appData"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": f"{self.web_base_url}/",
        }

        try:
            response = self.session.post(url, headers=headers, json={}, timeout=30)
        except Exception as e:
            print(f"  ✗ ERROR: Error fetching units of learning: {e}")
            return None

        if response.status_code != 200:
            print(f"  ✗ ERROR: UOL endpoint returned status {response.status_code}")
            return None

        try:
            data = response.json()
        except ValueError:
            print("  ✗ ERROR: Invalid JSON in UOL response")
            return None

        self.storage_manager.save_raw("uol", data, pupil_id=self.pupil_id)
        uols = data.get("uols", []) if isinstance(data, dict) else []
        print(f"  ✓ Successfully fetched {len(uols)} units of learning")
        return {
            str(u.get("id")): {
                "title": u.get("title", "?"),
                "state": u.get("state", ""),
            }
            for u in uols
            if u.get("id")
        }

    def process_uols(self):
        """Fetch, compare, and notify about UOL changes (never the full list)"""
        current = self.fetch_uols()
        if current is None:
            return

        previous = self.storage_manager.load_state("uol", pupil_id=self.pupil_id)
        if previous is None:
            print(f"  → First run for {self.pupil_name}, saving baseline.")
            self.storage_manager.save_state("uol", current, pupil_id=self.pupil_id)
            return

        lines = []
        for uol_id, uol in current.items():
            old = previous.get(uol_id)
            if old is None:
                lines.append(f"New: {uol['title']}")
            elif old.get("state") != uol.get("state"):
                lines.append(
                    f"{uol['title']}: {old.get('state', '?')} → {uol.get('state', '?')}"
                )

        if lines:
            print(f"  → Found {len(lines)} UOL changes")
            self.notifier.send_changes(
                "📚 Learning Update", lines, pupil_name=self.pupil_name
            )
        else:
            print("  → No UOL changes")

        self.storage_manager.save_state("uol", current, pupil_id=self.pupil_id)
