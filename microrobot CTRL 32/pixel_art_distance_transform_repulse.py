# SAM LAB, D H HAN
# 4x8 electromagnet herding GUI (target = location cells)
#
# Goal:
# - Attraction: keep TARGET cells ON with one polarity.
# - Repulsion squeeze: every time-frame, activate ~TARGET (or outside band) with the OPPOSITE polarity
#   to push/squeeze particles toward the target region.
#
# Usage:
# - Click "Start" (or press SPACE): run herding bands (outside -> inside) + repulsion squeeze.
# - Click "Stop" (or ESC): sends all zeros and exits.
#
# Coordinate convention:
# - ONE_BASED_CELLS uses (row, col) with 1-based indexing, where (1,1) is the LEFT-BOTTOM of the grid.

import pygame
import numpy as np
import time
import serial
from collections import deque

# ================== Config ==================
SERIAL_PORTS = ['/dev/cu.usbmodem1020BA0ABA902']

# Polarity convention (matches your UI labeling):
# direction =  1 -> NEG channel is the "attract" polarity (red)
# direction = -1 -> POS channel is the "attract" polarity (green)
direction = 1

# ------------------ Target location (1-based, (1,1)=LEFT-BOTTOM) ------------------
ONE_BASED_CELLS = [
    (2, 4), (2, 5), (3, 4), (3, 5)
]

# Herding timing (k: Dmax -> 0)
HERD_PULSE_DT = 5.0            # seconds: time between band steps (outside -> inside)
HERD_OVERLAP = True            # keep ring k and k-1 briefly together (visual smoothing)
HERD_OVERLAP_HOLD = 2.0        # seconds: overlap duration

FINAL_HOLD = True              # keep final target ON continuously after herding

# Serial
SERIAL_BAUD = 115200
SERIAL_SEND_DT = 0.10          # seconds: serial update interval (~10 Hz)

# Command amplitudes (0..10)
PWM_MAX = 10.0                 # maximum value sent per channel
ATTRACT_AMP = 10.0             # target strength
REPEL_AMP = 10               # squeeze strength (start lower than ATTRACT_AMP)

# Repulsion squeeze mode:
# - "complement": repel_mask = ~target (strong, global squeeze)
# - "outside_band": repel_mask = (D >= k+1) & ~target (push from outside toward current band)
REPEL_MODE = "outside_band"
# ================== Config ==================

# Convert (1-based, left-bottom origin) -> internal (0-based, top-left origin)
# N_ROWS is fixed = 4; mapping: i = N_ROWS - row, j = col - 1
N_ROWS, N_COLS = 4, 8
CELLS = [(N_ROWS - r, c - 1) for (r, c) in ONE_BASED_CELLS]

# UI
SCREEN_W, SCREEN_H = 800, 800
FPS = 30
BG_COLOR = (30, 30, 30)
GRID_COLOR = (80, 80, 80)
POS_COLOR = (0, 255, 0)   # POS channel visualization (green)
NEG_COLOR = (255, 0, 0)   # NEG channel visualization (red)
BUTTON_BG = (60, 60, 60)
BUTTON_BG_HOVER = (90, 90, 90)
TEXT_COLOR = (240, 240, 240)

# ---------------------------------------------
# Helpers
# ---------------------------------------------
def create_grid(n, m):
    # channels: [pos_val, neg_val, unused]
    return np.zeros((n, m, 3), dtype=float)

