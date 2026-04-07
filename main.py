import pygame
import sys
import os
import random
import math
import asyncio
from typing import List, Optional

import constants
from enums import FoodType, HorseState, PlayerState, CropState
from entities import Player, Horse, Crop, AppleTree, Poop
from assets_loader import AssetsLoader
from sound_manager import SoundManager

class Game:
    def __init__(self):
        pygame.init()
        self.sound_manager = SoundManager()  # SoundManager'ı en başta oluştur
        self.screen = pygame.display.set_mode((constants.SCREEN_WIDTH, constants.SCREEN_HEIGHT))
        pygame.display.set_caption("Feed the Herd")
        self.clock = pygame.time.Clock()
        self.font_small = pygame.font.SysFont("Arial", 20, bold=True)
        self.font_large = pygame.font.SysFont("Arial", 40, bold=True)
        self.version = "v1.9.0"
        self.game_state = "LOADING"
        self.mixer_initialized = False # We stay silent
        self._loading_done = False
        self._loading_frame = 0
        self._bg_cache = None  # Cached background surface
        self._font_cache = {}  # Font render cache
        self._notif_bg_cache = None  # Notification bg cache

        # Manuel tuş tracking (Edge WASM'da get_pressed() güvenilir değil)
        self._held_keys = set()

        # Instruction ekranı kontrolü
        self.show_instructions = True
        self.instructions_text = self._load_instructions()
        self.instructions_scroll = 0  # Talimat ekranı için scroll offset
        self._touch_last_y = None  # Touch/finger scroll tracking

        # Assets
        self.loader = AssetsLoader(os.path.join(os.getcwd(), "assets"))
        self.sprites = self.loader.load_all()

        # Entities
        self.player = Player()
        self.horses: List[Horse] = []
        self.crops: List[Crop] = []
        self.apple_trees: List[AppleTree] = []
        self.poops: List[Poop] = []

        # Level system
        self.level = 1
        self.score = 0
        self.level_up_timer = 0.0 # Legacy level up msg
        self.notification_timer = 0.0
        self.notification_msg = ""
        self.step_timer = 0.0
        self.unlocked_notifs = {3: False, 5: False}

        # Shop
        self.shop_open = False
        self.game_over = False

        # On-screen UI buttons for mouse/touch
        self._init_ui_buttons()

        # Tutorial (otomatik demo) kontrolü
        self.tutorial_active = True
        self.tutorial_phase = "intro"  # intro -> playing -> outro
        self.tutorial_step = 0
        self.tutorial_wait = 0.0
        self.tutorial_feed_count = 0
        # Otomatik demo adımları
        self.tutorial_steps = [
            {"target": (constants.STORAGE_X, constants.STORAGE_Y), "action": "move", "msg": "Markete gidiyorum..."},
            {"target": None, "action": "buy_seeds", "msg": "Havuç tohumu alıyorum!"},
            {"target": (160, 180), "action": "move", "msg": "Tarlaya gidiyorum..."},
            {"target": None, "action": "plant_all", "msg": "Havuçları ekiyorum!"},
            {"target": None, "action": "wait_grow_all", "msg": "Havuçlar büyüyor... Bekle..."},
            {"target": "crop", "action": "move", "msg": "Olgunlaşan havucu topluyorum!"},
            {"target": None, "action": "harvest_one", "msg": "Topladım!"},
            {"target": "horse", "action": "move", "msg": "Atın yanına gidiyorum..."},
            {"target": None, "action": "feed", "msg": "Atı besliyorum!"},
            {"target": "crop", "action": "move", "msg": "Diğer havucu toplamaya gidiyorum..."},
            {"target": None, "action": "harvest_one", "msg": "Topluyorum!"},
            {"target": "horse", "action": "move", "msg": "Atı tekrar beslemeye gidiyorum..."},
            {"target": None, "action": "feed", "msg": "Atı yine besliyorum!"},
            {"target": "poop", "action": "move", "msg": "Gübre düştü! Toplayayım..."},
            {"target": None, "action": "collect_poop", "msg": "Gübreyi topluyorum!"},
            {"target": (constants.STORAGE_X, constants.STORAGE_Y), "action": "move", "msg": "Markete götürüp satıyorum..."},
            {"target": None, "action": "sell_poop", "msg": "Gübreyi sattım, para kazandım!"},
            {"target": None, "action": "done", "msg": ""},
        ]

        self.reset_game()

    def _load_instructions(self):
        # INSTRUCTIONS.md dosyasını oku
        for path in [
            os.path.join(os.path.dirname(__file__), 'INSTRUCTIONS.md'),
            os.path.join(os.path.dirname(__file__), '../INSTRUCTIONS.md'),
            'INSTRUCTIONS.md',
        ]:
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return f.read()
            except Exception:
                continue
        return "Talimatlar yüklenemedi."
    
    def _init_ui_buttons(self):
        """Ekrandaki dokunmatik/mouse butonları"""
        btn_size = 56
        btn_gap = 10
        # Sağ alt köşede yön tuşları (D-pad)
        dpad_x = constants.SCREEN_WIDTH - 180
        dpad_y = constants.SCREEN_HEIGHT - 180
        self.btn_up = pygame.Rect(dpad_x + btn_size + btn_gap, dpad_y, btn_size, btn_size)
        self.btn_down = pygame.Rect(dpad_x + btn_size + btn_gap, dpad_y + 2*(btn_size + btn_gap), btn_size, btn_size)
        self.btn_left = pygame.Rect(dpad_x, dpad_y + btn_size + btn_gap, btn_size, btn_size)
        self.btn_right = pygame.Rect(dpad_x + 2*(btn_size + btn_gap), dpad_y + btn_size + btn_gap, btn_size, btn_size)

        # Sol alt köşede aksiyon butonları
        action_x = 20
        action_y = constants.SCREEN_HEIGHT - 110
        self.btn_action_e = pygame.Rect(action_x, action_y, 80, 44)
        self.btn_action_space = pygame.Rect(action_x + 90, action_y, 100, 44)
        
        # Sanal tuş durumları (mouse/touch basılı tutma)
        self.virtual_keys = {
            'up': False, 'down': False, 'left': False, 'right': False
        }

    def _get_button_at(self, pos):
        """Verilen pozisyondaki butonu döndür"""
        x, y = pos
        if self.btn_up.collidepoint(x, y): return 'up'
        if self.btn_down.collidepoint(x, y): return 'down'
        if self.btn_left.collidepoint(x, y): return 'left'
        if self.btn_right.collidepoint(x, y): return 'right'
        if self.btn_action_e.collidepoint(x, y): return 'action_e'
        if self.btn_action_space.collidepoint(x, y): return 'action_space'
        return None

    def reset_game(self):
        self.level = 1
        self.score = 0
        self.level_up_timer = 0.0
        self.notification_timer = 0.0
        self.notification_msg = ""
        self.unlocked_notifs = {3: False, 5: False}
        self.game_over = False
        self.game_state = "PLAYING"
        self.step_timer = 0.0
        
        # Reset Entities
        self.player = Player()
        self.crops = []
        self.apple_trees = []
        self.poops = []
        self._spawn_initial_horses()

    def _spawn_initial_horses(self):
        # Center horses vertically in the right column
        right_center_x = constants.HORSES_START + (constants.SCREEN_WIDTH - constants.HORSES_START) // 2
        self.horses = []
        for i in range(3):
            h = Horse(i, self.level)
            h.x = right_center_x
            h.y = 180 + i * 200 # Balanced vertical spacing
            self.horses.append(h)

    def _draw_text(self, text, pos, color, font):
        # Cached font rendering for performance
        cache_key = (text, color, id(font))
        cached = self._font_cache.get(cache_key)
        if cached is None:
            if isinstance(color, tuple) and len(color) == 4:
                surf = font.render(text, True, color[:3])
                surf.set_alpha(color[3])
            else:
                surf = font.render(text, True, color)
            if len(self._font_cache) > 200:
                self._font_cache.clear()
            self._font_cache[cache_key] = surf
            cached = surf
        self.screen.blit(cached, pos)

    def _draw_centered_text(self, text, y, color, font):
        cache_key = (text, color, id(font), 'centered')
        cached = self._font_cache.get(cache_key)
        if cached is None:
            cached = font.render(text, True, color)
            if len(self._font_cache) > 200:
                self._font_cache.clear()
            self._font_cache[cache_key] = cached
        rect = cached.get_rect(center=(constants.SCREEN_WIDTH//2, y))
        self.screen.blit(cached, rect)

    def _build_bg_cache(self):
        """Arka planı bir kez çiz, cache'le. Her frame'de 80+ blit yerine 1 blit."""
        self._bg_cache = pygame.Surface((constants.SCREEN_WIDTH, constants.SCREEN_HEIGHT))
        # Grass tiles
        for x in range(0, constants.SCREEN_WIDTH, 100):
            for y in range(0, constants.SCREEN_HEIGHT, 100):
                self._bg_cache.blit(self.sprites['bg_farm_bottom'], (x, y))
        # Carrot field
        carrot_field_surf = pygame.Surface((constants.FARM_END, constants.FARM_MID_Y), pygame.SRCALPHA)
        carrot_field_surf.blit(self.sprites['bg_farm_top'], (0, 0))
        mask = pygame.Surface((constants.FARM_END, constants.FARM_MID_Y), pygame.SRCALPHA)
        pygame.draw.rect(mask, (255, 255, 255, 255), (0, 0, constants.FARM_END, constants.FARM_MID_Y),
                         border_top_right_radius=50, border_bottom_right_radius=50)
        carrot_field_surf.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        self._bg_cache.blit(carrot_field_surf, (0, 0))

    async def run(self):
        while True:
            raw_dt = self.clock.tick(60) / 1000.0
            # Edge WASM'da FPS düşük olabilir (10-20 FPS)
            # dt'yi 0.1'e cap'le ama hareketi yeterli tut
            dt = min(raw_dt, 0.1)
            self._handle_events()
            
            # _held_keys fallback: event kaçırılırsa bir sonraki frame yakalar
            if pygame.K_SPACE in self._held_keys:
                if self.show_instructions:
                    self.show_instructions = False
                    self.reset_game()
                    self.tutorial_active = True
                    self._held_keys.discard(pygame.K_SPACE)
                elif self.tutorial_active:
                    if self.tutorial_phase == "intro":
                        self.tutorial_phase = "playing"
                        self.tutorial_step = 0
                        self.tutorial_wait = 0.0
                        self.tutorial_feed_count = 0
                        self.reset_game()
                        self.sound_manager.start_music()
                        self._held_keys.discard(pygame.K_SPACE)
                    elif self.tutorial_phase == "outro":
                        self.tutorial_active = False
                        self.sound_manager.stop_music()
                        self.reset_game()
                        self.sound_manager.start_music()
                        self._held_keys.discard(pygame.K_SPACE)
            
            if self.show_instructions:
                self._draw_instructions()
            elif self.tutorial_active:
                if self.tutorial_phase == "intro":
                    self._draw_tutorial_intro()
                elif self.tutorial_phase == "playing":
                    self._update_tutorial(dt)
                    self._draw()
                    self._draw_tutorial()
                elif self.tutorial_phase == "outro":
                    self._draw_tutorial_outro()
            else:
                if not self.shop_open:
                    self._update(dt)
                self._draw()
            await asyncio.sleep(0)


    def _handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            # Manuel tuş tracking — Edge WASM'da get_pressed() tuşları kaçırıyor
            if event.type == pygame.KEYDOWN:
                self._held_keys.add(event.key)
            elif event.type == pygame.KEYUP:
                self._held_keys.discard(event.key)

            # Unlock web audio on first user interaction
            if event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN, pygame.FINGERDOWN):
                self.sound_manager.unlock_audio()

            # --- Mouse/Touch: buton basılı tutma (D-pad) ---
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                btn = self._get_button_at(event.pos)
                if btn in ('up', 'down', 'left', 'right'):
                    self.virtual_keys[btn] = True
            if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                # Tüm sanal tuşları bırak
                for k in self.virtual_keys:
                    self.virtual_keys[k] = False

            if self.show_instructions:
                if event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_DOWN, pygame.K_s, pygame.K_RIGHT):
                        self.instructions_scroll += 40
                    elif event.key in (pygame.K_UP, pygame.K_w, pygame.K_LEFT):
                        self.instructions_scroll = max(0, self.instructions_scroll - 40)
                    elif event.key == pygame.K_SPACE:
                        self.show_instructions = False
                        self.reset_game()
                        self.tutorial_active = True
                # Mouse wheel scroll
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 4:  # scroll up
                    self.instructions_scroll = max(0, self.instructions_scroll - 40)
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 5:  # scroll down
                    self.instructions_scroll += 40
                # Mouse tıklama: sadece "Devam Et" butonuna basınca devam et
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mx, my = event.pos
                    # Devam butonu: sağ alt köşe 180x40
                    btn_w, btn_h = 180, 40
                    btn_x = constants.SCREEN_WIDTH - btn_w - 40
                    btn_y = constants.SCREEN_HEIGHT - 52
                    if btn_x <= mx <= btn_x + btn_w and btn_y <= my <= btn_y + btn_h:
                        self.show_instructions = False
                        self.reset_game()
                        self.tutorial_active = True
                # Touch scroll for instructions
                if event.type == pygame.FINGERDOWN:
                    self._touch_last_y = event.y * constants.SCREEN_HEIGHT
                if event.type == pygame.FINGERMOTION and self._touch_last_y is not None:
                    new_y = event.y * constants.SCREEN_HEIGHT
                    delta = self._touch_last_y - new_y
                    self.instructions_scroll = max(0, self.instructions_scroll + int(delta))
                    self._touch_last_y = new_y
                if event.type == pygame.FINGERUP:
                    self._touch_last_y = None
                continue

            if self.tutorial_active:
                # SPACE: event-based + _held_keys fallback (Edge WASM gecikme fix)
                space_pressed = (event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE)
                if space_pressed:
                    if self.tutorial_phase == "intro":
                        self.tutorial_phase = "playing"
                        self.tutorial_step = 0
                        self.tutorial_wait = 0.0
                        self.tutorial_feed_count = 0
                        self.reset_game()
                        self.sound_manager.start_music()
                    elif self.tutorial_phase == "outro":
                        self.tutorial_active = False
                        self.sound_manager.stop_music()
                        self.reset_game()
                        self.sound_manager.start_music()
                    elif self.tutorial_phase == "playing":
                        step = self.tutorial_steps[self.tutorial_step]
                        if step["action"] == "done":
                            self.tutorial_phase = "outro"
                # Mouse/touch: tutorial butonlarına tıklama ile devam
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mx, my = event.pos
                    # Buton alanı: 260x50, merkez X, Y=480
                    btn_w, btn_h = 260, 50
                    btn_x = constants.SCREEN_WIDTH // 2 - btn_w // 2
                    btn_y = 480
                    if btn_x <= mx <= btn_x + btn_w and btn_y <= my <= btn_y + btn_h:
                        if self.tutorial_phase == "intro":
                            self.tutorial_phase = "playing"
                            self.tutorial_step = 0
                            self.tutorial_wait = 0.0
                            self.tutorial_feed_count = 0
                            self.reset_game()
                            self.sound_manager.start_music()
                        elif self.tutorial_phase == "outro":
                            self.tutorial_active = False
                            self.sound_manager.stop_music()
                            self.reset_game()
                            self.sound_manager.start_music()
                    elif self.tutorial_phase == "playing":
                        step = self.tutorial_steps[self.tutorial_step]
                        if step["action"] == "done":
                            self.tutorial_phase = "outro"
                continue

            # --- OYUN İÇİ MOUSE/TOUCH ---
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                btn = self._get_button_at((mx, my))
                
                if btn == 'action_e':
                    self._handle_interaction()
                elif btn == 'action_space':
                    if self.game_over:
                        self.reset_game()
                    elif abs(self.player.x - constants.STORAGE_X) < 120 and abs(self.player.y - constants.STORAGE_Y) < 120:
                        self.shop_open = not self.shop_open
                        self.sound_manager.play("shop_open" if self.shop_open else "shop_close")
                    elif abs(self.player.x - constants.TRASH_X) < 120 and abs(self.player.y - constants.TRASH_Y) < 120:
                        self._handle_interaction()
                    else:
                        self.shop_open = False
                elif btn in ('up', 'down', 'left', 'right'):
                    pass  # D-pad basılı tutma yukarıda yönetiliyor
                elif self.shop_open:
                    # Shop butonlarına tıklama
                    self._handle_shop_click(mx, my)
                else:
                    # Boş alana tıklama = click-to-move
                    self.player.set_move_target(mx, my)

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    if self.game_over:
                        self.reset_game()
                    else:
                        # Toggle Shop or Trash
                        if abs(self.player.x - constants.STORAGE_X) < 120 and abs(self.player.y - constants.STORAGE_Y) < 120:
                            self.shop_open = not self.shop_open
                            self.sound_manager.play("shop_open" if self.shop_open else "shop_close")
                        elif abs(self.player.x - constants.TRASH_X) < 120 and abs(self.player.y - constants.TRASH_Y) < 120:
                            self._handle_interaction()
                        else:
                            self.shop_open = False

                if event.key == pygame.K_e:
                    self._handle_interaction()

                # Shop keyboard shortcuts
                if event.key == pygame.K_m:
                    self.sound_manager.toggle_music()
                if event.key == pygame.K_r:
                    self.sound_manager.stop_music()
                    self.reset_game()
                    self.sound_manager.start_music()

                if self.shop_open:
                    if event.key == pygame.K_1 or event.key == pygame.K_KP1:
                        self._buy_item("CARROT_SEEDS")
                    if (event.key == pygame.K_2 or event.key == pygame.K_KP2) and self.level >= 2:
                        self._buy_item("APPLE_SAPLING")
                    if (event.key == pygame.K_3 or event.key == pygame.K_KP3) and self.level >= 3:
                        self._buy_item("SPEED_BOOTS")
                    if (event.key == pygame.K_4 or event.key == pygame.K_KP4) and self.level >= 3:
                        self._buy_item("MEDIUM_BASKET")
                    if (event.key == pygame.K_5 or event.key == pygame.K_KP5) and self.level >= 4:
                        self._buy_item("WHEAT_SEEDS")
                    if (event.key == pygame.K_6 or event.key == pygame.K_KP6) and self.level >= 5:
                        self._buy_item("BIG_BASKET")
    def _update_tutorial(self, dt):
        # Her zaman crop'ları güncelle (büyüme ekranda görünsün)
        for crop in self.crops:
            crop.update(dt)

        if self.tutorial_step >= len(self.tutorial_steps):
            return
        step = self.tutorial_steps[self.tutorial_step]
        action = step["action"]
        target = step["target"]

        # Hedef belirleme
        tx, ty = self.player.x, self.player.y
        need_move = False
        if action == "move" and target is not None:
            if target == "horse" and self.horses:
                tx, ty = self.horses[0].x - 80, self.horses[0].y
                need_move = True
            elif target == "poop" and self.poops:
                tx, ty = self.poops[0].x, self.poops[0].y
                need_move = True
            elif target == "crop":
                # En yakın mature crop'a git, yoksa herhangi bir crop'a
                mature = [c for c in self.crops if c.state == CropState.MATURE]
                if mature:
                    tx, ty = mature[0].x, mature[0].y
                    need_move = True
                elif self.crops:
                    tx, ty = self.crops[0].x, self.crops[0].y
                    need_move = True
            elif isinstance(target, tuple):
                tx, ty = target
                need_move = True

            if need_move:
                dx = tx - self.player.x
                dy = ty - self.player.y
                dist = math.sqrt(dx*dx + dy*dy)
                if dist > 10:
                    # Piksel-bazlı minimum hız: en az 6 px/frame
                    speed = max(500 * dt, 6.0)
                    self.player.x += (dx / dist) * speed
                    self.player.y += (dy / dist) * speed
                    return
                else:
                    # Hedefe ulaştı, sonraki adıma geç
                    self.tutorial_step += 1
                    return

        # Aksiyonlar
        if action == "buy_seeds":
            if self.tutorial_wait == 0.0:
                self.player.coins = max(self.player.coins, 25)
                self.player.carrot_seeds = 5
                self.player.items.clear()
                self.player.items.append("SEED")
                self.sound_manager.play("buy")
            self.tutorial_wait += dt
            if self.tutorial_wait > 0.8:
                self.tutorial_wait = 0.0
                self.tutorial_step += 1
        elif action == "plant_all":
            if self.tutorial_wait == 0.0:
                # 2 havuç yan yana ek
                positions = [(140, 180), (220, 180)]
                for px, py in positions:
                    if not any(abs(c.x - px) < 5 and abs(c.y - py) < 5 for c in self.crops) and self.player.carrot_seeds > 0:
                        self.crops.append(Crop(px, py, FoodType.CARROT))
                        self.player.carrot_seeds -= 1
                self.player.items.clear()  # Tohum kafadan kalksın
                self.sound_manager.play("plant")
            self.tutorial_wait += dt
            if self.tutorial_wait > 1.0:
                self.tutorial_wait = 0.0
                self.tutorial_step += 1
        elif action == "wait_grow_all":
            # Tüm crop'ları hızlandır
            for crop in self.crops:
                crop.timer += dt * 4
            # En az 1 tanesi mature olunca geç
            if any(c.state == CropState.MATURE for c in self.crops):
                self.tutorial_wait += dt
                if self.tutorial_wait > 0.5:
                    self.tutorial_wait = 0.0
                    self.tutorial_step += 1
        elif action == "harvest_one":
            if self.tutorial_wait == 0.0:
                for crop in self.crops[:]:
                    if crop.state == CropState.MATURE:
                        self.crops.remove(crop)
                        self.player.items.clear()
                        self.player.items.append("CARROT")
                        self.sound_manager.play("harvest_carrot")
                        break
            self.tutorial_wait += dt
            if self.tutorial_wait > 0.5:
                self.tutorial_wait = 0.0
                self.tutorial_step += 1
        elif action == "feed":
            if self.tutorial_wait == 0.0:
                if "CARROT" in self.player.items and self.horses:
                    self.horses[0].receive_food(FoodType.CARROT)
                    self.player.items.clear()
                    self.sound_manager.play("feed")
                    self.tutorial_feed_count += 1
                    if not self.poops:
                        self.poops.append(Poop(self.horses[0].x + 100, self.horses[0].y + 10))
            self.tutorial_wait += dt
            if self.tutorial_wait > 1.0:
                self.tutorial_wait = 0.0
                self.tutorial_step += 1
        elif action == "collect_poop":
            if self.tutorial_wait == 0.0:
                if self.poops:
                    self.poops.pop(0)
                    self.player.items.clear()
                    self.player.items.append("POOP")
                    self.sound_manager.play("poop_collect")
            self.tutorial_wait += dt
            if self.tutorial_wait > 0.6:
                self.tutorial_wait = 0.0
                self.tutorial_step += 1
        elif action == "sell_poop":
            if self.tutorial_wait == 0.0:
                if "POOP" in self.player.items:
                    self.player.items.clear()
                    self.player.coins += constants.POOP_VALUE
                    self.sound_manager.play("coin")
            self.tutorial_wait += dt
            if self.tutorial_wait > 1.2:
                self.tutorial_wait = 0.0
                self.tutorial_step += 1
        elif action == "done":
            self.tutorial_phase = "outro"

    def _draw_focus_screen(self):
        self.screen.fill((20, 20, 35))
        title = self.font_large.render("🐴 Feed the Herd 🥕", True, (255, 215, 0))
        tr = title.get_rect(center=(constants.SCREEN_WIDTH // 2, 280))
        self.screen.blit(title, tr)
        info = self.font_large.render("▶  TIKLA veya BİR TUŞA BAS", True, (255, 255, 100))
        ir = info.get_rect(center=(constants.SCREEN_WIDTH // 2, 400))
        self.screen.blit(info, ir)
        pygame.display.flip()

    def _draw_tutorial_intro(self):
        self.screen.fill((25, 25, 40))
        # Başlık
        title = self.font_large.render("TUTORIAL OYUN", True, (255, 215, 0))
        tr = title.get_rect(center=(constants.SCREEN_WIDTH // 2, 200))
        self.screen.blit(title, tr)
        # Açıklama satırları
        lines = [
            "Şimdi kısa bir demo izleyeceksin.",
            "Çiftçi otomatik olarak hareket edecek.",
            "Tohum alma, ekim, hasat, at besleme",
            "ve gübre satışını göreceksin.",
        ]
        y = 280
        for line in lines:
            s = self.font_small.render(line, True, (200, 200, 220))
            r = s.get_rect(center=(constants.SCREEN_WIDTH // 2, y))
            self.screen.blit(s, r)
            y += 32
        # Tıklanabilir buton
        btn_w, btn_h = 260, 50
        btn_x = constants.SCREEN_WIDTH // 2 - btn_w // 2
        btn_y = 480
        btn_rect = pygame.Rect(btn_x, btn_y, btn_w, btn_h)
        pygame.draw.rect(self.screen, (60, 140, 60), btn_rect, border_radius=14)
        pygame.draw.rect(self.screen, (255, 255, 100), btn_rect, width=2, border_radius=14)
        btn_text = self.font_small.render("▶ DEMO'YU BAŞLAT", True, (255, 255, 255))
        self.screen.blit(btn_text, btn_text.get_rect(center=btn_rect.center))
        pygame.display.flip()

    def _draw_tutorial_outro(self):
        self.screen.fill((25, 25, 40))
        title = self.font_large.render("DEMO BİTTİ!", True, (100, 255, 100))
        tr = title.get_rect(center=(constants.SCREEN_WIDTH // 2, 200))
        self.screen.blit(title, tr)
        lines = [
            "Artık oyunun nasıl oynandığını biliyorsun!",
            "Tohum al, ek, hasat et, atları besle,",
            "gübre sat ve para kazan!",
            "",
            "Esas oyun şimdi başlıyor.",
        ]
        y = 280
        for line in lines:
            s = self.font_small.render(line, True, (200, 200, 220))
            r = s.get_rect(center=(constants.SCREEN_WIDTH // 2, y))
            self.screen.blit(s, r)
            y += 32
        btn_w, btn_h = 260, 50
        btn_x = constants.SCREEN_WIDTH // 2 - btn_w // 2
        btn_y = 480
        btn_rect = pygame.Rect(btn_x, btn_y, btn_w, btn_h)
        pygame.draw.rect(self.screen, (60, 60, 180), btn_rect, border_radius=14)
        pygame.draw.rect(self.screen, (255, 255, 100), btn_rect, width=2, border_radius=14)
        btn_text = self.font_small.render("▶ OYUNA BAŞLA!", True, (255, 255, 255))
        self.screen.blit(btn_text, btn_text.get_rect(center=btn_rect.center))
        pygame.display.flip()

    def _draw_tutorial(self):
        if self.tutorial_step >= len(self.tutorial_steps):
            return
        step = self.tutorial_steps[self.tutorial_step]
        msg = step["msg"]
        if not msg:
            return
        box_w = self.screen.get_width() - 120
        box_h = 70
        box_x = 60
        box_y = 20
        overlay = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
        overlay.fill((20, 20, 30, 220))
        pygame.draw.rect(overlay, (255, 215, 0), (0, 0, box_w, box_h), width=3, border_radius=18)
        self.screen.blit(overlay, (box_x, box_y))
        surf = self.font_small.render(msg, True, (255, 255, 255))
        self.screen.blit(surf, (box_x + 18, box_y + 14))
        # Para bilgisi
        coin_text = self.font_small.render(f"Para: {self.player.coins}", True, (255, 255, 100))
        self.screen.blit(coin_text, (box_x + box_w - 160, box_y + 14))
        # DEMO etiketi
        tag = self.font_small.render("DEMO", True, (255, 100, 100))
        self.screen.blit(tag, (box_x + box_w - 80, box_y + box_h - 28))
    def _draw_instructions(self):
        # Gelişmiş talimat ekranı, otomatik satır kaydırma ve scroll ile
        import textwrap
        self.screen.fill((30, 30, 40))
        margin_x = 60
        margin_y = 40
        line_gap = 6
        max_width = self.screen.get_width() - 2 * margin_x
        y = margin_y - self.instructions_scroll
        lines = self.instructions_text.split('\n')
        for line in lines:
            line = line.rstrip()
            if not line:
                y += self.font_small.get_height() // 2
                continue
            # Hangi font ve renk?
            if line.startswith('# '):
                font = self.font_large
                color = (255, 215, 0)
                text = line.replace('# ', '')
                y += 10
            elif line.startswith('## '):
                font = self.font_small
                color = (255, 255, 255)
                text = line.replace('## ', '')
                y += 8
            elif line.startswith('### '):
                font = self.font_small
                color = (200, 200, 255)
                text = line.replace('### ', '')
                y += 4
            elif line.startswith('- '):
                font = self.font_small
                color = (180, 220, 180)
                text = '• ' + line[2:]
            elif line.startswith('**') and line.endswith('**'):
                font = self.font_small
                color = (255, 255, 100)
                text = line.strip('*')
            else:
                font = self.font_small
                color = (220, 220, 220)
                text = line

            # Satır kaydırma
            wrapped = textwrap.wrap(text, width=60)
            for wline in wrapped:
                if y > self.screen.get_height() - margin_y - 40:
                    break
                if y + font.get_height() > margin_y:
                    surf = font.render(wline, True, color)
                    self.screen.blit(surf, (margin_x, y))
                y += font.get_height() + line_gap
            if y > self.screen.get_height() - margin_y - 40:
                break
        # Scroll ipucu ve devam butonu
        info_bg = pygame.Surface((self.screen.get_width(), 60), pygame.SRCALPHA)
        info_bg.fill((20, 20, 30, 230))
        self.screen.blit(info_bg, (0, self.screen.get_height() - 60))
        
        # Scroll ipucu (sol)
        scroll_info = self.font_small.render("Mouse scroll veya [↑/↓] ile kaydır", True, (180, 180, 200))
        self.screen.blit(scroll_info, (40, self.screen.get_height() - 45))
        
        # Tıklanabilir "DEVAM ET" butonu (sağ alt)
        btn_w, btn_h = 180, 40
        btn_x = self.screen.get_width() - btn_w - 40
        btn_y = self.screen.get_height() - 52
        btn_rect = pygame.Rect(btn_x, btn_y, btn_w, btn_h)
        pygame.draw.rect(self.screen, (60, 160, 60), btn_rect, border_radius=10)
        pygame.draw.rect(self.screen, (255, 255, 100), btn_rect, width=2, border_radius=10)
        btn_text = self.font_small.render("▶ DEVAM ET", True, (255, 255, 255))
        btn_tr = btn_text.get_rect(center=btn_rect.center)
        self.screen.blit(btn_text, btn_tr)
        
        # Devam butonu rect'ini kaydet (event handler'da kullanılacak)
        # Alt ortada 200x50 olan eski butonla uyumlu olması için güncelle
        pygame.display.flip()

    def _buy_item(self, item_type: str) -> bool:
        if item_type == "CARROT_SEEDS":
            cost = 25 # 5x
            if self.player.coins >= cost and self.player.carrot_seeds == 0:
                self.player.coins -= cost
                self.player.carrot_seeds = 5
                self.shop_open = False
                if "SEED" not in self.player.items: self.player.items.append("SEED")
                self.sound_manager.play("buy")  # Play buy sound
                return True
        elif item_type == "APPLE_SAPLING":
            cost = constants.APPLE_SAPLING_PRICE # 30
            if self.player.coins >= cost and self.player.apple_saplings < 2:
                self.player.coins -= cost
                self.player.apple_saplings += 1
                self.shop_open = False
                if "SAPLING" not in self.player.items: self.player.items.append("SAPLING")
                self.sound_manager.play("buy")  # Play buy sound
                return True
        elif item_type == "WHEAT_SEEDS":
            if self.level < 4: return False
            cost = 25 # 5x
            if self.player.coins >= cost and self.player.wheat_seeds == 0:
                self.player.coins -= cost
                self.player.wheat_seeds = 5
                self.shop_open = False
                if "WHEAT_SEED" not in self.player.items: self.player.items.append("WHEAT_SEED")
                self.sound_manager.play("buy")  # Play buy sound
                return True
        elif item_type == "SPEED_BOOTS":
            if self.level < 3: return False
            cost = constants.BOOTS_BASE_PRICE + (self.level - 3) * constants.BOOTS_PRICE_STEP
            duration = constants.BOOTS_BASE_DURATION + (self.level - 3) * constants.BOOTS_DURATION_STEP
            if self.player.coins >= cost:
                self.player.coins -= cost
                self.player.speed_boost_timer += duration
                self.shop_open = False
                self.sound_manager.play("buy")  # Play buy sound
                return True
        elif item_type == "MEDIUM_BASKET":
            if self.level < 3: return False
            cost = constants.UPGRADE_BASKET_2_PRICE
            if self.player.coins >= cost:
                self.player.coins -= cost
                self.player.basket_timer += constants.UPGRADE_DURATION
                self.player.basket_capacity = 2
                self.shop_open = False
                self.sound_manager.play("buy")  # Play buy sound
                return True
        elif item_type == "BIG_BASKET":
            if self.level < 5: return False
            cost = constants.UPGRADE_BASKET_3_PRICE
            if self.player.coins >= cost:
                self.player.coins -= cost
                self.player.basket_timer += constants.UPGRADE_DURATION
                self.player.basket_capacity = 3
                self.shop_open = False
                self.sound_manager.play("buy")  # Play buy sound
                return True
        return False

    def _handle_shop_click(self, mx, my):
        """Shop popup'ında mouse tıklama ile alışveriş"""
        w, h = 500, 420
        overlay_x = (constants.SCREEN_WIDTH - w) // 2
        overlay_y = (constants.SCREEN_HEIGHT - h) // 2
        # Her satır yaklaşık 40px yüksekliğinde, tıklama alanı geniş
        items = [
            (overlay_y + 80, overlay_y + 120, "CARROT_SEEDS", 1),
            (overlay_y + 120, overlay_y + 160, "APPLE_SAPLING", 2),
            (overlay_y + 160, overlay_y + 200, "WHEAT_SEEDS", 4),
            (overlay_y + 230, overlay_y + 270, "SPEED_BOOTS", 3),
            (overlay_y + 270, overlay_y + 310, "MEDIUM_BASKET", 3),
            (overlay_y + 310, overlay_y + 360, "BIG_BASKET", 5),
        ]
        for (y_top, y_bot, item_type, min_level) in items:
            if y_top <= my <= y_bot and overlay_x + 30 <= mx <= overlay_x + w - 30:
                if self.level >= min_level:
                    self._buy_item(item_type)
                    return
        # Kapat butonu alanı (en alt)
        if my >= overlay_y + 370 and my <= overlay_y + h:
            self.shop_open = False

    def _check_horse_finished(self, horse: Horse):
        if horse.is_finished():
            self.score += 10
            should_spawn = (self.level >= 2) or (horse.feedings_count % 2 == 1)
            if should_spawn:
                self.poops.append(Poop(horse.x + 100, horse.y + 10))
                self.sound_manager.play("poop_spawn")  # Play poop spawn sound
            horse.reset(self.level)
            self.sound_manager.play("horse_done")  # Play horse done sound

    def _handle_interaction(self):
        if self.shop_open: return
        
        # Standing at Shop to pick up items manually
        if abs(self.player.x - constants.STORAGE_X) < 100 and abs(self.player.y - constants.STORAGE_Y) < 100:
            max_cap = self.player.basket_capacity if self.player.basket_timer > 0 else 1
            if len(self.player.items) < max_cap:
                if self.player.carrot_seeds > 0 and "SEED" not in self.player.items:
                    self.player.items.append("SEED")
                    self.sound_manager.play("plant")  # Play plant sound
                    return
                elif self.player.apple_saplings > 0 and "SAPLING" not in self.player.items:
                    self.player.items.append("SAPLING")
                    self.sound_manager.play("plant")  # Play plant sound
                    return
                elif self.player.wheat_seeds > 0 and "WHEAT_SEED" not in self.player.items:
                    self.player.items.append("WHEAT_SEED")
                    self.sound_manager.play("plant")  # Play plant sound
                    return
        # Trash interaction
        if abs(self.player.x - constants.TRASH_X) < 100 and abs(self.player.y - constants.TRASH_Y) < 100:
            if self.player.items:
                self.player.items.pop()
                self.sound_manager.play("trash")  # Play trash sound
                return

        # 5. Plant (E)
        if self.player.x < constants.FARM_END:
            if "SEED" in self.player.items and self.player.y < constants.FARM_MID_Y:
                self.crops.append(Crop(self.player.x, self.player.y, FoodType.CARROT))
                self.player.carrot_seeds -= 1
                if self.player.carrot_seeds <= 0: self.player.items.remove("SEED")
                self.sound_manager.play("plant")  # Play plant sound
                return
            elif "WHEAT_SEED" in self.player.items and self.player.y < constants.FARM_MID_Y:
                self.crops.append(Crop(self.player.x, self.player.y, FoodType.WHEAT))
                self.player.wheat_seeds -= 1
                if self.player.wheat_seeds <= 0: self.player.items.remove("WHEAT_SEED")
                self.sound_manager.play("plant")  # Play plant sound
                return
            elif "SAPLING" in self.player.items and self.player.y >= constants.FARM_MID_Y:
                self.apple_trees.append(AppleTree(self.player.x, self.player.y))
                self.player.apple_saplings -= 1
                if self.player.apple_saplings <= 0: self.player.items.remove("SAPLING")
                self.sound_manager.play("plant")  # Play plant sound
                return
    def _update(self, dt):
        if self.game_over: return
        
        # Game Over Check
        for h in self.horses:
            if h.state == HorseState.DEAD:
                self.game_over = True
                return

        # Level up logic...
        # Level up logic (Every 50 points)
        new_lvl = (self.score // 50) + 1
        
        if new_lvl > self.level:
            self.level = new_lvl
            self.player.coins += 25
            self.sound_manager.play("level_up")
            # Reset horses to adapt to new level parameters
            for h in self.horses:
                h.reset(self.level)
            
            # Unlock Notifications
            if self.level == 3 and not self.unlocked_notifs[3]:
                self.notification_msg = "✨ YENİ GELİŞTİRMELER AÇILDI! Marketi ziyaret et. ✨"
                self.notification_timer = 6.0
                self.unlocked_notifs[3] = True
            elif self.level == 5 and not self.unlocked_notifs[5]:
                self.notification_msg = "🌟 BÜYÜK SEPET ARTIK KULANILABİLİR! 🌟"
                self.notification_timer = 6.0
                self.unlocked_notifs[5] = True

        if self.notification_timer > 0:
            self.notification_timer -= dt

        if self.level_up_timer > 0:
            self.level_up_timer -= dt
            
        # Manuel tuş tracking + D-pad birleştir (Edge WASM uyumu)
        held = self._held_keys
        vk = self.virtual_keys
        
        class ManualKeys:
            \"\"\"_held_keys + virtual_keys birleştirici\"\"\"
            def __getitem__(self, key):
                if key == pygame.K_UP and vk.get('up'): return True
                if key == pygame.K_DOWN and vk.get('down'): return True
                if key == pygame.K_LEFT and vk.get('left'): return True
                if key == pygame.K_RIGHT and vk.get('right'): return True
                return key in held
        
        combined = ManualKeys()
        self.player.move(combined, dt)
        
        if any(combined[k] for k in (pygame.K_w, pygame.K_s, pygame.K_a, pygame.K_d,
                                   pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT)):
            self.step_timer -= dt
            if self.step_timer <= 0:
                self.sound_manager.play("step")
                self.step_timer = 0.35
        else:
            self.step_timer = 0.0
        for crop in self.crops: crop.update(dt)
        for tree in self.apple_trees: tree.update(dt)
        for horse in self.horses: horse.update(dt)
        
        # Automatic Interactions (Walking over/near)
        if not self.shop_open:
            self._handle_automatic_interactions()

    def _handle_automatic_interactions(self):
        # Determine max capacity
        max_items = self.player.basket_capacity if self.player.basket_timer > 0 else 1

        # 1. Auto-Harvest Crops
        for crop in self.crops[:]:
            if len(self.player.items) >= max_items: break
            if crop.state == CropState.MATURE:
                dist = math.sqrt((self.player.x - crop.x)**2 + (self.player.y - crop.y)**2)
                if dist < 35:
                    self.crops.remove(crop)
                    item_type = "CARROT" if crop.type == FoodType.CARROT else "WHEAT"
                    self.player.items.append(item_type)
                    self.sound_manager.play("harvest_carrot")  # Play harvest sound
        # 2. Auto-Harvest Trees
        for tree in self.apple_trees[:]:
            if len(self.player.items) >= max_items: break
            if tree.state == "READY" and tree.apples_left > 0:
                dist = math.sqrt((self.player.x - tree.x)**2 + (self.player.y - tree.y)**2)
                if dist < 50:
                    tree.harvest()
                    self.player.items.append("APPLE")
                    if tree.apples_left == 0:
                        self.apple_trees.remove(tree)
                    self.sound_manager.play("harvest_apple")  # Play apple harvest sound
        # 3. Auto-Collect Poop
        for poop in self.poops[:]:
            if len(self.player.items) >= max_items: break
            dist = math.sqrt((self.player.x - poop.x)**2 + (self.player.y - poop.y)**2)
            if dist < 35:
                self.poops.remove(poop)
                self.player.items.append("POOP")
                self.sound_manager.play("poop_collect")  # Play poop collect sound
        # 4. Auto-Sell Poop
        if "POOP" in self.player.items:
            if abs(self.player.x - constants.STORAGE_X) < 80 and abs(self.player.y - constants.STORAGE_Y) < 80:
                self.player.coins += constants.POOP_VALUE
                self.player.items.remove("POOP")
                self.sound_manager.play("coin")  # Play coin sound
        # 5. Auto-Feed Horses
        for horse in self.horses:
            dist = math.sqrt((self.player.x - horse.x)**2 + (self.player.y - horse.y)**2)
            if dist < 150 and horse.state == HorseState.WAITING:
                for item in self.player.items[:]:
                    f_type = None
                    if item == "CARROT": f_type = FoodType.CARROT
                    elif item == "APPLE": f_type = FoodType.APPLE
                    elif item == "WHEAT": f_type = FoodType.WHEAT
                    if f_type and horse.receive_food(f_type):
                        self.player.items.remove(item)
                        self.sound_manager.play("feed")  # Play feed sound
                        self._check_horse_finished(horse)
        # ...existing code...

    def _draw(self):
        # 0. Cached background (1 blit instead of 80+)
        if self._bg_cache is None:
            self._build_bg_cache()
        self.screen.blit(self._bg_cache, (0, 0))
        
        # 3. Shop
        self._draw_text("ATLAR", (constants.HORSES_START + 10, 20), constants.COLOR_BLACK, self.font_small)
        shop_spr = self.sprites.get('shop_stall')
        if shop_spr:
            self.screen.blit(shop_spr, (constants.STORAGE_X - 80, constants.STORAGE_Y - 80))
            
        trash_spr = self.sprites.get('trash')
        if trash_spr:
            self.screen.blit(trash_spr, (constants.TRASH_X - 40, constants.TRASH_Y - 40))
            
        # Draw Prompts (Dynamic based on proximity)
        if abs(self.player.x - constants.TRASH_X) < 100 and abs(self.player.y - constants.TRASH_Y) < 100:
            if self.player.items:
                # Position it above the trash bin
                text_x = constants.TRASH_X - 40
                text_y = constants.TRASH_Y - 100
                self._draw_text("[SPACE] Çöpe At", (text_x, text_y), constants.COLOR_WHITE, self.font_small)
        
        # 4. Entities
        for crop in self.crops: crop.draw(self.screen, self.sprites)
        for tree in self.apple_trees: tree.draw(self.screen, self.sprites)
        for poop in self.poops: poop.draw(self.screen, self.sprites)
        for horse in self.horses: horse.draw(self.screen, self.sprites)
        self.player.draw(self.screen, self.sprites)
        
        # 5. UI (Compact Top Center)
        ui_y = constants.UI_BASE_Y
        self._draw_stat_box(constants.SCREEN_WIDTH // 2 - 110, ui_y, str(self.score), "SKOR", (255, 200, 50))
        self._draw_stat_box(constants.SCREEN_WIDTH // 2, ui_y, str(self.level), "LEVEL", (80, 200, 255))
        self._draw_stat_box(constants.SCREEN_WIDTH // 2 + 110, ui_y, str(self.player.coins), "PARA", (255, 255, 100))
        
        # Bottom UI (inventory)
        seed_text = f"TOHUM: {self.player.carrot_seeds}"
        self._draw_text(seed_text, (20, constants.SCREEN_HEIGHT - 40), constants.COLOR_BLACK, self.font_small)

        if self.level >= 2:
            sap_text = f"FİDAN: {self.player.apple_saplings}"
            self._draw_text(sap_text, (150, constants.SCREEN_HEIGHT - 40), constants.COLOR_BLACK, self.font_small)

        if self.level >= 4:
            wheat_text = f"BUĞDAY: {self.player.wheat_seeds}"
            self._draw_text(wheat_text, (280, constants.SCREEN_HEIGHT - 40), constants.COLOR_BLACK, self.font_small)

        if self.level_up_timer > 0:
            msg = f"LEVEL {self.level}!"
            surf = self.font_large.render(msg, True, (255, 100, 0))
            rect = surf.get_rect(center=(constants.SCREEN_WIDTH//2, constants.SCREEN_HEIGHT//2))
            # Shadow
            self.screen.blit(self.font_large.render(msg, True, (0,0,0)), rect.move(3,3))
            self.screen.blit(surf, rect)

        if self.notification_timer > 0:
            msg = self.notification_msg
            notif_w, notif_h = 550, 60
            # Cache notification background
            if self._notif_bg_cache is None:
                self._notif_bg_cache = pygame.Surface((notif_w, notif_h), pygame.SRCALPHA)
                pygame.draw.rect(self._notif_bg_cache, (20, 20, 30, 230), (0, 0, notif_w, notif_h), border_radius=15)
            
            notif_x = (constants.SCREEN_WIDTH - notif_w) // 2
            notif_y = 150
            self.screen.blit(self._notif_bg_cache, (notif_x, notif_y))
            pygame.draw.rect(self.screen, (255, 215, 0), (notif_x, notif_y, notif_w, notif_h), width=3, border_radius=15)
            
            self._draw_text(msg, (notif_x + (notif_w - self.font_small.size(msg)[0]) // 2 + 2,
                                  notif_y + (notif_h - self.font_small.get_height()) // 2 + 2),
                           (0, 0, 0), self.font_small)
            self._draw_text(msg, (notif_x + (notif_w - self.font_small.size(msg)[0]) // 2,
                                  notif_y + (notif_h - self.font_small.get_height()) // 2),
                           (255, 255, 255), self.font_small)

        # 6. Active Power-ups (Timers) - Top Center below Level
        timer_y = 115
        if self.player.speed_boost_timer > 0:
            msg = f"HIZ: {int(self.player.speed_boost_timer)}s"
            self._draw_centered_text(msg, timer_y, (255, 100, 0), self.font_small)
            timer_y += 25
        if self.player.basket_timer > 0:
            msg = f"SEPET: {int(self.player.basket_timer)}s"
            self._draw_centered_text(msg, timer_y, (0, 255, 100), self.font_small)

        # Müzik ve restart UI ipuçları
        music_icon = "♫ ON" if self.sound_manager.music_playing else "♫ OFF"
        music_color = (100, 255, 100) if self.sound_manager.music_playing else (255, 100, 100)
        self._draw_text(f"[M] {music_icon}", (10, 10), music_color, self.font_small)
        self._draw_text("[R] Yeniden Başlat", (10, 35), (180, 180, 180), self.font_small)

        # Version tag
        self._draw_text(self.version, (constants.SCREEN_WIDTH - 60, constants.SCREEN_HEIGHT - 30), (100, 100, 100), self.font_small)

        if self.game_over:
            self._draw_game_over()
        elif self.shop_open:
            self._draw_shop_popup()
            
        self._draw_interaction_prompts()
        
        # 8. On-screen D-pad and action buttons
        self._draw_onscreen_buttons()
        
        pygame.display.flip()

    def _draw_game_over(self):
        w, h = 600, 300
        overlay_x = (constants.SCREEN_WIDTH - w) // 2
        overlay_y = (constants.SCREEN_HEIGHT - h) // 2
        
        if not hasattr(self, '_gameover_bg'):
            self._gameover_bg = pygame.Surface((w, h), pygame.SRCALPHA)
            pygame.draw.rect(self._gameover_bg, (0, 0, 0, 220), (0, 0, w, h), border_radius=30)
        self.screen.blit(self._gameover_bg, (overlay_x, overlay_y))
        pygame.draw.rect(self.screen, (255, 50, 50), (overlay_x, overlay_y, w, h), width=4, border_radius=30)
        
        self._draw_centered_text("OYUN BİTTİ", overlay_y + 60, (255, 50, 50), self.font_large)
        self._draw_centered_text(f"Toplam Skor: {self.score}", overlay_y + 130, (255, 255, 255), self.font_small)
        self._draw_centered_text("Yeniden Başlamak İçin SPACE/Tıkla", overlay_y + 200, (200, 200, 200), self.font_small)

    def _draw_stat_box(self, x, y, val, title, color):
        width, height = constants.BOX_WIDTH, constants.BOX_HEIGHT
        rect = pygame.Rect(x - width//2, y - height//2, width, height)
        pygame.draw.rect(self.screen, (0,0,0,30), rect.move(3,3), border_radius=12)
        pygame.draw.rect(self.screen, color, rect, border_radius=12)
        pygame.draw.rect(self.screen, (30,30,30), rect, width=2, border_radius=12)
        
        # Cached font renders
        val_key = (val, 'stat_val')
        val_surf = self._font_cache.get(val_key)
        if val_surf is None:
            val_surf = self.font_large.render(val, True, constants.COLOR_BLACK)
            self._font_cache[val_key] = val_surf
        v_rect = val_surf.get_rect(center=(x, y-8))
        self.screen.blit(val_surf, v_rect)
        
        title_key = (title, 'stat_title')
        title_surf = self._font_cache.get(title_key)
        if title_surf is None:
            title_surf = self.font_small.render(title, True, constants.COLOR_BLACK)
            self._font_cache[title_key] = title_surf
        t_rect = title_surf.get_rect(center=(x, y + 18))
        self.screen.blit(title_surf, t_rect)

    def _draw_shop_popup(self):
        w, h = 500, 420
        overlay_x = (constants.SCREEN_WIDTH - w) // 2
        overlay_y = (constants.SCREEN_HEIGHT - h) // 2
        
        if not hasattr(self, '_shop_bg'):
            self._shop_bg = pygame.Surface((w, h), pygame.SRCALPHA)
            pygame.draw.rect(self._shop_bg, (0, 0, 0, 220), (0, 0, w, h), border_radius=25)
        self.screen.blit(self._shop_bg, (overlay_x, overlay_y))
        
        self._draw_text("PAZAR - SHOP", (overlay_x + 150, overlay_y + 30), (255, 255, 255), self.font_large)
        
        # 1-2 Items
        self._draw_text(f"[1] Havuç Tohumu (5x) - 25", (overlay_x + 50, overlay_y + 90), (255, 255, 255), self.font_small)
        if self.level >= 2:
            self._draw_text(f"[2] Elma Fidanı (1x) - 30", (overlay_x + 50, overlay_y + 130), (255, 255, 255), self.font_small)
        if self.level >= 4:
            self._draw_text(f"[5] Buğday Tohumu (5x) - 25", (overlay_x + 50, overlay_y + 170), (255, 255, 0), self.font_small)
        
        # Upgrades
        self._draw_text("--- GELİŞTİRMELER ---", (overlay_x + 50, overlay_y + 210), (150, 150, 150), self.font_small)
        if self.level < 3:
             self._draw_text("[!] Lvl 3'te Açılır", (overlay_x + 50, overlay_y + 240), (255, 100, 100), self.font_small)
        else:
            # Scaling Boots
            boots_price = constants.BOOTS_BASE_PRICE + (self.level - 3) * constants.BOOTS_PRICE_STEP
            boots_dur = constants.BOOTS_BASE_DURATION + (self.level - 3) * constants.BOOTS_DURATION_STEP
            self._draw_text(f"[3] Hız Botu ({int(boots_dur)}sn) - {boots_price}", (overlay_x + 50, overlay_y + 240), (255, 150, 50), self.font_small)
            
            # Medium Basket (2x)
            self._draw_text(f"[4] Orta Sepet (2x - 15sn) - {constants.UPGRADE_BASKET_2_PRICE}", (overlay_x + 50, overlay_y + 280), (50, 255, 150), self.font_small)
            
            # Big Basket (3x)
            if self.level >= 5:
                self._draw_text(f"[6] Büyük Sepet (3x - 15sn) - {constants.UPGRADE_BASKET_3_PRICE}", (overlay_x + 50, overlay_y + 320), (255, 215, 0), self.font_small)
            else:
                self._draw_text("[!] Büyük Sepet Lvl 5'te", (overlay_x + 50, overlay_y + 320), (100, 100, 100), self.font_small)

        self._draw_text("[SPACE/Tıkla] Kapat", (overlay_x + 150, overlay_y + 380), (200, 200, 200), self.font_small)

    def _draw_interaction_prompts(self):
        # Interaction hints
        prompt = ""
        # Shop prompt
        if abs(self.player.x - constants.STORAGE_X) < 100 and abs(self.player.y - constants.STORAGE_Y) < 100:
            prompt = "[SPACE/Tıkla] Market"
        
        # Plant hint
        if any(item in self.player.items for item in ["SEED", "SAPLING", "WHEAT_SEED"]) and self.player.x < constants.FARM_END:
            prompt = "[E/EK Butonu] Ek"

        if prompt:
            self._draw_centered_text(prompt, self.player.y - 70, constants.COLOR_BLACK, self.font_small)

    def _draw_onscreen_buttons(self):
        """Ekrandaki dokunmatik D-pad ve aksiyon butonlarını çiz"""
        if not hasattr(self, '_btn_surf_cache'):
            self._btn_surf_cache = {}

        # D-pad butonları
        dpad_buttons = [
            (self.btn_up, "▲"),
            (self.btn_down, "▼"),
            (self.btn_left, "◀"),
            (self.btn_right, "▶"),
        ]
        dpad_keys = ['up', 'down', 'left', 'right']
        
        for i, (rect, label) in enumerate(dpad_buttons):
            pressed = self.virtual_keys.get(dpad_keys[i], False)
            cache_key = (dpad_keys[i], pressed)
            if cache_key not in self._btn_surf_cache:
                bg_color = (80, 80, 120, 200) if not pressed else (140, 140, 200, 230)
                border_color = (180, 180, 220) if not pressed else (255, 255, 255)
                surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
                pygame.draw.rect(surf, bg_color, (0, 0, rect.width, rect.height), border_radius=10)
                pygame.draw.rect(surf, border_color, (0, 0, rect.width, rect.height), width=2, border_radius=10)
                txt = self.font_small.render(label, True, (255, 255, 255))
                tr = txt.get_rect(center=(rect.width // 2, rect.height // 2))
                surf.blit(txt, tr)
                self._btn_surf_cache[cache_key] = surf
            self.screen.blit(self._btn_surf_cache[cache_key], rect.topleft)

        # Aksiyon butonları
        action_buttons = [
            (self.btn_action_e, "EK [E]", "action_e", (60, 160, 60, 200)),
            (self.btn_action_space, "AKSİYON", "action_space", (60, 60, 160, 200)),
        ]
        for rect, label, key, bg in action_buttons:
            if key not in self._btn_surf_cache:
                surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
                pygame.draw.rect(surf, bg, (0, 0, rect.width, rect.height), border_radius=10)
                pygame.draw.rect(surf, (220, 220, 255), (0, 0, rect.width, rect.height), width=2, border_radius=10)
                txt = self.font_small.render(label, True, (255, 255, 255))
                tr = txt.get_rect(center=(rect.width // 2, rect.height // 2))
                surf.blit(txt, tr)
                self._btn_surf_cache[key] = surf
            self.screen.blit(self._btn_surf_cache[key], rect.topleft)

        # Click-to-move hedef göstergesi
        if self.player.move_target_x is not None:
            tx = int(self.player.move_target_x)
            ty = int(self.player.move_target_y)
            pygame.draw.circle(self.screen, (255, 255, 100, 120), (tx, ty), 8, 2)
            pygame.draw.line(self.screen, (255, 255, 100, 80), (tx - 5, ty), (tx + 5, ty), 1)
            pygame.draw.line(self.screen, (255, 255, 100, 80), (tx, ty - 5), (tx, ty + 5), 1)

    def _draw_text(self, text, pos, color, font):
        if isinstance(color, tuple) and len(color) == 4: # RGBA support for some calls
            surf = font.render(text, True, color[:3])
            surf.set_alpha(color[3])
        else:
            surf = font.render(text, True, color)
        self.screen.blit(surf, pos)

async def main():
    game = Game()
    await game.run()

# pygbag bu satırı yakalar ve kendi event loop'unda çalıştırır
# Desktop'ta da asyncio.run() ile çalışır
if __name__ == "__main__":
    asyncio.run(main())
else:
    # pygbag modülü __main__ olarak çalıştırmayabilir
    asyncio.run(main())
