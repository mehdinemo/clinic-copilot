"""Evaluation runner script for Clinic Operations Assistant.

Runs scripted operational scenarios against the live agent with real LLM tool calls.
Requires an API key (e.g., OPENAI_API_KEY in .env).
"""

import argparse
import os
import sys
import uuid
from typing import List

from dotenv import load_dotenv

from app import clock
from app.agent.graph import build_graph
from app.cli import run_turn
from app.db.database import (
    get_engine,
    get_session_factory,
    init_db,
    set_default_session_factory,
)
from app.db.seed import seed_database
from app.observability import InMemoryTraceCollector
from evals.checks import check_groundedness, check_phrases, check_trajectory
from evals.scenarios import SCENARIOS, EvalScenario

load_dotenv()


def run_scenario(scenario: EvalScenario) -> bool:
    """Execute all turns of a single evaluation scenario and assert compliance."""
    print(f"\n[RUNNING] Scenario: {scenario.name}")
    print(f"          Description: {scenario.description}")

    # 1. Reset clock to baseline
    clock.reset_now()

    # 2. Fresh in-memory seeded DB per scenario
    engine = get_engine("sqlite:///:memory:")
    init_db(engine)
    session_factory = get_session_factory(engine)
    set_default_session_factory(session_factory)

    with session_factory() as session:
        seed_database(session)

    # 3. Build live graph
    graph = build_graph()
    thread_id = uuid.uuid4().hex
    scenario_passed = True

    for i, turn in enumerate(scenario.turns, start=1):
        collector = InMemoryTraceCollector()
        print(f"  -> Turn {i}: '{turn.user_prompt}'")

        response = run_turn(
            graph=graph,
            text=turn.user_prompt,
            thread_id=thread_id,
            callbacks=[collector],
        )
        print(f"     Agent > {response[:160]}...")

        # Run checks
        traj_ok, traj_msg = check_trajectory(
            events=collector.events,
            expected_tools=turn.expected_tools,
            forbidden_tools=turn.forbidden_tools,
        )
        if not traj_ok:
            print(f"     [FAIL] Trajectory: {traj_msg}")
            scenario_passed = False
        else:
            print(f"     [PASS] Trajectory: {traj_msg}")

        phrase_ok, phrase_msg = check_phrases(
            response_text=response,
            expected_phrases=turn.expected_phrases,
            forbidden_phrases=turn.forbidden_phrases,
        )
        if not phrase_ok:
            print(f"     [FAIL] Phrases: {phrase_msg}")
            scenario_passed = False
        else:
            print("     [PASS] Semantic phrases verified.")

        if turn.check_groundedness:
            ground_ok, ground_msg = check_groundedness(
                response_text=response,
                events=collector.events,
                user_prompt=turn.user_prompt,
            )
            if not ground_ok:
                print(f"     [FAIL] Groundedness: {ground_msg}")
                scenario_passed = False
            else:
                print("     [PASS] Groundedness verified (no fabricated entities).")

    return scenario_passed


def main() -> None:
    """CLI entry point for running the evaluation harness."""
    parser = argparse.ArgumentParser(description="Clinic Copilot Evaluation Harness")
    parser.add_argument(
        "--scenario",
        type=str,
        default=None,
        help="Run only the specified scenario by name.",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=1,
        help="Number of iterations to evaluate pass rates under nondeterminism.",
    )
    args = parser.parse_args()

    # Verify API key is available
    if not os.environ.get("OPENAI_API_KEY") and not os.environ.get("ANTHROPIC_API_KEY"):
        print("=" * 60, file=sys.stderr)
        print(" [!] Missing API Credentials for Live Evaluation", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        print(
            "The evaluation harness tests real multi-tool trajectories with an LLM.\n"
            "Please configure OPENAI_API_KEY in your .env file or environment:\n\n"
            "    cp .env.example .env\n"
            "    # Edit .env and set OPENAI_API_KEY\n"
            "    uv run python -m evals.run\n",
            file=sys.stderr,
        )
        sys.exit(1)

    scenarios_to_run: List[EvalScenario] = SCENARIOS
    if args.scenario:
        scenarios_to_run = [s for s in SCENARIOS if s.name == args.scenario]
        if not scenarios_to_run:
            print(f"Error: Unknown scenario '{args.scenario}'", file=sys.stderr)
            sys.exit(1)

    print("==================================================")
    print("   Clinic Operations Assistant - Evaluation Suite ")
    print(f"   Configured runs per scenario: {args.runs}")
    print("==================================================")

    # Track results: scenario_name -> list of booleans (True=Pass, False=Fail)
    results: dict[str, list[bool]] = {sc.name: [] for sc in scenarios_to_run}

    for run_idx in range(1, args.runs + 1):
        if args.runs > 1:
            print(f"\n--- [RUN {run_idx}/{args.runs}] ---")
        for sc in scenarios_to_run:
            try:
                passed = run_scenario(sc)
                results[sc.name].append(passed)
            except Exception as exc:
                print(f"  [ERROR] Unhandled exception during scenario '{sc.name}': {exc}")
                results[sc.name].append(False)

    # Summary Table
    print("\n" + "=" * 70)
    print(f"{'Scenario Name':<35} | {'Passed/Total':<14} | {'Pass Rate':<10}")
    print("-" * 70)
    total_passes = 0
    total_executions = 0

    for name, run_outcomes in results.items():
        sc_passes = sum(1 for p in run_outcomes if p)
        sc_total = len(run_outcomes)
        total_passes += sc_passes
        total_executions += sc_total
        rate_str = f"{(sc_passes / sc_total * 100):.1f}%"
        print(f"{name:<35} | {f'{sc_passes}/{sc_total}':<14} | {rate_str:<10}")

    print("-" * 70)
    overall_pct = (total_passes / total_executions * 100) if total_executions > 0 else 0
    print(f"Overall: {total_passes}/{total_executions} passed ({overall_pct:.1f}%)\n")

    if total_passes < total_executions:
        sys.exit(1)


if __name__ == "__main__":
    main()
