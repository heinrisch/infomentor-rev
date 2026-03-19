import json
from pathlib import Path


class StorageManager:

    def __init__(self, output_dir: Path, files_dir: Path):
        self.output_dir = output_dir
        self.files_dir = files_dir
        self.output_dir.mkdir(exist_ok=True)
        self.files_dir.mkdir(exist_ok=True)

    def get_existing_ids(self, pupil_id=None):
        """Get set of existing news item IDs for a specific pupil (or all if None)"""
        existing_ids = set()
        pattern = f"news_{pupil_id}_*.json" if pupil_id else "news_*.json"
        for file in self.output_dir.glob(pattern):
            try:
                # Filename format: news_{pupil_id}_{news_id}.json or news_{news_id}.json
                parts = file.stem.split("_")
                if len(parts) >= 3:
                    news_id = int(parts[2])
                else:
                    news_id = int(parts[1])
                existing_ids.add(news_id)
            except (ValueError, IndexError):
                pass
        return existing_ids

    def get_existing_attachments(self):
        """Get set of existing attachment filenames"""
        return {f.name for f in self.files_dir.iterdir() if f.is_file()}

    def save_news_item(self, item, pupil_id=None):
        """Save a single news item to JSON file"""
        news_id = item.get("id")
        if not news_id:
            print("    ✗ ERROR: News item missing ID, cannot save")
            return None

        if pupil_id:
            filename = self.output_dir / f"news_{pupil_id}_{news_id}.json"
        else:
            filename = self.output_dir / f"news_{news_id}.json"

        try:
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(item, f, ensure_ascii=False, indent=2)
            return filename
        except Exception as e:
            print(f"    ✗ ERROR: Failed to save news item {news_id}: {e}")
            return None

    def save_schedule(self, week_str, schedule_data, pupil_id=None):
        """Save schedule for a specific week and pupil"""
        if pupil_id:
            filename = self.output_dir / f"schedule_{pupil_id}_{week_str}.json"
        else:
            filename = self.output_dir / f"schedule_{week_str}.json"
            
        try:
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(schedule_data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"    ✗ ERROR: Failed to save schedule: {e}")
            return False

    def load_schedule(self, week_str, pupil_id=None):
        """Load schedule for a specific week and pupil"""
        if pupil_id:
            filename = self.output_dir / f"schedule_{pupil_id}_{week_str}.json"
        else:
            filename = self.output_dir / f"schedule_{week_str}.json"
            
        if not filename.exists():
            return None

        try:
            with open(filename, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"    ✗ ERROR: Failed to load schedule: {e}")
            return None

    def get_last_sunday_post(self, pupil_id=None):
        """Get the date of the last Sunday schedule post for a pupil"""
        if pupil_id:
            state_file = self.output_dir / f"schedule_state_{pupil_id}.json"
        else:
            state_file = self.output_dir / "schedule_state.json"
            
        if not state_file.exists():
            return None
        try:
            with open(state_file, "r") as f:
                data = json.load(f)
                return data.get("last_sunday_post")
        except:
            return None

    def set_last_sunday_post(self, date_str, pupil_id=None):
        """Set the date of the last Sunday schedule post for a pupil"""
        if pupil_id:
            state_file = self.output_dir / f"schedule_state_{pupil_id}.json"
        else:
            state_file = self.output_dir / "schedule_state.json"
            
        data = {}
        if state_file.exists():
            try:
                with open(state_file, "r") as f:
                    data = json.load(f)
            except:
                pass

        data["last_sunday_post"] = date_str
        try:
            with open(state_file, "w") as f:
                json.dump(data, f)
        except:
            pass

    def get_existing_notification_ids(self, pupil_id=None):
        """Get set of existing notification IDs for a pupil"""
        existing_ids = set()
        pattern = f"notification_{pupil_id}_*.json" if pupil_id else "notification_*.json"
        for file in self.output_dir.glob(pattern):
            try:
                parts = file.stem.split("_")
                if len(parts) >= 3:
                    notif_id = int(parts[2])
                else:
                    notif_id = int(parts[1])
                existing_ids.add(notif_id)
            except (ValueError, IndexError):
                pass
        return existing_ids

    def save_notification(self, notification, pupil_id=None):
        """Save a single notification to JSON file"""
        notif_id = notification.get("id")
        if not notif_id:
            return None

        if pupil_id:
            filename = self.output_dir / f"notification_{pupil_id}_{notif_id}.json"
        else:
            filename = self.output_dir / f"notification_{notif_id}.json"

        try:
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(notification, f, ensure_ascii=False, indent=2)
            return filename
        except Exception as e:
            print(f"    ✗ ERROR: Failed to save notification {notif_id}: {e}")
            return None

    def save_pupils(self, pupils_data):
        """Save pupils information to JSON file"""
        filename = self.output_dir / "pupils.json"
        try:
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(pupils_data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"    ✗ ERROR: Failed to save pupils: {e}")
            return False
