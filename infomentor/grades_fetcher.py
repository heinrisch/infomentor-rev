import requests


class GradesFetcher:
    def __init__(self, session: requests.Session, storage_manager, notifier):
        self.session = session
        self.storage_manager = storage_manager
        self.notifier = notifier
        self.web_base_url = None
        self.pupil_name = None
        self.pupil_id = None

    def _post(self, path, body):
        url = f"{self.web_base_url}{path}"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": f"{self.web_base_url}/",
        }
        response = self.session.post(url, headers=headers, json=body, timeout=30)
        if response.status_code != 200:
            print(f"  ✗ ERROR: {path} returned status {response.status_code}")
            return None
        try:
            return response.json()
        except ValueError:
            print(f"  ✗ ERROR: Invalid JSON from {path}")
            return None

    def fetch_grades(self):
        """Fetch summary assessment marks (Lgr22) from InfoMentor"""
        print("\n[Grades] Fetching grades...")

        if not self.web_base_url:
            print("  ✗ ERROR: No web session established")
            return None

        try:
            app_data = self._post("/assessmentv2/assessmentv2/appData", {})
        except Exception as e:
            print(f"  ✗ ERROR: Error fetching grades: {e}")
            return None
        if not app_data:
            return None
        self.storage_manager.save_raw(
            "grades_app", app_data, pupil_id=self.pupil_id
        )

        if not app_data.get("enableSummaryAssessmentLgr22"):
            print("  → Summary assessments not enabled for this pupil")
            return {"terms": "", "marks": {}}

        terms = app_data.get("summaryAssessmentTermsLgr22", []) or []
        term_ids = ",".join(str(t.get("key")) for t in terms if t.get("key"))
        if not term_ids:
            print("  → No assessment terms available")
            return {"terms": "", "marks": {}}

        try:
            data = self._post(
                "/AssessmentV2/SummaryAssessments/GetSummaryAssessmentsLgr22",
                {"termId": term_ids},
            )
        except Exception as e:
            print(f"  ✗ ERROR: Error fetching grades: {e}")
            return None
        if not data:
            return None
        self.storage_manager.save_raw("grades", data, pupil_id=self.pupil_id)

        marks = {}
        for mark in data.get("summaryAssessmentMarks", []) or []:
            subject = mark.get("subject", "?")
            marks[str(subject)] = {
                "hasMarks": mark.get("hasMarks", False),
                "markState": mark.get("markState"),
            }
        print(f"  ✓ Successfully fetched marks for {len(marks)} subjects")
        return {"terms": term_ids, "marks": marks}

    def process_grades(self):
        """Fetch, compare, and notify about new/changed marks"""
        current = self.fetch_grades()
        if current is None:
            return

        previous = self.storage_manager.load_state("grades", pupil_id=self.pupil_id)
        if previous is None:
            print(f"  → First run for {self.pupil_name}, saving baseline.")
            self.storage_manager.save_state("grades", current, pupil_id=self.pupil_id)
            return

        old_marks = previous.get("marks", {})
        lines = []
        for subject, mark in current["marks"].items():
            old = old_marks.get(subject)
            if not mark.get("hasMarks"):
                continue
            if old is None or not old.get("hasMarks"):
                lines.append(f"New mark in {subject}")
            elif old.get("markState") != mark.get("markState"):
                lines.append(f"Updated mark in {subject}")

        if lines:
            print(f"  → Found {len(lines)} grade changes")
            self.notifier.send_changes(
                "📊 Grades Update", lines, pupil_name=self.pupil_name
            )
        else:
            print("  → No grade changes")

        self.storage_manager.save_state("grades", current, pupil_id=self.pupil_id)
