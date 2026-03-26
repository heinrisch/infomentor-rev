import re

import requests


class TelegramNotifier:
    def __init__(self, bot_token, chat_id):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}"

    def send_message(self, text, parse_mode=None, disable_web_page_preview=False):
        """Send a simple text message"""
        try:
            data = {
                "chat_id": self.chat_id,
                "text": text,
                "disable_web_page_preview": disable_web_page_preview,
            }
            if parse_mode:
                data["parse_mode"] = parse_mode

            response = requests.post(f"{self.api_url}/sendMessage", json=data, timeout=30)
            response.raise_for_status()
            return True
        except Exception as e:
            print(f"    ✗ Error sending Telegram message: {e}")
            if "response" in locals() and hasattr(response, "text"):
                print(f"    Response: {response.text[:200]}")
            return False

    def send_document(self, file_path, caption=None):
        """Send a document/file"""
        try:
            with open(file_path, "rb") as f:
                files = {"document": f}
                data = {"chat_id": self.chat_id}
                if caption:
                    data["caption"] = caption

                response = requests.post(
                    f"{self.api_url}/sendDocument", data=data, files=files, timeout=60
                )
                response.raise_for_status()
            return True
        except Exception as e:
            print(f"    ✗ Error sending Telegram document {file_path}: {e}")
            return False

    def escape_markdown(self, text):
        """Escape MarkdownV2 special characters"""
        if text is None:
            return ""
        text = str(text)
        # https://core.telegram.org/bots/api#markdownv2-style
        special_chars = r"_*[]()~`>#+-=|{}.!"
        return "".join(f"\\{c}" if c in special_chars else c for c in text)

    # --- Interface Methods (matching DiscordNotifier) ---

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
        display_title = news_title
        if pupil_name:
            display_title = f"[{pupil_name}] {news_title}"

        # 1. Prepare Summary Part
        summary_part = f"*{self.escape_markdown(display_title)}*\n\n"
        if summary:
            summary_part += f"{self.escape_markdown(summary)}\n"
        
        if highlights:
            summary_part += "\n*Highlights:*\n"
            for highlight in highlights:
                summary_part += f"• {self.escape_markdown(highlight)}\n"

        if events:
            summary_part += "\n*Events:*\n"
            for event in events:
                title = self.escape_markdown(event.get("title", "Event"))
                start = self.escape_markdown(event.get("start", ""))
                end = self.escape_markdown(event.get("end", ""))
                summary_part += f"• {title} \\({start} \\- {end}\\)\n"

        # 2. Prepare Full Content Part
        content_part = ""
        if full_item:
            title = full_item.get("title", "No Title")
            date = full_item.get("publishedDateString", "Unknown Date")
            author = full_item.get("publishedBy", "Unknown Author")
            raw_content = full_item.get("content", "")

            # Basic HTML to text conversion
            markdown_content = raw_content
            markdown_content = (
                markdown_content.replace("<br>", "\n")
                .replace("<br/>", "\n")
                .replace("</p>", "\n\n")
            )
            
            # Strip tags for now to avoid escaping nightmares with mixed markdown
            markdown_content = re.sub(r"<[^>]+>", "", markdown_content)
            
            # Unescape entities
            replacements = {"&nbsp;": " ", "&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": '"', "&#39;": "'", "&ndash;": "-", "&mdash;": "--"}
            for k, v in replacements.items():
                markdown_content = markdown_content.replace(k, v)
            
            markdown_content = re.sub(r"\n\s+\n", "\n\n", markdown_content).strip()
            
            content_part = f"\n*Full Content:*\n"
            content_part += f"{self.escape_markdown(title)}\n"
            # Note: | must be escaped in MarkdownV2
            content_part += f"_{self.escape_markdown(date)} \| {self.escape_markdown(author)}_\n\n"
            content_part += self.escape_markdown(markdown_content)

        # 3. Combine and Split (No Truncation)
        full_message = summary_part + content_part
        if not full_message.strip():
            full_message = f"New news item: {self.escape_markdown(display_title)}"

        # Telegram limit is 4096. We'll aim for 4000 to be safe.
        limit = 4000
        if len(full_message) <= limit:
            print("    → Sending Telegram notification...")
            self.send_message(full_message, parse_mode="MarkdownV2")
        else:
            print(f"    → Sending Telegram notification in multiple parts ({len(full_message)} chars)...")
            remaining = full_message
            part_num = 1
            while remaining:
                if len(remaining) <= limit:
                    chunk = remaining
                    remaining = ""
                else:
                    # Find a good split point
                    split_at = remaining.rfind("\n", 0, limit)
                    if split_at == -1:
                        split_at = remaining.rfind(" ", 0, limit)
                    if split_at == -1:
                        split_at = limit
                    
                    # Ensure we don't split in the middle of an escape sequence (\.)
                    temp_split = split_at
                    backslashes = 0
                    while temp_split > 0 and remaining[temp_split-1] == "\\":
                        backslashes += 1
                        temp_split -= 1
                    
                    if backslashes % 2 != 0:
                        split_at -= 1

                    chunk = remaining[:split_at]
                    remaining = remaining[split_at:]
                    # If we split at a newline or space, skip it for the next part
                    if remaining and remaining[0] in ("\n", " "):
                        remaining = remaining[1:]
                
                header = f"*Part {part_num}*\n" if part_num > 1 else ""
                self.send_message(header + chunk, parse_mode="MarkdownV2")
                part_num += 1

        # 4. Send Attachments
        if attachment_paths:
            print(f"    → Sending {len(attachment_paths)} attachments to Telegram...")
            for path in attachment_paths:
                if path.exists():
                    self.send_document(path)

    def send_schedule_update(
        self, schedule, week_str, is_new_week=False, changes=None, pupil_name=None
    ):
        title = f"📅 Schedule for week of {week_str}"
        if not is_new_week:
            title = f"⚠️ Schedule Update: Week of {week_str}"

        if pupil_name:
            title = f"[{pupil_name}] {title}"

        text = f"*{self.escape_markdown(title)}*\n\n"

        if changes:
            text += "*Changes:*\n"
            for change in changes:
                entry = change["entry"]
                ctype = change["type"]
                entry_str = f"{entry['formattedStartDate']} {entry['startTime'] or ''} - {entry['title']}"
                if ctype == "added":
                    text += f"➕ {self.escape_markdown(entry_str)}\n"
                elif ctype == "removed":
                    text += f"➖ {self.escape_markdown(entry_str)}\n"
                elif ctype == "modified":
                    text += f"✏️ {self.escape_markdown(entry_str)}\n"

            text += "\n"

        # Construct schedule text (simplified for Telegram)
        days = {}
        sorted_schedule = sorted(schedule, key=lambda x: x.get("startDateFull", ""))
        for entry in sorted_schedule:
            day = entry.get("formattedStartDate", "Unknown")
            if day not in days:
                days[day] = []
            days[day].append(entry)

        for day, entries in days.items():
            text += f"*{self.escape_markdown(day)}*\n"
            for entry in entries:
                time_str = (
                    f"{entry['startTime']}-{entry['endTime']}"
                    if entry["startTime"]
                    else "All Day"
                )
                text += f"• {self.escape_markdown(time_str)}: {self.escape_markdown(entry['title'])}\n"
            text += "\n"

        if len(text) > 4000:
            text = text[:3997] + r"\.\.\."

        print("    → Sending Telegram schedule notification...")
        self.send_message(text, parse_mode="MarkdownV2")

    def send_notification(self, notification, pupil_name=None):
        title = notification.get("title", "New Notification")
        subtitle = notification.get("subTitle", "")
        url = notification.get("url", "")

        display_title = f"🔔 {title}"
        if pupil_name:
            display_title = f"[{pupil_name}] {display_title}"

        text = f"*{self.escape_markdown(display_title)}*\n"
        if subtitle:
            text += f"{self.escape_markdown(subtitle)}\n\n"

        if url:
             full_url = f"https://hub.infomentor.se{url}"
             # In MarkdownV2, only ) and \ need to be escaped in the URL part
             safe_url = full_url.replace("\\", "\\\\").replace(")", "\\)")
             text += f"[Open in InfoMentor]({safe_url})"

        print("    → Sending Telegram app notification...")
        self.send_message(text, parse_mode="MarkdownV2")

    def send_attendance_update(self, new_records, pupil_name=None):
        if not new_records:
            return

        title = "📝 Attendance Update"
        if pupil_name:
            title = f"[{pupil_name}] {title}"

        text = f"*{self.escape_markdown(title)}*\n"
        text += f"Found {len(new_records)} new attendance records\\.\n\n"

        for record in new_records:
            date = self.escape_markdown(record.get("dateString", "Unknown Date"))
            lesson = self.escape_markdown(record.get("lessonName", "Unknown Lesson"))
            status = self.escape_markdown(record.get("registrationTypeName", "Unknown Status"))
            comment = self.escape_markdown(record.get("comment", ""))
            
            text += f"📅 *{date}*\n"
            text += f"• *Status:* {status}\n"
            text += f"• *Lesson:* {lesson}\n"
            if comment:
                text += f"• *Comment:* {comment}\n"
            text += "\n"

        if len(text) > 4000:
            text = text[:3997] + r"\.\.\."

        print("    → Sending Telegram attendance notification...")
        self.send_message(text, parse_mode="MarkdownV2")

    def send_error(self, context, error_message):
        text = f"🚨 *Error: {self.escape_markdown(context)}*\n\n"
        text += f"```{self.escape_markdown(str(error_message))}```"

        self.send_message(text, parse_mode="MarkdownV2")
