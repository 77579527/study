"""
贪吃蛇小游戏 - 优化版
"""
import pygame, random, sys, json, os, math
from enum import Enum
from dataclasses import dataclass
from typing import List, Tuple, Optional

WINDOW_WIDTH = 900
WINDOW_HEIGHT = 700
GRID_SIZE = 20
GRID_WIDTH = WINDOW_WIDTH // GRID_SIZE
GRID_HEIGHT = (WINDOW_HEIGHT - 100) // GRID_SIZE
GAME_AREA_TOP = 100
GAME_AREA_HEIGHT = GRID_HEIGHT * GRID_SIZE
GAME_AREA_BOTTOM = GAME_AREA_TOP + GAME_AREA_HEIGHT

COLORS = {
    'bg': (15, 15, 25), 'grid': (30, 30, 45), 'panel_bg': (20, 20, 35),
    'panel_border': (60, 60, 90), 'text_primary': (230, 230, 240),
    'text_secondary': (160, 160, 180), 'text_accent': (100, 220, 100),
    'text_warning': (255, 180, 60), 'text_danger': (255, 80, 80),
    'snake_head': (40, 220, 80), 'snake_tail': (30, 160, 60),
    'snake_border': (20, 120, 40), 'food_normal': (230, 60, 60),
    'food_golden': (255, 215, 0), 'food_slow': (60, 140, 255),
    'food_speed': (200, 60, 255), 'food_border': (255, 255, 255),
    'particle': (255, 200, 50), 'btn_normal': (50, 50, 80),
    'btn_hover': (80, 80, 120), 'btn_pressed': (100, 100, 150),
    'btn_text': (230, 230, 240),
}

UP = (0, -1); DOWN = (0, 1); LEFT = (-1, 0); RIGHT = (1, 0)
DIRECTIONS = [UP, DOWN, LEFT, RIGHT]
DIR_KEYS = {
    pygame.K_UP: UP, pygame.K_w: UP, pygame.K_DOWN: DOWN, pygame.K_s: DOWN,
    pygame.K_LEFT: LEFT, pygame.K_a: LEFT, pygame.K_RIGHT: RIGHT, pygame.K_d: RIGHT,
}
OPPOSITE = {UP: DOWN, DOWN: UP, LEFT: RIGHT, RIGHT: LEFT}

class GameState(Enum):
    MENU = "menu"; PLAYING = "playing"; PAUSED = "paused"
    GAME_OVER = "game_over"; SETTINGS = "settings"

class FoodType(Enum):
    NORMAL = "normal"; GOLDEN = "golden"; SLOW = "slow"; SPEED = "speed"

FOOD_PROBABILITIES = [
    (FoodType.NORMAL, 0.70), (FoodType.GOLDEN, 0.10),
    (FoodType.SLOW, 0.10), (FoodType.SPEED, 0.10),
]

HIGHSCORE_FILE = os.path.join(os.path.dirname(__file__), "highscore.json")

def lerp_color(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))

def draw_rounded_rect(surface, color, rect, radius, border=0, border_color=None):
    if radius <= 0:
        pygame.draw.rect(surface, color, rect, border)
        if border_color and border > 0:
            pygame.draw.rect(surface, border_color, rect, border)
        return
    temp_surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    temp_rect = pygame.Rect(0, 0, rect.width, rect.height)
    pygame.draw.rect(temp_surf, color, temp_rect, border_radius=radius)
    if border_color and border > 0:
        pygame.draw.rect(temp_surf, border_color, temp_rect, border, border_radius=radius)
    surface.blit(temp_surf, rect.topleft)

def load_highscore():
    try:
        if os.path.exists(HIGHSCORE_FILE):
            with open(HIGHSCORE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f).get('highscore', 0)
    except: pass
    return 0

def save_highscore(score):
    try:
        with open(HIGHSCORE_FILE, 'w', encoding='utf-8') as f:
            json.dump({'highscore': score}, f)
    except: pass
