import melee
import math
from Strategies.bait import Bait

from melee.enums import ProjectileType, Action, Button, Character

class ESAgent():
    """
    Expert system agent for SmashBot.
    This is the "manually programmed" TAS-looking agent.
    """
    def __init__(self, dolphin, smashbot_port, opponent_port, controller, difficulty=4):
        self.smashbot_port = smashbot_port
        self.opponent_port = opponent_port
        self.controller = controller
        self.framedata = melee.framedata.FrameData()
        self.logger = dolphin.logger
        self.difficulty = difficulty
        self.ledge_grab_count = 0
        self.tech_lockout = 0
        self.meteor_jump_lockout = 0
        self.meteor_ff_lockout = 0
        self.powershielded_last = False
        self.strategy = Bait(self.logger,
                            self.controller,
                            self.framedata,
                            self.difficulty)

    def act(self, gamestate):
        if self.smashbot_port not in gamestate.players:
            self.controller.release_all()
            return

        # Figure out who our opponent is
        #   Opponent is the closest player that is a different costume
        opponents = []
        for i, player in gamestate.players.items():
            if i == self.smashbot_port:
                continue
            if not gamestate.is_teams or (player.team_id != gamestate.players[self.smashbot_port].team_id):
                opponents.append(i)
        nearest_dist = 1000
        nearest_port = 1
        for i, player in gamestate.players.items():
            if len(opponents) > 0 and i not in opponents:
                continue
            xdist = gamestate.players[self.smashbot_port].position.x - player.position.x
            ydist = gamestate.players[self.smashbot_port].position.y - player.position.y
            dist = math.sqrt((xdist**2) + (ydist**2))
            if dist < nearest_dist:
                nearest_dist = dist
                nearest_port = i
        self.opponent_port = nearest_port
        gamestate.distance = nearest_dist            

        # Pick the right climber to be the opponent
        if gamestate.player[self.opponent_port].nana is not None:
            xdist = gamestate.player[self.opponent_port].nana.position.x - gamestate.player[self.smashbot_port].position.x
            ydist = gamestate.player[self.opponent_port].nana.position.y - gamestate.player[self.smashbot_port].position.y
            dist = math.sqrt((xdist**2) + (ydist**2))
            if dist < gamestate.distance:
                gamestate.distance = dist
                popo = gamestate.player[self.opponent_port]
                gamestate.player[self.opponent_port] = gamestate.player[self.opponent_port].nana
                gamestate.player[self.opponent_port].nana = popo

        knownprojectiles = []
        for projectile in gamestate.projectiles:
            # Held turnips and link bombs
            if projectile.type in [ProjectileType.TURNIP, ProjectileType.LINK_BOMB, ProjectileType.YLINK_BOMB]:
                if projectile.subtype in [0, 4, 5]:
                    continue
            # Charging arrows
            if projectile.type in [ProjectileType.YLINK_ARROW, ProjectileType.FIRE_ARROW, \
                ProjectileType.LINK_ARROW, ProjectileType.ARROW]:
                if projectile.speed.x == 0 and projectile.speed.y == 0:
                    continue
            # Pesticide
            if projectile.type == ProjectileType.PESTICIDE:
                continue
            # Ignore projectiles owned by us
            if projectile.owner == self.smashbot_port:
                continue
            if projectile.type not in [ProjectileType.UNKNOWN_PROJECTILE, ProjectileType.PEACH_PARASOL, \
                ProjectileType.FOX_LASER, ProjectileType.SHEIK_CHAIN, ProjectileType.SHEIK_SMOKE]:
                knownprojectiles.append(projectile)
        gamestate.projectiles = knownprojectiles

        # Yoshi shield animations are weird. Change them to normal shield
        if gamestate.player[self.opponent_port].character == Character.YOSHI:
            if gamestate.player[self.opponent_port].action in [melee.Action.NEUTRAL_B_CHARGING, melee.Action.NEUTRAL_B_FULL_CHARGE, melee.Action.LASER_GUN_PULL]:
                gamestate.player[self.opponent_port].action = melee.Action.SHIELD

        # Tech lockout
        if gamestate.player[self.smashbot_port].controller_state.button[Button.BUTTON_L]:
            self.tech_lockout = 40
        else:
            self.tech_lockout -= 1
            self.tech_lockout = max(0, self.tech_lockout)

        # Jump meteor cancel lockout
        if gamestate.player[self.smashbot_port].controller_state.button[Button.BUTTON_Y] or \
            gamestate.player[self.smashbot_port].controller_state.main_stick[1] > 0.8:
            self.meteor_jump_lockout = 40
        else:
            self.meteor_jump_lockout -= 1
            self.meteor_jump_lockout = max(0, self.meteor_jump_lockout)

        # Firefox meteor cancel lockout
        if gamestate.player[self.smashbot_port].controller_state.button[Button.BUTTON_B] and \
            gamestate.player[self.smashbot_port].controller_state.main_stick[1] > 0.8:
            self.meteor_ff_lockout = 40
        else:
            self.meteor_ff_lockout -= 1
            self.meteor_ff_lockout = max(0, self.meteor_ff_lockout)

        # Keep a ledge grab count
        if gamestate.player[self.opponent_port].action == Action.EDGE_CATCHING and gamestate.player[self.opponent_port].action_frame == 1:
            self.ledge_grab_count += 1
        if gamestate.player[self.opponent_port].on_ground:
            self.ledge_grab_count = 0
        if gamestate.frame == -123:
            self.ledge_grab_count = 0
        gamestate.custom["ledge_grab_count"] = self.ledge_grab_count
        gamestate.custom["tech_lockout"] = self.tech_lockout
        gamestate.custom["meteor_jump_lockout"] = self.meteor_jump_lockout
        gamestate.custom["meteor_ff_lockout"] = self.meteor_ff_lockout

        if gamestate.player[self.smashbot_port].action in [Action.SHIELD_REFLECT, Action.SHIELD_STUN]:
            if gamestate.player[self.smashbot_port].is_powershield:
                self.powershielded_last = True
            elif gamestate.player[self.smashbot_port].hitlag_left > 0:
                self.powershielded_last = False

        gamestate.custom["powershielded_last"] = self.powershielded_last

        # Let's treat Counter-Moves as invulnerable. So we'll know to not attack during that time
        countering = False
        if gamestate.player[self.opponent_port].character in [Character.ROY, Character.MARTH]:
            if gamestate.player[self.opponent_port].action in [Action.MARTH_COUNTER, Action.MARTH_COUNTER_FALLING]:
                # We consider Counter to start a frame early and a frame late
                if 4 <= gamestate.player[self.opponent_port].action_frame <= 30:
                    countering = True
        if gamestate.player[self.opponent_port].character == Character.PEACH:
            if gamestate.player[self.opponent_port].action in [Action.UP_B_GROUND, Action.DOWN_B_STUN]:
                if 4 <= gamestate.player[self.opponent_port].action_frame <= 30:
                    countering = True
        if countering:
            gamestate.player[self.opponent_port].invulnerable = True
            gamestate.player[self.opponent_port].invulnerability_left = max(29 - gamestate.player[self.opponent_port].action_frame, gamestate.player[self.opponent_port].invulnerability_left)

        # Platform drop is fully actionable. Don't be fooled
        if gamestate.players[self.opponent_port].action == Action.PLATFORM_DROP:
            gamestate.players[self.opponent_port].hitstun_frames_left = 0

        self.strategy.step(gamestate,
                           gamestate.players[self.smashbot_port],
                           gamestate.players[self.opponent_port])
