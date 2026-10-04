"""generate_flight_videos.py — Complete PyFlyt Flight Video Generator.

Simulates and records MP4 flight videos for benchmarked aircraft across phases into
dedicated nested directories under output/flight_videos/:
    output/flight_videos/
        phase0_baselines/
            pid_open_sky/
                test_A_open_sky_straight.mp4
                test_B_waypoint_course.mp4
                ...
        phase1_2_brain_evolution/
            phase2_neat_caged/
            talos_p2b_gen300/
        phase3_staged_body_evolution/
            p3a_champ_neat_gen300/
            p3b_champ_pid/
            p3c_champ_neat_gen300/
            ...
        phase4_testarossa_coevolution/
            testarossa_gen352_best/
            testarossa_gen424_latest/
            ...
        phase4_ultima_apex_coevolution/
            ultima_gen375_hairpin_best/
            ultima_gen411_peak_fitness/
            ultima_gen425_latest/
            ...

Records full camera tracking of the aircraft with HUD overlays.
Updates output/icarus.db visualizer_comparison_matrix and visualizer_manifest with video paths.
"""
from __future__ import annotations

import json
import math
import os
import shutil
import sqlite3
import sys
from typing import Any, Dict, List, Optional, Tuple

import imageio
import neat
import numpy as np

sys.path.insert(0, ".")

from src.experiment.metadata import load_config
from src.genome.controller import NEATController
from src.genome.morphology import MorphologyGenome
from src.genome.urdf_gen import generate_model_files
from src.simulation.env import FixedwingEnv
from src.simulation.generalization_benchmark import (
    BENCHMARK_TEST_CONFIGS,
    WP_COURSE_B,
    WP_COURSE_C,
    WP_COURSE_D,
    WP_COURSE_E,
)
from src.simulation.pid_controller import FixedwingPIDController
from src.dashboard.flight_hud import draw_hud
import pybullet as p

DB_PATH = "output/icarus.db"
BASE_VIDEO_DIR = os.path.join("output", "flight_videos")

