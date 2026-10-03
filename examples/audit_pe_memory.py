"""Replay the PPL PE_order=0 scratch-page writes for a boundary case.

This is a source arithmetic audit, not an assertion about scanner-language
overflow. It compares the PPL's declared disjoint arrays with the actual shared
word page and preserves the execution order of the writes and reads.
"""

import json
from pathlib import Path


def replay(no_views=1024, views_per_seg=512, te=36, esp=36):
    # PPL selects this legacy order only with diff_on=0; te_eff=scale(te,1,esp).
    te_eff = te // esp
    assert 1 <= views_per_seg <= no_views
    assert no_views % (2 * views_per_seg) == 0
    assert esp != 0 and te_eff <= views_per_seg
    views_per_echo = no_views // (2 * views_per_seg)
    view_shift = 0  # PF_echoes PARAMLIST value 0 is auto-filled to ETL.

    # Absolute offsets from PPL: CENOFFSET=0, LOCOFFSET=512,
    # GPOFFSET=1024. Simulate pw() words, retaining exact write order.
    mem = {}
    writes = []

    def put(region, idx, addr, value):
        old = mem.get(addr)
        mem[addr] = value
        writes.append({"region": region, "index": idx, "address": addr,
                       "value": value, "overwrote": old})

    def get(region, idx, addr):
        return mem.get(addr, 0)

    # PPL:987-1011, one-based array_count; both center halves are populated.
    for i in range(1, views_per_seg + 1):
        v = (i - te_eff) * views_per_echo - 1
        if v < (-no_views / 2) - view_shift:
            v += no_views
        if v >= (no_views / 2) - view_shift:
            v -= no_views
        put("centre_first", i, i, v)
        v = (1 - te_eff - i) * views_per_echo - 1
        if v < (-no_views / 2) - view_shift:
            v += no_views
        if v >= (no_views / 2) - view_shift:
            v -= no_views
        idx = i + views_per_seg
        put("centre_second", idx, idx, v)

    # PPL:1013-1026. This table starts at index 1, so the word at address 512
    # is unused by echo_location; its writes begin at address 513.
    for i in range(1, views_per_echo + 1):
        loc = views_per_echo // 2 - i + 1
        put("location_first", i, 512 + i, loc)
        put("location_second", i + views_per_echo, 512 + i + views_per_echo, loc)

    shared_order = []
    isolated_order = []
    array_count = 0
    for gp_loc in range(1, 2 * views_per_echo + 1):
        gp_store = views_per_seg if gp_loc > views_per_echo else 0
        for gp_cnt in range(1, views_per_seg + 1):
            centre_idx = gp_cnt + gp_store
            centre_addr = centre_idx  # CENOFFSET + index
            loc_addr = 512 + gp_loc
            shared = get("centre", centre_idx, centre_addr) + get("location", gp_loc, loc_addr)
            isolated = (mem.get(centre_addr, 0) if centre_idx <= 512 else
                        next(w["value"] for w in writes
                             if w["region"] == "centre_second" and w["index"] == centre_idx))
            isolated += next(w["value"] for w in writes
                             if w["region"] in ("location_first", "location_second")
                             and w["index"] == gp_loc)
            if shared < (-no_views / 2) - view_shift:
                shared += no_views
            if shared >= (no_views / 2) - view_shift:
                shared -= no_views
            if isolated < (-no_views / 2) - view_shift:
                isolated += no_views
            if isolated >= (no_views / 2) - view_shift:
                isolated -= no_views
            shared_order.append(shared)
            isolated_order.append(isolated)
            # PPL:1049-1051 put_gp_order(array_count), then increment.
            put("gp_order", array_count, 1024 + array_count, shared)
            array_count += 1

    mismatches = [{"output_index": i, "shared_word_value": a, "isolated_array_value": b}
                  for i, (a, b) in enumerate(zip(shared_order, isolated_order)) if a != b]
    return {
        "parameters": {"diff_on": 0, "PE_order": 0, "no_views": no_views,
                        "views_per_seg": views_per_seg, "te_ms": te, "esp_ms": esp,
                        "tr_ms": 30000, "no_slices": 1,
                        "PF_echoes": 0, "effective_te": te_eff,
                        "views_per_echo": views_per_echo},
        "checks": {"views_in_range": True, "ETL_in_range": True,
                    "divisibility_no_views_over_2ETL": True,
                    "PF_echoes_auto_default_is_ETL": True,
                    "PE_order_allowed_when_diffusion_off": True,
                    "te_eff_le_ETL": True},
        "ppl_source_lines": {"layout_and_offsets": "263-280",
                             "view_and_ETL_validation": "788-791",
                             "diffusion_off_selects_te_eff": "803-811",
                             "PF_auto_default_and_check": "867-877",
                             "PE0_divisibility_check": "949-956",
                             "center_writes": "987-1011",
                             "location_writes": "1013-1026",
                             "shared_center_location_reads_and_gp_writes": "1030-1055"},
        "layout": {"centre_reserved": "addresses 0..511",
                   "location_reserved": "addresses 512..1023",
                   "gp_reserved": "addresses 1024..2047",
                   "last_second_centre_index": 2 * views_per_seg,
                   "last_second_centre_address": 2 * views_per_seg,
                   "location_writes": [w for w in writes if w["region"].startswith("location")],
                   "first_gp_write": next(w for w in writes if w["region"] == "gp_order"),
                   "address_1024_center_before_gp_write": next(
                       w["value"] for w in writes if w["region"] == "centre_second"
                       and w["address"] == 1024)},
        "shared_order": shared_order,
        "isolated_order": isolated_order,
        "mismatch_count": len(mismatches),
        "first_mismatches": mismatches[:8],
    }


def main():
    result = replay()
    assert result["mismatch_count"] > 0
    out = Path(__file__).resolve().parent.parent / "runs" / "improve_pe_memory.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"evidence": str(out), "mismatch_count": result["mismatch_count"],
                      "first_mismatches": result["first_mismatches"]}, indent=2))


if __name__ == "__main__":
    main()
