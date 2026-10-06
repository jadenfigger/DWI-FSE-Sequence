# Scanner input upload checklist

Supply these exact inputs to continue v191/v192 implementation. Existing v18 and five top-level PPH files are already local and must remain unchanged.

## Required baseline dependencies

1. `tstex_15.pph`, plus every dependency it includes.
2. These eleven vendor libraries referenced by the actual v18 source, normally in `C:\smis\seqlib`:

```text
RFstd44.seq
gs_240Hz.seq
presat.seq
opt90_a.seq
opt90_as.seq
asym.seq
hypsec.seq
rfchess.seq
9lobsinb.seq
19lobsinb.seq
g3040_15.seq
```

These are vendor WavEd libraries, not Pulseq `.seq` exports. A ZIP retaining filenames is suitable. Include their editable WavEd source or sampled waveform/metadata export if available; named frames, RF board/address/wait metadata and signed phase/amplitude interpretation are necessary.

## Compiler, encoding and calibration evidence

- Vendor compiler/simulator build/version and compile logs for the supplied v18 PPL. If permitted and portable, supply the compiler/simulator tools and supporting files; otherwise console-generated logs/exports will support a staged workflow.
- Machine-readable v18 played RF/gradient/ADC event export and its format documentation, including event/sample times, RF complex phase/amplitude or documented equivalent, gradient coordinates/units, ADC times/demodulation, gradient/RF delays and selected protocol. Include dummy/navigator/multislice cases when possible.
- RF-library creation documentation and a working custom-RF example: WavEd file format, frame naming, sampled complex RF and gradient format, board dwell/sample limits, amplitude normalization, flip calibration and phase convention.
- Scanner system/calibration export: field strength, per-axis maximum gradient amplitude and slew, physical/logical coordinate convention, DAC-to-gradient conversion, measured gradient/RF delays, RF/transmit attenuation/calibration and applicable system limits. The existing user-adjustable DAC ceilings do not certify these physical ratings.
- Confirm whether local `scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.8.ppl` is the exact October 5 acquisition source. If uncertain, upload the source from `G:\J_Figger` and its dependencies for comparison, plus the intended eight-echo companion PPR.

## Exact paper-reproduction inputs, if available

- Gibbons authors' sampled SLR preparation excitation/refocusing, six-subpulse spectral-spatial tip-up plus synchronized gradient, and short imaging excitation/refocusing waveforms.
- Exact figure-specific Alsop/Le Roux and Busse refocusing angle/phase arrays, echo timings, initial states and acquisition ordering used for Figure 4 and S1.

The paper gives design targets but does not publish those complete sampled coefficients/arrays. They are not prerequisites for trying a disclosed new pulse design; they are needed to claim exact coefficient/schedule reproduction. Any newly designed substitute must be measured against magnitude **and phase** targets and labeled accordingly.

No scanner deployment or library overwrite is authorized by this checklist. Uploading inputs enables local implementation, event validation and independent review.
