import requests


class DocumentationFetcher:
    def __init__(self, session: requests.Session, storage_manager, notifier):
        self.session = session
        self.storage_manager = storage_manager
        self.notifier = notifier
        self.web_base_url = None
        self.pupil_name = None
        self.pupil_id = None

    def _post(self, path, raw_kind, empty):
        url = f"{self.web_base_url}{path}"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": f"{self.web_base_url}/",
        }
        response = self.session.post(url, headers=headers, json={}, timeout=30)
        if response.status_code != 200:
            print(f"  ✗ ERROR: {path} returned status {response.status_code}")
            return None
        try:
            data = response.json()
        except ValueError:
            if not response.text.strip():
                # Pupils without conferences (e.g. preschool) get 200
                # with an empty body. Not an error.
                print(f"  → {path} not available for this pupil")
                return empty
            print(f"  ✗ ERROR: Invalid JSON from {path}")
            name = (
                f"raw_error_{raw_kind}_{self.pupil_id}.txt"
                if self.pupil_id
                else f"raw_error_{raw_kind}.txt"
            )
            self.storage_manager.save_raw_text(name, response.text[:2000])
            return None
        self.storage_manager.save_raw(raw_kind, data, pupil_id=self.pupil_id)
        return data

    def fetch_documentation(self):
        """Fetch conferences and extra adaptations from InfoMentor"""
        print("\n[Documentation] Fetching documentation...")

        if not self.web_base_url:
            print("  ✗ ERROR: No web session established")
            return None

        try:
            conference = self._post(
                "/Documentation/Conference/GetCurrentConference",
                "documentation_conference",
                {},
            )
            history = self._post(
                "/Documentation/Conference/GetHistoryConferenceList",
                "documentation_history",
                [],
            )
            adaptations = self._post(
                "/Documentation/ExtraAdaptations/GetList",
                "documentation_adaptations",
                [],
            )
        except Exception as e:
            print(f"  ✗ ERROR: Error fetching documentation: {e}")
            return None

        if conference is None or history is None or adaptations is None:
            return None

        current = None
        if isinstance(conference, dict) and conference.get("id"):
            current = {
                "id": conference.get("id"),
                "status": conference.get("status", ""),
                "lastChangesInfo": conference.get("lastChangesInfo", ""),
            }
        print(f"  ✓ Successfully fetched documentation "
              f"(conference: {current['id'] if current else 'none'}, "
              f"{len(history)} archived, {len(adaptations)} adaptations)")
        return {
            "conference": current,
            "history": [h.get("id") for h in history if h.get("id")],
            "history_dates": {
                str(h.get("id")): h.get("changeStatusDate", "") for h in history
            },
            "adaptations": adaptations,
        }

    def process_documentation(self):
        """Fetch, compare, and notify about documentation changes"""
        current = self.fetch_documentation()
        if current is None:
            return

        previous = self.storage_manager.load_state(
            "documentation", pupil_id=self.pupil_id
        )
        if previous is None:
            print(f"  → First run for {self.pupil_name}, saving baseline.")
            self.storage_manager.save_state(
                "documentation", current, pupil_id=self.pupil_id
            )
            return

        lines = []
        old_conf = previous.get("conference") or {}
        new_conf = current.get("conference") or {}
        if new_conf.get("id") and new_conf.get("id") != old_conf.get("id"):
            lines.append(
                f"New conference (status: {new_conf.get('status', '?')})"
            )
        elif new_conf.get("id"):
            if new_conf.get("status") != old_conf.get("status"):
                lines.append(
                    f"Conference status: {old_conf.get('status', '?')} → "
                    f"{new_conf.get('status', '?')}"
                )
            elif new_conf.get("lastChangesInfo") != old_conf.get("lastChangesInfo"):
                lines.append(
                    f"Conference updated: {new_conf.get('lastChangesInfo', '')}"
                )

        old_history = set(previous.get("history", []) or [])
        for conf_id in current.get("history", []) or []:
            if conf_id not in old_history:
                when = current.get("history_dates", {}).get(str(conf_id), "")
                lines.append(f"Conference archived ({when})".rstrip())

        if current.get("adaptations") != previous.get("adaptations"):
            lines.append(
                f"Extra adaptations updated "
                f"({len(current.get('adaptations', []))} items)"
            )

        if lines:
            print(f"  → Found {len(lines)} documentation changes")
            self.notifier.send_changes(
                "📋 Documentation Update", lines, pupil_name=self.pupil_name
            )
        else:
            print("  → No documentation changes")

        self.storage_manager.save_state(
            "documentation", current, pupil_id=self.pupil_id
        )
