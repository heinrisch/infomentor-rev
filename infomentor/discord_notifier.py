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

    def send_webhook(
        self,
        summary,
        events,
        highlights,
        news_title,
        attachment_paths=None,
        full_item=None,
        pupil_name=None,
    ):
        if not self.webhook_url:
            print("    ⚠ No Discord webhook URL found, skipping notification")
            return

        def split_text(text, limit=4000):
            """Split text into chunks that fit within Discord limits"""
            chunks = []
            while len(text) > limit:
                # Find a good place to split (newline)
                split_at = text.rfind("\n", 0, limit)
                if split_at == -1:
                    split_at = limit
                chunks.append(text[:split_at])
                text = text[split_at:].lstrip()
            chunks.append(text)
            return chunks

        def send_discord_payload(embeds, files=None):
            data = {
                "embeds": embeds,
                "username": "InfoMentor News",
                "avatar_url": "https://www.infomentor.se/wp-content/uploads/2024/03/im-logo-full.png",
            }
            opened_files = []
            try:
                print(f"    → Sending Discord notification ({len(embeds)} embeds)...")
                if files:
                    payload_files = {}
                    for i, path in enumerate(files):
                        if path.exists():
                            f = open(path, "rb")
                            opened_files.append(f)
                            payload_files[f"attachment_{i}"] = (path.name, f, "application/octet-stream")
                    
                    response = requests.post(
                        self.webhook_url,
                        data={"payload_json": json.dumps(data)},
                        files=payload_files,
                        timeout=60,
                    )
                else:
                    response = requests.post(self.webhook_url, json=data, timeout=30)
                response.raise_for_status()
                return True
            except Exception as e:
                print(f"    ✗ Error sending to Discord: {e}")
                return False
            finally:
                for f in opened_files:
                    f.close()

        all_embeds = []
        
        # --- Embed 1: Summary, Events & Highlights ---
        summary_text = ""
        if summary:
            summary_text = summary + "\n\n"

        if highlights:
            summary_text += "**Highlights:**\n"
            for highlight in highlights:
                summary_text += f"• {highlight}\n"
            summary_text += "\n"

        if events:
            summary_text += "**Events:**\n"
            for event in events:
                gcal_url = self.generate_google_calendar_url(event)
                summary_text += f"- [{event['title']} ({event['start']} - {event['end']})]({gcal_url})\n"

        if not summary_text and not full_item:
            summary_text = "New news item published."

        title = f"News: {news_title}"
        if pupil_name:
            title = f"[{pupil_name}] {title}"

        if summary_text:
            chunks = split_text(summary_text)
            for i, chunk in enumerate(chunks):
                all_embeds.append({
                    "title": title if i == 0 else f"{title} (cont.)",
                    "description": chunk,
                    "color": 3447003,
                })

        # --- Embed 2+: Full Content ---
        if full_item:
            f_title = full_item.get("title", "No Title")
            date = full_item.get("publishedDateString", "Unknown Date")
            author = full_item.get("publishedBy", "Unknown Author")
            raw_content = full_item.get("content", "")

            # Convert HTML to Markdown
            markdown_content = raw_content
            markdown_content = markdown_content.replace("<br>", "\n").replace("<br/>", "\n").replace("</p>", "\n\n")
            markdown_content = markdown_content.replace("<strong>", "**").replace("</strong>", "**")
            markdown_content = markdown_content.replace("<b>", "**").replace("</b>", "**")
            markdown_content = markdown_content.replace("<em>", "*").replace("</em>", "*")
            markdown_content = markdown_content.replace("<i>", "*").replace("</i>", "*")
            markdown_content = markdown_content.replace("<ul>", "\n").replace("</ul>", "\n")
            markdown_content = markdown_content.replace("<ol>", "\n").replace("</ol>", "\n")
            markdown_content = markdown_content.replace("<li>", "- ").replace("</li>", "\n")
            markdown_content = re.sub(r'<a\s+(?:[^>]*?\s+)?href="([^"]*)"[^>]*>(.*?)</a>', r"[\2](\1)", markdown_content)
            markdown_content = re.sub(r"<[^>]+>", "", markdown_content)
            replacements = {"&nbsp;": " ", "&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": '"', "&#39;": "'", "&ndash;": "-", "&mdash;": "--"}
            for k, v in replacements.items():
                markdown_content = markdown_content.replace(k, v)
            markdown_content = re.sub(r"\n\s+\n", "\n\n", markdown_content).strip()

            full_desc_start = f"**{f_title}**\n*{date} | {author}*\n\n"
            full_text = full_desc_start + markdown_content
            
            chunks = split_text(full_text)
            for i, chunk in enumerate(chunks):
                all_embeds.append({
                    "title": "Full Content" if i == 0 and summary_text else (f"Full Content (cont. {i})" if summary_text else (f_title if i == 0 else f"{f_title} (cont. {i})")),
                    "description": chunk,
                    "color": 3447003,
                })

        # Send in batches of 10 embeds (Discord limit) and stay under 6000 total chars
        current_batch = []
        current_char_count = 0
        
        for i, embed in enumerate(all_embeds):
            embed_len = len(embed["description"]) + len(embed["title"])
            if len(current_batch) >= 10 or (current_char_count + embed_len > 5500):
                # Send current batch
                send_discord_payload(current_batch, attachment_paths if i == len(current_batch) else None)
                current_batch = []
                current_char_count = 0
                # Attachments only on the first message
                attachment_paths = None
            
            current_batch.append(embed)
            current_char_count += embed_len

        if current_batch:
            send_discord_payload(current_batch, attachment_paths)

    def send_schedule_update(
        self, schedule, week_str, is_new_week=False, changes=None, pupil_name=None
    ):
        if not self.webhook_url:
            return

        title_text = f"Schedule for week of {week_str}"
        if is_new_week:
            title = f"📅 {title_text}"
            description = "Here is the schedule for the upcoming week."
            color = 3447003  # Blue
        else:
            title = f"⚠️ Schedule Update: Week of {week_str}"
            description = "The schedule has been updated!"
            color = 15158332  # Red/Orange

        if pupil_name:
            title = f"[{pupil_name}] {title}"

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

    def send_notification(self, notification, pupil_name=None):
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

        embed_title = f"🔔 {title}"
        if pupil_name:
            embed_title = f"[{pupil_name}] {embed_title}"

        embed = {
            "title": embed_title,
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

    def send_attendance_update(self, new_records, pupil_name=None):
        if not self.webhook_url or not new_records:
            return

        title = "Attendance Update"
        if pupil_name:
            title = f"[{pupil_name}] {title}"

        description = f"Found {len(new_records)} new attendance records."
        
        fields = []
        for record in new_records:
            date = record.get("dateString", "Unknown Date")
            lesson = record.get("lessonName", "Unknown Lesson")
            status = record.get("registrationTypeName", "Unknown Status")
            comment = record.get("comment", "")
            
            value = f"**Status:** {status}\n**Lesson:** {lesson}"
            if comment:
                value += f"\n**Comment:** {comment}"
                
            fields.append({
                "name": date,
                "value": value,
                "inline": False
            })

        embed = {
            "title": f"📝 {title}",
            "description": description,
            "color": 15105570,  # Orange/Yellow
            "fields": fields[:25] # Discord limit is 25 fields
        }

        data = {
            "embeds": [embed],
            "username": "InfoMentor Attendance",
            "avatar_url": "https://www.infomentor.se/wp-content/uploads/2024/03/im-logo-full.png",
        }

        try:
            print("    → Sending Discord attendance notification...")
            requests.post(self.webhook_url, json=data, timeout=30)
            print("    ✓ Attendance update sent to Discord")
        except Exception as e:
            print(f"    ✗ Error sending attendance update to Discord: {e}")

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

