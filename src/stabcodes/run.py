"""Build and decode a benchmark through one interactive command."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, TypeVar

from stabcodes.cli.build import main as build_main
from stabcodes.decode.run import (
    DEFAULT_PROBABILITIES,
    main as decode_main,
    nonnegative_int,
    parse_probabilities,
    positive_int,
)

DEFAULT_SHOTS = 200_000
DEFAULT_SEED = 12_345

T = TypeVar("T")


def derive_output_directory(benchmark: Path, working_directory: Path) -> Path:
    """Derive results/<benchmark subdirectory>/<benchmark stem>."""
    benchmark_path = benchmark.resolve()
    benchmarks_root = (working_directory / "benchmarks").resolve()
    try:
        relative_path = benchmark_path.relative_to(benchmarks_root)
    except ValueError:
        relative_path = Path(benchmark_path.name)
    return working_directory / "results" / relative_path.with_suffix("")


def prompt_with_default(
    label: str,
    default_text: str,
    parser: Callable[[str], T],
) -> T:
    while True:
        try:
            entered = input(f"{label} [{default_text}]: ").strip()
        except EOFError:
            entered = ""

        try:
            return parser(entered or default_text)
        except (argparse.ArgumentTypeError, ValueError) as exc:
            print(f"Invalid value: {exc}. Please try again.")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Build and decode a benchmark in one interactive run."
    )
    parser.add_argument(
        "benchmark",
        type=Path,
        help="Path to a benchmark text file",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Optional output directory (otherwise derived from the benchmark path)",
    )
    args = parser.parse_args(argv)

    benchmark = args.benchmark.expanduser()
    if not benchmark.is_file():
        parser.error(f"benchmark file does not exist: {benchmark}")

    shots = prompt_with_default("Shots per physical error rate", str(DEFAULT_SHOTS), positive_int)
    probabilities = prompt_with_default(
        "Physical error rates (comma-separated)",
        DEFAULT_PROBABILITIES,
        parse_probabilities,
    )
    seed = prompt_with_default("Random seed", str(DEFAULT_SEED), nonnegative_int)

    output_directory = (
        args.out.expanduser()
        if args.out is not None
        else derive_output_directory(benchmark, Path.cwd())
    )

    print(
        "\n"
        f"Benchmark: {benchmark}\n"
        f"Output:    {output_directory}\n"
        f"Shots:     {shots}\n"
        f"p values:  {','.join(format(p, '.12g') for p in probabilities)}\n"
        f"Seed:      {seed}\n"
    )

    with benchmark.open(encoding="utf-8") as benchmark_file:
        original_stdin = sys.stdin
        try:
            sys.stdin = benchmark_file
            build_main(["--out", str(output_directory)])
        finally:
            sys.stdin = original_stdin

    metadata_path = output_directory / "build_meta.json"
    if not metadata_path.is_file():
        raise RuntimeError(
            "the circuit build did not produce build_meta.json; "
            "check the benchmark format above"
        )

    probability_text = ",".join(format(p, ".17g") for p in probabilities)
    decode_main(
        [
            "--meta",
            str(metadata_path),
            "--out",
            str(output_directory),
            "--shots",
            str(shots),
            "--plist",
            probability_text,
            "--seed",
            str(seed),
        ]
    )

    run_config = {
        "benchmark": str(benchmark.resolve()),
        "output_directory": str(output_directory.resolve()),
        "shots_per_probability": shots,
        "physical_error_rates": probabilities,
        "seed": seed,
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    config_path = output_directory / "run_config.json"
    with config_path.open("w", encoding="utf-8") as config_file:
        json.dump(run_config, config_file, indent=2)
        config_file.write("\n")

    print(f"Run configuration: {config_path}")


if __name__ == "__main__":
    main()
