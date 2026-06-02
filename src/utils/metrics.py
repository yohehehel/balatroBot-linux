import numpy as np
from stable_baselines3.common.callbacks import BaseCallback

class BalatroMetricsCallback(BaseCallback):
    """
    Custom callback for logging Balatro-specific metrics (win rate, max ante, money, etc.)
    to TensorBoard at the end of each rollout.
    """
    def __init__(self, verbose: int = 0):
        super().__init__(verbose)
        self.episode_wons = []
        self.episode_antes = []
        self.episode_moneys = []
        self.episode_rounds = []
        self.episode_chips = []

    def _on_step(self) -> bool:
        # Check if there are any environment info updates (SB3 VecEnv passes infos)
        for info in self.locals.get("infos", []):
            if "episode_metrics" in info:
                metrics = info["episode_metrics"]
                self.episode_wons.append(float(metrics.get("won", False)))
                self.episode_antes.append(float(metrics.get("ante", 1)))
                self.episode_moneys.append(float(metrics.get("money", 0.0)))
                self.episode_rounds.append(float(metrics.get("round", 0)))
                self.episode_chips.append(float(metrics.get("chips", 0.0)))
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
