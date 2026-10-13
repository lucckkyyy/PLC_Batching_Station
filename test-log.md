# Test Log

Three columns, three different kinds of evidence. Only claim a platform on your resume once its column is filled in with real results.

| # | Scenario | Expected | Software model | Rockwell RSLogix | Siemens S7-PLCSIM |
|---|---|---|---|---|---|
| 1 | Normal batch, 2 batches | Fill, hold, drain, count +1 per batch, lead rotates 1 then 2 | PASS | TBD | TBD |
| 2 | Pump 1 fails to give feedback | Alarm latches, standby pump takes over after the 2 s timeout, batch completes | PASS (switchover at 2.0 s) | TBD | TBD |
| 3 | E-stop opened mid-fill | All outputs off, fault latched, stays until reset | PASS | TBD | TBD |
| 4 | High-high level | Pumps off, alarm latched, reset refused while level high | PASS | TBD | TBD |
| 5 | Manual mode | Start ignored, pumps follow manual buttons only | PASS | TBD | TBD |
| 6 | All pumps failed (extra) | Fault, outputs off | PASS | TBD | TBD |

Software model results come from `python3 model/run_tests.py` (6/6 passed).

## How to run each scenario by hand on a PLC (or simulator)

1. Set AUTO, STOP_OK, ESTOP_OK true. Pulse START_PB. Watch the state bits.
2. Pump failure: do not turn on the pump 1 feedback bit. Expect switchover after the timeout.
3. E-stop: set ESTOP_OK false mid-fill.
4. High-high: set LVL_HIHI true mid-fill, then try reset while it is still true.
5. Manual: set AUTO_SW false, pulse START_PB (nothing should happen), then press MAN_P2.

## Siemens port checks

| # | Function | Result |
|---|---|---|
| 1 | E-stop | TBD |
| 2 | Fill/drain control | TBD |
| 3 | Pump rotation | TBD |