@dataclass
class Particle:
    x: float; y: float; vx: float; vy: float
    life: float; max_life: float
    color: Tuple[int, int, int]; size: float

class ParticleSystem:
    def __init__(self):
        self.particles: List[Particle] = []
    
    def emit(self, x, y, count=12, color=None, speed_range=(1.5, 4.0), 
             life_range=(0.4, 0.8), size_range=(3.0, 6.0)):
        if color is None: color = COLORS['particle']
        for _ in range(count):
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(*speed_range)
            self.particles.append(Particle(
                x=x, y=y, vx=math.cos(angle) * speed, vy=math.sin(angle) * speed,
                life=random.uniform(*life_range), max_life=0, color=color,
                size=random.uniform(*size_range)
            ))
        for p in self.particles[-count:]:
            p.max_life = p.life
    
    def update(self, dt):
        for p in self.particles[:]:
            p.x += p.vx * dt * 60
            p.y += p.vy * dt * 60
            p.vy += 0.15 * dt * 60
            p.life -= dt
            if p.life <= 0: self.particles.remove(p)
    
    def render(self, surface):
        for p in self.particles:
            alpha = int(255 * (p.life / p.max_life))
            size = int(p.size * (p.life / p.max_life))
            if size > 0:
                temp_surf = pygame.Surface((size * 2, size * 2), pygame.SRCALPHA)
                pygame.draw.circle(temp_surf, (*p.color, alpha), (size, size), size)
                surface.blit(temp_surf, (p.x - size, p.y - size))

