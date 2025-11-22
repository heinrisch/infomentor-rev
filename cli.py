#!/usr/bin/env python3


import argparse
from pathlib import Path

from infomentor.runner import InfoMentorFetcher
from infomentor.auth import TokenManager
from infomentor.config import Config


def cmd_fetch(args):
    try:
        fetcher = InfoMentorFetcher()
        if args.once:
            fetcher.fetch_and_process()
        else:
            fetcher.run(base_interval=args.interval)
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        import traceback

        traceback.print_exc()


def cmd_auth(args):
    config = Config()
    manager = TokenManager(config.token_file)
    manager.run_interactive_login()


def main():
    parser = argparse.ArgumentParser(description="InfoMentor News Tools")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    subparsers.required = True

    # Fetch command
    fetch_parser = subparsers.add_parser("fetch", help="Fetch news from InfoMentor")
    fetch_parser.add_argument("--once", action="store_true", help="Run once and exit")
    fetch_parser.add_argument(
        "--interval",
        type=int,
        default=60 * 60 * 12,
        help="Interval in seconds (default: 12 hours)",
    )
    fetch_parser.set_defaults(func=cmd_fetch)

    # Auth command
    auth_parser = subparsers.add_parser("auth", help="Interactive login to InfoMentor")
    auth_parser.set_defaults(func=cmd_auth)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
