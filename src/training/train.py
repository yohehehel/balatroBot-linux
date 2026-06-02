import os
import sys
import argparse
import logging
from stable_baselines3 import PPO
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv
from stable_baselines3.common.callbacks import CheckpointCallback, CallbackList

from src.env.balatro_env import BalatroEnv
from src.training.config import TrainingConfig
from src.utils.metrics import BalatroMetricsCallback

def main():
    parser = argparse.ArgumentParser(description="Train a PPO agent to play Balatro.")
    parser.add_argument("--api-url", type=str, default="http://127.0.0.1:12346", help="Balatro JSON-RPC API URL.")
    parser.add_argument("--total-timesteps", type=int, default=None, help="Override total training timesteps.")
    parser.add_argument("--learning-rate", type=float, default=None, help="Override PPO learning rate.")
    parser.add_argument("--ent-coef", type=float, default=None, help="Override entropy coefficient.")
    parser.add_argument("--resume", type=str, default=None, help="Path to a saved PPO model to resume training from.")
    parser.add_argument("--device", type=str, default=None, help="Override target device (cpu/cuda/auto).")
    args = parser.parse_args()

    # 1. Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    logger = logging.getLogger("TrainPPO")

    # 2. Load configuration
    config = TrainingConfig()
    if args.total_timesteps is not None:
        config.total_timesteps = args.total_timesteps
    if args.learning_rate is not None:
        config.learning_rate = args.learning_rate
    if args.ent_coef is not None:
        config.ent_coef = args.ent_coef
    if args.device is not None:
        config.device = args.device

    # Ensure output directories exist
    os.makedirs(config.log_dir, exist_ok=True)
    os.makedirs(config.model_dir, exist_ok=True)

    logger.info("Initializing Balatro Environment(s)...")
    # 3. Setup environment and detect active instances
    api_urls = []
    
    # If the user overrode --api-url, use only that one.
    # Otherwise, scan for active instances.
    if args.api_url != "http://127.0.0.1:12346":
        api_urls = [args.api_url]
    else:
        logger.info("Scanning for active Balatro API instances on ports 12346-12353...")
        import httpx
        base_port = 12346
        for p in range(base_port, base_port + 8):
            url = f"http://127.0.0.1:{p}"
            try:
                # We use a short timeout so scanning doesn't take too long.
                with httpx.Client(timeout=0.3) as client:
                    r = client.post(url, json={"jsonrpc": "2.0", "method": "health", "id": 1})
                    if r.status_code == 200:
                        api_urls.append(url)
            except Exception:
                pass
        
        if not api_urls:
            # Fallback to default port if none detected
            api_urls = ["http://127.0.0.1:12346"]

    logger.info(f"Active Balatro instance(s) detected: {api_urls}")

    # Helper function to create an env
    def make_env(url):
        def _init():
            return Monitor(BalatroEnv(base_url=url))
        return _init

    if len(api_urls) > 1:
        logger.info(f"Initializing SubprocVecEnv with {len(api_urls)} parallel environments...")
        env = SubprocVecEnv([make_env(url) for url in api_urls])
    else:
        logger.info("Initializing DummyVecEnv for a single environment.")
        # Ensure we can connect to the single instance before proceeding
        try:
            temp_env = BalatroEnv(base_url=api_urls[0])
            health = temp_env.client.health()
            logger.info(f"API Connection established on {api_urls[0]}. Health check: {health}")
        except Exception as e:
            logger.error(f"Could not connect to Balatro JSON-RPC API on {api_urls[0]}. Ensure Balatro is running with the mod loaded!")
            logger.error(str(e))
            sys.exit(1)
        env = DummyVecEnv([make_env(api_urls[0])])

    # 4. Initialize or Load Model
    if args.resume:
        logger.info(f"Resuming training from model checkpoint: {args.resume}")
        model = PPO.load(
            args.resume,
            env=env,
            device=config.device,
            tensorboard_log=config.log_dir,
        )
        # Update hyperparameters if overridden
        if args.learning_rate is not None:
            model.learning_rate = args.learning_rate
        if args.ent_coef is not None:
            model.ent_coef = args.ent_coef
    else:
        logger.info("Creating a new PPO model with MultiInputPolicy...")
        ppo_kwargs = config.to_ppo_kwargs()
        model = PPO(
            "MultiInputPolicy",
            env,
            verbose=1,
            tensorboard_log=config.log_dir,
            **ppo_kwargs
        )

    logger.info(f"Using device: {model.device}")

    # 5. Set up callbacks
    checkpoint_callback = CheckpointCallback(
        save_freq=max(1, config.save_freq),
        save_path=config.model_dir,
        name_prefix="ppo_balatro"
    )
    metrics_callback = BalatroMetricsCallback()
    callbacks = CallbackList([checkpoint_callback, metrics_callback])

    # 6. Start training
    logger.info(f"Starting training loop for {config.total_timesteps} steps...")
    try:
        model.learn(
            total_timesteps=config.total_timesteps,
            callback=callbacks,
            tb_log_name="PPO_Balatro",
            reset_num_timesteps=not args.resume
        )
        
        # Save final model
        final_model_path = os.path.join(config.model_dir, "ppo_balatro_final")
        model.save(final_model_path)
        logger.info(f"Training completed. Final model saved to {final_model_path}")
        
    except KeyboardInterrupt:
        logger.info("Training interrupted by user. Saving current model state...")
        interrupted_path = os.path.join(config.model_dir, "ppo_balatro_interrupted")
        model.save(interrupted_path)
        logger.info(f"Model saved to {interrupted_path}")
        
    except Exception as e:
        logger.error(f"Training crashed: {e}")
        raise e

if __name__ == "__main__":
    main()
