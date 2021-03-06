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
        self.strategy = Bait(self.logger,
                            self.controller,
                            self.framedata,
                            self.difficulty)

    def act(self, gamestate):
        knownprojectiles = []
        for projectile in gamestate.projectiles:
            # Held turnips
            if projectile.type == ProjectileType.TURNIP and projectile.type == 0:
                continue
            if projectile.type not in [ProjectileType.UNKNOWN_PROJECTILE, ProjectileType.PEACH_PARASOL, \
                ProjectileType.FOX_LASER, ProjectileType.SHEIK_CHAIN, ProjectileType.SHEIK_SMOKE]:
                knownprojectiles.append(projectile)
        gamestate.projectiles = knownprojectiles

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

        self.strategy.step(gamestate,
                           gamestate.players[self.smashbot_port],
                           gamestate.players[self.opponent_port])
