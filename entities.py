import pygame
import random
import math
from typing import List, Optional
import constants
from enums import FoodType, HorseState, PlayerState, CropState

class Poop:
    """Extra income collectible"""
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.size = constants.POOP_SIZE
        
    def draw(self, screen, sprites):
        spr = sprites.get('poop')
        if spr:
            screen.blit(spr, (int(self.x - self.size[0]//2), int(self.y - self.size[1]//2)))
        else:
            pygame.draw.circle(screen, (100, 70, 20), (int(self.x), int(self.y)), 15)

class Crop:
    """Level 1 Carrot / Level 4 Wheat crop"""
    def __init__(self, x: float, y: float, crop_type: FoodType = FoodType.CARROT):
        self.x = x
        self.y = y
        self.type = crop_type
        self.state = CropState.SEED
        self.timer = 0.0
        self.growth_time = constants.GROWTH_TIME_WHEAT if crop_type == FoodType.WHEAT else constants.GROWTH_TIME_CARROT
        
    def update(self, dt):
        if self.state == CropState.SEED:
            self.timer += dt
            if self.timer >= self.growth_time:
                self.state = CropState.MATURE # Instantly matures for now
    
    def draw(self, screen, sprites):
        growth = self.timer / self.growth_time
        # Size differences: Wheat is taller/wider
        target_size = (30, 36) if self.type == FoodType.CARROT else (45, 55)
        
        if self.state == CropState.MATURE:
            spr_key = 'crop_mature' if self.type == FoodType.CARROT else 'wheat'
            spr = sprites.get(spr_key)
            if spr:
                scaled = pygame.transform.smoothscale(spr, target_size)
                screen.blit(scaled, (int(self.x - target_size[0]//2), int(self.y - target_size[1]//2)))
        else:
            spr_key = 'crop_seed' if self.type == FoodType.CARROT else 'wheat_seed'
            spr = sprites.get(spr_key)
            if spr:
                # Growing phase scaling
                sw = int(target_size[0] * (0.4 + 0.6 * growth))
                sh = int(target_size[1] * (0.4 + 0.6 * growth))
                scaled = pygame.transform.smoothscale(spr, (sw, sh))
                screen.blit(scaled, (int(self.x - sw//2), int(self.y - sh//2)))

class AppleTree:
    """Level 2 Apple Tree"""
    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y
        self.state = "SEED" # SEED, STAGE1, STAGE2, READY
        self.timer = 0.0
        self.apples_left = 3
        self.growth_time = constants.GROWTH_TIME_APPLE_TREE
        
    def update(self, dt):
        if self.state != "READY":
            self.timer += dt
            if self.timer >= self.growth_time:
                self.state = "READY"
            elif self.timer >= self.growth_time * 0.8:
                self.state = "STAGE4"
            elif self.timer >= self.growth_time * 0.6:
                self.state = "STAGE3"
            elif self.timer >= self.growth_time * 0.4:
                self.state = "STAGE2"
            elif self.timer >= self.growth_time * 0.2:
                self.state = "STAGE1"
                
    def harvest(self) -> bool:
        if self.state == "READY" and self.apples_left > 0:
            self.apples_left -= 1
            return True
        return False
        
    def draw(self, screen, sprites):
        growth_ratio = min(1.0, self.timer / self.growth_time)
        # Smoothly scale from 30px to 120px
        current_size = int(30 + (120 - 30) * growth_ratio)
        
        # Use agac_4 for growth, agac_5 for final READY state
        spr_name = 'agac_4' if growth_ratio < 1.0 else 'agac_5'
        
        spr = sprites.get(spr_name)
        if spr:
            scaled = pygame.transform.smoothscale(spr, (current_size, current_size))
            screen.blit(scaled, (int(self.x - current_size//2), int(self.y - current_size//2)))
            
        if self.state == "READY" and self.apples_left > 0:
            apple_spr = sprites.get('apple')
            if apple_spr:
                # Draw remaining apples
                offsets = [(-15, -10), (15, -15), (0, 10)]
                for i in range(self.apples_left):
                    ox, oy = offsets[i]
                    screen.blit(apple_spr, (int(self.x + ox - 10), int(self.y + oy - 10)))
            

class Horse:
    def __init__(self, spawn_index: int, level: int = 1, can_have_three: bool = True):
        self.x = constants.HORSES_START + 50
        self.y = 100 + spawn_index * 180
        self.spawn_index = spawn_index
        self.state = HorseState.WAITING
        self.max_time = 80.0 if level == 1 else 60.0
        self.remaining_time = self.max_time
        self.previous_count = 0
        self.feedings_count = 0
        
        # New requirements logic
        self.wanted_items = self._generate_requests(level)
        self.initial_count = len(self.wanted_items)
        self.fed_items: List[FoodType] = [] # Track what has been fed

    def _generate_requests(self, level: int) -> List[FoodType]:
        # Count scaling: Level 1-2 (1-2 items), Level 3+ (1-3 items), Level 5+ (3 items)
        if level <= 2:
            num_items = random.randint(1, 2)
        elif level <= 4:
            num_items = random.randint(1, 3)
        else:
            num_items = 3
        
        # Avoid same count twice in a row if possible
        if num_items == self.previous_count and level < 5:
            num_items = random.randint(1, 3)
        self.previous_count = num_items

        # Item variety scaling
        pool = [FoodType.CARROT]
        if level >= 2: pool.append(FoodType.APPLE)
        if level >= 4: pool.append(FoodType.WHEAT)

        reqs = [random.choice(pool) for _ in range(num_items)]
        # Force Wheat at Level 4+ to guide player
        if level >= 4 and FoodType.WHEAT not in reqs:
            reqs[random.randint(0, len(reqs)-1)] = FoodType.WHEAT
        return reqs

    def update(self, dt) -> Optional[Poop]:
        if self.state == HorseState.WAITING:
            self.remaining_time -= dt
            if self.remaining_time <= 0:
                self.state = HorseState.DEAD
        return None

    def receive_food(self, food_type: FoodType) -> bool:
        if self.state == HorseState.WAITING and self.wanted_items:
            if food_type in self.wanted_items:
                self.wanted_items.remove(food_type)
                self.fed_items.append(food_type) # Track the fed item
                return True
        return False

    def is_finished(self) -> bool:
        return len(self.wanted_items) == 0

    def reset(self, level: int):
        self.state = HorseState.WAITING
        # Patience scaling: Level 1 (80s), Level 2-5 (60s), Level 6+ (-10% each level)
        base_patience = 80.0 if level == 1 else 60.0
        if level >= 6:
            reduction = (level - 5) * 0.1
            base_patience *= (1.0 - min(0.6, reduction)) # Max 60% reduction

        self.remaining_time = base_patience
        self.max_time = self.remaining_time
        self.fed_items = []
        self.wanted_items = self._generate_requests(level)
        self.initial_count = len(self.wanted_items)
        self.feedings_count += 1

    def draw(self, screen, sprites):
        spr = sprites.get('horse')
        if spr:
            # Center of right column is roughly 880 (750 + (1024-750)/2)
            screen.blit(spr, (int(self.x - 90), int(self.y - 55)))
            
        # UI overlays (Health Bar and Bubble)
        if self.state == HorseState.WAITING:
            # Health bar above horse
            bar_w = 100
            fill_w = int(bar_w * (self.remaining_time / self.max_time))
            pygame.draw.rect(screen, (50, 50, 50), (self.x - 50, self.y - 75, bar_w, 8))
            pygame.draw.rect(screen, (0, 255, 0), (self.x - 50, self.y - 75, fill_w, 8))
            
            # Logic: `fed_items` are FULL color, `wanted_items` are LOW opacity.
            # We show `fed_items` first, then `wanted_items`.
            all_icons = self.fed_items + self.wanted_items
            
            for i, item_type in enumerate(all_icons):
                bx = self.x - 140 - i * 45
                by = self.y - 15
                
                spr_name = 'carrot'
                if item_type == FoodType.APPLE: spr_name = 'apple'
                elif item_type == FoodType.WHEAT: spr_name = 'wheat'
                s = sprites.get(spr_name)
                
                if s:
                    # Draw circular bubble background
                    pygame.draw.circle(screen, (255, 255, 255, 180), (int(bx + 18), int(by + 18)), 22)
                    
                    # Create a copy to adjust alpha
                    icon_spr = pygame.transform.scale(s, (35, 35)).copy()
                    if i >= len(self.fed_items):
                        # Still needed -> Low opacity
                        icon_spr.set_alpha(80) # 80/255 opacity
                    else:
                        # Already fed -> Full opacity
                        icon_spr.set_alpha(255)
                        
                    screen.blit(icon_spr, (int(bx), int(by)))

class Player:
    def __init__(self):
        self.x = constants.SCREEN_WIDTH // 2
        self.y = constants.SCREEN_HEIGHT // 2
        self.base_speed = 240
        self.speed: float = float(self.base_speed)
        self.state = PlayerState.EMPTY
        self.items: List[str] = [] # Supports multiple items for Big Basket
        
        self.coins = constants.INITIAL_COINS
        self.carrot_seeds = 0
        self.apple_saplings = 0
        self.wheat_seeds = 0
        
        # Power-up timers
        self.speed_boost_timer = 0.0
        self.basket_timer = 0.0
        self.basket_capacity = 1 # Default
        
    def move(self, keys, dt):
        # Update timers
        if self.speed_boost_timer > 0:
            self.speed_boost_timer -= dt
            self.speed = self.base_speed * 1.6 # 60% boost
        else:
            self.speed = self.base_speed

        if self.basket_timer > 0:
            self.basket_timer -= dt

        dx, dy = 0, 0
        if keys[pygame.K_LEFT] or keys[pygame.K_a]: dx -= 1
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]: dx += 1
        if keys[pygame.K_UP] or keys[pygame.K_w]: dy -= 1
        if keys[pygame.K_DOWN] or keys[pygame.K_s]: dy += 1
        
        length = math.sqrt(dx*dx + dy*dy)
        if length > 0:
            self.x += (dx/length) * self.speed * dt
            self.y += (dy/length) * self.speed * dt
            
        # Bound to screen
        self.x = max(20, min(constants.SCREEN_WIDTH - 20, self.x))
        self.y = max(20, min(constants.SCREEN_HEIGHT - 20, self.y))

    def draw(self, screen, sprites):
        spr = sprites.get('player')
        if spr:
            screen.blit(spr, (int(self.x - 18), int(self.y - 22)))
            
        # Draw all items in inventory
        for i, item in enumerate(self.items):
            item_spr_name = item.lower()
            item_spr_name = item.lower()
            if item == "SEED": item_spr_name = 'crop_seed'
            elif item == "SAPLING": item_spr_name = 'agac_1'
            elif item == "WHEAT_SEED": item_spr_name = 'wheat_seed'
            
            item_spr = sprites.get(item_spr_name)
            if item_spr:
                sw, sh = item_spr.get_size()
                scale = 25 / max(sw, sh)
                scaled = pygame.transform.smoothscale(item_spr, (int(sw*scale), int(sh*scale)))
                # Stack items above head
                offset_y = -50 - (i * 20)
                screen.blit(scaled, (int(self.x - scaled.get_width()//2), int(self.y + offset_y)))
