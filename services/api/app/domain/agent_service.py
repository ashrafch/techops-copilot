from typing import Literal

Priority = Literal["P1", "P2", "P3", "P4"]


def priority_from_signal(event_type: str, severity: str) -> tuple[Priority, str]:
    severity_map: dict[str, Priority] = {
        "critical": "P1",
        "high": "P2",
        "medium": "P3",
        "low": "P4",
    }
    event_type_norm = event_type.strip().upper()
    severity_norm = severity.strip().lower()
    base = severity_map.get(severity_norm, "P3")

    # Domain rules for automation/logistics incidents.
    if event_type_norm in {"CONVEYOR_JAM", "ROBOT_STALL", "SAFETY_STOP"}:
        return "P1", f"forced_by_event_type:{event_type_norm}"
    if event_type_norm in {"PALLETIZER_WARNING", "FORKLIFT_BATTERY_LOW"} and base == "P1":
        return "P2", "downgraded_to_reduce_false_critical"

    return base, f"derived_from_severity:{severity_norm or 'default'}"


def recommend_playbook(event_type: str, severity: str) -> dict[str, str]:
    event_type_norm = event_type.strip().upper()
    severity_norm = severity.strip().lower()

    if event_type_norm == "CONVEYOR_JAM":
        return {
            "team": "automation-maintenance",
            "runbook": "RB-LOG-001",
            "action": "Isolate conveyor lane, clear jam, restart PLC sequence.",
        }
    if event_type_norm == "ROBOT_STALL":
        return {
            "team": "robotics-support",
            "runbook": "RB-AUTO-014",
            "action": "Check E-stop chain, inspect cell safety relays, recalibrate robot.",
        }
    if event_type_norm == "FORKLIFT_BATTERY_LOW":
        return {
            "team": "warehouse-ops",
            "runbook": "RB-LOG-009",
            "action": "Swap battery at nearest station and reroute picking queue.",
        }

    return {
        "team": "operations-dispatch",
        "runbook": "RB-GEN-000",
        "action": f"Triage incident with severity {severity_norm or 'medium'} and dispatch owner.",
    }
