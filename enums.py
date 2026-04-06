from enum import Enum

class FoodType(Enum):
    APPLE = 0
    CARROT = 1
    WHEAT = 2

class HorseState(Enum):
    WAITING = 0
    HUNGRY = 1
    CRITICAL = 2
    DEAD = 3
    FED = 4

class PlayerState(Enum):
    EMPTY = 0
    CARRYING_SEED = 1
    CARRYING_CARROT = 2

class CropState(Enum):
    SEED = 0
    GROWING = 1
    MATURE = 2
