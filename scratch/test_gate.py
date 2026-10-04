import sys
import numpy as np
import pybullet as p
from PyFlyt.core.aviary import Aviary

print("Initializing Aviary...")
av = Aviary(start_pos=np.array([[0.0, 0.0, 10.0]]), start_orn=np.array([[0.0, 0.0, 0.0]]), drone_type='fixedwing', render=False, drone_options={'use_camera': True})
pc = av.drones[0].p
print("Aviary client:", pc._client)
vs = pc.createVisualShape(p.GEOM_CYLINDER, radius=4.0, length=0.6, rgbaColor=[1.0, 0.8, 0.0, 0.8])
mb = pc.createMultiBody(baseMass=0, baseVisualShapeIndex=vs, basePosition=[10, 0, 10], baseOrientation=pc.getQuaternionFromEuler([0, float(np.pi/2), 0]))
print("Gate created:", mb)
av.disconnect()
print("Done!")
