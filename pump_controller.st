(* Three-pump batching controller, IEC 61131-3 Structured Text for OpenPLC Editor.
   Implements model/pump_controller.py. NOT YET COMPILED OR RUN: import it into
   OpenPLC Editor, fix any syntax warnings, then repeat the 5 scenarios in
   docs/test-log.md. Free alternative when RSLogix / TIA Portal are unavailable. *)
PROGRAM pump_station
  VAR
    START_PB    AT %IX0.0 : BOOL;
    STOP_OK     AT %IX0.1 : BOOL;   (* NC: TRUE = not pressed *)
    ESTOP_OK    AT %IX0.2 : BOOL;   (* NC: TRUE = healthy *)
    AUTO_SW     AT %IX0.3 : BOOL;
    LVL_LOW     AT %IX0.4 : BOOL;
    LVL_MID     AT %IX0.5 : BOOL;
    LVL_HIGH    AT %IX0.6 : BOOL;
    LVL_HIHI    AT %IX0.7 : BOOL;
    PUMP1_FB    AT %IX1.0 : BOOL;
    PUMP2_FB    AT %IX1.1 : BOOL;
    PUMP3_FB    AT %IX1.2 : BOOL;
    ALARM_RESET AT %IX1.3 : BOOL;
    MAN_P1      AT %IX1.4 : BOOL;
    MAN_P2      AT %IX1.5 : BOOL;
    MAN_P3      AT %IX1.6 : BOOL;
    PUMP1_RUN   AT %QX0.0 : BOOL;
    PUMP2_RUN   AT %QX0.1 : BOOL;
    PUMP3_RUN   AT %QX0.2 : BOOL;
    DRAIN_VALVE AT %QX0.3 : BOOL;
    ALARM_LAMP  AT %QX0.4 : BOOL;
    RUN_LAMP    AT %QX0.5 : BOOL;
  END_VAR
  VAR
    state        : INT := 0;          (* 0 IDLE, 1 FILL, 2 HOLD, 3 DRAIN, 4 FAULT *)
    lead         : INT := 0;          (* 0..2 = pump 1..3 *)
    batch_count  : INT := 0;
    batch_target : INT := 2;
    pump_fault   : ARRAY[0..2] OF BOOL;
    recipe_hold  : ARRAY[0..2] OF TIME := [T#3s, T#3s, T#3s];  (* indexed by batch *)
    alarm        : BOOL := FALSE;
    lead_fb      : BOOL;
    all_faulted  : BOOL;
    fb_switch    : BOOL := FALSE;     (* pulses to restart the feedback timer *)
    fb_tmr       : TON;
    hold_tmr     : TON;
    k            : INT;
    idx          : INT;
    found        : BOOL;
  END_VAR

  all_faulted := pump_fault[0] AND pump_fault[1] AND pump_fault[2];

  (* 1. Safety trips *)
  IF (NOT ESTOP_OK) OR LVL_HIHI THEN
    state := 4;
    alarm := TRUE;
  END_IF;

  IF state = 4 THEN
    (* 2. Fault: all off, leave only on reset with a safe plant *)
    PUMP1_RUN := FALSE; PUMP2_RUN := FALSE; PUMP3_RUN := FALSE; DRAIN_VALVE := FALSE;
    IF ALARM_RESET AND ESTOP_OK AND (NOT LVL_HIHI) THEN
      state := 0; alarm := FALSE; batch_count := 0;
      pump_fault[0] := FALSE; pump_fault[1] := FALSE; pump_fault[2] := FALSE;
    END_IF;
  ELSE
    IF ALARM_RESET THEN
      alarm := FALSE;
      pump_fault[0] := FALSE; pump_fault[1] := FALSE; pump_fault[2] := FALSE;
    END_IF;

    IF NOT AUTO_SW THEN
      (* 4. Manual mode *)
      state := 0;
      PUMP1_RUN := MAN_P1; PUMP2_RUN := MAN_P2; PUMP3_RUN := MAN_P3; DRAIN_VALVE := FALSE;
    ELSIF NOT STOP_OK THEN
      state := 0;
      PUMP1_RUN := FALSE; PUMP2_RUN := FALSE; PUMP3_RUN := FALSE; DRAIN_VALVE := FALSE;
    ELSE
      CASE state OF
        0: (* IDLE *)
          PUMP1_RUN := FALSE; PUMP2_RUN := FALSE; PUMP3_RUN := FALSE; DRAIN_VALVE := FALSE;
          IF START_PB THEN
            batch_count := 0;
            state := 1;
            fb_switch := TRUE;
          END_IF;

        1: (* FILL *)
          IF all_faulted THEN
            state := 4; alarm := TRUE;
            PUMP1_RUN := FALSE; PUMP2_RUN := FALSE; PUMP3_RUN := FALSE;
          ELSE
            (* skip a faulted lead: next healthy pump *)
            IF pump_fault[lead] THEN
              found := FALSE;
              FOR k := 1 TO 3 DO
                idx := (lead + k) MOD 3;
                IF (NOT found) AND (NOT pump_fault[idx]) THEN
                  lead := idx; found := TRUE;
                END_IF;
              END_FOR;
              fb_switch := TRUE;
            END_IF;

            PUMP1_RUN := (lead = 0);
            PUMP2_RUN := (lead = 1);
            PUMP3_RUN := (lead = 2);
            DRAIN_VALVE := FALSE;

            lead_fb := ((lead = 0) AND PUMP1_FB) OR ((lead = 1) AND PUMP2_FB) OR ((lead = 2) AND PUMP3_FB);
            fb_tmr(IN := (NOT lead_fb) AND (NOT fb_switch), PT := T#2s);
            IF fb_tmr.Q THEN
              pump_fault[lead] := TRUE;
              alarm := TRUE;
              fb_switch := TRUE;
            ELSE
              fb_switch := FALSE;
            END_IF;

            IF LVL_HIGH THEN
              PUMP1_RUN := FALSE; PUMP2_RUN := FALSE; PUMP3_RUN := FALSE;
              state := 2;
            END_IF;
          END_IF;

        2: (* HOLD: recipe time read by batch index (indirect addressing) *)
          PUMP1_RUN := FALSE; PUMP2_RUN := FALSE; PUMP3_RUN := FALSE;
          hold_tmr(IN := TRUE, PT := recipe_hold[batch_count MOD 3]);
          IF hold_tmr.Q THEN
            hold_tmr(IN := FALSE, PT := T#0s);
            state := 3;
          END_IF;

        3: (* DRAIN *)
          PUMP1_RUN := FALSE; PUMP2_RUN := FALSE; PUMP3_RUN := FALSE;
          DRAIN_VALVE := TRUE;
          IF NOT LVL_LOW THEN
            DRAIN_VALVE := FALSE;
            batch_count := batch_count + 1;
            IF NOT all_faulted THEN
              found := FALSE;
              FOR k := 1 TO 3 DO
                idx := (lead + k) MOD 3;
                IF (NOT found) AND (NOT pump_fault[idx]) THEN
                  lead := idx; found := TRUE;   (* floating master rotation *)
                END_IF;
              END_FOR;
            END_IF;
            IF batch_count >= batch_target THEN
              state := 0;
            ELSE
              state := 1;
              fb_switch := TRUE;
            END_IF;
          END_IF;
      END_CASE;
    END_IF;
  END_IF;

  ALARM_LAMP := alarm;
  RUN_LAMP := (state = 1) OR (state = 2) OR (state = 3);
END_PROGRAM

CONFIGURATION Config0
  RESOURCE Res0 ON PLC
    TASK task0(INTERVAL := T#20ms, PRIORITY := 0);
    PROGRAM instance0 WITH task0 : pump_station;
  END_RESOURCE
END_CONFIGURATION
