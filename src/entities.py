
import pygame
import random
import math
from src.config import *
from src.assets import *

class Wizard(pygame.sprite.Sprite):
    def __init__(self, x, y, color=(0, 255, 255), owner_id=1): # Default Cyan
        super().__init__()
        self.image = pygame.Surface((PLAYER_SIZE, PLAYER_SIZE), pygame.SRCALPHA)
        self.image.fill((0, 0, 0, 0)) # Transparent
        self.rect = self.image.get_rect()
        self.rect.midbottom = (x, y)
        self.color = color
        self.owner_id = owner_id
        self.vel_y = 0
        self.vel_x = 0
        self.facing_right = True
        self.jumping = False
        self.is_casting = False
        self.cast_cooldown = 0
        self.health = PLAYER_MAX_HEALTH
        self.max_health = PLAYER_MAX_HEALTH
        self.wand_level = 0 # 0 to 3 visual level
        self.attack_speed_boost = 0
        self.damage_multiplier = 1.0
        self.multishot = 1
        self.piercing = 0
        self.coins = 0
        # Tracks how many times each stat has been upgraded (Max 3)
        self.upgrade_levels = {
            "SPEED": 0,
            "DAMAGE": 0,
            "MULTISHOT": 0,
            "PIERCING": 0,
            "HEALTH": 0 # Unlimited
        }
        self.abilities = {
            "LIGHTNING": False,
            "TORNADO": False,
            "DRAGON": False
        }
        self.unlocked_weapons = ["DEFAULT"] # "ARCANE_VOLLEY", "VOID_LANCE", "FIRE_RING"
        self.current_weapon_index = 0
        
        # Initialize Weapon based on Color (Class)
        if self.color == (255, 0, 0): # Red -> Fire
            self.current_weapon = "FIRE_RING"
            self.unlocked_weapons.append("FIRE_RING")
        elif self.color == (128, 0, 128): # Purple -> Void
             self.current_weapon = "VOID_LANCE"
             self.unlocked_weapons.append("VOID_LANCE")
        elif self.color == (0, 0, 255): # Blue -> Arcane
             self.current_weapon = "ARCANE_VOLLEY"
             self.unlocked_weapons.append("ARCANE_VOLLEY")
        else:
            self.current_weapon = "DEFAULT"

    def update(self, keys, platforms):
        # Movement
        self.vel_x = 0
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            self.vel_x = -PLAYER_SPEED
            self.facing_right = False
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            self.vel_x = PLAYER_SPEED
            self.facing_right = True

        # Jump
        if (keys[pygame.K_SPACE] or keys[pygame.K_w] or keys[pygame.K_UP]) and not self.jumping:
            self.vel_y = JUMP_STRENGTH
            self.jumping = True

        # Gravity
        self.vel_y += GRAVITY
        
        # Apply Movement Y
        self.rect.y += self.vel_y
        
        # Collision Y
        for platform in platforms:
            if self.rect.colliderect(platform):
                if self.vel_y > 0: # Falling
                    self.rect.bottom = platform.top
                    self.vel_y = 0
                    self.jumping = False
                elif self.vel_y < 0: # Jumping up into ceiling
                    self.rect.top = platform.bottom
                    self.vel_y = 0
                    
        # Apply Movement X
        self.rect.x += self.vel_x
        
        # Collision X
        for platform in platforms:
             if self.rect.colliderect(platform):
                 if self.vel_x > 0: # Moving right
                     self.rect.right = platform.left
                 elif self.vel_x < 0: # Moving left
                     self.rect.left = platform.right

        # Screen Bounds
        if self.rect.left < 0: self.rect.left = 0
        if self.rect.right > SCREEN_WIDTH: self.rect.right = SCREEN_WIDTH
        if self.rect.bottom > SCREEN_HEIGHT - 50: # Ground Floor
            self.rect.bottom = SCREEN_HEIGHT - 50
            self.vel_y = 0
            self.jumping = False

        # Cooldown
        if self.cast_cooldown > 0:
            self.cast_cooldown -= 1
            if self.cast_cooldown < 10: # Reset animation state quickly
                self.is_casting = False

    def draw(self, surface):
        # Use self.color for robe/hat. WAND_COLORS is for projectiles?
        # Actually draw_wizard takes a 'color' which usually tints the robe.
        draw_wizard(surface, self.rect.centerx, self.rect.bottom, self.facing_right, self.is_casting, self.color)

    def select_weapon(self, slot_index):
        # 1-based index (1, 2, 3...) passed from input
        # Mapping: 1 -> index 1 of unlocked, etc.
        # But we want specific keys to map to specific weapons if owned?
        # User said: "con el 1 puedas usar una arma... con el 2 la otra".
        # Let's map strict slots:
        # Slot 0: DEFAULT (Always on '1' ?) 
        # Actually user says "comprar... luego con el 1 usar una, etc".
        # Let's make it:
        # 1: DEFAULT (Wand of Sparks)
        # 2: ARCANE VOLLEY
        # 3: VOID LANCE
        # 4: FIRE RING
        # 5: HEAL (New)
        
        target_wep = "DEFAULT"
        if slot_index == 1: target_wep = "DEFAULT"
        elif slot_index == 2: target_wep = "ARCANE_VOLLEY"
        elif slot_index == 3: target_wep = "VOID_LANCE"
        elif slot_index == 4: target_wep = "FIRE_RING"
        elif slot_index == 5:
             # Instant Heal, not a weapon switch? 
             # Or switch to "HEAL_WAND"?
             # Let's just trigger heal immediately? No, select_weapon is for selecting.
             # Let's make it a castable action separately.
             return False
        
        target_wep = "DEFAULT"
        if slot_index == 1: target_wep = "DEFAULT"
        elif slot_index == 2: target_wep = "ARCANE_VOLLEY"
        elif slot_index == 3: target_wep = "VOID_LANCE"
        elif slot_index == 4: target_wep = "FIRE_RING"
        
        if target_wep == "DEFAULT" or target_wep in self.unlocked_weapons:
            self.current_weapon = target_wep
            return True
        return False

    def shoot(self, target_pos=None):
        if self.cast_cooldown == 0:
            self.is_casting = True
            base_cooldown = 20
            
            # Weapon specific cooldowns
            if self.current_weapon == "VOID_LANCE": base_cooldown = 50
            elif self.current_weapon == "ARCANE_VOLLEY": base_cooldown = 40
            elif self.current_weapon == "FIRE_RING": base_cooldown = 70
            
            self.cast_cooldown = max(5, base_cooldown - self.attack_speed_boost)
            
            start_x = self.rect.centerx
            start_y_base = self.rect.centery - 20
            
            # Aim Logic
            aim_angle = 0
            if target_pos:
                mx, my = target_pos
                dx = mx - start_x
                dy = my - start_y_base
                aim_angle = math.atan2(dy, dx)
                self.facing_right = dx > 0 # Update facing
            else:
                aim_angle = 0 if self.facing_right else 3.14159
            
            projectiles = []
            damage = BASE_WAND_DAMAGE * self.damage_multiplier
            color = WAND_COLORS[min(self.wand_level, len(WAND_COLORS)-1)]
            
            # Determine Basic Attack Type based on Class Color
            p_type = "DEFAULT"
            p_speed = PROJECTILE_SPEED
            p_dmg = BASE_WAND_DAMAGE
            p_col = self.color
            
            if self.color == (255, 50, 0): # Fire (Red)
                p_type = "FIRE_BOLT"
                p_dmg = 30
                p_speed = 12
            elif self.color == (0, 200, 255): # Ice (Blue)
                p_type = "ICE_SHARD"
                p_dmg = 15
                p_speed = 12
            elif self.color == (120, 0, 200): # Void (Purple)
                p_type = "VOID_ORB"
                p_dmg = 25
                p_speed = 8
            elif self.color == (255, 255, 0): # Storm (Yellow)
                p_type = "LIGHTNING_BOLT"
                p_dmg = 10
                p_speed = 20
                
            # Common Projectile Velocity function
            def create_proj(speed, angle, p_type, col, dmg):
                p = Projectile(start_x, start_y_base, 1 if math.cos(angle)>0 else -1, col, p_type, owner_id=self.owner_id)
                p.vel_x = math.cos(angle) * speed
                p.vel_y = math.sin(angle) * speed
                p.damage = dmg # Set custom damage
                if p_type == "VOID_ORB": p.piercing = 999
                return p

            if self.current_weapon == "DEFAULT":
                # Standard Wand logic -> Class Specific
                # scale_factor = 1.0 + (self.multishot - 1) * 0.3 # Ignore multishot scale for now or apply to dmg
                
                # Apply Multishot stat as actual multiple projectiles
                actual_multishot = max(1, self.multishot)
                
                # Base angle is aim_angle
                for i in range(actual_multishot):
                    spread = 0
                    if actual_multishot > 1:
                        spread = (i - (actual_multishot-1)/2) * 0.2
                    
                    p = create_proj(p_speed, aim_angle + spread, p_type, p_col, p_dmg)
                    # Apply damage multiplier
                    p.damage = p_dmg * self.damage_multiplier
                    p.piercing = self.piercing
                    projectiles.append(p)

            elif self.current_weapon == "ARCANE_VOLLEY":
                # Fires spread of orb-like projectiles (Purple/Cyan mix)
                for i in range(5):
                    angle_offset = random.uniform(-0.4, 0.4) 
                    final_angle = aim_angle + angle_offset
                    
                    p = create_proj(PROJECTILE_SPEED, final_angle, "ARCANE_VOLLEY", (200, 100, 255))
                    p.damage = damage * 0.5 
                    p.scale = 0.7
                    p.life = 50 
                    projectiles.append(p)

            elif self.current_weapon == "VOID_LANCE":
                p = create_proj(PROJECTILE_SPEED * 2.5, aim_angle, "VOID_LANCE", (50, 0, 100))
                p.damage = damage * 2.5
                p.scale = 1.2
                p.piercing = 999
                p.life = 100
                projectiles.append(p)

            elif self.current_weapon == "FIRE_RING":
                 # Huge ring of fire that moves slowly but destroys everything
                 p = create_proj(PROJECTILE_SPEED * 0.6, aim_angle, "FIRE_RING", (255, 69, 0))
                 p.damage = damage * 3.0
                 p.piercing = 999
                 p.scale = 3.0 
                 p.life = 150
                 projectiles.append(p)

            return projectiles
            return projectiles
        return []

    def cast_heal(self):
        # 30% Heal logic
        heal_amt = self.max_health * 0.3
        if self.health < self.max_health:
             self.health += heal_amt
             if self.health > self.max_health: self.health = self.max_health
             return True
        return False

