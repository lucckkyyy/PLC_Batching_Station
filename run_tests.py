#!/usr/bin/env python3
"""Scenario tests for the pump controller model, with a simple tank/pump simulation.

Usage: python3 model/run_tests.py
These tests exercise the reference model in software. They are not a run on
RSLogix or TIA Portal; repeat the same scenarios there and record those results.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from pump_controller import (DRAIN, FAULT, FILL, HOLD, IDLE, STATE_NAMES,  # noqa: E402
                             FB_TIMEOUT, Inputs, PumpController)

DT = 0.1
FB_DELAY = 0.5  # pump feedback arrives this long after the contactor is commanded


class Sim:
    def __init__(self, **kw):
        self.ctrl = PumpController(**kw)
        self.inp = Inputs()
        self.level = 0.0
        self.t = 0.0
        self.on_time = [0.0, 0.0, 0.0]
        self.failed = set()       # pumps that never give feedback
        self.force_hihi = False
        self.ran = set()          # pumps that actually ran with feedback
        self.leads_at_fill = []
        self.out = self.ctrl._outputs()
        self._prev_state = IDLE

    def step(self, start=False, reset=False):
        c, i = self.ctrl, self.inp
        for k in range(3):
            self.on_time[k] = self.on_time[k] + DT if self.out["pumps"][k] else 0.0
            i.fb[k] = (k not in self.failed) and self.on_time[k] >= FB_DELAY
            if i.fb[k]:
                self.ran.add(k)
        flow = 10.0 * sum(i.fb) - (20.0 if self.out["drain"] else 0.0)
        self.level = min(100.0, max(0.0, self.level + flow * DT))
        i.lvl_low, i.lvl_mid, i.lvl_high = self.level >= 10, self.level >= 50, self.level >= 90
        i.lvl_hihi = self.force_hihi or self.level >= 98
        i.start, i.reset = start, reset
        self.out = c.scan(i, DT)
        if self.out["state"] == FILL and self._prev_state != FILL:
            self.leads_at_fill.append(c.lead)
        self._prev_state = self.out["state"]
        self.t += DT

    def run_until(self, cond, limit=300.0):
        while not cond() and self.t < limit:
            self.step()
        return cond()


def t1_normal_batch():
    s = Sim(batch_target=2, recipe_hold=(3.0, 3.0))
    s.step(start=True)
    done = s.run_until(lambda: s.ctrl.state == IDLE and s.ctrl.batch_count == 2)
    ok = (done and s.ctrl.batch_count == 2 and s.leads_at_fill == [0, 1]
          and not any(s.out["pumps"]) and not s.out["drain"] and not s.out["alarm"])
    return ok, f"batches={s.ctrl.batch_count}, lead per batch={s.leads_at_fill}, finished at t={s.t:.1f}s, alarm={s.out['alarm']}"


def t2_pump_failure_standby():
    s = Sim(batch_target=1, recipe_hold=(2.0,))
    s.failed.add(0)
    s.step(start=True)
    t_cmd = s.t
    s.run_until(lambda: s.ctrl.pump_fault[0])
    t_switch = s.t - t_cmd
    s.run_until(lambda: s.ctrl.state == IDLE and s.ctrl.batch_count == 1)
    ok = (s.ctrl.pump_fault[0] and s.out["alarm"] and 1 in s.ran and 0 not in s.ran
          and s.ctrl.batch_count == 1 and FB_TIMEOUT <= t_switch <= FB_TIMEOUT + 0.5)
    return ok, (f"pump1 faulted after {t_switch:.1f}s (timeout {FB_TIMEOUT}s), standby pumps that ran={sorted(p+1 for p in s.ran)}, "
                f"batch completed={s.ctrl.batch_count == 1}, alarm latched={s.out['alarm']}")


def t3_estop():
    s = Sim(batch_target=2)
    s.step(start=True)
    s.run_until(lambda: s.ctrl.state == FILL and s.t > 2.0)
    s.inp.estop_ok = False
    s.step()
    tripped = s.ctrl.state == FAULT and not any(s.out["pumps"]) and not s.out["drain"] and s.out["alarm"]
    s.inp.estop_ok = True
    for _ in range(10):
        s.step()
    stays = s.ctrl.state == FAULT  # must not self-restart without reset
    s.step(reset=True)
    cleared = s.ctrl.state == IDLE and not s.out["alarm"]
    return tripped and stays and cleared, f"tripped={tripped}, held after E-stop restored={stays}, cleared by reset={cleared}"


def t4_high_high():
    s = Sim(batch_target=1)
    s.step(start=True)
    s.run_until(lambda: s.ctrl.state == FILL and s.t > 1.0)
    s.force_hihi = True
    s.step()
    tripped = s.ctrl.state == FAULT and not any(s.out["pumps"]) and s.out["alarm"]
    s.step(reset=True)
    still = s.ctrl.state == FAULT  # reset refused while HIHI present
    s.force_hihi = False
    s.level = 20.0
    s.step(reset=True)
    cleared = s.ctrl.state == IDLE
    return tripped and still and cleared, f"tripped={tripped}, reset refused while HIHI active={still}, cleared after HIHI gone={cleared}"


def t5_manual_mode():
    s = Sim()
    s.inp.auto = False
    s.step(start=True)
    no_auto = s.ctrl.state == IDLE and not any(s.out["pumps"])
    s.inp.man[1] = True
    s.step()
    pump2_on = s.out["pumps"] == [False, True, False]
    s.inp.man[1] = False
    s.step()
    off = not any(s.out["pumps"])
    return no_auto and pump2_on and off, f"start ignored in manual={no_auto}, pump2 follows its button={pump2_on}, stops on release={off}"


def t6_all_pumps_failed():
    s = Sim(batch_target=1)
    s.failed.update({0, 1, 2})
    s.step(start=True)
    s.run_until(lambda: s.ctrl.state == FAULT, limit=30.0)
    ok = s.ctrl.state == FAULT and not any(s.out["pumps"]) and s.out["alarm"]
    return ok, f"fault after {s.t:.1f}s with no healthy pump, outputs off={not any(s.out['pumps'])}"


TESTS = [
    ("1 Normal batch (2 batches, lead rotates)", t1_normal_batch),
    ("2 Pump failure -> standby switchover", t2_pump_failure_standby),
    ("3 E-stop trips and holds until reset", t3_estop),
    ("4 High-high level alarm latches", t4_high_high),
    ("5 Manual mode", t5_manual_mode),
    ("6 All pumps failed -> fault (extra)", t6_all_pumps_failed),
]

if __name__ == "__main__":
    bad = 0
    for name, fn in TESTS:
        ok, detail = fn()
        bad += not ok
        print(f"{'PASS' if ok else 'FAIL'}  {name}\n      {detail}")
    print(f"\n{len(TESTS) - bad}/{len(TESTS)} scenarios passed")
    sys.exit(1 if bad else 0)
