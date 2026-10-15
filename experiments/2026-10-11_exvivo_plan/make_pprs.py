"""Generate today's 35-mm-FOV rat-brain/PBS scanner qualification protocols.

Preserves the new scanner templates and acquired October 10 calibrations.
No existing PPL, PPR or raw acquisition is modified.
"""
from pathlib import Path
import csv
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
VERSIONS = {"v182": "1.82", "v1912": "1.912"}
AXES = [(1000, 0, 0), (-1000, 0, 0), (0, 1000, 0),
        (0, -1000, 0), (0, 0, 1000), (0, 0, -1000)]
X = AXES[0]
LOW = [(b, X) for b in (0, 5, 10, 20, 100, 1000, 6000)]
CAL = [(10, X)] + [(b, d) for b in (500, 1000) for d in AXES] + [(10, X)]
SHORT = [(b, X) for b in (10, 1000, 6000)]
PAIR = [(b, X) for b in (10, 1000)]
FINAL = [(10, X)] + [(b, d) for b in (1000, 3000, 6000) for d in (AXES[0], AXES[2], AXES[4])]


def test(letter, version, purpose, rows, **settings):
    return dict(letter=letter, version=version, purpose=purpose, rows=rows,
                priority="core", dwell_us=50, esp=14 if version == "v182" else 13,
                tr=1000, te=54, big_delta=40000, nav_on=1,
                offsets=[0], matrix=128, expected_rejection=None, **settings)


# Use update rather than duplicate keyword defaults when defining variants.
def variant(letter, version, purpose, rows, **settings):
    item = test(letter, version, purpose, rows)
    item.update(settings)
    return item


