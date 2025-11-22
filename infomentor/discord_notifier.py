import json
import re
from datetime import datetime
from urllib.parse import quote

import requests


class DiscordNotifier:
    def __init__(self, webhook_url):
        self.webhook_url = webhook_url

    def generate_google_calendar_url(self, event):
        """Generate a Google Calendar add event URL"""
        try:
            title = quote(event.get("title", "Event"))
            details = quote(event.get("description", ""))

            # Parse dates
            dt_start = datetime.fromisoformat(event["start"])
            dt_end = datetime.fromisoformat(event["end"])

            # Format for Google Calendar: YYYYMMDDTHHMMSS
            start_str = dt_start.strftime("%Y%m%dT%H%M%S")
            end_str = dt_end.strftime("%Y%m%dT%H%M%S")

            url = f"https://www.google.com/calendar/render?action=TEMPLATE&text={title}&dates={start_str}/{end_str}&details={details}"
            return url
        except Exception as e:
            print(f"    ⚠ Error generating Google Calendar URL: {e}")
            return None

    def send_summary_message(self, summary, events, news_title, attachment_paths=None):
        if not self.webhook_url:
            print("    ⚠ No Discord webhook URL found, skipping notification")
            return

        # --- Message 1: Summary & Events ---
        summary_message = summary + "\n\n"

        if events:
            summary_message += "Events:\n"
            for event in events:
                gcal_url = self.generate_google_calendar_url(event)
                summary_message += f"- [{event['title']} ({event['start']} - {event['end']})]({gcal_url})\n"

        embed1 = {
            "title": f"News: {news_title}",
            "description": summary_message,
            "color": 3447003,
        }

        data1 = {
            "embeds": [embed1],
            "username": "InfoMentor News",
            "avatar_url": "https://www.infomentor.se/wp-content/uploads/2024/03/im-logo-full.png",
        }

        files = {}
        opened_files = []

        # Add physical attachments to Message 1
        if attachment_paths:
            for i, path in enumerate(attachment_paths):
                try:
                    if path.exists():
                        f = open(path, "rb")
                        opened_files.append(f)
                        files[f"attachment_{i}"] = (
                            path.name,
                            f,
                            "application/octet-stream",
                        )
                except Exception as e:
                    print(f"    ⚠ Could not attach file {path}: {e}")

        try:
            print("    → Sending Discord notification (Summary)...")
            if files:
                response = requests.post(
                    self.webhook_url,
                    data={"payload_json": json.dumps(data1)},
                    files=files,
                    timeout=60,
                )
            else:
                response = requests.post(self.webhook_url, json=data1, timeout=30)
            response.raise_for_status()
            print("    ✓ Summary sent to Discord")
        except Exception as e:
            print(f"    ✗ Error sending summary to Discord: {e}")
            if "response" in locals() and hasattr(response, "text"):
                print(f"    Response: {response.text[:200]}")
        finally:
            for f in opened_files:
                f.close()

    def send_full_content_message(self, full_item):
        if not self.webhook_url or not full_item:
            return

        # --- Message 2: Full Content ---
        title = full_item.get("title", "No Title")
        date = full_item.get("publishedDateString", "Unknown Date")
        author = full_item.get("publishedBy", "Unknown Author")
        raw_content = full_item.get("content", "")

        # Convert HTML to Markdown for Discord
        markdown_content = raw_content

        # Basic replacements
        markdown_content = (
            markdown_content.replace("<br>", "\n")
            .replace("<br/>", "\n")
            .replace("</p>", "\n\n")
        )
        markdown_content = markdown_content.replace("<strong>", "**").replace(
            "</strong>", "**"
        )
        markdown_content = markdown_content.replace("<b>", "**").replace("</b>", "**")
        markdown_content = markdown_content.replace("<em>", "*").replace("</em>", "*")
        markdown_content = markdown_content.replace("<i>", "*").replace("</i>", "*")

        # Lists
        markdown_content = markdown_content.replace("<ul>", "\n").replace("</ul>", "\n")
        markdown_content = markdown_content.replace("<ol>", "\n").replace("</ol>", "\n")
        markdown_content = markdown_content.replace("<li>", "- ").replace("</li>", "\n")

        # Links
        markdown_content = re.sub(
            r'<a\s+(?:[^>]*?\s+)?href="([^"]*)"[^>]*>(.*?)</a>',
            r"[\2](\1)",
            markdown_content,
        )

        # Strip remaining tags
        markdown_content = re.sub(r"<[^>]+>", "", markdown_content)

        # Unescape entities
        replacements = {
            "&nbsp;": " ",
            "&amp;": "&",
            "&lt;": "<",
            "&gt;": ">",
            "&quot;": '"',
            "&#39;": "'",
            "&ndash;": "-",
            "&mdash;": "--",
        }
        for k, v in replacements.items():
            markdown_content = markdown_content.replace(k, v)

        # Cleanup whitespace
        markdown_content = re.sub(r"\n\s+\n", "\n\n", markdown_content)
        markdown_content = markdown_content.strip()

        # Construct message
        full_content_message = f"**{title}**\n"
        full_content_message += f"*{date} | {author}*\n\n"
        full_content_message += markdown_content

        # Truncate if too long (Discord embed limit is 4096)
        if len(full_content_message) > 4000:
            full_content_message = full_content_message[:3997] + "..."

        embed2 = {
            "title": "Full Content",
            "description": full_content_message,
            "color": 3447003,
        }

        data2 = {
            "embeds": [embed2],
            "username": "InfoMentor News",
            "avatar_url": "https://www.infomentor.se/wp-content/uploads/2024/03/im-logo-full.png",
        }

        try:
            print("    → Sending Discord notification (Full Content)...")
            response = requests.post(self.webhook_url, json=data2, timeout=30)
            response.raise_for_status()
            print("    ✓ Full content sent to Discord")
        except Exception as e:
            print(f"    ✗ Error sending full content to Discord: {e}")

    def send_highlights_message(self, highlights):
        if not self.webhook_url or not highlights:
            return

        # --- Message 3: Highlights ---
        highlights_text = "**Viktigt:**\n"
        for highlight in highlights:
            highlights_text += f"• {highlight}\n"

        embed3 = {
            "title": "Highlights",
            "description": highlights_text,
            "color": 15158332,  # Red/Orange
        }

        data3 = {
            "embeds": [embed3],
            "username": "InfoMentor News",
            "avatar_url": "https://www.infomentor.se/wp-content/uploads/2024/03/im-logo-full.png",
        }

        try:
            print("    → Sending Discord notification (Highlights)...")
            response = requests.post(self.webhook_url, json=data3, timeout=30)
            response.raise_for_status()
            print("    ✓ Highlights sent to Discord")
        except Exception as e:
            print(f"    ✗ Error sending highlights to Discord: {e}")

    def send_webhook(
        self,
        summary,
        events,
        highlights,
        news_title,
        attachment_paths=None,
        full_item=None,
    ):
        self.send_summary_message(summary, events, news_title, attachment_paths)
        if full_item:
            self.send_full_content_message(full_item)
        if highlights:
            self.send_highlights_message(highlights)

    def send_schedule_update(self, schedule, week_str, is_new_week=False, changes=None):
        if not self.webhook_url:
            return

        title = f"📅 Schedule for week of {week_str}"
        if is_new_week:
            description = "Here is the schedule for the upcoming week."
            color = 3447003  # Blue
        else:
            title = f"⚠️ Schedule Update: Week of {week_str}"
            description = "The schedule has been updated!"
            color = 15158332  # Red/Orange

        fields = []

        if changes:
            change_text = ""
            for change in changes:
                entry = change["entry"]
                ctype = change["type"]

                if ctype == "added":
                    change_text += f"➕ **Added**: {entry['formattedStartDate']} {entry['startTime'] or ''} - {entry['title']}\n"
                elif ctype == "removed":
                    change_text += f"➖ **Removed**: {entry['formattedStartDate']} {entry['startTime'] or ''} - {entry['title']}\n"
                elif ctype == "modified":
                    change_text += f"✏️ **Modified**: {entry['formattedStartDate']} {entry['startTime'] or ''} - {entry['title']}\n"
                    for diff in change.get("diffs", []):
                        change_text += f"  - {diff}\n"

            if change_text:
                fields.append({"name": "Changes", "value": change_text[:1024]})

        # Group by day
        days = {}
        # Sort by startDateFull to ensure correct order
        sorted_schedule = sorted(schedule, key=lambda x: x.get("startDateFull", ""))

        for entry in sorted_schedule:
            day = entry.get("formattedStartDate", "Unknown")
            if day not in days:
                days[day] = []
            days[day].append(entry)

        schedule_text = ""
        for day, entries in days.items():
            schedule_text += f"**{day}**\n"
            for entry in entries:
                time_str = (
                    f"{entry['startTime']}-{entry['endTime']}"
                    if entry["startTime"]
                    else "All Day"
                )
                schedule_text += f"• {time_str}: {entry['title']}\n"
                if entry.get("description"):
                    # Strip HTML tags for description
                    desc = re.sub(r"<[^>]+>", "", entry["description"]).strip()
                    if desc:
                        # Truncate description if too long
                        if len(desc) > 100:
                            desc = desc[:97] + "..."
                        schedule_text += f"  _{desc}_\n"
            schedule_text += "\n"

        if len(schedule_text) > 2000:
            # Split if too long, or just truncate for now
            schedule_text = schedule_text[:1997] + "..."

        embed = {
            "title": title,
            "description": description + "\n\n" + schedule_text,
            "color": color,
            "fields": fields,
        }

        data = {
            "embeds": [embed],
            "username": "InfoMentor Schedule",
            "avatar_url": "https://www.infomentor.se/wp-content/uploads/2024/03/im-logo-full.png",
        }

        try:
            print("    → Sending Discord schedule notification...")
            requests.post(self.webhook_url, json=data, timeout=30)
            print("    ✓ Schedule sent to Discord")
        except Exception as e:
            print(f"    ✗ Error sending schedule to Discord: {e}")

    def send_notification(self, notification):
        if not self.webhook_url:
            return

        title = notification.get("title", "New Notification")
        subtitle = notification.get("subTitle", "")
        date_sent = notification.get("dateSent", "")
        url = notification.get("url", "")

        description = f"{subtitle}\n\n" if subtitle else ""

        if url:
            full_url = f"https://hub.infomentor.se{url}"
            description += f"[Open in InfoMentor]({full_url})"

        embed = {
            "title": f"🔔 {title}",
            "description": description,
            "color": 10181046,  # Purple
            "footer": {"text": f"Sent: {date_sent}"},
        }

        data = {
            "embeds": [embed],
            "username": "InfoMentor Notifications",
            "avatar_url": "https://www.infomentor.se/wp-content/uploads/2024/03/im-logo-full.png",
        }

        try:
            print("    → Sending Discord app notification...")
            requests.post(self.webhook_url, json=data, timeout=30)
            print("    ✓ Notification sent to Discord")
        except Exception as e:
            print(f"    ✗ Error sending notification to Discord: {e}")

    def send_error(self, context, error_message):
        if not self.webhook_url:
            return

        embed = {
            "title": f"🚨 Error: {context}",
            "description": f"An error occurred while running the InfoMentor fetcher.\n\n**Error:**\n```{str(error_message)}```",
            "color": 15158332,  # Red
            "footer": {"text": f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"},
        }

        data = {
            "embeds": [embed],
            "username": "InfoMentor Bot",
            "avatar_url": "https://www.infomentor.se/wp-content/uploads/2024/03/im-logo-full.png",
        }

        requests.post(self.webhook_url, json=data, timeout=30)

