
import pygame

# Screen
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
FPS = 60

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 50, 50)
GREEN = (50, 255, 50)
BLUE = (50, 50, 255)
YELLOW = (255, 255, 0)
CYAN = (0, 255, 255)
MAGENTA = (255, 0, 255)
ORANGE = (255, 165, 0)
GRAY = (100, 100, 100)
GOLD = (255, 215, 0)

# Wand/Projectile Colors by Level
WAND_COLORS = [
    (255, 69, 0),    # Red-Orange (Fire)
    (0, 191, 255), 
    (50, 205, 50), 
    (255, 0, 0)      
]

# Biomes Colors
FOREST_BG = (135, 206, 235)
FOREST_GROUND = (34, 139, 34)
ICE_BG = (200, 230, 255)
ICE_GROUND = (240, 248, 255)
VOLCANO_BG = (40, 0, 0)
VOLCANO_GROUND = (70, 20, 20)

# Physics
GRAVITY = 0.5
JUMP_STRENGTH = -14
PLAYER_SPEED = 6
PROJECTILE_SPEED = 12
OGRE_SPEED = 3

# Game Stats
PLAYER_MAX_HEALTH = 500
BASE_WAND_DAMAGE = 20 # High enough to kill weak enemies in 1 hit
OGRE_HEALTH_BASE = 20 # 1 hit for Ogre initially
GOBLIN_HEALTH_BASE = 10 # 1 hit always initially
TROLL_HEALTH_BASE = 50 # 3 hits initially

# Economy
COIN_VALUE = 10
BOSS_COIN_VALUE = 200

# Ability Costs
COST_LIGHTNING = 100
COST_TORNADO = 300
COST_DRAGON = 1000

# Weapon Costs
COST_ARCANE_VOLLEY = 1500
COST_VOID_LANCE = 2000
COST_FIRE_RING = 5000

# Shop Stat Upgrades (Permanent)
SHOP_UPGRADES_LIST = [
    {"id": "PERMA_DMG", "name": "Runic Power", "cost": 500, "desc": "+10% Base Damage (Permanent)", "stat": "damage_multiplier", "val": 0.1},
    {"id": "PERMA_HP", "name": "Titan Heart", "cost": 400, "desc": "+50 Max HP (Permanent)", "stat": "max_health", "val": 50},
    {"id": "PERMA_SPEED", "name": "Wind Soul", "cost": 400, "desc": "+Attack Speed (Permanent)", "stat": "attack_speed_boost", "val": 5}
]

# Wave Settings
ENEMIES_PER_WAVE_BASE = 5 # Starts low
TOTAL_WAVES = 9999 # Infinite

# Dimensions
PLAYER_SIZE = 60
OGRE_SIZE = 70
BOSS_SIZE = 150
PROJECTILE_RADIUS = 12 # Slightly larger

# Dragon Boss Stats (Story Mode - HARD)
DRAGON_BOSS_HEALTH = 15000 # Was 5000
DRAGON_BOSS_DAMAGE = 80    # Was 50
DRAGON_BOSS_SPEED = 5
DRAGON_BOSS_SIZE = 300     # Bigger

# Game Modes
MODE_STORY = "STORY"
MODE_INFINITE = "INFINITE"
