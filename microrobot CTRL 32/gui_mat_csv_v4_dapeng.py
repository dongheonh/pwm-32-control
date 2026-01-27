import pygame
import numpy as np
import serial
import time

# --- Constants ---
SCREEN_W, SCREEN_H = 800, 800
DECAY_DURATION = 3
FPS = 100

MIN_SIZE = 8
MAX_SIZE = 1024

BG_COLOR = (30, 30, 30)
GRID_COLOR = (80, 80, 80)
POS_COLOR = (0, 255, 0)
NEG_COLOR = (255, 0, 0)
BUTTON_COLOR = (100, 100, 100)
TEXT_COLOR = (255, 255, 255)
TABLE_BG = (15, 15, 15)
TABLE_GRID = (70, 70, 70)


SERIAL_PORT = '/dev/cu.usbmodem1020BA0ABA902'


SERIAL_BAUD = 115200

pygame.init()
screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
clock = pygame.time.Clock()
font = pygame.font.SysFont(None, 36)

n, m = 4, 8
setting_grid = True

BTN_SIZE = 40
n_dec_btn = pygame.Rect(200, 100, BTN_SIZE, BTN_SIZE)
n_inc_btn = pygame.Rect(300, 100, BTN_SIZE, BTN_SIZE)
m_dec_btn = pygame.Rect(200, 200, BTN_SIZE, BTN_SIZE)
m_inc_btn = pygame.Rect(300, 200, BTN_SIZE, BTN_SIZE)
n_box = pygame.Rect(245, 100, BTN_SIZE, BTN_SIZE)
m_box = pygame.Rect(245, 200, BTN_SIZE, BTN_SIZE)

#------ parameters of field control
A = 10.0              # base amplitude for both axes
w = 2*np.pi*3    # angular frequency (1 Hz)
duration = 4.0        # seconds
fps = 30              # frames per second
# Amplitudes (row and column) and phases
Ax = np.ones((1,n))*A                 # rows
Ay = np.ones((1,m))*A                 # cols
phix = np.zeros((1,n))
phiy = np.zeros((1,m))
for i in range(n):
    phix[0,i] = i*np.pi/n
for i in range(m):
    phiy[0,i] = i*np.pi/m


#phix = np.array([0.0, np.pi/3, np.pi/3*2])       # rows: 0, π, 0
#phiy = np.array([0.0, np.pi/3, np.pi/3*2])       # cols: 0, π, 0


def create_grid(n, m):
    return np.zeros((n, m, 3), dtype=float)

grid_data = create_grid(n, m)

def draw_text(surface, text, pos, center=False, size=36, color=TEXT_COLOR):
    f = pygame.font.SysFont(None, size)
    img = f.render(str(text), True, color)
    rect = img.get_rect()
    if center:
        rect.center = pos
    else:
        rect.topleft = po
    surface.blit(img, rect)

def draw_setup_ui():
    screen.fill(BG_COLOR)
    draw_text(screen, "Set Grid Size", (50, 30))
    draw_text(screen, "Rows (n):", (50, 110))
    draw_text(screen, "Cols (m):", (50, 210))
    pygame.draw.rect(screen, BUTTON_COLOR, n_dec_btn)
    pygame.draw.rect(screen, BUTTON_COLOR, n_inc_btn)
    pygame.draw.rect(screen, BUTTON_COLOR, m_dec_btn)
    pygame.draw.rect(screen, BUTTON_COLOR, m_inc_btn)
    pygame.draw.rect(screen, (50, 50, 150), n_box)
    pygame.draw.rect(screen, (50, 50, 150), m_box)
    draw_text(screen, "-", n_dec_btn.center, center=True)
    draw_text(screen, "+", n_inc_btn.center, center=True)
    draw_text(screen, "-", m_dec_btn.center, center=True)
    draw_text(screen, "+", m_inc_btn.center, center=True)
    draw_text(screen, str(n), n_box.center, center=True)
    draw_text(screen, str(m), m_box.center, center=True)
    draw_text(screen, "Press ENTER to confirm", (50, 300))

def get_dynamic_tile_size(n, m):
    tile_size = min(
        (SCREEN_W - 20) // m,
        (SCREEN_H - 180) // n
    )
    return max(4, tile_size)

