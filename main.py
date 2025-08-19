import pygame, random, math, os, sys
pygame.init()

# ---------------- SETTINGS ----------------
SCREEN_W, SCREEN_H = 1200, 700
FPS = 60
TITLE = "Space Invaders"

screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
pygame.display.set_caption(TITLE)
try:
    icon = pygame.image.load("3d-box.png")
    pygame.display.set_icon(icon)
except:
    pass

clock = pygame.time.Clock()

# ---------------- SAFE LOAD HELPERS ----------------
def load_image(path, scale=1.0, fallback_size=(64,64), tint=None):
    try:
        img = pygame.image.load(path).convert_alpha()
        if scale != 1.0:
            img = pygame.transform.smoothscale(img, (int(img.get_width()*scale), int(img.get_height()*scale)))
        if tint:
            tmp = img.copy()
            tmp.fill(tint, special_flags=pygame.BLEND_RGBA_MULT)
            return tmp
        return img
    except:
        surf = pygame.Surface(fallback_size, pygame.SRCALPHA)
        surf.fill((225, 225, 235, 230))
        pygame.draw.rect(surf, (70, 80, 100), surf.get_rect(), 2)
        return surf

def load_explosion_folder(folder_path, scale=0.6, fallback_color=(255,140,0)):
    frames = []
    if os.path.isdir(folder_path):
        for fn in sorted(os.listdir(folder_path)):
            if fn.lower().endswith(".png"):
                try:
                    img = pygame.image.load(os.path.join(folder_path, fn)).convert_alpha()
                    if scale != 1.0:
                        img = pygame.transform.smoothscale(img, (int(img.get_width()*scale), int(img.get_height()*scale)))
                    frames.append(img)
                except:
                    pass
    if not frames:
        for r in range(8, 72, 7):
            surf = pygame.Surface((140,140), pygame.SRCALPHA)
            pygame.draw.circle(surf, fallback_color, (70,70), r)
            pygame.draw.circle(surf, (255,255,255,120), (70,70), max(r-8,1))
            frames.append(surf)
    return frames

def try_sound(path):
    try:
        return pygame.mixer.Sound(path)
    except:
        return None

# ---------------- CAMERA SHAKE ----------------
class ScreenShake:
    def __init__(self):
        self.t = 0.0
        self.intensity = 0.0
    def add(self, intensity=5, duration=0.18):
        self.intensity = max(self.intensity, intensity)
        self.t = max(self.t, duration)
    def update(self, dt):
        if self.t > 0:
            self.t -= dt
            if self.t < 0: self.t = 0
        else:
            self.intensity = 0
    def offset(self):
        if self.t <= 0: return (0,0)
        k = self.t
        amp = int(self.intensity * k * 0.9)
        return (random.randint(-amp, amp), random.randint(-amp, amp))

shake = ScreenShake()

# ---------------- BACKGROUND ----------------
bg_base = load_image("freepik__upload__31851.png", 1.0, (SCREEN_W, SCREEN_H))
bg_base = pygame.transform.smoothscale(bg_base, (SCREEN_W, SCREEN_H))

def build_star_layer(density=90, alpha=(40,120)):
    s = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
    for _ in range(density):
        x = random.randint(0, SCREEN_W-2); y = random.randint(0, SCREEN_H-2)
        pygame.draw.circle(s, (255,255,255, random.randint(*alpha)), (x,y), random.randint(1,2))
    return s

bg_layer1 = build_star_layer(100, (40,120))
bg_layer2 = build_star_layer(60, (20,80))
p1 = 0.0; p2 = 0.0

vignette = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
for i in range(220):
    c = max(0, 160 - i)
    pygame.draw.rect(vignette, (0,0,0, int(c*0.25)), (i, i, SCREEN_W-2*i, SCREEN_H-2*i), 2)

# ---------------- SOUNDS ----------------
hit_snd = try_sound("sfx_hit.wav")
boom_snd = try_sound("sfx_boom.wav")
power_snd = try_sound("sfx_power.wav")
player_bullet_snd = try_sound("Untitled video - Made with Clipchamp (2).mp3")
enemy_bullet_snd = try_sound("Enemy1Blaster.mp3")
enemy2_bullet_snd = try_sound("Enemy2Blaster.mp3")
enemy3_bullet_snd = try_sound("Enemy3Blasters.mp3")
enemy4_bullet_snd = try_sound("Enemy4Blasters.mp3")
powerup_collect_snd = try_sound("power-up-type-1-230548.mp3")

try:
    pygame.mixer.music.load("spaceship-arcade-shooter-game-background-soundtrack-318508.mp3")
    pygame.mixer.music.set_volume(0.6)
    pygame.mixer.music.play(-1)
