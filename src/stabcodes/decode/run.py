from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, List, Mapping, Sequence

import matplotlib.pyplot as plt
import numpy as np
import pymatching as pm
import stim

from stabcodes.build.circuit import build_circuit_per_stabilizer_index_layers

DEFAULT_PROBABILITIES = "0.001,0.003,0.005,0.007,0.009"
WILSON_95_Z = 1.959963984540054


@dataclass(frozen=True)
class BuildMetadata:
    n: int
    rounds: int
    layer_count: int
    data_lin: list[int]
    z_anc_ids: list[int]
    x_anc_ids: list[int]
    edges_by_anc: dict[int, list[int]]
    layers_by_anc: dict[int, list[list[int]]]


@dataclass(frozen=True)
class DecodeResult:
    p: float
    shots: int
    errors: int
    ler_per_shot: float
    ci95_low: float
    ci95_high: float
    sample_seed: int | None


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def nonnegative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be a nonnegative integer")
    return parsed


def parse_probabilities(value: str) -> list[float]:
    try:
        probabilities = [float(item.strip()) for item in value.split(",") if item.strip()]
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "--plist must be a comma-separated list of numbers"
        ) from exc

    if not probabilities:
        raise argparse.ArgumentTypeError("--plist must contain at least one probability")
    if any(not math.isfinite(p) or not 0 < p <= 1 for p in probabilities):
        raise argparse.ArgumentTypeError(
            "each probability in --plist must be finite and in the interval (0, 1]"
        )
    return probabilities


def _integer_lists(value: Mapping[Any, Sequence[Any]]) -> dict[int, list[int]]:
    return {int(key): [int(item) for item in items] for key, items in value.items()}


def _integer_layers(
    value: Mapping[Any, Sequence[Sequence[Any]]],
) -> dict[int, list[list[int]]]:
    return {
        int(key): [[int(item) for item in layer] for layer in layers]
        for key, layers in value.items()
    }


def load_metadata(path: Path) -> BuildMetadata:
    try:
        with path.open(encoding="utf-8") as file:
            raw = json.load(file)
        if not isinstance(raw, dict):
            raise ValueError("the top-level JSON value must be an object")

        metadata = BuildMetadata(
            n=int(raw["n"]),
            rounds=int(raw["rounds"]),
            layer_count=int(raw["L"]),
            data_lin=[int(item) for item in raw["data_lin"]],
            z_anc_ids=[int(item) for item in raw["z_anc_ids"]],
            x_anc_ids=[int(item) for item in raw["x_anc_ids"]],
            edges_by_anc=_integer_lists(raw["edges_by_anc"]),
            layers_by_anc=_integer_layers(raw["layers_by_anc"]),
        )
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"invalid metadata file {path}: {exc}") from exc

    if metadata.n <= 0 or metadata.rounds <= 0 or metadata.layer_count <= 0:
        raise ValueError("metadata fields n, rounds, and L must all be positive")
    if len(metadata.data_lin) != metadata.n:
        raise ValueError(
            f"metadata declares n={metadata.n}, but contains "
            f"{len(metadata.data_lin)} data-qubit IDs"
        )
    if not metadata.z_anc_ids and not metadata.x_anc_ids:
        raise ValueError("metadata must contain at least one X or Z ancilla")

    ancilla_ids = set(metadata.z_anc_ids + metadata.x_anc_ids)
    if ancilla_ids != set(metadata.edges_by_anc):
        raise ValueError("edges_by_anc keys must exactly match the ancilla IDs")
    if ancilla_ids != set(metadata.layers_by_anc):
        raise ValueError("layers_by_anc keys must exactly match the ancilla IDs")
    if any(
        len(metadata.layers_by_anc[ancilla]) != metadata.layer_count
        for ancilla in ancilla_ids
    ):
        raise ValueError("every ancilla must have exactly L scheduling layers")

    return metadata


def rebuild_circuit_from_meta(meta: BuildMetadata, p_noise: float) -> stim.Circuit:
    return build_circuit_per_stabilizer_index_layers(
        n=meta.n,
        data_lin=meta.data_lin,
        z_anc_ids=meta.z_anc_ids,
        x_anc_ids=meta.x_anc_ids,
        edges_by_anc=meta.edges_by_anc,
        layers_by_anc=meta.layers_by_anc,
        L=meta.layer_count,
        rounds=meta.rounds,
        p_noise=p_noise,
    )


def count_logical_errors(
    circuit: stim.Circuit,
    shots: int,
    *,
    seed: int | None = None,
) -> int:
    """Sample and decode shots, returning the number of logical failures."""
    dem = circuit.detector_error_model(
        decompose_errors=True,
        approximate_disjoint_errors=True,
    )
    if dem.num_observables == 0:
        raise ValueError("the circuit has no logical observables to decode")

    matcher = pm.Matching.from_detector_error_model(dem)
    sampler = (
        circuit.compile_detector_sampler(seed=seed)
        if seed is not None
        else circuit.compile_detector_sampler()
    )

    try:
        detections, observables = sampler.sample(
            shots,
            separate_observables=True,
        )
    except TypeError:
        # Compatibility with Stim versions lacking separate_observables.
        samples = sampler.sample(shots, append_observables=True)
        split = circuit.num_detectors
        detections = samples[:, :split]
        observables = samples[:, split : split + circuit.num_observables]

    predicted_observables = matcher.decode_batch(detections)
    if predicted_observables.ndim == 1:
        predicted_observables = predicted_observables.reshape(-1, 1)
    if observables.ndim == 1:
        observables = observables.reshape(-1, 1)
    if predicted_observables.shape != observables.shape:
        raise RuntimeError(
            "decoder output shape does not match sampled observables: "
            f"{predicted_observables.shape} != {observables.shape}"
        )

    failed = np.any(
        np.logical_xor(predicted_observables, observables),
        axis=1,
    )
    return int(np.count_nonzero(failed))


