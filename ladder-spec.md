# Rockwell ladder specification (RSLogix 500 style)

Rung-by-rung build sheet derived from `model/pump_controller.py`. **This has not been entered into RSLogix yet.** Enter it, run the five scenarios in `docs/test-log.md`, and fix anything that differs from your course's addressing and instruction conventions (check your text for the exact indirect-addressing syntax).

Mnemonics: XIC = examine if closed (true), XIO = examine if open (false), OTE/OTL/OTU = output energize/latch/unlatch.

## Address map

| Address | Tag | Meaning |
|---|---|---|
| I:1/0 | START_PB | Start (NO) |
| I:1/1 | STOP_OK | Stop (NC, true = not pressed) |
| I:1/2 | ESTOP_OK | E-stop (NC, true = healthy) |
| I:1/3 | AUTO_SW | Auto = true, manual = false |
| I:1/4 to 1/7 | LVL_LOW, MID, HIGH, HIHI | Level sensors (true = covered) |
| I:1/8 to 1/10 | PUMP1_FB to PUMP3_FB | Pump run feedback |
| I:1/11 | ALARM_RESET | Reset pushbutton |
| I:1/12 to 1/14 | MAN_P1 to MAN_P3 | Manual pump buttons |
| O:2/0 to 2/2 | PUMP1_RUN to PUMP3_RUN | Pump contactors |
| O:2/3 | DRAIN_VALVE | Drain valve |
| O:2/4 | ALARM_LAMP | Alarm lamp |
| O:2/5 | RUN_LAMP | Run lamp |
| B3:0/0 to 0/4 | S_IDLE, S_FILL, S_HOLD, S_DRAIN, S_FAULT | State bits (exactly one set) |
| B3:1/0 | ALARM | Latched alarm |
| B3:1/1 to 1/3 | PF1 to PF3 | Latched pump faults |
| N7:0 | LEAD | Lead pump index, 0 to 2 |
| N7:1 | BATCH_CNT | Completed batches |
| N7:2 | BATCH_TGT | Batch target |
| N8:0 to N8:2 | RECIPE | Hold-time presets (seconds) per batch, read by index |
| T4:0 | HOLD_TMR | Hold timer, 1 s base |
| T4:1 | FB_TMR | Feedback timeout, 1 s base, preset 2 |

## Rungs

**R0 Safety trip.** Branch: XIO I:1/2 OR XIC I:1/7 then OTL B3:0/4, OTL B3:1/0, OTU B3:0/0, OTU B3:0/1, OTU B3:0/2, OTU B3:0/3. (E-stop opened or overfill: fault, alarm latched, other states cleared.)

**R1 Fault reset.** XIC B3:0/4, XIC I:1/11, XIC I:1/2, XIO I:1/7 then OTU B3:0/4, OTU B3:1/0, OTU B3:1/1, OTU B3:1/2, OTU B3:1/3, OTL B3:0/0, CLR N7:1.

**R2 Alarm acknowledge outside a fault.** XIO B3:0/4, XIC I:1/11 then OTU B3:1/0, OTU B3:1/1, OTU B3:1/2, OTU B3:1/3.

**R3 Start.** XIC B3:0/0, XIC I:1/3, XIC I:1/1, XIC I:1/0 then OTU B3:0/0, OTL B3:0/1, CLR N7:1, RES T4:1.

**R4 Stop returns to idle.** XIC I:1/3, XIO I:1/1, XIO B3:0/4 then OTL B3:0/0, OTU B3:0/1, OTU B3:0/2, OTU B3:0/3.

**R5 All pumps faulted.** XIC B3:1/1, XIC B3:1/2, XIC B3:1/3, XIC B3:0/1 then OTL B3:0/4, OTL B3:1/0, OTU B3:0/1.

**R6 Skip a faulted lead.** XIC B3:0/1 with a branch: (EQU N7:0 0 and XIC B3:1/1) OR (EQU N7:0 1 and XIC B3:1/2) OR (EQU N7:0 2 and XIC B3:1/3), then ADD N7:0 1 N7:0, RES T4:1. Follow with a rung: GEQ N7:0 3 then CLR N7:0. (This one rung covers live switchover and rotation onto a bad pump.)

**R7 Pump commands.** XIC B3:0/1 with EQU N7:0 0 then OTE O:2/0. Same for N7:0 = 1 then O:2/1, and N7:0 = 2 then O:2/2. In manual mode, XIO I:1/3 XIC I:1/12 then OTE O:2/0 (and I:1/13 to O:2/1, I:1/14 to O:2/2).

**R8 Feedback timeout.** XIC B3:0/1 with a branch for the lead pump's feedback: (EQU N7:0 0 and XIO I:1/8) OR (EQU N7:0 1 and XIO I:1/9) OR (EQU N7:0 2 and XIO I:1/10), then TON T4:1 (preset 2, base 1 s).

**R9 Latch pump fault on timeout.** XIC T4:1/DN with EQU N7:0 0 then OTL B3:1/1 (N7:0 = 1 then B3:1/2, N7:0 = 2 then B3:1/3). Also OTL B3:1/0 (alarm).

**R10 Fill complete.** XIC B3:0/1, XIC I:1/6 then OTU B3:0/1, OTL B3:0/2, RES T4:0, MOV N8:[N7:1] T4:0.PRE (indirect addressing: preset read from the recipe table by batch index).

**R11 Hold timer.** XIC B3:0/2 then TON T4:0 (base 1 s, preset loaded in R10).

**R12 Hold done.** XIC T4:0/DN then OTU B3:0/2, OTL B3:0/3.

**R13 Drain.** XIC B3:0/3 then OTE O:2/3.

**R14 Drain complete.** XIC B3:0/3, XIO I:1/4 then ADD N7:1 1 N7:1, ADD N7:0 1 N7:0 (rotate lead), OTU B3:0/3. Follow with: GEQ N7:1 N7:2 then OTL B3:0/0, else (LES N7:1 N7:2) then OTL B3:0/1, RES T4:1. Keep the lead-wrap rung from R6 after this one.

**R15 Lamps.** XIC B3:1/0 then OTE O:2/4. Branch XIC B3:0/1 OR XIC B3:0/2 OR XIC B3:0/3 then OTE O:2/5.

**R16 Fault outputs off.** XIC B3:0/4 then clear O:2/0 to O:2/3 (or use the fault bit as a series condition on R7 and R13).

Notes:
- RSLogix scan order matters for latches. Place R0 and R5 at the top and the output rungs (R7, R13, R15) at the bottom.
- The software model uses a 0.1 s scan and 2.0 s feedback timeout. A 1 s timer base gives 1 s resolution, so test the switchover with a 2 s preset and expect it to land between 2 and 3 seconds.
