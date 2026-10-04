"""Integer contract for scanner twoTE-1.7 crusher schedules.

Pulse numbers are one based; array indices are pulse minus one. This module
deliberately checks the PPL's 16/32-bit bounds before doing each operation.
Limits are calibrated logical DAC units, not an assertion of hardware ratings.
"""
from numbers import Integral

DAC_MAX = 32767
LONG_MAX = 2147483647
SCHEDULE_CAPACITY = 1024
CUSTOM_CAPACITY = 64
ADC_BASE_TICKS = 8997
ADC_SCHEDULE_TICKS = 18997
UPDATE_MAX_TICKS = 9000


def integer(value, name, low, high):
    if not isinstance(value, Integral) or isinstance(value, bool) or not low <= value <= high:
        raise ValueError(f'{name} must be an integer in {low}..{high}')
    return int(value)


def rounded_magnitude(base, factor):
    """factor is a nonnegative percentage; round half up before applying sign."""
    magnitude = abs(base)
    if magnitude and factor > (LONG_MAX - 50) // magnitude:
        raise ValueError('crusher magnitude product would overflow signed long')
    result = (magnitude * factor + 50) // 100
    if result > DAC_MAX:
        raise ValueError('crusher amplitude exceeds signed DAC range')
    return result


def schedule(etl, first, train, mode=0, step_pct=0, custom_count=0,
             custom_pct=None, max_dac=DAC_MAX, slew_dac_100us=DAC_MAX, ramp_us=200):
    """0 constant, 1 up, 2 alternate, 3 up/alternate, 4 down, 5 custom.

    Custom storage has exactly 64 signed integer percentages, with an explicit
    active count equal to ETL. There is no repetition or implicit truncation.
    Built-ins support ETL 1..1024. ETL 1 has only the special first amplitude;
    ETL 2 has no progression. Negative bases retain their sign before alternation.
    """
    etl = integer(etl, 'ETL', 1, SCHEDULE_CAPACITY)
    first = integer(first, 'diff_crush_amp', -DAC_MAX, DAC_MAX)
    train = integer(train, 'crush_amp', -DAC_MAX, DAC_MAX)
    mode = integer(mode, 'crusher_schedule', 0, 5)
    step_pct = integer(step_pct, 'crusher_step_pct', 0, 1000)
    max_dac = integer(max_dac, 'crusher_max_dac', 1, DAC_MAX)
    slew_dac_100us = integer(slew_dac_100us, 'crusher_slew_dac_100us', 1, DAC_MAX)
    ramp_us = integer(ramp_us, 'tramp', 100, 1000)
    if ramp_us % 10:
        raise ValueError('tramp must be a multiple of 10 us')
    if mode == 5:
        integer(custom_count, 'crusher_custom_count', 1, CUSTOM_CAPACITY)
        if custom_count != etl or custom_pct is None or len(custom_pct) != CUSTOM_CAPACITY:
            raise ValueError('custom count must equal ETL; storage must contain exactly 64 entries')
        factors = [integer(v, 'crusher_custom_pct entry', -DAC_MAX, DAC_MAX)
                   for v in custom_pct]
    else:
        factors = None
    values = []
    for pulse in range(1, etl + 1):
        base = first if pulse == 1 else train
        sign = -1 if base < 0 else 1
        factor = 100
        if mode == 5:
            factor = factors[pulse - 1]
            if factor < 0:
                sign *= -1
                factor = -factor
        elif pulse >= 2 and mode in (1, 3, 4):
            n = etl - pulse if mode == 4 else pulse - 2
            if n and step_pct > (LONG_MAX - 100) // n:
                raise ValueError('crusher progression would overflow signed long')
            factor += n * step_pct
        if mode in (2, 3) and pulse % 2 == 0:
            sign *= -1
        magnitude = rounded_magnitude(base, factor)
        if magnitude > max_dac:
            raise ValueError('crusher amplitude exceeds configured gradient amplitude limit')
        if magnitude * 100 > slew_dac_100us * ramp_us:
            raise ValueError('crusher ramp exceeds configured slew limit')
        values.append(sign * magnitude)
    return values


def acquisition_budget(samples, discard, sample_period_ticks, mode):
    """Mirror the scanner's padded ADC calculation, without extending ADC/TE."""
    integer(samples, 'no_samples', 1, 1024)
    integer(discard, 'no_discard', 0, 128)
    integer(sample_period_ticks, 'sample_period', 1, 32767)
    budget = ADC_SCHEDULE_TICKS if mode else ADC_BASE_TICKS
    remaining = (samples + discard) * sample_period_ticks - 3 - budget
    ms = remaining // 10000
    us = remaining // 10 - ms * 1000 - (sample_period_ticks == 250)
    if mode and (ms < 1 or us < 10):
        raise ValueError('sampling window cannot contain scheduled crusher update')
    return budget, ms, us


def pe0_capacity(etl, views_per_echo, no_views, diffusion_on=False):
    """Protect all one-based doubled scratch writes AND GP output writes."""
    if diffusion_on:
        raise ValueError('PE order 0 remains unsupported for DWI')
    integer(etl, 'ETL', 4, 1024)
    integer(views_per_echo, 'views_per_echo', 1, 1024)
    integer(no_views, 'no_views', 1, 1024)
    if 2 * etl >= 512 or 2 * views_per_echo >= 512:
        raise ValueError('PE order 0 exceeds scratch table capacity')
    if 2 * etl * views_per_echo != no_views:
        raise ValueError('PE order 0 GP table length does not match views')


def matrix_trace(values, trains=1):
    """Execution oracle: setup under ss=1, RF pair, ADC under aq=3, update.

    A secondary is updated only with aq selected, and completes before the next
    RF list selects its primary. Each train starts by preparing BOTH pairs.
    """
    events = []
    for shot in range(trains):
        matrices = {21: values[0], 22: values[1] if len(values) > 1 else 0}
        events.append((shot, 'reset', 1, dict(matrices)))
        matrix = 21
        for k, amplitude in enumerate(values):
            if matrices[matrix] != amplitude:
                raise AssertionError('stale crusher matrix')
            events.append((shot, 'pair', matrix, (k + 1, amplitude, amplitude)))
            if k + 1 < len(values):
                matrix = 22 if matrix == 21 else 21
                matrices[matrix] = values[k + 1]
                events.append((shot, 'prepare_under_aq', matrix + 256, values[k + 1]))
    return events
