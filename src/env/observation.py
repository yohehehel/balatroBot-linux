import numpy as np
from typing import Dict, Any
from gymnasium import spaces
from src.game_state import GameState, Card

STATES = [
    "UNKNOWN", "MENU", "BLIND_SELECT", "SELECTING_HAND",
    "ROUND_EVAL", "SHOP", "GAME_OVER", "SMODS_BOOSTER_OPENED"
]

SUITS = ["H", "D", "C", "S"]
RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "T", "J", "Q", "K", "A"]

def get_state_idx(state_name: str) -> int:
    if state_name in {"TAROT_PACK", "PLANET_PACK", "SPECTRAL_PACK", "STANDARD_PACK", "BUFFOON_PACK"}:
        state_name = "SMODS_BOOSTER_OPENED"
    try:
        return STATES.index(state_name)
    except ValueError:
        return 0

def get_observation_space() -> spaces.Dict:
    return spaces.Dict({
        "game_info": spaces.Box(low=0.0, high=1e9, shape=(10,), dtype=np.float32),
        "hand_cards": spaces.Box(low=0.0, high=1.0, shape=(8, 20), dtype=np.float32)
    })

def encode_card(card: Card) -> np.ndarray:
    # 20 features per card:
    # 4 for suit one-hot
    # 13 for rank one-hot
    # 3 for state flags (debuffed, hidden, highlight)
    features = np.zeros(20, dtype=np.float32)
    
    # Suit one-hot
    suit = card.value.suit
    if suit in SUITS:
        features[SUITS.index(suit)] = 1.0
        
    # Rank one-hot
    rank = card.value.rank
    if rank in RANKS:
        features[4 + RANKS.index(rank)] = 1.0
        
    # Flags
    if card.state.debuff:
        features[17] = 1.0
    if card.state.hidden:
        features[18] = 1.0
    if card.state.highlight:
        features[19] = 1.0
        
    return features

def encode_observation(state: GameState) -> Dict[str, np.ndarray]:
    # 1. Encode game_info (10 elements)
    # - round_num
    # - ante_num
    # - money
    # - hands_left
    # - hands_played
    # - discards_left
    # - discards_used
    # - chips (current round score)
    # - blind_target
    # - state_idx
    target_score = 0
    for blind in state.blinds.values():
        if blind.status == "CURRENT":
            target_score = blind.score
            break
            
    game_info = np.array([
        float(state.round_num),
        float(state.ante_num),
        float(state.money),
        float(state.round.hands_left),
        float(state.round.hands_played),
        float(state.round.discards_left),
        float(state.round.discards_used),
        float(state.round.chips),
        float(target_score),
        float(get_state_idx(state.state))
    ], dtype=np.float32)
    
    # 2. Encode hand_cards (8 slots, 20 features each)
    hand_cards = np.zeros((8, 20), dtype=np.float32)
    if state.hand and state.hand.cards:
        for i, card in enumerate(state.hand.cards[:8]):
            hand_cards[i] = encode_card(card)
            
    return {
        "game_info": game_info,
        "hand_cards": hand_cards
    }
