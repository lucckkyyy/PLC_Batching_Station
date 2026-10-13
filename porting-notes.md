# Siemens port notes (TIA Portal, S7-1200 + S7-PLCSIM)

Status: **not started.** Port only the three core functions you plan to claim: E-stop, fill/drain control, and pump rotation.

## Concept map from the Rockwell build

| Rockwell (RSLogix 500) | Siemens (TIA Portal) |
|---|---|
| I:1/0, O:2/0 file addressing | Symbolic tags in a tag table (`%I0.0`, `%Q0.0`) |
| XIC / XIO / OTE | Normally open / closed contact, coil |
| OTL / OTU | Set (S) / Reset (R) coil |
| TON T4:0 (1 s base, DN bit) | IEC TON in an instance DB (`.Q`, `.ET`, time as `T#2s`) |
| Counter / ADD N7:1 | CTU or ADD instruction on an INT tag |
| EQU / GEQ / LES | `==`, `>=`, `<` comparison boxes |
| Indirect `N8:[N7:1]` | Array in a global DB read with a variable index (`"Recipe".Hold[#batch]`) |
| B3 state bits | A single `State` INT in a DB, compared per rung (or an SCL `CASE`) |

## Suggested approach
1. Create an S7-1200 project, define the tag table from `rockwell/ladder-spec.md` (same names).
2. Build the state logic in one FB (ladder or SCL). The OpenPLC Structured Text in `st/pump_controller.st` is close to SCL and is a good starting point for the CASE block.
3. Simulate with S7-PLCSIM and a watch table. Drive the inputs by hand and reproduce scenarios 1 to 5 from `docs/test-log.md`.
4. Record what differs (addressing, timer behaviour, scan order) in this file. That comparison is the interesting part for an interview.

## Port checklist
- [ ] E-stop trips to FAULT, outputs off, holds until reset
- [ ] Fill/drain control with level sensors
- [ ] Lead/lag rotation each batch
