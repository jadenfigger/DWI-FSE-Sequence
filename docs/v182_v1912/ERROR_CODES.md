# Errors and protocol restrictions: v1.82 and v1.912

These messages describe source-level protocol checks. They have not been verified on the scanner console. In v1.82, messages are plain text. v1.912 uses numeric v1.911-style errors for method checks, with selected messages that print the computed minimum.

## v1.82 text messages

| Exact message | Meaning | Remedy |
|---|---|---|
| `V182 3D not supported` | `no_views_2 != 1`; 3D readout is compiled out to remain within the program image budget. | Use a single-slice 2D acquisition. |
| `V182 DE not supported` | Driven equilibrium is enabled. | Set driven equilibrium off. |
| `V182 nav_on must be 0..2` | Navigator mode is outside the defined 0–2 range. | Use 0 (off), 1 (per volume) or 2 (per shot). |
| `V182 raw views: >=2 shots of ETL+1` | Mode 2 has a raw-line count that is not an integer number of at least two `(ETL+1)` groups. | Set `NO_VIEWS=(ETL+1)×(1+N/ETL)` for the per-volume train and at least one imaging shot. |
| `V182 off-centre RF timer window invalid` | The frequency-offset window cannot be placed safely around the selected RF timing, or its represented timer span reaches the 49-ms limit. | Restore supported RF/ramp timing and reduce the offset/pulse geometry if necessary. |
| `V182 off-centre RF phase product overflow` | The accumulated frequency-offset × time phase product exceeds the safe integer representation. | Reduce the slice offset or selection gradient. |

CHESS remains supported. v1.82 otherwise inherits the v1.81 checks, including the DWI flow-compensation restriction and the existing read-balance and gradient limits; see [`docs/v181_v1911/ERROR_CODES.md`](../v181_v1911/ERROR_CODES.md).

## v1.912 numeric codes

| Code | Meaning | Remedy |
|---|---|---|
| E147 | Requested ESP is below the computed minimum for the active readout/timing layout. The error prints `V1912 minimum ESP=<n> ms`. | Increase ESP to the printed minimum or above. |
| E148 | Slice-centre separation is below `thickness × ((max(slab, tip-up)/1000 + 1)/2 + 0.75)`. The 0.75-thickness margin is rounded up in console units. The error prints `V1912 minimum slice separation=<n> units`. | Increase slice separation to the printed minimum or above. |
| E149 | A computed slice-frequency offset for a selection RF is outside the supported −32767…32767 Hz range. | Reduce slice offset or use a pulse geometry with a lower selection gradient. |
| E150 | `nav_on` is outside 0–2. | Set 0, 1 or 2. |
| E151 | Mode-2 navigator layout is invalid: unsupported PE order, raw count not divisible by `ETL+1`, or fewer than two total raw shots. | Use centric PE and `NO_VIEWS=(ETL+1)×(1+N/ETL)` for at least two total raw shots. The inherited E6 limit permits ETL 1–64, including mode 2. |

E3's v1.911 meaning (one centred slice only) is superseded: v1.912 supports multiple and off-centre slices subject to the phase, frequency-offset and E148 spacing checks. Other v1.912 inherited codes keep their v1.911 meanings except for the removed fixed ESP=13 rule: E144 no longer rejects ESP 14–16 by itself. The computed minimum handles ESP; genuine receiver/timer limits such as E32 still apply. Oblique orientations and the constrained fused-gradient geometry remain unsupported. For the full inherited table, see [`docs/v181_v1911/ERROR_CODES.md`](../v181_v1911/ERROR_CODES.md).
