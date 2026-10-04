import os, shutil, numpy as np, xml.etree.ElementTree as ET, yaml, PyFlyt
from src.experiment.metadata import load_config
from src.simulation.env import FixedwingEnv
from src.simulation.pid_controller import FixedwingPIDController
from src.genome.morphology import MorphologyGenome

pkg_dir = os.path.dirname(PyFlyt.__file__)
src_urdf = os.path.join(pkg_dir, 'models', 'vehicles', 'fixedwing', 'fixedwing.urdf')
src_yaml = os.path.join(pkg_dir, 'models', 'vehicles', 'fixedwing', 'fixedwing.yaml')

test_dir = os.path.abspath('scratch/test_model')
os.makedirs(test_dir, exist_ok=True)

morph = MorphologyGenome(np.array([2.2, 0.6, 0.1, 0.08, 0.8, 1.8, 0.02], dtype=np.float32))
p = morph.to_dict()

with open(src_yaml, 'r', encoding='utf-8') as f:
    ydata = yaml.safe_load(f)

wingspan = p['wingspan']
wing_area = p['wing_area']
h_tail_area = p['h_tail_area']
v_tail_area = p['v_tail_area']
thrust_to_weight = p['thrust_to_weight']
total_mass = p['total_mass']
cg_x_offset = p['cg_x_offset']

chord = float(wing_area / max(wingspan, 1e-4))
ht_span = float(np.sqrt(3.0 * h_tail_area))
ht_chord = float(h_tail_area / max(ht_span, 1e-4))
vt_span = float(np.sqrt(1.5 * v_tail_area))
vt_chord = float(v_tail_area / max(vt_span, 1e-4))
total_thrust = float(thrust_to_weight * total_mass * 9.81)

ydata['motor_params']['total_thrust'] = total_thrust
ydata['main_wing_params']['chord'] = chord
ydata['main_wing_params']['span'] = float(0.70 * wingspan)
ydata['left_wing_flapped_params']['chord'] = chord
ydata['left_wing_flapped_params']['span'] = float(0.15 * wingspan)
ydata['right_wing_flapped_params']['chord'] = chord
ydata['right_wing_flapped_params']['span'] = float(0.15 * wingspan)
ydata['horizontal_tail_params']['chord'] = ht_chord
ydata['horizontal_tail_params']['span'] = ht_span
ydata['vertical_tail_params']['chord'] = vt_chord
ydata['vertical_tail_params']['span'] = vt_span

out_yaml = os.path.join(test_dir, 'fixedwing.yaml')
with open(out_yaml, 'w', encoding='utf-8') as f:
    yaml.dump(ydata, f)

tree = ET.parse(src_urdf)
root = tree.getroot()
mass_scale = total_mass / 2.35

for link in root.findall('link'):
    name = link.get('name')
    m = link.find('inertial/mass')
    if m is not None:
        cur_m = float(m.get('value', 0.0))
        if cur_m > 0:
            m.set('value', f'{cur_m * mass_scale:.4f}')
    if name == 'base_link':
        orig = link.find('inertial/origin')
        if orig is not None:
            orig.set('xyz', f'{cg_x_offset:.4f} 0 0')
    elif name == 'main_wing_link':
        for b in link.findall('.//box'):
            b.set('size', f'{chord:.4f} {0.70 * wingspan:.4f} 0.05')
    elif name in ('ail_left_link', 'ail_right_link'):
        for b in link.findall('.//box'):
            b.set('size', f'{chord:.4f} {0.15 * wingspan:.4f} 0.06')
    elif name == 'horizontal_tail_link':
        for b in link.findall('.//box'):
            b.set('size', f'{ht_chord:.4f} {ht_span:.4f} 0.05')
    elif name == 'vertical_tail_link':
        for b in link.findall('.//box'):
            b.set('size', f'{vt_chord:.4f} 0.05 {vt_span:.4f}')

for joint in root.findall('joint'):
    jname = joint.get('name')
    orig = joint.find('origin')
    if orig is not None:
        if jname == 'ail_left_joint':
            orig.set('xyz', f'-0.5 {0.425 * wingspan:.4f} 0')
        elif jname == 'ail_right_joint':
            orig.set('xyz', f'-0.5 {-0.425 * wingspan:.4f} 0')
        elif jname == 'vertical_tail_joint':
            orig.set('xyz', f'-1.1 0 {0.5 * vt_span:.4f}')

out_urdf = os.path.join(test_dir, 'fixedwing.urdf')
tree.write(out_urdf, encoding='utf-8', xml_declaration=True)
print('URDF & YAML generated successfully!')

cfg = load_config('configs/controller_only/p2b_open_sky.json')
cfg['simulation']['flight_dome_size'] = 100.0
env = FixedwingEnv(config=cfg, model_dir=test_dir)
obs, _ = env.reset(seed=42)
pid = FixedwingPIDController(dt=1.0/env.control_hz, dome_radius=100.0)

for step in range(30):
    act = pid.predict(obs)
    obs, rew, term, trunc, info = env.step(act)
    if term or trunc:
        break

metrics = env.get_metrics()
print('Simulation ran successfully! Steps:', step + 1, 'Distance:', metrics.get('distance'), 'Survival:', metrics.get('survival_time'))
