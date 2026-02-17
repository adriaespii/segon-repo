import pygame
import sys
import random
import math
import json
from src.config import *
from src.assets import *
from src.entities import Wizard, Enemy, Projectile, EnemyProjectile, DragonBoss
from src.network import Network
import socket
import pickle

# Initialize Pygame
pygame.init()
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Wizard vs Ogres: Ultimate Edition")
clock = pygame.time.Clock()

# Fonts
font = pygame.font.SysFont("Arial", 36, bold=True)
small_font = pygame.font.SysFont("Arial", 24)
card_font = pygame.font.SysFont("Arial", 20, bold=True)
shop_font = pygame.font.SysFont("Arial", 28, bold=True)

# Game State
# MENU, PLAYING, SHOP, CARD_SELECT, GAME_OVER, VICTORY
game_state = "MENU"
# GAME_MODE: "STORY" or "INFINITE"
GAME_MODE = "STORY" 
current_biome = "FOREST"
current_wave = 1
enemies_killed_in_wave = 0
total_enemies_spawned_in_wave = 0
score = 0

# Entity Groups
all_sprites = pygame.sprite.Group()
projectiles = pygame.sprite.Group()
enemies = pygame.sprite.Group()
enemy_projectiles = pygame.sprite.Group()

# Player
wizard = Wizard(100, SCREEN_HEIGHT - 50)
all_sprites.add(wizard)

# Particles & Effects
particles = []
active_effects = [] # For Tornado, Dragon visuals

# Global Store for resetting logic
# We persist coins across runs? No, usually roguelike resets. 
# But user said "Menu inicial... tienda... monedas".
# Maybe consistent progression or just within the run?
# Let's assume persistent for this session, but reset on full restart?
# Actually "Menu inicial" implies a main menu before starting.
# Let's make coins persist in memory (session) but skills reset?
# Or roguelite style: coins are collected in run, then shop is accessible?
# User phrasing: "menu inicial, donde haya un menu para la tienda".
# So: Main Menu -> Shop (buy perma upgrades?) -> Play.
# Or: Play -> Get Coins -> Die/Win -> Main Menu -> Shop.
# Let's go with: Coins are persistent globally. Skills bought are permanent for the user profile.

TOTAL_COINS = 0
CURRENT_XP = 0
CURRENT_LEVEL = 1
XP_TO_NEXT_LEVEL = 100
UNLOCKED_ABILITIES = { 
    "LIGHTNING": False, "TORNADO": False, "DRAGON": False,
    "ARCANE_VOLLEY": False, "VOID_LANCE": False, "FIRE_RING": False
}
SHOP_UPGRADES_STATE = {} # Key: ID, Value: Level
shop_scroll_y = 0
shop_return_target = "MENU" # Tracks where to go after closing shop
gray = (100, 100, 100) # Defined gray here used in draw_shop

# Multiplayer Globals
net = Network()
is_multiplayer = False
is_host = False
mp_game_mode = "COOP" # "COOP" or "PVP"
remote_wizard = None # The other player (If Host -> P2, If Client -> P1)
mp_status_msg = ""
mp_input_ip = "127.0.0.1" # Default IP to join
mp_interfaces = []
mp_selected_interface_idx = 0
try:
    with open("server_ip.txt", "r") as f:
        content = f.read().strip()
        if content: mp_input_ip = content
except: pass
mp_input_active = False   # Is user typing IP?


SAVE_FILE = "save_game.json"

def save_data():
    global TOTAL_COINS, UNLOCKED_ABILITIES, SHOP_UPGRADES_STATE
    data = {
        "coins": TOTAL_COINS,
        "xp": CURRENT_XP,
        "level": CURRENT_LEVEL,
        "abilities": UNLOCKED_ABILITIES,
        "upgrades": SHOP_UPGRADES_STATE
    }
    try:
        with open(SAVE_FILE, "w") as f:
            json.dump(data, f)
    except Exception as e:
        print(f"Error saving data: {e}")

def load_data():
    global TOTAL_COINS, UNLOCKED_ABILITIES, SHOP_UPGRADES_STATE
    try:
        with open(SAVE_FILE, "r") as f:
            data = json.load(f)
            TOTAL_COINS = data.get("coins", 0)
            CURRENT_XP = data.get("xp", 0)
            CURRENT_LEVEL = data.get("level", 1)
            # Recalculate xp needed?
            XP_TO_NEXT_LEVEL = 100 * (1.2 ** (CURRENT_LEVEL - 1))
            
            CURRENT_XP = data.get("xp", 0)
            CURRENT_LEVEL = data.get("level", 1)
            # Recalculate xp needed?
            XP_TO_NEXT_LEVEL = 100 * (1.2 ** (CURRENT_LEVEL - 1))
            
            saved_abilities = data.get("abilities", {})
            # Update existing dict to keep keys
            for k, v in saved_abilities.items():
                if k in UNLOCKED_ABILITIES:
                    UNLOCKED_ABILITIES[k] = v
            SHOP_UPGRADES_STATE = data.get("upgrades", {})
    except FileNotFoundError:
        pass # No save file yet
    except Exception as e:
        print(f"Error loading data: {e}")
        
# Load immediately on import/run
load_data()

def gain_xp(amount):
    global CURRENT_XP, CURRENT_LEVEL, XP_TO_NEXT_LEVEL, UNLOCKED_ABILITIES, wizard
    CURRENT_XP += amount
    
    while CURRENT_XP >= XP_TO_NEXT_LEVEL:
        CURRENT_XP -= XP_TO_NEXT_LEVEL
        CURRENT_LEVEL += 1
        # Recalculate
        XP_TO_NEXT_LEVEL = int(100 * (1.2 ** (CURRENT_LEVEL - 1)))
        
        # Level Up Rewards (Unlock Abilities)
        if CURRENT_LEVEL >= 3 and not UNLOCKED_ABILITIES["LIGHTNING"]:
            UNLOCKED_ABILITIES["LIGHTNING"] = True
        if CURRENT_LEVEL >= 5 and not UNLOCKED_ABILITIES["TORNADO"]:
            UNLOCKED_ABILITIES["TORNADO"] = True
        if CURRENT_LEVEL >= 8 and not UNLOCKED_ABILITIES["ARCANE_VOLLEY"]:
             UNLOCKED_ABILITIES["ARCANE_VOLLEY"] = True
             if "ARCANE_VOLLEY" not in wizard.unlocked_weapons: wizard.unlocked_weapons.append("ARCANE_VOLLEY")
        if CURRENT_LEVEL >= 12 and not UNLOCKED_ABILITIES["VOID_LANCE"]:
             UNLOCKED_ABILITIES["VOID_LANCE"] = True
             if "VOID_LANCE" not in wizard.unlocked_weapons: wizard.unlocked_weapons.append("VOID_LANCE")
        if CURRENT_LEVEL >= 15 and not UNLOCKED_ABILITIES["FIRE_RING"]:
             UNLOCKED_ABILITIES["FIRE_RING"] = True
             if "FIRE_RING" not in wizard.unlocked_weapons: wizard.unlocked_weapons.append("FIRE_RING")
        
        save_data()
# (Effects are now imported from src.assets)

def cast_lightning():
    # Chain Lightning: Zap closest, then zap from that to next closest
    if not enemies: return
    
    # Find up to 3 targets
    targets = []
    
    # 1. Closest to Wizard
    sorted_enemies = sorted(enemies, key=lambda e: math.hypot(e.rect.centerx - wizard.rect.centerx, e.rect.centery - wizard.rect.centery))
    if sorted_enemies:
        t1 = sorted_enemies[0]
        if math.hypot(t1.rect.centerx - wizard.rect.centerx, t1.rect.centery - wizard.rect.centery) < 700:
            targets.append(t1)
            
            # 2. Closest to T1 (excluding T1)
            others = [e for e in enemies if e != t1]
            if others:
                t2 = min(others, key=lambda e: math.hypot(e.rect.centerx - t1.rect.centerx, e.rect.centery - t1.rect.centery))
                if math.hypot(t2.rect.centerx - t1.rect.centerx, t2.rect.centery - t1.rect.centery) < 400:
                    targets.append(t2)
                    
                    # 3. Closest to T2
                    others2 = [e for e in others if e != t2]
                    if others2:
                        t3 = min(others2, key=lambda e: math.hypot(e.rect.centerx - t2.rect.centerx, t2.rect.centery - t2.rect.centery))
                        if math.hypot(t3.rect.centerx - t2.rect.centerx, t3.rect.centery - t2.rect.centery) < 400:
                            targets.append(t3)

    # Apply Damage & Visuals
    prev_pos = wizard.rect.center
    for t in targets:
        t.health -= 5 # High damage
        
        # Visual Bolt from prev to current
        active_effects.append({
            "type": "LIGHTNING", 
            "start": prev_pos, 
            "end": t.rect.center, 
            "life": 15
        })
        prev_pos = t.rect.center
        
        if t.health <= 0:
            kill_enemy(t)

def cast_tornado():
    # Spawn 2 localized tornado objects that move outward
    # We need to track them in active_effects and handle collision logic THERE,
    # because they need to move over time.
    
    # Left Tornado
    active_effects.append({
        "type": "TORNADO_MOVING", 
        "x": wizard.rect.centerx - 50, 
        "y": wizard.rect.centery, 
        "life": 100, 
        "dir": -1
    })
    # Right Tornado
    active_effects.append({
        "type": "TORNADO_MOVING", 
        "x": wizard.rect.centerx + 50, 
        "y": wizard.rect.centery, 
        "life": 100, 
        "dir": 1
    })

