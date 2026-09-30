"""Ask one handbook question from the terminal."""

from __future__ import annotations

import argparse

from app.orchestrator import Orchestrator


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ask the Harborline handbook.")
    parser.add_argument("question", help="Policy question to answer from the local handbook.")
    args = parser.parse_args(argv)
    result = Orchestrator.from_settings().chat(None, args.question)
    print(result.answer)
    print()
    if result.sources:
        print("Sources:")
        for source in result.sources:
            print(
                f"- {source['title']} / {source['section']} "
                f"(score {source['score']}, owner {source['owner']})"
            )
    else:
        print("Sources: none")
    print(
        f"Model: {result.model} | Refused: {result.refused} | "
        f"Confidence: {result.confidence} | {result.latency_ms} ms"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
