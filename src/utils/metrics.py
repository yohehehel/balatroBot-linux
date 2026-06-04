import os
import json
import numpy as np
from stable_baselines3.common.callbacks import BaseCallback

class BalatroMetricsCallback(BaseCallback):
    """
    Custom callback for logging Balatro-specific metrics (win rate, max ante, money, etc.)
    to TensorBoard at the end of each rollout, and maintaining a local high-score file.
    """
    def __init__(self, verbose: int = 0):
        super().__init__(verbose)
        self.episode_wons = []
        self.episode_antes = []
        self.episode_moneys = []
        self.episode_rounds = []
        self.episode_chips = []
        
        self.records_path = "logs/best_records.json"
        self.best_records = {
            "best_ante": 1,
            "best_money": 0.0,
            "best_chips": 0.0,
            "total_episodes": 0
        }
        self._load_records()

    def _load_records(self):
        if os.path.exists(self.records_path):
            try:
                with open(self.records_path, "r", encoding="utf-8") as f:
                    self.best_records.update(json.load(f))
            except Exception:
                pass

    def _save_records(self):
        os.makedirs(os.path.dirname(self.records_path), exist_ok=True)
        try:
            with open(self.records_path, "w", encoding="utf-8") as f:
                json.dump(self.best_records, f, indent=4)
        except Exception:
            pass

    def _on_step(self) -> bool:
        # Check if there are any environment info updates (SB3 VecEnv passes infos)
        for info in self.locals.get("infos", []):
            if "episode_metrics" in info:
                metrics = info["episode_metrics"]
                won = bool(metrics.get("won", False))
                ante = int(metrics.get("ante", 1))
                money = float(metrics.get("money", 0.0))
                round_num = int(metrics.get("round", 0))
                chips = float(metrics.get("chips", 0.0))

                self.episode_wons.append(float(won))
                self.episode_antes.append(float(ante))
                self.episode_moneys.append(money)
                self.episode_rounds.append(float(round_num))
                self.episode_chips.append(chips)

                # Check and update historical best records
                updated = False
                self.best_records["total_episodes"] += 1
                if ante > self.best_records["best_ante"]:
                    self.best_records["best_ante"] = ante
                    updated = True
                if money > self.best_records["best_money"]:
                    self.best_records["best_money"] = money
                    updated = True
                if chips > self.best_records["best_chips"]:
                    self.best_records["best_chips"] = chips
                    updated = True

                if updated:
                    self._save_records()

        return True

    def _on_rollout_end(self) -> None:
        """
        Called when a rollout ends. Logs the average of the metrics collected
        during the rollout and clears the history.
        """
        if len(self.episode_wons) > 0:
            self.logger.record("balatro/win_rate", np.mean(self.episode_wons))
            self.logger.record("balatro/mean_max_ante", np.mean(self.episode_antes))
            self.logger.record("balatro/mean_money", np.mean(self.episode_moneys))
            self.logger.record("balatro/mean_round_num", np.mean(self.episode_rounds))
            self.logger.record("balatro/mean_final_chips", np.mean(self.episode_chips))
            
            # Clear history
            self.episode_wons.clear()
            self.episode_antes.clear()
            self.episode_moneys.clear()
            self.episode_rounds.clear()
            self.episode_chips.clear()
