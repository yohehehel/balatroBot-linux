import os
import shutil
import urllib.request
import zipfile
import sys
from pathlib import Path

# Paths configuration
BALATRO_DIR = Path(r"c:\Users\Thomas\Desktop\python\balatroBot\Balatro.v1.0.0i")
APPDATA_DIR = Path(os.environ.get("APPDATA", r"C:\Users\Thomas\AppData\Roaming"))
BALATRO_APPDATA = APPDATA_DIR / "Balatro"
MODS_DIR = BALATRO_APPDATA / "Mods"

# URLs for required tools
LOVELY_RELEASE_URL = "https://github.com/ethangreen-dev/lovely-injector/releases/download/v0.8.0/lovely-x86_64-pc-windows-msvc.zip"
# Steamodded 1.0.0-beta-1221a branch zip (stable compat with v1.0.0i)
STEAMODDED_ZIP_URL = "https://github.com/Steamopollys/Steamodded/archive/refs/tags/1.0.0-beta-1221a.zip"
# BalatroBot Lua mod repository zip
BALATROBOT_ZIP_URL = "https://github.com/coder/balatrobot/archive/refs/heads/main.zip"

def download_and_extract(url, extract_to, name=""):
    print(f"Téléchargement de {name} depuis {url}...")
    temp_zip = extract_to / "temp_download.zip"
    try:
        urllib.request.urlretrieve(url, temp_zip)
        print(f"Extraction de {name}...")
        with zipfile.ZipFile(temp_zip, 'r') as zip_ref:
            zip_ref.extractall(extract_to)
        os.remove(temp_zip)
        print(f"{name} installé avec succès dans {extract_to}.")
    except Exception as e:
        print(f"Erreur lors de l'installation de {name}: {e}")
        if temp_zip.exists():
            os.remove(temp_zip)
        raise e

def setup_lovely():
    print("--- Configuration de Lovely Injector ---")
    if not BALATRO_DIR.exists():
        print(f"Erreur: Le répertoire du jeu Balatro n'existe pas : {BALATRO_DIR}")
        sys.exit(1)
    
    # Download lovely injector zip to game directory and extract version.dll
    temp_dir = BALATRO_DIR / "lovely_temp"
    temp_dir.mkdir(exist_ok=True)
    
    try:
        download_and_extract(LOVELY_RELEASE_URL, temp_dir, "Lovely Injector")
        # Find version.dll inside temp_dir
        version_dll = temp_dir / "version.dll"
        if not version_dll.exists():
            # Sometimes inside subdirectory
            for p in temp_dir.glob("**/version.dll"):
                version_dll = p
                break
        
        if version_dll.exists():
            shutil.copy(version_dll, BALATRO_DIR / "version.dll")
            print("version.dll copiée à la racine de Balatro avec succès.")
        else:
            print("Erreur: version.dll introuvable dans l'archive Lovely.")
    finally:
        if temp_dir.exists():
            shutil.rmtree(temp_dir)

