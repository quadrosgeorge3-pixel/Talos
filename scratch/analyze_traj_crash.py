import json

with open('output/talos-p4-ultima_trajectory.json') as f:
    d = json.load(f)

traj = d['trajectory']
print(f"Gen: {d.get('generation')}")
print(f"Total points: {len(traj)}")
print(f"Crashed flag: {d.get('crashed')}")
print(f"Flight time: {d.get('flight_time')}")

min_z = min(p['z'] for p in traj)
max_z = max(p['z'] for p in traj)
print(f"min_z: {min_z:.2f}, max_z: {max_z:.2f}")

for p in traj:
    if p['z'] <= 0.2:
        print(f"First ground contact: t={p['time']:.2f}s, x={p['x']:.1f}, y={p['y']:.1f}, z={p['z']:.2f}, spd={p['airspeed']:.1f}, wp_hit={p['waypoints_hit']}")
        break

print("\nLast 5 points of trajectory:")
for p in traj[-5:]:
    print(f"t={p['time']:.2f}s, x={p['x']:.1f}, y={p['y']:.1f}, z={p['z']:.2f}, spd={p['airspeed']:.1f}, wp_hit={p['waypoints_hit']}")