except pygame.error:
    print("Could not load or play background music.")
    pass

# ---------------- SPRITES ----------------
class Bullet(pygame.sprite.Sprite):
    def __init__(self, x, y, img, vy, friendly=True):
        super().__init__()
        self.image = img
        self.rect = self.image.get_rect(center=(x,y))
        self.vy = vy
        self.friendly = friendly
    def update(self, dt):
        self.rect.y += int(self.vy * dt)
        if self.rect.bottom < -60 or self.rect.top > SCREEN_H + 60:
            self.kill()

class Particle(pygame.sprite.Sprite):
    def __init__(self, pos, color, life=0.45, gravity=380, velocity_range=(-150,150,-240,-20)):
        super().__init__()
        self.image = pygame.Surface((3,3), pygame.SRCALPHA)
        self.image.fill(color)
        self.rect = self.image.get_rect(center=pos)
        self.vx = random.uniform(velocity_range[0], velocity_range[1])
        self.vy = random.uniform(velocity_range[2], velocity_range[3])
        self.g = gravity
        self.life = life
        self.max_life = life
    def update(self, dt):
        self.life -= dt
        if self.life <= 0:
            self.kill(); return
        self.vy += self.g * dt
        self.rect.x += int(self.vx * dt)
        self.rect.y += int(self.vy * dt)
        self.image.set_alpha(int(255 * max(0, self.life/self.max_life)))

class Explosion(pygame.sprite.Sprite):
    def __init__(self, frames, center, fps=34):
        super().__init__()
        self.frames = frames
        self.index = 0
        self.timer = 0.0
        self.frame_time = 1.0 / fps
        self.image = self.frames[0]
        self.rect = self.image.get_rect(center=center)
    def update(self, dt):
        self.timer += dt
        while self.timer >= self.frame_time:
            self.timer -= self.frame_time
            self.index += 1
            if self.index >= len(self.frames):
                self.kill(); return
            c = self.rect.center
            self.image = self.frames[self.index]
            self.rect = self.image.get_rect(center=c)

