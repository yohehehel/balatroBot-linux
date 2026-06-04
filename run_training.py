import os
import sys
import subprocess
import time
import urllib.request
import json
import argparse
from pathlib import Path

def check_health(port):
    url = f"http://127.0.0.1:{port}"
    data = {"jsonrpc": "2.0", "method": "health", "params": {}, "id": 1}
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    try:
        with urllib.request.urlopen(req, timeout=2) as r:
            return r.status == 200
    except Exception:
        return False

def terminate_processes(processes):
    print("Terminating Balatro processes...")
    for p, stdout_file, stderr_file in processes:
        try:
            p.terminate()
            p.wait(timeout=5)
        except Exception:
            try:
                p.kill()
            except Exception:
                pass
        finally:
            try:
                stdout_file.close()
            except Exception:
                pass
            try:
                stderr_file.close()
            except Exception:
                pass
    print("All Balatro processes cleaned up.")

def main():
    parser = argparse.ArgumentParser(description="Run parallel Balatro bot PPO training with managed instances.")
    parser.add_argument("--num-instances", type=int, default=2, help="Number of Balatro instances to run in parallel.")
    parser.add_argument("--total-timesteps", type=int, default=200000, help="Total training timesteps.")
    parser.add_argument("--resume", type=str, default=None, help="Path to a saved PPO model to resume training from.")
    parser.add_argument("--learning-rate", type=float, default=None, help="Override PPO learning rate.")
    parser.add_argument("--ent-coef", type=float, default=None, help="Override entropy coefficient.")
    parser.add_argument("--device", type=str, default=None, help="Override target device (cpu/cuda/auto).")
    parser.add_argument("--deck", type=str, default="YELLOW", help="Deck to use for training. Default: YELLOW.")
    parser.add_argument("--stake", type=str, default="WHITE", help="Stake level. Default: WHITE.")
    args = parser.parse_args()

    balatro_exe = Path(r"c:\Users\Thomas\Desktop\python\balatroBot\Balatro.v1.0.0i\Balatro.exe")
    if not balatro_exe.exists():
        print(f"Error: Balatro.exe not found at {balatro_exe}")
        sys.exit(1)

    appdata = os.environ.get("APPDATA")
    if not appdata:
        print("Error: APPDATA environment variable not found.")
        sys.exit(1)
        
    original_balatro_dir = Path(appdata) / "Balatro"
    original_mods_dir = original_balatro_dir / "Mods"
    
    if not original_mods_dir.exists():
        print(f"Error: Mods directory not found at {original_mods_dir}")
        sys.exit(1)
    
    ports = [12346 + i for i in range(args.num_instances)]
    processes = []
    
    # Clean any orphaned Balatro processes first
    try:
        subprocess.run(["taskkill", "/f", "/im", "Balatro.exe"], capture_output=True)
    except Exception:
        pass

    print(f"Launching {args.num_instances} Balatro instances...")
    for port in ports:
        instance_mods_dir = original_balatro_dir / f"Mods_Instance_{port}"
        
        # Clean and copy mods to isolated folder
        if instance_mods_dir.exists():
            import shutil
            try:
                shutil.rmtree(instance_mods_dir)
            except Exception as e:
                print(f"Warning: Could not clean {instance_mods_dir}: {e}")
        os.makedirs(instance_mods_dir, exist_ok=True)
        
        print(f"Copying mods for instance on port {port}...")
        for mod_path in original_mods_dir.iterdir():
            if mod_path.is_dir() and mod_path.name.lower() != "lovely":
                import shutil
                shutil.copytree(mod_path, instance_mods_dir / mod_path.name)
                
        env = os.environ.copy()
        env["LOVELY_MOD_DIR"] = str(instance_mods_dir)
        env["BALATROBOT_HOST"] = "127.0.0.1"
        env["BALATROBOT_PORT"] = str(port)
        env["BALATROBOT_FAST"] = "1"
        env["BALATROBOT_GAMESPEED"] = "10"
        env["BALATROBOT_ANIMATION_FPS"] = "60"
        env["BALATROBOT_FPS_CAP"] = "120"
        env["BALATROBOT_NO_SHADERS"] = "1"
        env["BALATROBOT_HEADLESS"] = "1"
        env["BALATROBOT_RENDER_ON_API"] = "0"
        
        stdout_log = original_balatro_dir / f"instance_{port}_stdout.log"
        stderr_log = original_balatro_dir / f"instance_{port}_stderr.log"
        
        stdout_file = open(stdout_log, "w", encoding="utf-8", errors="ignore")
        stderr_file = open(stderr_log, "w", encoding="utf-8", errors="ignore")
        
        p = subprocess.Popen(
            [str(balatro_exe)],
            cwd=str(balatro_exe.parent),
            env=env,
            stdout=stdout_file,
            stderr=stderr_file
        )
        processes.append((p, stdout_file, stderr_file))
        print(f"Started instance on port {port} (PID: {p.pid})")
        time.sleep(2.0)
        
    print("Waiting 15 seconds for initialization...")
    time.sleep(15)
    
    # Check health
    all_healthy = True
    for port in ports:
        if check_health(port):
            print(f"Health check PASSED for port {port}")
        else:
            print(f"Health check FAILED for port {port}")
            all_healthy = False
            
    if not all_healthy:
        print("Not all instances started successfully. Aborting training.")
        terminate_processes(processes)
        sys.exit(1)
        
    print(f"Starting training session for {args.total_timesteps} timesteps...")
    
    # Forward arguments to train.py
    cmd = [
        sys.executable, "-m", "src.training.train",
        "--total-timesteps", str(args.total_timesteps)
    ]
    if args.resume:
        cmd.extend(["--resume", args.resume])
    if args.learning_rate is not None:
        cmd.extend(["--learning-rate", str(args.learning_rate)])
    if args.ent_coef is not None:
        cmd.extend(["--ent-coef", str(args.ent_coef)])
    if args.device:
        cmd.extend(["--device", args.device])
    cmd.extend(["--deck", args.deck])
    cmd.extend(["--stake", args.stake])

    try:
        # Use python from active virtualenv if present
        venv_python = Path(r"c:\Users\Thomas\Desktop\python\balatroBot\.venv\Scripts\python.exe")
        python_exe = str(venv_python) if venv_python.exists() else sys.executable
        cmd[0] = python_exe
        
        subprocess.run(
            cmd,
            cwd=r"c:\Users\Thomas\Desktop\python\balatroBot",
            check=True
        )
        print("Training session finished successfully!")
    except KeyboardInterrupt:
        print("Training interrupted by user. Cleaning up...")
    except Exception as e:
        print(f"Error during training: {e}")
    finally:
        terminate_processes(processes)

if __name__ == "__main__":
    main()