def get_dynamic_tile_size(n, m):
    tile_size = min((SCREEN_W - 40) // m, (SCREEN_H - 220) // n)
    return max(8, tile_size)

def draw_text(surface, text, pos, size=28, color=TEXT_COLOR, center=False):
    font = pygame.font.SysFont(None, size)
    img = font.render(str(text), True, color)
    rect = img.get_rect()
    if center:
        rect.center = pos
    else:
        rect.topleft = pos
    surface.blit(img, rect)
    return rect

def draw_grid(surface, grid):
    n, m, _ = grid.shape
    tile = get_dynamic_tile_size(n, m)
    grid_w, grid_h = m * tile, n * tile
    x0 = (SCREEN_W - grid_w) // 2
    y0 = 70

    for i in range(n):
        for j in range(m):
            x = x0 + j * tile
            y = y0 + i * tile
            pos_val, neg_val, _ = grid[i, j]
            rect = pygame.Rect(x, y, tile - 2, tile - 2)

            if pos_val > 0:
                alpha = int(max(25, min(255, 25.5 * (pos_val))))
                surf = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
                surf.fill((*POS_COLOR, alpha))
                surface.blit(surf, rect)
            elif neg_val > 0:
                alpha = int(max(25, min(255, 25.5 * (neg_val))))
                surf = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
                surf.fill((*NEG_COLOR, alpha))
                surface.blit(surf, rect)
            else:
                pygame.draw.rect(surface, GRID_COLOR, rect, 1)

    pygame.draw.rect(surface, GRID_COLOR, (x0, y0, grid_w, grid_h), 2)
    return (x0, y0, tile)

def get_output_matrix(grid):
    # pack [pos,neg] (2 channels) into rows of 16 ints
    arr = np.round(grid[:, :, :2]).astype(int).reshape(-1, 2)
    flat = arr.flatten()
    group = 16
    num_rows = (len(flat) + group - 1) // group
    A = np.zeros((num_rows, group), dtype=int)
    for idx, val in enumerate(flat):
        A[idx // group, idx % group] = val
    return A

def try_open_serial():
    for port in SERIAL_PORTS:
        try:
            ser = serial.Serial(port, SERIAL_BAUD, timeout=0)
            time.sleep(1.5)
            print(f"Serial opened: {port}")
            return ser
        except Exception:
            continue
    print("Serial not found; running without serial output.")
    return None

def send_matrix_over_serial(A, ser):
    if ser is None:
        return
    try:
        data = ",".join(str(int(v)) for v in A.flatten()) + "\n"
        ser.write(data.encode("utf-8"))
    except Exception:
        pass

def clear_all_pwm(grid, ser):
    grid[:, :, :2] = 0.0
    A = get_output_matrix(grid)
    send_matrix_over_serial(A, ser)

# --- Distance map & masks ---
def build_target_mask(n, m, cells):
    mask = np.zeros((n, m), dtype=bool)
    for (i, j) in cells:
        if 0 <= i < n and 0 <= j < m:
            mask[i, j] = True
    return mask

def manhattan_distance_to_targets(n, m, target_mask):
    D = np.full((n, m), np.inf, dtype=float)
    q = deque()
    ti, tj = np.where(target_mask)
    for i, j in zip(ti, tj):
        D[i, j] = 0
        q.append((i, j))

    while q:
        i, j = q.popleft()
        for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ni, nj = i + di, j + dj
            if 0 <= ni < n and 0 <= nj < m and D[ni, nj] > D[i, j] + 1:
                D[ni, nj] = D[i, j] + 1
                q.append((ni, nj))

    D[np.isinf(D)] = 0
    return D.astype(int)

def clamp_amp(x):
    return float(max(0.0, min(float(PWM_MAX), float(x))))

def apply_attract_and_repel(grid, target_mask, repel_mask, direction, attract_amp, repel_amp):
    """
    direction =  1: NEG(red) is attract channel, POS(green) is repel channel
    direction = -1: POS(green) is attract channel, NEG(red) is repel channel

    We set BOTH masks every frame (squeeze).
    """
    a = clamp_amp(attract_amp)
    r = clamp_amp(repel_amp)

    grid[:, :, :2] = 0.0  # reset every frame

    if direction == -1:
        # attract = POS (green)
        grid[target_mask, 0] = a
        # repel = NEG (red)
        grid[repel_mask, 1] = r
    else:
        # attract = NEG (red)
        grid[target_mask, 1] = a
        # repel = POS (green)
        grid[repel_mask, 0] = r

def band_masks(D, k, overlap):
    """
    Return the "active band" mask (ring) for visualization / herding schedule.
    If overlap=True, include k and k-1.
    """
    if overlap and k > 0:
        return (D == k) | (D == (k - 1))
    return (D == k)

# ---------------------------------------------
# Main
# ---------------------------------------------
def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    clock = pygame.time.Clock()

    grid = create_grid(N_ROWS, N_COLS)

    # UI buttons
    start_rect = pygame.Rect(0, 0, 180, 60)
    start_rect.center = (SCREEN_W // 2, SCREEN_H - 140)

    stop_rect = pygame.Rect(0, 0, 180, 60)
    stop_rect.center = (SCREEN_W // 2, SCREEN_H - 70)

    ser = try_open_serial()
    last_send_t = 0.0

    # Target mask and Manhattan distance to target cells
    target_mask = build_target_mask(N_ROWS, N_COLS, CELLS)
    D = manhattan_distance_to_targets(N_ROWS, N_COLS, target_mask)
    Dmax = int(D.max())

    # State
    started = False
    state = "idle"        # "idle" -> "herd" -> "hold"
    band_k = Dmax
    band_last_t = 0.0
    overlap_until = 0.0

    running = True
    while running:
        now = time.time()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_SPACE:
                    started = True
                    state = "herd"
                    band_k = Dmax
                    band_last_t = now - HERD_PULSE_DT
                    overlap_until = 0.0

            elif event.type == pygame.MOUSEBUTTONDOWN:
                mx, my = event.pos
                if start_rect.collidepoint(mx, my):
                    started = True
                    state = "herd"
                    band_k = Dmax
                    band_last_t = now - HERD_PULSE_DT
                    overlap_until = 0.0
                elif stop_rect.collidepoint(mx, my):
                    clear_all_pwm(grid, ser)
                    running = False

        # ----- Herding logic + squeeze (repulsion) -----
        if started:
            if state == "herd":
                if (now - band_last_t) >= HERD_PULSE_DT:
                    band_last_t = now
                    if HERD_OVERLAP:
                        overlap_until = now + HERD_OVERLAP_HOLD

                    # Step inward
                    band_k -= 1
                    if band_k < 0:
                        state = "hold" if FINAL_HOLD else "idle"

                # choose k for this frame (handle overlap smoothing)
                if HERD_OVERLAP and now < overlap_until:
                    k_use = max(band_k + 1, 0)  # just-activated
                    band_mask = band_masks(D, k_use, overlap=True)
                else:
                    k_use = max(band_k, 0)
                    band_mask = band_masks(D, k_use, overlap=False)

                # Build repel_mask
                if REPEL_MODE == "complement":
                    repel_mask = (~target_mask)
                else:
                    # "outside_band": repel everything outside the current band toward target (exclude target)
                    # push from far to near: D >= k_use+1
                    repel_mask = (D >= (k_use + 1)) & (~target_mask)

                # Apply BOTH: target attraction + opposite-polarity repulsion squeeze
                apply_attract_and_repel(
                    grid,
                    target_mask=target_mask,
                    repel_mask=repel_mask,
                    direction=direction,
                    attract_amp=ATTRACT_AMP,
                    repel_amp=REPEL_AMP
                )

            elif state == "hold":
                # Keep squeezing in hold if desired:
                # Here: complement squeeze (strong). If you want only target hold, set repel_mask to all False.
                repel_mask = (~target_mask) if REPEL_MODE == "complement" else ((D >= 1) & (~target_mask))
                apply_attract_and_repel(
                    grid,
                    target_mask=target_mask,
                    repel_mask=repel_mask,
                    direction=direction,
                    attract_amp=ATTRACT_AMP,
                    repel_amp=REPEL_AMP
                )

            # Serial output at fixed rate
            if (now - last_send_t) >= SERIAL_SEND_DT:
                A = get_output_matrix(grid)
                send_matrix_over_serial(A, ser)
                last_send_t = now

        # ----- Draw -----
        screen.fill(BG_COLOR)
        draw_text(screen, f"direction={direction}  (1: attract=NEG/red, -1: attract=POS/green)", (20, 10), size=22)
        draw_text(
            screen,
            f"target={ONE_BASED_CELLS} | state={state} | REPEL_MODE={REPEL_MODE} | ATTRACT={ATTRACT_AMP} REPEL={REPEL_AMP} | k={band_k}",
            (20, 38),
            size=18,
            color=(200, 220, 200)
        )

        draw_grid(screen, grid)

        # buttons
        for rect, label in [(start_rect, "Start (SPACE)"), (stop_rect, "Stop (ESC)")]:
            hover = rect.collidepoint(pygame.mouse.get_pos())
            pygame.draw.rect(screen, BUTTON_BG_HOVER if hover else BUTTON_BG, rect, border_radius=10)
            draw_text(screen, label, rect.center, size=26, center=True)

        pygame.display.flip()
        clock.tick(FPS)

    # Cleanup
    if ser is not None:
        try:
            clear_all_pwm(grid, ser)
            ser.close()
        except Exception:
            pass
    pygame.quit()

if __name__ == "__main__":
    main()