TESTS = [
    test("A", "v182", "Load/compile, low-b E1 diagnostic, tissue/PBS high-b baseline", LOW),
    test("B", "v1912", "Load/compile, matched ss-MGOT baseline and low-b/high-b diagnostic", LOW),
    test("C", "v182", "PBS ADC and axis calibration: +/-x,+/-y,+/-z at b500/b1000; bracketed reference", CAL),
    test("D", "v1912", "Matched ss-MGOT six-polarity PBS ADC/axis calibration", CAL),
    variant("E", "v182", "40-kHz minimum ESP, short-T2 benefit and high-b cleanliness", SHORT, dwell_us=25, esp=11),
    variant("F", "v1912", "40-kHz ss-MGOT minimum ESP and high-b cleanliness", SHORT, dwell_us=25, esp=10),
    variant("G", "v182", "40-kHz minimum ESP + 1 ms timing control", [(10, X)], dwell_us=25, esp=12),
    variant("H", "v1912", "40-kHz minimum ESP + 1 ms timing control", [(10, X)], dwell_us=25, esp=11),
    variant("I", "v182", "20-kHz minimum ESP + 1 ms timing control", [(10, X)], esp=15),
    variant("J", "v1912", "20-kHz minimum ESP + 1 ms timing control", [(10, X)], esp=14),
    variant("K", "v182", "K-style off-centre phase and tight-gap crosstalk with shot navigators", [(b, X) for b in (0, 10, 1000)], dwell_us=25, esp=11, nav_on=2, offsets=[-480, 0, 480]),
    variant("L", "v1912", "Minimum-spacing multi-slice ss-MGOT phase, crosstalk and shot navigators", [(b, X) for b in (0, 10, 1000)], dwell_us=25, esp=10, nav_on=2, offsets=[-1103, 0, 1103]),
    variant("M", "v182", "Single-slice nav2 control against E; crosstalk reference for K/O/S", PAIR, dwell_us=25, esp=11, nav_on=2),
    variant("N", "v1912", "Single-slice nav2 control against F; crosstalk reference for L/P", PAIR, dwell_us=25, esp=10, nav_on=2),
    variant("O", "v182", "Large off-centre RF phase at +/-5 mm", [(10, X)], dwell_us=25, esp=11, nav_on=2, offsets=[-2000, 0, 2000]),
    variant("P", "v1912", "Large off-centre per-width RF phase at +/-5 mm", [(10, X)], dwell_us=25, esp=10, nav_on=2, offsets=[-2000, 0, 2000]),
    variant("Q", "v182", "Delta30/TE44 tissue benefit and high-b gradient headroom with nav2", SHORT, dwell_us=25, esp=11, te=44, big_delta=30000, nav_on=2),
    variant("R", "v1912", "Matched Delta30/TE44 ss-MGOT tissue and navigator qualification", SHORT, dwell_us=25, esp=10, te=44, big_delta=30000, nav_on=2),
    variant("S", "v182", "2.4-mm gap crosstalk qualification before final pilot", [(10, X)], dwell_us=25, esp=11, nav_on=2, offsets=[-960, 0, 960]),
    test("T", "v182", "End-of-tests drift repeat against A (b10/b1000)", PAIR),
    test("U", "v1912", "End-of-tests drift repeat against B (b10/b1000)", PAIR),
    variant("V", "v182", "Final ex-vivo pilot: 256x256, 3 slices, 1 average, Delta30, 3 directions/shell", FINAL, dwell_us=25, esp=14, te=44, big_delta=30000, nav_on=2, offsets=[-960, 0, 960], matrix=256, tr=2000),
    variant("W", "v1912", "NO ACQUISITION: reject one console unit below the spacing bound", [(10, X)], dwell_us=25, esp=10, nav_on=2, offsets=[-1102, 0, 1102], priority="guard", expected_rejection="E148; minimum separation=1103 units"),
    variant("X", "v182", "NO ACQUISITION: reject ESP one ms below the 40-kHz minimum", [(10, X)], dwell_us=25, esp=10, priority="guard", expected_rejection="minimum esp=11 ms"),
    variant("Y", "v1912", "NO ACQUISITION: reject ESP one ms below the 40-kHz minimum", [(10, X)], dwell_us=25, esp=9, priority="guard", expected_rejection="E147; minimum ESP=10 ms"),
    variant("Z", "v1912", "Off-resonance follow-up: manually detune common TX/RX centre by -128 Hz", [(10, X)], dwell_us=25, esp=10, te=44, big_delta=30000, nav_on=2, priority="conditional", manual_centre_offset_hz=-128),
    variant("AA", "v1912", "Off-resonance follow-up: manually detune common TX/RX centre by +128 Hz", [(10, X)], dwell_us=25, esp=10, te=44, big_delta=30000, nav_on=2, priority="conditional", manual_centre_offset_hz=128),
    variant("AB", "v182", "Mixed-axis b1000 direction (577,577,577), for future non-axis direction sets", [(1000, (577, 577, 577))], dwell_us=25, esp=11),
    variant("AC", "v1912", "Matched mixed-axis b1000 direction, for future non-axis direction sets", [(1000, (577, 577, 577))], dwell_us=25, esp=10),
    variant("AD", "v182", "Alternative final pilot: 128x128; replaces V, same slices/shells/Delta/average count", FINAL, dwell_us=25, esp=11, te=44, big_delta=30000, nav_on=2, offsets=[-960, 0, 960], matrix=128, tr=2000, priority="alternative"),
]

RUN_ORDER = ["W", "X", "Y", "A", "B", "C", "D", "AB", "AC", "E", "F", "G", "H", "I", "J", "M", "N", "K", "L", "O", "P", "Q", "R", "Z", "AA", "S", "T", "U", "V", "AD"]


def replace_record(lines, name, value):
    hits = [i for i, line in enumerate(lines) if re.match(rf":\w+\s+{re.escape(name)}\s*,", line, re.I)]
    assert len(hits) == 1, (name, hits)
    parts = lines[hits[0]].split(",")
    parts[1] = " " + str(value)
    lines[hits[0]] = ",".join(parts)


