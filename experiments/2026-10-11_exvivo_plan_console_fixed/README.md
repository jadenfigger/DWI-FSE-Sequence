# October 11 console-compatible PPR copies

All 30 PPRs retain their original experiment folder/file names and 35-mm FOV.

The missing FOV_OFFSETS rows are restored for every multi-slice PPR, using physical offsets in mm.

Every original nav_on=2 PPR now uses nav_on=1 as a temporary workaround compatible with the current v1.82/v1.912 PPLs. The 128-matrix files have 136 raw views; the 256-matrix final V has 264. Imaging ETL remains 8. These copies have volume navigators and do not acquire appended per-shot navigators. M/N therefore serve as repeats, not per-shot navigator validation. A proper mode-2 fix requires changes to the PPL host parameter interface and corresponding reconstruction interpretation.

W/X/Y remain deliberately invalid guard tests: load in validation mode only and expect rejection before acquisition.

Use run_order.csv for the file list and original acquisition schedule. V is the final 256-matrix pilot; AD replaces V as the 128-matrix alternative. Both retain one average, Delta30 ms and three directions per shell.

No validation was run on these new copies, as requested. Original files remain in ../2026-10-11_exvivo_plan/.
