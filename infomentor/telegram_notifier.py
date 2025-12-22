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
    ):
        # 1. Send Summary with Events
        text = f"*{self.escape_markdown(news_title)}*\n\n"
        text += f"{self.escape_markdown(summary)}\n"

        if events:
            text += "\n*Events:*\n"
            for event in events:
                title = self.escape_markdown(event.get("title", "Event"))
                start = self.escape_markdown(event.get("start", ""))
                end = self.escape_markdown(event.get("end", ""))
                text += f"• {title} \\({start} \\- {end}\\)\n"

        if highlights:
            text += "\n*Highlights:*\n"
            for highlight in highlights:
                text += f"• {self.escape_markdown(highlight)}\n"

        print("    → Sending Telegram notification (Summary)...")
        self.send_message(text, parse_mode="MarkdownV2")

        # 2. Send Attachments
        if attachment_paths:
            print(f"    → Sending {len(attachment_paths)} attachments to Telegram...")
            for path in attachment_paths:
                if path.exists():
                    self.send_document(path)

        # 3. Send Full Content
        if full_item:
            self.send_full_content_message(full_item)

    def send_full_content_message(self, full_item):
        title = full_item.get("title", "No Title")
        date = full_item.get("publishedDateString", "Unknown Date")
        author = full_item.get("publishedBy", "Unknown Author")
        raw_content = full_item.get("content", "")

        # Use regex to clean up HTML - reusing logic similar to Discord Notifier
        markdown_content = raw_content

        # Basic replacements
        markdown_content = (
            markdown_content.replace("<br>", "\n")
            .replace("<br/>", "\n")
            .replace("</p>", "\n\n")
        )
        
        # Simple bold/italic replacements
        markdown_content = re.sub(r"<(strong|b)>", "*", markdown_content)
        markdown_content = re.sub(r"</(strong|b)>", "*", markdown_content)
        markdown_content = re.sub(r"<(em|i)>", "_", markdown_content)
        markdown_content = re.sub(r"</(em|i)>", "_", markdown_content)

        # Lists
        markdown_content = markdown_content.replace("<ul>", "\n").replace("</ul>", "\n")
        markdown_content = markdown_content.replace("<ol>", "\n").replace("</ol>", "\n")
        markdown_content = markdown_content.replace("<li>", "• ").replace("</li>", "\n")

        # Links - Telegram MarkdownV2 requires careful escaping, so we might just strip them or use a simpler approach
        # For now, let's keep them simple: [text](url)
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

        # Construct message (Plain Text)
        full_content_message = f"{title}\n"
        full_content_message += f"{date} | {author}\n\n"
        
        # We need to escape the content for MarkdownV2, but we already have some markdown characters in there
        # from our manual conversion (like * and _). 
        # Ideally, we should have escaped the *raw text* parts before adding the markdown syntax.
        # However, doing that correctly with mixed HTML input is hard without a proper parser.
        # Alternatively, we can just NOT use MarkdownV2 for the body and use just text, but that loses formatting.
        # Or we can use the 'HTML' parse mode supported by Telegram! That's much easier for converting from HTML.
        
        # Let's try HTML parse mode for the content to preserve basic formatting easily.
        # Telegram supports: <b>, <i>, <u>, <s>, <a>, <code>, <pre>
        
        # We need to restrict the tags to the supported ones.
        
        # Actually, let's stick to the previous plan but be careful.
        # Since 'escape_markdown' escapes EVERYTHING, it will break our manually added * and _.
        # We should probably just send the body as plain text if we can't reliably convert.
        
        # But wait, looking at DiscordNotifier, it uses fairly standard Markdown.
        # Telegram's Markdown (V1) is forgiving. MarkdownV2 is strict.
        # Let's try standard 'Markdown' (V1) or just do `escape_markdown` and loose internal formatting 
        # but keep the structure.
        
        # Actually, best approach is probably to just send it as text if we are lazy,
        # but let's try to match Discord's "Full Content" block title.
        
        # Let's use simple textual representation to allow for easy reading without markup errors.
        full_content_message = f"{title}\n"
        full_content_message += f"{date} | {author}\n\n"
        full_content_message += markdown_content # This still has some markdown-like chars we added (*, _)
        
        # Clean up our manual markdown additions if we are going plain text?
        # No, let's try to pass it as MarkdownV2 but we MUST escape everything correctly.
        # That's hard.
        
        # Let's use NO parse_mode for the body content to be safe and avoid "bad request" errors due to unescaped chars.
        # But we want the title bold. We can send the title as one message and content as another? No, too spammy.
        
        # Compromise: Send as plain text, but with clear separation.
        
        if len(full_content_message) > 4000:
            full_content_message = full_content_message[:3997] + "..."

        print("    → Sending Telegram notification (Full Content)...")
        # Sending without parse_mode to ensure delivery even if chars are special
        self.send_message(full_content_message)

    def send_schedule_update(self, schedule, week_str, is_new_week=False, changes=None):
        title = f"📅 Schedule for week of {week_str}"
        if not is_new_week:
            title = f"⚠️ Schedule Update: Week of {week_str}"

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
            text = text[:3997] + "..."

        print("    → Sending Telegram schedule notification...")
        self.send_message(text, parse_mode="MarkdownV2")

    def send_notification(self, notification):
        title = notification.get("title", "New Notification")
        subtitle = notification.get("subTitle", "")
        url = notification.get("url", "")

        text = f"🔔 *{self.escape_markdown(title)}*\n"
        if subtitle:
            text += f"{self.escape_markdown(subtitle)}\n\n"

        if url:
             full_url = f"https://hub.infomentor.se{url}"
             # In MarkdownV2, only ) and \ need to be escaped in the URL part
             safe_url = full_url.replace("\\", "\\\\").replace(")", "\\)")
             text += f"[Open in InfoMentor]({safe_url})"

        print("    → Sending Telegram app notification...")
        self.send_message(text, parse_mode="MarkdownV2")

    def send_error(self, context, error_message):
        text = f"🚨 *Error: {self.escape_markdown(context)}*\n\n"
        text += f"```{self.escape_markdown(str(error_message))}```"

        self.send_message(text, parse_mode="MarkdownV2")