# Clean folder mapping per category and model
CONTENDER_SPECS: List[Dict[str, Any]] = [
    # Phase 0
    {
        "controller_id": "pid_open_sky",
        "folder_path": os.path.join(BASE_VIDEO_DIR, "phase0_baselines", "pid_open_sky_default"),
        "type": "PID",
        "morphology": {"wingspan": 1.0, "wing_area": 0.3, "h_tail_area": 0.05, "v_tail_area": 0.05, "thrust_to_weight": 0.6, "total_mass": 1.2, "cg_x_offset": 0.0},
        "model_dir": None,
    },
    # Phase 1 & 2
    {
        "controller_id": "phase2_neat_caged",
        "folder_path": os.path.join(BASE_VIDEO_DIR, "phase1_2_brain_evolution", "phase2_neat_caged_early"),
        "type": "NEAT",
        "experiment_id": "C1",
        "gen": 121,
        "morphology": {"wingspan": 1.0, "wing_area": 0.3, "h_tail_area": 0.05, "v_tail_area": 0.05, "thrust_to_weight": 0.6, "total_mass": 1.2, "cg_x_offset": 0.0},
        "model_dir": None,
    },
    {
        "controller_id": "TALOS-P2B_gen300_champ",
        "folder_path": os.path.join(BASE_VIDEO_DIR, "phase1_2_brain_evolution", "talos_p2b_gen300_champ"),
        "type": "NEAT",
        "experiment_id": "TALOS-P2B",
        "gen": 299,
        "morphology": {"wingspan": 1.0, "wing_area": 0.3, "h_tail_area": 0.05, "v_tail_area": 0.05, "thrust_to_weight": 0.6, "total_mass": 1.2, "cg_x_offset": 0.0},
        "model_dir": None,
    },
    # Phase 3
    {
        "controller_id": "p3a_champ_neat_gen300",
        "folder_path": os.path.join(BASE_VIDEO_DIR, "phase3_staged_body_evolution", "p3a_champ_neat_gen300"),
        "type": "NEAT",
        "experiment_id": "TALOS-P2B",
        "gen": 299,
        "morphology": {"wingspan": 3.0, "wing_area": 0.76, "h_tail_area": 0.07, "v_tail_area": 0.06, "thrust_to_weight": 1.5, "total_mass": 2.94, "cg_x_offset": -0.03},
        "model_dir": "models/video_eval/p3a_champ",
    },
    {
        "controller_id": "p3b_champ_pid",
        "folder_path": os.path.join(BASE_VIDEO_DIR, "phase3_staged_body_evolution", "p3b_champ_pid_sailplane"),
        "type": "PID",
        "morphology": {"wingspan": 3.0, "wing_area": 0.42, "h_tail_area": 0.09, "v_tail_area": 0.02, "thrust_to_weight": 1.5, "total_mass": 4.22, "cg_x_offset": -0.05},
        "model_dir": "models/video_eval/p3b_champ",
    },
    {
        "controller_id": "p3c_champ_neat_gen300",
        "folder_path": os.path.join(BASE_VIDEO_DIR, "phase3_staged_body_evolution", "p3c_champ_neat_gen300_record"),
        "type": "NEAT",
        "experiment_id": "TALOS-P2B",
        "gen": 299,
        "morphology": {"wingspan": 1.8, "wing_area": 0.57, "h_tail_area": 0.22, "v_tail_area": 0.24, "thrust_to_weight": 1.49, "total_mass": 3.40, "cg_x_offset": 0.08},
        "model_dir": "models/video_eval/p3c_champ",
    },
    {
        "controller_id": "p3c_champ_pid",
        "folder_path": os.path.join(BASE_VIDEO_DIR, "phase3_staged_body_evolution", "p3c_champ_pid_tail_stable"),
        "type": "PID",
        "morphology": {"wingspan": 1.8, "wing_area": 0.57, "h_tail_area": 0.22, "v_tail_area": 0.24, "thrust_to_weight": 1.49, "total_mass": 3.40, "cg_x_offset": 0.08},
        "model_dir": "models/video_eval/p3c_champ",
    },
    # Phase 4 TESTAROSSA
    {
        "controller_id": "TALOS-P4-TESTAROSSA_gen352",
        "folder_path": os.path.join(BASE_VIDEO_DIR, "phase4_testarossa_coevolution", "testarossa_gen352_best_sweeper"),
        "type": "NEAT",
        "experiment_id": "TALOS-P4-TESTAROSSA",
        "gen": 352,
        "morphology": {"wingspan": 1.57, "wing_area": 1.18, "h_tail_area": 0.33, "v_tail_area": 0.15, "thrust_to_weight": 1.15, "total_mass": 3.63, "cg_x_offset": -0.08},
        "model_dir": "models/video_eval/testarossa_gen352",
    },
    {
        "controller_id": "TALOS-P4-TESTAROSSA_gen370",
        "folder_path": os.path.join(BASE_VIDEO_DIR, "phase4_testarossa_coevolution", "testarossa_gen370_high_speed"),
        "type": "NEAT",
        "experiment_id": "TALOS-P4-TESTAROSSA",
        "gen": 370,
        "morphology": {"wingspan": 1.72, "wing_area": 1.29, "h_tail_area": 0.32, "v_tail_area": 0.18, "thrust_to_weight": 1.20, "total_mass": 2.11, "cg_x_offset": -0.06},
        "model_dir": "models/video_eval/testarossa_gen370",
    },
    {
        "controller_id": "TALOS-P4-TESTAROSSA_gen424",
        "folder_path": os.path.join(BASE_VIDEO_DIR, "phase4_testarossa_coevolution", "testarossa_gen424_latest_glider"),
        "type": "NEAT",
        "experiment_id": "TALOS-P4-TESTAROSSA",
        "gen": 424,
        "morphology": {"wingspan": 1.93, "wing_area": 0.74, "h_tail_area": 0.35, "v_tail_area": 0.15, "thrust_to_weight": 0.50, "total_mass": 1.63, "cg_x_offset": -0.08},
        "model_dir": "models/video_eval/testarossa_gen424",
    },
    # Phase 4 ULTIMA
    {
        "controller_id": "TALOS-P4-ULTIMA_tier2",
        "folder_path": os.path.join(BASE_VIDEO_DIR, "phase4_ultima_apex_coevolution", "ultima_gen060_tier2_baseline"),
        "type": "NEAT",
        "experiment_id": "TALOS-P4-ULTIMA",
        "gen": 60,
        "morphology": {"wingspan": 3.0, "wing_area": 1.18, "h_tail_area": 0.39, "v_tail_area": 0.19, "thrust_to_weight": 1.12, "total_mass": 5.0, "cg_x_offset": -0.05},
        "model_dir": "models/video_eval/ultima_tier2",
    },
    {
        "controller_id": "TALOS-P4-ULTIMA_gen375_hairpin",
        "folder_path": os.path.join(BASE_VIDEO_DIR, "phase4_ultima_apex_coevolution", "ultima_gen375_hairpin_best"),
        "type": "NEAT",
        "experiment_id": "TALOS-P4-ULTIMA",
        "gen": 375,
        "morphology": {"wingspan": 2.15, "wing_area": 0.59, "h_tail_area": 0.23, "v_tail_area": 0.02, "thrust_to_weight": 1.92, "total_mass": 4.30, "cg_x_offset": -0.04},
        "model_dir": "models/video_eval/ultima_gen375",
    },
    {
        "controller_id": "TALOS-P4-ULTIMA_gen394_auto",
        "folder_path": os.path.join(BASE_VIDEO_DIR, "phase4_ultima_apex_coevolution", "ultima_gen394_high_speed"),
        "type": "NEAT",
        "experiment_id": "TALOS-P4-ULTIMA",
        "gen": 394,
        "morphology": {"wingspan": 1.86, "wing_area": 0.58, "h_tail_area": 0.24, "v_tail_area": 0.03, "thrust_to_weight": 1.90, "total_mass": 4.10, "cg_x_offset": -0.03},
        "model_dir": "models/video_eval/ultima_gen394",
    },
    {
        "controller_id": "TALOS-P4-ULTIMA_gen411_auto",
        "folder_path": os.path.join(BASE_VIDEO_DIR, "phase4_ultima_apex_coevolution", "ultima_gen411_peak_fitness"),
        "type": "NEAT",
        "experiment_id": "TALOS-P4-ULTIMA",
        "gen": 411,
        "morphology": {"wingspan": 2.20, "wing_area": 0.60, "h_tail_area": 0.25, "v_tail_area": 0.04, "thrust_to_weight": 1.88, "total_mass": 4.20, "cg_x_offset": -0.03},
        "model_dir": "models/video_eval/ultima_gen411",
    },
    {
        "controller_id": "TALOS-P4-ULTIMA_gen425_auto",
        "folder_path": os.path.join(BASE_VIDEO_DIR, "phase4_ultima_apex_coevolution", "ultima_gen425_latest_checkpoint"),
        "type": "NEAT",
        "experiment_id": "TALOS-P4-ULTIMA",
        "gen": 425,
        "morphology": {"wingspan": 1.99, "wing_area": 0.70, "h_tail_area": 0.34, "v_tail_area": 0.14, "thrust_to_weight": 0.80, "total_mass": 2.20, "cg_x_offset": -0.06},
        "model_dir": "models/video_eval/ultima_gen425",
    },
]


