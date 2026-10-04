# Reviewable scanner corrections

These patches target the unchanged v1.6 source in the parent directory. They
are **not compiled or scanner validated**. `git apply --check --ignore-space-change`
passes against the repository source. Preserve a copy of v1.6 before applying.

The [v1.7 successor](../../docs/scanner_v17.md) implements both corrections
and bounded native signed crusher schedules without editing v1.6. Its default
PPR uses original amplitudes; separately named experimental PPRs enable increasing
and increasing-plus-alternating crushers. Do not apply these baseline patches
again to v1.7. Compilation and physical qualification remain pending.

* `refocus_centering.patch`: removes the opposite `rfdelay` terms from the
  independent-crusher pre/post pads. Their sum, and hence RF-block duration,
  remains constant. The RF-start and post-RF waits then provide the same physical
  group-delay compensation as excitation/ADC. Recompute all setup timing budgets;
  check the physical plateau/RF overlap and measured TE/ESP/Delta on a phantom.
  The generator comparison is `sim_fix_refocus_centering=true`; its waveform
  translation holds RF centres fixed and shifts refocus/diffusion gradient lists.
  This equivalence assumes the PPL balance equations cancel instruction overhead;
  it does not establish the scanner's microsecond instruction timing.
* `pe0_scratch_guard.patch`: rejects one-based doubled PE-order-0 tables that
  exceed their reserved RAM regions. It conservatively rejects ETL 256 too,
  although the replay demonstrates actual corruption at ETL 512. DWI already
  excludes PE order 0; this corrects the diffusion-OFF branch only.

The varying-crusher experiment is provided as generator parameters in
`docs/params/improvement_candidate.json`, not as unvalidated real-time matrix
code. Its eight signed crusher DACs are 2754, 5482, 7675, 9868, 12060, 14253,
16446, 18639. To port it, expose an ETL-sized table, select each value for both
lobes around that refocusing RF, and update the *inactive* secondary crusher
matrix before the next refocus list. PPL hooks: matrices 3080/3089, switch 3737,
list selection 3531. Reserve matrix storage and budget its setup instructions;
do not alter a matrix while its gradient list is active. Bounds must reject
out-of-range DACs and table/ETL mismatches. No timing or SAR approval is implied.

For the linear candidate, an alternative to a full table is a new PPR parameter
`crusher_step_pct=40`, with pulse 1 retaining `diff_crush_amp`, pulse 2 retaining
`crush_amp`, and pulse k>=3 using
`crush_amp + (IntToLong(crush_amp)*IntToLong(crusher_step_pct)*IntToLong(k-2)+50L)/100L`.
This reproduces the tested positive-amplitude table exactly. Restrict the initial
implementation to positive base/step values and bound the 32-bit product and
result before playing gradients. The optional stronger purity candidate has a
nonlinear table in `docs/params/improvement_purity_candidate.json`.
