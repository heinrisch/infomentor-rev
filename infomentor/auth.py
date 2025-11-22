import json
import os
import re
import time
import urllib.parse
from urllib.parse import urlparse

import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions

# Constants
CLIENT_ID = "notificationapp"
CLIENT_SECRET = "NONE"
REDIRECT_URI = "InfomentorNotification://oauth2Callback"
SCOPE = "IM2-API-NOTIFICATION"
DEVICE_PLATFORM = "Android"
DEFAULT_AUTH_BASE_URL = "https://api.infomentor.se"
DEFAULT_API_BASE_URL = "https://api.infomentor.se"


class TokenManager:
    def __init__(self, token_file, auth_base_url=DEFAULT_AUTH_BASE_URL):
        self.token_file = token_file
        self.auth_base_url = auth_base_url
        self.token_data = self.load_tokens() or {}

        if self.token_data.get("auth_base_url"):
            self.auth_base_url = self.token_data.get("auth_base_url")

    def load_tokens(self):
        """Load tokens from file"""
        try:
            if os.path.exists(self.token_file):
                with open(self.token_file, "r") as f:
                    data = json.load(f)
                    # print(f"✓ Loaded tokens from {self.token_file}")
                    return data
            return None
        except Exception as e:
            print(f"✗ ERROR: Error loading tokens: {e}")
            return None

    def save_tokens(self):
        """Save updated tokens to file"""
        try:
            with open(self.token_file, "w") as f:
                json.dump(self.token_data, f, indent=4)
            print("✓ Tokens saved successfully")
        except Exception as e:
            print(f"✗ ERROR: Error saving tokens: {e}")

    def get_access_token(self):
        """Get current access token"""
        return self.token_data.get("tokens", {}).get("access_token")

    def get_refresh_token(self):
        """Get refresh token"""
        return self.token_data.get("tokens", {}).get("refresh_token")

    def is_token_expired(self):
        """Check if access token is expired"""
        expires_in = self.token_data.get("tokens", {}).get("expires_in", 3600)
        saved_at = self.token_data.get("saved_at", 0)
        elapsed = time.time() - saved_at
        # Add 10 minute buffer to avoid edge cases
        return elapsed >= (expires_in - 600)

    def refresh_access_token(self):
        """Refresh the access token using refresh token"""
        print("  → Access token expired, refreshing...")

        refresh_token = self.get_refresh_token()
        if not refresh_token:
            print("  ✗ ERROR: No refresh token available")
            return False

        endpoint = f"{self.auth_base_url}/Authentication/OAuth2/Token"

        payload = {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "scope": SCOPE,
        }

        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        try:
            print(f"  → Calling token refresh endpoint: {endpoint}")
            response = requests.post(
                endpoint, data=payload, headers=headers, timeout=30
            )

            if response.status_code == 200:
                try:
                    new_tokens = response.json()
                    if "access_token" not in new_tokens:
                        print(
                            "  ✗ ERROR: Invalid token response - missing access_token"
                        )
                        return False

                    if "tokens" not in self.token_data:
                        self.token_data["tokens"] = {}

                    self.token_data["tokens"].update(new_tokens)
                    self.token_data["saved_at"] = time.time()
                    self.save_tokens()
                    print("  ✓ Token refreshed successfully")
                    return True
                except json.JSONDecodeError:
                    print("  ✗ ERROR: Invalid JSON in token response")
                    return False
            else:
                print(
                    f"  ✗ ERROR: Token refresh failed with status {response.status_code}"
                )
                return False
        except Exception as e:
            print(f"  ✗ ERROR: Error refreshing token: {e}")
            return False

    def validate_and_refresh_token(self):
        """Validate token and refresh if needed"""
        print("\n[1/4] Validating tokens...")

        access_token = self.get_access_token()
        if not access_token:
            print("  ✗ ERROR: No access token found in token file")
            return False

        if self.is_token_expired():
            print("  → Token is expired or expiring soon")
            if not self.refresh_access_token():
                print(
                    "\n✗ ERROR: Could not refresh access token. Please re-authenticate."
                )
                return False
        else:
            elapsed = time.time() - self.token_data.get("saved_at", 0)
            expires_in = self.token_data.get("tokens", {}).get("expires_in", 3600)
            remaining = expires_in - elapsed
            print(f"  ✓ Access token is still valid (expires in {int(remaining)}s)")

        return True

    # --- Login Flow Methods ---

    def get_login_url_sweden(self):
        return "https://infomentor.se/Swedish/Production/mentor/?isimhapp=1"

    def extract_auth_guid(self, json_str):
        """Extracts authGuid from the JSON string"""
        match = re.search(r'authGuid=([^&"]+)', json_str)
        if match:
            return match.group(1)
        return None

    def perform_login_oauth2(self, auth_guid, device_id="python_script"):
        """Calls the LoginOAuth2 endpoint to get the authorization code"""
        endpoint = f"{self.auth_base_url}/Authentication/Authentication/LoginOAuth2"

        params = {
            "authGuid": auth_guid,
            "DeviceIdentifier": device_id,
            "DeviceFriendlyName": "Python Script",
            "DevicePlatform": DEVICE_PLATFORM,
            "scope": SCOPE,
            "redirect_uri": REDIRECT_URI,
            "client_id": CLIENT_ID,
            "response_type": "code",
            "isSandBox": "false",
        }

        print(f"Requesting Authorization Code from {endpoint}...")
        response = requests.get(endpoint, params=params, allow_redirects=False)

        if response.status_code == 302:
            location = response.headers.get("Location")
            parsed = urllib.parse.urlparse(location)
            query_params = urllib.parse.parse_qs(parsed.query)
            code = query_params.get("code", [None])[0]
            return code
        return None

    def exchange_code_for_token(self, code):
        """Exchanges the authorization code for tokens"""
        endpoint = f"{self.auth_base_url}/Authentication/OAuth2/Token"

        payload = {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
        }

        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        print(f"Exchanging code for token at {endpoint}...")
        response = requests.post(endpoint, data=payload, headers=headers)

        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error exchanging token: {response.status_code}")
            print(response.text)
            return None

    def run_interactive_login(self):
        """Run the interactive login flow"""
        print("InfoMentor Auth Script (Mobile Flow)")
        print("-------------------------------------")

        print("\nINSTRUCTIONS:")
        print(f"1. Open Chrome or Firefox and go to: {self.get_login_url_sweden()}")
        print("2. Log in with BankID.")
        print(
            "3. Wait until you are fully logged in and see the main InfoMentor dashboard."
        )
        print("4. Open Developer Tools (F12) -> Console.")
        print("5. PASTE the following command into the Console and press Enter:")
        print("-" * 60)
        print(
            'fetch("account/pair/GetAuthenticationData", {method: "POST"}).then(r => r.text()).then(console.log);'
        )
        print("-" * 60)
        print("6. Copy the JSON string that appears in the console.")

        json_str = input("\nPaste the JSON string here: ").strip()

        if not json_str:
            print("No data provided. Exiting.")
            return

        try:
            data = json.loads(json_str)
            auth_url = data.get("authenticationUrl", "")
            api_base_url = data.get("apiUrl", DEFAULT_API_BASE_URL)

            if "/Authentication/" in auth_url:
                self.auth_base_url = auth_url.split("/Authentication/")[0]

            print(f"Auth Base URL: {self.auth_base_url}")
            print(f"API Base URL: {api_base_url}")

            auth_guid = self.extract_auth_guid(json_str)
            if not auth_guid:
                print("Could not extract authGuid from the provided JSON.")
                return

            print(f"Auth GUID: {auth_guid}")

            code = self.perform_login_oauth2(auth_guid)
            if code:
                print(f"Got Authorization Code: {code}")
                tokens = self.exchange_code_for_token(code)

                if tokens:
                    self.token_data = {
                        "tokens": tokens,
                        "auth_base_url": self.auth_base_url,
                        "api_base_url": api_base_url,
                        "saved_at": time.time(),
                    }
                    self.save_tokens()
                    print("\nLogin successful!")
                else:
                    print("\nLogin failed during token exchange.")
            else:
                print("\nLogin failed during authorization.")

        except json.JSONDecodeError:
            print("Invalid JSON string.")


