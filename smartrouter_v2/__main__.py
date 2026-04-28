"""SmartRouter — CLI.

Usage:
    python -m smartrouter "Implement a Pydantic schema for IntelItem"
    python -m smartrouter --provider kimi "Refactor this module"
    python -m smartrouter --type coding_complex "Build the SourceCollector"
    python -m smartrouter --status
    python -m smartrouter --classify "Debug the edge case in scoring"
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys

from .router import SmartRouter
from .schemas import ProviderID, TaskType


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
        level=level,
    )


def print_colored(text: str, color: str = "green") -> None:
    """Simple ANSI color output."""
    colors = {
        "green": "\033[92m",
        "yellow": "\033[93m",
        "red": "\033[91m",
        "blue": "\033[94m",
        "cyan": "\033[96m",
        "magenta": "\033[95m",
        "reset": "\033[0m",
        "bold": "\033[1m",
        "dim": "\033[2m",
    }
    c = colors.get(color, "")
    reset = colors["reset"]
    print(f"{c}{text}{reset}")


def print_result(result) -> None:
    """Pretty-print a RoutingResult."""
    status_color = "green" if result.status.value == "ok" else "red"

    print()
    print_colored("─" * 60, "dim")
    print_colored(f"  Provider:  {result.provider_used.value}", "cyan")
    print_colored(
        f"  Type:      {result.classification.task_type.value} "
        f"(confidence: {result.classification.confidence:.0%})",
        "blue",
    )
    print_colored(f"  Fallback:  {'yes' if result.was_fallback else 'no'}", "yellow")
    print_colored(f"  Status:    {result.status.value}", status_color)
    print_colored(f"  Latency:   {result.latency_ms:.0f}ms", "magenta")
    print_colored(f"  Tokens:    {result.tokens_used}", "magenta")
    print_colored(f"  Cost:      ${result.cost_estimate_usd:.6f}", "magenta")
    print_colored("─" * 60, "dim")
    print()

    if result.response:
        print(result.response)
    elif result.error_message:
        print_colored(f"Error: {result.error_message}", "red")


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="SmartRouter — Multi-LLM Orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m smartrouter "Implement a Pydantic schema"
  python -m smartrouter --provider kimi "Refactor this module"
  python -m smartrouter --type architecture "Review my LangGraph design"
  python -m smartrouter --classify "Debug the edge case in scoring"
  python -m smartrouter --status
        """,
    )
    parser.add_argument(
        "task",
        nargs="?",
        help="Task description to route",
    )
    parser.add_argument(
        "--provider",
        type=str,
        choices=[p.value for p in ProviderID],
        help="Force a specific provider (skip routing)",
    )
    parser.add_argument(
        "--type",
        type=str,
        choices=[t.value for t in TaskType],
        help="Override task type classification",
    )
    parser.add_argument(
        "--system",
        type=str,
        default=None,
        help="System prompt to prepend",
    )
    parser.add_argument(
        "--classify",
        type=str,
        help="Only classify a task (don't call LLM)",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show circuit breaker status",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose logging",
    )

    args = parser.parse_args()
    setup_logging(args.verbose)

    router = SmartRouter()

    # Mode: classify only
    if args.classify:
        classification = router.classifier.classify(args.classify)
        print()
        print_colored("  Classification Result", "bold")
        print_colored("─" * 40, "dim")
        print_colored(f"  Type:       {classification.task_type.value}", "cyan")
        print_colored(f"  Complexity: {classification.complexity.value}", "blue")
        print_colored(f"  Confidence: {classification.confidence:.0%}", "yellow")
        print_colored(f"  Sensitive:  {classification.has_sensitive_data}", "red")
        print_colored(f"  Long ctx:   {classification.requires_long_context}", "magenta")
        print_colored(f"  Est tokens: {classification.estimated_tokens}", "dim")
        print_colored("─" * 40, "dim")
        print()
        return

    # Mode: status
    if args.status:
        stats = router.get_stats()
        print()
        print_colored("  SmartRouter Status", "bold")
        print_colored("─" * 40, "dim")
        print(json.dumps(stats, indent=2, default=str))
        return

    # Mode: route
    if not args.task:
        parser.print_help()
        sys.exit(1)

    force_provider = ProviderID(args.provider) if args.provider else None
    force_type = TaskType(args.type) if args.type else None

    result = await router.route(
        args.task,
        system_prompt=args.system,
        force_provider=force_provider,
        force_type=force_type,
    )
    print_result(result)


def cli_entry():
    """Entry point for `python -m smartrouter`."""
    asyncio.run(main())


if __name__ == "__main__":
    cli_entry()
