# SAM LAB, D H HAN
# 09/23/2025
# Fixed 4x8 electromagnet GUI -> simple, no setup UI

import pygame
import numpy as np
import serial
import time

# ================== Config ==================
SERIAL_PORT = '/dev/cu.usbmodem1020BA0ABA902'
DECAY_DURATION = 0.1        # decaying time: how long do you want to turn magnet on?
maxIntensity = 10           # maximum intensity of each magnet [0,10]
# ================== Config ==================













# === Pygame / UI ===
SERIAL_BAUD = 115200
SCREEN_W, SCREEN_H = 800, 550
FPS = 30
BG_COLOR   = (30, 30, 30)
GRID_COLOR = (80, 80, 80)
POS_COLOR  = (255, 0, 0)  # positive (shown when grid[i,j,0] > 0)
NEG_COLOR  = (0, 0, 255)  # negative (shown when grid[i,j,1] > 0)
TEXT_COLOR = (255, 255, 255)
TABLE_BG   = (15, 15, 15)
TABLE_GRID = (70, 70, 70)

# === Grid fixed ===
n, m = 4, 8  # rows=4, cols=8 (fixed)

def create_grid(n, m):
    # channels: [pos_val (0..10), neg_val (0..10), t_start]
    return np.zeros((n, m, 3), dtype=float)

grid_data = create_grid(n, m)

pygame.init()
screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
clock  = pygame.time.Clock()

def draw_text(surface, text, pos, center=False, size=28, color=TEXT_COLOR):
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

# this is to show grid (control input in UI)
def draw_grid(grid):
    tile = get_dynamic_tile_size(n, m)
    grid_w, grid_h = m*tile, n*tile
    x0 = (SCREEN_W - grid_w)//2
    y0 = 20
    screen.fill(BG_COLOR)
    for i in range(n):
        for j in range(m):
            x = x0 + j*tile
            y = y0 + i*tile
            pos_val, neg_val, _ = grid[i, j]
            if pos_val > 0:
                alpha = int(np.clip(25.5 * pos_val, 25, 255))
                surf = pygame.Surface((tile-2, tile-2), pygame.SRCALPHA)
                surf.fill((*POS_COLOR, alpha))
                screen.blit(surf, (x, y))
            elif neg_val > 0:
                alpha = int(np.clip(25.5 * neg_val, 25, 255))
                surf = pygame.Surface((tile-2, tile-2), pygame.SRCALPHA)
                surf.fill((*NEG_COLOR, alpha))
                screen.blit(surf, (x, y))
            else:
                pygame.draw.rect(screen, GRID_COLOR, (x, y, tile-2, tile-2))
    return x0, y0 + grid_h, grid_w, tile, y0

def update_decay(grid):
    now = time.time()
    for i in range(n):
        for j in range(m):
            pos_val, neg_val, t0 = grid[i, j]
            if t0 > 0:
                elapsed = now - t0
                if elapsed < DECAY_DURATION:
                    k = 1.0 - (elapsed / DECAY_DURATION)
                    if pos_val > 0: grid[i, j][0] = 10 * k
                    if neg_val > 0: grid[i, j][1] = 10 * k
                else:
                    grid[i, j][:] = 0.0

