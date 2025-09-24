import pygame
import numpy as np
import time
import serial

# ================== Config ==================
SERIAL_PORTS = ['/dev/cu.usbmodem1020BA0ABA902']
# ------------------ Pattern (1-based -> convert to 0-based) ------------------
ONE_BASED_CELLS = [
    (1,3), (1,5), (1,2), (1,8),
    (2,3), (2,4), (2,5), (2,6),
    (3,2), (3,4), (3,6),
    (4,2), (4,7)
]
# ================== Config ==================










SCREEN_W, SCREEN_H = 800, 800
FPS = 30

# Grid size (fixed)
N_ROWS, N_COLS = 4, 8

# Polarity control: direction = 1 -> negative (red), -1 -> positive (green)
direction = 1

# Colors
BG_COLOR = (30, 30, 30)
GRID_COLOR = (80, 80, 80)
POS_COLOR = (0, 255, 0)
NEG_COLOR = (255, 0, 0)
BUTTON_BG = (60, 60, 60)
BUTTON_BG_HOVER = (90, 90, 90)
TEXT_COLOR = (240, 240, 240)

# Serial (optional). If port not found, code still runs.
SERIAL_BAUD = 115200


CELLS = [(r-1, c-1) for (r, c) in ONE_BASED_CELLS]

# ---------------------------------------------
# Helpers
# ---------------------------------------------

def create_grid(n, m):
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
    y0 = 40

    for i in range(n):
        for j in range(m):
            x = x0 + j * tile
            y = y0 + i * tile
            pos_val, neg_val, _ = grid[i, j]
            rect = pygame.Rect(x, y, tile - 2, tile - 2)
            if pos_val > 0:
                alpha = int(max(25, min(255, 25.5 * pos_val)))
                surf = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
                surf.fill((*POS_COLOR, alpha))
                surface.blit(surf, rect)
            elif neg_val > 0:
                alpha = int(max(25, min(255, 25.5 * neg_val)))
                surf = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
                surf.fill((*NEG_COLOR, alpha))
                surface.blit(surf, rect)
            else:
                pygame.draw.rect(surface, GRID_COLOR, rect, 1)

    pygame.draw.rect(surface, GRID_COLOR, (x0, y0, grid_w, grid_h), 2)

    return (x0, y0, tile)


def activate_pattern(grid, cells, direction):
    for (i, j) in cells:
        if 0 <= i < grid.shape[0] and 0 <= j < grid.shape[1]:
            if direction == -1:
                grid[i, j] = [10.0, 0.0, 0.0]
            else:
                grid[i, j] = [0.0, 10.0, 0.0]


def get_output_matrix(grid):
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
        ser.write(data.encode('utf-8'))
    except Exception:
        pass


def clear_all_pwm(grid, ser):
    # set entire grid to 0
    grid[:, :, :2] = 0
    A = get_output_matrix(grid)
    send_matrix_over_serial(A, ser)

# ---------------------------------------------
# Main
# ---------------------------------------------

def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    clock = pygame.time.Clock()

    grid = create_grid(N_ROWS, N_COLS)

    start_w, start_h = 180, 60
    stop_w, stop_h = 120, 44
    start_rect = pygame.Rect(0, 0, start_w, start_h)
    start_rect.center = (SCREEN_W // 2, SCREEN_H // 2 + 260)
    stop_rect = pygame.Rect(0, 0, stop_w, stop_h)
    stop_rect.center = (SCREEN_W // 2, SCREEN_H // 2 + 260 + 70)

    running = True
    started = False

    ser = try_open_serial()
    last_send = 0.0

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_SPACE:
                    started = True
                    activate_pattern(grid, CELLS, direction)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                mx, my = event.pos
                if start_rect.collidepoint(mx, my):
                    started = True
                    activate_pattern(grid, CELLS, direction)
                elif stop_rect.collidepoint(mx, my):
                    clear_all_pwm(grid, ser)
                    running = False

        now = time.time()
        if started and (now - last_send) >= 0.5:
            A = get_output_matrix(grid)
            send_matrix_over_serial(A, ser)
            last_send = now

        screen.fill(BG_COLOR)
        draw_text(screen, f"direction = {direction}  (1: negative/red, -1: positive/green)", (20, 8), size=24)
        draw_text(screen, f"Grid: {N_ROWS} x {N_COLS} | pattern cells: {len(CELLS)}", (20, 34), size=22, color=(200, 220, 200))
        draw_grid(screen, grid)

        for rect, label in [(start_rect, "Start"), (stop_rect, "Stop")]:
            hover = rect.collidepoint(pygame.mouse.get_pos())
            pygame.draw.rect(screen, BUTTON_BG_HOVER if hover else BUTTON_BG, rect, border_radius=10)
            draw_text(screen, label, rect.center, size=28, center=True)

        pygame.display.flip()
        clock.tick(FPS)

    if ser is not None:
        try:
            clear_all_pwm(grid, ser)
            ser.close()
        except Exception:
            pass
    pygame.quit()

if __name__ == "__main__":
    main()