class EnemyProjectile(pygame.sprite.Sprite):
    def __init__(self, x, y, target_x, target_y, is_boss=False, p_type="DEFAULT"):
        super().__init__()
        self.p_type = p_type
        
        if p_type == "ARROW":
             size = 20 # Longer logic?
             self.image = pygame.Surface((30, 5), pygame.SRCALPHA)
             self.image.fill((200, 200, 200)) # Grey Arrow Shaft
             # Add tip
             pygame.draw.circle(self.image, (150, 150, 150), (30, 2), 4)
             self.speed = 15
             self.damage = 30 # User requested 30 damage
        else:
             size = 20 if is_boss else 10
             self.image = pygame.Surface((size, size), pygame.SRCALPHA)
             col = (255, 0, 0) if not is_boss else (100, 0, 100) # Red or Purple
             pygame.draw.circle(self.image, col, (size//2, size//2), size//2)
             self.speed = 12 if is_boss else 10 # Faster arrows (was 8)
             self.damage = 25 if is_boss else 15
        
        self.rect = self.image.get_rect()
        self.rect.center = (x, y)
        
        dx = target_x - x
        dy = target_y - y
        dist = math.hypot(dx, dy)
        if dist == 0: dist = 1
        
        # Rotation for Arrow
        if p_type == "ARROW":
             # Original image is horizontal pointing right? Yes 30x5.
             # atan2(dy, dx) gives angle in radians. positive y is Down in Pygame.
             # degrees(-angle)
             angle = math.degrees(math.atan2(-dy, dx))
             self.image = pygame.transform.rotate(self.image, angle)
             self.rect = self.image.get_rect(center=(x, y))
             
        self.vel_x = (dx / dist) * self.speed
        self.vel_y = (dy / dist) * self.speed
        
        # Floating point position for precision
        self.exact_x = float(self.rect.centerx)
        self.exact_y = float(self.rect.centery)
        
        # Move it slightly forward?
        self.exact_x += self.vel_x * 4
        self.exact_y += self.vel_y * 4
        self.rect.centerx = int(self.exact_x)
        self.rect.centery = int(self.exact_y)
        
        self.life = 300 

    def update(self):
        self.exact_x += self.vel_x
        self.exact_y += self.vel_y
        
        self.rect.centerx = int(self.exact_x)
        self.rect.centery = int(self.exact_y)
        
        self.life -= 1
        if self.life <= 0:
            self.kill()
        
        # Expanded bounds to avoid premature despawn
        if self.rect.right < -50 or self.rect.left > SCREEN_WIDTH + 50 or self.rect.bottom < -50 or self.rect.top > SCREEN_HEIGHT + 50:
            self.kill()

class Enemy(pygame.sprite.Sprite):
    def __init__(self, x, y, enemy_type="OGRE"):
        super().__init__()
        self.enemy_type = enemy_type
        
        # Stats based on type
        if self.enemy_type == "GOBLIN":
            size = 50
            self.speed = OGRE_SPEED * 1.5
            self.health = OGRE_HEALTH_BASE * 0.5
        elif self.enemy_type == "TROLL":
            size = 90
            self.speed = OGRE_SPEED * 0.6
            self.health = OGRE_HEALTH_BASE * 2.0
        elif self.enemy_type == "SKELETON_ARCHER":
            size = 45
            self.speed = OGRE_SPEED * 0.9
            self.health = OGRE_HEALTH_BASE * 0.4
        elif self.enemy_type == "OGRE_KING": # BOSS
            size = 180 # Massive
            self.speed = OGRE_SPEED * 0.5
            self.health = OGRE_HEALTH_BASE * 15.0 # Tanky
        else: # OGRE
            size = OGRE_SIZE
            self.speed = OGRE_SPEED
            self.health = OGRE_HEALTH_BASE

        self.image = pygame.Surface((size, size), pygame.SRCALPHA)
        self.rect = self.image.get_rect()
        self.rect.midbottom = (x, y)
        self.vel_y = 0
        self.direction = -1 
        self.is_attacking = False
        self.did_attack = False
        self.attack_timer = 0
        
        # Attack Logic & Cooldowns
        if self.enemy_type == "SKELETON_ARCHER":
            self.stop_range = 500 # Ranged
            self.damage = 20 # NO MELEE DAMAGE
            self.attack_cooldown_max = 100 # Faster fire rate 
        elif self.enemy_type == "OGRE_KING":
            self.stop_range = 100
            self.damage = 50
            self.attack_cooldown_max = 200 
        elif self.enemy_type == "GOBLIN":
            self.stop_range = 80 
            self.damage = 20
            self.attack_cooldown_max = 120
        elif self.enemy_type == "TROLL":
            self.stop_range = 120
            self.damage = 45
            self.attack_cooldown_max = 240
        else: # OGRE
            self.stop_range = 100
            self.damage = 30
            self.attack_cooldown_max = 180
        
    def update(self, player_rect):
        self.did_attack = False
        new_projectile = None
        
        player_x = player_rect.centerx
        player_y = player_rect.centery
        
        # Tracking AI
        dist = self.rect.centerx - player_x
        abs_dist = abs(dist)
        
        # Face player
        if dist > 0:
            self.direction = -1
        else:
            self.direction = 1
            
            
        # Move only if outside stop range (with Hysteresis)
        # If already attacking, allow player to be slightly further before moving again.
        tolerance = 100 if self.is_attacking else 0
        
        if abs_dist > self.stop_range + tolerance:
            self.rect.x += self.speed * self.direction
            self.is_attacking = False
            self.attack_timer = 0 
        else:
            # Stop and Attack
            self.is_attacking = True
            
            # Attack Timer
            self.attack_timer += 1
            
            # Trigger damage/shoot at HALF swing
            # (Attack happens faster now, so /2 of 100 = 50 frames ~ 0.8s)
            if self.attack_timer == self.attack_cooldown_max // 2:
                if self.enemy_type == "SKELETON_ARCHER":
                    # Fire Arrow
                    new_projectile = EnemyProjectile(self.rect.centerx, self.rect.centery, player_x, player_y, is_boss=False, p_type="ARROW")
                elif self.enemy_type == "OGRE_KING": 
                    # Boss Smash & Projectile
                    self.did_attack = True # Melee smash
                    # Also spawn a ring or shockwave? Or just melee for now?
                    # Let's say he throws a rock AND smashes
                    new_projectile = EnemyProjectile(self.rect.centerx, self.rect.centery, player_x, player_y, is_boss=True)
                else:
                    # Melee
                    self.did_attack = True
                
            if self.attack_timer >= self.attack_cooldown_max:
                self.attack_timer = 0 # Reset
                
        # Gravity
        self.vel_y += GRAVITY
        self.rect.y += self.vel_y
        
        if self.rect.bottom > SCREEN_HEIGHT - 50:
            self.rect.bottom = SCREEN_HEIGHT - 50
            self.vel_y = 0
            
        return new_projectile

    def draw(self, surface):
        t = pygame.time.get_ticks()
        # Calculate Phase (0.0 to 1.0)
        phase = 0.0
        if self.is_attacking and self.attack_cooldown_max > 0:
            phase = self.attack_timer / self.attack_cooldown_max
            
        if self.enemy_type == "GOBLIN":
            draw_goblin(surface, self.rect.centerx, self.rect.bottom, self.direction > 0, tick=t, is_attacking=self.is_attacking, attack_phase=phase)
        elif self.enemy_type == "TROLL":
             draw_troll(surface, self.rect.centerx, self.rect.bottom, self.direction > 0, tick=t, is_attacking=self.is_attacking, attack_phase=phase)
        elif self.enemy_type == "SKELETON_ARCHER":
             draw_skeleton(surface, self.rect.centerx, self.rect.bottom, self.direction > 0, scale=1.0, tick=t, is_attacking=self.is_attacking, attack_phase=phase)
        elif self.enemy_type == "OGRE_KING":
             draw_ogre(surface, self.rect.centerx, self.rect.bottom, self.direction > 0, scale=2.5, tick=t, is_attacking=self.is_attacking, attack_phase=phase)

        elif self.enemy_type == "DRAGON_BOSS":
             draw_dragon_boss(surface, self.rect.centerx, self.rect.centery, self.direction > 0, scale=1.0, tick=t, is_attacking=self.is_attacking, attack_phase=phase)
        else:
            draw_ogre(surface, self.rect.centerx, self.rect.bottom, self.direction > 0, tick=t, is_attacking=self.is_attacking, attack_phase=phase)

class DragonBoss(Enemy):
    def __init__(self, x, y):
        super().__init__(x, y, "DRAGON_BOSS")
        # Override stats
        self.health = DRAGON_BOSS_HEALTH 
        self.max_health = DRAGON_BOSS_HEALTH
        self.speed = DRAGON_BOSS_SPEED
        self.size = DRAGON_BOSS_SIZE
        
        # Hitbox setup
        self.image = pygame.Surface((self.size, self.size), pygame.SRCALPHA)
        self.rect = self.image.get_rect()
        self.rect.center = (x, y)
        
        # Flight logic
        self.target_y = y
        self.hover_offset = 0
        self.attack_cooldown_max = 100 # Fast attacks
        self.stop_range = 350 
        
        # State Machine: FLYING -> LANDING -> GROUNDED -> TAKEOFF -> FLYING
        self.state = "FLYING"
        self.state_timer = 0
        self.ground_y = 750 # Lower to touch ground (Screen 900, size 300, half is 150 -> bottom 900)
        
    def update(self, player_rect):
        self.did_attack = False
        new_projectile_list = []
        
        player_x = player_rect.centerx
        player_y = player_rect.centery
        
        # Tracking X
        dist_x = self.rect.centerx - player_x
        
        # Face player
        self.direction = -1 if dist_x > 0 else 1
            
        # State Logic
        self.state_timer += 1
        
        if self.state == "FLYING":
            target_y = player_y - 250 # Fly high
            if target_y < 100: target_y = 100
            
            # Transition to Land after 10s
            if self.state_timer > 600: 
                self.state = "LANDING"
                self.state_timer = 0
                
        elif self.state == "LANDING":
            target_y = self.ground_y
            # Check if reached ground
            if abs(self.rect.centery - target_y) < 20:
                self.state = "GROUNDED"
                self.state_timer = 0
                
        elif self.state == "GROUNDED":
            target_y = self.ground_y
            # Stay for 5s (300 frames)
            if self.state_timer > 300:
                self.state = "TAKEOFF"
                self.state_timer = 0
                
        elif self.state == "TAKEOFF":
            target_y = player_y - 250
            if abs(self.rect.centery - target_y) < 50:
                 self.state = "FLYING"
                 self.state_timer = 0
        
        # Smooth Y movement
        dy = target_y - self.rect.centery
        self.rect.centery += dy * 0.05
        
        # Move X (Keep distance)
        abs_dist = abs(dist_x)
        wanted_dist = self.stop_range
        if self.state == "GROUNDED": wanted_dist = 200 # Get closer on ground
        
        if abs_dist > wanted_dist:
            self.rect.x += self.speed * self.direction
            self.is_attacking = False
            self.attack_timer = 0 # Reset attack if moving
        elif abs_dist < wanted_dist - 100:
             # Too close, back up (only if flying)
             if self.state == "FLYING":
                 self.rect.x -= self.speed * self.direction * 0.5
        else:
            # In range, Attack!
            self.is_attacking = True
            self.attack_timer += 1
            
            # Fire Attack Logic
            # Phase 0.0 to 1.0 (Attack Cooldown)
            
            # Select Attack Type randomly?
            # 1. Triple Fireball (Standard)
            # 2. Fire Breath (Stream down to ground) - NEW
            
            if self.attack_timer == 1: # Decide attack at start of cycle
                 self.current_attack = "TRIPLE" if random.random() > 0.4 else "BREATH"
            
            if self.current_attack == "TRIPLE":
                if self.attack_timer == self.attack_cooldown_max // 2:
                    self.did_attack = True
                    # Center shot
                    p1 = EnemyProjectile(self.rect.centerx, self.rect.centery + 50, player_x, player_y, is_boss=True)
                    p1.image.fill((255, 100, 0)) 
                    new_projectile_list.append(p1)
                    # Angled Up
                    p2 = EnemyProjectile(self.rect.centerx, self.rect.centery + 50, player_x, player_y - 150, is_boss=True)
                    new_projectile_list.append(p2)
                    # Angled Down
                    p3 = EnemyProjectile(self.rect.centerx, self.rect.centery + 50, player_x, player_y + 150, is_boss=True)
                    new_projectile_list.append(p3)
            
            elif self.current_attack == "BREATH":
                # Stream of fire for 30 frames
                if self.attack_timer > 30 and self.attack_timer < 60:
                    if self.attack_timer % 3 == 0:
                        # Target ground below player (or just player)
                        # Spread slightly
                        tx = player_x + random.randint(-50, 50)
                        ty = player_y + random.randint(-20, 20)
                        
                        p = EnemyProjectile(self.rect.centerx, self.rect.centery + 40, tx, ty, is_boss=True)
                        p.image.fill((255, 50, 0)) # Redder
                        p.speed = 15 # Fast breath
                        p.size = 15
                        # Recalculate vel for new speed
                        dx = tx - p.rect.centerx
                        dy = ty - p.rect.centery
                        dist = math.hypot(dx, dy)
                        if dist == 0: dist = 1
                        p.vel_x = (dx/dist)*p.speed
                        p.vel_y = (dy/dist)*p.speed
                        
                        new_projectile_list.append(p)

            if self.attack_timer >= self.attack_cooldown_max:
                self.attack_timer = 0
        
        # Apply Logic for Boss (No Gravity in same sense)
        if self.rect.top < 0: self.rect.top = 0
        if self.rect.bottom > SCREEN_HEIGHT - 50: self.rect.bottom = SCREEN_HEIGHT - 50
        
        return new_projectile_list

class Projectile(pygame.sprite.Sprite):
    def __init__(self, x, y, facing_right, color=WHITE, type="DEFAULT", owner_id=0):
        super().__init__()
        self.color = color
        self.type = type
        self.owner_id = owner_id
        self.damage = BASE_WAND_DAMAGE
        self.piercing = 0
        self.hit_list = [] 
        self.scale = 1.0 # Default scale
        
        self.is_seeker = False
        self.target = None
        
        # Fireball sizing
        self.image = pygame.Surface((PROJECTILE_RADIUS*3, PROJECTILE_RADIUS*3), pygame.SRCALPHA)
        self.rect = self.image.get_rect()
        self.rect.center = (x, y)
        self.vel_x = PROJECTILE_SPEED if facing_right else -PROJECTILE_SPEED
        self.vel_y = 0 
        
        self.life = 100
        
        # Particle System for Trail
        # Each particle: [x, y, vx, vy, life, max_life, size, color_type]
        self.particles = []
        
    def update_rect(self):
        # Update rect size based on scale if not already done
        # We'll do this on the fly or after init if scale is changed externally
        # But rect center needs to persist.
        c = self.rect.center
        
        # Base Size * Scale
        size = int(PROJECTILE_RADIUS * 3 * self.scale)
        if self.image.get_width() != size:
            self.image = pygame.Surface((size, size), pygame.SRCALPHA)
            self.rect = self.image.get_rect()
            self.rect.center = c
            
    def update(self, enemies_group=None):
        # Ensure rect matches scale (lazy update or just check)
        expected_size = int(PROJECTILE_RADIUS * 3 * self.scale)
        if self.rect.width != expected_size:
            c = self.rect.center
            self.image = pygame.Surface((expected_size, expected_size), pygame.SRCALPHA)
            self.rect = self.image.get_rect()
            self.rect.center = c
            
        # Seeker Logic
        if self.is_seeker:
             # Find closest enemy if no target or target dead
             if (not self.target or not self.target.alive()) and enemies_group:
                 # Find closest
                 closest = None
                 min_dist = 9999
                 for e in enemies_group:
                     d = math.hypot(e.rect.centerx - self.rect.centerx, e.rect.centery - self.rect.centery)
                     if d < min_dist:
                         min_dist = d
                         closest = e
                 if closest:
                     self.target = closest
             
             if self.target and self.target.alive():
                 # Steer towards target
                 tx, ty = self.target.rect.center
                 dx = tx - self.rect.centerx
                 dy = ty - self.rect.centery
                 dist = math.hypot(dx, dy)
                 if dist != 0:
                     dx /= dist
                     dy /= dist
                     
                     # Seeker Speed
                     speed = PROJECTILE_SPEED * 0.8
                     self.vel_x = self.vel_x * 0.9 + dx * speed * 0.1
                     self.vel_y = self.vel_y * 0.9 + dy * speed * 0.1
                     
                     # Normalize and apply speed
                     cur_speed = math.hypot(self.vel_x, self.vel_y)
                     if cur_speed != 0:
                         self.vel_x = (self.vel_x / cur_speed) * speed
                         self.vel_y = (self.vel_y / cur_speed) * speed

        if self.type == "FIRE_RING":
            # Spin effect or just particle emission?
            # Let's add rotational velocity to particles for cool ring effect
            pass 

        self.rect.x += self.vel_x
        self.rect.y += self.vel_y
        self.life -= 1
        
        # --- Spawn Trail Particles ---
        # Spawn more particles if bigger
        count = 3 + int(self.scale * 2)
        
        for _ in range(count):
            # Random offset from center (scaled)
            spread = 5 * self.scale
            off_x = random.uniform(-spread, spread)
            off_y = random.uniform(-spread, spread)
            
            px = self.rect.centerx + off_x
            py = self.rect.centery + off_y
            
            # Velocity
            vx = -self.vel_x * 0.3 + random.uniform(-1, 1)
            vy = -self.vel_y * 0.3 + random.uniform(-1, 1)  # Added vy reaction
            
            life = random.randint(15, 30)
            size = random.randint(4, 10) * self.scale # Scale particles too
            
            # Store particle
            self.particles.append([px, py, vx, vy, life, life, size])

        # --- Update Particles ---
        for p in self.particles:
            p[0] += p[2] # x move
            p[1] += p[3] # y move
            p[4] -= 1    # life drain
            p[6] *= 0.95 # shrink
            
        # Remove dead particles
        self.particles = [p for p in self.particles if p[4] > 0 and p[6] > 1] 

        return self.life > 0

    def draw(self, surface):
        draw_projectile(surface, self.rect.centerx, self.rect.centery, self.color, self.particles, self.scale, self.type)

class Particle(pygame.sprite.Sprite):
    def __init__(self, x, y, color):
        super().__init__()
        self.x = x
        self.y = y
        self.color = color
        self.vel_x = random.uniform(-2, 2)
        self.vel_y = random.uniform(-2, 2)
        self.life = 30
        self.max_life = 30
        self.size = random.randint(2, 5)

    def update(self):
        self.x += self.vel_x
        self.y += self.vel_y
        self.life -= 1
        return self.life > 0
