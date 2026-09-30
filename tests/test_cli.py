"""Tests for raw response dumps and the --no-notify flag.

Stdlib only (unittest); run with: python3 -m unittest discover tests
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from infomentor.storage import StorageManager


class StorageRawTest(unittest.TestCase):
    def test_save_raw_roundtrip_and_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            storage = StorageManager(Path(tmp) / "news", Path(tmp) / "files")
            first = storage.save_raw("news", {"items": [1]}, pupil_id="7")
            self.assertTrue(first.name.startswith("raw_news_7"))
            second = storage.save_raw("news", {"items": [1, 2]}, pupil_id="7")
            self.assertEqual(first, second)  # latest wins, no accumulation
            saved = json.loads(second.read_text(encoding="utf-8"))
            self.assertEqual(saved, {"items": [1, 2]})
            # raw files must not pollute the news id scan
            self.assertEqual(storage.get_existing_ids(pupil_id="7"), set())

    def test_save_raw_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            storage = StorageManager(Path(tmp) / "news", Path(tmp) / "files")
            path = storage.save_raw_text("raw_pupils.html", "<html></html>")
            self.assertEqual(path.read_text(encoding="utf-8"), "<html></html>")


class NoNotifyTest(unittest.TestCase):
    def test_no_notify_wires_zero_notifiers(self):
        from infomentor.runner import InfoMentorFetcher

        fetcher = InfoMentorFetcher(notify=False)
        self.assertEqual(fetcher.notifier.notifiers, [])

    def test_fetch_help_mentions_no_notify(self):
        proc = subprocess.run(
            [sys.executable, str(ROOT / "cli.py"), "fetch", "--help"],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertIn("--no-notify", proc.stdout)

    def test_no_llm_disables_summarization(self):
        from infomentor.llm_client import LLMClient
        from infomentor.runner import InfoMentorFetcher

        client = LLMClient("key", "key", enabled=False)
        self.assertIsNone(client.summarize_news_entry("x" * 500, "2026-01-01"))
        fetcher = InfoMentorFetcher(enable_llm=False)
        self.assertFalse(fetcher.llm_client.enabled)


class FakeJsonResponse:
    _NO_TEXT = object()

    def __init__(self, payload=None, status_code=200, raw_text=_NO_TEXT):
        self._payload = payload
        self.status_code = status_code
        self._raw_text = raw_text

    def json(self):
        if self._raw_text is not FakeJsonResponse._NO_TEXT:
            raise ValueError("Invalid JSON")
        return self._payload

    @property
    def text(self):
        if self._raw_text is FakeJsonResponse._NO_TEXT:
            return ""
        return self._raw_text


class FakeRawResponse(FakeJsonResponse):
    """Non-JSON response with a given body."""

    def __init__(self, raw_text, status_code=200):
        super().__init__(status_code=status_code, raw_text=raw_text)


class FakePostSession:
    """Replays canned POST responses and records request bodies."""

    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.bodies = []

    def post(self, url, headers=None, json=None, data=None, timeout=None):
        self.bodies.append(json if json is not None else data)
        return FakeJsonResponse(self.payloads.pop(0))


class FakeRawPostSession(FakePostSession):
    """Like FakePostSession but replays response objects as-is."""

    def post(self, url, headers=None, json=None, data=None, timeout=None):
        self.bodies.append(json if json is not None else data)
        return self.payloads.pop(0)


def make_storage(tmp):
    return StorageManager(Path(tmp) / "news", Path(tmp) / "files")


def process_with(fetcher_cls, payloads, tmp, pupil_id="7"):
    """Run a fetcher's process_* once with canned responses."""
    storage = make_storage(tmp)
    capture = CaptureNotifier()
    fetcher = fetcher_cls(FakePostSession(payloads), storage, capture.notifier)
    fetcher.web_base_url = "https://hub.infomentor.se"
    fetcher.pupil_id = pupil_id
    fetcher.pupil_name = "Test Pupil"
    process = next(
        getattr(fetcher, name)
        for name in dir(fetcher)
        if name.startswith("process_")
    )
    process()
    return capture.sent


def attendance_record(**overrides):
    record = {
        "id": 243858266,
        "shortDate": "2026-09-01",
        "longDate": "den 1 september 2026",
        "time": "09:10",
        "subject": "Svenska",
        "reason": "Sen ankomst - ogiltig",
        "comment": "",
        "minutes": "5",
    }
    record.update(overrides)
    return record