def draw_grid(grid):
    tile_size = get_dynamic_tile_size(n, m)
    grid_w = m * tile_size
    grid_h = n * tile_size
    x_offset = (SCREEN_W - grid_w) // 2
    y_offset = 20

    screen.fill(BG_COLOR)
    for i in range(n):
        for j in range(m):
            x = x_offset + j * tile_size
            y = y_offset + i * tile_size
            pos_val, neg_val, _ = grid[i, j]
            if pos_val > 0:
                alpha = int(np.clip(25.5 * pos_val, 25, 255))
                color = (*POS_COLOR, alpha)
                rect_surf = pygame.Surface((tile_size - 2, tile_size - 2), pygame.SRCALPHA)
                rect_surf.fill(color)
                screen.blit(rect_surf, (x, y))
            elif neg_val > 0:
                alpha = int(np.clip(25.5 * neg_val, 25, 255))
                color = (*NEG_COLOR, alpha)
                rect_surf = pygame.Surface((tile_size - 2, tile_size - 2), pygame.SRCALPHA)
                rect_surf.fill(color)
                screen.blit(rect_surf, (x, y))
            else:
                pygame.draw.rect(screen, GRID_COLOR, (x, y, tile_size - 2, tile_size - 2))
    return x_offset, y_offset + grid_h, grid_w

def update_decay(grid):
    now = time.time()
    for i in range(n):
        for j in range(m):
            pos_val, neg_val, t_start = grid[i, j]
            if pos_val > 0 and t_start > 0:
                elapsed = now - t_start
                if elapsed < DECAY_DURATION:
                    grid[i, j][0] = 10 * (1 - elapsed / DECAY_DURATION)
                else:
                    grid[i, j][0] = 0
                    grid[i, j][2] = 0
            if neg_val > 0 and t_start > 0:
                elapsed = now - t_start
                if elapsed < DECAY_DURATION:
                    grid[i, j][1] = 10 * (1 - elapsed / DECAY_DURATION)
                else:
                    grid[i, j][1] = 0
                    grid[i, j][2] = 0

