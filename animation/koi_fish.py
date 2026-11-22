"""
Standalone pygame Realistic Living Koi Pond.

RealisticKoi (32-segment spine, fins, barbels, soft 3D shadow) on a
procedural pond bed (depth gradient + stones) with caustics and swaying
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


class RealisticKoi:
    def __init__(self, x, y, angle, base_speed, scale, variety):
        self.x = x
        self.y = y
        self.angle = angle
        self.base_speed = base_speed
        self.speed = base_speed
        self.scale = scale
        self.variety = variety

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

        # Pre-render corak acak organik untuk masing-masing ikan agar tidak berubah-ubah
        self.spots = self._generate_organic_spots()

    def _generate_organic_spots(self):
        rng = random.Random(hash((self.variety, round(self.scale, 2), round(self.phase, 2))))
        spots = []
        if self.variety in ("kohaku", "sanke", "showa"):
            for _ in range(rng.randint(3, 5)):
                spots.append({
                    "t_center": rng.uniform(0.08, 0.78),
                    "t_radius": rng.uniform(0.08, 0.16),
                    "side_offset": rng.uniform(-0.35, 0.35),
                    "color": (228, 62, 22) if rng.random() > 0.3 else (242, 85, 28),
                })
        if self.variety in ("sanke", "showa"):
            for _ in range(rng.randint(3, 6)):
                spots.append({
                    "t_center": rng.uniform(0.15, 0.82),
                    "t_radius": rng.uniform(0.04, 0.09),
                    "side_offset": rng.uniform(-0.45, 0.45),
                    "color": (24, 26, 32),
                })
        return spots

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

        # Update ruas tulang belakang (Inverse Kinematics / Chain Following)
        self.joints[0] = [self.x, self.y]
        for i in range(1, self.num_joints):
            t = i / (self.num_joints - 1)
            px, py = self.joints[i - 1]
            cx, cy = self.joints[i]

            # Arah dari ruas sekarang ke ruas depannya
            ang = math.atan2(py - cy, px - cx)

            # Tambahkan gelombang kibasan berenang yang membesar ke ekor
            swim_wave = math.sin(self.phase - t * 5.2) * (0.14 * (t ** 1.35))
            target_ang = ang + swim_wave

            self.joints[i][0] = px - math.cos(target_ang) * self.joint_dist
            self.joints[i][1] = py - math.sin(target_ang) * self.joint_dist

    def _body_radius(self, t):
        """Profil ketebalan tubuh ikan koi yang realistis dari moncong ke pangkal ekor."""
        if t < 0.26:
            return (0.28 + 0.72 * math.sin((t / 0.26) * (math.pi / 2))) * 22.0 * self.scale
        else:
            u = (t - 0.26) / 0.74
            return (math.cos(u * (math.pi / 2)) ** 0.85) * 22.0 * self.scale

    def draw(self, surf):
        # Hitung sudut masing-masing ruas
        angles = []
        for i in range(self.num_joints):
            if i == 0:
                ang = self.angle
            else:
                dx = self.joints[i - 1][0] - self.joints[i][0]
                dy = self.joints[i - 1][1] - self.joints[i][1]
                ang = math.atan2(dy, dx)
            angles.append(ang)

        # Tentukan bounding box lokal agar menggambar alpha sangat cepat (60 FPS)
        xs = [p[0] for p in self.joints]
        ys = [p[1] for p in self.joints]
        pad = int(75 * self.scale)
        min_x = max(0, int(min(xs)) - pad)
        min_y = max(0, int(min(ys)) - pad)
        max_x = min(W, int(max(xs)) + pad + 35)
        max_y = min(H, int(max(ys)) + pad + 35)
        bw, bh = max_x - min_x, max_y - min_y
        if bw <= 0 or bh <= 0:
            return

        local_surf = pygame.Surface((bw, bh), pygame.SRCALPHA)

        def to_loc(px, py):
            return px - min_x, py - min_y

        # 1. Bayangan lembut ikan di dasar kolam (memberi ilusi 3D melayang di dalam air)
        for i in range(self.num_joints):
            t = i / (self.num_joints - 1)
            r = int(self._body_radius(t) * 0.95)
            if r > 1:
                lx, ly = to_loc(self.joints[i][0] + 24, self.joints[i][1] + 30)
                pygame.draw.circle(local_surf, (2, 10, 14, 48), (int(lx), int(ly)), r)

        # 2. Sungut khas ikan koi (Barbels) di ujung kepala
        hx, hy = to_loc(*self.joints[0])
        hang = angles[0]
        for side in (-1, 1):
            b_ang = hang + side * 0.55 + math.sin(self.phase) * 0.08
            bx1 = hx + math.cos(hang + side * 0.35) * 4 * self.scale
            by1 = hy + math.sin(hang + side * 0.35) * 4 * self.scale
            bx2 = bx1 + math.cos(b_ang) * 12 * self.scale
            by2 = by1 + math.sin(b_ang) * 12 * self.scale
            pygame.draw.line(local_surf, (235, 225, 215, 190), (bx1, by1), (bx2, by2), max(1, int(1.6 * self.scale)))

        # 3. Sirip Pektoral (kiri & kanan) transparan dengan serat halus
        px_base, py_base = to_loc(*self.joints[5])
        pang = angles[5]
        flap = math.sin(self.phase * 0.85) * 0.26
        for side in (-1, 1):
            f_ang = pang + side * (1.12 + flap)
            p1 = (px_base, py_base)
            p2 = (
                px_base + math.cos(f_ang - 0.28 * side) * 38 * self.scale,
                py_base + math.sin(f_ang - 0.28 * side) * 38 * self.scale,
            )
            p3 = (
                px_base + math.cos(f_ang + 0.12 * side) * 42 * self.scale,
                py_base + math.sin(f_ang + 0.12 * side) * 42 * self.scale,
            )
            p4 = (
                px_base + math.cos(f_ang + 0.42 * side) * 26 * self.scale,
                py_base + math.sin(f_ang + 0.42 * side) * 26 * self.scale,
            )
            pygame.draw.polygon(local_surf, (245, 248, 252, 115), [p1, p2, p3, p4])
            for ray_pt in (p2, p3, p4):
                pygame.draw.line(local_surf, (255, 255, 255, 145), p1, ray_pt, 1)

        # 4. Sirip Ekor (Caudal Fin) melengkung organik dan transparan
        tx, ty = to_loc(*self.joints[-1])
        tang = angles[-1] + math.pi
        tail_poly = [(tx, ty)]
        num_rays = 11
        for k in range(num_rays):
            u = (k / (num_rays - 1)) * 2.0 - 1.0
            spread = u * 0.62
            fork = 1.0 - 0.18 * math.exp(-(u * 3.0) ** 2)
            length = (46.0 * fork * (1.0 - 0.18 * (u ** 2))) * self.scale
            wave_tail = math.sin(self.phase - 5.5 + u * 0.8) * 0.18
            ang = tang + spread + wave_tail
            tail_poly.append((tx + math.cos(ang) * length, ty + math.sin(ang) * length))

        pygame.draw.polygon(local_surf, (248, 246, 242, 135), tail_poly)
        for pt in tail_poly[1::2]:
            pygame.draw.line(local_surf, (255, 255, 255, 160), (tx, ty), pt, 1)

        # 5. Tubuh Utama (dari ekor ke kepala agar tumpukan mulus)
        base_col = (242, 242, 245) if self.variety != "ogon" else (245, 195, 45)
        edge_col = (195, 200, 210) if self.variety != "ogon" else (190, 140, 20)

        for i in range(self.num_joints - 1, -1, -1):
            t = i / (self.num_joints - 1)
            lx, ly = to_loc(*self.joints[i])
            ang = angles[i]
            r = max(1, int(self._body_radius(t)))

            pygame.draw.circle(local_surf, edge_col, (int(lx), int(ly)), r)
            if r > 2:
                pygame.draw.circle(local_surf, base_col, (int(lx - 1), int(ly - 1)), int(r * 0.88))

            for spot in self.spots:
                dist_t = abs(t - spot["t_center"])
                if dist_t < spot["t_radius"]:
                    factor = math.cos((dist_t / spot["t_radius"]) * (math.pi / 2))
                    sr = int(r * 0.86 * factor)
                    if sr > 1:
                        perp_ang = ang + math.pi / 2
                        sx = lx + math.cos(perp_ang) * (r * spot["side_offset"])
                        sy = ly + math.sin(perp_ang) * (r * spot["side_offset"])
                        pygame.draw.circle(local_surf, spot["color"], (int(sx), int(sy)), sr)

            if r > 4 and 0.08 < t < 0.72:
                pygame.draw.circle(local_surf, (255, 255, 255, 95), (int(lx - 2), int(ly - 2)), int(r * 0.42))

        # 6. Sirip Punggung (Dorsal Fin)
        dorsal_pts = []
        for i in range(8, 22):
            t = i / (self.num_joints - 1)
            lx, ly = to_loc(*self.joints[i])
            ang = angles[i]
            wave_d = math.sin(self.phase - t * 5.0) * 4.5 * self.scale
            dx = lx + math.cos(ang + math.pi / 2) * wave_d
            dy = ly + math.sin(ang + math.pi / 2) * wave_d
            dorsal_pts.append((dx, dy))
        if len(dorsal_pts) >= 2:
            pygame.draw.lines(local_surf, (255, 255, 255, 165), False, dorsal_pts, max(2, int(3.2 * self.scale)))

        # 7. Sepasang Mata dengan kilau pupil
        ex_base, ey_base = to_loc(*self.joints[2])
        eang = angles[2]
        for side in (-1, 1):
            perp = eang + side * 1.48
            ex = ex_base + math.cos(perp) * 11.5 * self.scale
            ey = ey_base + math.sin(perp) * 11.5 * self.scale
            er = max(2, int(2.8 * self.scale))
            pygame.draw.circle(local_surf, (220, 215, 200), (int(ex), int(ey)), er + 1)
            pygame.draw.circle(local_surf, (12, 14, 18), (int(ex), int(ey)), er)
            pygame.draw.circle(local_surf, (255, 255, 255), (int(ex - 1), int(ey - 1)), 1)

        surf.blit(local_surf, (min_x, min_y))


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
        RealisticKoi(420, 310, 0.3, 105, 1.18, "kohaku"),
        RealisticKoi(740, 450, 3.4, 95, 1.12, "sanke"),
        RealisticKoi(580, 520, -1.2, 88, 1.00, "showa"),
        RealisticKoi(320, 500, -0.5, 92, 0.92, "ogon"),
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

        # Update & gambar semua ikan koi (tetap memakai RealisticKoi)
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