def _wilson_interval(errors: int, shots: int) -> tuple[float, float]:
    rate = errors / shots
    z_squared = WILSON_95_Z**2
    if errors == 0:
        return 0.0, z_squared / (shots + z_squared)
    if errors == shots:
        return shots / (shots + z_squared), 1.0

    denominator = 1 + z_squared / shots
    center = (rate + z_squared / (2 * shots)) / denominator
    margin = (
        WILSON_95_Z
        * math.sqrt(rate * (1 - rate) / shots + z_squared / (4 * shots**2))
        / denominator
    )
    return max(0.0, center - margin), min(1.0, center + margin)


def run_experiments(
    meta: BuildMetadata,
    probabilities: Sequence[float],
    shots: int,
    seed: int | None,
) -> list[DecodeResult]:
    seed_generator = np.random.default_rng(seed) if seed is not None else None
    results: list[DecodeResult] = []

    for probability in probabilities:
        sample_seed = (
            int(seed_generator.integers(0, np.iinfo(np.int64).max))
            if seed_generator is not None
            else None
        )
        circuit = rebuild_circuit_from_meta(meta, p_noise=probability)
        errors = count_logical_errors(circuit, shots, seed=sample_seed)
        rate = errors / shots
        ci_low, ci_high = _wilson_interval(errors, shots)
        result = DecodeResult(
            p=probability,
            shots=shots,
            errors=errors,
            ler_per_shot=rate,
            ci95_low=ci_low,
            ci95_high=ci_high,
            sample_seed=sample_seed,
        )
        results.append(result)
        print(
            f"n={meta.n}, p={probability:.6f}, logical_error_rate={rate:.6e}, "
            f"95% CI=[{ci_low:.6e}, {ci_high:.6e}]"
        )

    return results


def save_metrics(results: Sequence[DecodeResult], output_dir: Path) -> tuple[Path, Path]:
    json_path = output_dir / "metrics.json"
    csv_path = output_dir / "metrics.csv"
    field_names = list(DecodeResult.__dataclass_fields__)

    with json_path.open("w", encoding="utf-8") as file:
        json.dump([asdict(result) for result in results], file, indent=2)
        file.write("\n")

    with csv_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=field_names)
        writer.writeheader()
        writer.writerows(asdict(result) for result in results)

    return json_path, csv_path


def plot_results(
    results: Sequence[DecodeResult],
    output_path: Path,
    *,
    code_size: int,
) -> None:
    positive_results = [result for result in results if result.ler_per_shot > 0]

    fig, ax = plt.subplots(figsize=(6, 4))
    if positive_results:
        xs = np.array([result.p for result in positive_results])
        ys = np.array([result.ler_per_shot for result in positive_results])
        lower_errors = ys - np.array([result.ci95_low for result in positive_results])
        upper_errors = (
            np.array([result.ci95_high for result in positive_results]) - ys
        )
        ax.errorbar(
            xs,
            ys,
            yerr=np.vstack((lower_errors, upper_errors)),
            marker="o",
            capsize=3,
            label=f"n={code_size} (95% CI)",
        )
        ax.legend()
    else:
        ax.text(
            0.5,
            0.5,
            "No logical failures observed",
            ha="center",
            va="center",
            transform=ax.transAxes,
        )

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.grid(which="both", linestyle=":")
    ax.set_title("Logical Error vs Physical Error")
    ax.set_xlabel("Physical Error Rate p")
    ax.set_ylabel("Logical Error Rate per shot")
    fig.tight_layout()
    fig.savefig(output_path, dpi=200)
    plt.close(fig)


def main(argv: List[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Rebuild a circuit from build_meta.json and decode it with "
            "Stim and PyMatching across physical error rates."
        )
    )
    parser.add_argument("--meta", required=True, type=Path, help="Path to build_meta.json")
    parser.add_argument("--out", required=True, type=Path, help="Output directory")
    parser.add_argument(
        "--shots",
        type=positive_int,
        default=200_000,
        help="Positive number of shots per physical error rate (default: 200000)",
    )
    parser.add_argument(
        "--plist",
        type=parse_probabilities,
        default=parse_probabilities(DEFAULT_PROBABILITIES),
        help=f"Comma-separated probabilities (default: {DEFAULT_PROBABILITIES})",
    )
    parser.add_argument(
        "--seed",
        type=nonnegative_int,
        default=None,
        help="Optional seed for reproducible sampling",
    )
    args = parser.parse_args(argv)

    try:
        metadata = load_metadata(args.meta)
    except ValueError as exc:
        parser.error(str(exc))

    args.out.mkdir(parents=True, exist_ok=True)
    print()
    results = run_experiments(metadata, args.plist, args.shots, args.seed)
    json_path, csv_path = save_metrics(results, args.out)
    plot_path = args.out / "plot.png"
    plot_results(results, plot_path, code_size=metadata.n)

    print(f"\nWrote: {json_path}\n       {csv_path}\n       {plot_path}")


if __name__ == "__main__":
    main()

