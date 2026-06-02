import numpy as np
from gymnasium import spaces
from typing import Dict, Any, Tuple, List
from src.game_state import GameState

# Action Types:
# 0: PLAY_HAND
# 1: DISCARD
# 2: SELECT_BLIND
# 3: SKIP_BLIND
# 4: CASH_OUT
# 5: NEXT_ROUND

def get_action_space() -> spaces.MultiDiscrete:
    # 9 discrete dimensions:
    # Dim 0: action type (0 to 5)
    # Dim 1 to 8: binary selection of cards (0: off, 1: on)
    return spaces.MultiDiscrete([6, 2, 2, 2, 2, 2, 2, 2, 2])

def decode_action(action: np.ndarray, game_state: GameState) -> Tuple[dict, bool]:
    """
    Decodes a Gymnasium action into a dictionary describing the API call.
    Automatically projects/corrects invalid actions into valid ones to prevent agent penalties.
    Always returns True for is_valid.
    """
    action_type = action[0]
    card_mask = action[1:]
    
    state_name = game_state.state
    
    # 1. BLIND_SELECT State
    if state_name == "BLIND_SELECT":
        # Force either select_blind (2) or skip_blind (3). Default to select_blind.
        if action_type in [2, 3]:
            chosen_action = "select_blind" if action_type == 2 else "skip_blind"
        else:
            chosen_action = "select_blind"
            
        # Bugfix: Boss blind cannot be skipped. If the Boss blind is selectable, force select_blind.
        is_boss_selectable = False
        if game_state.blinds:
            for blind in game_state.blinds.values():
                if blind.type == "BOSS" and blind.status in ["SELECT", "CURRENT"]:
                    is_boss_selectable = True
                    break
        if is_boss_selectable and chosen_action == "skip_blind":
            chosen_action = "select_blind"
            
        return {"action": chosen_action}, True
            
    # 2. SELECTING_HAND State
    elif state_name == "SELECTING_HAND":
        if not game_state.hand or not game_state.hand.cards:
            return {"action": "wait"}, True
            
        hand_size = len(game_state.hand.cards)
        # Select cards based on mask, limited to the actual hand size
        selected_cards = [i for i in range(min(8, hand_size)) if card_mask[i] == 1]
        
        # Auto-correct selected cards to be between 1 and 5 cards
        if len(selected_cards) == 0:
            selected_cards = [0]  # Default to the first card in hand
        elif len(selected_cards) > 5:
            selected_cards = selected_cards[:5]  # Truncate to first 5 cards
            
        # Determine the action type: play (0) or discard (1).
        # Map any other value to 0 or 1.
        if action_type not in [0, 1]:
            action_type = action_type % 2
            
        # If discard is chosen but no discards are left, force play (0)
        if action_type == 1 and game_state.round.discards_left <= 0:
            action_type = 0
            
        if action_type == 0:
            return {"action": "play", "cards": selected_cards}, True
        else:
            return {"action": "discard", "cards": selected_cards}, True
            
    # 3. ROUND_EVAL State
    elif state_name == "ROUND_EVAL":
        return {"action": "cash_out"}, True
            
    # 4. SHOP State
    elif state_name == "SHOP":
        return {"action": "next_round"}, True
            
    # 5. Other / Menu / Game Over
    elif state_name == "MENU" or state_name == "GAME_OVER":
        if state_name == "MENU":
            return {"action": "start_game", "deck": "RED", "stake": "WHITE"}, True
        elif state_name == "GAME_OVER":
            return {"action": "menu"}, True
            
    return {"action": "wait"}, True
