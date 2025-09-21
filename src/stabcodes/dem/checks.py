from typing import List, Tuple


def find_anticommuting_pairs(
    z_sets: List[Tuple[int, ...]],
    x_sets: List[Tuple[int, ...]],
) -> List[Tuple[int, int]]:
    """Return pairs (zi, xi) where Z_i and X_i anticommute (odd overlap)."""
    bad = []
    for zi, ZS in enumerate(z_sets):
        sZ = set(ZS)
        for xi, XS in enumerate(x_sets):
            if len(sZ & set(XS)) % 2 == 1:
                bad.append((zi, xi))
    return bad
