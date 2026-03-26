# InfoMentor Notifier Architecture

This document describes the internal architecture of the InfoMentor Notifier project and how its various components work together to fetch, process, and deliver updates to end users.

## 1. System Overview

The InfoMentor Notifier is designed as a modular polling system. It authenticates with the InfoMentor platform, extracts session cookies, queries internal APIs for various pupil data (news, schedules, attendance, and notifications), processes this data (sometimes leveraging an LLM for summarization), and broadcasts updates to configured chat platforms (Discord and Telegram).

## 2. Core Components

The project is structured around distinct responsibilities. Here is a breakdown of the key components located in the `infomentor/` package:

### 2.1 Orchestration (`cli.py` & `runner.py`)
- **`cli.py`**: The command-line interface. It handles argument parsing (e.g., whether to run an initial authentication flow, fetch once, or run as a continuous daemon loop).
- **`runner.py` (`InfoMentorFetcher`)**: The central orchestrator. It initializes all managers, fetchers, and notifiers. Its `run` loop periodically calls `fetch_and_process()`, which validates the token, establishes the web session, determines the list of pupils, and sequentially triggers each data fetcher per pupil.

### 2.2 Authentication & Session Management (`auth.py`)
Because InfoMentor requires BankID and specific mobile-app-like authentication flows, session management is handled in two parts:
- **`TokenManager`**: Manages long-lived OAuth2 tokens. It provides functions for interactive login, token storage, and automatic token refresh when the access token expires.
- **`SessionManager`**: Bridges the gap between the mobile API and the web hub. It uses the `TokenManager`'s access token to hit an SSO endpoint, retrieving a one-time login URL. It then spins up a headless Selenium browser, navigates to the SSO URL, waits for the JavaScript-heavy authentication redirect to complete, and extracts the resulting web cookies. These cookies are attached to a standard `requests.Session` that the rest of the application uses for fast API calls.

### 2.3 Data Fetchers (`*_fetcher.py`)
Each type of data has its own dedicated fetcher class. They all share the authenticated `requests.Session` and `StorageManager`.
- **`PupilFetcher`**: Retrieves the list of children associated with the parent's account. This dictates the loops for the other fetchers.
- **`NewsFetcher`**: Checks for new news items. If it detects a new item (by cross-referencing with `StorageManager`), it downloads associated attachments and passes the raw text to the LLM for summarization before notifying.
- **`ScheduleFetcher`**: Downloads the weekly schedule, comparing it against the previous state to detect modifications (additions, removals, changes).
- **`AttendanceFetcher`**: Polls for new attendance records (e.g., sick leave or late arrivals).
- **`NotificationFetcher`**: Pulls from the general notification feed. When an alert corresponds to a deeper message or news item, it attempts to fetch the full context for a richer payload.

### 2.4 Data Processing (`llm_client.py`)
To make lengthy, formal Swedish school updates easily digestible, the system employs an LLM.
- **`LLMClient`**: Wraps the Perplexity and Gemini APIs. If a news post or message exceeds 300 characters, the text is sent to an LLM with strict instructions to return a JSON object containing a concise summary, key highlights, and specific chronological events (formatted as ISO 8601). This structured data is then attached to the outgoing notification payload.

### 2.5 Storage (`storage.py`)
The system avoids duplicate notifications by keeping a local, file-based state.
- **`StorageManager`**: Saves raw JSON responses to the `news/` directory using naming conventions tied to pupil IDs and entity IDs. Before a fetcher processes an item, it queries the `StorageManager` to see if the ID already exists on disk. It also manages file downloads (attachments) to a `files/` directory.

### 2.6 Notification Layer (`notifier.py`, `discord_notifier.py`, `telegram_notifier.py`)
The system supports multiple broadcast channels.
- **`CompositeNotifier`**: A wrapper class that iterates over all enabled notifiers. It wraps each broadcast in a `try-except` block to ensure that a failure in one service (e.g., Discord rate limiting) does not block delivery to another service (e.g., Telegram).
- **`DiscordNotifier` & `TelegramNotifier`**: Service-specific implementations. They receive identical generic arguments (summaries, highlights, attachments) and are responsible for formatting the data according to the platform's specific markdown and payload constraints (e.g., handling Telegram's strict MarkdownV2 escaping and chunking text to fit Discord's 4096-character embed limits).

## 3. The Data Flow (Typical Cycle)

1. **Wake Up**: The daemon loop in `runner.py` wakes up after its sleep interval.
2. **Session Check**: The `TokenManager` validates the OAuth2 token (refreshing via API if necessary). The `SessionManager` checks the web session; if invalid, it performs the Selenium SSO handshake to get fresh cookies.
3. **Pupil Discovery**: `PupilFetcher` grabs the list of students.
4. **Context Switching**: For each student, the `requests.Session` hits a context-switch endpoint on the InfoMentor hub to lock the API responses to that specific child.
5. **Fetching & Storage**:
   - `NewsFetcher` hits the news endpoint. It checks the IDs against `StorageManager`. New items are written to disk.
   - Attachments are downloaded.
   - The text is passed to `LLMClient` for summarization.
   - The final packaged payload (Summary, Highlights, Events, Attachments) is sent to `CompositeNotifier`.
6. **Iteration**: Steps 4 and 5 are repeated for Schedules, Attendance, and Notifications.
7. **Sleep**: The cycle completes, and the system sleeps with a randomized jitter to prevent rigid polling patterns.
