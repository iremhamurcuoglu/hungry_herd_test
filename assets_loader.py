import pygame
import os
import random
import constants

class AssetsLoader:
    """Handles asset loading and procedural generation"""
    VERSION = "1.4.0"
    
    REQUIRED_ASSETS = [
        'horse', 'player', 'apple', 'apple_pale', 'carrot', 'carrot_pale',
        'crop_seed', 'crop_mature', 'bg_farm_top', 'bg_farm_bottom', 'bg_grass', 
        'bg_horses', 'shop_stall', 'apple_tree', 'agac_1', 'agac_2', 'agac_3', 'agac_4', 'agac_5', 'poop', 'trash',
        'wheat_seed', 'wheat'
    ]
    
    TARGET_SIZES = {
        'player': (36, 44),
        'carrot': (20, 24),
        'carrot_pale': (20, 24),
        'crop_seed': (16, 16),
        'crop_mature': (20, 24),
        'apple': (30, 30),
        'apple_pale': (30, 30),
        'horse': (180, 110),
        'shop_stall': (160, 160),
        'apple_tree': (100, 100),
        'agac_1': (120, 120),
        'agac_2': (120, 120),
        'agac_3': (120, 120),
        'agac_4': (120, 120),
        'agac_5': (120, 120),
        'poop': (50, 50),
        'trash': (80, 80),
        'wheat_seed': (25, 25),
        'wheat': (35, 45)
    }

    def __init__(self, assets_dir: str):
        self.assets_dir = assets_dir
        self.sprites = {}

    def load_all(self):
        """Main method to load or generate all assets"""
        if not os.path.exists(self.assets_dir):
            os.makedirs(self.assets_dir)

        missing = any(not os.path.exists(os.path.join(self.assets_dir, f"{r}.png")) for r in self.REQUIRED_ASSETS)
        
        if missing:
            self._generate_missing_assets()

        for name in self.REQUIRED_ASSETS:
            surf = self._load_asset(name)
            if surf:
                if name in self.TARGET_SIZES:
                    surf = pygame.transform.smoothscale(surf, self.TARGET_SIZES[name])
                self.sprites[name] = surf
            else:
                self.sprites[name] = self._create_procedural_fallback(name)
                # Save procedurally generated ones if they weren't on disk
                path = os.path.join(self.assets_dir, f"{name}.png")
                if not os.path.exists(path):
                    try:
                        pygame.image.save(self.sprites[name], path)
                    except Exception as e:
                        print(f"Failed to save {name}.png: {e}")
        return self.sprites

 
    def _load_asset(self, name):
        path = os.path.join(self.assets_dir, f"{name}.png")
        try:
            return pygame.image.load(path).convert_alpha()
        except:
            return None

    def _generate_missing_assets(self):
        """Attempts to use external gen script if available"""
        try:
            # We assume the user might have a generation script
            import assets.generate_assets as gen
            gen.generate(self.assets_dir)
        except Exception as e:
            print("External asset generation failed, falling back to procedural:", e)

    def _create_procedural_fallback(self, name):
        """Creates basic shapes if assets are missing"""
        def make_surface(w, h):
            return pygame.Surface((w, h), pygame.SRCALPHA)

        if name == 'horse':
            s = make_surface(100, 60)
            pygame.draw.ellipse(s, constants.COLOR_BROWN, (0, 12, 80, 38))
            pygame.draw.circle(s, constants.COLOR_DARK_BROWN, (72, 20), 12)
            pygame.draw.polygon(s, constants.COLOR_DARK_BROWN, [(74, 10), (92, 6), (82, 24)])
            return s
        elif name == 'player':
            s = make_surface(36, 44)
            pygame.draw.polygon(s, constants.COLOR_GREEN, [(18, 2), (2, 40), (34, 40)])
            pygame.draw.polygon(s, constants.COLOR_BLACK, [(18, 2), (2, 40), (34, 40)], 2)
            return s
        elif name == 'apple':
            s = make_surface(20, 20)
            pygame.draw.circle(s, constants.COLOR_RED, (10, 10), 8)
            pygame.draw.circle(s, constants.COLOR_BLACK, (10, 10), 8, 1)
            return s
        elif name == 'apple_pale':
            s = make_surface(20, 20)
            pygame.draw.circle(s, constants.COLOR_PALE_RED, (10, 10), 8)
            pygame.draw.circle(s, constants.COLOR_BLACK, (10, 10), 8, 1)
            return s
        elif name == 'carrot':
            s = make_surface(20, 24)
            pygame.draw.rect(s, constants.COLOR_ORANGE, (4, 3, 12, 18))
            pygame.draw.rect(s, constants.COLOR_BLACK, (4, 3, 12, 18), 1)
            return s
        elif name == 'carrot_pale':
            s = make_surface(20, 24)
            pygame.draw.rect(s, constants.COLOR_PALE_ORANGE, (4, 3, 12, 18))
            pygame.draw.rect(s, constants.COLOR_BLACK, (4, 3, 12, 18), 1)
            return s
        elif name == 'crop_seed':
            s = make_surface(16, 16)
            pygame.draw.circle(s, constants.COLOR_GREEN, (8, 8), 4)
            pygame.draw.circle(s, constants.COLOR_BLACK, (8, 8), 4, 1)
            return s
        elif name == 'crop_mature':
            s = make_surface(20, 24)
            pygame.draw.rect(s, constants.COLOR_ORANGE, (4, 6, 12, 16))
            pygame.draw.rect(s, constants.COLOR_BLACK, (4, 6, 12, 16), 1)
            return s
        elif name == 'bg_farm_top':
            s = make_surface(constants.FARM_END, constants.FARM_MID_Y)
            # Rich Deep Brown base
            s.fill((80, 50, 30)) 
            # High-contrast furrows (Ridge & Shadow)
            row_spacing = 40
            for j in range(0, constants.FARM_MID_Y, row_spacing):
                # Deep furrow shadow (lower side of ridge)
                pygame.draw.rect(s, (40, 25, 10), (0, j + 25, constants.FARM_END, 12))
                # Lighter ridge top (upper side)
                pygame.draw.rect(s, (115, 80, 50), (0, j + 5, constants.FARM_END, 8))
            # Intense dirt/stone texture
            for _ in range(400):
                rx, ry = random.randint(0, constants.FARM_END), random.randint(0, constants.FARM_MID_Y)
                c = random.choice([(60, 35, 20), (100, 70, 40)])
                pygame.draw.circle(s, c, (rx, ry), random.randint(1, 2))
            return s
        elif name == 'bg_farm_bottom':
            s = make_surface(constants.FARM_END, constants.SCREEN_HEIGHT - constants.FARM_MID_Y)
            s.fill((130, 170, 80)) # Harmonized grass
            # Dense grass/flower texture
            for _ in range(120):
                rx, ry = random.randint(0, constants.FARM_END), random.randint(0, constants.SCREEN_HEIGHT - constants.FARM_MID_Y)
                c = random.choice([(110, 150, 65), (140, 185, 95)])
                pygame.draw.line(s, c, (rx, ry), (rx, ry-3), 2)
                if random.random() < 0.1: # Small blue/yellow/white flowers
                    fc = random.choice([(255,255,255), (255,220,50), (80,150,255)])
                    pygame.draw.circle(s, fc, (rx, ry-4), 1)
            return s
        elif name == 'apple_tree':
            s = make_surface(constants.APPLE_TREE_SIZE[0], constants.APPLE_TREE_SIZE[1])
            # Premium procedural tree
            pygame.draw.rect(s, (80, 55, 35), (42, 65, 16, 35)) # Trunk
            # Layered foliage for depth
            pygame.draw.circle(s, (70, 130, 55), (50, 45), 42)
            pygame.draw.circle(s, (90, 160, 70), (35, 40), 28)
            pygame.draw.circle(s, (90, 160, 70), (65, 40), 28)
            pygame.draw.circle(s, (115, 190, 90), (50, 32), 22)
            return s
        elif name == 'bg_grass':
            s = make_surface(constants.HORSES_START - constants.FARM_END, constants.SCREEN_HEIGHT)
            s.fill(constants.COLOR_GRASS)
            return s
        elif name == 'bg_horses':
            s = make_surface(constants.SCREEN_WIDTH - constants.HORSES_START, constants.SCREEN_HEIGHT)
            s.fill(constants.COLOR_GRASS)
            return s
        elif name == 'wheat_seed':
             s = make_surface(16, 16)
             pygame.draw.circle(s, (200, 180, 50), (8, 8), 5)
             return s
        elif name == 'wheat':
             s = make_surface(20, 24)
             pygame.draw.rect(s, (220, 200, 60), (4, 4, 12, 18))
             return s
        return make_surface(10, 10)
