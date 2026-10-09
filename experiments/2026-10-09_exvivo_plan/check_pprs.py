"""Dry-run each 10-09 PPR through the repo PPL interpreter (source model only)."""
import re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from dwfse.ppl.run import map_events
from examples import v19_validate_events as old
from dwfse.ppl.events import rf_pulses

PPL = {"1.8": ROOT / "scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.8.ppl",
       "1.81": ROOT / "scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.81.ppl",
       "1.91": ROOT / "docs/v181_v1911/baseline_v7/FSE_dwi_CPMG_non_CPMG_twoTE-1.91.ppl",
       "1.911": ROOT / "scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.911.ppl"}
for ppr in sorted(Path(__file__).parent.glob("*.ppr")):
    ver = re.search(r"twoTE-([\d.]+)\.ppl", ppr.read_text("latin-1").splitlines()[0]).group(1)
    it = map_events(PPL[ver], ppr, max_shots=6, **old.NOMINAL)
    rf = len([p for p in rf_pulses(it) if p.get("library")])
    msgs = [m.strip() for _, m in it.out if m.strip()]
    bad = [m for m in msgs if re.search(r"error|too short|invalid|increase|not supported|exceed", m, re.I)]
    print(f"{ppr.stem:42s} v{ver:6s} RF={rf:4d} ADC={len(it.adc):4d} msgs={bad[:2] or 'none'}")
