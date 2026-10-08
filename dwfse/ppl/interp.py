"""Executable source-to-event mapper for MR Solutions PPL (research tool).

The interpreter executes the *actual* preprocessed PPL (including vendor include
macros) with explicit 16-bit ``int`` / 32-bit ``long`` semantics and a hardware
model of the documented PPL library calls.  It records gradient sequencer
output, RF frame playback, phase/frequency state and ADC windows.

What this establishes and what it does not
------------------------------------------
* Control flow, arithmetic, array bounds, integer overflow/narrowing, timer
  deadlines (including the documented 5-ms overrun extension), gradient list
  construction, matrix selection/creation order and RF/ADC ordering follow the
  source exactly, *given the semantics below*.
* Instruction execution times are **nominal**: documented manual costs where
  they exist, source-comment empirical costs for MR3040 calls, and a uniform
  per-statement cost (``stmt_cost_us``, default 0) elsewhere.  Event times inside
  untimed code are therefore estimates.  Hardware latencies (gradient group
  delay, RF pipeline, ADC filter delay) are not modeled.  No compiler output was
  available; this is not compiler or console verification.
* Semantics that the supplied manual leaves ambiguous are recorded in
  ``ASSUMPTIONS`` and exposed in every result.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math
import re

import numpy as np

ASSUMPTIONS = [
    "MR3040_Output(loop, addr, points, waits): outputs `points` samples, each held `waits` master-clock periods (vendor macro argument order; the manual's +1 register description is not applied).",
    "grad.size.<frame> = sample count; grad.waits.<frame> = WavEd frame dwell field (1 for all ramp frames).",
    "Gradient channel output = primary_sample/32767*M[id] + secondary_sample/32767*M[id+256], logical axes, identity rotation (non-zero angles rejected for physics use).",
    "A matrix created by CREATE_MATRIX becomes valid caldelay (100 us) after the call returns; nonzero use before then is flagged.",
    "RF frame playback starts at MR3031_go; each sample lasts frame_waits*0.1 us; output is gated by rfon level>0.",
    "RF amplitude = sample/2047 * board_multiplier (signed real frames only).",
    "Transmit phase = multiple*phase_increment*0.225 deg at the time of MR3031_go; receiver phase = rphase at initiate().",
    "waittimer(T) exits T ticks after starttimer entry; if code has already used longer, the exit is extended by whole 5000-us periods (manual pp.90-91).",
    "delay32(x) delays x * 0.1 us (usage in vendor/v18 code; not documented in the supplied manual).",
    "scale(a,b,c) = trunc(a*b/c) evaluated in 32 bits.",
    "aqphase(n, pc) returns 0 for phase_cycle 1, 2*(n%2) for phase_cycle 2.",
    "hostrequest() returns 1 (no host update).",
    "OrderTimeToPos/BatchTimeToPos return the sequential time index (single-slice use only).",
    "acqpad(sample_period) (vendor digital-filter padding, undocumented) returns acqpad_ticks (default 3730 = 10 x var_20 tfilter initializer 373 us).",
    "input#n reads 0 (no gating/mains trigger hardware).",
    "complete() returns after the digital-filter flush, acqpad/10 us (+5.2 us documented). Inferred from v18 self-consistency: without it every v18 train SetList(slice_180_refocus) would hit a still-active channel and be ignored, removing refocusing slice selection that the October acquisitions demonstrably had.",
]

# documented / source-comment costs in microseconds
COSTS = {
    "starttimer": 0.5, "phase": 29.0, "rphase": 29.4, "reset_frequency": 25.4,
    "frequency": 139.2, "frequency_buffer": 0.5, "offset_frequency": 91.0,
    "initiate": 7.6, "complete": 5.2, "resync": 5.2, "rfon": 1.5, "rfampon": 1.2,
    "rfoff": 1.1, "aqphase": 1.2, "phase_increment": 13.6, "__noop": 0.1,
    # empirical comments in the v18 source
    "mr3040_setlist": 3.3, "mr3040_selectmatrix": 2.0, "mr3040_clock": 2.2,
    "mr3040_start": 2.4, "mr3040_continue": 2.4, "mr3040_creatematrix": 135.6,
    # manual 4.8.9 / 4.8.12: conversion and scale functions
    "inttolong": 0.5, "unsignedtolong": 0.5, "scale": 11.1,
}

# EVO manual 4.9.2 expression timings, 100-ns units: (long operands, int operands)
OP_COST = {"!": (7, 4), "~": (2, 1), "neg": (4, 1), "*": (90, 3), "/": (1232, 111),
           "%": (1208, 53), "+": (8, 1), "-": (8, 1), ">": (12, 1), "<": (12, 1),
           ">=": (13, 2), "<=": (13, 2), "==": (9, 4), "!=": (9, 4), "&": (11, 1),
           "^": (11, 1), "|": (11, 1), "&&": (24, 13), "||": (24, 13),
           "<<": (11, 1), ">>": (11, 1)}
ACCESS_COST = {"long": 7, "int": 4, "common": 12}

CH = {0x0002: "R", 0x0020: "P", 0x0200: "S"}
AXES = ("S", "P", "R")


class PPLRuntimeError(Exception):
    pass


class StopRun(Exception):
    pass


def wrap16(v):
    return ((int(v) + 32768) % 65536) - 32768


def wrap32(v):
    return ((int(v) + 2**31) % 2**32) - 2**31


def ctrunc_div(a, b):
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b >= 0) else -q


def cmod(a, b):
    return a - ctrunc_div(a, b) * b


@dataclass
class Var:
    typ: str
    value: object
    size: int | None = None
    common: bool = False


@dataclass
class Channel:
    name: str
    list_start: int = 0
    state: str = "idle"       # idle, running, held, stopped
    pc: int = 0
    sample_i: int = 0
    t: float = 0.0             # time up to which output has been generated
    out: tuple = (0, 0)
    latch_continue: bool = False
    loop_stack: list = field(default_factory=list)
    segments: list = field(default_factory=list)   # (t0, t1, prim, sec)


class GradHW:
    def __init__(self, lib, owner):
        self.owner = owner
        self.mem = {}
        self.pointer = 0
        self.last_stop = None
        self.frames = {}
        self.samples = []
        addr = 0
        for fr in lib.frames:
            s = fr.samples
            if s.ndim != 2:
                continue
            self.frames[fr.name] = (addr, len(s), fr.wait_ticks)
            self.samples.extend((int(a), int(b)) for a, b in s)
            addr += len(s)
        self.ch = {a: Channel(a) for a in AXES}
        self.clock_hist = [(0.0, 10)]
        self.sel_hist = [(0.0, 0)]
        self.mats = {}   # id -> list of (t_call, t_ready, s, p, r)
        self.mats[0] = [(-1.0, -1.0, 0, 0, 0)]
        self.mats[256] = [(-1.0, -1.0, 0, 0, 0)]
        self.loop_count = 0
        self.starts = []

    # list construction ---------------------------------------------------
    def init_list(self):
        addr = self.pointer if self.last_stop is None else self.last_stop + 1
        self.mem[addr] = ("stop",)
        self.last_stop = addr
        self.pointer = addr
        return addr

    def _write(self, ins):
        self.mem[self.pointer] = ins
        self.pointer += 1
        self.mem[self.pointer] = ("stop",)
        self.last_stop = self.pointer

    def output(self, loop, addr, points, waits):
        if points < 1 or waits < 1:
            self.owner.flag("gradient", f"MR3040_Output with points={points}, waits={waits}")
        self._write(("out", loop, addr, points, waits))

    def hold(self, loop):
        self._write(("hold", loop))

    # playback -------------------------------------------------------------
    def clock_at(self, t):
        c = self.clock_hist[0][1]
        for tc, v in self.clock_hist:
            if tc <= t + 1e-9:
                c = v
            else:
                break
        return c

    def advance(self, t_now):
        for c in self.ch.values():
            self._advance_channel(c, t_now)

    def _advance_channel(self, c, t_now):
        guard = 0
        while c.state == "running" and c.t < t_now - 1e-9:
            guard += 1
            if guard > 2_000_000:
                raise PPLRuntimeError("gradient playback runaway")
            ins = self.mem.get(c.pc, ("stop",))
            if ins[0] == "stop":
                c.state = "stopped"
                return
            if ins[0] == "hold":
                if c.latch_continue:
                    c.latch_continue = False
                    c.pc += 1
                    continue
                c.state = "held"
                return
            _, loop, addr, points, waits = ins
            if loop == 4:  # STARTLOOP
                c.loop_stack.append((c.pc, self.loop_count))
            clk = self.clock_at(c.t)
            dt = waits * clk * 0.1
            val = self.samples[addr + c.sample_i]
            c.segments.append((c.t, c.t + dt, val[0], val[1]))
            c.out = val
            c.t += dt
            c.sample_i += 1
            if c.sample_i >= points:
                c.sample_i = 0
                if loop in (8, 12) and c.loop_stack:
                    top, cnt = c.loop_stack[-1]
                    if loop == 12 or cnt > 0:
                        c.loop_stack[-1] = (top, cnt - 1)
                        c.pc = top
                        continue
                    c.loop_stack.pop()
                c.pc += 1
        # held/stopped/idle channels keep output constant; nothing to record

    def start(self, mask, t):
        self.advance(t)
        for bit, a in CH.items():
            if mask & bit:
                c = self.ch[a]
                if c.state in ("running", "held"):
                    continue
                c.state = "running"
                c.pc = c.list_start
                c.sample_i = 0
                c.t = t
                c.loop_stack = []
                self.starts.append((t, a, c.list_start))

    def cont(self, mask, t):
        self.advance(t)
        for bit, a in CH.items():
            if mask & bit:
                c = self.ch[a]
                if c.state == "held":
                    # held output occupies [hold time, t)
                    c.segments.append((c.t, t, c.out[0], c.out[1]))
                    c.state = "running"
                    c.t = t
                    c.pc += 1
                else:
                    c.latch_continue = True

    def set_list(self, addr, mask, t):
        self.advance(t)
        for bit, a in CH.items():
            if mask & bit:
                c = self.ch[a]
                if c.state in ("running", "held"):
                    self.owner.flag("gradient", f"SetList on active channel {a} ignored")
                    continue
                c.list_start = addr

    def finish(self, t_end):
        self.advance(t_end)
        for c in self.ch.values():
            if c.state == "held":
                c.segments.append((c.t, t_end, c.out[0], c.out[1]))
                c.t = t_end

    def matrix_at(self, mid, t):
        defs = self.mats.get(mid)
        if not defs:
            return None
        cur = None
        for d in defs:
            if d[0] <= t + 1e-9:
                cur = d
            else:
                break
        return cur

    def selected_at(self, t):
        cur = 0
        for ts, mid in self.sel_hist:
            if ts <= t + 1e-9:
                cur = mid
            else:
                break
        return cur


class RFHW:
    def __init__(self):
        self.mul = 0
        self.addr = None
        self.waits = None
        self.gate = False
        self.level = 0
        self.events = []
        self.level_hist = [(0.0, 0)]


class Interp:
    def __init__(self, program, uses, libraries, params, *, stmt_cost_us=0.0,
                 shot_label="slice_block_loop", max_shots=None, record_vars=None,
                 rf_latency_us=0.0, grad_latency_us=0.0, acqpad_ticks=3730, expr_costs=False):
        self.globals_decl, self.funcs = program
        self.uses = uses
        self.params = {k.lower(): v for k, v in params.items()}
        self.stmt_cost = stmt_cost_us
        # expr_costs=True: charge manual 4.9.2 operator/access/constant costs
        self.expr_costs = expr_costs
        self.expr_scale = 1.0
        self.window_use = []
        self.shot_label = shot_label
        self.max_shots = max_shots
        self.shots = 0
        self.t = 0.0
        self.timer_ref = None
        self.vars: dict[str, Var] = {}
        self.page = {}
        self.out = []
        self.flags = []
        self.used_params = set()
        self.compiled = {}
        self.record_vars = record_vars or []
        self.rf_latency = rf_latency_us
        self.acqpad_ticks = acqpad_ticks
        self.grad_latency = grad_latency_us
        # libraries: alias -> decoded Library
        self.rf_registry = {}
        self.rf_frames = {}
        self.board_of = {}
        grad_lib = None
        for kind, path, alias in uses:
            lib = libraries[alias]
            if kind == "GRAD":
                grad_lib = lib
            else:
                for fr in lib.frames:
                    if fr.samples.ndim == 1:
                        fid = 1000 + len(self.rf_registry)
                        self.rf_registry[(alias, fr.name)] = fid
                        self.rf_frames[fid] = (alias, fr.name, fr.samples.astype(float), fr.wait_ticks)
                self.board_of[alias] = 16
        self.grad = GradHW(grad_lib, self)
        self.rf = RFHW()
        self.phase_inc = 400
        self.tx_phase = 0
        self.rx_phase = 0
        self.freq_buf = 0
        self.freq = {}         # buffer -> (base_khz_tuple, offset_hz, preset_offset)
        self.tx_freq_hz = 0.0
        self.rx_latched_hz = 0.0
        self.adc = []
        self.adc_open = None
        self.dummy_cycles = 0
        self.dummy_cycles2 = 0
        self.discard_n = 2
        self.sync_t = 0.0
        self.misc_events = []
        self.stmt_count = 0
        self.call_stack_where = None

    # diagnostics -----------------------------------------------------------
    def flag(self, kind, msg):
        self.flags.append({"t_us": round(self.t, 3), "kind": kind, "msg": msg,
                           "where": self.call_stack_where})

    def advance(self, dt):
        if dt < -1e-9:
            self.flag("timing", f"negative delay {dt}")
            dt = 0
        self.t += dt

    # compilation (flatten structured code) --------------------------------------
    def compile(self, body):
        code = []
        labels = {}

        def emit(x):
            code.append(x)
            return len(code) - 1

        counter = [0]

        def comp(s):
            k = s[0]
            if k == "block":
                for x in s[1]:
                    comp(x)
            elif k in ("expr", "decl", "return"):
                emit(s)
            elif k == "nop":
                pass
            elif k == "label":
                labels[s[1]] = len(code)
            elif k == "goto":
                emit(("jmp_label", s[1], s[2]))
            elif k == "if":
                j = emit(["jfalse", s[1], None, s[4]])
                comp(s[2])
                if s[3] is not None:
                    j2 = emit(["jmp", None])
                    code[j][2] = len(code)
                    comp(s[3])
                    code[j2][1] = len(code)
                else:
                    code[j][2] = len(code)
            elif k == "do":
                top = len(code)
                comp(s[1])
                emit(["jfalse", s[2], top, s[3]])
            elif k == "for":
                counter[0] += 1
                cv = f"__for{counter[0]}_{id(s)}"
                emit(("for_init", cv, s[1], s[3]))
                top = emit(["for_test", cv, None])
                comp(s[2])
                emit(["jmp", top])
                code[top][2] = len(code)
            else:
                raise PPLRuntimeError(f"cannot compile {k}")

        comp(body)
        return code, labels

    # variables ------------------------------------------------------------------
    def declare(self, decl, scope):
        _, typ, common, items, where = decl
        for name, size_e, init in items:
            if size_e is not None:
                n, _ = self.eval(size_e, scope)
                arr = [0] * n
                if init is not None and init[0] == "list":
                    for i, e in enumerate(init[1]):
                        arr[i] = self.conv(self.eval(e, scope), typ)
                v = Var(typ, arr, n, bool(common))
            else:
                val = 0
                if init is not None:
                    val = self.conv(self.eval(init, scope), typ)
                v = Var(typ, val, None, bool(common))
            if name in self.params:
                self.apply_param(name, v)
            scope[name] = v

    def apply_param(self, name, v):
        p = self.params[name]
        self.used_params.add(name)
        if v.size is not None:
            vals = p if isinstance(p, list) else [p]
            for i, x in enumerate(vals[: v.size]):
                v.value[i] = self.conv((int(x), v.typ == "long"), v.typ)
        else:
            x = p[0] if isinstance(p, list) else p
            v.value = self.conv((int(x), v.typ == "long"), v.typ)

    def conv(self, tv, typ, where=None):
        val, _ = tv
        if typ == "long":
            w = wrap32(val)
            if w != val:
                self.flag("overflow", f"long overflow {val}")
            return w
        w = wrap16(val)
        if w != val:
            self.flag("narrowing", f"value {val} narrowed to int {w}")
        return w

    def lookup(self, name, scope):
        if name in scope:
            return scope[name]
        if name in self.vars:
            return self.vars[name]
        raise PPLRuntimeError(f"undefined variable {name} at {self.call_stack_where}")

    # expression evaluation --------------------------------------------------------
    def _c(self, units):
        if self.expr_costs:
            self.t += units * 0.1 * self.expr_scale

    def _acc(self, v):
        self._c(ACCESS_COST["common" if v.common else v.typ])

    def eval(self, e, scope):
        k = e[0]
        if k == "num":
            self._c(4 if e[2] else 2)
            return e[1], e[2]
        if k == "var":
            name = e[1]
            if name in ("us", "ms", "sec", "ss"):
                return {"ss": 0, "sec": 0, "ms": 1, "us": 2}[name], False
            if name in self.board_of and name not in scope and name not in self.vars:
                return name, False
            v = self.lookup(name, scope)
            if v.size is not None:
                return ("array", name), False
            self._acc(v)
            return v.value, v.typ == "long"
        if k == "index":
            v = self.lookup(e[1], scope)
            i, _ = self.eval(e[2], scope)
            if v.size is None or not 0 <= i < v.size:
                raise PPLRuntimeError(f"array index {e[1]}[{i}] out of bounds (size {v.size}) at {self.call_stack_where}")
            self._c(9 if v.typ == "long" else 5)
            return v.value[i], v.typ == "long"
        if k == "str":
            return e[1], False
        if k == "member":
            return self.member(e[1], e[2]), False
        if k == "input":
            return 0, False
        if k == "assign":
            val = self.eval(e[2], scope)
            tgt = e[1]
            if tgt[0] == "var":
                v = self.lookup(tgt[1], scope)
                self._acc(v)
                if val[1] and v.typ != "long":
                    self._c(1)
                elif not val[1] and v.typ == "long":
                    self._c(3)
                v.value = self.conv(val, v.typ)
                return v.value, v.typ == "long"
            v = self.lookup(tgt[1], scope)
            i, _ = self.eval(tgt[2], scope)
            self._c(9 if v.typ == "long" else 5)
            if not 0 <= i < v.size:
                raise PPLRuntimeError(f"array store {tgt[1]}[{i}] out of bounds (size {v.size}) at {self.call_stack_where}")
            v.value[i] = self.conv(val, v.typ)
            return v.value[i], v.typ == "long"
        if k == "un":
            val, lg = self.eval(e[2], scope)
            op = e[1]
            key = {"-": "neg", "!": "!", "~": "~"}.get(op)
            if key:
                self._c(OP_COST[key][0 if lg else 1])
            if op == "-":
                r = -val
            elif op == "+":
                r = val
            elif op == "!":
                return (0 if val else 1), False
            else:
                r = ~val
            return self.arith(r, lg), lg
        if k == "bin":
            op = e[1]
            if op in ("&&", "||"):
                self._c(OP_COST[op][1])
            if op == "&&":
                a, _ = self.eval(e[2], scope)
                if not a:
                    return 0, False
                b, _ = self.eval(e[3], scope)
                return (1 if b else 0), False
            if op == "||":
                a, _ = self.eval(e[2], scope)
                if a:
                    return 1, False
                b, _ = self.eval(e[3], scope)
                return (1 if b else 0), False
            a, la = self.eval(e[2], scope)
            b, lb = self.eval(e[3], scope)
            lg = la or lb
            if la != lb:
                self._c(3)
            self._c(OP_COST[op][0 if lg else 1])
            if op in ("==", "!=", "<", ">", "<=", ">="):
                r = {"==": a == b, "!=": a != b, "<": a < b, ">": a > b, "<=": a <= b, ">=": a >= b}[op]
                return (1 if r else 0), False
            if op == "+":
                r = a + b
            elif op == "-":
                r = a - b
            elif op == "*":
                r = a * b
            elif op == "/":
                if b == 0:
                    raise PPLRuntimeError(f"division by zero at {self.call_stack_where}")
                r = ctrunc_div(a, b)
            elif op == "%":
                if b == 0:
                    raise PPLRuntimeError(f"modulo by zero at {self.call_stack_where}")
                r = cmod(a, b)
            elif op == "&":
                r = a & b
            elif op == "|":
                r = a | b
            elif op == "^":
                r = a ^ b
            elif op == "<<":
                r = a << b
            elif op == ">>":
                r = a >> b
            else:
                raise PPLRuntimeError(op)
            return self.arith(r, lg), lg
        if k == "call":
            return self.call(e[1], e[2], scope)
        raise PPLRuntimeError(f"cannot evaluate {k}")

    def arith(self, r, lg):
        w = wrap32(r) if lg else wrap16(r)
        if w != r:
            self.flag("overflow", f"{'long' if lg else 'int'} arithmetic overflow {r}->{w}")
        return w

    def member(self, base, fields):
        if base == "grad":
            kind, name = fields
            if name not in self.grad.frames:
                raise PPLRuntimeError(f"unknown gradient frame {name}")
            addr, size, waits = self.grad.frames[name]
            return {"address": addr, "size": size, "waits": waits}[kind]
        # RF library alias
        if base in self.board_of:
            if fields == ["board1"]:
                return self.board_of[base]
            kind, name = fields
            if (base, name) not in self.rf_registry:
                raise PPLRuntimeError(f"unknown RF frame {base}.{name}")
            fid = self.rf_registry[(base, name)]
            if kind == "address":
                return fid
            if kind == "waits":
                return self.rf_frames[fid][3]
            if kind == "size":
                return len(self.rf_frames[fid][2])
        raise PPLRuntimeError(f"unknown member {base}.{fields}")

    # function calls -----------------------------------------------------------------
    def call(self, name, args, scope):
        if name in self.funcs:
            params, body = self.funcs[name]
            # CREATE_MATRIX's v18-measured 1356 clocks already cover its arguments
            # and wrapper; charge only the documented/measured call cost there.
            saved = self.expr_costs
            if name == "creatematrixtest":
                self.expr_costs = False
            try:
                vals = [self.eval(a, scope) for a in args]
                local = {}
                for (typ, pname), tv in zip(params, vals):
                    local[pname] = Var(typ, self.conv(tv, typ))
                r = self.run_code(name, body, local)
            finally:
                self.expr_costs = saved
            return (r if r is not None else 0), False
        fn = getattr(self, "b_" + name, None)
        if fn is None:
            raise PPLRuntimeError(f"unknown function {name} at {self.call_stack_where}")
        if name == "printf":
            vals = [self.eval(a, scope) for a in args]
        else:
            vals = [self.eval(a, scope) for a in args]
        cost = COSTS.get(name, 0.0)
        r = fn(*[v[0] for v in vals])
        if cost:
            self.advance(cost)
        if r is None:
            return 0, False
        if isinstance(r, tuple):
            return r
        return r, False

    # execution -------------------------------------------------------------------------
    def run(self):
        self.vars = {}
        for decl in self.globals_decl:
            if decl[0] == "decl":
                self.declare(decl, self.vars)
        params, body = self.funcs["main"]
        try:
            self.run_code("main", body, self.vars)
        except StopRun:
            pass
        self.grad.finish(self.t)
        unused = sorted(set(self.params) - self.used_params)
        return unused

    def run_code(self, fname, body, scope):
        if fname not in self.compiled:
            self.compiled[fname] = self.compile(body)
        code, labels = self.compiled[fname]
        pc = 0
        n = len(code)
        while pc < n:
            ins = code[pc]
            k = ins[0]
            self.stmt_count += 1
            if k == "expr":
                self.call_stack_where = ins[2]
                self.advance(self.stmt_cost)
                self.eval(ins[1], scope)
                pc += 1
            elif k == "decl":
                self.declare(ins, scope)
                pc += 1
            elif k == "jfalse":
                self.call_stack_where = ins[3]
                c, _ = self.eval(ins[1], scope)
                pc = pc + 1 if c else ins[2]
            elif k == "jmp":
                pc = ins[1]
            elif k == "jmp_label":
                lab = ins[1]
                if lab not in labels:
                    raise PPLRuntimeError(f"unknown label {lab}")
                if lab == "end":
                    self.misc_events.append(("end", self.t, ins[2]))
                pc = labels[lab]
                if lab == self.shot_label:
                    self.on_shot()
            elif k == "return":
                if ins[1] is None:
                    return None
                return self.eval(ins[1], scope)[0]
            elif k == "for_init":
                cnt, _ = self.eval(ins[2], scope)
                scope[ins[1]] = Var("int", cnt)
                pc += 1
            elif k == "for_test":
                v = scope[ins[1]]
                if v.value <= 0:
                    pc = ins[2]
                else:
                    v.value -= 1
                    pc += 1
            else:
                raise PPLRuntimeError(k)
            # fallthrough into the shot label
            if pc < n and fname == "main" and labels.get(self.shot_label) == pc and k != "jmp_label":
                self.on_shot()
        return None

    def on_shot(self):
        self.shots += 1
        self.misc_events.append(("shot", self.t, self.shots))
        if self.max_shots is not None and self.shots > self.max_shots:
            raise StopRun()

    def snapshot(self):
        out = {}
        for n in self.record_vars:
            v = self.vars.get(n)
            if v is not None and v.size is None:
                out[n] = v.value
        return out

    # ---------------------------------------------------------------- builtins
    def b_printf(self, fmt, *args):
        s = fmt
        try:
            pyfmt = re.sub(r"%l([di])", r"%\1", fmt)
            pyfmt = re.sub(r"%u", r"%d", pyfmt)
            s = pyfmt % tuple(args)
        except Exception:
            s = fmt + " " + repr(args)
        self.out.append((round(self.t, 1), s))

    def b___noop(self):
        pass

    def b_scale(self, a, b, c):
        if c == 0:
            raise PPLRuntimeError("scale by zero")
        r = ctrunc_div(a * b, c)
        if wrap16(r) != r:
            self.flag("overflow", f"scale({a},{b},{c})={r} exceeds int")
        return wrap16(r)

    def b_inttolong(self, a):
        return a, True

    def b_unsignedtolong(self, a):
        return a & 0xFFFF, True

    def b_starttimer(self):
        self.timer_ref = self.t

    def b_waittimer(self, ticks):
        if self.timer_ref is None:
            self.flag("timer", "waittimer without starttimer")
            return
        if not 0 <= ticks <= 65500:
            self.flag("timer_arg", f"waittimer argument {ticks} outside 0..65500 (16-bit narrowing)")
        ticks = ticks & 0xFFFF
        target = self.timer_ref + ticks / 10.0
        self.window_use.append((self.call_stack_where, ticks, (self.t - self.timer_ref) * 10.0))
        if self.t <= target + 1e-9:
            self.t = target
        else:
            k = math.ceil((self.t - target) / 5000.0 - 1e-12)
            self.flag("timer_overrun", f"waittimer({ticks}) overrun by {self.t-target:.2f} us -> +{k}x5 ms")
            self.t = target + 5000.0 * k
        self.misc_events.append(("waittimer", self.t, ticks))

    def b_gettimer(self):
        el = int(round((self.t - (self.timer_ref or self.t)) * 10))
        return wrap16(el & 0xFFFF)

    def b_delay(self, n, unit):
        if n > 65535:
            self.flag("timing", f"delay argument {n} exceeds 16 bits")
        if n < 0:
            self.flag("timing", f"delay with negative argument {n}")
            n = 0
        self.advance(n * {0: 1e6, 1: 1e3, 2: 1.0}[unit])

    def b_delay32(self, ticks):
        if ticks < 0:
            self.flag("timing", f"delay32 negative {ticks}")
            ticks = 0
        self.advance(ticks / 10.0)

    def b_acqpad(self, sp):
        return self.acqpad_ticks

    def b_hostrequest(self):
        return 1

    def b_killscan(self, x):
        raise StopRun()

    def b_pw(self, val, off, page):
        self.page[(page, off)] = val

    def b_pr(self, off, page):
        return self.page.get((page, off), 0)

    def b_userout(self, x):
        self.misc_events.append(("userout", self.t, x))

    def b_systemout(self, x):
        self.misc_events.append(("systemout", self.t, x))

    def b_ordertimetopos(self, n, inter, idx):
        return idx

    def b_batchtimetopos(self, bi, n, si, bs, idx):
        if n != 1:
            self.flag("assumption", "multi-slice position order not modeled")
        return idx

    def b_aqphase(self, n, pc):
        if pc == 2:
            return 2 * (n % 2)
        return 0

    def b_discard(self, n):
        self.discard_n = n

    def b_phase_increment(self, n):
        self.phase_inc = n if n != 0 else 400

    def b_phase(self, m):
        self.tx_phase = m

    def b_rphase(self, m):
        self.rx_phase = m

    def phase_deg(self, m):
        return (m * self.phase_inc * 0.225) % 360.0

    def b_setsync(self, x):
        pass

    def b_sync(self):
        self.sync_t = self.t

    def b_resync(self):
        self.misc_events.append(("resync", self.t, None))

    def b_frequency_buffer(self, n):
        self.freq_buf = n

    def b_frequency(self, mhz, khz, hz, rx):
        self.freq[self.freq_buf] = [(khz * 1000 + hz), 0, 0]
        self._send_tx()

    def b_offset_frequency(self, hz):
        f = self.freq.setdefault(self.freq_buf, [0, 0, 0])
        f[2] = hz

    def b_preset_frequency(self, *a):
        self.flag("unsupported", "preset_frequency")

    def b_reset_frequency(self):
        f = self.freq.setdefault(self.freq_buf, [0, 0, 0])
        f[1] = f[2]
        self._send_tx()

    def _send_tx(self):
        f = self.freq.get(self.freq_buf, [0, 0, 0])
        self.tx_freq_hz = f[0] + f[1]
        self.rx_latched_hz = f[0] + f[1]

    def b_initiate(self, sp):
        if self.adc_open is not None:
            self.flag("adc", "initiate while ADC open")
        self.adc_open = {"t_init": self.t, "sample_period_ticks": sp, "rx_phase_units": self.rx_phase,
                         "rx_phase_deg": self.phase_deg(self.rx_phase), "rx_freq_hz": self.rx_latched_hz,
                         "dummy_cycles": self.dummy_cycles, "Dummy_Cycles": self.dummy_cycles2,
                         "discard": self.discard_n, "vars": self.snapshot(), "sync_t": self.sync_t}

    def b_complete(self):
        self.advance(self.acqpad_ticks / 10.0)
        if self.adc_open is None:
            self.flag("adc", "complete without initiate")
            return
        a = self.adc_open
        a["t_complete"] = self.t
        self.adc.append(a)
        self.adc_open = None

    def b_dummy_cycles(self, x):
        # PPL identifiers are case-insensitive; dummy_cycles and Dummy_Cycles are
        # the same function. Track last value.
        self.dummy_cycles = x
        self.dummy_cycles2 = x

    # RF ------------------------------------------------------------------------------
    def b_set_board_multipliers(self, m1, m2, board):
        if not -2047 <= m1 <= 2047:
            self.flag("rf", f"board multiplier {m1} outside 12-bit range")
        self.rf.mul = m1

    def b_set3031address(self, addr, board):
        self.rf.addr = addr

    def b_set3031waits(self, w, board):
        self.rf.waits = w

    def b_append_boards_ready(self, b):
        pass

    def b_rfampon(self, x):
        self.rf.gate = True

    def b_rfon(self, level):
        self.rf.level = level
        self.rf.level_hist.append((self.t, level))

    def b_rfoff(self):
        self.rf.level = 0
        self.rf.gate = False
        self.rf.level_hist.append((self.t, 0))

    def b_mr3031_go(self):
        if self.rf.addr in self.rf_frames:
            alias, name, samples, fw = self.rf_frames[self.rf.addr]
            if self.rf.waits != fw:
                self.flag("rf", f"RF waits {self.rf.waits} differ from frame dwell {fw} for {name}")
            self.rf.events.append({"t_go": self.t + self.rf_latency, "frame": name, "library": alias,
                                   "mul": self.rf.mul, "waits": self.rf.waits, "n": len(samples),
                                   "duration_us": len(samples) * self.rf.waits * 0.1,
                                   "phase_units": self.tx_phase, "phase_deg": self.phase_deg(self.tx_phase),
                                   "tx_freq_hz": self.tx_freq_hz, "level": self.rf.level,
                                   "gate": self.rf.gate, "vars": self.snapshot()})
        else:
            self.rf.events.append({"t_go": self.t, "frame": f"setup:{self.rf.addr}", "mul": self.rf.mul,
                                   "phase_deg": self.phase_deg(self.tx_phase), "level": self.rf.level,
                                   "vars": self.snapshot()})

    def b_mr3031_setup(self, pf, what, a, b, c, mul):
        self.rf.addr = f"hard:{what}"
        self.rf.mul = mul

    # gradients ------------------------------------------------------------------------
    def b_mr3040_clock(self, c):
        if not 10 <= c <= 4096:
            self.flag("gradient", f"clock {c} outside 10..4096")
        self.grad.advance(self.t)
        self.grad.clock_hist.append((self.t, c))

    def b_mr3040_setlistaddress(self, a):
        self.grad.pointer = a & 0xFFFF
        self.grad.last_stop = None

    def b_mr3040_initlist(self):
        return self.grad.init_list()

    def b_mr3040_output(self, loop, addr, points, waits):
        self.grad.output(loop, addr, points, waits)

    def b_mr3040_hold(self, loop):
        self.grad.hold(loop)

    def b_mr3040_loopcount(self, n):
        self.grad.loop_count = n

    def b_mr3040_setlist(self, addr, mask):
        self.grad.set_list(addr & 0xFFFF, mask, self.t)

    def b_mr3040_start(self, mask):
        self.grad.start(mask, self.t + self.grad_latency)

    def b_mr3040_continue(self, mask):
        self.grad.cont(mask, self.t + self.grad_latency)

    def b_mr3040_selectmatrix(self, mid):
        self.grad.advance(self.t)
        self.grad.sel_hist.append((self.t, mid))

    def b_mr3040_createbasematrix(self, *a):
        if any(a[:3]):
            self.flag("orientation", "non-zero patient angles; logical-axis mapping only")
        return 0

    def b_mr3040_creatematrix(self, mid, d3, s, d2, p, d1, r, flip, za, ya, xa):
        if any((za, ya, xa)):
            self.flag("orientation", "oblique scan angles; logical-axis mapping only")
        for nm, v in (("s", s), ("p", p), ("r", r)):
            if not -32767 <= v <= 32767:
                self.flag("gradient", f"matrix {mid} {nm}={v} outside DAC range")
        sel = self.grad.selected_at(self.t)
        if mid == sel or (mid >= 256 and mid - 256 == sel):
            self.flag("matrix_active", f"CREATE_MATRIX({mid}) while matrix {sel} active")
        t_ready = self.t + COSTS["mr3040_creatematrix"] + 100.0
        self.grad.mats.setdefault(mid, []).append((self.t, t_ready, s, p, r))
        return 0
