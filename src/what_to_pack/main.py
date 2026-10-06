"""Multi-Agent Travel Packing System using Microsoft Agentic Framework and Azure AI Foundry."""

import argparse
import asyncio
import os
import sys

# Allow direct script execution without installing the src-layout package.
if __package__ is None:
    src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)

if __package__:
    from .workflow import run_with_timeout
else:
    from what_to_pack.workflow import run_with_timeout


def main() -> int:
    """Main entry point for the application."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request", nargs="?", help="Travel description; prompts if omitted")
    args = parser.parse_args()
    print("🧠 AI-Powered Travel Packing Assistant (Azure AI Foundry Required)")
    print("📝 Microsoft Agentic Framework with Azure AI Foundry")
    print("Weather data: current temperature and wind, not a forecast for your travel dates.")
    print("=" * 60)

    try:
        user_input = args.request if args.request is not None else input("✈️  Describe your travel plans: ")
        result = asyncio.run(run_with_timeout(user_input))
        print("\n" + "=" * 60)
        print(result)
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
        return 130
    except EOFError:
        print("\nNo input received. Pass a travel description as an argument.", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"\n❌ Configuration or runtime error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
