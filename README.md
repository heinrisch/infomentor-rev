# InfoMentor Notifier

A Python tool designed to fetch news, schedules, and notifications from the InfoMentor platform and deliver them directly to your Discord server.

## Features

- **Automated Fetching**: Retrieves news, schedules, and notifications from InfoMentor.
- **Discord Integration**: Sends updates directly to a configured Discord webhook.
- **Smart Processing**: Leveraging Perplexity AI for content analysis (implied usage).
- **Persistent Session**: Handles authentication via Selenium and maintains session tokens for long-running operation.

## Prerequisites

- Python 3.11 or higher
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

## Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd infomentor-rev
   ```

2. Install dependencies:
   ```bash
   uv sync
   ```

## Configuration

1. Create a `.env` file in the root directory:
   ```bash
   touch .env
   ```

2. Add the following configuration variables to `.env`:
   ```env
   PERPLEXITY_API_KEY=your_perplexity_api_key
   DISCORD_WEBHOOK_URL=your_discord_webhook_url
   ```

## Usage

The application is controlled via the `cli.py` script.

### 1. Authentication

First, run the authentication command to log in to InfoMentor. This will launch a browser window (Selenium) for you to log in interactively. Tokens will be saved to `infomentor_tokens.json`.

```bash
uv run cli.py auth
```

### 2. Fetching Data

To start fetching data, you can run the tool in two modes:

**Run once and exit:**
```bash
uv run cli.py fetch --once
```

**Run as a daemon (continuous polling):**
```bash
uv run cli.py fetch
```