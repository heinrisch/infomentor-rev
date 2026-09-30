#!/usr/bin/env python3


import argparse
from datetime import datetime
from pathlib import Path

from infomentor.runner import CriticalFetchError, InfoMentorFetcher
from infomentor.auth import TokenManager
from infomentor.config import Config


def at_type(value):
    times = []
    for part in value.split(","):
        try:
            times.append(datetime.strptime(part.strip(), "%H:%M").time())
        except ValueError:
            raise argparse.ArgumentTypeError(
                f"invalid time {part.strip()!r}, expected HH:MM"
            )
    if not times:
        raise argparse.ArgumentTypeError("expected at least one HH:MM time")
    return times


def cmd_fetch(args):
    try:
        fetcher = InfoMentorFetcher(
            notify=not args.no_notify, enable_llm=not args.no_llm
        )
        if args.once:
            try:
                fetcher.fetch_and_process()
            except CriticalFetchError as e:
                print(f"\nCRITICAL ERROR: {e}")
                fetcher.notifier.send_error("Fetch Failed", str(e))
        else:
            fetcher.run(base_interval=args.interval, at_times=args.at)
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
    fetch_parser.add_argument(
        "--no-notify",
        action="store_true",
        help="Fetch and store without sending notifications",
    )
    fetch_parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Skip LLM summarization",
    )
    fetch_parser.add_argument(
        "--at",
        type=at_type,
        default=None,
        metavar="HH:MM[,HH:MM...]",
        help="Run once at start, then daily at these local times "
        "(e.g. --at 06:00,18:00). Overrides --interval.",
    )
    fetch_parser.set_defaults(func=cmd_fetch)

    # Auth command
    auth_parser = subparsers.add_parser("auth", help="Interactive login to InfoMentor")
    auth_parser.set_defaults(func=cmd_auth)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
