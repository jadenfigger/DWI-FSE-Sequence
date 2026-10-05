"""
Reader for multidimensional MRD / SUR magnetic resonance raw data files with PPR header parsing.
Ported from Get_mrd_3D4.m (originally by Ruslan Garipov).
"""

from datetime import datetime
import os
from pathlib import Path
import re
import struct
import numpy as np


def get_mrd_3d4(filename, reordering1="seq", reordering2="seq"):
    """
    Read multidimensional MRD/SUR file and parse parameters from the PPR section.

    Parameters
    ----------
    filename : str or Path
        Path to the .MRD or .SUR file.
    reordering1 : str, optional
        Reordering for 2D (views): 'seq' or 'cen' (default 'seq').
    reordering2 : str, optional
        Reordering for 3D (views_2): 'seq' or 'cen' (default 'seq').

    Returns
    -------
    im : np.ndarray
        Complex data array with shape (no_expts, no_echoes, no_slices, no_views_2, no_views, no_samples).
    dim : list of int
        [no_expts, no_echoes, no_slices, no_views_2, no_views, no_samples]
    par : dict
        Parsed header parameters.
    """
    filename = Path(filename)
    if not filename.is_file():
        raise FileNotFoundError(f"File not found: {filename}")

    with open(filename, "rb") as fid:
        # Read dimensions at offset 0
        xdim, ydim, zdim, dim4 = struct.unpack("<4i", fid.read(16))

        # Read datatype at offset 18
        fid.seek(18, os.SEEK_SET)
        datatype_raw = struct.unpack("<H", fid.read(2))[0]
        datatype_hex = f"{datatype_raw:x}".upper()

        # Read scaling at offset 48
        fid.seek(48, os.SEEK_SET)
        scaling = struct.unpack("<f", fid.read(4))[0]
        bitsperpixel = struct.unpack("<B", fid.read(1))[0]

        # Read dim5, dim6 at offset 152
        fid.seek(152, os.SEEK_SET)
        dim5, dim6 = struct.unpack("<2i", fid.read(8))

        # Seek to offset 256 and read 256-byte header text
        fid.seek(256, os.SEEK_SET)
        _ = fid.read(256)

        no_samples = xdim
        no_views = ydim
        no_views_2 = zdim
        no_slices = dim4
        no_echoes = dim5
        no_expts = dim6

        dim = [no_expts, no_echoes, no_slices, no_views_2, no_views, no_samples]

        # Determine complexity & data format
        if len(datatype_hex) > 1:
            onlydatatype = datatype_hex[1]
            iscomplex = 2
        else:
            onlydatatype = datatype_hex[0]
            iscomplex = 1

        dtype_map = {
            "0": np.uint8,
            "1": np.int8,
            "2": np.int16,
            "3": np.int16,
            "4": np.int32,
            "5": np.float32,
            "6": np.float64,
        }
        data_dtype = dtype_map.get(onlydatatype, np.int32)

        num2read = (
            no_expts
            * no_echoes
            * no_slices
            * no_views_2
            * no_views
            * no_samples
            * iscomplex
        )

        # Read binary raw data
        m_total = np.fromfile(fid, dtype=data_dtype, count=num2read)
        if m_total.size != num2read:
            print(f"Warning: Expected {num2read} values, read {m_total.size}.")

        if iscomplex == 2:
            m_real = m_total[0::2]
            m_imag = m_total[1::2]
            m_C = m_real + 1j * m_imag
        else:
            m_C = m_total.astype(np.complex64)

        # Build view reordering indices (0-based)
        ord_views = np.arange(no_views)
        if reordering1 == "cen":
            half_v = no_views // 2
            for g in range(1, half_v + 1):
                ord_views[2 * g - 2] = half_v + g - 1
                ord_views[2 * g - 1] = half_v - g

        ord_views2 = np.arange(no_views_2)
        if reordering2 == "cen":
            half_v2 = no_views_2 // 2
            for g in range(1, half_v2 + 1):
                ord_views2[2 * g - 2] = half_v2 + g - 1
                ord_views2[2 * g - 1] = half_v2 - g

        # The on-disk loop order in Get_mrd_3D4.m is
        # experiment, echo, slice, view, view_2, sample.  Reshaping in C
        # order reproduces that explicit loop exactly; using order="F" here
        # would incorrectly mix readout samples with phase-encode views.
        raw = m_C.reshape(
            (no_expts, no_echoes, no_slices, no_views, no_views_2, no_samples),
            order="C",
        )

        # Public convention is [experiment, echo, slice, view_2, view,
        # sample].  ``ord_*`` map an acquired index to its destination, so
        # indexing by their inverse puts the acquired data into that
        # destination without an ambiguous advanced-index assignment.
        im = raw.transpose(0, 1, 2, 4, 3, 5)
        im = im[:, :, :, np.argsort(ord_views2), :, :]
        im = im[:, :, :, :, np.argsort(ord_views), :]
        im = np.ascontiguousarray(im, dtype=np.complex64)

        # Read sample filename and trailing PPR parameters
        _ = fid.read(120)
        ppr_bytes = fid.read()

    # Parse PPR header section
    par = _parse_ppr(ppr_bytes, str(filename), datatype_hex, scaling)
    return im, dim, par