def load_neat_controller(experiment_id: str, gen: int) -> Optional[neat.nn.FeedForwardNetwork]:
    """Reconstruct a feed-forward neural network from SQLite individuals."""
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute(
        "SELECT controller_json FROM individuals WHERE experiment_id = ? AND generation = ?",
        (experiment_id, gen)
    )
    row = cur.fetchone()
    con.close()

    if not row or not row[0]:
        return None

    ctrl_data = json.loads(row[0])
    cfg_path = "configs/coevolution/p4_ultima_coevo.json" if "ULTIMA" in experiment_id else (
        "configs/coevolution/p4_testarossa.json" if "TESTAROSSA" in experiment_id else "configs/controller_only/c1_controller_only.json"
    )
    cfg = load_config(cfg_path)
    neat_cfg = NEATController._build_neat_config(cfg)

    genome = neat.DefaultGenome(ctrl_data["id"])
    genome.fitness = ctrl_data.get("fitness", 0.0)

    for out_id in range(6):
        node = genome.create_node(neat_cfg.genome_config, out_id)
        node.bias = 0.0
        node.activation = neat_cfg.genome_config.output_activation_default
        node.aggregation = neat_cfg.genome_config.aggregation_default
        node.response = 1.0
        genome.nodes[out_id] = node

    for n in ctrl_data.get("nodes", []):
        nid = n["id"]
        if nid < 0:
            continue
        node = genome.create_node(neat_cfg.genome_config, nid)
        node.bias = n.get("bias", 0.0)
        node.activation = n.get("activation", "tanh")
        node.aggregation = n.get("aggregation", "sum")
        node.response = n.get("response", 1.0)
        genome.nodes[nid] = node

    for idx, c in enumerate(ctrl_data.get("connections", [])):
        cid = (c["from"], c["to"])
        conn = genome.create_connection(neat_cfg.genome_config, c["from"], c["to"], innovation=idx)
        conn.weight = c.get("weight", 0.0)
        conn.enabled = c.get("enabled", True)
        genome.connections[cid] = conn

    return neat.nn.FeedForwardNetwork.create(genome, neat_cfg)