def setup_steamodded():
    print("\n--- Configuration de Steamodded ---")
    MODS_DIR.mkdir(parents=True, exist_ok=True)
    smods_dir = MODS_DIR / "smods"
    
    # If already exists, clear it
    if smods_dir.exists():
        shutil.rmtree(smods_dir)
    smods_dir.mkdir(exist_ok=True)
    
    temp_dir = MODS_DIR / "smods_temp"
    temp_dir.mkdir(exist_ok=True)
    
    try:
        download_and_extract(STEAMODDED_ZIP_URL, temp_dir, "Steamodded")
        # Steamodded zip contains a root folder like 'Steamodded-1.0.0-beta-1221a'
        root_dir = next(temp_dir.iterdir())
        for item in root_dir.iterdir():
            shutil.move(str(item), smods_dir / item.name)
        
        # Patch sticker.toml for Balatro v1.0.0i compatibility (rental sticker does not exist in v1.0.0i)
        sticker_toml_path = smods_dir / "lovely" / "sticker.toml"
        if sticker_toml_path.exists():
            print("Applying Balatro v1.0.0i compatibility patch to sticker.toml...")
            sticker_toml_content = sticker_toml_path.read_text(encoding="utf-8")
            fixed_content = sticker_toml_content.replace(
                'pattern = "if v == \'rental\' then*"',
                'pattern = "if v == \'pinned_left\' then*"'
            )
            sticker_toml_path.write_text(fixed_content, encoding="utf-8")
            print("sticker.toml patched successfully.")
            
        # Patch stake.toml for Balatro v1.0.0i compatibility (stake >= 8 does not enable rentals in v1.0.0i)
        stake_toml_path = smods_dir / "lovely" / "stake.toml"
        if stake_toml_path.exists():
            print("Applying Balatro v1.0.0i compatibility patch to stake.toml...")
            stake_toml_content = stake_toml_path.read_text(encoding="utf-8")
            old_patch = """[[patches]]
[patches.pattern]
target = "game.lua"
pattern = "if self.GAME.stake >= 8 then self.GAME.modifiers.enable_rentals_in_shop = true end"
position = "after"
payload = "end SMODS.setup_stake(self.GAME.stake)"
match_indent = true"""
            new_patch = """[[patches]]
[patches.regex]
target = "game.lua"
pattern = '''(?<indent>[\\t ]*)if self\\.GAME\\.stake >= 8 then\\s*(?:self\\.GAME\\.modifiers\\.enable_rentals_in_shop = true\\s*end|.*?\\n[\\t ]*self\\.GAME\\.starting_params\\.hand_size = self\\.GAME\\.starting_params\\.hand_size - 1\\s*\\r?\\n[\\t ]*end)'''
position = "after"
line_prepend = "$indent"
payload = "end SMODS.setup_stake(self.GAME.stake)"\t"""
            normalized_content = stake_toml_content.replace('\r\n', '\n')
            old_patch_normalized = old_patch.replace('\r\n', '\n')
            new_patch_normalized = new_patch.replace('\r\n', '\n')
            fixed_content = normalized_content.replace(old_patch_normalized, new_patch_normalized)
            stake_toml_path.write_text(fixed_content, encoding="utf-8")
            print("stake.toml patched successfully.")
            
        # Patch joker_retriggers.toml for Balatro v1.0.0i compatibility (Yorick event logic)
        joker_retriggers_toml_path = smods_dir / "lovely" / "joker_retriggers.toml"
        if joker_retriggers_toml_path.exists():
            print("Applying Balatro v1.0.0i compatibility patch to joker_retriggers.toml...")
            joker_retriggers_toml_content = joker_retriggers_toml_path.read_text(encoding="utf-8")
            old_patch = """# Yorick
[[patches]]
[patches.pattern]
target = "card.lua"
pattern = "self.ability.yorick_discards = self.ability.yorick_discards - 1"
position = "after"
match_indent = true
payload = "return nil, true\""""
            new_patch = """# Yorick
[[patches]]
[patches.pattern]
target = "card.lua"
pattern = "self.ability.yorick_discards = self.ability.yorick_discards - 1"
position = "after"
match_indent = true
payload = "do return nil, true end\""""
            normalized_content = joker_retriggers_toml_content.replace('\r\n', '\n')
            old_patch_normalized = old_patch.replace('\r\n', '\n')
            new_patch_normalized = new_patch.replace('\r\n', '\n')
            fixed_content = normalized_content.replace(old_patch_normalized, new_patch_normalized)
            joker_retriggers_toml_path.write_text(fixed_content, encoding="utf-8")
            print("joker_retriggers.toml patched successfully.")
            
        # Patch game_object.lua for Balatro v1.0.0i compatibility (G.COLLABS is nil in v1.0.0i)
        game_object_path = smods_dir / "src" / "game_object.lua"
        if game_object_path.exists():
            print("Applying Balatro v1.0.0i compatibility patch to game_object.lua...")
            game_object_content = game_object_path.read_text(encoding="utf-8")
            collabs_patch = """function loadAPIs()
    if not G.COLLABS then
        G.COLLABS = {
            options = {
                Hearts = {'default_Hearts'},
                Clubs = {'default_Clubs'},
                Diamonds = {'default_Diamonds'},
                Spades = {'default_Spades'}
            },
            pos = {},
            colour_palettes = setmetatable({}, {
                __index = function(t, k)
                    return {}
                end
            })
        }
    end
    if G.localization and G.localization.misc then
        G.localization.misc.collabs = G.localization.misc.collabs or {}
        G.localization.misc.collab_palettes = G.localization.misc.collab_palettes or {}
        G.localization.misc.quips = G.localization.misc.quips or {}
    end
    if G.SETTINGS then
        G.SETTINGS.CUSTOM_DECK = G.SETTINGS.CUSTOM_DECK or { Collabs = {} }
        G.SETTINGS.colour_palettes = G.SETTINGS.colour_palettes or {}
    end"""
            normalized_content = game_object_content.replace('\r\n', '\n')
            fixed_content = normalized_content.replace("function loadAPIs()", collabs_patch)
            
            old_skin_block = """                local skin = self.obj_table[G.SETTINGS.CUSTOM_DECK.Collabs[k]]
                local pal = G.SETTINGS.colour_palettes[k]
                if not skin.outdated and skin.palette_map and not skin.palette_map[pal] then
                    G.SETTINGS.colour_palettes[k] = skin.palettes[1].key
                end"""
            new_skin_block = """                local skin = self.obj_table[G.SETTINGS.CUSTOM_DECK.Collabs[k]]
                if skin then
                    local pal = G.SETTINGS.colour_palettes[k]
                    if not skin.outdated and skin.palette_map and not skin.palette_map[pal] then
                        G.SETTINGS.colour_palettes[k] = skin.palettes[1].key
                    end
                end"""
            fixed_content = fixed_content.replace(old_skin_block.replace('\r\n', '\n'), new_skin_block.replace('\r\n', '\n'))
            
            game_object_path.write_text(fixed_content, encoding="utf-8")
            print("game_object.lua patched successfully.")
            
        # Patch card_limit.toml for Balatro v1.0.0i compatibility (local hand_space pattern differs)
        card_limit_toml_path = smods_dir / "lovely" / "card_limit.toml"
        if card_limit_toml_path.exists():
            print("Applying Balatro v1.0.0i compatibility patch to card_limit.toml...")
            card_limit_toml_content = card_limit_toml_path.read_text(encoding="utf-8")
            fixed_content = card_limit_toml_content.replace(
                'pattern = "local hand_space = e or*"',
                'pattern = "local hand_space = math.min(#G.deck.cards, G.hand.config.card_limit - #G.hand.cards)"'
            )
            card_limit_toml_path.write_text(fixed_content, encoding="utf-8")
            print("card_limit.toml patched successfully.")
            
        print("Steamodded configuré dans le dossier Mods/smods.")
    finally:
        if temp_dir.exists():
            shutil.rmtree(temp_dir)

