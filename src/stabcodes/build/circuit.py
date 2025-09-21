from typing import Dict, List, Optional
import stim

# If you keep a module-level default noise, we’ll respect it unless p_noise is passed.
try:
    P_NOISE  # type: ignore
except NameError:
    P_NOISE = 0.0  # safe default if not defined elsewhere


def build_circuit_per_stabilizer_index_layers(
    n: int,
    data_lin: List[int],
    z_anc_ids: List[int],
    x_anc_ids: List[int],
    edges_by_anc: Dict[int, List[int]],
    layers_by_anc: Dict[int, List[List[int]]],
    L: int,
    rounds: int = 1,
    p_noise: Optional[float] = None,
) -> stim.Circuit:
    """Serial-by-stabilizer schedule using L layers per ancilla (coordinate-free IDs).

    Option A behavior:
      * If ONLY Z stabilizers are present (and no X), the circuit prepares data in Z,
        ends with Z-basis data measurement, builds space-like detectors from Z-checks,
        and includes a Z-type logical observable. This avoids non-deterministic observables.
    """
    assert rounds >= 1 and L >= 1
    p = P_NOISE if p_noise is None else float(p_noise)

    # Qubit id layout in circuit: data first, then ancillas in deterministic order
    data_ids_print = list(sorted(data_lin))
    anc_all_print = z_anc_ids + x_anc_ids
    m_total = len(anc_all_print)

    def qid_of_data_lin(i: int) -> int: return i
    def qid_of_anc(a: int) -> int: return a

    circ = stim.Circuit()

    def _dep1(qs: List[int]):
        if p and qs:
            circ.append("DEPOLARIZE1", qs, [p])

    def _dep2(pairs_flat: List[int]):
        if p and pairs_flat:
            circ.append("DEPOLARIZE2", pairs_flat, [p])

    only_z = (len(z_anc_ids) > 0 and len(x_anc_ids) == 0)
    only_x = (len(x_anc_ids) > 0 and len(z_anc_ids) == 0)

    # Initial data prep (Option A: Z-only -> Z prep; otherwise X prep)
    if only_z and not only_x:
        circ.append("R", data_ids_print)
        if p: circ.append("X_ERROR", data_ids_print, [p])
    else:
        circ.append("RX", data_ids_print)
        if p: circ.append("Z_ERROR", data_ids_print, [p])

    # Ancilla prep
    circ.append("R", anc_all_print)
    if p: circ.append("X_ERROR", anc_all_print, [p])

    x_ids_print = list(x_anc_ids)

    for r in range(rounds):
        circ.append("TICK")
        _dep1(data_ids_print)

        # Pre-H on X ancillas
        if x_ids_print:
            circ.append("H", x_ids_print)
            _dep1(x_ids_print)
        circ.append("TICK")

        # ----- X stabilizers (anc -> data), in L layers -----
        for a in x_anc_ids:
            a_layers = layers_by_anc.get(a)
            if not a_layers or len(a_layers) != L:
                sup = sorted(set(edges_by_anc[a]))
                # simple round-robin default
                a_layers = [[] for _ in range(L)]
                for i, idx in enumerate(sup):
                    a_layers[i % L].append(idx)
            for layer in a_layers:
                tgt: List[int] = []
                for lin in layer:
                    tgt += [qid_of_anc(a), qid_of_data_lin(lin)]
                if tgt:
                    circ.append("CX", tgt)
                    _dep2(tgt)
                circ.append("TICK")

        # ----- Z stabilizers (data -> anc), in L layers -----
        for a in z_anc_ids:
            a_layers = layers_by_anc.get(a)
            if not a_layers or len(a_layers) != L:
                sup = sorted(set(edges_by_anc[a]))
                a_layers = [[] for _ in range(L)]
                for i, idx in enumerate(sup):
                    a_layers[i % L].append(idx)
            for layer in a_layers:
                tgt: List[int] = []
                for lin in layer:
                    tgt += [qid_of_data_lin(lin), qid_of_anc(a)]
                if tgt:
                    circ.append("CX", tgt)
                    _dep2(tgt)
                circ.append("TICK")

        # Post-H on X ancillas
        if x_ids_print:
            circ.append("H", x_ids_print)
            _dep1(x_ids_print)
        circ.append("TICK")

        # Measure ancillas (time-like detectors only for X ancillas)
        if p: circ.append("X_ERROR", anc_all_print, [p])
        circ.append("MR", anc_all_print)
        if p: circ.append("X_ERROR", anc_all_print, [p])

        # Time-like detectors (X ancillas only)
        for aq in x_ids_print:
            j = anc_all_print.index(aq)
            back_curr = -(m_total - j)
            if r == 0:
                circ.append("DETECTOR", [stim.target_rec(back_curr)])
            else:
                back_prev = -(m_total + (m_total - j))
                circ.append("DETECTOR", [stim.target_rec(back_curr), stim.target_rec(back_prev)])

    # -------- Final data measurement & space-like detectors / logical --------
    def _rec_pos_after_meas(qs_measured: List[int]) -> Dict[int, int]:
        return {q: i for i, q in enumerate(qs_measured)}

    if only_x and not only_z:
        # X-only: finish with MX and X logical
        if p: circ.append("Z_ERROR", data_ids_print, [p])
        circ.append("MX", data_ids_print)
        mx_pos = _rec_pos_after_meas(data_ids_print)

        # space-like closures using X supports
        for a in x_anc_ids:
            support_qs = [q for q in sorted(set(edges_by_anc[a])) if q in mx_pos]
            if len(support_qs) < 2:
                continue
            j = anc_all_print.index(a)
            anc_back = -(len(data_ids_print) + (m_total - j))
            terms = [stim.target_rec(-(len(data_ids_print) - mx_pos[q])) for q in support_qs]
            terms.append(stim.target_rec(anc_back))
            circ.append("DETECTOR", terms)

        # logical: product of MX over all data (simple default)
        if data_ids_print:
            obs_terms = [stim.target_rec(-(len(data_ids_print) - mx_pos[q])) for q in data_ids_print]
            circ.append("OBSERVABLE_INCLUDE", obs_terms, [0])

    elif only_z and not only_x:
        # Z-only (Option A): finish with M (Z-basis) and Z logical
        if p: circ.append("X_ERROR", data_ids_print, [p])
        circ.append("M", data_ids_print)
        mz_pos = _rec_pos_after_meas(data_ids_print)

        # space-like closures using Z supports
        for a in z_anc_ids:
            support_qs = [q for q in sorted(set(edges_by_anc[a])) if q in mz_pos]
            if len(support_qs) < 2:
                continue
            j = anc_all_print.index(a)
            anc_back = -(len(data_ids_print) + (m_total - j))
            terms = [stim.target_rec(-(len(data_ids_print) - mz_pos[q])) for q in support_qs]
            terms.append(stim.target_rec(anc_back))
            circ.append("DETECTOR", terms)

        # logical: product of MZ over all data (simple default)
        if data_ids_print:
            obs_terms = [stim.target_rec(-(len(data_ids_print) - mz_pos[q])) for q in data_ids_print]
            circ.append("OBSERVABLE_INCLUDE", obs_terms, [0])

    else:
        # Both families present: finish with MX and close using X supports
        if p: circ.append("Z_ERROR", data_ids_print, [p])
        circ.append("MX", data_ids_print)
        mx_pos = _rec_pos_after_meas(data_ids_print)

        for a in x_anc_ids:
            support_qs = [q for q in sorted(set(edges_by_anc[a])) if q in mx_pos]
            if len(support_qs) < 2:
                continue
            j = anc_all_print.index(a)
            anc_back = -(len(data_ids_print) + (m_total - j))
            terms = [stim.target_rec(-(len(data_ids_print) - mx_pos[q])) for q in support_qs]
            terms.append(stim.target_rec(anc_back))
            circ.append("DETECTOR", terms)

        if data_ids_print:
            obs_terms = [stim.target_rec(-(len(data_ids_print) - mx_pos[q])) for q in data_ids_print]
            circ.append("OBSERVABLE_INCLUDE", obs_terms, [0])

    return circ