class AttendanceRecordKeyTest(unittest.TestCase):
    def test_same_record_same_key(self):
        from infomentor.attendance_fetcher import AttendanceFetcher

        self.assertEqual(
            AttendanceFetcher.record_key(attendance_record()),
            AttendanceFetcher.record_key(attendance_record()),
        )

    def test_distinct_records_distinct_keys(self):
        from infomentor.attendance_fetcher import AttendanceFetcher

        key = AttendanceFetcher.record_key
        base = key(attendance_record())
        self.assertNotEqual(base, key(attendance_record(id=999)))
        self.assertNotEqual(base, key(attendance_record(shortDate="2026-09-02")))
        self.assertNotEqual(base, key(attendance_record(reason="Sjuk")))

    def test_placeholder_ids_tell_rows_apart(self):
        from infomentor.attendance_fetcher import AttendanceFetcher

        key = AttendanceFetcher.record_key
        first = key(attendance_record(id=-1, shortDate="2026-09-01"))
        second = key(attendance_record(id=-1, shortDate="2026-09-02"))
        self.assertNotEqual(first, second)


class AttendancePagingTest(unittest.TestCase):
    def make_fetcher(self, session, tmp):
        from infomentor.attendance_fetcher import AttendanceFetcher

        storage = StorageManager(Path(tmp) / "news", Path(tmp) / "files")
        fetcher = AttendanceFetcher(session, storage, notifier=None)
        fetcher.web_base_url = "https://hub.infomentor.se"
        fetcher.pupil_id = "7"
        return fetcher, storage

    def test_combines_pages(self):
        first = attendance_record()
        second = attendance_record(id=2, shortDate="2026-09-02")
        third = attendance_record(id=3, shortDate="2026-09-03")
        session = FakePostSession(
            [
                {"page": 1, "totalItems": 3, "items": [first], "more": True},
                {"page": 2, "totalItems": 3, "items": [second, third],
                 "more": False},
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            fetcher, _ = self.make_fetcher(session, tmp)
            records = fetcher.fetch_attendance()
        self.assertEqual(len(records), 3)
        self.assertEqual(session.bodies[0], {})
        self.assertEqual(session.bodies[1], {"page": 2, "pageSize": 20})

    def test_ignores_unhonored_paging_without_dupes(self):
        record = attendance_record()
        page = {"page": 1, "totalItems": 99, "items": [record], "more": True}
        session = FakePostSession([page, dict(page)])
        with tempfile.TemporaryDirectory() as tmp:
            fetcher, _ = self.make_fetcher(session, tmp)
            records = fetcher.fetch_attendance()
        self.assertEqual(len(session.bodies), 2)
        self.assertEqual(records, [record])


class CaptureNotifier:
    """TelegramNotifier with network stubbed out."""

    def __init__(self):
        from infomentor.telegram_notifier import TelegramNotifier

        self.notifier = TelegramNotifier.__new__(TelegramNotifier)
        self.sent = []
        self.notifier.send_message = self.capture

    def capture(self, text, parse_mode=None, disable_web_page_preview=False):
        self.sent.append(text)
        return True


class AttendanceMessageTest(unittest.TestCase):
    def test_renders_real_fields(self):
        capture = CaptureNotifier()
        capture.notifier.send_attendance_update([attendance_record()])
        (text,) = capture.sent
        self.assertIn("Sen ankomst", text)
        self.assertIn("Svenska", text)
        self.assertIn("09:10", text)
        self.assertIn("5 min", text)
        self.assertNotIn("Unknown", text)

    def test_lesson_line_dropped_when_no_lesson(self):
        capture = CaptureNotifier()
        capture.notifier.send_attendance_update(
            [attendance_record(subject=None, time=None)]
        )
        (text,) = capture.sent
        self.assertNotIn("Lesson:", text)
        self.assertNotIn("Unknown Lesson", text)
        self.assertIn("Sen ankomst", text)


class CalendarUrlTest(unittest.TestCase):
    def test_parse_calendar_url(self):
        from infomentor.notification_fetcher import parse_calendar_url

        self.assertEqual(
            parse_calendar_url(
                "/#/calendarv2/whole_week"
                "?selectedYear=2026&selectedWeek=39&eventId=221961206"
            ),
            (2026, 39, 221961206),
        )
        self.assertIsNone(parse_calendar_url("/#/communication/news/1915089"))
        self.assertIsNone(parse_calendar_url(None))
        self.assertIsNone(
            parse_calendar_url("/#/calendarv2/whole_week?selectedYear=2026")
        )

    def test_calendar_week_range(self):
        from infomentor.notification_fetcher import calendar_week_range

        self.assertEqual(
            calendar_week_range(2026, 39), ("2026/09/20", "2026/09/28")
        )
        self.assertIsNone(calendar_week_range(2025, 53))

    def test_calendar_entry_to_item(self):
        from infomentor.notification_fetcher import NotificationFetcher

        item = NotificationFetcher.calendar_entry_to_item(
            {
                "title": "Tidig stängning",
                "description": "<p>Skolan stänger kl. 15.</p>",
                "formattedStartDate": "tor 2 okt",
                "startTime": "08:00",
                "endTime": "15:00",
            }
        )
        self.assertEqual(item["title"], "Tidig stängning")
        self.assertIn("Skolan stänger", item["content"])
        self.assertEqual(item["publishedDateString"], "tor 2 okt")
        self.assertEqual(item["publishedBy"], "08:00-15:00")


class FakeGetResponse:
    status_code = 200

    def __init__(self, content=b"img", content_type="image/jpeg"):
        self._content = content
        self.headers = {"Content-Type": content_type}

    def iter_content(self, chunk_size=None):
        yield self._content


class FakeGetSession:
    def __init__(self, response):
        self.response = response

    def get(self, url, stream=None, timeout=None):
        return self.response


class NewsImageTest(unittest.TestCase):
    def make_fetcher(self, tmp, content_type="image/jpeg"):
        from infomentor.news_fetcher import NewsFetcher

        files_dir = Path(tmp) / "files"
        files_dir.mkdir()
        session = FakeGetSession(FakeGetResponse(content_type=content_type))
        fetcher = NewsFetcher(session, None, None, None, files_dir)
        fetcher.web_base_url = "https://hub.infomentor.se"
        return fetcher

    def test_image_downloaded_with_extension(self):
        with tempfile.TemporaryDirectory() as tmp:
            fetcher = self.make_fetcher(tmp)
            count, paths = fetcher.download_attachments(
                {
                    "id": 99,
                    "attachments": [],
                    "newsImageUrl": "/Resources/Resource/Download/1?api=IM2",
                },
                set(),
            )
            self.assertEqual(count, 1)
            self.assertEqual(paths[0].name, "news_99_image.jpg")
            self.assertTrue(paths[0].exists())

    def test_image_skipped_when_already_an_attachment(self):
        with tempfile.TemporaryDirectory() as tmp:
            fetcher = self.make_fetcher(tmp)
            count, paths = fetcher.download_attachments(
                {
                    "id": 99,
                    "attachments": [
                        {
                            "url": "/Resources/Resource/Download/1?api=IM2",
                            "title": "pic.pdf",
                        }
                    ],
                    "newsImageUrl": "/Resources/Resource/Download/1?api=IM2",
                },
                set(),
            )
        self.assertEqual(count, 1)
        self.assertEqual(paths[0].name, "pic.pdf")


class StorageStateTest(unittest.TestCase):
    def test_roundtrip_and_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            storage = make_storage(tmp)
            self.assertIsNone(storage.load_state("tasks", pupil_id="7"))
            storage.save_state("tasks", {"a": 1}, pupil_id="7")
            self.assertEqual(
                storage.load_state("tasks", pupil_id="7"), {"a": 1}
            )


class ChangesMessageTest(unittest.TestCase):
    def test_formats_title_pupil_and_lines(self):
        capture = CaptureNotifier()
        capture.notifier.send_changes(
            "📝 Tasks Update", ["New: x", "Updated: y"], pupil_name="N N"
        )
        (text,) = capture.sent
        self.assertIn("Tasks Update", text)
        self.assertIn("N N", text)
        self.assertIn("New: x", text)

    def test_empty_sends_nothing_and_long_capped(self):
        capture = CaptureNotifier()
        capture.notifier.send_changes("T", [], pupil_name=None)
        self.assertEqual(capture.sent, [])
        capture.notifier.send_changes(
            "T", [f"line {i}" for i in range(30)], pupil_name=None
        )
        (text,) = capture.sent
        self.assertIn("line 24", text)
        self.assertNotIn("line 25", text)
        self.assertIn("5 more", text)


class TasksProcessTest(unittest.TestCase):
    def test_new_task_notifies_and_rerun_silent(self):
        from infomentor.tasks_fetcher import TaskFetcher

        empty = {"taskResults": {"items": [], "more": False,
                                "totalOverdue": 0, "totalDue": 0}}
        task = {"id": 5, "title": "Läxa kap 3", "dueDate": "2026-10-02"}
        one = {"taskResults": {"items": [task], "more": False,
                              "totalOverdue": 0, "totalDue": 1}}
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(process_with(TaskFetcher, [empty], tmp), [])
            sent = process_with(TaskFetcher, [one], tmp)
            self.assertEqual(len(sent), 1)
            self.assertIn("Läxa kap 3", sent[0])
            self.assertEqual(process_with(TaskFetcher, [one], tmp), [])

    def test_overdue_increase_notifies(self):
        from infomentor.tasks_fetcher import TaskFetcher

        def payload(overdue):
            return {"taskResults": {"items": [], "more": False,
                                   "totalOverdue": overdue, "totalDue": 0}}

        with tempfile.TemporaryDirectory() as tmp:
            process_with(TaskFetcher, [payload(0)], tmp)
            sent = process_with(TaskFetcher, [payload(2)], tmp)
            self.assertEqual(len(sent), 1)
            self.assertIn("Overdue", sent[0])


class GradesProcessTest(unittest.TestCase):
    APP = {
        "enableSummaryAssessmentLgr22": True,
        "summaryAssessmentTermsLgr22": [
            {"key": "1", "value": "t1"},
            {"key": "2", "value": "t2"},
        ],
    }

    def marks(self, **overrides):
        mark = {"subject": "Bild", "id": 1, "hasMarks": False,
                "markState": None}
        mark.update(overrides)
        return {"summaryAssessmentMarks": [mark]}

    def test_new_mark_notifies(self):
        from infomentor.grades_fetcher import GradesFetcher

        with tempfile.TemporaryDirectory() as tmp:
            sent = process_with(
                GradesFetcher, [dict(self.APP), self.marks()], tmp
            )
            self.assertEqual(sent, [])  # baseline, no marks yet
            sent = process_with(
                GradesFetcher,
                [dict(self.APP), self.marks(hasMarks=True, markState=2)],
                tmp,
            )
            self.assertEqual(len(sent), 1)
            self.assertIn("Bild", sent[0])

    def test_term_ids_joined_from_app_data(self):
        from infomentor.grades_fetcher import GradesFetcher

        session = FakePostSession([dict(self.APP), self.marks()])
        with tempfile.TemporaryDirectory() as tmp:
            storage = make_storage(tmp)
            fetcher = GradesFetcher(session, storage, None)
            fetcher.web_base_url = "https://hub.infomentor.se"
            fetcher.fetch_grades()
        self.assertEqual(session.bodies[1], {"termId": "1,2"})


class DocumentationProcessTest(unittest.TestCase):
    def payloads(self, status="Started", info="a"):
        return [
            {"id": 9, "status": status, "lastChangesInfo": info},
            [{"id": 9, "changeStatusDate": "igår"}],
            [],
        ]

    def test_status_change_notifies(self):
        from infomentor.documentation_fetcher import DocumentationFetcher

        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(
                process_with(DocumentationFetcher, self.payloads(), tmp), []
            )
            sent = process_with(
                DocumentationFetcher, self.payloads(status="Completed"), tmp
            )
            self.assertEqual(len(sent), 1)
            self.assertIn("Completed", sent[0])

    def test_empty_body_means_not_available(self):
        from infomentor.documentation_fetcher import DocumentationFetcher
        from infomentor.storage import StorageManager

        with tempfile.TemporaryDirectory() as tmp:
            storage = make_storage(tmp)
            capture = CaptureNotifier()
            session = FakeRawPostSession(
                [FakeRawResponse(""), FakeRawResponse(""), FakeJsonResponse([])]
            )
            fetcher = DocumentationFetcher(session, storage, capture.notifier)
            fetcher.web_base_url = "https://hub.infomentor.se"
            fetcher.pupil_id = "7"
            fetcher.process_documentation()
            # Baseline saved, nothing sent, no error state saved
            self.assertEqual(capture.sent, [])
            state = storage.load_state("documentation", pupil_id="7")
            self.assertIsNotNone(state)
            self.assertIsNone(state["conference"])

    def test_garbage_body_saved_for_inspection(self):
        from infomentor.documentation_fetcher import DocumentationFetcher

        with tempfile.TemporaryDirectory() as tmp:
            storage = make_storage(tmp)
            capture = CaptureNotifier()
            session = FakeRawPostSession(
                [
                    FakeRawResponse("<html>oops</html>"),
                    FakeJsonResponse([]),
                    FakeJsonResponse([]),
                ]
            )
            fetcher = DocumentationFetcher(session, storage, capture.notifier)
            fetcher.web_base_url = "https://hub.infomentor.se"
            fetcher.pupil_id = "7"
            fetcher.process_documentation()
            self.assertEqual(capture.sent, [])
            self.assertIsNone(storage.load_state("documentation", pupil_id="7"))
            debug = Path(tmp) / "news" / "raw_error_documentation_conference_7.txt"
            self.assertTrue(debug.exists())
            self.assertIn("oops", debug.read_text(encoding="utf-8"))


class TimetableProcessTest(unittest.TestCase):
    def lesson(self, **overrides):
        entry = {
            "start": "2026-09-28T08:10:00",
            "end": "2026-09-28T09:00:00",
            "title": "Svenska",
            "startTime": "08:10",
            "endTime": "09:00",
            "notes": {"roomInfo": "G310"},
        }
        entry.update(overrides)
        return entry

    def test_week_range_is_monday_to_sunday(self):
        from infomentor.timetable_fetcher import current_week_range

        monday, sunday, _ = current_week_range()
        self.assertEqual(monday.weekday(), 0)
        self.assertEqual((sunday - monday).days, 6)

    def test_added_lesson_notifies(self):
        from infomentor.timetable_fetcher import TimetableFetcher

        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(process_with(TimetableFetcher, [[]], tmp), [])
            sent = process_with(TimetableFetcher, [[self.lesson()]], tmp)
            self.assertEqual(len(sent), 1)
            self.assertIn("Svenska", sent[0])
            self.assertIn("G310", sent[0])


class TimeRegistrationProcessTest(unittest.TestCase):
    def day(self, **overrides):
        day = {
            "date": "2026-09-28T00:00:00",
            "startDateTime": "2026-09-28T07:00:00",
            "endDateTime": "2026-09-28T17:00:00",
            "onLeave": False,
            "hasUnreadComments": False,
        }
        day.update(overrides)
        return {"days": [day]}

    def test_unread_comment_notifies(self):
        from infomentor.timeregistration_fetcher import TimeRegistrationFetcher

        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(
                process_with(TimeRegistrationFetcher, [self.day()], tmp), []
            )
            sent = process_with(
                TimeRegistrationFetcher,
                [self.day(hasUnreadComments=True)],
                tmp,
            )
            self.assertEqual(len(sent), 1)
            self.assertIn("comment", sent[0])


class UolClasslistProcessTest(unittest.TestCase):
    def test_uol_state_change_notifies(self):
        from infomentor.uol_fetcher import UolFetcher

        def payload(state):
            return {"uols": [{"id": 3, "title": "Bråk", "state": state}]}

        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(process_with(UolFetcher, [payload("active")], tmp), [])
            sent = process_with(UolFetcher, [payload("finished")], tmp)
            self.assertEqual(len(sent), 1)
            self.assertIn("Bråk", sent[0])

    def test_classlist_membership_changes_notify(self):
        from infomentor.classlist_fetcher import ClassListFetcher

        def payload(names):
            return {
                "groupConfig": [
                    {
                        "title": "2B",
                        "items": [
                            {"id": str(i), "name": n}
                            for i, n in enumerate(names)
                        ],
                    }
                ]
            }

        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(
                process_with(ClassListFetcher, [payload(["A"])], tmp), []
            )
            sent = process_with(ClassListFetcher, [payload(["A", "B"])], tmp)
            self.assertEqual(len(sent), 1)
            self.assertIn("B", sent[0])
            self.assertIn("2B", sent[0])


class ScheduleTimeTest(unittest.TestCase):
    def test_at_type_parses_times(self):
        from cli import at_type

        times = at_type("06:00,18:00")
        self.assertEqual(
            [(t.hour, t.minute) for t in times], [(6, 0), (18, 0)]
        )

    def test_at_type_rejects_garbage(self):
        import argparse

        from cli import at_type

        for bad in ("25:00", "abc", "06:00,xx"):
            with self.assertRaises(argparse.ArgumentTypeError):
                at_type(bad)

    def test_next_run_same_day(self):
        from datetime import datetime

        from infomentor.runner import seconds_until_next_run
        from cli import at_type

        now = datetime(2026, 1, 1, 4, 0, 0)
        seconds, nxt = seconds_until_next_run(at_type("06:00,18:00"), now=now)
        self.assertEqual(seconds, 2 * 3600)
        self.assertEqual(nxt, datetime(2026, 1, 1, 6, 0, 0))

    def test_next_run_rolls_to_tomorrow(self):
        from datetime import datetime

        from infomentor.runner import seconds_until_next_run
        from cli import at_type

        now = datetime(2026, 1, 1, 19, 0, 0)
        seconds, nxt = seconds_until_next_run(at_type("06:00,18:00"), now=now)
        self.assertEqual(seconds, 11 * 3600)
        self.assertEqual(nxt, datetime(2026, 1, 2, 6, 0, 0))


if __name__ == "__main__":
    unittest.main()