def _parse_ppr(ppr_bytes, filename, datatype_hex, scaling):
    """Internal helper to parse key-value lines from the PPR section."""
    par = {
        "filename": filename,
        "datatype": datatype_hex,
        "scaling": scaling,
    }

    try:
        mtime = os.path.getmtime(filename)
        par["date"] = datetime.fromtimestamp(mtime).strftime("%d-%b-%Y %H:%M:%S")
    except Exception:
        par["date"] = ""

    if not ppr_bytes:
        return par

    # Decode PPR text
    ppr_text = ppr_bytes.decode("latin-1", errors="ignore")
    lines = [line.strip() for line in re.split(r"[\r\n]+", ppr_text) if line.strip()]

    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith(":"):
            tokens = line[1:].strip().split(None, 1)
            key = tokens[0] if tokens else ""
            rest = tokens[1] if len(tokens) > 1 else ""

            # 1. IM_ORIENTATION / IM_OFFSETS
            if key in ("IM_ORIENTATION", "IM_OFFSETS"):
                nums = [float(x) for x in re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", rest)]
                par[key] = np.array(nums)

            # 2. VAR_ARRAY / angles
            elif key in ("VAR_ARRAY", "X_ANGLE", "Y_ANGLE", "Z_ANGLE"):
                parts = [p.strip() for p in rest.split(",") if p.strip()]
                if parts:
                    arr_name = parts[0]
                    vals = []
                    # Read inline numbers
                    for p in parts[1:]:
                        vals.extend([float(x) for x in re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", p)])
                    # Read continuation lines until next ':'
                    while i + 1 < len(lines) and not lines[i + 1].startswith(":"):
                        i += 1
                        vals.extend([float(x) for x in re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", lines[i])])
                    par[arr_name] = np.array(vals)

            # 3. Text fields (PPL, OBSERVE_FREQUENCY)
            elif key in ("PPL", "OBSERVE_FREQUENCY"):
                par[key] = rest.strip()

            # 4. Standard key-value or variable parameters
            elif rest:
                # Comma-separated structure, e.g. "no_samples, 16" or "gs_var, -799, 100"
                parts = [p.strip() for p in rest.split(",") if p.strip()]
                nums = [float(x) for x in re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", rest)]

                if len(parts) >= 2 and not re.match(r"^[-+]?\d", parts[0]):
                    var_name = parts[0]
                    par[var_name] = nums[0] if len(nums) == 1 else np.array(nums)
                    par[key] = par[var_name]
                elif nums:
                    par[key] = nums[0] if len(nums) == 1 else np.array(nums)
                else:
                    par[key] = rest
        i += 1

    if "OBSERVE_FREQUENCY" in par and isinstance(par["OBSERVE_FREQUENCY"], str):
        tokens = par["OBSERVE_FREQUENCY"].split()
        par["Nucleus"] = tokens[0] if tokens else "Unspecified"
    else:
        par["Nucleus"] = "Unspecified"

    return par
