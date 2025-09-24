import pygame, numpy as np, time, serial

# ================== Config ==================
SCREEN_W, SCREEN_H = 800, 800
FPS = 60

# Grid
N_ROWS, N_COLS = 4, 8

# Polarity channels (fixed mapping)
CH_NEG = 0   # e.g., green
CH_POS = 1   # e.g., red

# ---- Tuning parameters ----
FULL_NEG = 100.0   # amplitude for -1 (CH_NEG)
FULL_POS = 100.0   # amplitude for +1 (CH_POS)

DUR_NEG  = 0.5     # seconds for -1
DUR_POS  = 0.5     # seconds for +1
DUR_OFF  = 0.5     # seconds for 0 (OFF)

SEND_ON_SWITCH = True  # send immediately when switching states
SEND_EVERY    = 1      # periodic resend interval; None disables

# Choose the sequence: list of (polarity, duration)
# polarity: -1 = NEG channel, +1 = POS channel, 0 = OFF
PATTERN = [
    (-1, DUR_NEG),
    (0,  DUR_OFF),
    (+1, DUR_POS),
    (0,  DUR_OFF),
]

# Colors (for visualization)
BG_COLOR=(30,30,30); GRID_COLOR=(80,80,80)
POS_COLOR=(0,255,0); NEG_COLOR=(255,0,0)
TEXT_COLOR=(240,240,240)

# Serial (optional)
SERIAL_PORTS=['/dev/cu.usbmodemF412FA64B66C2']
SERIAL_BAUD=115200

# ================== Helpers ==================
def create_grid(n,m): return np.zeros((n,m,3), dtype=float)
def get_tile(n,m): return max(8, min((SCREEN_W-40)//m, (SCREEN_H-220)//n))

def draw_text(surf, text, pos, size=24, color=TEXT_COLOR, center=False):
    font = pygame.font.SysFont(None, size)
    img = font.render(str(text), True, color)
    rect = img.get_rect()
    rect.center = pos if center else rect.move(pos).topleft
    surf.blit(img, rect)

def draw_grid(surf, grid, alpha_scale=255.0):
    n,m,_=grid.shape; tile=get_tile(n,m)
    gw,gh=m*tile, n*tile; x0=(SCREEN_W-gw)//2; y0=40
    for i in range(n):
        for j in range(m):
            x=x0+j*tile; y=y0+i*tile
            pos_val, neg_val, _ = grid[i,j]
            r = pygame.Rect(x,y,tile-2,tile-2)
            if pos_val>0:
                a=int(max(25,min(255,alpha_scale*pos_val)))
                pb=pygame.Surface((r.w,r.h), pygame.SRCALPHA)
                pb.fill((*POS_COLOR,a)); surf.blit(pb,r)
            elif neg_val>0:
                a=int(max(25,min(255,alpha_scale*neg_val)))
                nb=pygame.Surface((r.w,r.h), pygame.SRCALPHA)
                nb.fill((*NEG_COLOR,a)); surf.blit(nb,r)
            else:
                pygame.draw.rect(surf, GRID_COLOR, r, 1)
    pygame.draw.rect(surf, GRID_COLOR, (x0,y0,gw,gh), 2)

def try_open_serial():
    for port in SERIAL_PORTS:
        try:
            ser=serial.Serial(port, SERIAL_BAUD, timeout=0)
            time.sleep(1.0)
            print(f"Serial opened: {port}")
            return ser
        except Exception: continue
    print("Serial not found; running without serial output.")
    return None

def get_output_matrix(grid):
    arr = np.round(grid[:,:,:2]).astype(int).reshape(-1,2)
    flat = arr.flatten(); group=16
    A = np.zeros(((len(flat)+group-1)//group, group), dtype=int)
    for idx,val in enumerate(flat): A[idx//group, idx%group]=val
    return A

def send_matrix(A, ser):
    if ser is None: return
    try:
        ser.write( (",".join(str(int(v)) for v in A.flatten())+"\n").encode("utf-8") )
    except Exception: pass

def clear_pwm(grid, ser):
    grid[:,:,:2]=0; send_matrix(get_output_matrix(grid), ser)

def apply_polarity(grid, pol):
    grid[:,:,:2]=0
    if pol == -1: grid[:,:,CH_NEG]=FULL_NEG
    elif pol == +1: grid[:,:,CH_POS]=FULL_POS
    else: pass  # OFF = 0

# ================== Main ==================
def main():
    pygame.init()
    screen=pygame.display.set_mode((SCREEN_W, SCREEN_H))
    clock=pygame.time.Clock()

    grid=create_grid(N_ROWS,N_COLS)
    ser = try_open_serial()

    alpha_scale = 255.0 / max(1e-6, max(FULL_NEG, FULL_POS))

    # Build state machine from PATTERN
    states = [
        (f"POL_{p}", dur, (lambda pol=p: (lambda g: apply_polarity(g, pol)))())
        for (p, dur) in PATTERN
    ]
    si = 0
    name, dur, apply_fn = states[si]
    apply_fn(grid)
    if SEND_ON_SWITCH: send_matrix(get_output_matrix(grid), ser)
    next_switch = time.time() + dur
    next_periodic = time.time() + (SEND_EVERY if SEND_EVERY else 1e9)

    running=True
    while running:
        for e in pygame.event.get():
            if e.type==pygame.QUIT: running=False
            elif e.type==pygame.KEYDOWN and e.key==pygame.K_ESCAPE: running=False

        now=time.time()
        if now >= next_switch:
            si = (si+1) % len(states)
            name, dur, apply_fn = states[si]
            apply_fn(grid)
            if SEND_ON_SWITCH: send_matrix(get_output_matrix(grid), ser)
            next_switch = now + dur
            next_periodic = now + (SEND_EVERY if SEND_EVERY else 1e9)

        if SEND_EVERY and now >= next_periodic:
            send_matrix(get_output_matrix(grid), ser)
            next_periodic = now + SEND_EVERY

        # Draw
        screen.fill(BG_COLOR)
        draw_text(screen, f"state={name}", (20,12), size=22)
        draw_text(screen, f"pattern={PATTERN}", (20,36), size=20, color=(200,220,200))
        draw_grid(screen, grid, alpha_scale=alpha_scale)

        pygame.display.flip()
        clock.tick(FPS)

    if ser is not None:
        try: clear_pwm(grid, ser); ser.close()
        except Exception: pass
    pygame.quit()

if __name__ == "__main__":
    main()
