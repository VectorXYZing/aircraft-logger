#!/usr/bin/env python3
import argparse
import subprocess
import sys
import os

def run_logger():
    print("Starting Aircraft Logger...")
    subprocess.run([sys.executable, "aircraft_logger.py"])

def run_dashboard():
    print("Starting Aircraft Dashboard...")
    subprocess.run([sys.executable, "dashboard.py"])

def migrate_db():
    print("Running database migrations...")
    from airlogger.db import init_db
    init_db()
    print("Database is up to date.")

def cleanup():
    print("Running manual cleanup...")
    from airlogger.core import cleanup_old_logs
    cleanup_old_logs()
    print("Cleanup complete.")

def main():
    parser = argparse.ArgumentParser(description="Aircraft Logger Management Tool")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("run-logger", help="Start the aircraft logger service")
    subparsers.add_parser("run-dashboard", help="Start the dashboard web server")
    subparsers.add_parser("migrate", help="Initialize or migrate the database")
    subparsers.add_parser("cleanup", help="Manually trigger log cleanup")

    args = parser.parse_args()

    if args.command == "run-logger":
        run_logger()
    elif args.command == "run-dashboard":
        run_dashboard()
    elif args.command == "migrate":
        migrate_db()
    elif args.command == "cleanup":
        cleanup()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
