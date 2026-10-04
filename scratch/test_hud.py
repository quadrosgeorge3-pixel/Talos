import sys
sys.path.insert(0, ".")
import numpy as np
from src.dashboard.flight_hud import draw_hud
from PIL import Image

dummy_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
dummy_frame[:] = [30, 40, 60] # sky blue-ish gray
out = draw_hud(
    frame_rgb=dummy_frame,
    roll=0.15,
    pitch=0.08,
    yaw=1.2,
    airspeed=26.4,
    altitude=18.5,
    climb_rate=1.2,
    throttle=0.85,
    flight_time=4.5,
    wp_idx=1,
    total_wps=4,
    dist_to_wp=34.2,
    target_pos=np.array([40, 20, 15]),
    current_pos=np.array([12, 5, 18]),
    contender_name='TALOS-P4-ULTIMA (GEN 411)',
    test_title='Test B - Waypoint Course',
)
print('HUD successfully rendered, out shape:', out.shape)
Image.fromarray(out).save('scratch/test_hud_sample.png')
print('Saved test_hud_sample.png')