def render_flight_video(
    controller_type: str,
    controller_obj: Any,
    custom_waypoints: Optional[np.ndarray],
    duration: float,
    flight_dome_size: float,
    waypoint_radius: float,
    model_dir: Optional[str],
    output_mp4_path: str,
    seed: int = 42,
    render_interval: int = 2,
    contender_label: str = "AIRCRAFT",
    test_title: str = "Test Flight",
) -> bool:
    """Run simulation with 1280x720 HD render_mode, visible 3D waypoints, and aviation HUD."""
    config = load_config("configs/controller_only/c1_controller_only.json")
    config["simulation"]["episode_duration"] = duration
    config["simulation"]["flight_dome_size"] = flight_dome_size
    config["simulation"]["render_mode"] = "rgb_array"

    os.makedirs(os.path.dirname(output_mp4_path), exist_ok=True)

    try:
        env = FixedwingEnv(config=config, model_dir=model_dir)
        env.env.unwrapped.flight_dome_size = flight_dome_size
        env.max_steps = int(duration * env.control_hz)

        obs, _ = env.reset(seed=seed)
        
        # Configure High-Definition Chase Camera
        drone = env.env.unwrapped.env.drones[0]
        pc = drone.p
        drone.camera.camera_position_offset = np.array([-7.2, 0.0, 2.4])
        drone.camera.camera_resolution = np.array([720, 1280])
        drone.camera.camera_FOV_degrees = 68.0
        drone.camera.proj_mat = pc.computeProjectionMatrixFOV(
            fov=68.0, aspect=1280.0 / 720.0, nearVal=0.1, farVal=1200.0
        )
        env.env.unwrapped.render_resolution = (720, 1280)

        # Build 3D Waypoint Visual Beacons & Rings in PyBullet
        waypoint_bodies: List[Dict[str, Any]] = []
        if custom_waypoints is not None:
            # Re-initialize waypoint logic targets
            wp_handler = env.env.unwrapped.waypoints
            wp_handler.targets = custom_waypoints.copy()
            wp_handler.num_targets = len(custom_waypoints)
            wp_handler.goal_reach_distance = float(waypoint_radius)
            
            # Remove any default targets created randomly by PyFlyt
            if hasattr(wp_handler, "target_visual") and wp_handler.target_visual:
                for old_vis in wp_handler.target_visual:
                    try:
                        pc.removeBody(old_vis)
                    except Exception:
                        pass
                wp_handler.target_visual = []

            # Create vibrant 3D beacon markers for each waypoint
            for i, wp_pos in enumerate(custom_waypoints):
                wp_x, wp_y, wp_z = float(wp_pos[0]), float(wp_pos[1]), float(wp_pos[2])
                
                # Active target sphere (Radius: 2.2m)
                vs_sphere = pc.createVisualShape(
                    p.GEOM_SPHERE,
                    radius=2.2,
                    rgbaColor=[1.0, 0.82, 0.1, 0.88] if i == 0 else [0.0, 0.88, 1.0, 0.80]
                )
                mb_sphere = pc.createMultiBody(
                    baseMass=0,
                    baseVisualShapeIndex=vs_sphere,
                    basePosition=[wp_x, wp_y, wp_z]
                )

                # Outer navigation ring / gate (Cylinder radius: 4.8m, length: 0.6m)
                # Calculate orientation towards next waypoint or default forward
                if i + 1 < len(custom_waypoints):
                    diff = custom_waypoints[i + 1] - wp_pos
                    ring_yaw = math.atan2(diff[1], diff[0])
                else:
                    ring_yaw = 0.0
                ring_orn = pc.getQuaternionFromEuler([0, float(np.pi / 2), ring_yaw])
                
                vs_ring = pc.createVisualShape(
                    p.GEOM_CYLINDER,
                    radius=4.8,
                    length=0.6,
                    rgbaColor=[1.0, 0.65, 0.0, 0.70] if i == 0 else [0.1, 0.75, 0.9, 0.55]
                )
                mb_ring = pc.createMultiBody(
                    baseMass=0,
                    baseVisualShapeIndex=vs_ring,
                    basePosition=[wp_x, wp_y, wp_z],
                    baseOrientation=ring_orn
                )

                # Ground vertical altitude beacon line / pillar (connects waypoint to ground)
                pillar_len = max(wp_z, 1.0)
                vs_pillar = pc.createVisualShape(
                    p.GEOM_CYLINDER,
                    radius=0.32,
                    length=pillar_len,
                    rgbaColor=[1.0, 0.82, 0.1, 0.40] if i == 0 else [0.0, 0.88, 1.0, 0.30]
                )
                mb_pillar = pc.createMultiBody(
                    baseMass=0,
                    baseVisualShapeIndex=vs_pillar,
                    basePosition=[wp_x, wp_y, pillar_len / 2.0]
                )

                waypoint_bodies.append({
                    "idx": i,
                    "pos": np.array([wp_x, wp_y, wp_z]),
                    "sphere": mb_sphere,
                    "ring": mb_ring,
                    "pillar": mb_pillar,
                    "cleared": False,
                })

        if controller_type == "PID":
            controller_obj.reset()

        frames: List[np.ndarray] = []
        step = 0
        num_wp_total = len(custom_waypoints) if custom_waypoints is not None else 0
        current_target_idx = 0
        prev_alt = 10.0
        dt = 1.0 / env.control_hz

        # Capture initial frame with HUD
        init_frame = env.env.render()
        if init_frame is not None:
            frame_rgb = init_frame[:, :, :3]
            pos = np.array([0.0, 0.0, 10.0])
            t_pos = custom_waypoints[0] if custom_waypoints is not None and len(custom_waypoints) > 0 else None
            hud_frame = draw_hud(
                frame_rgb=frame_rgb,
                roll=0.0,
                pitch=0.0,
                yaw=0.0,
                airspeed=20.0,
                altitude=10.0,
                climb_rate=0.0,
                throttle=0.7,
                flight_time=0.0,
                wp_idx=0,
                total_wps=num_wp_total,
                dist_to_wp=float(np.linalg.norm(t_pos - pos)) if t_pos is not None else 0.0,
                target_pos=t_pos,
                current_pos=pos,
                contender_name=contender_label,
                test_title=test_title,
            )
            frames.append(hud_frame)

        while step < env.max_steps:
            if controller_type == "PID":
                action = controller_obj.predict(obs)
            else:
                action = np.asarray(controller_obj.activate(obs), dtype=np.float32)

            obs, _, term, trunc, info = env.step(action)
            step += 1

            # Extract accurate aircraft attitude & spatial state
            drone_state = drone.state
            ang_pos = drone_state[1]      # [roll, pitch, yaw]
            lin_vel = drone_state[2]      # [u, v, w]
            lin_pos = drone_state[3]      # [x, y, z]

            roll = float(ang_pos[0])
            pitch = float(ang_pos[1])
            yaw = float(ang_pos[2])
            airspeed = float(np.linalg.norm(lin_vel))
            altitude = float(lin_pos[2])
            climb_rate = (altitude - prev_alt) / dt
            prev_alt = altitude
            throttle_val = float(np.clip(action[5], 0.0, 1.0)) if len(action) > 5 else 0.5
            flight_time = step * dt

            # Update waypoint progression and visual color transitions
            wp_handler = getattr(env.env.unwrapped, "waypoints", None)
            waypoints_hit = int(getattr(wp_handler, "num_targets_reached", 0)) if wp_handler else 0
            
            # Update active waypoint index and color styling in 3D scene
            if waypoints_hit != current_target_idx and current_target_idx < len(waypoint_bodies):
                # Mark previous as cleared (turn emerald green)
                for k in range(min(waypoints_hit, len(waypoint_bodies))):
                    wb = waypoint_bodies[k]
                    if not wb["cleared"]:
                        wb["cleared"] = True
                        try:
                            pc.changeVisualShape(wb["sphere"], -1, rgbaColor=[0.1, 1.0, 0.3, 0.4])
                            pc.changeVisualShape(wb["ring"], -1, rgbaColor=[0.1, 1.0, 0.3, 0.3])
                            pc.changeVisualShape(wb["pillar"], -1, rgbaColor=[0.1, 1.0, 0.3, 0.15])
                        except Exception:
                            pass
                current_target_idx = waypoints_hit
                # Set new active waypoint to glowing gold
                if current_target_idx < len(waypoint_bodies):
                    wb = waypoint_bodies[current_target_idx]
                    try:
                        pc.changeVisualShape(wb["sphere"], -1, rgbaColor=[1.0, 0.85, 0.0, 0.95])
                        pc.changeVisualShape(wb["ring"], -1, rgbaColor=[1.0, 0.65, 0.0, 0.85])
                        pc.changeVisualShape(wb["pillar"], -1, rgbaColor=[1.0, 0.85, 0.0, 0.5])
                    except Exception:
                        pass

            active_target_pos = (
                custom_waypoints[current_target_idx]
                if (custom_waypoints is not None and current_target_idx < len(custom_waypoints))
                else None
            )
            dist_to_active = (
                float(np.linalg.norm(active_target_pos - lin_pos))
                if active_target_pos is not None
                else 0.0
            )

            # Render frame every render_interval steps (15 fps)
            if step % render_interval == 0 or term or trunc:
                frame = env.env.render()
                if frame is not None:
                    frame_rgb = frame[:, :, :3]
                    hud_frame = draw_hud(
                        frame_rgb=frame_rgb,
                        roll=roll,
                        pitch=pitch,
                        yaw=yaw,
                        airspeed=airspeed,
                        altitude=altitude,
                        climb_rate=climb_rate,
                        throttle=throttle_val,
                        flight_time=flight_time,
                        wp_idx=current_target_idx,
                        total_wps=num_wp_total,
                        dist_to_wp=dist_to_active,
                        target_pos=active_target_pos,
                        current_pos=lin_pos,
                        contender_name=contender_label,
                        test_title=test_title,
                    )
                    frames.append(hud_frame)

            # Stop if all targets are reached
            if custom_waypoints is not None and (
                (wp_handler and getattr(wp_handler, "all_targets_reached", False))
                or (waypoints_hit >= num_wp_total and num_wp_total > 0)
            ):
                break

            if term or trunc:
                break

        # Clean up custom waypoint bodies from pybullet simulation
        for wb in waypoint_bodies:
            try:
                pc.removeBody(wb["sphere"])
                pc.removeBody(wb["ring"])
                pc.removeBody(wb["pillar"])
            except Exception:
                pass

        env.env.close()

        if len(frames) > 0:
            fps = max(10, int(env.control_hz / render_interval))
            imageio.mimsave(output_mp4_path, frames, fps=fps)
            print(f"  -> Remade {os.path.basename(output_mp4_path)} ({len(frames)} frames @ {fps}fps, {len(frames)/fps:.1f}s)")
            return True
        return False
    except Exception as ex:
        print(f"  [ERROR] Failed to generate video {output_mp4_path}: {ex}")
        return False