def setup_balatrobot_mod():
    print("\n--- Configuration du Mod BalatroBot ---")
    bot_mod_dir = MODS_DIR / "balatrobot"
    if bot_mod_dir.exists():
        shutil.rmtree(bot_mod_dir)
    bot_mod_dir.mkdir(exist_ok=True)
    
    temp_dir = MODS_DIR / "balatrobot_temp"
    temp_dir.mkdir(exist_ok=True)
    
    try:
        download_and_extract(BALATROBOT_ZIP_URL, temp_dir, "BalatroBot Repo")
        # Repo has a root folder like 'balatrobot-main'
        root_dir = next(temp_dir.iterdir())
        
        # We need to copy files from the mod's LUA files directory:
        # According to BalatroBot documentation:
        # We need balatrobot.json, balatrobot.lua, and the src/lua/ directory copied to Mods/balatrobot/
        
        # In github repo, the mod files are directly in the root or a subfolder?
        # Let's inspect the files or move the whole content of the mod subfolder.
        # Actually, coder/balatrobot is a python package AND a lua mod.
        # Let's look at the structure of the repo. We will copy:
        # - balatrobot.lua
        # - balatrobot.json
        # - src/ folder (contains lua files if any)
        
        # Let's copy the entire contents of the cloned repo to the mod folder for simplicity,
        # or structure it specifically.
        # We can look at what's in the repo.
        # Let's copy:
        #   balatrobot.lua
        #   balatrobot.json
        #   src/ (recursive)
        
        shutil.copy(root_dir / "balatrobot.lua", bot_mod_dir / "balatrobot.lua")
        shutil.copy(root_dir / "balatrobot.json", bot_mod_dir / "balatrobot.json")
        
        # Copy the src directory if it exists and has lua files
        src_lua_src = root_dir / "src"
        if src_lua_src.exists():
            shutil.copytree(src_lua_src, bot_mod_dir / "src")

        # Patch start.lua for clean resets and clearing unlock events
        start_lua_path = bot_mod_dir / "src" / "lua" / "endpoints" / "start.lua"
        if start_lua_path.exists():
            print("Applying BalatroBot start.lua patch...")
            content = start_lua_path.read_text(encoding="utf-8")
            target = "G.FUNCS.setup_run({ config = {} })"
            replacement = "G.FUNCS.setup_run({ config = {} })\n    if G.E_MANAGER and G.E_MANAGER.queues and G.E_MANAGER.queues.unlock then\n      G.E_MANAGER.queues.unlock = {}\n    end\n    G.FUNCS.exit_overlay_menu()"
            if target in content and replacement not in content:
                content = content.replace(target, replacement)
                start_lua_path.write_text(content, encoding="utf-8")
                print("start.lua patched successfully.")

        # Patch balatrobot.lua to override create_unlock_overlay and bypass unlock popups
        balatrobot_lua_path = bot_mod_dir / "balatrobot.lua"
        if balatrobot_lua_path.exists():
            print("Applying BalatroBot balatrobot.lua bypass patch...")
            content = balatrobot_lua_path.read_text(encoding="utf-8")
            bypass_code = "\n-- Bypass unlock popups to prevent the game/API from hanging during automated bot training\nlocal original_create_unlock_overlay = create_unlock_overlay\ncreate_unlock_overlay = function(key)\n  sendInfoMessage(\"Bypassing unlock overlay popup for key: \" .. tostring(key), \"BB.MOD\")\nend\n"
            if "Bypassing unlock overlay popup" not in content:
                content = content + bypass_code
                balatrobot_lua_path.write_text(content, encoding="utf-8")
                print("balatrobot.lua patched successfully.")
            
        print("Mod BalatroBot Lua installé dans Mods/balatrobot.")
    except Exception as e:
        print(f"Erreur lors du déploiement du Mod BalatroBot: {e}")
        # Let's list files to debug if copy failed
        if temp_dir.exists():
            print("Contenu du dépôt téléchargé :")
            for p in temp_dir.glob("**/*"):
                if p.is_file():
                    print("-", p.relative_to(temp_dir))
        raise e
    finally:
        if temp_dir.exists():
            shutil.rmtree(temp_dir)

if __name__ == "__main__":
    setup_lovely()
    setup_steamodded()
    setup_balatrobot_mod()
    print("\n=== INSTALLATION TERMINÉE AVEC SUCCÈS ===")
    print("Veuillez lancer Balatro.exe pour vérifier que Lovely Injector charge bien Steamodded et BalatroBot.")
