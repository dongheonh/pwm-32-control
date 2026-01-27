# SAM LAB, D H HAN
# 4x8 electromagnet GUI (NO DECAY)
# - region1/region2: vibrating regions (square wave in time)
# - trap: always-ON magnets (independent of vibration)
#
# Change requested:
# - Allow intensity_range to be given as either:
#     (neg_level, pos_level)  e.g. (-1, 1)  => start with NEG when polarity="alt"
#   or
#     (pos_level, neg_level)  e.g. (1, -1)  => start with POS when polarity="alt"
# - Interpretation rule for polarity="alt":
#     k = floor(now / period)
#     if k even  -> "start polarity" sign (set by intensity_range ordering)
#     if k odd   -> opposite sign
#
# ===================== CONFIG (EDIT ONLY THESE) =====================
# Coordinates: (row,col), 1-indexed, (1,1)=LEFT-BOTTOM

# --- vibrating region 1 ---
location = [(1, 1), (1,3), (2,2), (2,4), (3,1), (3,3), (4,2), (4,4)]
intensity_range = (-1, 1)     # can be (-, +) OR (+, -) to set start sign
polarity = "alt"              # "pos", "neg", "alt"
period = 1/2                    # [sec]
dutycycle = 1                 # [0,1]

# --- vibrating region 2 ---
location2 = [(1, 2), (1,4), (2,1), (2,3), (3,2), (3,4), (4,1), (4,3)]
intensity_range2 = (1, -1)    # start with +1 when polarity="alt"
polarity2 = "alt"
period2 = 1/2
dutycycle2 = 1

# --- trap magnets (always ON) ---
trap_location =  [(5,1), (5,3), (6,2), (6,4), (7,1), (7,3), (8,2), (8,4), (5,2), (5,4), (6,1), (6,3), (7,2), (7,4), (8,1), (8,3)] 
trap_intensity = 0.8         # [-1,1]

SERIAL_PORT = '/dev/cu.usbmodem1020BA0ABA902'
SERIAL_BAUD = 115200
SEND_HZ = 10
PWM_MAX = 10                  # hardware scaling (0..PWM_MAX)
# ====================================================================

import pygame
import numpy as np
import serial
import time

# UI
SCREEN_W, SCREEN_H = 800, 550
FPS = 30
BG_COLOR   = (30, 30, 30)
GRID_COLOR = (80, 80, 80)
POS_COLOR  = (255, 0, 0)
NEG_COLOR  = (0, 0, 255)
TEXT_COLOR = (255, 255, 255)
TABLE_BG   = (15, 15, 15)
TABLE_GRID = (70, 70, 70)

# Grid
n, m = 4, 8

def create_grid(n, m):
    # grid[i,j] = [pos_pwm, neg_pwm, reserved]
    return np.zeros((n, m, 3), dtype=float)

grid_data = create_grid(n, m)

pygame.init()
screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
pygame.display.set_caption("4x8 magnet GUI (2 regions + trap + square vibration)")
clock = pygame.time.Clock()

def clamp(x, lo, hi):
    return lo if x < lo else hi if x > hi else x

def draw_text(surface, text, pos, center=False, size=18, color=TEXT_COLOR):
    f = pygame.font.SysFont(None, size)
    img = f.render(str(text), True, color)
    rect = img.get_rect()
    if center:
        rect.center = pos
    else:
        rect.topleft = pos
    surface.blit(img, rect)

