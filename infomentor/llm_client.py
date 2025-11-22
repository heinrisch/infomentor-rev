import requests
import json
import re


class LLMClient:
    def __init__(self, api_key):
        self.api_key = api_key

    def clean_json_response(self, response_text):
        """Extract JSON from potential markdown code blocks or raw text"""
        if "```json" in response_text:
            match = re.search(r"```json\s*(.*?)\s*```", response_text, re.DOTALL)
            if match:
                return match.group(1)
        elif "```" in response_text:
            match = re.search(r"```\s*(.*?)\s*```", response_text, re.DOTALL)
            if match:
                return match.group(1)

        # Fallback: Find first { and last }
        start = response_text.find("{")
        end = response_text.rfind("}")
        if start != -1 and end != -1:
            return response_text[start : end + 1]

        return response_text

    def summarize_news_entry(self, content, published_date):
        if not self.api_key:
            print("    ⚠ No Perplexity API key found, skipping LLM analysis")
            return None

        url = "https://api.perplexity.ai/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        system_prompt = "You are a strict data extraction AI. You output ONLY JSON."

        user_prompt = f"""
        The current news item was published on: {published_date}.
        
        Analyze the following school news text (which may be HTML) and extract specific information.
        
        1. Create a concise summary highlighting important information for a parent (in Swedish).
        2. Highlight extra important sections of information, like school ends early. 
        3. Extract any specific events that have a date and time.
        
        IMPORTANT: All dates mentioned in the text (like "on Friday" or "tomorrow") must be calculated relative to the publish date: {published_date}.
        If a year is not specified, assume it is the same year as the publish date, unless the date has already passed relative to the publish date, in which case it is the next year.
        
        Return ONLY a valid JSON object with this structure. Do not include any markdown formatting or explanations outside the JSON.
        Do not include any preamble. Start directly with the JSON object.
        {{
            "summary": "The summary text...",
            "highlights": [
                "Ta med gosedjur den 11/12", 
                "Skolan slutar 15.00 den 1/2"
            ],
            "events": [
                {{
                    "title": "Event Title",
                    "start": "YYYY-MM-DDTHH:MM:SS",
                    "end": "YYYY-MM-DDTHH:MM:SS", 
                    "description": "Details about the event"
                }}
            ]
        }}
        Rules for events:
        - If a date is mentioned without a year, assume the next occurrence of that date.
        - If no specific time is mentioned for a date, assume 08:00:00 for start and 09:00:00 for end.
        - Format dates strictly as ISO 8601 (YYYY-MM-DDTHH:MM:SS).
        - If no events are found, "events" should be an empty list.
        - Respond with only the JSON object, wrapped in three backticks (```json ... ```).

        Text to analyze:
        {content}
        """

        payload = {
            "model": "sonar-pro",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }

        try:
            print("    → Calling Perplexity API for analysis...")
            response = requests.post(url, json=payload, headers=headers, timeout=60)

            if response.status_code != 200:
                print(f"    ✗ Perplexity API returned status {response.status_code}")
                print(f"    Response body: {response.text[:500]}")

            response.raise_for_status()
            print("    ✓ Perplexity API response received")

            response_json = response.json()
            content = response_json["choices"][0]["message"]["content"]
            cleaned_content = self.clean_json_response(content)

            try:
                return json.loads(cleaned_content)
            except json.JSONDecodeError as e:
                print(f"    ✗ JSON Decode Error: {e}")
                print(f"    Raw content: {content!r}")
                print(f"    Cleaned content: {cleaned_content!r}")
                return None

        except requests.exceptions.RequestException as e:
            print(f"    ✗ HTTP Error calling Perplexity API: {e}")
            if hasattr(e, "response") and e.response is not None:
                print(f"    Response body: {e.response.text[:500]}")
            return None
        except Exception as e:
            print(f"    ✗ Unexpected error calling Perplexity API: {e}")
            return None
