import re
import sys
from typing import List, Tuple


def parse_stabilizers() -> Tuple[List[str], List[str]]:
    """Interactive parser for a block of stabilizers.

    Accepts either:
      1) Pauli-grid rows consisting of only 'Z'/'X'/'I' (one row per stabilizer)
         - Each row must be pure-X or pure-Z (no mixing X and Z in the same row).
      2) Sparse list format like "Z0 Z1 Z4" or "X2 X7 X9".
         - One stabilizer per line.
    Finish input with an empty line.
    """
    print("Paste stabilizers (single block). Either Pauli grid (Z/X/I) OR 'Zk ...' / 'Xk ...' lines.")
    print("Finish with an empty line.\n")

    rows_raw: List[str] = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line is None:
            break
        s = (line or "").strip().upper()
        if s == "":
            break
        rows_raw.append(s)

    if not rows_raw:
        print("Error: expected at least one line of stabilizers.", file=sys.stderr)
        sys.exit(1)

    is_pauli_grid = all(re.fullmatch(r'[ZXI]+', r) is not None for r in rows_raw)
    is_stab_list = all(re.fullmatch(r'(?:[ZX]\d+(?:[ ,]+\s*[ZX]\d+)*)', r) is not None for r in rows_raw)

    if not (is_pauli_grid or is_stab_list):
        print("Error: input must be either all Pauli rows or all 'Zk/Xk' lines.", file=sys.stderr)
        sys.exit(1)

    if is_pauli_grid:
        n = len(rows_raw[0])
        if any(len(r) != n for r in rows_raw):
            print("Error: all Pauli rows must have same length.", file=sys.stderr)
            sys.exit(1)

        Z_rows: List[str] = []
        X_rows: List[str] = []
        for r in rows_raw:
            chars = set(r)
            only_ZI = chars.issubset({'Z', 'I'})
            only_XI = chars.issubset({'X', 'I'})
            if only_ZI and not only_XI:
                Z_rows.append(r)
            elif only_XI and not only_ZI:
                X_rows.append(r)
            elif chars == {'I'}:
                pass  # ignore all-I rows
            else:
                print("Error: a row mixes X and Z; each row must be purely X or purely Z.", file=sys.stderr)
                sys.exit(1)
        if not Z_rows and not X_rows:
            print("Error: need at least one Z or X stabilizer.", file=sys.stderr)
            sys.exit(1)
        return Z_rows, X_rows

    # sparse 'Zk/Xk' format
    all_indices: List[int] = []
    parsed_lines: List[List[Tuple[str, int]]] = []
    for r in rows_raw:
        toks = re.findall(r'([ZX])(\d+)', r)
        if not toks:
            print(f"Error: couldn't parse stabilizer line: {r}", file=sys.stderr)
            sys.exit(1)
        fams = {p for p, _ in toks}
        if len(fams) != 1:
            print(f"Error: line mixes X and Z: {r}", file=sys.stderr)
            sys.exit(1)
        items = [(p, int(k)) for p, k in toks]
        parsed_lines.append(items)
        all_indices.extend(k for _, k in items)

    def make_row(letter: str, idxs: List[int]) -> str:
        N = max(all_indices) + 1 if all_indices else 0
        arr = ['I'] * N
        for k in idxs:
            if k < 0:
                print(f"Error: negative index {k}", file=sys.stderr)
                sys.exit(1)
            arr[k] = letter
        return ''.join(arr)

    Z_rows: List[str] = []
    X_rows: List[str] = []
    for items in parsed_lines:
        fam = items[0][0]
        idxs = sorted(k for _, k in items)
        row = make_row(fam, idxs)
        (Z_rows if fam == 'Z' else X_rows).append(row)
    if not Z_rows and not X_rows:
        print("Error: need at least one Z or X stabilizer.", file=sys.stderr)
        sys.exit(1)
    return Z_rows, X_rows


def rows_to_index_sets(rows: List[str], symbol: str) -> List[Tuple[int, ...]]:
    """Convert Pauli rows back into tuples of indices where `symbol` appears."""
    out: List[Tuple[int, ...]] = []
    for r in rows:
        idxs = tuple(i for i, ch in enumerate(r) if ch == symbol)
        if idxs:
            out.append(tuple(sorted(set(idxs))))
    return out
