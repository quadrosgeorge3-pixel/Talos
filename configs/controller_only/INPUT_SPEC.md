# Phase 2 (Controller-Only Evolution) — Exact Input Specification

This document details the exact inputs driving **Phase 2: Controller-Only Evolution** (`C1_controller_only`), in accordance with **Build Order §6.2** of `project-spec-evolved-aircraft.md`.

---

## 1. Flight Sensor Observation Inputs (15 Floats)
At every control step ($120\text{ Hz}$, every $8.33\text{ ms}$), the neural network receives a vector of **15 continuous state observations** from PyFlyt:

| Index | Input Identifier | Physical Quantity | Units | Coordinate Frame | Typical Flight Range |
|---|---|---|---|---|---|
| `0` | `ang_vel_p` | Roll angular rate ($p$) | $\text{rad/s}$ | Body-fixed ($X_{\text{body}}$) | $[-2.0, +2.0]$ |
| `1` | `ang_vel_q` | Pitch angular rate ($q$) | $\text{rad/s}$ | Body-fixed ($Y_{\text{body}}$) | $[-2.0, +2.0]$ |
| `2` | `ang_vel_r` | Yaw angular rate ($r$) | $\text{rad/s}$ | Body-fixed ($Z_{\text{body}}$) | $[-2.0, +2.0]$ |
| `3` | `roll` | Bank angle ($\phi$) | $\text{rad}$ | Euler attitude | $[-\pi, +\pi]$ |
| `4` | `pitch` | Elevation angle ($\theta$) | $\text{rad}$ | Euler attitude | $[-\pi/2, +\pi/2]$ |
| `5` | `yaw` | Heading angle ($\psi$) | $\text{rad}$ | Euler attitude | $[-\pi, +\pi]$ |
| `6` | `lin_vel_u` | Forward surge velocity | $\text{m/s}$ | Body-fixed | $[0.0, 30.0]$ |
| `7` | `lin_vel_v` | Lateral sway velocity | $\text{m/s}$ | Body-fixed | $[-5.0, +5.0]$ |
| `8` | `lin_vel_w` | Vertical heave velocity | $\text{m/s}$ | Body-fixed | $[-10.0, +10.0]$ |
| `9` | `pos_x` | Inertial position $X$ | $\text{m}$ | World Frame | $[0.0, 150.0]$ |
| `10` | `pos_y` | Inertial position $Y$ | $\text{m}$ | World Frame | $[-30.0, +30.0]$ |
| `11` | `pos_z` | Altitude above ground | $\text{m}$ | World Frame | $[0.0, 20.0]$ (Target: $10\text{m}$) |
| `12` | `waypoint_dx` | Relative delta to target $X$ | $\text{m}$ | World Frame | $[-50.0, +50.0]$ |
| `13` | `waypoint_dy` | Relative delta to target $Y$ | $\text{m}$ | World Frame | $[-50.0, +50.0]$ |
| `14` | `waypoint_dz` | Relative delta to target $Z$ | $\text{m}$ | World Frame | $[-15.0, +15.0]$ |

---

## 2. Flight Actuator Control Outputs (6 Floats)
The output layer maps continuous network activations to 6 independent aerodynamic surfaces in PyFlyt:

| Output Index | Actuator Name | Deflection Range | Function & Physical Mapping |
|---|---|---|---|
| `u_0` | `left_aileron` | $[-1.0, +1.0]$ | Left wing trailing edge (Roll control) |
| `u_1` | `right_aileron` | $[-1.0, +1.0]$ | Right wing trailing edge (Roll control, differential) |
| `u_2` | `elevator` | $[-1.0, +1.0]$ | Horizontal tail flap (Negative = Pitch up / climb) |
| `u_3` | `rudder` | $[-1.0, +1.0]$ | Vertical fin trailing edge (Yaw control) |
| `u_4` | `main_wing_flap` | $[0.0, 1.0]$ | Inboard flaps (Lift augmentation & drag) |
| `u_5` | `thrust` | $[0.0, 1.0]$ | Brushless motor propeller throttle |

---

## 3. Evolutionary Algorithm & Hyperparameter Inputs

```json
{
  "population_size": 50,
  "generations": 100,
  "episodes_per_evaluation": 3,
  "fitness_criterion": "max",
  "initial_topology": "full_direct",
  "structural_mutations": {
    "add_connection_probability": 0.50,
    "delete_connection_probability": 0.20,
    "add_node_probability": 0.30,
    "delete_node_probability": 0.10
  },
  "weight_mutations": {
    "mutate_rate": 0.80,
    "replace_rate": 0.10,
    "max_weight": 3.0,
    "initial_std": 1.0
  },
  "speciation": {
    "compatibility_threshold": 3.0,
    "excess_disjoint_coefficient": 1.0,
    "weight_difference_coefficient": 0.5
  }
}
```

---

## 4. Multi-Objective Fitness Evaluation Function

Each genome $i$ is evaluated across $N=3$ randomized seed episodes:
$$\text{Fitness}(i) = w_{\text{surv}} \cdot S + w_{\text{eff}} \cdot E + w_{\text{man}} \cdot M - P_{\text{crash}} - P_{\text{stall}}$$

- **Survival ($w = 0.4$)**: Normalized flight duration up to episode limit ($10.0\text{ s}$).
- **Efficiency ($w = 0.3$)**: Distance covered per unit of energy expended ($D / \int T^2 dt$).
- **Maneuverability ($w = 0.3$)**: Altitude tracking precision ($\exp(-\|\Delta z\|)$) and waypoint convergence.
- **Penalties**: Crash $=-100.0$; Stall event $=-5.0$; Ground impact or boundary exceedance $=-2.0$.

---

## 5. Airframe Isolation Constraint (Spec §6.2)
In Phase 2, **the morphology genome is strictly locked** to the default PyFlyt airframe:
- Wingspan: $1.80\text{ m}$
- Wing Area: $0.45\text{ m}^2$
- Mass: $1.50\text{ kg}$
- Static Margin: $+12.4\%\text{ MAC}$

This ensures that any observed performance improvement is purely attributable to neural controller topology and weight evolution.
