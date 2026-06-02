import gymnasium as gym
import numpy as np
import logging
from typing import Dict, Any, Tuple, Optional

from src.client import BalatroClient, BalatroAPIError
from src.game_state import GameState
from src.env.observation import get_observation_space, encode_observation
from src.env.action import get_action_space, decode_action

logger = logging.getLogger("BalatroEnv")

class BalatroEnv(gym.Env):
    metadata = {"render_modes": []}

    def __init__(self, base_url: str = "http://127.0.0.1:12346", timeout: float = 10.0):
        super().__init__()
        self.client = BalatroClient(base_url=base_url, timeout=timeout)
        
        # Define spaces
        self.observation_space = get_observation_space()
        self.action_space = get_action_space()
        
        # Environment state
        self.current_state: Optional[GameState] = None
        self.invalid_actions_in_a_row = 0
        self.max_invalid_actions = 20

    def _auto_skip_boosters(self, state: GameState) -> GameState:
        """Automatically skip booster pack selection to prevent the environment from getting stuck."""
        booster_states = {
            "SMODS_BOOSTER_OPENED",
            "TAROT_PACK",
            "PLANET_PACK",
            "SPECTRAL_PACK",
            "STANDARD_PACK",
            "BUFFOON_PACK",
        }
        while state.state in booster_states:
            logger.info(f"Booster pack screen detected ({state.state}). Automatically skipping booster pack...")
            try:
                state = self.client.pack(skip=True)
            except Exception as e:
                logger.error(f"Failed to skip booster pack: {e}")
                break
        return state

    def reset(self, seed: Optional[int] = None, options: Optional[dict] = None) -> Tuple[Dict[str, np.ndarray], dict]:
        import time
        super().reset(seed=seed)
        self.invalid_actions_in_a_row = 0
        
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                logger.info(f"Resetting Balatro environment (attempt {attempt}/{max_attempts})...")
                state = self.client.gamestate()
                
                # If not in main menu, return to menu first to ensure a clean start
                if state.state != "MENU":
                    logger.info("Returning to menu to start fresh run...")
                    state = self.client.menu()
                
                # Verify we successfully made it to the menu
                if state.state != "MENU":
                    raise RuntimeError(f"Expected game state to be MENU, but got {state.state}")
                
                # Start a new run (RED deck, WHITE stake)
                logger.info("Starting new run (RED deck, WHITE stake)...")
                state = self.client.start(deck="RED", stake="WHITE")
                
                # Handle any booster screens (if any auto-opens on startup, unlikely but safe)
                state = self._auto_skip_boosters(state)
                
                self.current_state = state
                obs = encode_observation(state)
                return obs, {}
                
            except Exception as e:
                logger.warning(f"Reset attempt {attempt} failed: {e}")
                if attempt == max_attempts:
                    logger.error("All reset attempts failed.")
                    raise e
                time.sleep(2.0)

    def step(self, action: np.ndarray) -> Tuple[Dict[str, np.ndarray], float, bool, bool, dict]:
        if self.current_state is None:
            raise RuntimeError("Environment must be reset before step can be called.")

        state = self.current_state
        action_dict, is_valid = decode_action(action, state)
        action_type = action_dict.get("action", "wait")
        
        reward = 0.0
        terminated = False
        truncated = False
        
        if not is_valid:
            self.invalid_actions_in_a_row += 1
            reward = -0.1
            new_state = state
            logger.warning(f"Invalid action chosen: {action} (interpreted as {action_dict}) in state {state.state}")
            
            if self.invalid_actions_in_a_row >= self.max_invalid_actions:
                logger.warning(f"Too many invalid actions in a row ({self.invalid_actions_in_a_row}). Truncating episode.")
                truncated = True
        else:
            self.invalid_actions_in_a_row = 0
            
            # Execute action
            try:
                if action_type == "play":
                    new_state = self.client.play(action_dict["cards"])
                elif action_type == "discard":
                    new_state = self.client.discard(action_dict["cards"])
                elif action_type == "select_blind":
                    new_state = self.client.select()
                elif action_type == "skip_blind":
                    new_state = self.client.skip()
                elif action_type == "cash_out":
                    new_state = self.client.cash_out()
                elif action_type == "next_round":
                    new_state = self.client.next_round()
                elif action_type == "start_game":
                    new_state = self.client.start(deck="RED", stake="WHITE")
                elif action_type == "menu":
                    new_state = self.client.menu()
                else:
                    new_state = state
            except BalatroAPIError as e:
                logger.error(f"API Error during step execution: {e}. Attempting to recover state...")
                reward = -0.5
                try:
                    new_state = self.client.gamestate()
                    logger.info(f"State successfully recovered. New state: {new_state.state}")
                except Exception as recovery_err:
                    logger.error(f"Failed to recover state: {recovery_err}")
                    new_state = state
            except Exception as e:
                logger.error(f"Unexpected connection error during step execution: {e}. Attempting to recover state...")
                reward = -0.5
                try:
                    new_state = self.client.gamestate()
                    logger.info(f"State successfully recovered after connection error. New state: {new_state.state}")
                except Exception as recovery_err:
                    logger.error(f"Failed to recover state: {recovery_err}")
                    new_state = state
                
            # Post-action processing: handle booster pack screen
            new_state = self._auto_skip_boosters(new_state)
            
            # Calculate reward
            reward = self._calculate_reward(state, new_state)
            
        # Update current state
        self.current_state = new_state
        obs = encode_observation(new_state)
        
        info = {}
        if new_state.state == "GAME_OVER":
            terminated = True
            
        if terminated or truncated:
            info["episode_metrics"] = {
                "won": bool(new_state.won) if new_state.won is not None else False,
                "ante": int(new_state.ante_num),
                "round": int(new_state.round_num),
                "money": float(new_state.money),
                "chips": float(new_state.round.chips) if new_state.round else 0.0,
            }
            
        return obs, reward, terminated, truncated, info

    def _calculate_reward(self, old_state: GameState, new_state: GameState) -> float:
        reward = 0.0
        
        # 1. Round outcome transitions (Blind won)
        if old_state.state == "SELECTING_HAND" and new_state.state == "ROUND_EVAL":
            reward += 1.0
            
        # 2. Score progression (Reward for playing cards that increase score)
        if old_state.state == "SELECTING_HAND" and new_state.state == "SELECTING_HAND":
            target_score = 0
            for blind in old_state.blinds.values():
                if blind.status == "CURRENT":
                    target_score = blind.score
                    break
            
            if target_score > 0:
                score_diff = new_state.round.chips - old_state.round.chips
                # Reward is proportional to the fraction of blind completed
                reward += max(0.0, float(score_diff) / target_score)
                
        # 3. Ante progression (Defeating Boss Blind of current Ante)
        if int(new_state.ante_num) > int(old_state.ante_num):
            reward += 5.0 * (int(new_state.ante_num) - int(old_state.ante_num))
            logger.info(f"Ante increased from {old_state.ante_num} to {new_state.ante_num}! +5.0 Reward.")

        # 4. Money accumulation (Encourage earning money, but do not penalize spending)
        if float(new_state.money) > float(old_state.money):
            reward += 0.1 * (float(new_state.money) - float(old_state.money))

        # 5. Game end conditions
        if new_state.state == "GAME_OVER":
            if new_state.won:
                reward += 10.0
                logger.info("RUN WON! Large reward given.")
            else:
                reward -= 5.0
                logger.info("GAME OVER (RUN LOST). Penalty given.")
                
        return reward