def draw_table(grid, pos_x, pos_y, width):
    table_top = pos_y + 10
    cell_h = 28
    cell_w = max(width // max(m,1), 28)
    if n > 16 or m > 32:
        msg = f"Table display is limited to 16 x 32"
        draw_text(screen, msg, (SCREEN_W//2, table_top+30), center=True, size=32, color=(200,100,100))
        return
    table_h = n * cell_h
    pygame.draw.rect(screen, TABLE_BG, (pos_x, table_top, m*cell_w, table_h))
    for i in range(n):
        ry = table_top + i*cell_h + cell_h//2
        draw_text(screen, i, (pos_x - 20, table_top + i*cell_h + 3), center=False, size=16, color=(200, 220, 180))
        for j in range(m):
            cx = pos_x + j*cell_w + cell_w//2
            pos_val = int(round(grid[i,j][0]))
            neg_val = int(round(grid[i,j][1]))
            s = f"{pos_val}/{neg_val}"
            draw_text(screen, s, (cx, ry), center=True, size=16)
    for i in range(n+1):
        y = table_top + i*cell_h
        pygame.draw.line(screen, TABLE_GRID, (pos_x, y), (pos_x + m*cell_w, y))
    for j in range(m+1):
        x = pos_x + j*cell_w
        pygame.draw.line(screen, TABLE_GRID, (x, table_top), (x, table_top + n*cell_h))

def get_output_matrix(grid):
    arr = np.round(grid[:, :, :2]).astype(int).reshape(-1, 2)
    flat = arr.flatten()
    group = (m // 8) * 16 if m >= 8 else m * 2
    if group == 0:
        group = 1
    num_rows = len(flat) // group
    if len(flat) % group != 0:
        num_rows += 1
    A = np.zeros((num_rows, group), dtype=int)
    for idx, val in enumerate(flat):
        row = idx // group
        col = idx % group
        A[row, col] = val
    return A
#mouse
def matrix_to_csv_string(matrix: np.ndarray):
    rows, cols = matrix.shape
    # Always show output, even if cols not divisible by 16
    if cols == 0:
        return ""
    grouped_data = []
    for row in range(rows):
        for col in range(cols):
            grouped_data.append(matrix[row, col])
    data_str = ",".join(str(int(v)) for v in grouped_data)
    return data_str

def draw_csv_string(csv_str, pos_x, pos_y, width):
    start_y = pos_y + 40
    max_chars_per_line = max(width // 12, 40)
    lines = [csv_str[i:i+max_chars_per_line] for i in range(0, len(csv_str), max_chars_per_line)]
    draw_text(screen, "CSV output =", (pos_x, start_y), center=False, size=22, color=(255,220,150))
    for idx, line in enumerate(lines[:8]):
        draw_text(screen, line, (pos_x + 40, start_y + 25 + idx*22), center=False, size=18, color=(220,255,220))
    if len(lines) > 8:
        draw_text(screen, "...", (pos_x + 40, start_y + 25 + 8*22), center=False, size=18, color=(220,255,220))

def draw_csv_input_string(csv_str, pos_x, pos_y, width):
    start_y = pos_y + 150
    max_chars_per_line = max(width // 12, 40)
    lines = [csv_str[i:i+max_chars_per_line] for i in range(0, len(csv_str), max_chars_per_line)]
    draw_text(screen, "CSV input =", (pos_x, start_y), center=False, size=22, color=(150,220,255))
    for idx, line in enumerate(lines[:8]):
        draw_text(screen, line, (pos_x + 40, start_y + 25 + idx*22), center=False, size=18, color=(220,220,255))
    if len(lines) > 8:
        draw_text(screen, "...", (pos_x + 40, start_y + 25 + 8*22), center=False, size=18, color=(200,220,255))

def send_matrix_over_serial(matrix: np.ndarray, ser):
    flat = matrix.flatten()
    data_str = ",".join(str(int(v)) for v in flat) + "\n"
    try:
        ser.write(data_str.encode('utf-8'))
    except Exception as e:
        print(f"Serial error: {e}")

def magnetOutputField(grid_data,t_start): ## governing equation added by dapeng 
    t = time.time()-t_start
    for i in range(n):
        for j in range(m):
            grid_data[i,j][0] = np.maximum(Ax[0,i]*np.sin(w*t + phix[0,i]) + Ay[0,j]*np.sin(w*t + phiy[0,j]),0)            
            grid_data[i,j][1] = -1*np.minimum(Ax[0,i]*np.sin(w*t + phix[0,i]) + Ay[0,j]*np.sin(w*t + phiy[0,j]),0)


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
counter = 0
while running:
    now = time.time()
    if counter == 0:
        t_start = now
        counter += 1
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.MOUSEBUTTONDOWN and setting_grid:
            if n_dec_btn.collidepoint(event.pos):
                n = max(n - 1, MIN_SIZE)
            elif n_inc_btn.collidepoint(event.pos):
                n = min(n + 1, MAX_SIZE)
            elif m_dec_btn.collidepoint(event.pos):
                m = max(m - 8, MIN_SIZE)
                m = m - (m % 8)
            elif m_inc_btn.collidepoint(event.pos):
                m = min(m + 8, MAX_SIZE)
                m = m - (m % 8)
        elif event.type == pygame.KEYDOWN:
            if setting_grid and event.key == pygame.K_RETURN:
                grid_data = create_grid(n, m)
                setting_grid = False
        elif event.type == pygame.MOUSEBUTTONDOWN and not setting_grid:
            tile_size = get_dynamic_tile_size(n, m)
            grid_w = m * tile_size
            grid_h = n * tile_size
            x_offset = (SCREEN_W - grid_w) // 2
            y_offset = 20
            mx, my = pygame.mouse.get_pos() #Click to get item1
            j = (mx - x_offset) // tile_size
            i = (my - y_offset) // tile_size
            if 0 <= i < n and 0 <= j < m:
                if event.button == 1:
                    grid_data[i, j] = [0, 10, time.time()]
                elif event.button == 3:
                    grid_data[i, j] = [10, 0, time.time()]
    
    magnetOutputField(grid_data,t_start)
    if setting_grid:
        draw_setup_ui()
    else:
        update_decay(grid_data)
        pos_x, pos_y, grid_w = draw_grid(grid_data)
        draw_table(grid_data, pos_x, pos_y, grid_w)

        # csv matrix A output update
        if n <= 16 and m <= 32:
            A = get_output_matrix(grid_data)
            csv_output_str = matrix_to_csv_string(A)
        else:
            csv_output_str = ""

        draw_csv_string(csv_output_str, pos_x, pos_y + n*28 + 10, grid_w)

        # send (10Hz) - 0.1
        if n <= 16 and m <= 32 and ser:
            if now - last_sent >= 0.1:
                send_matrix_over_serial(A, ser)
                last_sent = now

            if ser.in_waiting:
                try:
                    line = ser.readline().decode('utf-8', errors='ignore').strip()
                    if line:
                        csv_input_str = line
                except Exception:
                    pass

        if csv_input_str:
            draw_csv_input_string(csv_input_str, pos_x, pos_y + n*28 + 10, grid_w)

    pygame.display.flip()
    clock.tick(FPS)

if ser:
    ser.close()
pygame.quit()