class Player(pygame.sprite.Sprite):
    def __init__(self, img, bullet_img, exhaust_img):
        super().__init__()
        self.base_img = img
        self.image = self.base_img.copy()
        self.rect = self.image.get_rect(midbottom=(SCREEN_W//2, SCREEN_H-28))
        self.bullet_img = bullet_img
        self.exhaust_img = exhaust_img
        self.speed = 420
        self.cooldown = 0.18
        self.cool = 0
        self.lives = 5
        self.score = 0
        self.target_score = 0
        self.inv = 0.0
        self.flash = 0.0
        self.rapid = 0.0
        self.rapid_max = 7.0
        self.shield = 0.0
        self.shield_max = 5.5
        
        # New visual effect timers
        self.damage_spark_timer = 0
        self.hull_glow_t = 0
        self.engine_t = 0
        self.is_shooting = False

    def update(self, dt, keys):
        dx = (keys[pygame.K_RIGHT] or keys[pygame.K_d]) - (keys[pygame.K_LEFT] or keys[pygame.K_a])
        self.rect.x += int(dx * self.speed * dt)
        self.rect.x = max(0, min(SCREEN_W - self.rect.width, self.rect.x))

        if self.cool > 0: self.cool -= dt
        if self.inv > 0: self.inv -= dt
        if self.flash > 0: self.flash -= dt
        if self.rapid > 0: self.rapid -= dt
        if self.shield > 0: self.shield -= dt
        
        # Update visual effect timers
        if self.damage_spark_timer > 0: self.damage_spark_timer -= dt
        self.hull_glow_t += dt
        self.engine_t += dt
        self.is_shooting = (keys[pygame.K_SPACE] or keys[pygame.K_w] or keys[pygame.K_UP]) and self.can_shoot()
        
        # Flashing white on hit
        if self.flash > 0:
            self.image = self.base_img.copy()
            overlay = pygame.Surface(self.image.get_size(), pygame.SRCALPHA)
            overlay.fill((255,255,255,120))
            self.image.blit(overlay, (0,0))
        else:
            self.image = self.base_img
        
        if self.score < self.target_score:
            self.score += min(50, self.target_score - self.score)

    def can_shoot(self): return self.cool <= 0
    def shoot(self, group):
        if not self.can_shoot(): return
        cd = 0.09 if self.rapid>0 else self.cooldown
        self.cool = cd
        bx, by = self.rect.centerx, self.rect.top+10
        if self.rapid>0:
            for ox in (-12, 0, 12):
                group.add(Bullet(bx+ox, by, self.bullet_img, vy=-880, friendly=True))
        else:
            group.add(Bullet(bx, by, self.bullet_img, vy=-880, friendly=True))

        if player_bullet_snd:
            player_bullet_snd.play()
    
    def hit(self):
        if self.inv > 0 or self.shield > 0: return False
        self.lives -= 1
        self.inv = 1.1
        self.flash = 0.25
        self.damage_spark_timer = 0.6  # Start spark effect
        shake.add(7, 0.22)
        return self.lives <= 0

class Enemy(pygame.sprite.Sprite):
    def __init__(self, img, bullet_img, explosion_frames, spawn_rect, speed=140, shoot_cool=(0.9, 2.2), score=70):
        super().__init__()
        self.image = img
        self.base_img = img
        self.rect = self.image.get_rect()
        self.spawn_rect = spawn_rect
        self.speed = speed
        self.shoot_rng = shoot_cool
        self.bullet_img = bullet_img
        self.exp_frames = explosion_frames
        self.score_val = score
        self.alive = True
        self.respawn()
    def respawn(self):
        self.rect.x = random.randint(self.spawn_rect.left, self.spawn_rect.right - self.rect.width)
        self.rect.y = random.randint(self.spawn_rect.top, self.spawn_rect.bottom)
        self.vx = random.choice([-1,1]) * (self.speed + random.uniform(-30,30))
        self.shoot_t = random.uniform(*self.shoot_rng)
        self.alive = True
    def update(self, dt):
        if not self.alive: return
        self.rect.x += int(self.vx * dt)
        if self.rect.left <= 0:
            self.vx = abs(self.vx)
        elif self.rect.right >= SCREEN_W:
            self.vx = -abs(self.vx)
    def try_shoot(self, dt, group):
        if not self.alive: return
        self.shoot_t -= dt
        if self.shoot_t <= 0:
            self.shoot_t = random.uniform(*self.shoot_rng)
            group.add(Bullet(self.rect.centerx, self.rect.bottom-6, self.bullet_img, vy=400, friendly=False))

            if self.bullet_img == bullet_e1 and enemy_bullet_snd:
                enemy_bullet_snd.play()
            elif self.bullet_img == bullet_e2 and enemy2_bullet_snd:
                enemy2_bullet_snd.play()
            elif self.bullet_img == bullet_e3 and enemy3_bullet_snd:
                enemy3_bullet_snd.play()
            elif self.bullet_img == bullet_e4 and enemy4_bullet_snd:
                enemy4_bullet_snd.play()

    def explode(self, effects, particles):
        self.alive = False
        effects.add(Explosion(self.exp_frames, self.rect.center, fps=40))
        for _ in range(16):
            particles.add(Particle(self.rect.center, (255, 170, 60)))
        if boom_snd: boom_snd.play()
        shake.add(11, 0.25)

class PowerUp(pygame.sprite.Sprite):
    TYPES = ("heal", "rapid", "shield")
    def __init__(self, center):
        super().__init__()
        self.type = random.choice(PowerUp.TYPES)
        color = {"heal":(90,240,120), "rapid":(120,170,255), "shield":(255,220,120)}[self.type]
        self.image = pygame.Surface((26,26), pygame.SRCALPHA)
        pygame.draw.circle(self.image, color, (13,13), 13)
        pygame.draw.circle(self.image, (255,255,255,100), (13,13), 10, 2)
        self.rect = self.image.get_rect(center=center)
        self.vy = 140
        self.t = 9.0
    def update(self, dt):
        self.rect.y += int(self.vy * dt)
        self.t -= dt
        if self.t <= 0 or self.rect.top > SCREEN_H: self.kill()

def apply_powerup(player, t):
    if t == "heal":
        player.lives = min(7, player.lives + 1)
    elif t == "rapid":
        player.rapid = player.rapid_max
    elif t == "shield":
        player.shield = player.shield_max
    if powerup_collect_snd:
        powerup_collect_snd.play()
    elif power_snd:
        power_snd.play()

# ---------------- ASSETS ----------------
player_img = load_image("PNG/Example/03.png", 0.5, (84,84))
player_bullet_img = load_image("PNG/Bullets/12.png", 0.6, (10,24))
player_exhaust_img = load_image("PNG/Flame/11.png", 0.4, (20,20))

bullet_e1 = load_image("11.png", 0.7, (12,24))
bullet_e2 = load_image("09.png", 0.7, (12,24))
bullet_e3 = load_image("04.png", 0.7, (12,24))
bullet_e4 = load_image("02.png", 0.7, (12,24))

enemy1_img = load_image("Ship6/Ship6-ezgif.com-rotate.png", 0.6, (80,80))
enemy2_img = load_image("Ship4-ezgif.com-rotate.png", 0.6, (80,80))
enemy3_img = load_image("Ship3-ezgif.com-rotate.png", 0.6, (80,80))
enemy4_img = load_image("Ship5-ezgif.com-rotate.png", 0.6, (80,80))

exp1 = load_explosion_folder(r"C:\Users\d1mas\Desktop\Game2\Ship6_Explosion", 0.6, (255,130,80))
exp2 = load_explosion_folder(r"C:\Users\d1mas\Desktop\Game2\Ship4_Explosion", 0.6, (120,255,210))
exp3 = load_explosion_folder(r"C:\Users\d1mas\Desktop\Game2\Ship3_Explosion", 0.6, (255,90,170))
exp4 = load_explosion_folder(r"C:\Users\d1mas\Desktop\Game2\Ship5_Explosion", 0.6, (255,245,120))

asteroid_atlas = load_image("Setofcolorfulasteroidsofdifferentshapestexturesandsize-ezgif.com-crop.jpg", 1.0, (180,140))

# ---------------- GROUPS ----------------
all_sprites = pygame.sprite.LayeredUpdates()
player_group = pygame.sprite.GroupSingle()
enemy_group = pygame.sprite.Group()
bullet_group = pygame.sprite.Group()
effects_group = pygame.sprite.Group()
particles_group = pygame.sprite.Group()
powerups_group = pygame.sprite.Group()
asteroid_group = pygame.sprite.Group()

player = Player(player_img, player_bullet_img, player_exhaust_img)
player_group.add(player)
all_sprites.add(player)

spawn_rect = pygame.Rect(0, 40, SCREEN_W, 190)

def spawn_wave(num, tier=1):
    for _ in range(num):
        t = random.choice([1,2,3,4])
        # Increase enemy speed and adjust shoot cooldown for higher tiers
        enemy_speed = 140 + 10 * tier
        shoot_cooldown_min = max(0.4, 0.9 - 0.05 * tier) # Min cooldown can't go below 0.4
        shoot_cooldown_max = max(1.0, 2.2 - 0.1 * tier) # Max cooldown can't go below 1.0

        if t==1:
            e=Enemy(enemy1_img, bullet_e1, exp1, spawn_rect, enemy_speed, (shoot_cooldown_min,shoot_cooldown_max), 60)
        elif t==2:
            e=Enemy(enemy2_img, bullet_e2, exp2, spawn_rect, enemy_speed + 10, (shoot_cooldown_min - 0.05, shoot_cooldown_max - 0.05), 80)
        elif t==3:
            e=Enemy(enemy3_img, bullet_e3, exp3, spawn_rect, enemy_speed + 20, (shoot_cooldown_min - 0.1, shoot_cooldown_max - 0.1), 95)
        else: # t==4
            e=Enemy(enemy4_img, bullet_e4, exp4, spawn_rect, enemy_speed + 30, (shoot_cooldown_min - 0.15, shoot_cooldown_max - 0.15), 110)
        enemy_group.add(e); all_sprites.add(e)

wave = 1
wave_cooldown = 2.0
wave_active = False

# ---------------- UI ----------------
font_sm = pygame.font.Font(None, 28)
font_md = pygame.font.Font(None, 36)
font_big = pygame.font.Font(None, 64)

# New fonts for the main menu, mimicking the CSS
font_menu_title = pygame.font.SysFont('Courier New', 72, bold=True)
font_menu_sub = pygame.font.SysFont('Courier New', 22)
font_menu_button = pygame.font.SysFont('Courier New', 36, bold=True)

# New fonts for the HUD, also matching the CSS
font_hud_label = pygame.font.SysFont('Courier New', 16, bold=True)
font_hud_score = pygame.font.SysFont('Courier New', 32, bold=True)
font_hud_wave = pygame.font.SysFont('Courier New', 24, bold=True)

def draw_rounded_rect(surf, rect, color, radius=10, width=0):
    x,y,w,h = rect
    shape = pygame.Surface((w,h), pygame.SRCALPHA)
    pygame.draw.rect(shape, color, (radius,0,w-2*radius,h))
    pygame.draw.rect(shape, color, (0,radius,w,h-2*radius))
    pygame.draw.circle(shape, color, (radius, radius), radius)
    pygame.draw.circle(shape, color, (w-radius, radius), radius)
    pygame.draw.circle(shape, color, (radius, h-radius), radius)
    pygame.draw.circle(shape, color, (w-radius, h-radius), radius)
    surf.blit(shape, (x,y), special_flags=0)

def draw_lives(surf, x, y, lives):
    heart_surf = pygame.Surface((28,28), pygame.SRCALPHA)
    pygame.draw.circle(heart_surf, (255,100,120, 200), (8,8), 8)
    pygame.draw.circle(heart_surf, (255,100,120, 200), (20,8), 8)
    pygame.draw.polygon(heart_surf, (255,100,120, 200), [(4,12),(24,12),(14,24)])
    for i in range(lives):
        surf.blit(heart_surf, (x + i * 26, y))
        
def draw_powerup_bar(surf, y, label, current_time, max_time, color):
    if current_time <= 0: return

    # Bar background
    bar_width = 120
    bar_height = 10
    bar_x = (SCREEN_W - bar_width) // 2
    bar_y = y
    pygame.draw.rect(surf, (20, 25, 40, 120), (bar_x, bar_y, bar_width, bar_height), border_radius=5)

    # Bar foreground
    fill_width = bar_width * (current_time / max_time)
    pygame.draw.rect(surf, color, (bar_x, bar_y, fill_width, bar_height), border_radius=5)
    
    # Label
    label_text = font_sm.render(label, True, (200, 200, 220))
    label_rect = label_text.get_rect(center=(SCREEN_W // 2, y + bar_height + 14))
    surf.blit(label_text, label_rect)

def draw_hud(surface, player, wave):
    # Main HUD box
    hud_rect = (0, 0, SCREEN_W, 60)
    draw_rounded_rect(surface, hud_rect, (30, 0, 60, 240), 0)
    pygame.draw.line(surface, (139, 92, 246), (0, 59), (SCREEN_W, 59), 2)
    
    # Left: Lives
    lives_label = font_hud_label.render("LIVES", True, (167, 139, 250))
    surface.blit(lives_label, (20, 10))
    draw_lives(surface, 20, 25, max(0, player.lives))
    
    # Center: Score
    score_label = font_hud_label.render("SCORE", True, (167, 139, 250))
    score_text = font_hud_score.render(f"{player.score:06d}", True, (59, 130, 246))
    score_rect_label = score_label.get_rect(center=(SCREEN_W//2, 18))
    score_rect_value = score_text.get_rect(center=(SCREEN_W//2, 40))
    surface.blit(score_label, score_rect_label)
    surface.blit(score_text, score_rect_value)
    
    # Right: Wave
    wave_label = font_hud_label.render("WAVE", True, (167, 139, 250))
    wave_text = font_hud_wave.render(f"{wave:02d}", True, (139, 92, 246))
    surface.blit(wave_label, (SCREEN_W - wave_label.get_width() - 20, 18))
    surface.blit(wave_text, (SCREEN_W - wave_text.get_width() - 20, 36))
    
    # Power-up bars below HUD
    powerup_y = 65
    if player.rapid > 0:
        draw_powerup_bar(surface, powerup_y, "RAPID", player.rapid, player.rapid_max, (120, 170, 255))
        powerup_y += 30
    if player.shield > 0:
        draw_powerup_bar(surface, powerup_y, "SHIELD", player.shield, player.shield_max, (255, 220, 120))


# ---------------- NEW MENU FUNCTIONS ----------------

def draw_menu_background():
    # Similar to the game loop background
    global p1, p2
    dt = 1.0/FPS
    p1 = (p1 - 18 * dt) % SCREEN_W
    p2 = (p2 - 45 * dt) % SCREEN_W
    screen.blit(bg_base, (0,0))
    s1 = bg_layer1; s2 = bg_layer2
    screen.blit(s1, (-p1, 0)); screen.blit(s1, (-p1 + SCREEN_W, 0))
    screen.blit(s2, (-p2, 0)); screen.blit(s2, (-p2 + SCREEN_W, 0))

class MenuBullet(pygame.sprite.Sprite):
    def __init__(self, x, y, vy):
        super().__init__()
        self.size = 6
        self.image = pygame.Surface((self.size, self.size), pygame.SRCALPHA)
        self.rect = self.image.get_rect(center=(x, y))
        self.vy = vy
    
    def update(self, dt):
        self.rect.y += self.vy * dt
        if self.rect.bottom < 0:
            self.kill()

    def draw(self, surface):
        # Draw a core white pixel
        pygame.draw.rect(surface, (255, 255, 255), (self.rect.x + self.size//2, self.rect.y + self.size//2, 1, 1))

        # Create a glowing trail behind the bullet
        glow_alpha = 100
        for i in range(1, 4):
            glow_surf = pygame.Surface((self.size + i*4, self.size + i*4), pygame.SRCALPHA)
            pygame.draw.circle(glow_surf, (255, 255, 255, glow_alpha - i*20), (glow_surf.get_width() // 2, glow_surf.get_height() // 2), self.size // 2 + i*2)
            surface.blit(glow_surf, glow_surf.get_rect(center=self.rect.center))

class PlayerRocket(pygame.sprite.Sprite):
    def __init__(self, img, exhaust_img):
        super().__init__()
        self.image = img
        self.exhaust_img = exhaust_img
        self.rect = self.image.get_rect(centerx=SCREEN_W//2, bottom=SCREEN_H+20)
        self.vy = -180
        self.exhaust_t = 0.0
        self.bullets = pygame.sprite.Group()
        self.shoot_cooldown = 0.25
        self.cool = self.shoot_cooldown
        
    def update(self, dt):
        self.rect.y += self.vy * dt
        self.exhaust_t += dt
        self.cool -= dt
        
        if self.cool <= 0:
            self.bullets.add(MenuBullet(self.rect.centerx, self.rect.top, self.vy))
            self.cool = self.shoot_cooldown
            
        self.bullets.update(dt)

        if self.rect.bottom < 0:
            self.rect.y = SCREEN_H + 20
            self.bullets.empty()
            
    def draw(self, surface):
        surface.blit(self.image, self.rect)
        if self.exhaust_t > 0.05:
            self.exhaust_t = 0
        exhaust_rect = self.exhaust_img.get_rect(midtop=(self.rect.centerx, self.rect.bottom-12))
        surface.blit(self.exhaust_img, exhaust_rect)
        self.bullets.draw(surface)

def start_menu():
    global game_state
    
    menu_rect_w = 800
    menu_rect_h = 400
    menu_rect = pygame.Rect((SCREEN_W - menu_rect_w) / 2, (SCREEN_H - menu_rect_h) / 2, menu_rect_w, menu_rect_h)
    
    button_w = 300
    button_h = 80
    
    # Adjusted button position
    button_y = menu_rect.y + menu_rect_h - 180 
    button_rect = pygame.Rect((SCREEN_W - button_w) / 2, button_y, button_w, button_h)

    # Initialize the rocket animation
    rocket = PlayerRocket(player_img, player_exhaust_img)

    while game_state == "menu":
        dt = clock.tick(FPS) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if button_rect.collidepoint(event.pos):
                    game_state = "game"
                    return # Exit the menu loop

        # Update and draw background animation
        draw_menu_background()
        rocket.update(dt)
        rocket.draw(screen)

        # Draw menu box on top of the animation
        draw_rounded_rect(screen, menu_rect, (30, 0, 60, 240), 20)
        pygame.draw.rect(screen, (139, 92, 246), menu_rect, 2, border_radius=20)
        
        # Title text
        title_text = font_menu_title.render("SPACE INVADERS", True, (139, 92, 246))
        title_text.set_alpha(180 + int(75 * abs(math.sin(pygame.time.get_ticks()/1000)))) # pulsing alpha
        title_rect = title_text.get_rect(center=(SCREEN_W // 2, menu_rect.top + 80))
        screen.blit(title_text, title_rect)

        sub_text = font_menu_sub.render("Defend Earth from the alien invasion!", True, (167, 139, 250))
        sub_rect = sub_text.get_rect(center=(SCREEN_W // 2, menu_rect.top + 130))
        screen.blit(sub_text, sub_rect)
        
        # Draw Start Button with gradient-like effect
        mouse_pos = pygame.mouse.get_pos()
        hover_color = (139, 92, 246)
        normal_color = (59, 130, 246)
        button_color = hover_color if button_rect.collidepoint(mouse_pos) else normal_color
        
        draw_rounded_rect(screen, button_rect, button_color, 10)
        
        button_text = font_menu_button.render("START GAME", True, (255, 255, 255))
        button_text_rect = button_text.get_rect(center=button_rect.center)
        screen.blit(button_text, button_text_rect)
        
        controls_text = font_menu_sub.render("Use ← → arrows to move, SPACE to shoot", True, (167, 139, 250))
        controls_rect = controls_text.get_rect(center=(SCREEN_W // 2, menu_rect.bottom - 40))
        screen.blit(controls_text, controls_rect)

        pygame.display.flip()

# ---------------- GAME STATE ----------------
game_state = "menu" # Initial state: "menu", "game", "game_over"
paused = False

# ---------------- MAIN LOOP ----------------
running = True
while running:
    dt = clock.tick(FPS) / 1000.0

    if game_state == "menu":
        start_menu()
        continue
    
    shoot_pressed = False
    for event in pygame.event.get():
        if event.type == pygame.QUIT: running = False
        elif event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_p):
                paused = not paused
            elif game_state == "game" and not paused and event.key in (pygame.K_SPACE, pygame.K_w, pygame.K_UP):
                shoot_pressed = True
            elif game_state == "game_over" and event.key == pygame.K_r:
                game_state = "menu"
                # Reset game variables
                for g in (enemy_group, bullet_group, effects_group, particles_group, powerups_group, asteroid_group):
                    for s in g: s.kill()
                player.lives = 5
                player.score = 0
                player.target_score = 0
                player.inv = player.flash = player.rapid = player.shield = 0
                wave = 1
                wave_cooldown = 2.0
                wave_active = False

    if paused:
        screen.blit(bg_base, (0,0))
        ptxt = font_big.render("PAUSED", True, (240,240,255))
        screen.blit(ptxt, (SCREEN_W//2 - ptxt.get_width()//2, SCREEN_H//2 - 40))
        pygame.display.flip()
        continue

    if game_state == "game_over":
        screen.blit(bg_base, (0,0))
        screen.blit(vignette, (0,0))
        gtxt = font_big.render("GAME OVER", True, (255,80,80))
        stxt = font_md.render("Press R to Restart", True, (235,240,255))
        ftxt = font_md.render(f"Final Score: {player.score:,}", True, (235,240,255))
        
        # New "How to Play" section
        how_to_play_title = font_md.render("How to Play:", True, (255, 255, 255))
        how_to_play_text1 = font_sm.render("• Use ← and → arrows to move.", True, (200, 200, 220))
        how_to_play_text2 = font_sm.render("• Press SPACE to shoot.", True, (200, 200, 220))
        how_to_play_text3 = font_sm.render("• Press ESC or P to pause.", True, (200, 200, 220))
        how_to_play_text4 = font_sm.render("• Power-ups: Heal (green), Rapid Fire (blue), Shield (yellow).", True, (200, 200, 220))

        gtxt_rect = gtxt.get_rect(center=(SCREEN_W//2, SCREEN_H//2 - 120))
        ftxt_rect = ftxt.get_rect(center=(SCREEN_W//2, SCREEN_H//2 - 60))
        stxt_rect = stxt.get_rect(center=(SCREEN_W//2, SCREEN_H//2 - 20))
        
        htp_title_rect = how_to_play_title.get_rect(center=(SCREEN_W//2, SCREEN_H//2 + 40))
        htp_text1_rect = how_to_play_text1.get_rect(center=(SCREEN_W//2, SCREEN_H//2 + 80))
        htp_text2_rect = how_to_play_text2.get_rect(center=(SCREEN_W//2, SCREEN_H//2 + 105))
        htp_text3_rect = how_to_play_text3.get_rect(center=(SCREEN_W//2, SCREEN_H//2 + 130))
        htp_text4_rect = how_to_play_text4.get_rect(center=(SCREEN_W//2, SCREEN_H//2 + 155))
        
        screen.blit(gtxt, gtxt_rect)
        screen.blit(ftxt, ftxt_rect)
        screen.blit(stxt, stxt_rect)
        screen.blit(how_to_play_title, htp_title_rect)
        screen.blit(how_to_play_text1, htp_text1_rect)
        screen.blit(how_to_play_text2, htp_text2_rect)
        screen.blit(how_to_play_text3, htp_text3_rect)
        screen.blit(how_to_play_text4, htp_text4_rect)

        pygame.display.flip()
        continue

    p1 = (p1 - 18*dt) % SCREEN_W
    p2 = (p2 - 45*dt) % SCREEN_W

    keys = pygame.key.get_pressed()
    player.update(dt, keys)
    if shoot_pressed:
        player.shoot(bullet_group)

    if not wave_active:
        wave_cooldown -= dt
        if wave_cooldown <= 0:
            for e in list(enemy_group): e.kill()
            for b in list(bullet_group): b.kill()
            
            spawn_wave(min(6 + wave, 22), wave)
            wave_active = True
            wave_cooldown = 0

    if wave_active:
        for e in list(enemy_group):
            e.update(dt)
            e.try_shoot(dt, bullet_group)
    
    for b in list(bullet_group):
        b.update(dt)

    effects_group.update(dt)
    particles_group.update(dt)
    powerups_group.update(dt)
    asteroid_group.update(dt)

    for b in [x for x in bullet_group if x.friendly]:
        if wave_active:
            hits = [e for e in enemy_group if e.alive and e.rect.colliderect(b.rect)]
            if hits:
                b.kill()
                for e in hits:
                    e.explode(effects_group, particles_group)
                    enemy_group.remove(e)
                    player.target_score += e.score_val
                    if random.random() < 0.16:
                        p = PowerUp(e.rect.center)
                        powerups_group.add(p)
                if hit_snd: hit_snd.play()
        for a in list(asteroid_group):
            if a.rect.colliderect(b.rect):
                b.kill()
                a.kill()
                player.target_score += 10
                break

    for b in [x for x in bullet_group if not x.friendly]:
        if player.rect.colliderect(b.rect):
            b.kill()
            if player.hit():
                game_state = "game_over"
                break

    for a in list(asteroid_group):
        if player.rect.colliderect(a.rect):
            a.kill()
            if player.hit():
                game_state = "game_over"
                break

    for p in list(powerups_group):
        if player.rect.colliderect(p.rect):
            apply_powerup(player, p.type)
            p.kill()

    if wave_active and not enemy_group:
        wave += 1
        wave_active = False
        wave_cooldown = 3.0
        for b in list(bullet_group):
            if b.friendly: b.kill()

    shake.update(dt)
    ox, oy = shake.offset()

    screen.blit(bg_base, (ox//3, oy//3))
    s1 = bg_layer1; s2 = bg_layer2
    screen.blit(s1, (-p1 + ox, 0+oy)); screen.blit(s1, (-p1 + SCREEN_W + ox, 0+oy))
    screen.blit(s2.copy(), (-p2 + ox, 0+oy)); screen.blit(s2.copy(), (-p2 + SCREEN_W + ox, 0+oy))

    for a in asteroid_group:
        screen.blit(a.image, a.rect.move(ox, oy))

    if wave_active:
        for e in enemy_group:
            screen.blit(e.image, e.rect.move(ox, oy))
    for b in bullet_group:
        screen.blit(b.image, b.rect.move(ox, oy))
    for fx in effects_group:
        screen.blit(fx.image, fx.rect.move(ox, oy))
    for pr in particles_group:
        screen.blit(pr.image, pr.rect.move(ox, oy))
    for p in powerups_group:
        glow = pygame.Surface((p.rect.width+18, p.rect.height+18), pygame.SRCALPHA)
        pygame.draw.ellipse(glow, (240,240,255,70), glow.get_rect())
        screen.blit(glow, glow.get_rect(center=p.rect.center).move(ox, oy))
        screen.blit(p.image, p.rect.move(ox, oy))

    if player.shield > 0:
        glow = pygame.Surface((player.rect.width+24, player.rect.height+24), pygame.SRCALPHA)
        pygame.draw.ellipse(glow, (130,200,255,85), glow.get_rect())
        screen.blit(glow, glow.get_rect(center=player.rect.center).move(ox, oy))

    # --- Player Ship Polish Drawing ---
    
    # 1. Engine Trails with Afterburners
    engine_color = (255, 120, 0) if player.is_shooting else (120, 200, 255)
    
    if player.engine_t > 0.05:
        player.engine_t = 0
        particles_group.add(Particle(
            pos=player.rect.midbottom,
            color=engine_color,
            life=0.2,
            gravity=0,
            velocity_range=(-30, 30, 100, 150)
        ))
        
    # 2. Subtle Hull Lighting/Reflections
    glow_alpha = 30 + 20 * abs(math.sin(pygame.time.get_ticks() / 600))
    glow_surf = pygame.Surface(player.image.get_size(), pygame.SRCALPHA)
    pygame.draw.circle(glow_surf, (200, 220, 255, glow_alpha), (player.image.get_width()//2, player.image.get_height()//2), player.image.get_width()//2-10)
    screen.blit(glow_surf, player.rect.move(ox,oy))

    # 3. Damage Indicators (Sparks)
    if player.damage_spark_timer > 0:
        if random.random() < 0.35:  
            spark_pos = (
                player.rect.x + random.randint(0, player.rect.width),
                player.rect.y + random.randint(0, player.rect.height)
            )
            particles_group.add(Particle(
                pos=spark_pos,
                color=(255, 255, 255),
                life=0.15,
                gravity=100,
                velocity_range=(-200, 200, -200, -20)
            ))

    screen.blit(player.image, player.rect.move(ox, oy))
    draw_hud(screen, player, wave)
    screen.blit(vignette, (0,0))
    
    if not wave_active:
        wave_text = font_big.render(f"WAVE {wave}", True, (255, 255, 255))
        wave_rect = wave_text.get_rect(center=(SCREEN_W//2, SCREEN_H//2))
        screen.blit(wave_text, wave_rect)

    pygame.display.flip()

pygame.quit()
sys.exit()