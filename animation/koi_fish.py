"""
Standalone pygame Realistic Living Koi Pond.

RealisticKoi (32-segment spine, smooth polygon silhouette with blunt head,
clipped kohaku/sanke/showa/tancho/asagi/ogon patterns, scales, soft 3D
shading, fan pectorals, flexible twin-lobed tail, barbels, blurred shadow)
on a procedural pond bed (depth gradient + stones) with caustics and swaying
lily/lotus. Left click: ripples + feed pellets + attract. Right click:
wider double ripples, no feed. Esc quits.

Run:
    python animation/koi_fish.py
"""

import math
import os
import random
import pygame

# Memposisikan jendela otomatis di tengah layar laptop
os.environ["SDL_VIDEO_CENTERED"] = "1"

pygame.init()
W, H = 1150, 720
screen = pygame.display.set_mode((W, H))
pygame.display.set_caption("Realistic Living Koi Pond")
clock = pygame.time.Clock()


def create_pond_bed():
    """Membuat dasar kolam alami dengan gradasi kedalaman dan batu-batu sungai."""
    bed = pygame.Surface((W, H))
    cx, cy = W // 2, H // 2
    max_d = math.hypot(cx, cy)

    # 1. Gradasi air dalam (biru kehijauan gelap alami)
    for y in range(0, H, 2):
        for x in range(0, W, 2):
            d = math.hypot(x - cx, y - cy) / max_d
            r = int(max(5, 16 * (1 - d * 0.75)))
            g = int(max(18, 54 * (1 - d * 0.65)))
            b = int(max(24, 68 * (1 - d * 0.55)))
            pygame.draw.rect(bed, (r, g, b), (x, y, 2, 2))

    # 2. Batu-batu halus di dasar kolam (terlihat samar di kedalaman air)
    rng = random.Random(42)
    stone_surf = pygame.Surface((W, H), pygame.SRCALPHA)
    for _ in range(55):
        sx = rng.randint(40, W - 40)
        sy = rng.randint(40, H - 40)
        rx = rng.randint(18, 48)
        ry = int(rx * rng.uniform(0.65, 0.9))
        ang = rng.uniform(0, 180)
        shade = rng.randint(18, 38)

        s_tmp = pygame.Surface((rx * 2 + 10, ry * 2 + 10), pygame.SRCALPHA)
        pygame.draw.ellipse(s_tmp, (shade, shade + 12, shade + 16, 65), (5, 5, rx * 2, ry * 2))
        pygame.draw.ellipse(s_tmp, (shade + 10, shade + 22, shade + 25, 45), (7, 6, int(rx * 1.6), int(ry * 1.5)))
        rot_s = pygame.transform.rotate(s_tmp, ang)
        stone_surf.blit(rot_s, rot_s.get_rect(center=(sx, sy)))

    bed.blit(stone_surf, (0, 0))
    return bed


SS = 2  # supersampling: ikan digambar 2x lebih besar lalu diperkecil -> tepi halus

RED = (210, 44, 22)
RED2 = (224, 66, 28)
RED3 = (198, 36, 20)
SUMI = (18, 18, 22)
SHIRO = (246, 243, 235)

KOI_STYLES = {
    "kohaku": dict(base=SHIRO, fin=(250, 247, 242), fin_base=(250, 247, 242), ray=(255, 255, 255),
                   scale=(90, 70, 60, 26), hl=55, dorsal=(252, 250, 246)),
    "tancho": dict(base=SHIRO, fin=(250, 247, 242), fin_base=(250, 247, 242), ray=(255, 255, 255),
                   scale=(90, 80, 70, 24), hl=55, dorsal=(252, 250, 246)),
    "sanke": dict(base=SHIRO, fin=(250, 247, 242), fin_base=(236, 232, 226), ray=(60, 60, 66),
                  scale=(90, 70, 60, 26), hl=55, dorsal=(252, 250, 246)),
    "showa": dict(base=(22, 22, 26), fin=(246, 242, 236), fin_base=(24, 24, 28), ray=(255, 255, 255),
                  scale=(255, 255, 255, 16), hl=42, dorsal=(40, 40, 46)),
    "ogon": dict(base=(230, 172, 44), fin=(242, 202, 98), fin_base=(234, 178, 56), ray=(255, 236, 170),
                 scale=(255, 246, 200, 60), hl=95, dorsal=(244, 198, 82)),
    "asagi": dict(base=(108, 132, 158), fin=(238, 228, 216), fin_base=(222, 100, 52), ray=(255, 240, 225),
                  scale=(26, 40, 66, 125), hl=38, dorsal=(150, 166, 184)),
}