class Snake:
    def __init__(self): self.reset()
    
    def reset(self):
        start_x = (GRID_WIDTH // 2) * GRID_SIZE
        start_y = GAME_AREA_TOP + (GRID_HEIGHT // 2) * GRID_SIZE
        self.positions = [(start_x, start_y)]
        self.direction = random.choice(DIRECTIONS)
        self.next_direction = self.direction
        self.length = 3; self.grow_pending = 0
        self.alive = True; self.death_animation = 0.0
    
    def get_head(self): return self.positions[0]
    
    def set_direction(self, new_dir):
        if new_dir != OPPOSITE.get(self.direction, (0, 0)):
            self.next_direction = new_dir
    
    def update(self):
        if not self.alive:
            self.death_animation += 0.15; return
        self.direction = self.next_direction
        head_x, head_y = self.get_head()
        dx, dy = self.direction
        new_head = (head_x + dx * GRID_SIZE, head_y + dy * GRID_SIZE)
        if new_head[0] < 0: new_head = (WINDOW_WIDTH - GRID_SIZE, new_head[1])
        elif new_head[0] >= WINDOW_WIDTH: new_head = (0, new_head[1])
        if new_head[1] < GAME_AREA_TOP: new_head = (new_head[0], GAME_AREA_BOTTOM - GRID_SIZE)
        elif new_head[1] >= GAME_AREA_BOTTOM: new_head = (new_head[0], GAME_AREA_TOP)
        if new_head in self.positions:
            self.alive = False; self.death_animation = 0.0; return
        self.positions.insert(0, new_head)
        if self.grow_pending > 0:
            self.grow_pending -= 1; self.length += 1
        else: self.positions.pop()
    
    def grow(self, amount=1): self.grow_pending += amount
    
    def render(self, surface, dt):
        if not self.alive:
            alpha = int(255 * (0.5 + 0.5 * math.sin(self.death_animation * 20)))
            for pos in self.positions:
                temp_surf = pygame.Surface((GRID_SIZE, GRID_SIZE), pygame.SRCALPHA)
                pygame.draw.rect(temp_surf, (255, 60, 60, alpha), (0, 0, GRID_SIZE, GRID_SIZE), border_radius=6)
                surface.blit(temp_surf, pos)
            return
        for i, pos in enumerate(self.positions):
            t = i / max(1, len(self.positions) - 1)
            color = lerp_color(COLORS['snake_head'], COLORS['snake_tail'], t)
            rect = pygame.Rect(pos[0], pos[1], GRID_SIZE, GRID_SIZE)
            if i == 0:
                draw_rounded_rect(surface, color, rect, 8, 2, COLORS['snake_border'])
                self._draw_eyes(surface, pos)
            elif i == len(self.positions) - 1:
                draw_rounded_rect(surface, color, rect, 6, 1, COLORS['snake_border'])
            else:
                draw_rounded_rect(surface, color, rect, 5, 1, COLORS['snake_border'])
    
    def _draw_eyes(self, surface, pos):
        cx, cy = pos[0] + GRID_SIZE // 2, pos[1] + GRID_SIZE // 2
        eye_offset = GRID_SIZE // 3; eye_size = 4; pupil_size = 2
        if self.direction == UP:
            eye_positions = [(cx - eye_offset, cy - eye_offset), (cx + eye_offset, cy - eye_offset)]
            pupil_offset = (0, -1)
        elif self.direction == DOWN:
            eye_positions = [(cx - eye_offset, cy + eye_offset), (cx + eye_offset, cy + eye_offset)]
            pupil_offset = (0, 1)
        elif self.direction == LEFT:
            eye_positions = [(cx - eye_offset, cy - eye_offset), (cx - eye_offset, cy + eye_offset)]
            pupil_offset = (-1, 0)
        else:
            eye_positions = [(cx + eye_offset, cy - eye_offset), (cx + eye_offset, cy + eye_offset)]
            pupil_offset = (1, 0)
        for ex, ey in eye_positions:
            pygame.draw.circle(surface, (255, 255, 255), (ex, ey), eye_size)
            px, py = ex + pupil_offset[0] * 2, ey + pupil_offset[1] * 2
            pygame.draw.circle(surface, (20, 20, 20), (px, py), pupil_size)
class Food:
    def __init__(self, snake_positions):
        self.position = (0, 0)
        self.type = FoodType.NORMAL
        self.animation_time = 0.0
        self.pulse_scale = 1.0
        self.randomize(snake_positions)
    
    def randomize(self, snake_positions):
        rand = random.random()
        cumulative = 0.0
        for food_type, prob in FOOD_PROBABILITIES:
            cumulative += prob
            if rand <= cumulative:
                self.type = food_type
                break
        available = []
        for gx in range(GRID_WIDTH):
            for gy in range(GRID_HEIGHT):
                px = gx * GRID_SIZE
                py = GAME_AREA_TOP + gy * GRID_SIZE
                if (px, py) not in snake_positions:
                    available.append((px, py))
        if available: self.position = random.choice(available)
        else: self.position = (GRID_SIZE, GAME_AREA_TOP + GRID_SIZE)
        self.animation_time = 0.0
    
    def update(self, dt):
        self.animation_time += dt
        self.pulse_scale = 1.0 + 0.15 * math.sin(self.animation_time * 6)
        if self.type == FoodType.GOLDEN:
            self.pulse_scale = 1.0 + 0.2 * math.sin(self.animation_time * 8)
    
    def get_color(self):
        if self.type == FoodType.NORMAL: return COLORS['food_normal']
        elif self.type == FoodType.GOLDEN: return COLORS['food_golden']
        elif self.type == FoodType.SLOW: return COLORS['food_slow']
        elif self.type == FoodType.SPEED: return COLORS['food_speed']
        return COLORS['food_normal']
    
    def get_score_value(self):
        if self.type == FoodType.NORMAL: return 10
        elif self.type == FoodType.GOLDEN: return 50
        elif self.type == FoodType.SLOW: return 15
        elif self.type == FoodType.SPEED: return 15
        return 10
    
    def get_effect(self):
        if self.type == FoodType.SLOW: return ("slow", 3.0)
        elif self.type == FoodType.SPEED: return ("speed", 3.0)
        return ("none", 0.0)
    
    def render(self, surface):
        color = self.get_color()
        cx = self.position[0] + GRID_SIZE // 2
        cy = self.position[1] + GRID_SIZE // 2
        radius = int((GRID_SIZE // 2 - 2) * self.pulse_scale)
        if self.type == FoodType.GOLDEN:
            glow_radius = radius + 4
            glow_surf = pygame.Surface((glow_radius * 2, glow_radius * 2), pygame.SRCALPHA)
            for i in range(3):
                alpha = 60 - i * 15
                pygame.draw.circle(glow_surf, (*COLORS['food_golden'], alpha), 
                                 (glow_radius, glow_radius), glow_radius - i * 2)
            surface.blit(glow_surf, (cx - glow_radius, cy - glow_radius))
        pygame.draw.circle(surface, color, (cx, cy), radius)
        pygame.draw.circle(surface, COLORS['food_border'], (cx, cy), radius, 2)
        if self.type == FoodType.GOLDEN:
            self._draw_star(surface, cx, cy, radius // 2, COLORS['food_border'])
        elif self.type == FoodType.SLOW:
            self._draw_slow_symbol(surface, cx, cy, radius // 2)
        elif self.type == FoodType.SPEED:
            self._draw_speed_symbol(surface, cx, cy, radius // 2)
    
    def _draw_star(self, surface, cx, cy, size, color):
        points = []
        for i in range(5):
            angle = math.pi / 2 + i * 2 * math.pi / 5
            x = cx + math.cos(angle) * size; y = cy - math.sin(angle) * size
            points.append((x, y))
            angle += math.pi / 5
            x = cx + math.cos(angle) * (size // 2); y = cy - math.sin(angle) * (size // 2)
            points.append((x, y))
        pygame.draw.polygon(surface, color, points)
    
    def _draw_slow_symbol(self, surface, cx, cy, size):
        points = [(cx, cy + size), (cx - size // 2, cy - size // 3), (cx + size // 2, cy - size // 3)]
        pygame.draw.polygon(surface, COLORS['food_border'], points)
    
    def _draw_speed_symbol(self, surface, cx, cy, size):
        points = [(cx - size // 3, cy - size), (cx + size // 6, cy), (cx - size // 6, cy),
                  (cx + size // 3, cy + size), (cx - size // 6, cy), (cx + size // 6, cy)]
        pygame.draw.polygon(surface, COLORS['food_border'], points)

class Button:
    def __init__(self, rect, text, font, callback=None):
        self.rect = rect; self.text = text; self.font = font; self.callback = callback
        self.color_normal = COLORS['btn_normal']; self.color_hover = COLORS['btn_hover']
        self.color_pressed = COLORS['btn_pressed']; self.text_color = COLORS['btn_text']
        self.hovered = False; self.pressed = False
    
    def handle_event(self, event):
        if event.type == pygame.MOUSEMOTION:
            self.hovered = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.hovered: self.pressed = True
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.pressed and self.hovered and self.callback: self.callback()
            self.pressed = False
    
    def render(self, surface):
        color = self.color_pressed if self.pressed else (self.color_hover if self.hovered else self.color_normal)
        draw_rounded_rect(surface, color, self.rect, 8, 2, COLORS['panel_border'])
        text_surf = self.font.render(self.text, True, self.text_color)
        text_rect = text_surf.get_rect(center=self.rect.center)
        surface.blit(text_surf, text_rect)
class SnakeGame:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("贪吃蛇 Pro - 优化版")
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        self.clock = pygame.time.Clock()
        self.running = True
        
        self.font_large = pygame.font.Font(None, 56)
        self.font_medium = pygame.font.Font(None, 36)
        self.font_small = pygame.font.Font(None, 24)
        self.font_tiny = pygame.font.Font(None, 18)
        
        self.snake = Snake()
        self.food = Food(self.snake.positions)
        self.particles = ParticleSystem()
        
        self.state = GameState.MENU
        self.score = 0
        self.highscore = load_highscore()
        self.combo = 0
        self.last_food_time = 0
        
        self.base_fps = 10
        self.current_fps = self.base_fps
        self.speed_multiplier = 1.0
        self.speed_effect_timer = 0.0
        self.speed_effect_type = "none"
        
        self._create_menu_buttons()
        self.bg_particles = self._create_bg_particles()
    
    def _create_menu_buttons(self):
        btn_w, btn_h = 240, 56
        center_x = WINDOW_WIDTH // 2 - btn_w // 2
        start_y = WINDOW_HEIGHT // 2 - 40
        gap = 70
        
        self.menu_buttons = [
            Button(pygame.Rect(center_x, start_y, btn_w, btn_h), "开始游戏", self.font_medium,
                   lambda: self._start_game()),
            Button(pygame.Rect(center_x, start_y + gap, btn_w, btn_h), "设置", self.font_medium,
                   lambda: setattr(self, 'state', GameState.SETTINGS)),
            Button(pygame.Rect(center_x, start_y + 2 * gap, btn_w, btn_h), "退出", self.font_medium,
                   lambda: setattr(self, 'running', False)),
        ]
        
        self.gameover_buttons = [
            Button(pygame.Rect(center_x, start_y + 60, btn_w, btn_h), "再来一局", self.font_medium,
                   lambda: self._start_game()),
            Button(pygame.Rect(center_x, start_y + 60 + gap, btn_w, btn_h), "返回菜单", self.font_medium,
                   lambda: setattr(self, 'state', GameState.MENU)),
        ]
        
        self.pause_buttons = [
            Button(pygame.Rect(center_x, start_y, btn_w, btn_h), "继续", self.font_medium,
                   lambda: setattr(self, 'state', GameState.PLAYING)),
            Button(pygame.Rect(center_x, start_y + gap, btn_w, btn_h), "返回菜单", self.font_medium,
                   lambda: setattr(self, 'state', GameState.MENU)),
        ]
    
    def _create_bg_particles(self):
        particles = []
        for _ in range(30):
            particles.append({
                'x': random.uniform(0, WINDOW_WIDTH),
                'y': random.uniform(0, WINDOW_HEIGHT),
                'vx': random.uniform(-0.3, 0.3),
                'vy': random.uniform(-0.3, 0.3),
                'size': random.uniform(1, 3),
                'alpha': random.randint(20, 60),
                'color': random.choice([(100, 150, 255), (150, 100, 255), (100, 255, 150)])
            })
        return particles
    
    def _start_game(self):
        self.snake.reset()
        self.food = Food(self.snake.positions)
        self.particles = ParticleSystem()
        self.score = 0; self.combo = 0; self.last_food_time = 0
        self.current_fps = self.base_fps; self.speed_multiplier = 1.0
        self.speed_effect_timer = 0.0; self.speed_effect_type = "none"
        self.state = GameState.PLAYING
    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False; return
            
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if self.state == GameState.PLAYING: self.state = GameState.PAUSED
                    elif self.state == GameState.PAUSED: self.state = GameState.PLAYING
                    elif self.state in (GameState.GAME_OVER, GameState.SETTINGS): self.state = GameState.MENU
                    elif self.state == GameState.MENU: self.running = False
                    return
                
                if event.key == pygame.K_SPACE:
                    if self.state == GameState.PLAYING: self.state = GameState.PAUSED
                    elif self.state == GameState.PAUSED: self.state = GameState.PLAYING
                    return
                
                if event.key == pygame.K_r and self.state == GameState.GAME_OVER:
                    self._start_game(); return
                
                if self.state == GameState.PLAYING and event.key in DIR_KEYS:
                    self.snake.set_direction(DIR_KEYS[event.key])
            
            if self.state == GameState.MENU:
                for btn in self.menu_buttons: btn.handle_event(event)
            elif self.state == GameState.GAME_OVER:
                for btn in self.gameover_buttons: btn.handle_event(event)
            elif self.state == GameState.PAUSED:
                for btn in self.pause_buttons: btn.handle_event(event)
    
    def update(self, dt):
        for p in self.bg_particles:
            p['x'] += p['vx'] * dt * 60; p['y'] += p['vy'] * dt * 60
            if p['x'] < 0: p['x'] = WINDOW_WIDTH
            if p['x'] > WINDOW_WIDTH: p['x'] = 0
            if p['y'] < 0: p['y'] = WINDOW_HEIGHT
            if p['y'] > WINDOW_HEIGHT: p['y'] = 0
        
        if self.state != GameState.PLAYING:
            self.particles.update(dt); return
        
        if self.speed_effect_timer > 0:
            self.speed_effect_timer -= dt
            if self.speed_effect_timer <= 0:
                self.speed_effect_type = "none"
                self.speed_multiplier = 1.0
                self.current_fps = self.base_fps
        
        self.snake.update()
        
        if not self.snake.alive:
            self.state = GameState.GAME_OVER
            if self.score > self.highscore:
                self.highscore = self.score; save_highscore(self.highscore)
            return
        
        if self.snake.get_head() == self.food.position:
            food_score = self.food.get_score_value()
            current_time = pygame.time.get_ticks() / 1000
            if current_time - self.last_food_time < 2.0:
                self.combo += 1; food_score += self.combo * 5
            else: self.combo = 0
            self.last_food_time = current_time
            self.score += food_score
            
            head = self.snake.get_head()
            self.particles.emit(head[0] + GRID_SIZE // 2, head[1] + GRID_SIZE // 2,
                count=18, color=self.food.get_color(), speed_range=(2, 5),
                life_range=(0.5, 1.0), size_range=(4, 8))
            
            effect_type, duration = self.food.get_effect()
            if effect_type != "none":
                self.speed_effect_type = effect_type
                self.speed_effect_timer = duration
                if effect_type == "slow":
                    self.speed_multiplier = 0.5; self.current_fps = max(5, int(self.base_fps * 0.5))
                elif effect_type == "speed":
                    self.speed_multiplier = 1.8; self.current_fps = int(self.base_fps * 1.8)
            
            self.snake.grow(1 if self.food.type != FoodType.GOLDEN else 2)
            self.food = Food(self.snake.positions)
        
        target_fps = self.base_fps + (self.score // 50) * 1
        if self.speed_effect_type == "none":
            self.current_fps = min(25, target_fps)
        
        self.food.update(dt)
        self.particles.update(dt)
    
    def render(self):
        self.screen.fill(COLORS['bg'])
        
        for p in self.bg_particles:
            temp_surf = pygame.Surface((int(p['size'] * 2), int(p['size'] * 2)), pygame.SRCALPHA)
            pygame.draw.circle(temp_surf, (*p['color'], p['alpha']), 
                             (int(p['size']), int(p['size'])), int(p['size']))
            self.screen.blit(temp_surf, (int(p['x']), int(p['y'])))
        
        game_rect = pygame.Rect(0, GAME_AREA_TOP, WINDOW_WIDTH, GAME_AREA_HEIGHT)
        pygame.draw.rect(self.screen, (10, 10, 20), game_rect)
        self._draw_grid()
        
        if self.state == GameState.MENU: self._render_menu()
        elif self.state == GameState.PLAYING: self._render_game()
        elif self.state == GameState.PAUSED:
            self._render_game(); self._render_pause_overlay()
        elif self.state == GameState.GAME_OVER:
            self._render_game(); self._render_game_over()
        elif self.state == GameState.SETTINGS: self._render_settings()
        
        pygame.display.flip()
    
    def _draw_grid(self):
        for x in range(0, WINDOW_WIDTH, GRID_SIZE):
            pygame.draw.line(self.screen, COLORS['grid'], (x, GAME_AREA_TOP), (x, GAME_AREA_BOTTOM), 1)
        for y in range(GAME_AREA_TOP, GAME_AREA_BOTTOM, GRID_SIZE):
            pygame.draw.line(self.screen, COLORS['grid'], (0, y), (WINDOW_WIDTH, y), 1)
    def _render_game(self):
        self._render_top_panel()
        self.food.render(self.screen)
        dt = self.clock.get_time() / 1000
        self.snake.render(self.screen, dt)
        self.particles.render(self.screen)
        if self.speed_effect_type != "none": self._render_speed_indicator()
    
    def _render_top_panel(self):
        panel_rect = pygame.Rect(0, 0, WINDOW_WIDTH, GAME_AREA_TOP)
        draw_rounded_rect(self.screen, COLORS['panel_bg'], panel_rect, 0, 2, COLORS['panel_border'])
        
        score_text = self.font_large.render(f"分数: {self.score}", True, COLORS['text_primary'])
        self.screen.blit(score_text, (30, 20))
        
        hs_text = self.font_medium.render(f"最高分: {self.highscore}", True, COLORS['text_accent'])
        self.screen.blit(hs_text, (30, 60))
        
        len_text = self.font_medium.render(f"长度: {len(self.snake.positions)}", True, COLORS['text_secondary'])
        self.screen.blit(len_text, (250, 30))
        
        speed_text = self.font_medium.render(f"速度: {self.current_fps} FPS", True, COLORS['text_secondary'])
        self.screen.blit(speed_text, (250, 60))
        
        if self.combo > 0:
            combo_text = self.font_medium.render(f"连击 x{self.combo}!", True, COLORS['text_warning'])
            self.screen.blit(combo_text, (480, 30))
        
        hint_text = self.font_tiny.render("方向键/WASD 移动  |  空格暂停  |  ESC 菜单", True, COLORS['text_secondary'])
        hint_rect = hint_text.get_rect(right=WINDOW_WIDTH - 20, bottom=GAME_AREA_TOP - 10)
        self.screen.blit(hint_text, hint_rect)
    
    def _render_speed_indicator(self):
        indicator_w, indicator_h = 180, 40
        x = WINDOW_WIDTH - indicator_w - 20
        y = GAME_AREA_TOP + 20
        rect = pygame.Rect(x, y, indicator_w, indicator_h)
        
        if self.speed_effect_type == "slow":
            color = COLORS['food_slow']; text = "减速中..."
        else:
            color = COLORS['food_speed']; text = "加速中!"
        
        draw_rounded_rect(self.screen, (*color, 180), rect, 10, 2, color)
        progress = self.speed_effect_timer / 3.0
        bar_rect = pygame.Rect(x + 10, y + 10, int((indicator_w - 20) * progress), 20)
        draw_rounded_rect(self.screen, color, bar_rect, 5)
        
        text_surf = self.font_small.render(text, True, COLORS['text_primary'])
        text_rect = text_surf.get_rect(center=rect.center)
        self.screen.blit(text_surf, text_rect)
    
    def _render_menu(self):
        title = self.font_large.render("贪吃蛇 Pro", True, COLORS['text_primary'])
        title_rect = title.get_rect(center=(WINDOW_WIDTH // 2, 150))
        self.screen.blit(title, title_rect)
        
        subtitle = self.font_medium.render("优化版 - 粒子特效 · 特殊食物 · 连击系统", True, COLORS['text_secondary'])
        sub_rect = subtitle.get_rect(center=(WINDOW_WIDTH // 2, 210))
        self.screen.blit(subtitle, sub_rect)
        
        hs_text = self.font_medium.render(f"历史最高分: {self.highscore}", True, COLORS['text_accent'])
        hs_rect = hs_text.get_rect(center=(WINDOW_WIDTH // 2, 270))
        self.screen.blit(hs_text, hs_rect)
        
        for btn in self.menu_buttons: btn.render(self.screen)
        
        hint = self.font_small.render("方向键/WASD 控制移动  |  空格暂停  |  ESC 退出", True, COLORS['text_secondary'])
        hint_rect = hint.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT - 40))
        self.screen.blit(hint, hint_rect)
    
    def _render_pause_overlay(self):
        overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180)); self.screen.blit(overlay, (0, 0))
        
        pause_text = self.font_large.render("游戏暂停", True, COLORS['text_warning'])
        pause_rect = pause_text.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 - 80))
        self.screen.blit(pause_text, pause_rect)
        
        for btn in self.pause_buttons: btn.render(self.screen)
    
    def _render_game_over(self):
        overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 200)); self.screen.blit(overlay, (0, 0))
        
        panel_w, panel_h = 400, 320
        panel_x = WINDOW_WIDTH // 2 - panel_w // 2
        panel_y = WINDOW_HEIGHT // 2 - panel_h // 2
        panel_rect = pygame.Rect(panel_x, panel_y, panel_w, panel_h)
        draw_rounded_rect(self.screen, COLORS['panel_bg'], panel_rect, 16, 3, COLORS['panel_border'])
        
        title = self.font_large.render("游戏结束", True, COLORS['text_danger'])
        title_rect = title.get_rect(center=(WINDOW_WIDTH // 2, panel_y + 60))
        self.screen.blit(title, title_rect)
        
        score_text = self.font_medium.render(f"最终分数: {self.score}", True, COLORS['text_primary'])
        score_rect = score_text.get_rect(center=(WINDOW_WIDTH // 2, panel_y + 130))
        self.screen.blit(score_text, score_rect)
        
        hs_color = COLORS['text_accent'] if self.score >= self.highscore else COLORS['text_secondary']
        hs_text = self.font_medium.render(f"最高分: {self.highscore}", True, hs_color)
        hs_rect = hs_text.get_rect(center=(WINDOW_WIDTH // 2, panel_y + 180))
        self.screen.blit(hs_text, hs_rect)
        
        if self.score >= self.highscore and self.score > 0:
            new_record = self.font_small.render("★ 新纪录! ★", True, COLORS['food_golden'])
            nr_rect = new_record.get_rect(center=(WINDOW_WIDTH // 2, panel_y + 215))
            self.screen.blit(new_record, nr_rect)
        
        for btn in self.gameover_buttons: btn.render(self.screen)
    
    def _render_settings(self):
        title = self.font_large.render("设置", True, COLORS['text_primary'])
        title_rect = title.get_rect(center=(WINDOW_WIDTH // 2, 100))
        self.screen.blit(title, title_rect)
        
        back_btn = Button(pygame.Rect(50, 50, 120, 40), "返回", self.font_medium,
                          lambda: setattr(self, 'state', GameState.MENU))
        back_btn.render(self.screen)
        
        settings = [
            f"基础速度: {self.base_fps} FPS", "穿墙模式: 开启",
            "连击奖励: 开启", "粒子特效: 开启",
        ]
        for i, s in enumerate(settings):
            text = self.font_medium.render(s, True, COLORS['text_secondary'])
            self.screen.blit(text, (WINDOW_WIDTH // 2 - 150, 200 + i * 50))
    
    def run(self):
        while self.running:
            dt = self.clock.tick(60) / 1000
            self.handle_events()
            self.update(dt)
            self.render()
            if self.state == GameState.PLAYING:
                pygame.time.delay(max(0, int(1000 / self.current_fps) - self.clock.get_time()))
        pygame.quit(); sys.exit()

if __name__ == '__main__':
    try:
        game = SnakeGame()
        game.run()
    except Exception as e:
        print(f"游戏错误: {e}")
        import traceback; traceback.print_exc()
        pygame.quit(); sys.exit(1)