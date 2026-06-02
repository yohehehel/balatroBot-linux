import os
import sys
import subprocess
import argparse
import shutil
import time
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="Launch multiple Balatro instances configured for parallel bot training.")
    parser.add_argument("--num-instances", type=int, default=2, help="Number of Balatro instances to launch.")
    parser.add_argument("--visible", action="store_true", help="Launch visible windows instead of headless.")
    parser.add_argument("--base-port", type=int, default=12346, help="Starting port for JSON-RPC API.")
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
        print(f"Error: Mods directory not found at {original_mods_dir}. Please run setup_mods.py first.")
        sys.exit(1)

    processes = []
    print(f"Launching {args.num_instances} isolated Balatro instances starting on port {args.base_port}...")
    
    for i in range(args.num_instances):
        port = args.base_port + i
        
        # Isolate mod folder for this port to prevent log collisions
        instance_mods_dir = original_balatro_dir / f"Mods_Instance_{port}"
        
        # Remove any existing instance mods dir to start fresh and avoid sharing state
        if instance_mods_dir.exists():
            try:
                shutil.rmtree(instance_mods_dir)
            except Exception as e:
                print(f"  Warning: Could not clean {instance_mods_dir}: {e}")
                    
        os.makedirs(instance_mods_dir, exist_ok=True)
        
        # Copy required mod directories (smods, balatrobot)
        # We skip 'lovely' directory because it contains large log/dump files and will be auto-created
        print(f"  Copying mods for instance on port {port}...")
        for mod_path in original_mods_dir.iterdir():
            if mod_path.is_dir() and mod_path.name.lower() != "lovely":
                target_path = instance_mods_dir / mod_path.name
                shutil.copytree(mod_path, target_path)

        env = os.environ.copy()
        # Instruct Lovely Injector to use this isolated mod folder (saves logs and loads mods here)
        env["LOVELY_MOD_DIR"] = str(instance_mods_dir)
        env["BALATROBOT_HOST"] = "127.0.0.1"
        env["BALATROBOT_PORT"] = str(port)
        env["BALATROBOT_FAST"] = "1"
        env["BALATROBOT_GAMESPEED"] = "10"
        env["BALATROBOT_ANIMATION_FPS"] = "60"
        env["BALATROBOT_FPS_CAP"] = "120"
        env["BALATROBOT_NO_SHADERS"] = "1"
        
        if args.visible:
            print(f"  [{i+1}/{args.num_instances}] Launching VISIBLE instance on port {port}...")
            env["BALATROBOT_HEADLESS"] = "0"
            env["BALATROBOT_RENDER_ON_API"] = "1"
        else:
            print(f"  [{i+1}/{args.num_instances}] Launching HEADLESS instance on port {port}...")
            env["BALATROBOT_HEADLESS"] = "1"
            env["BALATROBOT_RENDER_ON_API"] = "0"
            
        stdout_log = original_balatro_dir / f"instance_{port}_stdout.log"
        stderr_log = original_balatro_dir / f"instance_{port}_stderr.log"
        
        # Keep file handles open in a list to prevent them from being closed
        # immediately on Windows before Balatro has finished starting up.
        if 'opened_files' not in locals():
            opened_files = []
            
        try:
            stdout_file = open(stdout_log, "w", encoding="utf-8", errors="ignore")
            stderr_file = open(stderr_log, "w", encoding="utf-8", errors="ignore")
            opened_files.append(stdout_file)
            opened_files.append(stderr_file)
            
            process = subprocess.Popen(
                [str(balatro_exe)],
                cwd=str(balatro_exe.parent),
                env=env,
                stdout=stdout_file,
                stderr=stderr_file
            )
            processes.append(process)
            print(f"    Started successfully (PID: {process.pid}) at http://127.0.0.1:{port}")
            print(f"      Logs: {stdout_log.name} and {stderr_log.name}")
        except Exception as e:
            print(f"    Failed to launch instance on port {port}: {e}")
            
        # Stagger the launches to avoid concurrent file lock collisions on settings.jkr on startup
        if i < args.num_instances - 1:
            print("  Waiting 2 seconds before launching the next instance to prevent startup collisions...")
            time.sleep(2.0)
            
    print("\nAll isolated instances started successfully.")
    print("You can now run your training script: python -m src.training.train")
    
    # We intentionally do not close the file handles here.
    # On Windows, closing them or letting them close when the launcher script exits
    # can cause the child processes to crash if the handles are not kept alive.
    # The OS will clean them up when the child processes themselves exit.

if __name__ == "__main__":
    main()
