import math
import numpy as np
from PIL import Image, ImageDraw, ImageFont

def get_font(size: int):
    try:
        return ImageFont.truetype("arial.ttf", size)
    except Exception:
        try:
            return ImageFont.truetype("calibri.ttf", size)
        except Exception:
            return ImageFont.load_default()

FONT_TITLE = get_font(18)
FONT_LABEL = get_font(13)
FONT_VALUE = get_font(15)
FONT_SMALL = get_font(11)

def draw_hud(
    frame_rgb: np.ndarray,
    roll: float,          # rad
    pitch: float,         # rad
    yaw: float,           # rad
    airspeed: float,      # m/s
    altitude: float,      # m
    climb_rate: float,    # m/s
    throttle: float,      # 0..1
    flight_time: float,   # s
    wp_idx: int,
    total_wps: int,
    dist_to_wp: float,    # m
    target_pos: np.ndarray | None,
    current_pos: np.ndarray,
    contender_name: str,
    test_title: str,
) -> np.ndarray:
    """Renders a modern, professional aviation glass cockpit HUD overlay onto frame_rgb."""
    img = Image.fromarray(frame_rgb)
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    W, H = img.size
    cx, cy = W // 2, H // 2

    CYAN = (0, 240, 255, 230)
    CYAN_DIM = (0, 200, 230, 140)
    GREEN = (50, 255, 120, 230)
    AMBER = (255, 190, 20, 230)
    WHITE = (240, 245, 255, 240)
    WHITE_DIM = (200, 210, 230, 140)
    DARK_BG = (10, 20, 30, 175)
    DARK_BADGE = (12, 24, 38, 200)

    # -------------------------------------------------------------
    # 1. TOP HEADER BANNER (Contender & Flight Details)
    # -------------------------------------------------------------
    d.rectangle([(0, 0), (W, 48)], fill=(8, 16, 26, 215))
    d.line([(0, 48), (W, 48)], fill=(0, 200, 240, 180), width=1)
    
    # Title & Subtitle
    d.text((20, 10), "PROJECT TALOS // 3D FLIGHT TELEMETRY", font=FONT_TITLE, fill=CYAN)
    d.text((20, 30), f"CONTENDER: {contender_name.upper()}", font=FONT_SMALL, fill=WHITE)
    
    # Mission Test Name & Time in Center/Right
    test_text = f"MISSION: {test_title}"
    d.text((W // 2 - 120, 14), test_text, font=FONT_VALUE, fill=WHITE)
    time_text = f"T+{flight_time:05.1f}s"
    d.text((W - 130, 14), time_text, font=FONT_TITLE, fill=GREEN)

    # -------------------------------------------------------------
    # 2. TOP HEADING COMPASS TAPE
    # -------------------------------------------------------------
    comp_y = 60
    comp_w = 320
    comp_h = 26
    d.rectangle([(cx - comp_w // 2, comp_y), (cx + comp_w // 2, comp_y + comp_h)], fill=DARK_BADGE, outline=CYAN_DIM)
    
    deg_yaw = (math.degrees(yaw)) % 360
    cardinals = {0: "N", 45: "NE", 90: "E", 135: "SE", 180: "S", 225: "SW", 270: "W", 315: "NW"}
    
    for offset in range(-75, 76, 15):
        h_deg = (int(deg_yaw) + offset) % 360
        px = cx + offset * 2
        if cx - comp_w // 2 + 8 <= px <= cx + comp_w // 2 - 8:
            if h_deg in cardinals:
                d.text((px - 7, comp_y + 4), cardinals[h_deg], font=FONT_SMALL, fill=CYAN)
            else:
                d.line([(px, comp_y + 12), (px, comp_y + comp_h - 2)], fill=CYAN_DIM, width=1)
                
    # Center Heading Pointer
    d.polygon([(cx, comp_y + comp_h + 2), (cx - 5, comp_y + comp_h + 8), (cx + 5, comp_y + comp_h + 8)], fill=AMBER)
    d.text((cx - 14, comp_y + comp_h + 9), f"{int(deg_yaw):03d}°", font=FONT_SMALL, fill=AMBER)

    # Waypoint bearing pointer on compass tape
    if target_pos is not None:
        rel_vec = target_pos - current_pos
        wp_bearing_deg = (math.degrees(math.atan2(rel_vec[1], rel_vec[0]))) % 360
        bearing_diff = (wp_bearing_deg - deg_yaw + 180) % 360 - 180
        if -75 <= bearing_diff <= 75:
            b_px = cx + bearing_diff * 2
            if cx - comp_w // 2 + 5 <= b_px <= cx + comp_w // 2 - 5:
                # Green diamond for waypoint
                d.polygon([(b_px, comp_y + 1), (b_px - 4, comp_y + 6), (b_px, comp_y + 11), (b_px + 4, comp_y + 6)], fill=GREEN)

    # -------------------------------------------------------------
    # 3. ARTIFICIAL HORIZON & PITCH LADDER
    # -------------------------------------------------------------
    pitch_deg = math.degrees(pitch)
    pitch_px_offset = pitch_deg * 4.0
    
    sin_r = math.sin(-roll)
    cos_r = math.cos(-roll)

    # Center aircraft reticle (waterline marker)
    d.line([(cx - 28, cy), (cx - 10, cy)], fill=AMBER, width=2)
    d.line([(cx - 10, cy), (cx - 10, cy + 7)], fill=AMBER, width=2)
    d.line([(cx + 10, cy), (cx + 28, cy)], fill=AMBER, width=2)
    d.line([(cx + 10, cy), (cx + 10, cy + 7)], fill=AMBER, width=2)
    d.ellipse([(cx - 4, cy - 4), (cx + 4, cy + 4)], fill=None, outline=AMBER, width=2)

    # Pitch ladder for -30° to +30°
    for deg in range(-30, 31, 10):
        line_half = 75 if deg == 0 else 40
        dy = -(deg * 4.0 - pitch_px_offset)
        if -140 <= dy <= 140:
            p1_x = cx + (-line_half) * cos_r - dy * sin_r
            p1_y = cy + (-line_half) * sin_r + dy * cos_r
            p2_x = cx + (line_half) * cos_r - dy * sin_r
            p2_y = cy + (line_half) * sin_r + dy * cos_r
            
            color = CYAN if deg == 0 else (CYAN_DIM if deg > 0 else (255, 120, 100, 170))
            width = 2 if deg == 0 else 1
            d.line([(p1_x, p1_y), (p2_x, p2_y)], fill=color, width=width)
            
            if deg != 0 and abs(dy) > 12:
                d.text((p1_x - 22, p1_y - 6), f"{abs(deg)}", font=FONT_SMALL, fill=color)

    # Roll & Pitch values under reticle
    roll_deg = math.degrees(roll)
    d.text((cx - 25, cy + 115), f"ROLL:  {roll_deg:+03.0f}°", font=FONT_SMALL, fill=WHITE_DIM)
    d.text((cx - 25, cy + 130), f"PITCH: {pitch_deg:+03.0f}°", font=FONT_SMALL, fill=WHITE_DIM)

    # -------------------------------------------------------------
    # 4. SPEED TAPE (Left) & ALTITUDE TAPE (Right)
    # -------------------------------------------------------------
    tape_h = 240
    sp_x = 75
    d.rectangle([(sp_x, cy - tape_h // 2), (sp_x + 65, cy + tape_h // 2)], fill=DARK_BG, outline=CYAN_DIM)
    d.text((sp_x + 8, cy - tape_h // 2 + 5), "AIRSPEED", font=FONT_SMALL, fill=WHITE_DIM)
    
    for sp in range(int(airspeed) - 15, int(airspeed) + 16, 5):
        if sp < 0:
            continue
        sy = cy - (sp - airspeed) * 7
        if cy - tape_h // 2 + 25 <= sy <= cy + tape_h // 2 - 10:
            d.line([(sp_x + 45, sy), (sp_x + 63, sy)], fill=CYAN_DIM, width=1)
            d.text((sp_x + 12, sy - 6), f"{sp:2d}", font=FONT_SMALL, fill=WHITE_DIM)
            
    # Center Current Speed Box
    d.rectangle([(sp_x - 6, cy - 14), (sp_x + 74, cy + 14)], fill=(15, 30, 45, 240), outline=AMBER, width=2)
    d.text((sp_x + 2, cy - 8), f"{airspeed:4.1f} m/s", font=FONT_VALUE, fill=WHITE)

    # Stall warning indicator
    if airspeed < 9.0:
        d.rectangle([(sp_x - 6, cy + 18), (sp_x + 74, cy + 36)], fill=(180, 20, 20, 220))
        d.text((sp_x + 10, cy + 20), "STALL WARN", font=FONT_SMALL, fill=WHITE)

    # Altitude Tape (Right)
    alt_x = W - 140
    d.rectangle([(alt_x, cy - tape_h // 2), (alt_x + 65, cy + tape_h // 2)], fill=DARK_BG, outline=CYAN_DIM)
    d.text((alt_x + 10, cy - tape_h // 2 + 5), "ALTITUDE", font=FONT_SMALL, fill=WHITE_DIM)
    
    for a in range(int(altitude) - 15, int(altitude) + 16, 5):
        if a < 0:
            continue
        ay = cy - (a - altitude) * 7
        if cy - tape_h // 2 + 25 <= ay <= cy + tape_h // 2 - 10:
            d.line([(alt_x + 2, ay), (alt_x + 20, ay)], fill=CYAN_DIM, width=1)
            d.text((alt_x + 26, ay - 6), f"{a:2d}", font=FONT_SMALL, fill=WHITE_DIM)
            
    # Center Current Alt Box
    d.rectangle([(alt_x - 8, cy - 14), (alt_x + 72, cy + 14)], fill=(15, 30, 45, 240), outline=AMBER, width=2)
    d.text((alt_x - 2, cy - 8), f"{altitude:4.1f} m", font=FONT_VALUE, fill=WHITE)

    # Climb rate (VSI)
    vsi_color = GREEN if climb_rate >= 0 else (255, 100, 100, 240)
    d.text((alt_x + 4, cy + tape_h // 2 + 6), f"VSI: {climb_rate:+4.1f} m/s", font=FONT_SMALL, fill=vsi_color)

    # -------------------------------------------------------------
    # 5. WAYPOINT TARGET HUD CARD (Bottom-Left)
    # -------------------------------------------------------------
    wp_card_w = 260
    wp_card_h = 105
    wpx = 25
    wpy = H - wp_card_h - 25
    d.rectangle([(wpx, wpy), (wpx + wp_card_w, wpy + wp_card_h)], fill=DARK_BG, outline=GREEN, width=2)
    
    # Waypoint Title badge
    d.rectangle([(wpx, wpy), (wpx + wp_card_w, wpy + 24)], fill=(16, 55, 36, 230))
    wp_status_str = f"TARGET WAYPOINT // WP {min(wp_idx + 1, total_wps)} of {total_wps}"
    d.text((wpx + 10, wpy + 5), wp_status_str, font=FONT_SMALL, fill=GREEN)
    
    if target_pos is not None:
        d.text((wpx + 12, wpy + 32), f"DIST TO WP:  {dist_to_wp:5.1f} m", font=FONT_VALUE, fill=WHITE)
        d.text((wpx + 12, wpy + 54), f"WP COORDS: [{target_pos[0]:4.0f}, {target_pos[1]:4.0f}, {target_pos[2]:4.0f}]", font=FONT_SMALL, fill=CYAN)
        d.text((wpx + 12, wpy + 74), f"PLANE POS:  [{current_pos[0]:4.0f}, {current_pos[1]:4.0f}, {current_pos[2]:4.0f}]", font=FONT_SMALL, fill=WHITE_DIM)
    else:
        d.text((wpx + 12, wpy + 48), "COURSE COMPLETE!", font=FONT_TITLE, fill=GREEN)
        d.text((wpx + 12, wpy + 74), "ALL WAYPOINTS CAPTURED", font=FONT_SMALL, fill=WHITE)

    # -------------------------------------------------------------
    # 6. ENGINE THROTTLE & CONTROL STATUS (Bottom-Right)
    # -------------------------------------------------------------
    th_w = 220
    th_h = 105
    thx = W - th_w - 25
    thy = H - th_h - 25
    d.rectangle([(thx, thy), (thx + th_w, thy + th_h)], fill=DARK_BG, outline=CYAN_DIM, width=1)
    
    d.text((thx + 12, thy + 8), "PROPULSION & CONTROL", font=FONT_SMALL, fill=CYAN)
    
    # Throttle bar
    d.text((thx + 12, thy + 30), f"THROTTLE: {int(throttle * 100)}%", font=FONT_VALUE, fill=WHITE)
    d.rectangle([(thx + 12, thy + 54), (thx + th_w - 15, thy + 66)], fill=(20, 30, 40, 200), outline=WHITE_DIM)
    th_fill_w = int((th_w - 27) * min(max(throttle, 0.0), 1.0))
    if th_fill_w > 0:
        d.rectangle([(thx + 13, thy + 55), (thx + 13 + th_fill_w, thy + 65)], fill=CYAN)
        
    d.text((thx + 12, thy + 74), "SURFACE CTRL: 6-AXIS DIRECT", font=FONT_SMALL, fill=GREEN)

    # Composite
    out = Image.alpha_composite(img.convert("RGBA"), overlay)
    return np.asarray(out.convert("RGB"))
