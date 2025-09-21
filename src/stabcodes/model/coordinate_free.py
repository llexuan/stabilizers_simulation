from collections import defaultdict
from typing import Dict, List, Tuple


def make_coordinate_free_model(
    n: int,
    z_sets: List[Tuple[int, ...]],
    x_sets: List[Tuple[int, ...]],
):
    """Assign one ancilla per stabilizer; no geometry/coords assumed.

    Returns:
        data_lin:      [0..n-1]
        z_anc_ids:     list of ancilla ids for Z checks (start at n)
        x_anc_ids:     list of ancilla ids for X checks (after Z ancillas)
        edges_by_anc:  dict[ancilla_id] -> list of data indices in its support
    """
    data_lin = list(range(n))
    edges_by_anc: Dict[int, List[int]] = defaultdict(list)

    z_anc_ids: List[int] = []
    x_anc_ids: List[int] = []

    next_aid = n
    for S in z_sets:
        aid = next_aid
        next_aid += 1
        z_anc_ids.append(aid)
        edges_by_anc[aid] = list(S)
    for S in x_sets:
        aid = next_aid
        next_aid += 1
        x_anc_ids.append(aid)
        edges_by_anc[aid] = list(S)

    return data_lin, z_anc_ids, x_anc_ids, edges_by_anc
