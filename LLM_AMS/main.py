#!/usr/bin/env python3
import sys


if __name__ == "__main__":
    try:
        from cli import run_cli
        run_cli()
    except KeyboardInterrupt:
        sys.stderr.write("\nInterrupted.\n")
        sys.exit(130)
    except Exception as exc:
        sys.stderr.write(f"Error: {exc}\n")
        sys.stderr.write("\nUsage:\n  python main.py\n")
        sys.exit(1)
