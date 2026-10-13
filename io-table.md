# I/O Table

Addresses are RSLogix 500 style. The full address map, including internal bits, integers, and timers, is in `rockwell/ladder-spec.md`. Siemens uses the same tag names with `%I`/`%Q` addresses.

## Inputs

| Address | Tag | Description |
|---|---|---|
| I:1/0 | START_PB | Start pushbutton (NO) |
| I:1/1 | STOP_OK | Stop pushbutton (NC, true = not pressed) |
| I:1/2 | ESTOP_OK | Emergency stop (NC, true = healthy) |
| I:1/3 | AUTO_SW | Auto/manual selector |
| I:1/4 | LVL_LOW | Tank not empty |
| I:1/5 | LVL_MID | Mid level |
| I:1/6 | LVL_HIGH | Tank full |
| I:1/7 | LVL_HIHI | Overfill alarm |
| I:1/8 to I:1/10 | PUMP1_FB to PUMP3_FB | Pump run feedback |
| I:1/11 | ALARM_RESET | Reset pushbutton |
| I:1/12 to I:1/14 | MAN_P1 to MAN_P3 | Manual pump buttons |

## Outputs

| Address | Tag | Description |
|---|---|---|
| O:2/0 to O:2/2 | PUMP1_RUN to PUMP3_RUN | Pump contactors |
| O:2/3 | DRAIN_VALVE | Drain valve |
| O:2/4 | ALARM_LAMP | Alarm indicator |
| O:2/5 | RUN_LAMP | Running indicator |

## Data

| Item | Purpose |
|---|---|
| N8:0 to N8:2 | Recipe: hold time per batch, read by index (indirect addressing) |
| N7:1 / N7:2 | Batch count / batch target |
| N7:0 | Lead pump index (rotates each batch) |
| B3:1/1 to B3:1/3 | Latched pump faults |
