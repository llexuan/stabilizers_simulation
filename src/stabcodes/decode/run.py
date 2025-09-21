import argparse
import json
import os
from typing import Dict, List, Tuple

import numpy as np
import matplotlib.pyplot as plt
import stim
import pymatching as pm

from stabcodes.build.circuit import build_circuit_per_stabilizer_index_layers


def _ensure_dir(p: str):
    os.makedirs(p, exist_ok=True)


def _int_keys(d: Dict[str, List[int]]) -> Dict[int, List[int]]:
    return {int(k): list(map(int, v)) for k, v in d.items()}


def _int_layers_by_anc(d: Dict[str, List[List[int]]]) -> Dict[int, List[List[int]]]:
    out: Dict[int, List[List[int]]] = {}
    for k, layers in d.items():
        out[int(k)] = [list(map(int, layer)) for layer in layers]
    return out


def rebuild_circuit_from_meta(meta: Dict, p_noise: float) -> stim.Circuit:
    n = int(meta["n"])
    rounds = int(meta["rounds"])
    L = int(meta["L"])
    data_lin = list(map(int, meta["data_lin"]))
    z_anc_ids = list(map(int, meta["z_anc_ids"]))
    x_anc_ids = list(map(int, meta["x_anc_ids"]))
    edges_by_anc = _int_keys(meta["edges_by_anc"])
    layers_by_anc = _int_layers_by_anc(meta["layers_by_anc"])

    # Rebuild with the requested physical noise p
    circ = build_circuit_per_stabilizer_index_layers(
        n=n,
        data_lin=data_lin,
        z_anc_ids=z_anc_ids,
        x_anc_ids=x_anc_ids,
        edges_by_anc=edges_by_anc,
        layers_by_anc=layers_by_anc,
        L=L,
        rounds=rounds,
        p_noise=p_noise,   # <-- important: vary p here
    )
    return circ


def decode_rate_with_pm(circ: stim.Circuit, shots: int) -> Tuple[int, int]:
    """Return (errors, shots) using Stim+PyMatching directly.

    We:
      1) build DEM from the circuit,
      2) build a matcher from the DEM,
      3) sample detection events + observables,
      4) decode to predicted observables,
      5) count logical failures (predicted != actual).
    """
    # 1) DEM
    dem = circ.detector_error_model(
        decompose_errors=True,
        approximate_disjoint_errors=True,
    )

    # 2) Matcher
    matcher = pm.Matching.from_detector_error_model(dem)

    # 3) Sample dets + obs
    sampler = circ.compile_detector_sampler()
    try:
        dets, obs = sampler.sample(shots, separate_observables=True)
    except TypeError:
        # Older stim: returns a single array with dets then obs appended.
        arr = sampler.sample(shots)
        # Try to learn sizes from DEM.
        try:
            num_dets = dem.num_detectors  # stim>=1.11
            num_obs = dem.num_observables
        except AttributeError:
            # Fallback: estimate from circuit sampler shape (last cols are obs).
            # This branch should rarely be needed; keeping as safety.
            # Assume there is at least 1 observable (your builder adds one).
            num_dets = arr.shape[1] - 1
            num_obs = 1
        dets = arr[:, :num_dets].astype(np.uint8, copy=False)
        obs = arr[:, num_dets:num_dets + num_obs].astype(np.uint8, copy=False)

    # 4) Decode. PyMatching returns predicted observables parity (shots x num_obs).
    pred_obs = matcher.decode_batch(dets)

    # Normalize shapes to (shots, num_obs)
    if pred_obs.ndim == 1:
        pred_obs = pred_obs.reshape(-1, 1)
    if obs.ndim == 1:
        obs = obs.reshape(-1, 1)

    # 5) Count logical failures: any observable bit wrong.
    wrong = np.any((pred_obs ^ obs).astype(bool), axis=1)
    errors = int(np.count_nonzero(wrong))
    return errors, shots


def main(argv: List[str] | None = None):
    ap = argparse.ArgumentParser(
        description="Rebuild circuit per p from build_meta.json, then Stim+PyMatching decode."
    )
    ap.add_argument("--meta", required=True, help="Path to build_meta.json")
    ap.add_argument("--out", required=True, help="Output dir (metrics, plot)")
    ap.add_argument("--shots", type=int, default=200_000, help="Shots per p")
    ap.add_argument(
        "--plist",
        type=str,
        default="0.001,0.003,0.005,0.007,0.009",
        help="Comma-separated p values to test",
    )
    args = ap.parse_args(argv)

    _ensure_dir(args.out)

    with open(args.meta, "r") as f:
        meta = json.load(f)

    p_list = [float(x) for x in args.plist.split(",") if x.strip()]

    # Run per p
    results: List[Tuple[float, int, int]] = []  # (p, errors, shots)
    print()
    for p in p_list:
        circ = rebuild_circuit_from_meta(meta, p_noise=p)
        errors, shots = decode_rate_with_pm(circ, shots=args.shots)
        ler = errors / shots
        # Your preferred print style (these are "error per shot"):
        print(f"d=3, p={p:0.6f}, error={ler:0.6e}")
        results.append((p, errors, shots))

    # Save metrics
    import csv
    metrics_path_json = os.path.join(args.out, "metrics.json")
    metrics_path_csv = os.path.join(args.out, "metrics.csv")
    plot_path = os.path.join(args.out, "plot.png")

    payload = [
        {"p": p, "shots": shots, "errors": errors, "ler_per_shot": errors / shots}
        for p, errors, shots in results
    ]
    with open(metrics_path_json, "w") as f:
        json.dump(payload, f, indent=2)

    with open(metrics_path_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["p", "shots", "errors", "ler_per_shot"])
        for p, errors, shots in results:
            w.writerow([p, shots, errors, errors / shots])

    # Plot
    xs = np.array([p for p, _, _ in results])
    ys = np.array([e / s for _, e, s in results])
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(xs, ys, marker="o", label="n=9")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.grid(which="both", ls=":")
    ax.set_title("Logical Error vs Physical Error")
    ax.set_xlabel("Physical Error Rate p")
    ax.set_ylabel("Logical Error Rate / shot")
    ax.legend()
    fig.tight_layout()
    fig.savefig(plot_path, dpi=200)

    print(f"\nWrote: {metrics_path_json}\n       {metrics_path_csv}\n       {plot_path}")


if __name__ == "__main__":
    main()

