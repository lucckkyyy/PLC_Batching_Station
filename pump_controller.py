"""Reference model of the three-pump batching controller (one PLC scan per call).

This is the specification in executable form. The Rockwell rungs, the Siemens port
and the OpenPLC Structured Text program all implement this same behaviour.

Sensor convention: a level sensor is TRUE while the liquid covers it.
  LVL_LOW  : tank not empty        LVL_HIGH : tank full (stop filling)
  LVL_HIHI : overfill alarm        LVL_MID  : informational
Stop and E-stop are normally-closed contacts: TRUE means healthy / not pressed.
"""
from dataclasses import dataclass, field

IDLE, FILL, HOLD, DRAIN, FAULT = range(5)
STATE_NAMES = ["IDLE", "FILL", "HOLD", "DRAIN", "FAULT"]
FB_TIMEOUT = 2.0  # seconds a commanded pump may run without feedback


@dataclass
class Inputs:
    start: bool = False
    stop_ok: bool = True
    estop_ok: bool = True
    auto: bool = True
    lvl_low: bool = False
    lvl_mid: bool = False
    lvl_high: bool = False
    lvl_hihi: bool = False
    fb: list = field(default_factory=lambda: [False, False, False])
    reset: bool = False
    man: list = field(default_factory=lambda: [False, False, False])


class PumpController:
    def __init__(self, batch_target=2, recipe_hold=(3.0, 3.0, 3.0)):
        self.batch_target = batch_target
        self.recipe_hold = list(recipe_hold)  # hold time per batch, read by index (indirect addressing)
        self.state = IDLE
        self.lead = 0
        self.batch_count = 0
        self.pump_fault = [False, False, False]
        self.alarm = False
        self.fb_timer = 0.0
        self.hold_timer = 0.0
        self.pumps = [False, False, False]
        self.drain = False

    # ---- helpers ----
    def _all_faulted(self):
        return all(self.pump_fault)

    def _advance_lead(self):
        """Move the lead to the next healthy pump (wraps). Caller checks not all faulted."""
        for k in range(1, 4):
            idx = (self.lead + k) % 3
            if not self.pump_fault[idx]:
                self.lead = idx
                return

    def _all_off(self):
        self.pumps = [False, False, False]
        self.drain = False

    # ---- one scan ----
    def scan(self, i: Inputs, dt: float):
        # 1. Safety trips: E-stop opened or overfill. Latch the fault and alarm.
        if (not i.estop_ok) or i.lvl_hihi:
            self.state = FAULT
            self.alarm = True

        # 2. Fault state: everything off, leaves only on reset with a safe plant.
        if self.state == FAULT:
            self._all_off()
            if i.reset and i.estop_ok and not i.lvl_hihi:
                self.state = IDLE
                self.alarm = False
                self.pump_fault = [False, False, False]
                self.batch_count = 0
                self.fb_timer = self.hold_timer = 0.0
            return self._outputs()

        # 3. Alarm acknowledge outside a fault (clears a latched pump alarm)
        if i.reset:
            self.alarm = False
            self.pump_fault = [False, False, False]

        # 4. Manual mode: operator commands pumps directly, sequence is held in IDLE.
        if not i.auto:
            self.state = IDLE
            self.drain = False
            self.pumps = [bool(m) for m in i.man]
            self.fb_timer = self.hold_timer = 0.0
            return self._outputs()

        # 5. Stop pushbutton returns the sequence to IDLE.
        if not i.stop_ok:
            self.state = IDLE
            self._all_off()
            return self._outputs()

        # 6. Automatic sequence.
        if self.state == IDLE:
            self._all_off()
            if i.start:
                self.batch_count = 0
                if self.pump_fault[self.lead]:
                    self._advance_lead()
                self.state = FILL
                self.fb_timer = 0.0

        elif self.state == FILL:
            if self._all_faulted():
                self.state = FAULT
                self.alarm = True
                self._all_off()
                return self._outputs()
            # skip a faulted lead (covers rotation onto a bad pump and live switchover)
            if self.pump_fault[self.lead]:
                self._advance_lead()
                self.fb_timer = 0.0
            self.pumps = [k == self.lead for k in range(3)]
            self.drain = False
            if i.fb[self.lead]:
                self.fb_timer = 0.0
            else:
                self.fb_timer += dt
                if self.fb_timer >= FB_TIMEOUT:
                    self.pump_fault[self.lead] = True  # latched until reset
                    self.alarm = True
                    self.fb_timer = 0.0
            if i.lvl_high:
                self.pumps = [False, False, False]
                self.state = HOLD
                self.hold_timer = 0.0

        elif self.state == HOLD:
            self._all_off()
            self.hold_timer += dt
            if self.hold_timer >= self.recipe_hold[self.batch_count % len(self.recipe_hold)]:
                self.state = DRAIN

        elif self.state == DRAIN:
            self.pumps = [False, False, False]
            self.drain = True
            if not i.lvl_low:  # tank drained below the low sensor
                self.drain = False
                self.batch_count += 1
                if not self._all_faulted():
                    self._advance_lead()  # floating master: rotate lead every batch
                if self.batch_count >= self.batch_target:
                    self.state = IDLE
                else:
                    self.state = FILL
                    self.fb_timer = 0.0

        return self._outputs()

    def _outputs(self):
        return {
            "pumps": list(self.pumps),
            "drain": self.drain,
            "alarm": self.alarm,
            "run": self.state in (FILL, HOLD, DRAIN),
            "state": self.state,
        }
