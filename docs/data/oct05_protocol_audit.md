# October 5 physical scanner protocol audit

This audit checks all 20 cataloged acquisitions using each MRD's embedded PPR block, the adjacent PPR file, and any JSON sidecar. The script and machine-readable outputs are [oct05_protocol_audit.py](oct05_protocol_audit.py), [oct05_protocol_audit.json](oct05_protocol_audit.json), [oct05_protocol_scans.csv](oct05_protocol_scans.csv), and [oct05_protocol_pairs.csv](oct05_protocol_pairs.csv).

## Findings

- Audited 20 MRDs; all expected binary payloads fit before their embedded PPR blocks, and every PPR starts after at least 120 interstitial bytes.
- All 60 of 60 expected experiment slots contain nonzero raw data, including all three slots in legacy testa.
- Adjacent sidecar PPR protocol values match the embedded protocol values across all 20 scans; MRDs also contain scanner runtime tags absent from the standalone PPRs.
- JSON sidecars are present for 18 of 20 scans. Every available JSON comparison for PE order, diffusion settings, delta timings, b-values, and slice spacing matches the MRD; JSON contains no scanner gain or acquisition date fields.
- The 19 v1.8 MRDs embed the scanner source path `G:\J_Figger\FSE_dwi_CPMG_non_CPMG_twoTE-1.8.ppl`; testa embeds the v1.3 path. Git HEAD 724b9a7 contains tracked PPL versions 1.6 and 1.7 only, with no v1.8 PPL/PPR in history. The acquisition version label is recorded, while the precise v1.8 source cannot be verified here.
- AcquisitionStartTime is a hardware performance-counter tick value, not a calendar timestamp. The CSV gives its relative order and minutes from test0; filesystem modification times are kept separately as file metadata.
- Counter order from test0 is: test0, test1, testa, test2, test3, test1b, test1c, test1d, test2b, test3b, test1e, test4, test5, test6, test7, test4b, test2c, test1f, test2d, test1g. This order places testa after test1 and interleaves several PE/schedule variants; it is based on the common 10 MHz counter values.
- Embedded receiver gain is 180.0 for test0 and 30.0 for all other scans. Transmit and decoupling gains are -205.0 and -453.0 throughout. This makes test0 a receiver-gain confound in comparisons with the other scans.
- The stored PPR filenames in test1e, test1f, and test1g reuse `FSE-DWI_10-05-2026_v18_test1.ppr`. The audit associates each PPR with its enclosing folder and compares embedded protocol fields independently.

## Controlled PE groups

The constant-crusher controls test1e/f/g share all embedded records except PE_order and AcquisitionStartTime; their PE orders are 1, 6, and 7. The increasing-schedule controls test2b/c/d follow the same pattern. Checks compare every embedded protocol and scanner record, including multiline arrays. The pairs CSV also records additional crusher and schedule contrasts.

## Legacy testa completeness

Legacy testa was checked from MRD dimensions, datatype, b-value array, payload size, PPR, and the three saved reconstructed image / reordered k-space pairs. It has an MRD and adjacent PPR but no JSON, bval, bvec, or NIfTI sidecars in the supplied folder. The available raw MRD includes three experiment entries; the exact v1.3 protocol differences remain visible in the scan CSV and its embedded PPR fields.

Protocol settings describe stored and embedded metadata. They do not establish image quality or physical calibration accuracy.
