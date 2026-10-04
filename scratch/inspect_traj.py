import json
import numpy as np

with open('output/p3c_trajectory.json') as f:
    traj = json.load(f)

gen = traj.get('generation')
dist = traj.get('distance', 0.0)
pts = traj.get('trajectory', [])
crashed = traj.get('crashed', False)

print(f"Latest Live Champion Trajectory: Gen {gen}, Distance: {dist:.1f}m, Crashed: {crashed}, Points: {len(pts)}")
if pts:
    z_vals = [p['z'] for p in pts]
    x_vals = [p['x'] for p in pts]
    y_vals = [p['y'] for p in pts]
    rolls = [p['roll'] for p in pts]
    yaws = [p['yaw'] for p in pts]
    
    print(f"Alt (Z): min={min(z_vals):.2f}m, max={max(z_vals):.2f}m, mean={np.mean(z_vals):.2f}m")
    print(f"X range: [{min(x_vals):.1f}, {max(x_vals):.1f}], Y range: [{min(y_vals):.1f}, {max(y_vals):.1f}]")
    print(f"Max abs roll: {np.max(np.abs(rolls)):.2f} rad ({np.degrees(np.max(np.abs(rolls))):.1f} deg)")
    
    print("\nFirst 8 trajectory sample points:")
    for p in pts[:8]:
        print(f"  step {p['step']:3d}: x={p['x']:6.1f}, y={p['y']:6.1f}, z={p['z']:5.2f} | roll={p['roll']:5.2f}, pitch={p['pitch']:5.2f}, yaw={p['yaw']:5.2f}, spd={p['airspeed']:4.1f}m/s")
    
    print("\nLast 5 trajectory sample points:")
    for p in pts[-5:]:
        print(f"  step {p['step']:3d}: x={p['x']:6.1f}, y={p['y']:6.1f}, z={p['z']:5.2f} | roll={p['roll']:5.2f}, pitch={p['pitch']:5.2f}, yaw={p['yaw']:5.2f}, spd={p['airspeed']:4.1f}m/s")