def draw_table(grid, pos_x, pos_y, width):
    # limited pretty print up to 16x32; here it’s 4x8 so fine.
    table_top = pos_y + 10
    cell_h = 28
    cell_w = max(width // max(m, 1), 28)
    pygame.draw.rect(screen, TABLE_BG, (pos_x, table_top, m*cell_w, n*cell_h))
    for i in range(n):
        ry = table_top + i*cell_h + cell_h//2
        draw_text(screen, i, (pos_x - 20, table_top + i*cell_h + 3), center=False, size=16, color=(200,220,180))
        for j in range(m):
            cx = pos_x + j*cell_w + cell_w//2
            pos_val = int(round(grid[i,j][0]))
            neg_val = int(round(grid[i,j][1]))
            draw_text(screen, f"{pos_val}/{neg_val}", (cx, ry), center=True, size=16)
    for i in range(n+1):
        y = table_top + i*cell_h
        pygame.draw.line(screen, TABLE_GRID, (pos_x, y), (pos_x + m*cell_w, y))
    for j in range(m+1):
        x = pos_x + j*cell_w
        pygame.draw.line(screen, TABLE_GRID, (x, table_top), (x, table_top + n*cell_h))

def get_output_matrix(grid):
    # Flatten [pos,neg] pairs (rounded to int)
    arr  = np.round(grid[:, :, :2]).astype(int).reshape(-1, 2)  # (n*m, 2)
    flat = arr.flatten()                                        # length = n*m*2 = 64
    group = 16  # m==8 => (m//8)*16 = 16
    rows  = len(flat) // group
    A = np.zeros((rows, group), dtype=int)
    for idx, v in enumerate(flat):
        A[idx // group, idx % group] = v
    return A

def matrix_to_csv_string(A):
    return ",".join(str(int(v)) for v in A.flatten())

def draw_csv_string(csv_str, pos_x, pos_y, width, label="CSV output ="):
    start_y = pos_y + 40
    max_chars = max(width // 12, 40)
    lines = [csv_str[i:i+max_chars] for i in range(0, len(csv_str), max_chars)]
    draw_text(screen, label, (pos_x, start_y), center=False, size=22, color=(255,220,150))
    for k, line in enumerate(lines[:8]):
        draw_text(screen, line, (pos_x + 40, start_y + 25 + k*22), center=False, size=18, color=(220,255,220))
    if len(lines) > 8:
        draw_text(screen, "...", (pos_x + 40, start_y + 25 + 8*22), center=False, size=18, color=(220,255,220))

def send_matrix_over_serial(A, ser):
    data_str = matrix_to_csv_string(A) + "\n"
    try:
        ser.write(data_str.encode('utf-8'))
    except Exception as e:
        print(f"Serial error: {e}")

# Open serial
ser = None
try:
    ser = serial.Serial(SERIAL_PORT, SERIAL_BAUD, timeout=0)
    time.sleep(2)
except Exception as e:
    print(f"Serial open error: {e}")

csv_input_str = ""
csv_output_str = ""
last_sent = time.time()
running = True

while running:
    now = time.time()
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.MOUSEBUTTONDOWN:
            # map mouse to cell and set impulse (L: neg=10, R: pos=10) strength: [0,100]
            # you can tunne maximum from the top
            x0, pos_y, grid_w, tile, y0 = draw_grid(grid_data)  # get geometry
            mx, my = pygame.mouse.get_pos()
            j = (mx - x0) // tile
            i = (my - y0) // tile
            if 0 <= i < n and 0 <= j < m:
                if event.button == 1:   # left click => negative
                    grid_data[i, j] = [0, maxIntensity, time.time()]
                elif event.button == 3: # right click => positive
                    grid_data[i, j] = [maxIntensity, 0, time.time()]

    update_decay(grid_data)
    x0, pos_y, grid_w, _, _ = draw_grid(grid_data)
    draw_table(grid_data, x0, pos_y, grid_w)

    # build & show CSV (for 4x8 always valid)
    A = get_output_matrix(grid_data)
    csv_output_str = matrix_to_csv_string(A)
    # draw_csv_string(csv_output_str, x0, pos_y + n*28 + 10, grid_w, label="CSV output =")

    # send @10Hz
    if ser and (now - last_sent) >= 0.1:
        send_matrix_over_serial(A, ser)
        last_sent = now

        # read echo or MCU response if any
        if ser.in_waiting:
            try:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                if line:
                    csv_input_str = line
            except Exception:
                pass

    #if csv_input_str:
        #draw_text(screen, "CSV input =", (x0, pos_y + n*28 + 10 + 220), center=False, size=22, color=(150,220,255))
        #draw_text(screen, csv_input_str[:120], (x0 + 120, pos_y + n*28 + 10 + 220), center=False, size=18, color=(200,220,255))
    pygame.display.flip()
    clock.tick(FPS)

if ser:
    ser.close()
pygame.quit()