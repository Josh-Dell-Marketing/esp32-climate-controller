"""Write the KiCad project file (net classes, board rules) and custom DRC rules."""
import json
import os

import design as D

HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.dirname(HERE)


def netclass(name, clearance, track, via_d, via_drill, priority):
    return {
        "name": name, "clearance": clearance, "track_width": track,
        "via_diameter": via_d, "via_drill": via_drill,
        "microvia_diameter": 0.3, "microvia_drill": 0.1,
        "diff_pair_gap": 0.25, "diff_pair_via_gap": 0.25, "diff_pair_width": 0.2,
        "wire_width": 6, "bus_width": 12, "line_style": 0,
        "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)",
        "priority": priority,
    }


def write_project():
    patterns = []
    for n in D.MAINS_NETS:
        patterns.append({"netclass": "Mains", "pattern": f"*{n}"})
    for n in ["VIN_RAW", "VIN_FUSED"] + D.COIL_NETS:
        patterns.append({"netclass": "Power", "pattern": f"*{n}"})
    for n in ["+5V", "GND"]:
        patterns.append({"netclass": "Power", "pattern": n})

    pro = {
        "meta": {"filename": f"{D.PROJECT}.kicad_pro", "version": 3},
        "board": {
            "design_settings": {
                "defaults": {
                    "board_outline_line_width": 0.1, "copper_line_width": 0.2,
                    "copper_text_size_h": 1.5, "copper_text_size_v": 1.5, "copper_text_thickness": 0.3,
                    "silk_line_width": 0.12, "silk_text_size_h": 1.0, "silk_text_size_v": 1.0,
                    "silk_text_thickness": 0.15,
                },
                "rules": {
                    "min_clearance": 0.2, "min_track_width": 0.25, "min_via_diameter": 0.6,
                    "min_via_annular_width": 0.13, "min_through_hole_diameter": 0.3,
                    "min_hole_clearance": 0.25, "min_hole_to_hole": 0.25,
                    "min_copper_edge_clearance": 0.5, "min_silk_clearance": 0.0,
                    "min_text_height": 0.8, "min_text_thickness": 0.08,
                    "solder_mask_to_copper_clearance": 0.0,
                },
                "rule_severities": {
                    "silk_overlap": "warning", "silk_over_copper": "warning",
                    "silk_edge_clearance": "warning", "lib_footprint_mismatch": "warning",
                    "lib_footprint_issues": "warning", "text_height": "warning",
                },
            },
        },
        "net_settings": {
            "classes": [
                netclass("Default", 0.25, D.WIDTH["signal"], 0.8, 0.4, 2147483647),
                netclass("Mains", 2.0, D.WIDTH["mains"], 1.2, 0.6, 0),
                netclass("Power", 0.3, 0.8, 1.0, 0.5, 1),
            ],
            "meta": {"version": 4},
            "net_colors": None,
            "netclass_assignments": None,
            "netclass_patterns": patterns,
        },
        "libraries": {"pinned_footprint_libs": [], "pinned_symbol_libs": []},
        "pcbnew": {"page_layout_descr_file": ""},
        "schematic": {"legacy_lib_dir": "", "legacy_lib_list": []},
        "sheets": [],
        "text_variables": {},
    }
    with open(os.path.join(HW, f"{D.PROJECT}.kicad_pro"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(pro, f, indent=2)
        f.write("\n")

    rules = """(version 1)

# Mains (relay contact) copper must stay well away from everything else.
# Note: KiCad ignores '!B.hasNetclass(...)' here - use B.NetClass != 'Mains'.
(rule "mains_to_low_voltage_clearance"
  (constraint clearance (min 3.0mm))
  (condition "A.NetClass == 'Mains' && B.NetClass != 'Mains'"))

(rule "mains_to_low_voltage_creepage"
  (constraint creepage (min 4.0mm))
  (condition "A.NetClass == 'Mains' && B.NetClass != 'Mains'"))

# Between different mains nets (e.g. COM and NO across an open contact,
# or two channels on different circuits).
(rule "mains_to_mains_clearance"
  (constraint clearance (min 2.0mm))
  (condition "A.NetClass == 'Mains' && B.NetClass == 'Mains'"))

# Every ground pad is also joined by a routed track, so one pour spoke is enough.
(rule "ground_pad_spokes"
  (constraint min_resolved_spokes 1)
  (condition "A.Type == 'Pad' && A.NetName == 'GND'"))

# Metal mounting screws: keep mains copper away from the holes.
(rule "mains_to_mounting_hole"
  (constraint hole_clearance (min 3.0mm))
  (condition "A.NetClass == 'Mains' && B.Type == 'Pad' && B.Pad_Type == 'NPTH, mechanical'"))
"""
    with open(os.path.join(HW, f"{D.PROJECT}.kicad_dru"), "w", encoding="utf-8", newline="\n") as f:
        f.write(rules)


if __name__ == "__main__":
    write_project()
    print("wrote project and rules")
