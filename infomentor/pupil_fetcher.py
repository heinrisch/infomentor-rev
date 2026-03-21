import json
import re
import requests


class PupilFetcher:
    def __init__(self, session: requests.Session, storage_manager):
        self.session = session
        self.storage_manager = storage_manager
        self.web_base_url = None

    def fetch_pupils(self):
        """Fetch pupils from the root page (hub.infomentor.se)"""
        print("\n[Pupils] Fetching pupil information...")

        if not self.web_base_url:
            print("  ✗ ERROR: No web session established")
            return None

        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "en-US,en;q=0.9",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Pragma": "no-cache",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }

        url = f"{self.web_base_url}/"

        try:
            response = self.session.get(
                url, headers=headers, timeout=30, allow_redirects=True
            )

            if response.status_code == 200:
                html_content = response.text
                return self.parse_pupils_from_html(html_content)
            else:
                print(
                    f"  ✗ ERROR: Root page returned status {response.status_code}"
                )
                return None
        except Exception as e:
            print(f"  ✗ ERROR: Error fetching root page: {e}")
            return None

    def parse_pupils_from_html(self, html_content):
        """Parse pupils and switch URLs from HTML source"""
        # Search for pupil data in script tags. 
        # Typically InfoMentor hub stores this in a JSON-like structure in the HTML.
        
        pupils = []
        
        # Look for patterns like: "pupils": [ ... ]
        # This is often found in a script tag as part of a larger object.
        pupil_list_match = re.search(r'["\']pupils["\']\s*:\s*(\[.*?\])\s*[,}]', html_content, re.DOTALL)
        
        if pupil_list_match:
            try:
                pupils_json = pupil_list_match.group(1)
                # Some basic cleanup in case of non-strict JSON (like trailing commas)
                # but usually it's injected from a server-side object and valid.
                pupils = json.loads(pupils_json)
                print(f"  ✓ Found {len(pupils)} pupils in JSON block")
            except json.JSONDecodeError:
                # If direct JSON load fails, try a more manual approach
                print("  ⚠ Failed to parse pupils JSON block directly, attempting regex extraction...")
        
        if not pupils:
            # Fallback: regex search for individual pupil objects containing switchPupilUrl
            # This looks for objects with name and switchPupilUrl fields.
            pattern = r'\{[^{}]*?["\']name["\']\s*:\s*["\']([^"\']+)["\'][^{}]*?["\']switchPupilUrl["\']\s*:\s*["\']([^"\']+)["\'][^{}]*?\}'
            matches = re.finditer(pattern, html_content)
            for match in matches:
                name = match.group(1)
                switch_url = match.group(2)
                
                # Try to extract ID from switch URL (e.g. ...?pupilId=123 or .../123)
                pupil_id = None
                id_match = re.search(r'pupilId=([^&"\']+)', switch_url)
                if id_match:
                    pupil_id = id_match.group(1)
                
                pupils.append({
                    "name": name,
                    "id": pupil_id,
                    "switchPupilUrl": switch_url
                })
            
            if pupils:
                print(f"  ✓ Found {len(pupils)} pupils via regex pattern matching")

        if not pupils:
            print("  ✗ ERROR: Could not find pupil information in HTML")
            return None

        # Ensure every pupil has an ID
        for i, pupil in enumerate(pupils):
            if not pupil.get("id"):
                # Try to extract from switchPupilUrl if it wasn't done above (for JSON branch)
                switch_url = pupil.get("switchPupilUrl", "")
                id_match = re.search(r'pupilId=([^&"\']+)', switch_url)
                if id_match:
                    pupil["id"] = id_match.group(1)
                else:
                    # Last resort: use a hash or index-based ID
                    import hashlib
                    pupil["id"] = hashlib.md5(pupil.get("name", f"pupil_{i}").encode()).hexdigest()[:8]


        # Save to storage
        self.storage_manager.save_pupils(pupils)
        return pupils

    def process_pupils(self):
        """Fetch and save pupil information"""
        return self.fetch_pupils()
