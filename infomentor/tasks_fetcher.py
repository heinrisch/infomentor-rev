import requests

# Task item shape varies; pick the first known key for each role.
TITLE_KEYS = ("title", "name", "subject")
DUE_KEYS = ("dueDate", "deadline", "endDate", "end", "date")
STATE_KEYS = ("status", "state")


class TaskFetcher:
    def __init__(self, session: requests.Session, storage_manager, notifier):
        self.session = session
        self.storage_manager = storage_manager
        self.notifier = notifier
        self.web_base_url = None
        self.pupil_name = None
        self.pupil_id = None

    @staticmethod
    def summarize_task(item):
        """One-line human summary from best-effort fields."""
        title = next(
            (str(item.get(k)) for k in TITLE_KEYS if item.get(k)),
            f"Task {item.get('id', '?')}",
        )
        due = next((str(item.get(k)) for k in DUE_KEYS if item.get(k)), None)
        state = next((str(item.get(k)) for k in STATE_KEYS if item.get(k)), None)
        line = title
        if due:
            line += f" (due {due})"
        if state:
            line += f" [{state}]"
        return line

    def fetch_tasks(self):
        """Fetch homework/tasks overview from InfoMentor web endpoint"""
        print("\n[Tasks] Fetching tasks...")

        if not self.web_base_url:
            print("  ✗ ERROR: No web session established")
            return None

        url = f"{self.web_base_url}/task/task/appData"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": f"{self.web_base_url}/",
        }

        try:
            response = self.session.post(url, headers=headers, json={}, timeout=30)
        except Exception as e:
            print(f"  ✗ ERROR: Error fetching tasks: {e}")
            return None

        if response.status_code != 200:
            print(
                f"  ✗ ERROR: Tasks endpoint returned status {response.status_code}"
            )
            return None

        try:
            data = response.json()
        except ValueError:
            print("  ✗ ERROR: Invalid JSON in tasks response")
            return None

        self.storage_manager.save_raw("tasks", data, pupil_id=self.pupil_id)
        results = data.get("taskResults", {}) if isinstance(data, dict) else {}
        items = results.get("items", []) or []
        print(f"  ✓ Successfully fetched {len(items)} tasks "
              f"({results.get('totalOverdue', 0)} overdue)")
        if results.get("more"):
            print("  ⚠ More tasks available than returned (paging unknown)")
        return {
            "items": items,
            "overdue": results.get("totalOverdue", 0),
            "due": results.get("totalDue", 0),
        }

    def process_tasks(self):
        """Fetch, compare, and notify about new/changed tasks"""
        current = self.fetch_tasks()
        if current is None:
            return

        previous = self.storage_manager.load_state("tasks", pupil_id=self.pupil_id)
        state = {
            "items": {str(i.get("id")): i for i in current["items"] if i.get("id")},
            "overdue": current["overdue"],
            "due": current["due"],
        }

        if previous is None:
            print(f"  → First run for {self.pupil_name}, saving baseline.")
            self.storage_manager.save_state("tasks", state, pupil_id=self.pupil_id)
            return

        old_items = previous.get("items", {})
        lines = []
        for item_id, item in state["items"].items():
            old = old_items.get(item_id)
            if old is None:
                lines.append(f"New: {self.summarize_task(item)}")
            elif old != item:
                lines.append(f"Updated: {self.summarize_task(item)}")

        old_overdue = previous.get("overdue", 0)
        if state["overdue"] > old_overdue:
            lines.append(
                f"Overdue tasks: {state['overdue']} (was {old_overdue})"
            )

        if lines:
            print(f"  → Found {len(lines)} task changes")
            self.notifier.send_changes(
                "📝 Tasks Update", lines, pupil_name=self.pupil_name
            )
        else:
            print("  → No task changes")

        self.storage_manager.save_state("tasks", state, pupil_id=self.pupil_id)
