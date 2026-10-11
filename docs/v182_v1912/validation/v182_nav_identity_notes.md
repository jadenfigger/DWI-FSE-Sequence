# Navigator isolation control

`v182_items2to4_control.ppl` is a validation-only source artifact, not a scanner
release. `v182_nav_identity.py` derives it directly from the immutable-baseline
builder by removing only the navigator mode 2 transformations. The actual-DAC
slice frequency calculation, accumulated RF phase correction, pulse-local
frequency gates, and approved 3D/DE image compaction remain in the control.

Reproduce from the repository root:

```text
python docs/v182_v1912/validation/v182_nav_identity.py
```

The script writes the control and `v182_nav_identity.json`, including hashes of
the final sequence, control, and protocol. It verifies modes 0 and 1 over two
actual shots in all eight instruction-cost models. RF and ADC signatures, all
played S/P/R gradient segments, and sync-to-first-RF timing agree at the mapper's
1 ns signature resolution in all 16 cases. Matrix values also agree. Expression
models shift some secondary matrix register writes inside the padded ADC timer
window (maximum 1.84 us nominal, 2.30 us at manual x1.0); played events agree.

This isolates the navigator requirement from the RF phase work. A separate
centred nav1 comparison against v1.81 shows a nominal 3.2 us increment per RF
interval and corresponding cumulative ADC shifts. The new phase-gate branches
add conditional-evaluation costs outside some inherited timer windows even
when the slice offset is zero. Accordingly the complete new sequence is not
claimed to preserve every v1.81 event timestamp. Hard-coded nominal delay
compensation would not establish equivalence across all cost models and was
not applied. The scanner PPL remained unchanged during this control analysis.

These are source-model results; vendor compilation and scanner timing remain
separate validation requirements.