class RealisticKoi:
    """Koi dengan siluet poligon halus, corak ter-clip ke tubuh, sisik, shading & sirip lentur."""

    MAX_HALF_W = 21.5  # setengah lebar tubuh maksimum (px pada scale 1)

    def __init__(self, x, y, angle, base_speed, scale, variety):
        self.x = x
        self.y = y
        self.angle = angle
        self.base_speed = base_speed
        self.speed = base_speed
        self.scale = scale
        self.variety = variety
        self.style = KOI_STYLES[variety]

        self.phase = random.uniform(0, 6.28)
        self.turn_vel = 0.0
        self.burst_timer = random.uniform(1.0, 4.0)

        # Tulang belakang (32 ruas) menggunakan Follow-the-Leader Kinematics
        self.num_joints = 32
        self.joint_dist = 4.6 * scale
        self.joints = [
            [x - math.cos(angle) * i * self.joint_dist, y - math.sin(angle) * i * self.joint_dist]
            for i in range(self.num_joints)
        ]

        # Corak (blob dalam koordinat tubuh: t sepanjang badan, s lateral) - tetap per ikan
        self.blobs = self._generate_pattern()

    # ------------------------------------------------------------------ corak
    def _generate_pattern(self):
        rng = random.Random(f"{self.variety}-{self.x}-{self.y}-{self.scale}")
        ts = self.MAX_HALF_W / ((self.num_joints - 1) * 4.6)  # konversi satuan lebar -> t
        blobs = []

        def patch(t0, s0, r, col, n):
            for _ in range(n):
                a = rng.uniform(0, 2 * math.pi)
                d = math.sqrt(rng.random()) * r * 0.75
                blobs.append((t0 + math.cos(a) * d * ts, s0 + math.sin(a) * d, r * rng.uniform(0.38, 0.62), col))

        def kohaku_hi():
            if rng.random() < 0.85:
                patch(0.11, rng.uniform(-0.1, 0.1), 0.6, RED, 7)
            t = rng.uniform(0.3, 0.36)
            while t < 0.86:
                patch(t, rng.uniform(-0.35, 0.35), rng.uniform(0.7, 0.95), rng.choice((RED, RED2, RED3)),
                      rng.randint(6, 9))
                t += rng.uniform(0.18, 0.27)

        v = self.variety
        if v == "kohaku":
            kohaku_hi()
        elif v == "tancho":
            blobs.append((0.095, 0.0, 0.40, RED))
        elif v == "sanke":
            kohaku_hi()
            for _ in range(rng.randint(3, 5)):
                patch(rng.uniform(0.25, 0.85), rng.uniform(-0.55, 0.55), rng.uniform(0.22, 0.36), SUMI, 3)
        elif v == "showa":
            patch(0.1, rng.uniform(-0.2, 0.2), 0.62, RED, 6)
            t = rng.uniform(0.3, 0.36)
            while t < 0.82:
                patch(t, rng.uniform(-0.4, 0.4), rng.uniform(0.7, 0.9), rng.choice((RED, RED2)), 7)
                t += rng.uniform(0.2, 0.28)
            for _ in range(rng.randint(2, 3)):
                patch(rng.uniform(0.25, 0.8), rng.uniform(-0.5, 0.5), rng.uniform(0.45, 0.6), SHIRO, 5)
            patch(0.06, rng.choice((-0.35, 0.35)), 0.3, SUMI, 3)  # menware (sumi di kepala)
            for _ in range(rng.randint(2, 3)):
                patch(rng.uniform(0.3, 0.8), rng.uniform(-0.6, 0.6), rng.uniform(0.25, 0.4), SUMI, 3)
        elif v == "asagi":
            patch(0.06, 0.0, 0.55, (198, 208, 212), 4)
            t = 0.1
            while t < 0.95:
                for side in (-1, 1):
                    blobs.append((t, side * (self._width(t) + 0.12), rng.uniform(0.38, 0.55), RED2))
                t += 0.05
            for side in (-1, 1):
                blobs.append((0.05, side * 0.72, 0.28, RED2))
        return blobs

    # -------------------------------------------------------------- perilaku
    def attract_to(self, tx, ty):
        """Ikan tertarik mendekati titik klik (seperti diberi pakan)."""
        desired = math.atan2(ty - self.y, tx - self.x)
        diff = (desired - self.angle + math.pi) % (2 * math.pi) - math.pi
        self.turn_vel = max(-1.8, min(1.8, diff * 2.5))
        self.speed = self.base_speed * 1.45

    def update(self, dt):
        # Variasi kecepatan alami (meluncur santai lalu mengibas)
        self.burst_timer -= dt
        if self.burst_timer <= 0:
            self.burst_timer = random.uniform(2.0, 5.0)
            self.speed = self.base_speed * random.uniform(0.85, 1.3)
        else:
            self.speed += (self.base_speed - self.speed) * 1.5 * dt

        # Kemudi organik (wandering + menghindari dinding kolam dengan mulus)
        self.turn_vel += random.uniform(-1.4, 1.4) * dt
        self.turn_vel *= 0.94

        margin = 160
        steer_x, steer_y = 0.0, 0.0
        if self.x < margin:
            steer_x += (margin - self.x) / margin
        elif self.x > W - margin:
            steer_x -= (self.x - (W - margin)) / margin
        if self.y < margin:
            steer_y += (margin - self.y) / margin
        elif self.y > H - margin:
            steer_y -= (self.y - (H - margin)) / margin

        if steer_x != 0.0 or steer_y != 0.0:
            wall_ang = math.atan2(steer_y, steer_x)
            diff = (wall_ang - self.angle + math.pi) % (2 * math.pi) - math.pi
            self.angle += diff * 2.2 * dt
        else:
            self.angle += self.turn_vel * dt

        # Gerakkan kepala
        self.x += math.cos(self.angle) * self.speed * dt
        self.y += math.sin(self.angle) * self.speed * dt
        self.phase += (self.speed * 0.075 + 2.2) * dt

        # Update ruas tulang belakang (Chain Following) + gelombang renang ke arah ekor
        self.joints[0] = [self.x, self.y]
        for i in range(1, self.num_joints):
            t = i / (self.num_joints - 1)
            px, py = self.joints[i - 1]
            cx, cy = self.joints[i]
            ang = math.atan2(py - cy, px - cx)
            swim_wave = math.sin(self.phase - t * 5.2) * (0.12 * (t ** 1.5))
            target_ang = ang + swim_wave
            self.joints[i][0] = px - math.cos(target_ang) * self.joint_dist
            self.joints[i][1] = py - math.sin(target_ang) * self.joint_dist

    # ---------------------------------------------------------------- bentuk
    @staticmethod
    def _width(t):
        """Profil setengah-lebar (0..1) tampak atas: kepala tumpul, bahu lebar, pangkal ekor ramping."""
        if t < 0.27:
            u = t / 0.27
            return 0.58 + 0.42 * (math.sin(u * math.pi / 2) ** 0.8)
        u = (t - 0.27) / 0.73
        return 0.19 + 0.81 * (math.cos(u * math.pi / 2) ** 1.2)

    # ----------------------------------------------------------------- gambar
    def draw(self, surf):
        N = self.num_joints
        st = self.style
        A = [self.angle]
        for i in range(1, N):
            dx = self.joints[i - 1][0] - self.joints[i][0]
            dy = self.joints[i - 1][1] - self.joints[i][1]
            A.append(math.atan2(dy, dx))

        xs = [p[0] for p in self.joints]
        ys = [p[1] for p in self.joints]
        pad = int(78 * self.scale)
        sh_off = (16 * self.scale, 22 * self.scale)
        min_x = int(min(xs)) - pad
        min_y = int(min(ys)) - pad
        bw = int(max(xs)) + pad + int(sh_off[0]) + 4 - min_x
        bh = int(max(ys)) + pad + int(sh_off[1]) + 4 - min_y
        if min_x > W or min_y > H or min_x + bw < 0 or min_y + bh < 0:
            return

        S = SS
        K = self.scale * S
        MW = self.MAX_HALF_W * K
        size = (bw * S, bh * S)
        P = [((x - min_x) * S, (y - min_y) * S) for x, y in self.joints]

        def spine(t):
            f = min(max(t, 0.0), 1.0) * (N - 1)
            i = min(int(f), N - 2)
            u = f - i
            a0 = A[i]
            da = (A[i + 1] - a0 + math.pi) % (2 * math.pi) - math.pi
            return (P[i][0] + (P[i + 1][0] - P[i][0]) * u,
                    P[i][1] + (P[i + 1][1] - P[i][1]) * u,
                    a0 + da * u)

        def at(t, s):
            x, y, a = spine(t)
            return x - math.sin(a) * s, y + math.cos(a) * s

        def outline(f=1.0, ox=0.0, oy=0.0):
            left, right = [], []
            for i in range(N):
                x, y = P[i]
                a = A[i]
                w = self._width(i / (N - 1)) * MW * f
                nx, ny = -math.sin(a), math.cos(a)
                left.append((x + nx * w + ox, y + ny * w + oy))
                right.append((x - nx * w + ox, y - ny * w + oy))
            x0, y0 = P[0]
            fx, fy = math.cos(A[0]), math.sin(A[0])
            nx, ny = -fy, fx
            w0 = self._width(0.0) * MW * f
            cap = []
            for k in range(1, 14):
                th = -math.pi / 2 + math.pi * k / 14
                cap.append((x0 + fx * math.cos(th) * w0 * 1.08 + nx * math.sin(th) * w0 + ox,
                            y0 + fy * math.cos(th) * w0 * 1.08 + ny * math.sin(th) * w0 + oy))
            return left + right[::-1] + cap

        # ---- 1. Sirip-sirip (digambar di bawah tubuh)
        fins = pygame.Surface(size, pygame.SRCALPHA)
        fin_polys = []

        def fan(base_t, side, length, direction, spread, a_out=105, a_in=175):
            bx, by = at(base_t, side * self._width(base_t) * MW * 0.72)
            arc, inner = [], []
            n = 10
            for j in range(n + 1):
                u = j / n
                ang = direction + side * (-0.5 + u) * spread
                ln = length * (0.62 + 0.38 * math.sin(math.pi * (0.15 + 0.85 * u)))
                arc.append((bx + math.cos(ang) * ln, by + math.sin(ang) * ln))
                inner.append((bx + math.cos(ang) * ln * 0.42, by + math.sin(ang) * ln * 0.42))
            poly = [(bx, by)] + arc
            pygame.draw.polygon(fins, (*st["fin"], a_out), poly)
            pygame.draw.polygon(fins, (*st["fin_base"], a_in), [(bx, by)] + inner)
            for pt in arc[::2]:
                pygame.draw.line(fins, (*st["ray"], 120), (bx, by), pt, max(1, int(0.5 * K)))
            fin_polys.append(poly)

        # Sungut (barbels) - menonjol sedikit di depan mulut
        x0, y0 = P[0]
        a0 = A[0]
        w0 = self._width(0.0) * MW
        for side in (-1, 1):
            th = side * 0.8
            bx = x0 + math.cos(a0) * math.cos(th) * w0 - math.sin(a0) * math.sin(th) * w0
            by = y0 + math.sin(a0) * math.cos(th) * w0 + math.cos(a0) * math.sin(th) * w0
            wig = math.sin(self.phase * 1.3 + side) * 0.15
            a1 = a0 + side * (0.75 + wig)
            mx, my = bx + math.cos(a1) * 6 * K, by + math.sin(a1) * 6 * K
            a2 = a1 + side * 0.35
            ex, ey = mx + math.cos(a2) * 5 * K, my + math.sin(a2) * 5 * K
            pygame.draw.lines(fins, (226, 214, 196, 215), False, [(bx, by), (mx, my), (ex, ey)],
                              max(1, int(1.2 * K)))

        # Sirip dada (pectoral) besar membulat & sirip perut (pelvic)
        for side in (-1, 1):
            a_p = spine(0.2)[2]
            flap = math.sin(self.phase * 0.9 + side * 0.5) * 0.24
            fan(0.2, side, 40 * K * (0.9 + 0.1 * math.cos(self.phase * 0.9)),
                a_p + side * (math.pi / 2 + 0.6 + flap), 0.95)
            a_v = spine(0.52)[2]
            fan(0.52, side, 21 * K, a_v + side * (math.pi / 2 + 0.85 + flap * 0.5), 0.8)

        # Sirip ekor (caudal) dua lobus, melentur mengikuti kibasan
        xe, ye = P[-1]
        ae = A[-1]
        back = ae + math.pi
        swing = math.sin(self.phase - 5.9) * 0.34
        TL = 58 * K
        pw = self._width(1.0) * MW
        nx, ny = -math.sin(ae), math.cos(ae)
        tips, inner, rays = [], [], []
        M = 19
        for j in range(M):
            u = j / (M - 1) * 2 - 1
            au = abs(u)
            ln = TL * (0.52 + 0.48 * au ** 0.85) * (1.0 - 0.4 * max(0.0, au - 0.82) / 0.18)
            ang1 = back + u * 0.5 + swing * 0.55
            ang2 = back + u * 0.66 + swing * (1.0 + 0.5 * au)
            mx, my = xe + math.cos(ang1) * ln * 0.45, ye + math.sin(ang1) * ln * 0.45
            tx, ty = mx + math.cos(ang2) * ln * 0.55, my + math.sin(ang2) * ln * 0.55
            tips.append((tx, ty))
            inner.append((xe + math.cos(ang1) * ln * 0.5, ye + math.sin(ang1) * ln * 0.5))
            rays.append(((mx, my), (tx, ty)))
        lp = (xe + nx * pw, ye + ny * pw)
        rp = (xe - nx * pw, ye - ny * pw)
        tail_poly = [lp] + tips + [rp]
        pygame.draw.polygon(fins, (*st["fin"], 100), tail_poly)
        pygame.draw.polygon(fins, (*st["fin_base"], 165), [lp] + inner + [rp])
        for (mx, my), (tx, ty) in rays[::2]:
            pygame.draw.lines(fins, (*st["ray"], 115), False, [(xe, ye), (mx, my), (tx, ty)], max(1, int(0.5 * K)))
        fin_polys.append(tail_poly)

        # ---- 2. Tubuh: warna dasar + corak, nanti di-clip dengan mask siluet
        # Lapisan tubuh cukup seukuran bounding box tubuh (jauh lebih kecil = lebih cepat)
        body_pts_fin = outline()
        bx0 = int(min(x for x, _ in body_pts_fin)) - 2
        by0 = int(min(y for _, y in body_pts_fin)) - 2
        size = (int(max(x for x, _ in body_pts_fin)) + 3 - bx0, int(max(y for _, y in body_pts_fin)) + 3 - by0)
        P[:] = [(x - bx0, y - by0) for x, y in P]  # spine()/at()/outline() kini dalam koordinat tubuh
        body_pts = outline()
        body = pygame.Surface(size, pygame.SRCALPHA)
        body.fill((*st["base"], 255))
        for t, s, r, col in self.blobs:
            pygame.draw.circle(body, col, at(t, s * MW), r * MW)

        # Sisik + sirip punggung (overlay transparan)
        ov = pygame.Surface(size, pygame.SRCALPHA)
        sc_r = 3.1 * K
        body_len = (N - 1) * self.joint_dist * S
        dt_row = sc_r * 1.45 / body_len
        lw = max(1, int((0.9 if self.variety == "asagi" else 0.5) * K))
        t = 0.17
        row = 0
        while t < 0.93:
            x_c, y_c, a = spine(t)
            w = self._width(t) * MW * 0.9
            step = sc_r * 1.55
            s = -w + (step * 0.5 if row % 2 else 0.0)
            th = -(a + math.pi)
            while s <= w:
                cx = x_c - math.sin(a) * s
                cy = y_c + math.cos(a) * s
                pygame.draw.arc(ov, st["scale"], (cx - sc_r, cy - sc_r, 2 * sc_r, 2 * sc_r),
                                th - 1.15, th + 1.15, lw)
                s += step
            t += dt_row
            row += 1

        dl, dr = [], []
        for j in range(13):
            u = j / 12
            t = 0.3 + 0.36 * u
            x_c, y_c, a = spine(t)
            sway = math.sin(self.phase - t * 5.0 - 0.9) * 3.2 * K * u
            thick = (0.4 + 1.6 * math.sin(math.pi * u) ** 0.7) * K
            nx_, ny_ = -math.sin(a), math.cos(a)
            dl.append((x_c + nx_ * (sway + thick), y_c + ny_ * (sway + thick)))
            dr.append((x_c + nx_ * (sway - thick), y_c + ny_ * (sway - thick)))
        pygame.draw.polygon(ov, (*st["dorsal"], 150), dl + dr[::-1])
        pygame.draw.lines(ov, (255, 255, 255, 90), False, dl, max(1, int(0.6 * K)))
        body.blit(ov, (0, 0))

        # Shading 3D lembut (digambar resolusi rendah lalu diperbesar = blur murah)
        q = 4
        small = (size[0] // q + 1, size[1] // q + 1)

        def scaled(pts):
            return [(x / q, y / q) for x, y in pts]

        dark = pygame.Surface(small, pygame.SRCALPHA)
        dark.fill((0, 0, 0, 0))
        pygame.draw.polygon(dark, (0, 0, 0, 110), scaled(body_pts))
        pygame.draw.polygon(dark, (0, 0, 0, 40), scaled(outline(0.78, -1.5 * K, -1.5 * K)))
        pygame.draw.polygon(dark, (0, 0, 0, 0), scaled(outline(0.52, -1.5 * K, -1.5 * K)))
        hl = pygame.Surface(small, pygame.SRCALPHA)
        hl.fill((255, 255, 255, 0))
        pygame.draw.polygon(hl, (255, 255, 255, st["hl"]), scaled(outline(0.3, -2.0 * K, -2.0 * K)))
        body.blit(pygame.transform.smoothscale(dark, size), (0, 0))
        body.blit(pygame.transform.smoothscale(hl, size), (0, 0))

        # Mata di sisi kepala + lubang hidung
        for side in (-1, 1):
            ex, ey = at(0.075, side * 0.66 * MW)
            er = 2.5 * K
            pygame.draw.circle(body, (196, 176, 130), (ex, ey), er + 0.9 * K)
            pygame.draw.circle(body, (10, 10, 14), (ex, ey), er)
            pygame.draw.circle(body, (255, 255, 255), (ex - 0.8 * K, ey - 0.8 * K), 0.8 * K)
            hx, hy = at(0.018, side * 0.3 * MW)
            pygame.draw.circle(body, (40, 30, 30), (hx, hy), 0.9 * K)

        # Clip semua lapisan tubuh ke siluet ikan
        mask = pygame.Surface(size, pygame.SRCALPHA)
        mask.fill((255, 255, 255, 0))
        pygame.draw.polygon(mask, (255, 255, 255, 255), body_pts)
        body.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)

        fins.blit(body, (bx0, by0))

        # ---- 3. Bayangan buram di dasar kolam
        sq = q * S
        shadow = pygame.Surface((bw // q + 1, bh // q + 1), pygame.SRCALPHA)
        shadow.fill((2, 10, 14, 0))
        so = (sh_off[0] * S, sh_off[1] * S)
        for poly in fin_polys:
            pygame.draw.polygon(shadow, (2, 10, 14, 40), [((x + so[0]) / sq, (y + so[1]) / sq) for x, y in poly])
        pygame.draw.polygon(shadow, (2, 10, 14, 80), [((x + so[0]) / sq, (y + so[1]) / sq) for x, y in body_pts_fin])
        surf.blit(pygame.transform.smoothscale(shadow, (bw, bh)), (min_x, min_y))

        # ---- 4. Turunkan resolusi (anti-alias) & tempel ke layar
        surf.blit(pygame.transform.smoothscale(fins, (bw, bh)), (min_x, min_y))


class Ripple:
    def __init__(self, x, y, max_r=95):
        self.x = x
        self.y = y
        self.r = 5.0
        self.max_r = max_r
        self.alpha = 110.0

    def update(self, dt):
        self.r += 42.0 * dt
        self.alpha = max(0.0, 110.0 * (1.0 - self.r / self.max_r))

    def draw(self, surf):
        if self.alpha > 2:
            size = int(self.r * 2 + 6)
            rs = pygame.Surface((size, size), pygame.SRCALPHA)
            c = size // 2
            pygame.draw.circle(rs, (175, 225, 245, int(self.alpha)), (c, c), int(self.r), 1)
            if self.r > 18:
                pygame.draw.circle(rs, (175, 225, 245, int(self.alpha * 0.5)), (c, c), int(self.r - 12), 1)
            surf.blit(rs, (int(self.x - c), int(self.y - c)))


class FeedPellet:
    """Butiran pakan koi yang mengapung & perlahan larut/tenggelam di titik klik."""

    def __init__(self, x, y):
        self.x = x + random.uniform(-12, 12)
        self.y = y + random.uniform(-12, 12)
        self.vx = random.uniform(-8, 8)
        self.vy = random.uniform(-8, 8)
        self.life = random.uniform(4.5, 7.5)
        self.max_life = self.life
        self.radius = random.uniform(2.2, 3.6)

    def update(self, dt):
        self.life -= dt
        self.vx *= 0.96
        self.vy *= 0.96
        self.x += self.vx * dt
        self.y += self.vy * dt

    def draw(self, surf):
        if self.life > 0:
            ratio = max(0.0, self.life / self.max_life)
            alpha = int(225 * ratio)
            ps = pygame.Surface((12, 12), pygame.SRCALPHA)
            pygame.draw.circle(ps, (235, 175, 85, alpha), (6, 6), max(1, int(self.radius)))
            pygame.draw.circle(ps, (255, 225, 150, alpha), (5, 5), max(1, int(self.radius * 0.5)))
            surf.blit(ps, (int(self.x - 6), int(self.y - 6)))


def draw_water_surface(surf, t):
    """Efek kilau cahaya matahari di permukaan air & daun teratai."""
    caustic_surf = pygame.Surface((W, H), pygame.SRCALPHA)
    for i in range(7):
        cx = W * 0.5 + math.cos(t * 0.35 + i * 1.1) * 280
        cy = H * 0.5 + math.sin(t * 0.28 + i * 1.4) * 180
        rad = int(130 + 35 * math.sin(t * 0.6 + i))
        pygame.draw.circle(caustic_surf, (120, 210, 235, 8), (int(cx), int(cy)), rad)
    surf.blit(caustic_surf, (0, 0))

    pads = [
        (135, 125, 62, 0.45, True),
        (205, 178, 44, 2.2, False),
        (1025, 595, 68, 3.7, True),
        (955, 635, 48, 1.1, False),
    ]
    for px, py, rad, notch, has_flower in pads:
        sway_x = math.sin(t * 0.8 + px * 0.01) * 3.0
        sway_y = math.cos(t * 0.7 + py * 0.01) * 2.5
        x, y = px + sway_x, py + sway_y

        ps = pygame.Surface((rad * 2 + 40, rad * 2 + 40), pygame.SRCALPHA)
        c = rad + 15
        pygame.draw.circle(ps, (2, 10, 14, 80), (c + 14, c + 18), rad)
        pygame.draw.circle(ps, (26, 76, 40), (c, c), rad)
        pygame.draw.circle(ps, (38, 102, 54), (c - 2, c - 2), int(rad * 0.86))
        for k in range(8):
            va = notch + 0.5 + k * 0.68
            pygame.draw.line(
                ps,
                (52, 122, 68, 120),
                (c, c),
                (c + math.cos(va) * (rad * 0.85), c + math.sin(va) * (rad * 0.85)),
                1,
            )
        cut_pts = [
            (c, c),
            (c + math.cos(notch - 0.24) * (rad + 4), c + math.sin(notch - 0.24) * (rad + 4)),
            (c + math.cos(notch + 0.24) * (rad + 4), c + math.sin(notch + 0.24) * (rad + 4)),
        ]
        pygame.draw.polygon(ps, (0, 0, 0, 0), cut_pts)

        if has_flower:
            fx, fy = c - 6, c - 4
            for layer_r, col in [(16, (235, 140, 165)), (11, (250, 185, 200)), (6, (255, 235, 130))]:
                for p_ang in range(0, 360, 45):
                    ra = math.radians(p_ang + t * 4)
                    px_f = fx + math.cos(ra) * (layer_r * 0.55)
                    py_f = fy + math.sin(ra) * (layer_r * 0.55)
                    pygame.draw.circle(ps, col, (int(px_f), int(py_f)), layer_r // 2)

        surf.blit(ps, (int(x - c), int(y - c)))


def main():
    pond_bed = create_pond_bed()

    kois = [
        RealisticKoi(420, 310, 0.3, 100, 1.18, "kohaku"),
        RealisticKoi(740, 450, 3.4, 92, 1.12, "sanke"),
        RealisticKoi(580, 520, -1.2, 86, 1.05, "showa"),
        RealisticKoi(320, 500, -0.5, 90, 0.95, "ogon"),
        RealisticKoi(860, 260, 2.2, 84, 1.00, "tancho"),
        RealisticKoi(640, 200, 1.0, 80, 0.90, "asagi"),
    ]

    ripples = []
    pellets = []
    ripple_timer = 0.0
    sim_time = 0.0

    running = True
    while running:
        dt = clock.tick(60) / 1000.0
        sim_time += dt

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                mx, my = event.pos
                ripples.append(Ripple(mx, my, max_r=135))
                if event.button == 1:
                    # Klik kiri: tebar butiran pakan & panggil ikan koi mendekat
                    for _ in range(6):
                        pellets.append(FeedPellet(mx, my))
                    for k in kois:
                        k.attract_to(mx, my)
                elif event.button == 3:
                    # Klik kanan: riak air saja tanpa pakan
                    ripples.append(Ripple(mx, my, max_r=165))

        screen.blit(pond_bed, (0, 0))

        # Update & gambar butiran pakan (jika ada yang dimakan ikan, pellet hilang)
        for p in pellets[:]:
            p.update(dt)
            eaten = False
            for k in kois:
                if math.hypot(k.x - p.x, k.y - p.y) < 22.0 * k.scale:
                    eaten = True
                    ripples.append(Ripple(p.x, p.y, max_r=45))
                    break
            if eaten or p.life <= 0:
                pellets.remove(p)
            else:
                p.draw(screen)

        # Update & gambar semua ikan koi
        for k in kois:
            k.update(dt)
            k.draw(screen)

        # Riak air otomatis dari gerakan ikan
        ripple_timer += dt
        if ripple_timer > 0.75:
            ripple_timer = 0.0
            chosen = random.choice(kois)
            ripples.append(Ripple(chosen.x, chosen.y, max_r=85))

        for r in ripples[:]:
            r.update(dt)
            r.draw(screen)
            if r.alpha <= 2:
                ripples.remove(r)

        # Permukaan cahaya air & daun/bunga teratai
        draw_water_surface(screen, sim_time)

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
