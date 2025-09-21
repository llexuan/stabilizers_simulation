import re
from typing import Dict, List, Tuple


def default_layers_for_support(support: List[int], L: int) -> List[List[int]]:
    """Round-robin split of support across L layers."""
    sup_sorted = sorted(support)
    layers: List[List[int]] = [[] for _ in range(L)]
    for i, idx in enumerate(sup_sorted):
        layers[i % L].append(idx)
    return layers


def collect_per_stab_cnot_layers_by_indices(
    z_anc_ids: List[int],
    x_anc_ids: List[int],
    edges_by_anc: Dict[int, List[int]],
) -> Tuple[int, Dict[int, List[List[int]]]]:
    """Interactive layer assignment.

    User first sets a global L, then for each stabilizer provides ONE layer number
    per support index (in the **same order shown**). Each number is in [1..L].

    Example (L=4, support [0,1,3,4]): "4,2,3,1"
    """
    print("Enter number of CNOT layers per round L (default 4): ", end="")
    try:
        sL = input().strip()
    except EOFError:
        sL = ""
    L = 4 if sL == "" else max(1, int(sL))
    print(f"Using L = {L} layer(s).\n")

    layers_by_anc: Dict[int, List[List[int]]] = {}
    label_id = 1

    def prompt_one(a: int, fam_label: str):
        nonlocal label_id
        support = sorted(set(edges_by_anc[a]))
        default_assign = [((i % L) + 1) for i in range(len(support))]
        default_str = ",".join(map(str, default_assign))

        print(f"{fam_label} stabilizer S{label_id}: support indices {support}")
        print(f"Enter layer numbers 1..{L} for each support index, in the SAME ORDER, comma-separated.")
        print(f"(Press Enter for default: {default_str})")
        try:
            s = input().strip()
        except EOFError:
            s = ""

        if s == "":
            assign = default_assign
        else:
            parts = [p.strip() for p in s.split(",") if p.strip() != ""]
            ok = True
            if len(parts) != len(support):
                ok = False
            else:
                try:
                    nums = [int(p) for p in parts]
                    if not all(1 <= v <= L for v in nums):
                        ok = False
                except ValueError:
                    ok = False
            if not ok:
                print("  ! Invalid entry. Using default.\n")
                assign = default_assign
            else:
                assign = nums

        layers = [[] for _ in range(L)]
        for idx, layer_num in zip(support, assign):
            layers[layer_num - 1].append(idx)

        layers_by_anc[a] = layers
        label_id += 1
        print()

    for a in z_anc_ids:
        prompt_one(a, "Z")
    for a in x_anc_ids:
        prompt_one(a, "X")

    return L, layers_by_anc
