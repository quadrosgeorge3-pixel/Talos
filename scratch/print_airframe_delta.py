import numpy as np

# Baseline Default PyFlyt Fixedwing
base = {
    "wingspan": 1.80,
    "wing_area": 0.45,
    "h_tail_area": 0.08,
    "v_tail_area": 0.06,
    "thrust_to_weight": 0.85,
    "total_mass": 1.50,
    "cg_x_offset": 0.0,
}

# P3C Champion (Gen 23 Ind 23)
p3c = {
    "wingspan": 1.7862,
    "wing_area": 0.5699,
    "h_tail_area": 0.2235,
    "v_tail_area": 0.2385,
    "thrust_to_weight": 1.4926,
    "total_mass": 3.4162,
    "cg_x_offset": 0.0847,
}

def analyze(p):
    b = p["wingspan"]
    S = p["wing_area"]
    c = S / b
    AR = (b ** 2) / S
    m = p["total_mass"]
    tw = p["thrust_to_weight"]
    thrust = tw * m * 9.81
    wl = m / S
    Sh = p["h_tail_area"]
    Sv = p["v_tail_area"]
    # Tail dimensions
    ht_span = np.sqrt(3.0 * Sh)
    ht_chord = Sh / ht_span
    vt_span = np.sqrt(1.5 * Sv)
    vt_chord = Sv / vt_span
    # Tail volume approximations (lever arm l ~ 0.7m)
    Vh = (Sh * 0.7) / (S * c)
    Vv = (Sv * 0.7) / (S * b)
    return {
        "b": b, "S": S, "c": c, "AR": AR, "m": m, "tw": tw, "thrust": thrust,
        "wl": wl, "Sh": Sh, "Sv": Sv, "ht_span": ht_span, "vt_span": vt_span,
        "Vh": Vh, "Vv": Vv, "cg": p["cg_x_offset"]
    }

b_met = analyze(base)
p_met = analyze(p3c)

print(f"{'Metric':<28} | {'Default PyFlyt':<16} | {'P3C Champion':<16} | {'Delta':<12}")
print("-" * 78)
for k, label in [
    ("b", "Wingspan (b)"),
    ("S", "Wing Area (S)"),
    ("c", "Mean Chord (c)"),
    ("AR", "Aspect Ratio (AR)"),
    ("m", "Total Mass (m)"),
    ("tw", "Thrust-to-Weight (T/W)"),
    ("thrust", "Max Motor Thrust (T)"),
    ("wl", "Wing Loading (m/S)"),
    ("Sh", "Horizontal Tail (S_h)"),
    ("Sv", "Vertical Tail (S_v)"),
    ("ht_span", "Horiz Tail Span"),
    ("vt_span", "Vert Tail Span (Height)"),
    ("Vh", "Horiz Tail Volume (V_h)"),
    ("Vv", "Vert Tail Volume (V_v)"),
    ("cg", "CG Offset (dx)"),
]:
    v0 = b_met[k]
    v1 = p_met[k]
    pct = ((v1 - v0) / v0) * 100.0 if v0 != 0 else (v1 * 100.0)
    fmt0 = f"{v0:.2f}" if abs(v0) > 0.1 else f"{v0:.3f}"
    fmt1 = f"{v1:.2f}" if abs(v1) > 0.1 else f"{v1:.3f}"
    print(f"{label:<28} | {fmt0:<16} | {fmt1:<16} | {pct:+6.1f}%")
