# src/stabcodes/cli/build.py
from __future__ import annotations

import argparse
import json
import os
from typing import Dict, List, Tuple

import stim

from ..io.parse import parse_stabilizers, rows_to_index_sets
from ..model.coordinate_free import make_coordinate_free_model
from ..schedule.layers import collect_per_stab_cnot_layers_by_indices
from ..build.circuit import build_circuit_per_stabilizer_index_layers
from ..dem.checks import find_anticommuting_pairs


def _ensure_dir(p: str) -> None:
    os.makedirs(p, exist_ok=True)


def _layers_family_from_anc_order(
    z_anc_ids: List[int],
    x_anc_ids: List[int],
    layers_by_anc: Dict[int, List[List[int]]],
) -> Dict[str, List[List[List[int]]]]:
    """Return {'Z': [layers_for_Z1, ...], 'X': [...]} preserving input order."""
    return {
        "Z": [layers_by_anc[a] for a in z_anc_ids],
        "X": [layers_by_anc[a] for a in x_anc_ids],
    }


def main(argv: List[str] | None = None) -> None:
    ap = argparse.ArgumentParser(
        description="Build a coordinate-free CSS circuit + DEM from pasted stabilizers."
    )
    ap.add_argument(
        "--out",
        default="results/run",
        help="Output directory to write circuit.stim, dem.txt, build_meta.json",
    )
    ap.add_argument(
        "--p-noise",
        type=float,
        default=None,
        help="Override depolarizing probability for this build (only affects the preview circuit here).",
    )
    args = ap.parse_args(argv)

    # 1) Parse stabilizers (interactive)
    Z_rows, X_rows = parse_stabilizers()
    z_sets = rows_to_index_sets(Z_rows, "Z")
    x_sets = rows_to_index_sets(X_rows, "X")
    if not z_sets and not x_sets:
        print("Error: need at least one Z or X stabilizer.")
        return

    n_candidates: List[int] = []
    if Z_rows:
        n_candidates.append(len(Z_rows[0]))
    if X_rows:
        n_candidates.append(len(X_rows[0]))
    if any(len(r) != n_candidates[0] for r in Z_rows + X_rows):
        print("Error: mixed row lengths between Z and X families.")
        return
    n = n_candidates[0]

    # 2) Model
    data_lin, z_anc_ids, x_anc_ids, edges_by_anc = make_coordinate_free_model(
        n, z_sets, x_sets
    )

    # 3) Rounds
    print("Enter number of rounds R (default 1): ", end="")
    try:
        sR = input().strip()
    except EOFError:
        sR = ""
    rounds = 1 if sR == "" else max(1, int(sR))

    # 4) Layer assignment (interactive)
    L, layers_by_anc = collect_per_stab_cnot_layers_by_indices(
        z_anc_ids, x_anc_ids, edges_by_anc
    )

    # 5) Circuit (preview at this single p if --p-noise was given)
    circ = build_circuit_per_stabilizer_index_layers(
        n,
        data_lin,
        z_anc_ids,
        x_anc_ids,
        edges_by_anc,
        layers_by_anc=layers_by_anc,
        L=L,
        rounds=rounds,
        p_noise=args.p_noise if args.p_noise is not None else None,
    )

    print("\nConstructed circuit:\n")
    print(circ)

    # 6) DEM (best-effort)
    dem_ok = True
    try:
        dem = circ.detector_error_model(
            decompose_errors=True, approximate_disjoint_errors=True
        )
        print("\nDetector Error Model (DEM):\n")
        print(dem)
    except Exception as e:
        dem_ok = False
        print("\n[DEM] Failed to construct a detector error model.")
        print(f"Reason: {e}")
        bad_pairs = find_anticommuting_pairs(z_sets, x_sets)
        if bad_pairs:
            print(
                f"Likely cause: X/Z sets anticommute (odd overlap). "
                f"Found {len(bad_pairs)} pair(s)."
            )
        else:
            print(
                "Could also be due to non-deterministic detectors or unsupported "
                "measurement basis for space-like checks."
            )

    # 7) Write outputs
    out_dir = args.out
    _ensure_dir(out_dir)

    with open(os.path.join(out_dir, "circuit.stim"), "w") as f:
        f.write(str(circ))

    if dem_ok:
        with open(os.path.join(out_dir, "dem.txt"), "w") as f:
            f.write(str(dem))

    # Build meta so decode can rebuild circuits across different p values (the decoder
    # chooses its own p_list; it doesn’t need p_list embedded here).
    meta = {
        "n": n,
        "rounds": rounds,
        "L": L,
        "data_lin": list(data_lin),
        "z_anc_ids": list(z_anc_ids),
        "x_anc_ids": list(x_anc_ids),
        "edges_by_anc": {str(k): list(v) for k, v in edges_by_anc.items()},
        "layers_by_anc": {
            str(k): [list(layer) for layer in layers_by_anc[k]] for k in layers_by_anc
        },
        "z_sets": [list(t) for t in z_sets],
        "x_sets": [list(t) for t in x_sets],
        # Optional: paths, purely informative for humans:
        "stim_path": os.path.join(out_dir, "circuit.stim"),
        "dem_path": os.path.join(out_dir, "dem.txt") if dem_ok else None,
    }
    with open(os.path.join(out_dir, "build_meta.json"), "w") as f:
        json.dump(meta, f, indent=2)

    print(f"\nWrote files into: {out_dir}")
    print("  - circuit.stim")
    if dem_ok:
        print("  - dem.txt")
    print("  - build_meta.json")


if __name__ == "__main__":
    main()