def run_all_video_generation(test_filter: Optional[List[str]] = None, overwrite: bool = True) -> None:
    """Iterate through all canonical models and generate test flight videos in nested folders."""
    print("=" * 75)
    print("  PROJECT TALOS — BATCH PYFLYT FLIGHT VIDEO GENERATOR (HD + 3D WAYPOINTS + HUD)")
    print(f"  Base Video Directory: {BASE_VIDEO_DIR}")
    print("=" * 75)

    test_code_map = {
        "Test A - Open-Sky Straight Flight": "A_straight_cruise",
        "Test B - Open-Sky Waypoint Course": "B_waypoint_course",
        "Test C - Aggressive Aero Slalom": "C_aero_slalom",
        "Test D - AUVSI SUAS Autonomous Challenge": "D_auvsi_challenge",
        "Test E - FAI F3D/F5D Pylon Racing": "E_pylon_racing",
    }

    test_short_codes = {
        "Test A - Open-Sky Straight Flight": "A",
        "Test B - Open-Sky Waypoint Course": "B",
        "Test C - Aggressive Aero Slalom": "C",
        "Test D - AUVSI SUAS Autonomous Challenge": "D",
        "Test E - FAI F3D/F5D Pylon Racing": "E",
    }

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    total_generated = 0

    for spec in CONTENDER_SPECS:
        cid = spec["controller_id"]
        folder = spec["folder_path"]
        ctype = spec["type"]
        morph_dict = spec["morphology"]
        model_dir = spec["model_dir"]

        print(f"\nProcessing Contender: {cid} -> {os.path.relpath(folder, BASE_VIDEO_DIR)}")
        os.makedirs(folder, exist_ok=True)

        # Prepare physical airframe model files if customized
        if model_dir is not None:
            morph_genome = MorphologyGenome.from_dict(morph_dict)
            generate_model_files(morph_genome, model_dir)

        # Build controller instance
        if ctype == "PID":
            ctrl = FixedwingPIDController(dt=1.0 / 30.0)
        else:
            ctrl = load_neat_controller(spec["experiment_id"], spec["gen"])
            if ctrl is None:
                print(f"  [WARN] Could not load NEAT controller for {cid} (Gen {spec['gen']}). Skipping.")
                continue

        # Iterate tests
        for t_name, wp_array, duration, dome, wp_rad in BENCHMARK_TEST_CONFIGS:
            t_slug = test_code_map.get(t_name, "test")
            t_short = test_short_codes.get(t_name, "A")

            if test_filter and t_short not in test_filter:
                continue

            video_filename = f"{t_slug}.mp4"
            video_filepath = os.path.join(folder, video_filename)

            if not overwrite and os.path.isfile(video_filepath) and os.path.getsize(video_filepath) > 1000:
                print(f"  [SKIP] Already exists: {video_filename}")
                rel_path = os.path.relpath(video_filepath, ".").replace("\\", "/")
                cur.execute(
                    "UPDATE visualizer_comparison_matrix SET video_path = ? WHERE test_code = ? AND controller_id = ?",
                    (rel_path, t_short, cid)
                )
                con.commit()
                continue

            success = render_flight_video(
                controller_type=ctype,
                controller_obj=ctrl,
                custom_waypoints=wp_array,
                duration=duration,
                flight_dome_size=dome,
                waypoint_radius=wp_rad,
                model_dir=model_dir,
                output_mp4_path=video_filepath,
                seed=42,
                render_interval=2,
                contender_label=cid,
                test_title=t_name,
            )

            if success:
                total_generated += 1
                rel_path = os.path.relpath(video_filepath, ".").replace("\\", "/")
                cur.execute(
                    "UPDATE visualizer_comparison_matrix SET video_path = ? WHERE test_code = ? AND controller_id = ?",
                    (rel_path, t_short, cid)
                )
                con.commit()

    con.close()
    print(f"\n[talos] Video generation completed. Total new videos: {total_generated}")


if __name__ == "__main__":
    filt = sys.argv[1:] if len(sys.argv) > 1 else None
    run_all_video_generation(test_filter=filt, overwrite=True)