def cast_dragon():
    # Kill all enemies on screen
    for e in enemies:
        e.health = 0
        kill_enemy(e)
    
    # Visual
    active_effects.append({"type": "DRAGON", "x": SCREEN_WIDTH//2, "y": SCREEN_HEIGHT//2, "life": 120})


MISSIONS = [
    {"id": "KILL_OGRES", "desc": "Slay 5 Ogres", "target": 5, "current": 0, "type": "KILL_ENEMY", "etype": "OGRE", "reward_xp": 100},
    {"id": "KILL_ARCHERS", "desc": "Slay 3 Archers", "target": 3, "current": 0, "type": "KILL_ENEMY", "etype": "SKELETON_ARCHER", "reward_xp": 150},
    {"id": "SURVIVE_WAVE", "desc": "Reach Wave 5", "target": 5, "current": 0, "type": "REACH_WAVE", "reward_xp": 300}
]

def check_mission_progress(event_type, **kwargs):
    global MISSIONS
    for m in MISSIONS:
        if m["current"] >= m["target"]: continue # Already done? Or remove?
        
        if m["type"] == event_type:
            if m["type"] == "KILL_ENEMY":
                if kwargs.get("etype") == m["etype"]:
                    m["current"] += 1
            elif m["type"] == "REACH_WAVE":
                m["current"] = kwargs.get("wave")
            
                if m["id"] == "KILL_OGRES" and m["type"] == "KILL_ENEMY":
                     # This logic is duplicate of kill_enemy for now.
                     pass 


def kill_enemy(enemy):
    global score, enemies_killed_in_wave, TOTAL_COINS, game_state
    if not enemy.alive(): return # Already dead
    
    # Victory Check (Dragon Boss)
    if enemy.enemy_type == "DRAGON_BOSS":
        game_state = "VICTORY"
        UNLOCKED_ABILITIES["DRAGON"] = True
        # Bonus Coins
        TOTAL_COINS += 5000
        save_data()
    
    enemy.kill()
    enemies_killed_in_wave += 1
    score += 10 * current_wave
    
    # Coins
    is_boss = enemy.rect.width > 100
    coin_val = BOSS_COIN_VALUE if is_boss else COIN_VALUE
    if enemy.enemy_type == "DRAGON_BOSS": coin_val = 1000
    
    TOTAL_COINS += coin_val
    gain_xp(coin_val // 2) # XP is related to coins/difficulty
    
    # Check missions
    for m in MISSIONS:
        if m["type"] == "KILL_ENEMY" and m["etype"] == enemy.enemy_type:
             m["current"] += 1
             if m["current"] >= m["target"]:
                 gain_xp(m["reward_xp"])
                 # Difficulty Up
                 m["current"] = 0
                 m["target"] += 5
                 m["reward_xp"] += 50
                 save_data()
    
    # Particles
    for _ in range(15):
        particles.append({
            'x': enemy.rect.centerx + random.randint(-15, 15),
            'y': enemy.rect.centery + random.randint(-15, 15),
            'life': 30, 'max_life': 30, 'size': random.randint(3, 8), 'color': (0, 255, 0)
        })

# --- UI STATES ---

def draw_menu(surface):
    # 1. Background & Atmosphere
    # Fill specific sky color first to prevent black voids if assets fail
    surface.fill((20, 10, 30))
    draw_background_scenery(surface, "FOREST", SCREEN_WIDTH, SCREEN_HEIGHT)
    
    ground_y = SCREEN_HEIGHT - 80
    
    # Subtle Overlay (just to unify colors, not hide them)
    s_overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    s_overlay.fill((10, 20, 30, 80)) # Blue-ish tint, low alpha
    surface.blit(s_overlay, (0,0))

    cx = SCREEN_WIDTH // 2
    cy = SCREEN_HEIGHT // 2
    
    # 2. Hero Character (The Wizard) - LEFT SIDE
    # Position him at ~25% width
    wiz_x = int(SCREEN_WIDTH * 0.3)
    wiz_y = ground_y - 20
    draw_scaled_wizard(surface, wiz_x, wiz_y, scale=3.0)
    
    # Magical Particles around Wizard
    t = pygame.time.get_ticks()
    random.seed(t // 50) 
    for _ in range(8):
        sx = wiz_x + random.randint(-100, 100)
        sy = wiz_y - 200 - random.randint(0, 300)
        alpha = random.randint(150, 255)
        radius = random.randint(2, 4)
        if random.random() < 0.2: radius += 2 # Occasional big spark
        
        s_part = pygame.Surface((radius*2, radius*2), pygame.SRCALPHA)
        pygame.draw.circle(s_part, (255, 230, 150, alpha), (radius, radius), radius)
        surface.blit(s_part, (sx, sy))
    
    # 3. UI Section - RIGHT SIDE
    ui_center_x = int(SCREEN_WIDTH * 0.7)
    
    # Epic Title
    title_text = "WIZARD vs OGRES"
    # Use a nice bold font
    title_font = pygame.font.SysFont("Verdana", 60, bold=True)
    
    # Shadow
    shad = title_font.render(title_text, True, (0, 0, 0))
    shad_rect = shad.get_rect(center=(ui_center_x + 4, 104))
    surface.blit(shad, shad_rect)
    
    # Main Title
    tit = title_font.render(title_text, True, (255, 200, 50)) 
    tit_rect = tit.get_rect(center=(ui_center_x, 100))
    surface.blit(tit, tit_rect)
    
    sub_font = pygame.font.SysFont("Arial", 24, italic=True)
    sub = sub_font.render("- ENCHANTED FOREST EDITION -", True, (150, 220, 255))
    surface.blit(sub, sub.get_rect(center=(ui_center_x, 150)))

    # 4. Menu Options (Right Side)
    mouse_pos = pygame.mouse.get_pos()
    menu_opts = [
        {"text": "STORY MODE", "key": "1", "action": "STORY"},
        {"text": "INFINITE MODE", "key": "2", "action": "INFINITE"},
        {"text": "MULTIPLAYER (LAN)", "key": "M", "action": "MULTI"},
        {"text": "ITEM SHOP", "key": "S", "action": "SHOP"},
        {"text": "EXIT", "key": "Q", "action": "QUIT"}
    ]
    
    start_y = 220 # Moved up slightly to fit more options
    btn_w, btn_h = 280, 55
    spacing = 15
    
    for i, opt in enumerate(menu_opts):
        btn_y = start_y + i * (btn_h + spacing)
        rect = pygame.Rect(ui_center_x - btn_w//2, btn_y, btn_w, btn_h)
        
        is_hover = rect.collidepoint(mouse_pos)
        
        # Style
        # Glass morphism style
        bg_col = (10, 10, 20, 180) if not is_hover else (50, 50, 90, 220)
        border_col = (100, 100, 150) if not is_hover else (255, 220, 100)
        
        # Draw Button Box
        s_btn = pygame.Surface((btn_w, btn_h), pygame.SRCALPHA)
        pygame.draw.rect(s_btn, bg_col, (0,0,btn_w,btn_h), border_radius=12)
        pygame.draw.rect(s_btn, border_col, (0,0,btn_w,btn_h), 2, border_radius=12)
        surface.blit(s_btn, rect)
        
        # Text
        txt_col = (220, 220, 220) if not is_hover else (255, 255, 255)
        mtxt = shop_font.render(opt["text"], True, txt_col)
        surface.blit(mtxt, mtxt.get_rect(center=rect.center))
        
        hint = small_font.render(f"[{opt['key']}]", True, (120, 120, 120))
        surface.blit(hint, (rect.right + 10, rect.centery - 10))

    # 5. Bottom Stats Bar
    bar_y = SCREEN_HEIGHT - 40
    pygame.draw.rect(surface, (0,0,0,150), (0, bar_y, SCREEN_WIDTH, 40))
    
    c_txt = small_font.render(f"GOLD: {TOTAL_COINS}", True, GOLD)
    surface.blit(c_txt, (20, bar_y + 8))
    
    ver = small_font.render("v2.4 (Multiplayer Update)", True, GRAY)
    surface.blit(ver, (SCREEN_WIDTH - 180, bar_y + 8))

def draw_shop(surface):
    global TOTAL_COINS
    surface.fill((20, 20, 30))
    
    title = font.render(f"MAGIC SHOP", True, MAGENTA)
    coins_txt = font.render(f"Your Coins: {TOTAL_COINS}", True, GOLD)
    
    exit_label = "Press [ESC] to Return"
    if shop_return_target == "PLAYING":
        exit_label = "Press [ENTER] to Start Next Wave"
    
    exit_txt = small_font.render(exit_label, True, WHITE)
    
    # Header Overlay (to cover scrolled items)
    pygame.draw.rect(surface, (20, 20, 30), (0, 0, SCREEN_WIDTH, 130))
    surface.blit(title, (50, 50))
    surface.blit(coins_txt, (50, 100))
    surface.blit(exit_txt, (50, SCREEN_HEIGHT - 50))
    
    items = [
        {"id": "LIGHTNING", "name": "Lightning Strike (Auto)", "cost": COST_LIGHTNING, "desc": "Zaps closest enemy periodically."},
        {"id": "TORNADO", "name": "Wind Blast (Key: T)", "cost": COST_TORNADO, "desc": "Push enemies back with 'T'."},
        {"id": "DRAGON", "name": "Dragon Summon (Key: R)", "cost": COST_DRAGON, "desc": "Summon Dragon to clear screen."},
        {"id": "ARCANE_VOLLEY", "name": "Arcane Volley (Key: 2)", "cost": COST_ARCANE_VOLLEY, "desc": "Fires 5 unstable magic orbs."},
        {"id": "VOID_LANCE", "name": "Void Lance (Key: 3)", "cost": COST_VOID_LANCE, "desc": "Piercing beam of dark energy."},
        {"id": "FIRE_RING", "name": "Inferno Ring (Key: 4)", "cost": COST_FIRE_RING, "desc": "Massive ring of fire destruction."}
    ]
    
    mouse_pos = pygame.mouse.get_pos()
    click = pygame.mouse.get_pressed()[0]
    
    start_y = 200
    for i, item in enumerate(items):
        y = start_y + i * 120 + shop_scroll_y
        rect = pygame.Rect(50, y, 800, 100)
        
        is_owned = UNLOCKED_ABILITIES[item["id"]]
        color = (50, 50, 50)
        if is_owned: 
            color = (30, 80, 30) # Owned
        elif rect.collidepoint(mouse_pos) and (y > 100 and y < SCREEN_HEIGHT - 60):
             if TOTAL_COINS >= item["cost"]:
                color = (80, 80, 80) # Affordable Highlight
                if click:
                    TOTAL_COINS -= item["cost"]
                    UNLOCKED_ABILITIES[item["id"]] = True
                    # Immediate unlock if playing
                    if item["id"] in ["ARCANE_VOLLEY", "VOID_LANCE", "FIRE_RING"] and item["id"] not in wizard.unlocked_weapons:
                        wizard.unlocked_weapons.append(item["id"])
                    save_data()
                    pygame.time.wait(200)
        
        pygame.draw.rect(surface, color, rect, border_radius=10)
        pygame.draw.rect(surface, WHITE, rect, 2, border_radius=10)
        
        name_s = shop_font.render(f"{item['name']}", True, CYAN if is_owned else WHITE)
        cost_s = shop_font.render("OWNED" if is_owned else f"{item['cost']} G", True, GOLD)
        desc_s = small_font.render(item['desc'], True, GRAY)
        
        surface.blit(name_s, (70, y + 20))
        surface.blit(cost_s, (700, y + 35))
        surface.blit(desc_s, (70, y + 60))
        
    # --- Permanent Upgrades Section ---
    section_y_base = start_y + len(items) * 120 + 20
    sect_title = shop_font.render("PERMANENT UPGRADES", True, ORANGE)
    surface.blit(sect_title, (50, section_y_base + shop_scroll_y))
    
    start_y_upg = section_y_base + 50
    for i, item in enumerate(SHOP_UPGRADES_LIST):
        y = start_y_upg + i * 120 + shop_scroll_y
        rect = pygame.Rect(50, y, 800, 100)
        
        lvl = SHOP_UPGRADES_STATE.get(item["id"], 0)
        cost = item["cost"] * (lvl + 1)
        
        color = (50, 50, 60)
        if rect.collidepoint(mouse_pos) and (y > 100 and y < SCREEN_HEIGHT - 60):
             if TOTAL_COINS >= cost:
                color = (70, 70, 90) # Affordable
                if click:
                    TOTAL_COINS -= cost
                    SHOP_UPGRADES_STATE[item["id"]] = lvl + 1
                    save_data()
                    pygame.time.wait(200)
    
        pygame.draw.rect(surface, color, rect, border_radius=10)
        pygame.draw.rect(surface, (100, 100, 255), rect, 2, border_radius=10)
        
        name_s = shop_font.render(f"{item['name']} (Lvl {lvl})", True, WHITE)
        cost_s = shop_font.render(f"{cost} G", True, GOLD)
        desc_s = small_font.render(item['desc'], True, GRAY)
        
        surface.blit(name_s, (70, y + 20))
        surface.blit(cost_s, (700, y + 35))
        surface.blit(desc_s, (70, y + 60))
        
    # Scrollbar indicator (simple)
    total_h = section_y_base + 50 + len(SHOP_UPGRADES_LIST) * 120
    if total_h > SCREEN_HEIGHT:
        bar_h = (SCREEN_HEIGHT / total_h) * SCREEN_HEIGHT
        bar_y = (-shop_scroll_y / total_h) * SCREEN_HEIGHT
        pygame.draw.rect(surface, (100, 100, 100), (SCREEN_WIDTH - 10, bar_y, 10, bar_h))

    # Header Overlay (to cover scrolled items)
    pygame.draw.rect(surface, (20, 20, 30), (0, 0, SCREEN_WIDTH, 130))
    surface.blit(title, (50, 50))
    surface.blit(coins_txt, (50, 100))
    # surface.blit(exit_txt, (50, SCREEN_HEIGHT - 50)) # Draw exit text on top of everything? No, footer better.
    
    # Footer Overlay
    pygame.draw.rect(surface, (20, 20, 30), (0, SCREEN_HEIGHT - 60, SCREEN_WIDTH, 60))
    surface.blit(exit_txt, (50, SCREEN_HEIGHT - 50))

# --- GAME LOGIC HELPERS ---

def reset_run(mode=None):
    global score, current_wave, enemies_killed_in_wave, total_enemies_spawned_in_wave
    global current_biome, game_state, particles, GAME_MODE
    global enemies, projectiles, enemy_projectiles, active_effects, spawn_timer
    
    if mode: GAME_MODE = mode
    
    score = 0
    current_wave = 1
    enemies_killed_in_wave = 0
    total_enemies_spawned_in_wave = 0
    current_biome = "FOREST"
    
    enemies.empty()
    projectiles.empty()
    enemy_projectiles.empty()
    all_sprites.empty()
    particles.clear()
    active_effects.clear()
    spawn_timer = 0
    global boss_intro_timer
    boss_intro_timer = 0
    
    wizard.__init__(100, SCREEN_HEIGHT - 50) # Reset hp/stats
    # Reset upgrade levels
    wizard.upgrade_levels = {
            "SPEED": 0,
            "DAMAGE": 0,
            "MULTISHOT": 0,
            "PIERCING": 0,
            "HEALTH": 0
    }
    
    # Apply bought upgrades (Abilities)
    wizard.abilities = UNLOCKED_ABILITIES.copy()
    
    # Populate unlocked weapons
    wizard.unlocked_weapons = ["DEFAULT"]
    if UNLOCKED_ABILITIES["ARCANE_VOLLEY"]: wizard.unlocked_weapons.append("ARCANE_VOLLEY")
    if UNLOCKED_ABILITIES["VOID_LANCE"]: wizard.unlocked_weapons.append("VOID_LANCE")
    if UNLOCKED_ABILITIES["FIRE_RING"]: wizard.unlocked_weapons.append("FIRE_RING")
    
    # Apply Permanent Stats from Shop
    # {"id": "PERMA_DMG", "val": 0.1, "stat": "damage_multiplier"}
    for upg in SHOP_UPGRADES_LIST:
        lvl = SHOP_UPGRADES_STATE.get(upg["id"], 0)
        if lvl > 0:
            if upg["stat"] == "damage_multiplier":
                wizard.damage_multiplier += (upg["val"] * lvl)
            elif upg["stat"] == "max_health":
                wizard.max_health += (upg["val"] * lvl)
                wizard.health = wizard.max_health
            elif upg["stat"] == "attack_speed_boost":
                wizard.attack_speed_boost += (upg["val"] * lvl)
    
    all_sprites.add(wizard)
    
    global remote_wizard
    if is_multiplayer:
        # Create remote wizard instance (Target dummy for rendering/logic)
        remote_wizard = Wizard(200, SCREEN_HEIGHT - 50) # Start slightly offset
        remote_wizard.image.fill((100, 100, 255)) # Blue tint to distinguish
        all_sprites.add(remote_wizard)
    else:
        remote_wizard = None
        
    game_state = "PLAYING"

def spawn_enemy_logic():
    global enemies, particles, projectiles, enemy_projectiles, active_effects, score, current_wave, spawn_timer, wizard, enemies_killed_in_wave
    
    # --- STORY MODE LOGIC ---
    if GAME_MODE == "STORY":
        # Wave 10: FINAL BOSS
        if current_wave == 10:
             boss_exists = False
             for e in enemies:
                 if e.enemy_type == "DRAGON_BOSS": 
                     boss_exists = True
                     break
             
             if not boss_exists and enemies_killed_in_wave == 0:
                 # Trigger Cinematic Entrance instead of direct spawn
                 global game_state, boss_intro_timer
                 game_state = "BOSS_INTRO"
                 boss_intro_timer = 0
                 return
             return # Only Boss in Wave 10
             
        # Regular Waves (1-9)
        # Cap enemies
        cap = 4 + current_wave
        if len(enemies) < cap:
            side = random.choice([-50, SCREEN_WIDTH + 50])
            roll = random.random()
            etype = "OGRE"
            
            # Biome-specific spawns
            if current_biome == "ICE": # Waves 4-6
                if roll < 0.3: etype = "TROLL"
                elif roll < 0.6: etype = "GOBLIN"
                else: etype = "OGRE"
            elif current_biome == "VOLCANO": # Waves 7-9
                if roll < 0.2: etype = "TROLL"
                elif roll < 0.5: etype = "SKELETON_ARCHER"
                elif roll < 0.8: etype = "GOBLIN"
                else: etype = "OGRE"
            else: # FOREST (Waves 1-3)
                if roll < 0.3: etype = "GOBLIN"
                else: etype = "OGRE"
            
            e = Enemy(side, SCREEN_HEIGHT - 50, etype)
            
            # Story Mode Harder Scaling
            if GAME_MODE == "STORY":
                 e.health *= 1.5 # 50% more HP
                 e.damage *= 1.2 # 20% more damage
                 if current_wave >= 7: # Volcano Hard
                     e.speed += 0.5 
            
            enemies.add(e)
            all_sprites.add(e)

    # --- INFINITE MODE LOGIC ---
    else:
        # Endless waves, scaling difficulty
        # Boss every 10 waves (Ogre King or Dragon?)
        # Let's keep Ogre King for infinite mode bosses for now, or Dragon at 50?
        if current_wave % 10 == 0:
            boss_exists = False
            for e in enemies:
                if e.enemy_type == "OGRE_KING": 
                    boss_exists = True
                    break
            
            if not boss_exists and enemies_killed_in_wave == 0:
                side = random.choice([-100, SCREEN_WIDTH + 100])
                e = Enemy(side, SCREEN_HEIGHT - 50, "OGRE_KING")
                enemies.add(e)
                all_sprites.add(e)
                return
        
        # Regular Spawn
        cap = 5 + int(current_wave * 1.5) # Scale faster
        if len(enemies) < cap:
            side = random.choice([-50, SCREEN_WIDTH + 50])
            roll = random.random()
            etype = "OGRE"
            
            # Progressive difficulty
            troll_chance = min(0.4, current_wave * 0.02)
            archer_chance = min(0.4, current_wave * 0.02)
            goblin_chance = 0.3
            
            if current_wave > 5 and roll < troll_chance: 
                 etype = "TROLL"
            elif current_wave > 2 and roll < (troll_chance + archer_chance):
                 etype = "SKELETON_ARCHER"
            elif roll < (troll_chance + archer_chance + goblin_chance): # Remaining pool
                 etype = "GOBLIN"
            
            e = Enemy(side, SCREEN_HEIGHT - 50, etype)
            enemies.add(e)
            all_sprites.add(e)

# Cards Logic (Same as before)
cards = []
def generate_upgrades():
    options = [
        {"type": "HEALTH", "name": "Vitality Boost", "desc": "+50 HP (Max & Heal)", "color": GREEN},
        {"type": "SPEED", "name": "Swift Caster", "desc": "+Attack Speed", "color": YELLOW},
        {"type": "DAMAGE", "name": "Arcane Power", "desc": "+25% Damage", "color": MAGENTA},
        {"type": "MULTISHOT", "name": "Fire Mastery", "desc": "Power Up! +Size +Damage", "color": CYAN},
        {"type": "PIERCING", "name": "Spectral Bolt", "desc": "Pierce +1 Enemy", "color": WHITE},
        {"type": "COINS", "name": "Treasure Hunter", "desc": "+500 Instant Coins", "color": GOLD},
    ]
    
    # Filter based on max level (3)
    valid_options = []
    for opt in options:
        t = opt["type"]
        # Unlimited upgrades: Health, Coins
        if t in ["HEALTH", "COINS"]:
            valid_options.append(opt)
        elif t in wizard.upgrade_levels:
            lvl_current = wizard.upgrade_levels[t]
            if lvl_current < 3:
                # Add level info. 
                # If current is 0, next is 1. Text: (1/3)
                # If current is 1, next is 2. Text: (2/3)
                # If current is 2, next is 3. Text: (MAX)
                next_lvl = lvl_current + 1
                tag = f"({next_lvl}/3)" if next_lvl < 3 else "(MAX)"
                
                opt_copy = opt.copy()
                opt_copy["name"] += f" {tag}"
                valid_options.append(opt_copy)
            # If maxed (3), do not append to valid_options
    
    # Be safe if we ran out of options (shouldn't happen with Health/Coins)
    if len(valid_options) < 3:
        # Pad with coins/health
        while len(valid_options) < 3:
            valid_options.append({"type": "COINS", "name": "Bonus Coins", "desc": "+200 Coins", "color": GOLD})
            
    selection = random.sample(valid_options, 3)
    return selection

def apply_card(card):
    global score
    t = card["type"]
    
    if t == "HEALTH":
        wizard.max_health += 50 
        wizard.health = wizard.max_health
    elif t == "COINS":
        global TOTAL_COINS
        TOTAL_COINS += 500
    else:
        # Stat upgrades
        if t in wizard.upgrade_levels and wizard.upgrade_levels[t] < 3:
            wizard.upgrade_levels[t] += 1
            
            if t == "SPEED":
                wizard.attack_speed_boost += 3 # Nerfed from 5
            elif t == "DAMAGE":
                wizard.damage_multiplier += 0.15 # Nerfed from 0.25
            elif t == "MULTISHOT":
                wizard.multishot += 1
            elif t == "PIERCING":
                wizard.piercing += 1
                
def draw_cards_ui(surface, events):
    global current_wave, enemies_killed_in_wave, total_enemies_spawned_in_wave, current_biome, game_state, cards, GAME_MODE
    
    # Overlay
    s = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    s.fill((0, 0, 0, 200))
    surface.blit(s, (0,0))
    
    title = font.render(f"WAVE {current_wave} CLEARED!", True, WHITE)
    surface.blit(title, title.get_rect(center=(SCREEN_WIDTH//2, 80)))
    
    global cards
    if not cards: cards = generate_upgrades()
    
    mouse_pos = pygame.mouse.get_pos()
    
    clicked = False
    for e in events:
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            clicked = True
    
    start_x = (SCREEN_WIDTH - (3 * 250 + 40)) // 2
    
    for i, c in enumerate(cards):
        rect = pygame.Rect(start_x + i * 270, 150, 250, 350)
        col = (40, 40, 40)
        if rect.collidepoint(mouse_pos):
            col = (60, 60, 60)
            if clicked:
                apply_card(c)
                cards = []
                global shop_return_target, spawn_timer
                
                # Next wave
                current_wave += 1
                enemies_killed_in_wave = 0
                total_enemies_spawned_in_wave = 0
                
                # BIOME TRANSITION LOGIC
                if GAME_MODE == "STORY":
                    if current_wave <= 3: current_biome = "FOREST"
                    elif current_wave <= 6: current_biome = "ICE"
                    elif current_wave <= 10: current_biome = "VOLCANO"
                else:
                    if current_wave > 2: current_biome = "ICE"
                    if current_wave > 4: current_biome = "VOLCANO"
                
                game_state = "PLAYING"
                scale = 1.0 # Reset scale? No, wizard scale is static?
                
                pygame.time.wait(200)
                return
        
        pygame.draw.rect(surface, col, rect, border_radius=10)
        pygame.draw.rect(surface, c["color"], rect, 4, border_radius=10)
        
        name = card_font.render(c["name"], True, c["color"])
        desc = small_font.render(c["desc"], True, WHITE)
        
        surface.blit(name, name.get_rect(center=rect.center))
        surface.blit(desc, desc.get_rect(midtop=(rect.centerx, rect.centery + 30)))

    # Draw Shop Hint
    shop_hint = shop_font.render("Press [S] to Open Shop", True, GOLD)
    surface.blit(shop_hint, shop_hint.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT - 50)))

# --- MAIN LOOPS ---
spawn_timer = 0
lightning_timer = 0 # For auto lightning
tornado_cooldown = 0
dragon_cooldown = 0
boss_intro_timer = 0

running = True
while running:
    # Global Input
    events = pygame.event.get()
    for e in events:
        if e.type == pygame.QUIT: running = False
        
        # Text Input for Multiplayer IP
        if game_state == "MP_MENU" and e.type == pygame.KEYDOWN:
            if e.key == pygame.K_BACKSPACE:
                mp_input_ip = mp_input_ip[:-1]
            elif e.key == pygame.K_RETURN:
                pass # Handled by button usually, or trigger connect
            elif len(mp_input_ip) < 15: # IPv4 max length roughly
                # Allow numbers and dots
                if e.unicode in "0123456789.":
                     mp_input_ip += e.unicode
    
    # State Machine
    if game_state == "MENU":
        draw_menu(screen)
        
        # Logic for buttons (must match draw_menu rects)
        ui_center_x = int(SCREEN_WIDTH * 0.7)
        start_y = 220
        btn_w, btn_h = 280, 55
        spacing = 15
        
        # Check clicks
        mouse_pos = pygame.mouse.get_pos()
        click = False
        for e in events:
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                click = True
        
        # Reconstruct rects to check collisions
        # 0: STORY
        rect_story = pygame.Rect(ui_center_x - btn_w//2, start_y, btn_w, btn_h)
        if rect_story.collidepoint(mouse_pos) and click:
            reset_run(mode="STORY")
            
        # 1: INFINITE
        rect_inf = pygame.Rect(ui_center_x - btn_w//2, start_y + (btn_h + spacing), btn_w, btn_h)
        if rect_inf.collidepoint(mouse_pos) and click:
            reset_run(mode="INFINITE")
            
        # 2: MULTIPLAYER
        rect_multi = pygame.Rect(ui_center_x - btn_w//2, start_y + 2*(btn_h + spacing), btn_w, btn_h)
        if rect_multi.collidepoint(mouse_pos) and click:
            mp_interfaces = net.get_local_interfaces() 
            mp_selected_interface_idx = 0
            mp_status_msg = "Select Network Interface"
            game_state = "MP_MENU"
            
        # 3: SHOP
        rect_shop = pygame.Rect(ui_center_x - btn_w//2, start_y + 3*(btn_h + spacing), btn_w, btn_h)
        if rect_shop.collidepoint(mouse_pos) and click:
            shop_return_target = "MENU"
            game_state = "SHOP"
            
        # 4: EXIT
        rect_exit = pygame.Rect(ui_center_x - btn_w//2, start_y + 4*(btn_h + spacing), btn_w, btn_h)
        if rect_exit.collidepoint(mouse_pos) and click:
            running = False

        keys = pygame.key.get_pressed()
        if keys[pygame.K_1]:
            is_multiplayer = False
            reset_run(mode="STORY")
        if keys[pygame.K_2]:
            is_multiplayer = False
            reset_run(mode="INFINITE")
        if keys[pygame.K_m]:
            # Initial Setup for MP Menu
            mp_interfaces = net.get_local_interfaces() 
            mp_selected_interface_idx = 0
            mp_status_msg = "Select Network Interface"
            game_state = "MP_MENU"
        if keys[pygame.K_s]:
            shop_return_target = "MENU"
            game_state = "SHOP"
        if keys[pygame.K_q]:
            running = False

    elif game_state == "MP_MENU":
        screen.fill((20, 10, 30))
        title = font.render("MULTIPLAYER LOBBY", True, CYAN)
        screen.blit(title, (SCREEN_WIDTH//2 - title.get_width()//2, 30))
        
        # --- INTERFACE SELECTION ---
        if not mp_interfaces:
            mp_interfaces = net.get_local_interfaces()
            
        int_lbl = small_font.render("Network Interface (Card):", True, GRAY)
        screen.blit(int_lbl, (50, 70))
        
        int_box = pygame.Rect(260, 65, 300, 30)
        pygame.draw.rect(screen, (40, 40, 60), int_box, border_radius=5)
        pygame.draw.rect(screen, WHITE, int_box, 1, border_radius=5)
        
        current_ip = mp_interfaces[mp_selected_interface_idx] if mp_interfaces else "None"
        ip_t = small_font.render(current_ip, True, WHITE)
        screen.blit(ip_t, (270, 68))
        
        # Cycle buttons
        btn_prev = pygame.Rect(230, 65, 25, 30)
        btn_next = pygame.Rect(565, 65, 25, 30)
        
        pygame.draw.rect(screen, (60, 60, 80), btn_prev, border_radius=3)
        pygame.draw.rect(screen, (60, 60, 80), btn_next, border_radius=3)
        screen.blit(small_font.render("<", True, WHITE), (237, 68))
        screen.blit(small_font.render(">", True, WHITE), (572, 68))
        
        mouse_pos = pygame.mouse.get_pos()
        click = False
        for e in events:
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                click = True
        
        if click:
            if btn_prev.collidepoint(mouse_pos):
                mp_selected_interface_idx = (mp_selected_interface_idx - 1) % len(mp_interfaces)
                if net.discovery.running: 
                    net.stop()
                    net.start_discovery(mp_interfaces[mp_selected_interface_idx])
            elif btn_next.collidepoint(mouse_pos):
                mp_selected_interface_idx = (mp_selected_interface_idx + 1) % len(mp_interfaces)
                if net.discovery.running:
                    net.stop()
                    net.start_discovery(mp_interfaces[mp_selected_interface_idx])

        # Start Discovery if not started
        if not net.discovery.running and mp_interfaces:
            net.start_discovery(mp_interfaces[mp_selected_interface_idx])
            
        # --- LEFT PANEL: DISCOVERED PLAYERS ---
        panel_rect = pygame.Rect(50, 100, 400, 400)
        pygame.draw.rect(screen, (30, 30, 40), panel_rect, border_radius=10)
        pygame.draw.rect(screen, (100, 100, 150), panel_rect, 2, border_radius=10)
        
        lbl = small_font.render("Players on Network:", True, GRAY)
        screen.blit(lbl, (60, 110))
        
        peers = net.discovery.get_peers()
        
        y_off = 150
        if not peers:
             txt = small_font.render("Scanning...", True, (100, 100, 100))
             screen.blit(txt, (60, 150))
             
        for ip, data in peers.items():
            p_rect = pygame.Rect(60, y_off, 380, 40)
            col = (50, 50, 60)
            if p_rect.collidepoint(mouse_pos):
                col = (70, 70, 90)
                if click and net.connection_status == "IDLE":
                    # SEND INVITE
                    mp_status_msg = f"Inviting {data['name']}..."
                    net.send_invite(ip, "WizardPlayer", mp_game_mode) # TODO: Custom Name
                    pygame.time.wait(200)

            pygame.draw.rect(screen, col, p_rect, border_radius=5)
            name_t = small_font.render(f"{data['name']} ({ip})", True, WHITE)
            screen.blit(name_t, (70, y_off + 10))
            
            # Invite Icon/Text
            inv_t = small_font.render("INVITE", True, GREEN)
            screen.blit(inv_t, (350, y_off + 10))
            
            y_off += 50

        # --- RIGHT PANEL: STATUS & MANUAL ---
        stat_lbl = small_font.render("Status:", True, GRAY)
        screen.blit(stat_lbl, (500, 110))
        
        st_col = YELLOW
        if net.connection_status == "CONNECTED": st_col = GREEN
        elif net.connection_status == "FAILED": st_col = RED
        elif net.connection_status == "INVITING": st_col = CYAN
        
        st_t = shop_font.render(net.connection_status, True, st_col)
        screen.blit(st_t, (500, 140))
        
        msg_t = small_font.render(mp_status_msg, True, WHITE)
        screen.blit(msg_t, (500, 180))

        # Manual IP Invite (Fallback)
        lbl_m = small_font.render("Manual IP Invite:", True, GRAY)
        screen.blit(lbl_m, (500, 250))
        
        ip_box = pygame.Rect(500, 280, 240, 40)
        pygame.draw.rect(screen, (20, 20, 30), ip_box)
        pygame.draw.rect(screen, (80, 80, 100), ip_box, 2)
        ip_s = shop_font.render(mp_input_ip, True, WHITE)
        screen.blit(ip_s, (510, 285))
        
        btn_inv = pygame.Rect(750, 280, 100, 40)
        col_btn = (50, 80, 50) if not btn_inv.collidepoint(mouse_pos) else (80, 120, 80)
        pygame.draw.rect(screen, col_btn, btn_inv, border_radius=5)
        btn_t = small_font.render("INVITE", True, WHITE)
        screen.blit(btn_t, (765, 288))
        
        if btn_inv.collidepoint(mouse_pos) and click and net.connection_status == "IDLE":
             if mp_input_ip:
                 mp_status_msg = f"Inviting {mp_input_ip}..."
                 net.send_invite(mp_input_ip, "WizardPlayer", mp_game_mode)
                 pygame.time.wait(200)

        # Game Mode Selector (Host Only or Global)
        mode_lbl = small_font.render("Game Mode:", True, GRAY)
        screen.blit(mode_lbl, (500, 350))
        
        mode_rect = pygame.Rect(650, 345, 150, 35)
        mode_col = GREEN if mp_game_mode == "COOP" else RED
        pygame.draw.rect(screen, mode_col, mode_rect, border_radius=5)
        
        mode_txt_s = shop_font.render(mp_game_mode, True, WHITE)
        screen.blit(mode_txt_s, mode_txt_s.get_rect(center=mode_rect.center))
        
        if click and mode_rect.collidepoint(mouse_pos):
             mp_game_mode = "PVP" if mp_game_mode == "COOP" else "COOP"

        # --- INCOMING INVITE POPUP ---
        if net.incoming_invite:
            # Draw Modal Overlay
            overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 180))
            screen.blit(overlay, (0,0))
            
            w, h = 500, 250
            cx, cy = SCREEN_WIDTH//2, SCREEN_HEIGHT//2
            rect = pygame.Rect(cx - w//2, cy - h//2, w, h)
            pygame.draw.rect(screen, (40, 40, 50), rect, border_radius=15)
            pygame.draw.rect(screen, GOLD, rect, 3, border_radius=15)
            
            title_inv = shop_font.render("GAME INVITATION", True, GOLD)
            screen.blit(title_inv, title_inv.get_rect(center=(cx, cy - 80)))
            
            from_t = font.render(f"From: {net.incoming_invite['name']}", True, WHITE)
            ip_t = small_font.render(f"({net.incoming_invite['ip']}) - Mode: {net.incoming_invite.get('mode', 'COOP')}", True, GRAY)
            screen.blit(from_t, from_t.get_rect(center=(cx, cy - 20)))
            screen.blit(ip_t, ip_t.get_rect(center=(cx, cy + 20)))
            
            # Yes / No Buttons
            btn_yes = pygame.Rect(cx - 150, cy + 60, 120, 50)
            btn_no = pygame.Rect(cx + 30, cy + 60, 120, 50)
            
            col_y = (0, 100, 0) if not btn_yes.collidepoint(mouse_pos) else (0, 150, 0)
            col_n = (100, 0, 0) if not btn_no.collidepoint(mouse_pos) else (150, 0, 0)
            
            pygame.draw.rect(screen, col_y, btn_yes, border_radius=8)
            pygame.draw.rect(screen, col_n, btn_no, border_radius=8)
            
            ty = shop_font.render("ACCEPT", True, WHITE)
            tn = shop_font.render("DECLINE", True, WHITE)
            screen.blit(ty, ty.get_rect(center=btn_yes.center))
            screen.blit(tn, tn.get_rect(center=btn_no.center))
            
            if click:
                if btn_yes.collidepoint(mouse_pos):
                    # Set Game Mode from Invite
                    if net.incoming_invite and "mode" in net.incoming_invite:
                        mp_game_mode = net.incoming_invite["mode"]
                    net.accept_invite()
                elif btn_no.collidepoint(mouse_pos):
                    net.decline_invite()

        # BACK BUTTON
        back_btn = pygame.Rect(50, 520, 150, 40)
        pygame.draw.rect(screen, (70, 50, 50), back_btn, border_radius=8)
        bt = small_font.render("BACK", True, WHITE)
        screen.blit(bt, bt.get_rect(center=back_btn.center))
             
        if back_btn.collidepoint(mouse_pos) and click:
            game_state = "MENU"
            net.stop()
        
        # STATUS DISPLAY & LOGIC
        status_col = YELLOW
        if net.connection_status == "CONNECTED":
            status_col = GREEN
            mp_status_msg = "Connected! Starting Game..."
        elif net.connection_status == "FAILED":
            status_col = RED
            mp_status_msg = "Connection Failed. Try again."
            # Allow reset
            reset_btn = pygame.Rect(SCREEN_WIDTH//2 - 100, 450, 200, 40)
            pygame.draw.rect(screen, (100, 0, 0), reset_btn)
            rt = small_font.render("Reset Network", True, WHITE)
            screen.blit(rt, rt.get_rect(center=reset_btn.center))
            if reset_btn.collidepoint(pygame.mouse.get_pos()) and pygame.mouse.get_pressed()[0]:
                net.connection_status = "IDLE"
                net.close()
                net = Network() # Re-init
        
        st = shop_font.render(mp_status_msg, True, status_col)
        screen.blit(st, st.get_rect(center=(SCREEN_WIDTH//2, 250)))

        # Transition to Game if Connected
        if net.connection_status == "CONNECTED":
            # Wait a moment to show success message
            pygame.display.flip()
            pygame.time.wait(1000)
            is_multiplayer = True
            is_host = net.is_host
            reset_run(mode="INFINITE")

    elif game_state == "SHOP":
        # Handle Scroll
        for e in events:
            if e.type == pygame.MOUSEWHEEL:
                shop_scroll_y += e.y * 30
                # Clamp scroll_y
                # Calculate max scroll down (total height of content - screen height)
                total_content_height = 200 + len(UNLOCKED_ABILITIES) * 120 + 20 + 50 + len(SHOP_UPGRADES_LIST) * 120
                max_scroll_down = -(total_content_height - SCREEN_HEIGHT + 130 + 60) # Header + Footer height
                if max_scroll_down > 0: max_scroll_down = 0 # If content is smaller than screen, no scroll
                
                if shop_scroll_y > 0: shop_scroll_y = 0
                if shop_scroll_y < max_scroll_down: shop_scroll_y = max_scroll_down
                
        draw_shop(screen)
        keys = pygame.key.get_pressed()
        if keys[pygame.K_ESCAPE] or (keys[pygame.K_RETURN] and shop_return_target == "PLAYING"):
            game_state = shop_return_target
            shop_scroll_y = 0 # Reset scroll
         
         # Arrow key scroll
        if keys[pygame.K_UP]: shop_scroll_y += 10
        if keys[pygame.K_DOWN]: shop_scroll_y -= 10
        
        # Clamp scroll_y for arrow keys too
        total_content_height = 200 + len(UNLOCKED_ABILITIES) * 120 + 20 + 50 + len(SHOP_UPGRADES_LIST) * 120
        max_scroll_down = -(total_content_height - SCREEN_HEIGHT + 130 + 60)
        if max_scroll_down > 0: max_scroll_down = 0
        
        if shop_scroll_y > 0: shop_scroll_y = 0
        if shop_scroll_y < max_scroll_down: shop_scroll_y = max_scroll_down
            
    elif game_state == "PLAYING":
        boss_active = None
        # --- MULTIPLAYER SYNC ---
        if is_multiplayer:
            if is_host:
                # HOST LOGIC
                # 1. Receive Inputs from Client (P2)
                # Non-blocking receive? Network code should handle checks
                try:
                    # Very simple protocol: Receive 1 packet per frame if available
                    data = net.receive() 
                    if data:
                        # Apply inputs to remote_wizard (P2)
                        remote_keys = data.get('keys')
                        remote_mouse = data.get('mouse') 
                        remote_click = data.get('click')
                        
                        if remote_keys:
                             remote_wizard.update(remote_keys, [])
                        
                        if remote_click and remote_mouse:
                             projs = remote_wizard.shoot(target_pos=remote_mouse)
                             if projs:
                                 projectiles.add(projs)
                                 all_sprites.add(projs)
                    state = {
                        'p1': {
                            'x': wizard.rect.x, 'y': wizard.rect.y, 'hp': wizard.health,
                            'face': wizard.facing_right, 'cast': wizard.is_casting
                        },
                        'p2': {
                            'x': remote_wizard.rect.x, 'y': remote_wizard.rect.y, 'hp': remote_wizard.health,
                            'face': remote_wizard.facing_right, 'cast': remote_wizard.is_casting
                        } if remote_wizard else None,
                        'enemies': [{'x': e.rect.x, 'y': e.rect.y, 'type': e.enemy_type} for e in enemies],
                        'projs': [{'x': p.rect.x, 'y': p.rect.y, 'c': p.color, 't': p.type} for p in projectiles]
                    }
                    net.send(state)
                    
                except Exception as e:
                    pass
                    
            else:
                # CLIENT LOGIC
                # 1. Send Inputs
                keys = pygame.key.get_pressed()
                input_data = {'keys': keys, 'mouse': pygame.mouse.get_pos(), 'click': pygame.mouse.get_pressed()[0]}
                net.send(input_data)
                
                # 2. Receive World State
                state = net.receive()
                if state:
                    if state.get('p2'):
                        wizard.rect.x = state['p2']['x']
                        wizard.rect.y = state['p2']['y']
                        wizard.health = state['p2']['hp']
                        wizard.facing_right = state['p2']['face']
                        wizard.is_casting = state['p2']['cast']
                        
                    if state.get('p1') and remote_wizard:
                        remote_wizard.rect.x = state['p1']['x']
                        remote_wizard.rect.y = state['p1']['y']
                        remote_wizard.health = state['p1']['hp']
                        remote_wizard.facing_right = state['p1']['face']
                        remote_wizard.is_casting = state['p1']['cast']
                        
                    # Sync Enemies
                    enemies.empty()
                    for ed in state.get('enemies', []):
                        e = Enemy(ed['x'], ed['y'], ed['type']) 
                        enemies.add(e)
                    
                    # Sync Projectiles (Visual only)
                    projectiles.empty()
                    for pd in state.get('projs', []):
                         p = Projectile(pd['x'], pd['y'], True, pd['c'], pd['t'])
                         projectiles.add(p)
                        
                # 3. SKIP LOGIC
                # Draw and continue
                # We need to skip the "Update Logic" block below if Client
                # Refactor: Encapsulate Update Logic in "if is_host or not is_multiplayer:"
                
        # --- UPDATE LOGIC (Host or Singleplayer) ---
        if not is_multiplayer or is_host:
            keys = pygame.key.get_pressed()
            # If Host, we handle our own input for Wizard 1
            wizard.update(keys, [])
            
            # If Host, update Remote Wizard (P2) using received inputs?
            # We need to store received inputs in a variable
            if is_multiplayer and is_host and remote_wizard:
                # Use stored P2 keys. For now dummy update.
                # remote_wizard.update(p2_keys, [])
                pass
                
            # Shooting
            if keys[pygame.K_SPACE] or pygame.mouse.get_pressed()[0]:
                projs = wizard.shoot(target_pos=pygame.mouse.get_pos())
                if projs: 
                    projectiles.add(projs)
                    all_sprites.add(projs)

            # Ability Inputs
            if UNLOCKED_ABILITIES["TORNADO"] and keys[pygame.K_t] and tornado_cooldown == 0:
                cast_tornado()
                tornado_cooldown = 300 
                
            if UNLOCKED_ABILITIES["DRAGON"] and keys[pygame.K_r] and dragon_cooldown == 0:
                cast_dragon()
                dragon_cooldown = 1800 
            
            if tornado_cooldown > 0: tornado_cooldown -= 1
            if dragon_cooldown > 0: dragon_cooldown -= 1
            
            # Auto Lightning
            if UNLOCKED_ABILITIES["LIGHTNING"]:
                if lightning_timer <= 0:
                    cast_lightning()
                    lightning_timer = 120 
                lightning_timer -= 1
                
            # Weapon Switching
            for e in events:
                if e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_1: wizard.select_weapon(1)
                    if e.key == pygame.K_2: wizard.select_weapon(2)
                    if e.key == pygame.K_3: wizard.select_weapon(3)
                    if e.key == pygame.K_4: wizard.select_weapon(4)
                        
            # Projectiles
            # Spawning
            # Spawning (COOP ONLY)
            if spawn_timer <= 0 and mp_game_mode == "COOP":
                spawn_enemy_logic()
                spawn_timer = 120 - (current_wave * 2) 
                if spawn_timer < 40: spawn_timer = 40
                
                is_boss_alive = False
                for e in enemies:
                    if e.enemy_type == "OGRE_KING":
                        is_boss_alive = True
                        break
                
                if is_boss_alive:
                    spawn_timer = 300 
                    
            spawn_timer -= 1

            # Projectiles
            projectiles.update(enemies) 
            enemy_projectiles.update() 
            
            for p in projectiles:
                if p.rect.left > SCREEN_WIDTH + 200 or p.rect.right < -200 or p.rect.bottom < -200 or p.rect.top > SCREEN_HEIGHT + 200:
                    p.kill()

            # PvP Collision Checks
            if is_multiplayer and mp_game_mode == "PVP":
                 # Check if any projectile hits any player
                 # Host Wizard
                 hits_p1 = pygame.sprite.spritecollide(wizard, projectiles, True)
                 if hits_p1:
                     damage = sum(p.damage for p in hits_p1)
                     wizard.health -= damage
                     for _ in range(5):
                        particles.append({'x': wizard.rect.centerx, 'y': wizard.rect.centery, 'life': 10, 'max_life': 10, 'size': 4, 'color': (255, 50, 50)})
                 
                 # Remote Wizard (P2)
                 if remote_wizard:
                     hits_p2 = pygame.sprite.spritecollide(remote_wizard, projectiles, True)
                     if hits_p2:
                         damage = sum(p.damage for p in hits_p2)
                         remote_wizard.health -= damage
                         for _ in range(5):
                            particles.append({'x': remote_wizard.rect.centerx, 'y': remote_wizard.rect.centery, 'life': 10, 'max_life': 10, 'size': 4, 'color': (255, 50, 50)})

            # Enemy Projectile Collisions
            # Check collisions for BOTH players if multiplayer
            targets = [wizard]
            if is_multiplayer and remote_wizard: targets.append(remote_wizard)
            
            for target in targets:
                hits = pygame.sprite.spritecollide(target, enemy_projectiles, True)
                for hit in hits:
                    target.health -= hit.damage
                    for _ in range(5):
                            particles.append({'x': target.rect.centerx, 'y': target.rect.centery, 'life': 10, 'max_life': 10, 'size': 4, 'color': (200, 50, 255)})
                    if target.health <= 0 and target == wizard: # Only Game Over if local player dies? Or shared?
                        pass # Let's keep playing until both die? Or revive?
                        # For simple coop, if P1 dies, Game Over.

            # Enemies Logic
            boss_active = None
            
            for e in enemies:
                # Update Enemy (Target closest player)
                target_rect = wizard.rect
                if is_multiplayer and remote_wizard:
                     d1 = math.hypot(e.rect.centerx - wizard.rect.centerx, e.rect.centery - wizard.rect.centery)
                     d2 = math.hypot(e.rect.centerx - remote_wizard.rect.centerx, e.rect.centery - remote_wizard.rect.centery)
                     if d2 < d1: target_rect = remote_wizard.rect
                     
                new_proj = e.update(target_rect)
                if new_proj:
                    enemy_projectiles.add(new_proj)
                    all_sprites.add(new_proj)
                
                if e.enemy_type in ["OGRE_KING", "DRAGON_BOSS"]:
                    boss_active = e
                
                # Attack Damage
                if e.enemy_type != "SKELETON_ARCHER":
                    if e.did_attack and e.damage > 0:
                        # Check against BOTH players
                        for target in targets:
                            dist_to_p = math.hypot(e.rect.centerx - target.rect.centerx, e.rect.centery - target.rect.centery)
                            if dist_to_p < 150:
                                target.health -= e.damage
                                if target.health < 0: target.health = 0
                                # Feedback...
                
                # Contact Logic
                for target in targets:
                    if e.rect.colliderect(target.rect):
                        target.health -= 1
                        if target.health < 0: target.health = 0
                        # Push
                        if e.rect.centerx < target.rect.centerx: target.rect.x += 5
                        else: target.rect.x -= 5
            
            # Check Game Over
            if wizard.health <= 0:
                game_state = "GAME_OVER"
            
            # Wave Logic... (Keep same)
            
            # Player Projectile Collisions make damage
            # Keep same...
            hits = pygame.sprite.groupcollide(enemies, projectiles, False, False)
            for enemy, projs in hits.items():
                for p in projs:
                    if not hasattr(p, 'hit_list'): p.hit_list = []
                    if enemy not in p.hit_list:
                        enemy.health -= p.damage
                        p.hit_list.append(enemy)
                        # ... Logic ...
                        if p.piercing <= 0: p.kill()
                        else: p.piercing -= 1
                if enemy.health <= 0:
                    kill_enemy(enemy)
            
            enemy_projectiles.empty()


        # Ensure boss_active is set (for Client mainly)
        if boss_active is None:
             for e in enemies:
                 if e.enemy_type in ["OGRE_KING", "DRAGON_BOSS"]:
                     boss_active = e
                     break

        # 2. Drawing
        draw_background_scenery(screen, current_biome, SCREEN_WIDTH, SCREEN_HEIGHT)
        
        # Draw Entities
        # Draw Entities
        for e in enemies:
            scale = 1.0
            # Boss scale handled in draw()
            # if e.rect.width > 90: scale = 1.5 
            
            # Use internal draw method which delegates
            e.draw(screen)
            
        for ep in enemy_projectiles:
            screen.blit(ep.image, ep.rect)
            
        if is_multiplayer and remote_wizard:
            # Draw remote wizard
            remote_wizard.draw(screen)
        wizard.draw(screen)
        for p in projectiles:
            p.draw(screen)
            
        for p in enemy_projectiles:
            ep_s = pygame.Surface((p.rect.width*3, p.rect.height*3), pygame.SRCALPHA)
            ep_cx, ep_cy = ep_s.get_width()//2, ep_s.get_height()//2
            ep_r = p.rect.width//2
            # Outer glow
            pygame.draw.circle(ep_s, (255, 50, 50, 40), (ep_cx, ep_cy), ep_r + 6)
            pygame.draw.circle(ep_s, (255, 80, 80, 80), (ep_cx, ep_cy), ep_r + 3)
            # Main body
            pygame.draw.circle(ep_s, (200, 0, 0), (ep_cx, ep_cy), ep_r)
            # Inner bright core
            pygame.draw.circle(ep_s, (255, 150, 100), (ep_cx, ep_cy), max(1, ep_r - 2))
            # Hot center
            pygame.draw.circle(ep_s, (255, 255, 200), (ep_cx, ep_cy), max(1, ep_r // 2))
            screen.blit(ep_s, (p.rect.centerx - ep_cx, p.rect.centery - ep_cy))
            
        # Draw Particles
        for p in particles[:]:
            p['life'] -= 1
            p['x'] += random.uniform(-1, 1)
            p['y'] += random.uniform(-1, 1)
            if p['life'] <= 0: particles.remove(p); continue
            
            s = pygame.Surface((p['size']*2, p['size']*2), pygame.SRCALPHA)
            col = p['color']
            alpha = int((p['life']/p['max_life'])*255)
            if len(col)==3: col = (*col, alpha)
            else: col = (col[0], col[1], col[2], alpha)
            pygame.draw.circle(s, col, (p['size'], p['size']), p['size'])
            screen.blit(s, (p['x']-p['size'], p['y']-p['size']))

        # Draw Active Effects (Lightning, Dragon)
        for eff in active_effects[:]:
            eff["life"] -= 1
            if eff["life"] <= 0: active_effects.remove(eff); continue
            
            if eff["type"] == "LIGHTNING":
                draw_lightning_bolt(screen, eff["start"], eff["end"])
            elif eff["type"] == "TORNADO_MOVING":
                # Moving Logic for Tornado inside Draw Loop (simplest way without defining new class)
                eff["x"] += 5 * eff["dir"] # Move 5px/frame
                
                # Draw
                draw_tornado_effect(screen, eff["x"], eff["y"], eff["life"])
                
                # Collision with enemies
                t_rect = pygame.Rect(eff["x"] - 40, eff["y"] - 150, 80, 150)
                for e in enemies:
                    if t_rect.colliderect(e.rect):
                        # Push Back
                        e.rect.x += 10 * eff["dir"]
                        # Damage (only every f few frames? No, tornados hurt fast)
                        if eff["life"] % 5 == 0:
                            e.health -= 1
                            if e.health <= 0: kill_enemy(e)
                            
            elif eff["type"] == "DRAGON":
                draw_dragon_effect(screen, eff["x"], eff["y"], eff["life"])

        # UI
        

        draw_health_bar(screen, 20, 20, wizard.health, wizard.max_health)
        


        # --- NEW HUD ---
        # 1. Main Stats Logic
        # (Already have wizard.health)
        
        # 2. XP Bar (Top Left - Under Health)
        pygame.draw.rect(screen, (30, 30, 30), (20, 50, 250, 15), border_radius=4)
        if XP_TO_NEXT_LEVEL > 0:
            xp_ratio = min(1.0, CURRENT_XP / XP_TO_NEXT_LEVEL)
        else:
            xp_ratio = 1.0
        pygame.draw.rect(screen, (0, 150, 255), (20, 50, int(250 * xp_ratio), 15), border_radius=4)
        pygame.draw.rect(screen, (100, 100, 100), (20, 50, 250, 15), 1, border_radius=4)
        
        xp_txt = small_font.render(f"LVL {CURRENT_LEVEL}", True, WHITE)
        screen.blit(xp_txt, (20, 70))
        
        # 3. Wave & Coins
        info = small_font.render(f"Wave: {current_wave}", True, WHITE)
        coins_ui = small_font.render(f"Coins: {TOTAL_COINS}", True, GOLD)
        screen.blit(info, (SCREEN_WIDTH - 150, 20))
        screen.blit(coins_ui, (SCREEN_WIDTH - 150, 50))
        
        # 4. Missions
        mission_y = 100
        m_title = shop_font.render("MISSIONS", True, (200, 200, 255))
        screen.blit(m_title, (SCREEN_WIDTH - 220, mission_y))
        mission_y += 30
        
        for m in MISSIONS:
            if m["current"] >= m["target"]: col = GREEN
            else: col = WHITE
            mtxt = small_font.render(f"{m['desc']}: {m['current']}/{m['target']}", True, col)
            screen.blit(mtxt, (SCREEN_WIDTH - 220, mission_y))
            mission_y += 25
            
        if boss_active:
             # BOSS BAR at Top Center
             bw = 500
             bh = 30
             bx = SCREEN_WIDTH//2 - bw//2
             by = 20
             
             # Name and Max Health selection
             if boss_active.enemy_type == "DRAGON_BOSS":
                 name_txt = "ANCIENT DRAGON"
                 max_hp = DRAGON_BOSS_HEALTH
                 bar_col = (255, 100, 0) # Orange
             else:
                 name_txt = f"OGRE KING (Wave {current_wave})"
                 max_hp = OGRE_HEALTH_BASE * 15.0
                 bar_col = (200, 0, 0) # Red
                 
             # Draw Boss Bar
             pygame.draw.rect(screen, (50, 0, 0), (bx, by, bw, bh))
             pct = max(0, boss_active.health / max_hp)
             pygame.draw.rect(screen, bar_col, (bx, by, int(bw*pct), bh))
             pygame.draw.rect(screen, WHITE, (bx, by, bw, bh), 2)
             
             
             bn = font.render(name_txt, True, WHITE)
             screen.blit(bn, (SCREEN_WIDTH//2 - bn.get_width()//2, by - 25))
        
        # Cooldowns HUD
        if UNLOCKED_ABILITIES["TORNADO"]:
            col = GREEN if tornado_cooldown == 0 else RED
            txt = small_font.render("Tornado [T]", True, col)
            screen.blit(txt, (20, SCREEN_HEIGHT - 60))
        if UNLOCKED_ABILITIES["DRAGON"]:
            col = GREEN if dragon_cooldown == 0 else RED
            txt = small_font.render("Dragon [R]", True, col)
            screen.blit(txt, (20, SCREEN_HEIGHT - 30))

        # UI: Draw Weapon Hotbar (Moved here to draw ON TOP)
        hotbar_x = 20
        hotbar_y = 120
        slot_size = 50
        padding = 10
        
        # Weapon Metadata for Display
        hotbar_slots = [
            {"key": "1", "id": "DEFAULT", "color": (255, 200, 50)},    # Gold/Yellow
            {"key": "2", "id": "ARCANE_VOLLEY", "color": (200, 100, 255)}, # Purple
            {"key": "3", "id": "VOID_LANCE", "color": (50, 0, 100)},   # Dark Purple
            {"key": "4", "id": "FIRE_RING", "color": (255, 69, 0)}     # Orange Red
        ]
        
        for i, slot in enumerate(hotbar_slots):
            # Status
            is_unlocked = slot["id"] == "DEFAULT" or slot["id"] in wizard.unlocked_weapons
            is_active = wizard.current_weapon == slot["id"]
            
            # Position
            rx = hotbar_x + i * (slot_size + padding)
            ry = hotbar_y
            rect = pygame.Rect(rx, ry, slot_size, slot_size)
            
            # Background Color
            if is_active:
                bg_col = (50, 50, 70) # Highlight active bg
                border_col = (255, 255, 255) # Bright border
                width = 3
            elif is_unlocked:
                bg_col = (30, 30, 30) # Unlocked but inactive
                border_col = (100, 100, 100)
                width = 1
            else:
                bg_col = (10, 10, 10) # Locked
                border_col = (50, 50, 50)
                width = 1
                
            pygame.draw.rect(screen, bg_col, rect, border_radius=5)
            pygame.draw.rect(screen, border_col, rect, width, border_radius=5)
            
            # Weapon Icon (Detailed Representation)
            if is_unlocked:
                center = rect.center
                cx, cy = center
                
                # Base Color (Dimmed if inactive)
                icon_col = slot["color"]
                if not is_active:
                    icon_col = (icon_col[0]//3, icon_col[1]//3, icon_col[2]//3)
                
                if slot["id"] == "DEFAULT":
                    # Simple Spark Orb
                    pygame.draw.circle(screen, icon_col, center, 8)
                    if is_active:
                        pygame.draw.circle(screen, (255, 255, 200), center, 4) # Inner glow
                        
                elif slot["id"] == "ARCANE_VOLLEY":
                    # Three small orbs in local spread
                    #  o
                    # o o
                    offsets = [(0, -6), (-6, 4), (6, 4)]
                    for ox, oy in offsets:
                        pygame.draw.circle(screen, icon_col, (cx + ox, cy + oy), 4)
                        
                elif slot["id"] == "VOID_LANCE":
                    # A diagonal beam/line
                    #  /
                    pygame.draw.line(screen, icon_col, (cx - 10, cy + 10), (cx + 10, cy - 10), 4)
                    if is_active:
                        pygame.draw.line(screen, (200, 100, 255), (cx - 10, cy + 10), (cx + 10, cy - 10), 1)
                        
                elif slot["id"] == "FIRE_RING":
                    # A Ring (Hollow Circle)
                    pygame.draw.circle(screen, icon_col, center, 12, 3)
                    if is_active:
                         # Flames on ring?
                         pass

                # Key Number
                key_txt = small_font.render(slot["key"], True, (200, 200, 200) if is_active else (80, 80, 80))
                screen.blit(key_txt, (rect.right - 15, rect.bottom - 20))
            else:
                # Draw Lock? Or just empty dark slot
                key_txt = small_font.render(slot["key"], True, (40, 40, 40))
                screen.blit(key_txt, (rect.right - 15, rect.bottom - 20))

    elif game_state == "BOSS_INTRO":
        # Cinematic Sequence
        boss_intro_timer += 1
        progress = min(1.0, boss_intro_timer / 300.0) # 5 seconds intro
        
        # Draw game world behind (frozen or not?)
        draw_background_scenery(screen, current_biome, SCREEN_WIDTH, SCREEN_HEIGHT)
        wizard.draw(screen)
        
        # Draw Cinematic
        draw_dragon_cinematic_entrance(screen, progress)
        
        if boss_intro_timer >= 300:
            # Spawn Boss and Start Fight
            game_state = "PLAYING"
            # Spawn Boss
            e = DragonBoss(SCREEN_WIDTH//2, SCREEN_HEIGHT - 300)
            enemies.add(e)
            all_sprites.add(e)
            
            # Sound effect placeholder
            # pygame.mixer.Sound("roar.wav").play()
            
    elif game_state == "CARD_SELECT":
        draw_cards_ui(screen, events)
        
        keys = pygame.key.get_pressed()
        if keys[pygame.K_s]:
             shop_return_target = "CARD_SELECT"
             game_state = "SHOP"
        
    elif game_state in ["GAME_OVER", "VICTORY"]:
        screen.fill(BLACK)
        txt = "VICTORY!" if game_state == "VICTORY" else "GAME OVER"
        col = GREEN if game_state == "VICTORY" else RED
        
        t = font.render(txt, True, col)
        s = small_font.render(f"Final Score: {score} - Coins Earned: {TOTAL_COINS}", True, WHITE)
        r = small_font.render("Press [ESC] to Return Menu", True, GRAY)
        
        cx, cy = SCREEN_WIDTH//2, SCREEN_HEIGHT//2
        screen.blit(t, t.get_rect(center=(cx, cy - 40)))
        screen.blit(s, s.get_rect(center=(cx, cy)))
        screen.blit(r, r.get_rect(center=(cx, cy + 50)))
        
        keys = pygame.key.get_pressed()
        if keys[pygame.K_ESCAPE]:
            game_state = "MENU"

    pygame.display.flip()
    clock.tick(FPS)

pygame.quit()
sys.exit()
