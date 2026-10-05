"""Integer checks mirroring the v1.7 scanner preflight (not a vendor compiler)."""


def scaled_diffusion_dac(dac, percentage, diffusion_on=True):
    if not 0 <= dac <= 32767 or not 100 <= percentage <= 200:
        raise ValueError('Invalid diffusion DAC or scale')
    # Scanner operands are widened BEFORE multiplication; maximum product 6553400.
    value = dac * percentage // 100
    if value > 32767 or (diffusion_on and value > 30000):
        raise ValueError('Diffusion DAC exceeds limit before int conversion')
    return value


def diffusion_components(dac, direction, b_value_mode=False):
    if len(direction) != 3 or any(not -1000 <= x <= 1000 for x in direction):
        raise ValueError('Invalid diffusion direction')
    # EVO scale() divides toward zero, not toward negative infinity.
    values = [(-1 if x < 0 else 1) * (dac * abs(x) // 1000) for x in direction]
    if b_value_mode and dac > 0 and not any(values):
        if not any(direction):
            raise ValueError('Zero direction defeats b=0 workaround')
        axis = max(range(3), key=lambda k: abs(direction[k]))
        values[axis] = -1 if direction[axis] < 0 else 1
    return tuple(values)


def refocus_timer_targets(crusher_us, ramp_us, pre_pad_us, post_pad_us,
                          rf_delay_us, gate_delay_us):
    played = crusher_us + pre_pad_us
    pre = (played + ramp_us - 40 + rf_delay_us - (gate_delay_us - 17)) * 10
    post = (played + ramp_us - rf_delay_us + post_pad_us - pre_pad_us) * 10
    if not (50 <= pre <= 65500 and 50 <= post <= 65500):
        raise ValueError('Refocus wait exceeds timer range')
    return pre, post


def post_adc_targets(base_us, train_balance_us, pad_delta_us=0):
    return base_us * 10, (base_us + train_balance_us + pad_delta_us) * 10


# EVO manual pp.118-121 expression costs, in 100-ns ticks. The gettimer sample
# precedes its result assignment. Only these operations remain before waittimer:
# ret=gettimer()+250: literal 2, add 1, lhs int 4.
# templ3=templ3-ret: long 7, int 4, promotion 3, long subtraction 8, lhs long 7.
# ret=ret+25: int 4, literal 2, add 1, lhs int 4.
# waittimer(ret-25): int 4, literal 2, subtraction 1.
# Reserve the manual's entire minimum starttimer/waittimer interval (30 ticks)
# for dispatch, in addition to expression costs. This is a source estimate;
# target compiler instruction timing and optional PDD paths need measurement.
POST_ADC_EXPRESSION_TICKS = 7 + 29 + 11 + 7
POST_ADC_DISPATCH_RESERVE_TICKS = 30
POST_ADC_ALLOWANCE_TICKS = 250
