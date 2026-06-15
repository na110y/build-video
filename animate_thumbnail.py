#!/usr/bin/env python3
"""
animate_thumbnail.py - Xoay thực sự vòng tròn ma pháp trong ảnh

Kỹ thuật: Polar coordinate rotation + character mask
- Pixel vùng background (vòng tròn ma pháp): xoay theo tọa độ cực
- Pixel vùng nhân vật: giữ nguyên + thêm wave displacement cho tóc
- Blend mượt tại ranh giới nhân vật / background
"""
import cv2
import numpy as np
import subprocess
from pathlib import Path

INPUT  = "product/Võ Luyện Đỉnh Phong/thumbnail.jpg"
OUTPUT = "product/Võ Luyện Đỉnh Phong/thumbnail_animated.mp4"

FPS      = 30
DURATION = 12   # giây
ROT_SPEED = 0.20  # rad/s (~1 vòng / 31 giây)

# ── Load ảnh ──────────────────────────────────────────────────────────────────
img = cv2.imread(INPUT)
assert img is not None, f"Không đọc được: {INPUT}"
H, W = img.shape[:2]
H -= H % 2; W -= W % 2
img = img[:H, :W]
TOTAL = FPS * DURATION
print(f"Ảnh {W}×{H}  |  {TOTAL} frames ({DURATION}s @ {FPS}fps)")

# ── Tâm vòng tròn ma pháp (ước lượng từ ảnh) ─────────────────────────────────
CX = int(W * 0.44)
CY = int(H * 0.43)

# ── Precompute polar grids ─────────────────────────────────────────────────────
y_grid, x_grid = np.mgrid[0:H, 0:W].astype(np.float32)
dx_grid   = x_grid - CX
dy_grid   = y_grid - CY
dist_grid = np.sqrt(dx_grid**2 + dy_grid**2)
theta_grid = np.arctan2(dy_grid, dx_grid)

# ── Character mask ─────────────────────────────────────────────────────────────
# Nhân vật đứng lệch trái, che khuất trung tâm vòng tròn
CHAR_CX = int(W * 0.44)
CHAR_CY = int(H * 0.57)
CHAR_RX = int(W * 0.24)
CHAR_RY = int(H * 0.44)

char_dist = ((x_grid - CHAR_CX)**2 / CHAR_RX**2 +
             (y_grid - CHAR_CY)**2 / CHAR_RY**2)

# rotation_weight: 0 = nhân vật (không xoay), 1 = background (xoay)
INNER, OUTER = 0.80, 1.15
rotation_weight = np.clip((char_dist - INNER) / (OUTER - INNER), 0, 1).astype(np.float32)
rotation_weight = cv2.GaussianBlur(rotation_weight, (61, 61), 0)

# ── Hair mask (chỉ ở vùng nhân vật, không ảnh hưởng chữ tiêu đề) ─────────────
HAIR_BOT = int(H * 0.53)
FADE     = 120
hair_mask = np.zeros((H, W), dtype=np.float32)
hair_mask[:HAIR_BOT, :] = 1.0
hair_mask[HAIR_BOT - FADE:HAIR_BOT, :] = np.linspace(1, 0, FADE)[:, None]
hair_mask[:int(H * 0.50), int(W * 0.55):] = 0.0
hair_mask *= (1 - rotation_weight)  # tóc chỉ tác động vùng nhân vật

# ── Particles ─────────────────────────────────────────────────────────────────
rng   = np.random.default_rng(42)
N_P   = 28
p_x   = rng.integers(int(W * 0.03), int(W * 0.80), N_P)
p_spd = rng.uniform(20, 60, N_P)
p_off = rng.uniform(0, H, N_P)


# ── Tạo một frame ──────────────────────────────────────────────────────────────
def make_frame(i: int) -> np.ndarray:
    t     = i / FPS
    alpha = t * ROT_SPEED   # góc xoay hiện tại (radian)

    # 1. Xoay toàn bộ ảnh theo tọa độ cực quanh tâm CX,CY
    new_theta = theta_grid - alpha
    src_x = np.clip(CX + dist_grid * np.cos(new_theta), 0, W - 1).astype(np.float32)
    src_y = np.clip(CY + dist_grid * np.sin(new_theta), 0, H - 1).astype(np.float32)
    rotated = cv2.remap(img, src_x, src_y, cv2.INTER_LINEAR)

    # 2. Wave displacement cho tóc (chỉ trong character zone)
    s  = 5.5
    dx = s * np.sin(2*np.pi*0.018*y_grid + t*2.6) * np.cos(2*np.pi*0.008*x_grid + t*1.3) * hair_mask
    dy = s * 0.35 * np.cos(2*np.pi*0.015*x_grid + t*2.1) * hair_mask
    map_x = np.clip(x_grid + dx, 0, W - 1).astype(np.float32)
    map_y = np.clip(y_grid + dy, 0, H - 1).astype(np.float32)
    hair_frame = cv2.remap(img, map_x, map_y, cv2.INTER_LINEAR)

    # 3. Blend: nhân vật dùng hair_frame, background dùng rotated
    w = rotation_weight[:, :, None]
    frame = (hair_frame.astype(np.float32) * (1 - w) +
             rotated.astype(np.float32) * w)
    frame = frame.astype(np.uint8)

    # 4. Breathing glow
    pulse = 1.0 + 0.022 * np.sin(t * 1.8)
    frame = np.clip(frame.astype(np.float32) * pulse, 0, 255).astype(np.uint8)

    # 5. Floating sparkle particles
    for k in range(N_P):
        py = H - 1 - int((p_off[k] + i * p_spd[k] / FPS) % H)
        if 0 <= py < H:
            br = int(140 + 80 * np.sin(t * 4.5 + k * 1.3))
            cv2.circle(frame, (int(p_x[k]), py), 2, (br, br, 255), -1)

    return frame


# ── Render qua FFmpeg pipe ────────────────────────────────────────────────────
Path(OUTPUT).parent.mkdir(parents=True, exist_ok=True)
ffmpeg = subprocess.Popen([
    "ffmpeg", "-y",
    "-f", "rawvideo", "-vcodec", "rawvideo",
    "-s", f"{W}x{H}", "-pix_fmt", "bgr24", "-r", str(FPS),
    "-i", "pipe:0",
    "-c:v", "libx264", "-preset", "fast", "-crf", "18",
    "-pix_fmt", "yuv420p",
    OUTPUT,
], stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)

print("Đang render...")
for i in range(TOTAL):
    ffmpeg.stdin.write(make_frame(i).tobytes())
    if i % FPS == 0:
        print(f"  {i//FPS}/{DURATION}s")

ffmpeg.stdin.close()
ffmpeg.wait()
print(f"\nXong!  →  {OUTPUT}")