class SessionManager:
    def __init__(
        self, token_manager: TokenManager, session: requests.Session, api_base_url
    ):
        self.token_manager = token_manager
        self.session = session
        self.api_base_url = api_base_url
        self.web_base_url = None
        self.use_bearer_token = False

    def get_sso_url(self):
        """
        Call the SSO endpoint to get a web URL with session.
        This mimics what the Android app does in MainPresenter.singleSignIn()
        """
        endpoint = f"{self.api_base_url}/NA1/Authentication/sso"

        access_token = self.token_manager.get_access_token()
        headers = {
            "Authorization": f"Bearer {access_token}",
            "User-Agent": "InfoMentor/1.0.85 (Android; 35)",
            "X-IMHomeApp-Version": "Android_V_1.0.85",
        }

        try:
            print(f"  → Calling SSO endpoint: {endpoint}")
            response = requests.get(
                endpoint, headers=headers, allow_redirects=False, timeout=30
            )

            if response.status_code == 200:
                sso_url = response.text.strip().strip('"').strip("'")

                # Validate URL format
                if not sso_url.startswith("http"):
                    print(f"  ✗ ERROR: Invalid SSO URL format: {sso_url[:100]}")
                    return None

                print(f"  ✓ Got SSO URL: {sso_url[:80]}...")
                return sso_url
            elif response.status_code == 401:
                print("  ✗ ERROR: Unauthorized (401). Token may be invalid or expired.")
                print(f"  Response: {response.text[:200]}")
                return None
            else:
                print(f"  ✗ ERROR: SSO endpoint returned status {response.status_code}")
                print(f"  Response: {response.text[:500]}")
                return None
        except requests.exceptions.RequestException as e:
            print(f"  ✗ ERROR: Network error getting SSO URL: {e}")
            return None
        except Exception as e:
            print(f"  ✗ ERROR: Unexpected error getting SSO URL: {e}")
            return None

    def establish_web_session_with_selenium(self, sso_url):
        """
        Use Selenium to load the SSO URL and let JavaScript execute to complete authentication.
        Then extract cookies and add them to the requests session.
        """
        print("  → Using Selenium to complete SSO authentication...")

        driver = None
        try:
            # Set up Chrome options for headless mode
            chrome_options = ChromeOptions()
            chrome_options.add_argument("--headless=new")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument(
                "--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )

            # Create driver
            try:
                driver = webdriver.Chrome(options=chrome_options)
            except Exception as e:
                print(f"  ✗ ERROR: Failed to create Chrome driver: {e}")
                print("  → Make sure Chrome/Chromium is installed")
                print(
                    "  → On Linux, install with: sudo apt-get install chromium-browser"
                )
                return False

            driver.set_page_load_timeout(30)

            print("  → Loading SSO URL in browser...")
            driver.get(sso_url)

            # Wait for page to load and JavaScript to execute
            print("  → Waiting for authentication to complete...")

            try:
                # Wait until we're not on a login page anymore, or wait for a timeout
                max_wait = 30
                waited = 0
                while waited < max_wait:
                    current_url = driver.current_url
                    if (
                        "login" not in current_url.lower()
                        or "hub.infomentor.se" in current_url
                    ):
                        print(f"  → Redirected to: {current_url[:100]}")
                        break
                    time.sleep(1)
                    waited += 1

                # Give a bit more time for any final JavaScript execution
                time.sleep(2)

            except Exception as e:
                print(f"  ⚠ Timeout or error waiting for redirect: {e}")

            # Extract cookies from Selenium and add to requests session
            print("  → Extracting cookies from browser...")
            selenium_cookies = driver.get_cookies()

            for cookie in selenium_cookies:
                self.session.cookies.set(
                    name=cookie["name"],
                    value=cookie["value"],
                    domain=cookie.get("domain", ""),
                    path=cookie.get("path", "/"),
                )

            print(f"  → Extracted {len(selenium_cookies)} cookies from browser")

            final_url = driver.current_url
            print(f"  → Final URL after SSO: {final_url[:100]}")

            return True

        except Exception as e:
            print(f"  ✗ ERROR: Selenium error: {e}")
            import traceback

            traceback.print_exc()
            return False
        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass

    def establish_web_session(self):
        """
        Use the SSO URL to establish a web session with cookies.
        Uses Selenium to execute JavaScript and complete authentication.
        """
        print("\n[2/4] Establishing web session...")

        sso_url = self.get_sso_url()
        if not sso_url:
            print("  ✗ ERROR: Could not get SSO URL")
            return False

        # Extract base URL from SSO URL
        parsed = urlparse(sso_url)
        self.web_base_url = f"{parsed.scheme}://hub.infomentor.se"
        print(f"  → Using hub URL: {self.web_base_url}")

        # Use Selenium to complete the SSO flow
        if not self.establish_web_session_with_selenium(sso_url):
            print("  ✗ ERROR: Failed to establish session with Selenium")
            return False

        # Verify the session works by testing the news API
        print("  → Testing session with news API endpoint...")
        test_url = f"{self.web_base_url}/Communication/News/GetNewsList"
        test_headers = {
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "en-US,en;q=0.6",
            "Cache-Control": "no-cache",
            "Origin": "https://hub.infomentor.se",
            "Pragma": "no-cache",
            "Referer": f"{self.web_base_url}/",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "X-Requested-With": "XMLHttpRequest",
        }

        try:
            test_response = self.session.get(
                test_url, headers=test_headers, timeout=10, allow_redirects=False
            )

            if test_response.status_code == 200:
                try:
                    test_data = test_response.json()
                    if isinstance(test_data, dict):
                        print("  ✓ Session test successful - got valid JSON response")
                        return True
                except:
                    pass
                print(
                    f"  ✓ Session test got 200 OK (response length: {len(test_response.text)} bytes)"
                )
                return True
            elif test_response.status_code in [301, 302, 303, 307, 308]:
                redirect_url = test_response.headers.get("Location", "")
                print(f"  ⚠ Session test got redirect {test_response.status_code}")
                if redirect_url:
                    print(f"  → Redirect to: {redirect_url[:100]}")
                if "login" in redirect_url.lower():
                    print(
                        "  ✗ ERROR: Still redirected to login - session not authenticated"
                    )
                    return False
                # Try following the redirect
                final_response = self.session.get(
                    redirect_url, headers=test_headers, timeout=10
                )
                if final_response.status_code == 200:
                    print("  ✓ Session test successful after redirect")
                    return True
            else:
                print(f"  ✗ ERROR: Session test returned {test_response.status_code}")
                print(f"  → Response: {test_response.text[:200]}")
                return False
        except Exception as e:
            print(f"  ✗ ERROR: Error testing session: {e}")
            return False
