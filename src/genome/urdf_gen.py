"""URDF/YAML generation from morphology parameters.

Setup-phase implementation: generates a URDF/YAML pair from a
``MorphologyGenome`` by scaling PyFlyt's built-in fixedwing template.

NOTE: The full template-based scaling logic is deferred to the
experiment phase. For the setup phase we provide:

- Model directory creation
- Default-model copy (no scaling)
- Functional stub with clear TODO markers
"""
from __future__ import annotations

import json
import os
import shutil
import xml.etree.ElementTree as ET
from typing import Any, Dict, Optional

import numpy as np
import yaml

from .morphology import MorphologyGenome


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

def model_dir_for(
    base_models_dir: str,
    experiment_id: str,
    generation: int,
    individual: int,
) -> str:
    """Return and create the per-individual model directory.

    Layout: models/<experiment_id>/gen<NNN>/ind<NNN>/
    """
    path = os.path.join(
        base_models_dir,
        experiment_id,
        f"gen{generation:03d}",
        f"ind{individual:03d}",
    )
    os.makedirs(path, exist_ok=True)
    return path


# ---------------------------------------------------------------------------
# URDF / YAML generation
# ---------------------------------------------------------------------------

def generate_model_files(
    morphology: MorphologyGenome,
    out_dir: str,
    drone_model: str = "fixedwing",
    template_dir: Optional[str] = None,
) -> Dict[str, str]:
    """Generate scaled ``drone.urdf`` and ``drone.yaml`` for a morphology genome.

    Parameters
    ----------
    morphology : MorphologyGenome
        Morphology parameters to encode: [wingspan, wing_area, h_tail_area,
        v_tail_area, thrust_to_weight, total_mass, cg_x_offset].
    out_dir : str
        Destination directory for the model files.
    drone_model : str
        Base filename (will gain ``.urdf`` / ``.yaml``).
    template_dir : str | None
        Directory containing the PyFlyt default fixedwing template files.
        If ``None``, we attempt to locate them inside the installed
        ``PyFlyt`` package.

    Returns
    -------
    dict
        Paths to the generated URDF and YAML files.
    """
    os.makedirs(out_dir, exist_ok=True)

    template_dir = template_dir or _locate_pyflyt_default_model()
    if template_dir is None:
        raise FileNotFoundError(
            "Could not locate PyFlyt's default fixedwing model files. "
            "Pass `template_dir` explicitly."
        )

    src_urdf = os.path.join(template_dir, f"{drone_model}.urdf")
    src_yaml = os.path.join(template_dir, f"{drone_model}.yaml")

    if not os.path.isfile(src_urdf) or not os.path.isfile(src_yaml):
        raise FileNotFoundError(
            f"Template files not found in {template_dir}: "
            f"expected {drone_model}.urdf and {drone_model}.yaml"
        )

    p = morphology.to_dict()
    wingspan = float(p.get("wingspan", 1.80))
    wing_area = float(p.get("wing_area", 0.45))
    h_tail_area = float(p.get("h_tail_area", 0.08))
    v_tail_area = float(p.get("v_tail_area", 0.06))
    thrust_to_weight = float(p.get("thrust_to_weight", 0.85))
    total_mass = float(p.get("total_mass", 1.50))
    cg_x_offset = float(p.get("cg_x_offset", 0.0))

    # Aerodynamic geometric dimensions
    chord = float(wing_area / max(wingspan, 1e-4))
    ht_span = float(np.sqrt(3.0 * max(h_tail_area, 1e-4)))
    ht_chord = float(h_tail_area / max(ht_span, 1e-4))
    vt_span = float(np.sqrt(1.5 * max(v_tail_area, 1e-4)))
    vt_chord = float(v_tail_area / max(vt_span, 1e-4))
    total_thrust = float(thrust_to_weight * total_mass * 9.81)

    # 1. Scale YAML parameters
    with open(src_yaml, "r", encoding="utf-8") as f:
        ydata = yaml.safe_load(f)

    if "motor_params" in ydata:
        ydata["motor_params"]["total_thrust"] = total_thrust
    if "main_wing_params" in ydata:
        ydata["main_wing_params"]["chord"] = chord
        ydata["main_wing_params"]["span"] = float(0.70 * wingspan)
    if "left_wing_flapped_params" in ydata:
        ydata["left_wing_flapped_params"]["chord"] = chord
        ydata["left_wing_flapped_params"]["span"] = float(0.15 * wingspan)
    if "right_wing_flapped_params" in ydata:
        ydata["right_wing_flapped_params"]["chord"] = chord
        ydata["right_wing_flapped_params"]["span"] = float(0.15 * wingspan)
    if "horizontal_tail_params" in ydata:
        ydata["horizontal_tail_params"]["chord"] = ht_chord
        ydata["horizontal_tail_params"]["span"] = ht_span
    if "vertical_tail_params" in ydata:
        ydata["vertical_tail_params"]["chord"] = vt_chord
        ydata["vertical_tail_params"]["span"] = vt_span

    yaml_path = os.path.join(out_dir, f"{drone_model}.yaml")
    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(ydata, f, default_flow_style=False)

    # 2. Scale URDF links, geometries, and masses
    tree = ET.parse(src_urdf)
    root = tree.getroot()
    base_ref_mass = 2.35  # Sum of default link masses in PyFlyt fixedwing template
    mass_scale = total_mass / base_ref_mass

    for link in root.findall("link"):
        name = link.get("name")
        m = link.find("inertial/mass")
        if m is not None:
            cur_m = float(m.get("value", 0.0))
            if cur_m > 0:
                m.set("value", f"{cur_m * mass_scale:.4f}")

        if name == "base_link":
            orig = link.find("inertial/origin")
            if orig is not None:
                orig.set("xyz", f"{cg_x_offset:.4f} 0 0")
        elif name == "main_wing_link":
            for b in link.findall(".//box"):
                b.set("size", f"{chord:.4f} {0.70 * wingspan:.4f} 0.05")
        elif name in ("ail_left_link", "ail_right_link"):
            for b in link.findall(".//box"):
                b.set("size", f"{chord:.4f} {0.15 * wingspan:.4f} 0.06")
        elif name == "horizontal_tail_link":
            for b in link.findall(".//box"):
                b.set("size", f"{ht_chord:.4f} {ht_span:.4f} 0.05")
        elif name == "vertical_tail_link":
            for b in link.findall(".//box"):
                b.set("size", f"{vt_chord:.4f} 0.05 {vt_span:.4f}")

    for joint in root.findall("joint"):
        jname = joint.get("name")
        orig = joint.find("origin")
        if orig is not None:
            if jname == "ail_left_joint":
                orig.set("xyz", f"-0.5 {0.425 * wingspan:.4f} 0")
            elif jname == "ail_right_joint":
                orig.set("xyz", f"-0.5 {-0.425 * wingspan:.4f} 0")
            elif jname == "vertical_tail_joint":
                orig.set("xyz", f"-1.1 0 {0.5 * vt_span:.4f}")

    urdf_path = os.path.join(out_dir, f"{drone_model}.urdf")
    tree.write(urdf_path, encoding="utf-8", xml_declaration=True)

    # Persist the morphology alongside the model for traceability
    meta_path = os.path.join(out_dir, "morphology.json")
    with open(meta_path, "w", encoding="utf-8") as fh:
        json.dump(p, fh, indent=4)

    return {"urdf": urdf_path, "yaml": yaml_path}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _locate_pyflyt_default_model() -> Optional[str]:
    """Find PyFlyt's bundled fixedwing model directory."""
    try:
        import PyFlyt
    except ImportError:
        try:
            import pyflyt as PyFlyt
        except ImportError:
            return None

    pkg_dir = os.path.dirname(PyFlyt.__file__)

    candidates = [
        os.path.join(pkg_dir, "models", "vehicles", "fixedwing"),
        os.path.join(pkg_dir, "models", "fixedwing"),
        os.path.join(pkg_dir, "gym_envs", "fixedwing_env", "models", "fixedwing"),
        os.path.join(pkg_dir, "gym_envs", "fixedwing", "models", "fixedwing"),
    ]

    for candidate in candidates:
        if os.path.isfile(os.path.join(candidate, "fixedwing.urdf")):
            return candidate

    return None