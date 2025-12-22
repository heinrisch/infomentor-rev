# InfoMentor Notifier

A Python tool designed to fetch news, schedules, and notifications from the [InfoMentor](https://www.infomentor.se/) platform and deliver them directly to your Discord server or Telegram chat.

- Uses long-lived tokens from mobile auth
- Supports BankID login

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
   TELEGRAM_BOT_TOKEN=your_telegram_bot_token
   TELEGRAM_CHAT_ID=your_telegram_chat_id
   ```

   > **Note:** The notification channels are enabled based on which variables are present.
   > - To enable **Discord**, set `DISCORD_WEBHOOK_URL`.
   > - To enable **Telegram**, set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`.
   > - To enable **both**, set all variables.
   > - To **disable** a channel, simply remove or comment out (`#`) the corresponding lines in `.env`.

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

## Docker Setup

The application can be run in a Docker container for easier deployment and isolation.

### Prerequisites

- Docker
- Docker Compose (recommended)

### Quick Start with Docker Compose

1. **Copy the example environment file:**
   ```bash
   cp .env.example .env
   ```

2. **Edit `.env` and add your credentials:**
   ```env
   DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN
   PERPLEXITY_API_KEY=pplx-your-api-key-here
   TELEGRAM_BOT_TOKEN=your_telegram_bot_token
   TELEGRAM_CHAT_ID=your_telegram_chat_id
   ```

3. **Authenticate (one-time setup):**
   
   Before running the fetcher, you need to authenticate. Run the auth command:
   ```bash
   docker-compose run --rm infomentor-fetcher auth
   ```
   
   Follow the interactive prompts to log in with BankID. This will create `infomentor_tokens.json` in your current directory.

4. **Start the fetcher:**
   ```bash
   docker-compose up -d
   ```

5. **View logs:**
   ```bash
   docker-compose logs -f
   ```

6. **Stop the fetcher:**
   ```bash
   docker-compose down
   ```

### Docker Compose Configuration

The `docker-compose.yml` file includes the following configurable options:

- **Environment Variables:** Set via `.env` file
  - `DISCORD_WEBHOOK_URL` - Discord webhook for notifications
  - `TELEGRAM_BOT_TOKEN` - Telegram Bot Token
  - `TELEGRAM_CHAT_ID` - Telegram Chat ID
  - `PERPLEXITY_API_KEY` - API key for LLM processing

- **Volumes:** Persistent data storage
  - `./infomentor_tokens.json` - Authentication tokens
  - `./news` - Fetched news articles
  - `./files` - Downloaded files

- **Command Options:** Modify the `command` in `docker-compose.yml`:
  ```yaml
  command: ["fetch", "--once"]  # Run once and exit
  command: ["fetch", "--interval", "3600"]  # Run every hour (3600 seconds)
  ```

### Standalone Docker Usage

If you prefer not to use Docker Compose:

1. **Build the image:**
   ```bash
   docker build -t infomentor-fetcher .
   ```

2. **Run authentication:**
   ```bash
   docker run --rm -it \
     -v $(pwd)/infomentor_tokens.json:/app/infomentor_tokens.json \
     infomentor-fetcher auth
   ```

3. **Run the fetcher:**
   ```bash
   docker run -d \
     --name infomentor-fetcher \
     --shm-size=2gb \
     -e DISCORD_WEBHOOK_URL="your_webhook_url" \
     -e TELEGRAM_BOT_TOKEN="your_bot_token" \
     -e TELEGRAM_CHAT_ID="your_chat_id" \
     -e PERPLEXITY_API_KEY="your_api_key" \
     -v $(pwd)/infomentor_tokens.json:/app/infomentor_tokens.json \
     -v $(pwd)/news:/app/news \
     -v $(pwd)/files:/app/files \
     infomentor-fetcher fetch
   ```

### Troubleshooting Docker

- **Chromium issues:** The container includes Chromium for Selenium. If you encounter issues, ensure `shm_size` is set to at least `2gb`.
- **Permission issues:** Ensure the mounted volumes have appropriate permissions.
- **Token expiration:** If authentication fails, re-run the `auth` command to refresh tokens.