def replace_array(lines, name, values, resize=False):
    hits = [i for i, line in enumerate(lines) if re.match(rf":\w+\s+{re.escape(name)}\s*,", line, re.I)]
    assert len(hits) == 1, name
    i = hits[0]
    n = len(values) if resize else int(lines[i].split(",")[1])
    assert len(values) <= n
    values = list(values) + [0] * (n-len(values))
    end = i+1
    while end < len(lines) and lines[end].startswith(","):
        end += 1
    head = lines[i].split(",")[0]
    # Match the scanner's acquired serialization: angles keep all elements
    # on continuation lines; offsets and diffusion arrays inline element 0.
    angle = name in ("r_angle_var", "p_angle_var", "s_angle_var")
    block = [f"{head}, {n}" if angle else f"{head}, {n}, {values[0]}"]
    block += [", " + ", ".join(map(str, values[j:j+8])) for j in range(0 if angle else 1, n, 8)]
    lines[i:end] = block


def replace_meta(lines, name, first, continuation=None):
    i = next(i for i,line in enumerate(lines) if line.startswith(f":{name} "))
    end=i+1
    while end < len(lines) and lines[end].startswith(","):
        end += 1
    lines[i:end] = [f":{name} {first}"] + (continuation or [])


def build(item):
    version=VERSIONS[item["version"]]
    template=ROOT / f"scanner/FSE_dwi_CPMG_non_CPMG_twoTE-{version}.ppr"
    lines=template.read_bytes().decode("latin-1").replace("\r\n","\n").split("\n")
    lines[0]=f":PPL G:\\J_Figger\\FSE_dwi_CPMG_non_CPMG_twoTE-{version}.ppl"
    n=item["matrix"]
    etl=8
    raw=(etl+1)*(1+n//etl) if item["nav_on"]==2 else n+etl
    # The played PE table uses n+etl logical views, even when raw nav2 has
    # additional appended rows. Scale the acquired 136-view calibration by
    # that logical view count; scaling by raw would change the phase FOV.
    pe_scale=(n+etl)/136
    edits=dict(no_samples=n,no_views=raw,views_per_seg=etl,no_views_2=1,
               nav_on=item["nav_on"],no_experiments=len(item["rows"]),
               no_diff_acq=len(item["rows"]),no_averages=1,no_disacq=4,
               no_slices=len(item["offsets"]),batch_slices=0,
               tr=item["tr"],te=item["te"],esp=item["esp"],
               big_delta=item["big_delta"],sm_delta=4000,b_input_mode=1,
               crush_amp=-8223,diff_crush_amp=-5482,
               gr_var=-1471 if item["dwell_us"]==25 else -735,
               gp_init_var=-round(1000*pe_scale),report_on=0,
               chess_on=0,mtc_on=0,de_on=0,flow_comp_on=0,PE_order=1,
               rec_freq=0,subj_angle_x=0,subj_angle_y=0,subj_angle_z=0)
    for name,value in edits.items():
        replace_record(lines,name,value)
    replace_meta(lines,"SAMPLE_PERIOD",'sample_period, 250, 17, "40.0 KHz  25 µs"' if item["dwell_us"]==25 else 'sample_period, 500, 12, "20.0 KHz  50 µs"')
    replace_meta(lines,"SMX","0.0449126" if item["dwell_us"]==25 else "0.0224563")
    replace_meta(lines,"SMY",f"{0.0305406*pe_scale:.10g}")
    replace_meta(lines,"FOV","35")
    ns=len(item["offsets"])
    if ns > 1:
        gap_mm=(item["offsets"][1]-item["offsets"][0])/400
        replace_meta(lines,"SLICE_SEPARATION",f"slice_offset, {round(gap_mm*1070)}, {gap_mm:g}")
    for name in ("r_angle_var","p_angle_var","s_angle_var","fov_read_off","fov_phase_off"):
        replace_array(lines,name,[0]*ns,resize=True)
    replace_array(lines,"fov_slice_off",item["offsets"],resize=True)
    replace_meta(lines,"MULTI_ORIENTATION",ns,[", 0"]*ns)
    # Display-only host offset metadata: mimic the acquired K convention for
    # multiple slices, whose operative position records are FOV_*_OFF above.
    replace_meta(lines,"FOV_OFFSETS",ns,[", 0, 0, 0"] if ns==1 else [])
    replace_array(lines,"acq_b",[b for b,_ in item["rows"]])
    for axis,name in enumerate(("acq_x","acq_y","acq_z")):
        replace_array(lines,name,[d[axis] for _,d in item["rows"]])
    return "\r\n".join(lines).encode("latin-1"), raw, edits


def main():
    manifest=[]
    for item in TESTS:
        stem=f"FSE-DWI_10-11-2026_{item['version']}_test{item['letter']}"
        folder=OUT/stem
        folder.mkdir(exist_ok=True)
        data,raw,edits=build(item)
        ppr=folder/f"{stem}.ppr"
        ppr.write_bytes(data)
        # Validate-mode source duration: a TR covers a whole auto-sized slice
        # batch; do not multiply again by slice count. Four dummies per volume.
        shots=item["matrix"]//8+1+4
        duration=0 if item["expected_rejection"] else len(item["rows"])*shots*item["tr"]/1000
        record=dict(item,stem=stem,ppr=str(ppr.relative_to(OUT)).replace("\\","/"),
                    ppr_sha256=hashlib.sha256(data).hexdigest(),raw_views=raw,
                    effective_phase_views=item["matrix"]+8,
                    gp_init_var=edits["gp_init_var"],
                    nominal_duration_s=duration,slice_offsets_mm=[x/400 for x in item["offsets"]])
        manifest.append(record)
        (folder/"protocol_notes.json").write_text(json.dumps(record,indent=2)+"\n")
    summary=dict(fov_mm=35,assumption="Fixed brain in PBS; record fixation and measured temperature on scanner.",
                 core_duration_s=sum(x["nominal_duration_s"] for x in manifest if x["priority"]=="core"),
                 conditional_duration_s=sum(x["nominal_duration_s"] for x in manifest if x["priority"]=="conditional"),
                 alternative_total_duration_s=sum(x["nominal_duration_s"] for x in manifest if x["priority"]=="core" and x["letter"]!="V")+next(x["nominal_duration_s"] for x in manifest if x["letter"]=="AD"),
                 ppl_sha256={v:hashlib.sha256((ROOT/f"scanner/FSE_dwi_CPMG_non_CPMG_twoTE-{version}.ppl").read_bytes()).hexdigest() for v,version in VERSIONS.items()},
                 protocols=manifest)
    (OUT/"manifest.json").write_text(json.dumps(summary,indent=2)+"\n")
    with (OUT/"run_order.csv").open("w",newline="",encoding="utf-8-sig") as f:
        writer=csv.writer(f)
        writer.writerow(["test","version","priority","purpose","volumes","dwell_us","ESP_ms","TE_ms","Delta_ms","TR_ms","matrix","slices","navigator","raw_views","scan_minutes","PPR"])
        by_letter={x["letter"]:x for x in manifest}
        assert set(RUN_ORDER)==set(by_letter) and len(RUN_ORDER)==len(by_letter)
        for letter in RUN_ORDER:
            x=by_letter[letter]
            writer.writerow([x["letter"],x["version"],x["priority"],x["purpose"],len(x["rows"]),x["dwell_us"],x["esp"],x["te"],x["big_delta"]/1000,x["tr"],x["matrix"],len(x["offsets"]),x["nav_on"],x["raw_views"],round(x["nominal_duration_s"]/60,3),x["ppr"]])
    print(f"Generated {len(manifest)} protocols. Core={summary['core_duration_s']/60:.2f} min; with conditional off-resonance={sum(summary[k] for k in ['core_duration_s','conditional_duration_s'])/60:.2f} min.")


if __name__=="__main__":
    main()
