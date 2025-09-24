import pygame
import numpy as np
import time
import serial

# ================== Config ==================
SCREEN_W, SCREEN_H = 800, 800
FPS = 60

# Grid
N_ROWS, N_COLS = 4, 8

# Polarity control: direction = 1 -> red(channel 1), -1 -> green(channel 0)
direction = 1

# ---- Ramp params ----
MAX_INTENSITY   = 100.0   # 하드웨어 상한에 맞춰 조정
STEP_PCT        = 100     # 10%씩
UPDATE_INTERVAL = 0.5    # 1초마다 갱신

# Colors (viz)
BG_COLOR=(30,30,30); GRID_COLOR=(80,80,80)
POS_COLOR=(0,255,0); NEG_COLOR=(255,0,0)
BUTTON_BG=(60,60,60); BUTTON_BG_HOVER=(90,90,90)
TEXT_COLOR=(240,240,240)

# Serial (optional)
SERIAL_PORTS = ['/dev/cu.usbmodem1020BA0ABA902','/dev/cu.usbmodemF412FA64B66C2']
SERIAL_BAUD = 115200

# ================== Helpers ==================
def create_grid(n, m): return np.zeros((n, m, 3), dtype=float)

def get_dynamic_tile_size(n, m):
    return max(8, min((SCREEN_W-40)//m, (SCREEN_H-220)//n))

def draw_text(surface, text, pos, size=24, color=TEXT_COLOR, center=False):
    font = pygame.font.SysFont(None, size)
    img = font.render(str(text), True, color)
    rect = img.get_rect()
    rect.center = pos if center else rect.move(pos).topleft
    surface.blit(img, rect)

def draw_grid(surface, grid, alpha_scale=255.0):
    n, m, _ = grid.shape
    tile = get_dynamic_tile_size(n, m)
    grid_w, grid_h = m*tile, n*tile
    x0 = (SCREEN_W-grid_w)//2; y0 = 40
    for i in range(n):
        for j in range(m):
            x = x0 + j*tile; y = y0 + i*tile
            pos_val, neg_val, _ = grid[i, j]
            r = pygame.Rect(x, y, tile-2, tile-2)
            if pos_val > 0:
                alpha = int(max(25, min(255, alpha_scale*pos_val)))
                surf = pygame.Surface((r.w, r.h), pygame.SRCALPHA)
                surf.fill((*POS_COLOR, alpha)); surface.blit(surf, r)
            elif neg_val > 0:
                alpha = int(max(25, min(255, alpha_scale*neg_val)))
                surf = pygame.Surface((r.w, r.h), pygame.SRCALPHA)
                surf.fill((*NEG_COLOR, alpha)); surface.blit(surf, r)
            else:
                pygame.draw.rect(surface, GRID_COLOR, r, 1)
    pygame.draw.rect(surface, GRID_COLOR, (x0, y0, grid_w, grid_h), 2)

def try_open_serial():
    for port in SERIAL_PORTS:
        try:
            ser = serial.Serial(port, SERIAL_BAUD, timeout=0)
            time.sleep(1.0); print(f"Serial opened: {port}")
            return ser
        except Exception:
            continue
    print("Serial not found; running without serial output.")
    return None

def get_output_matrix(grid):
    arr = np.round(grid[:, :, :2]).astype(int).reshape(-1, 2)
    flat = arr.flatten()
    group = 16
    A = np.zeros(((len(flat)+group-1)//group, group), dtype=int)
    for idx, val in enumerate(flat):
        A[idx//group, idx%group] = val
    return A

def send_matrix_over_serial(A, ser):
    if ser is None: return
    try:
        data = ",".join(str(int(v)) for v in A.flatten()) + "\n"
        ser.write(data.encode('utf-8'))
    except Exception:
        pass

def clear_all_pwm(grid, ser):
    grid[:, :, :2] = 0
    send_matrix_over_serial(get_output_matrix(grid), ser)

def set_all_constant(grid, value, direction):
    grid[:, :, :2] = 0
    if direction == -1: grid[:, :, 0] = value
    else:               grid[:, :, 1] = value

# ================== Main ==================
def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    clock = pygame.time.Clock()

    grid = create_grid(N_ROWS, N_COLS)

    # UI
    stop_w, stop_h = 120, 44
    stop_rect = pygame.Rect(0, 0, stop_w, stop_h); stop_rect.center = (SCREEN_W//2, SCREEN_H//2 + 260)

    ser = try_open_serial()
    running = True

    # Ramp state
    pct = 0               # 0..100
    direction_step = +1   # +1: up, -1: down
    next_update = time.time()

    alpha_scale = 255.0 / max(1e-6, MAX_INTENSITY)

    # 초기 적용/전송
    val = MAX_INTENSITY * (pct/100.0)
    set_all_constant(grid, val, direction)
    send_matrix_over_serial(get_output_matrix(grid), ser)

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT: running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE: running = False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if stop_rect.collidepoint(*event.pos): running = False

        now = time.time()
        if now >= next_update:
            # 1초에 10%씩 변화
            pct += direction_step * STEP_PCT
            if pct >= 100:
                pct = 100
                direction_step = -1
            elif pct <= 0:
                pct = 0
                direction_step = +1

            val = MAX_INTENSITY * (pct/100.0)
            set_all_constant(grid, val, direction)

            # 전송(1 Hz)
            send_matrix_over_serial(get_output_matrix(grid), ser)

            next_update += UPDATE_INTERVAL

        # Draw
        screen.fill(BG_COLOR)
        draw_text(screen, f"dir={direction} | {pct:3d}% | val={val:.1f}/{MAX_INTENSITY}", (20,12), size=22)
        draw_text(screen, f"ramp: 0→100→0 @ 10%/s", (20,36), size=20, color=(200,220,200))
        draw_grid(screen, grid, alpha_scale=alpha_scale)

        hover = stop_rect.collidepoint(pygame.mouse.get_pos())
        pygame.draw.rect(screen, BUTTON_BG_HOVER if hover else BUTTON_BG, stop_rect, border_radius=10)
        draw_text(screen, "Stop", stop_rect.center, size=28, center=True)

        pygame.display.flip()
        clock.tick(FPS)

    if ser is not None:
        try: clear_all_pwm(grid, ser); ser.close()
        except Exception: pass
    pygame.quit()

if __name__ == "__main__":
    main()