def get_dynamic_tile_size(n, m):
    tile_size = min((SCREEN_W - 20)//m, (SCREEN_H - 180)//n)
    return max(4, tile_size)

def draw_grid(grid):
    tile = get_dynamic_tile_size(n, m)
    grid_w, grid_h = m * tile, n * tile
    x0 = (SCREEN_W - grid_w) // 2
    y0 = 20
    screen.fill(BG_COLOR)

    for i in range(n):
        for j in range(m):
            x = x0 + j * tile
            y = y0 + i * tile
            pos_val, neg_val, _ = grid[i, j]

            if pos_val > 0:
                alpha = int(np.clip(255.0 * (pos_val / PWM_MAX), 25, 255))
                surf = pygame.Surface((tile - 2, tile - 2), pygame.SRCALPHA)
                surf.fill((*POS_COLOR, alpha))
                screen.blit(surf, (x, y))
            elif neg_val > 0:
                alpha = int(np.clip(255.0 * (neg_val / PWM_MAX), 25, 255))
                surf = pygame.Surface((tile - 2, tile - 2), pygame.SRCALPHA)
                surf.fill((*NEG_COLOR, alpha))
                screen.blit(surf, (x, y))
            else:
                pygame.draw.rect(screen, GRID_COLOR, (x, y, tile - 2, tile - 2))

    return x0, y0 + grid_h, grid_w, tile, y0

def draw_table(grid, pos_x, pos_y, width):
    table_top = pos_y + 10
    cell_h = 28
    cell_w = max(width // max(m, 1), 28)
    pygame.draw.rect(screen, TABLE_BG, (pos_x, table_top, m * cell_w, n * cell_h))

    for i in range(n):
        user_row = n - i
        draw_text(screen, user_row, (pos_x - 26, table_top + i * cell_h + 6), size=16, color=(200, 220, 180))
        for j in range(m):
            cx = pos_x + j * cell_w + cell_w // 2
            cy = table_top + i * cell_h + cell_h // 2
            pv = int(round(grid[i, j][0]))
            nv = int(round(grid[i, j][1]))
            draw_text(screen, f"{pv}/{nv}", (cx, cy), center=True, size=16)

    for i in range(n + 1):
        y = table_top + i * cell_h
        pygame.draw.line(screen, TABLE_GRID, (pos_x, y), (pos_x + m * cell_w, y))
    for j in range(m + 1):
        x = pos_x + j * cell_w
        pygame.draw.line(screen, TABLE_GRID, (x, table_top), (x, table_top + n * cell_h))

def user_to_ij(rc):
    r, c = rc
    i = n - int(r)       # 1-indexed bottom -> 0-indexed top
    j = int(c) - 1
    return i, j

def square_gate(now, period, dutycycle):
    T = float(period)
    if T <= 0:
        return 1.0
    d = clamp(float(dutycycle), 0.0, 1.0)
    phase = now % T
    return 1.0 if phase < (d * T) else 0.0

def clear_all(grid):
    grid[:, :, :] = 0.0

def add_cells(grid, cells, signed_level):
    """
    signed_level in [-1,1]
    + => pos channel, - => neg channel
    magnitude => abs(signed_level)*PWM_MAX
    """
    signed_level = clamp(float(signed_level), -1.0, 1.0)
    amp = abs(signed_level) * PWM_MAX
    if amp <= 0:
        return

    for rc in cells:
        i, j = user_to_ij(rc)
        if 0 <= i < n and 0 <= j < m:
            if signed_level >= 0:
                grid[i, j][0] = max(grid[i, j][0], amp)
                grid[i, j][1] = 0.0
            else:
                grid[i, j][1] = max(grid[i, j][1], amp)
                grid[i, j][0] = 0.0

def parse_intensity_range(ir):
    """
    Accept either ordering:
      (-, +) or (+, -)

    Returns:
      neg_level <= 0
      pos_level >= 0
      start_sign_for_alt in {+1,-1}:
        - if ir[0] >= 0 and ir[1] <= 0  => start with POS (+1)
        - if ir[0] <= 0 and ir[1] >= 0  => start with NEG (-1)
        - otherwise (ambiguous): default start with POS
    """
    a, b = float(ir[0]), float(ir[1])

    # clamp raw values first
    a = clamp(a, -1.0, 1.0)
    b = clamp(b, -1.0, 1.0)

    if a >= 0 and b <= 0:
        # (pos, neg)
        pos_level = clamp(a, 0.0, 1.0)
        neg_level = clamp(b, -1.0, 0.0)
        start_sign = +1
    elif a <= 0 and b >= 0:
        # (neg, pos)
        neg_level = clamp(a, -1.0, 0.0)
        pos_level = clamp(b, 0.0, 1.0)
        start_sign = -1
    else:
        # ambiguous (both >=0 or both <=0): interpret as (neg,pos) by magnitude and start POS
        neg_level = clamp(min(a, b), -1.0, 0.0)
        pos_level = clamp(max(a, b), 0.0, 1.0)
        start_sign = +1

    return neg_level, pos_level, start_sign

def polarity_sign(now, polarity, period, start_sign_for_alt):
    """
    For polarity="alt", the FIRST half-period (k=0) uses start_sign_for_alt.
    """
    if polarity == "pos":
        return +1
    if polarity == "neg":
        return -1

    T = float(period)
    if T <= 0:
        return start_sign_for_alt

    k = int(now // T)          # period index
    return start_sign_for_alt if (k % 2 == 0) else -start_sign_for_alt

def apply_location_vibration_region(grid, now, location, intensity_range, polarity, period, dutycycle):
    g = square_gate(now, period, dutycycle)
    if g <= 0:
        return

    neg_level, pos_level, start_sign = parse_intensity_range(intensity_range)
    s = polarity_sign(now, polarity, period, start_sign)

    signed_level = pos_level if s > 0 else neg_level
    add_cells(grid, location, signed_level)

# Serial open
ser = None
try:
    ser = serial.Serial(SERIAL_PORT, SERIAL_BAUD, timeout=0)
    time.sleep(2)
except Exception as e:
    print(f"Serial open error: {e}")
    ser = None

def get_output_matrix(grid):
    arr = np.round(grid[:, :, :2]).astype(int).reshape(-1, 2)  # (n*m, 2)
    flat = arr.flatten()                                       # length = n*m*2
    group = 16
    rows = len(flat) // group
    A = np.zeros((rows, group), dtype=int)
    for idx, v in enumerate(flat):
        A[idx // group, idx % group] = v
    return A

def matrix_to_csv_string(A):
    return ",".join(str(int(v)) for v in A.flatten())

def send_matrix_over_serial(A, ser):
    ser.write((matrix_to_csv_string(A) + "\n").encode("utf-8"))

last_sent = time.time()
send_dt = 1.0 / float(SEND_HZ)
running = True

while running:
    now = time.time()

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            running = False

    # compose field
    clear_all(grid_data)

    # region 1
    apply_location_vibration_region(
        grid_data, now,
        location, intensity_range, polarity, period, dutycycle
    )

    # region 2
    apply_location_vibration_region(
        grid_data, now,
        location2, intensity_range2, polarity2, period2, dutycycle2
    )

    # always-on trap (applied last)
    add_cells(grid_data, trap_location, trap_intensity)

    # draw
    x0, pos_y, grid_w, _, _ = draw_grid(grid_data)
    draw_table(grid_data, x0, pos_y, grid_w)

    # show current signs (helpful debug)
    n1, p1, start1 = parse_intensity_range(intensity_range)
    n2, p2, start2 = parse_intensity_range(intensity_range2)
    s1 = polarity_sign(now, polarity, period, start1)
    s2 = polarity_sign(now, polarity2, period2, start2)

    draw_text(screen, f"region1 location: {location}", (20, SCREEN_H - 130))
    draw_text(screen, f"region1 intensity_range={intensity_range} (start={'POS' if start1>0 else 'NEG'})", (20, SCREEN_H - 108))
    draw_text(screen, f"region1 T={period}s, duty={dutycycle}, gate={int(square_gate(now, period, dutycycle))}, sign={'POS' if s1>0 else 'NEG'}",
              (20, SCREEN_H - 86))

    draw_text(screen, f"region2 location: {location2}", (20, SCREEN_H - 64))
    draw_text(screen, f"region2 intensity_range={intensity_range2} (start={'POS' if start2>0 else 'NEG'})", (20, SCREEN_H - 42))
    draw_text(screen, f"region2 T={period2}s, duty={dutycycle2}, gate={int(square_gate(now, period2, dutycycle2))}, sign={'POS' if s2>0 else 'NEG'}",
              (20, SCREEN_H - 20))

    draw_text(screen, f"trap: {trap_location}, I={trap_intensity}", (420, SCREEN_H - 20))

    # send
    A = get_output_matrix(grid_data)
    if ser and (now - last_sent) >= send_dt:
        try:
            send_matrix_over_serial(A, ser)
        except Exception as e:
            print("Serial write error:", e)
        last_sent = now

    pygame.display.flip()
    clock.tick(FPS)

if ser:
    ser.close()
pygame.quit()
