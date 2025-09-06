#!/usr/bin/python3
import os
import json
import pexpect
from flask import Flask, jsonify, request
from redis import Redis

# --- Configuration ---
SAVES_DIR = '/data/saves'
REDIS_HOST = os.environ.get('REDIS_HOST', 'redis')

# --- Initialization ---
app = Flask(__name__)
redis = Redis(host=REDIS_HOST, db=0, socket_connect_timeout=2, socket_timeout=2, decode_responses=True)

# Ensure the save directory exists
os.makedirs(SAVES_DIR, exist_ok=True)


# --- Profile Management ---
def get_profile(email):
    """Retrieves a user profile from Redis."""
    profile_json = redis.get(email)
    return json.loads(profile_json) if profile_json else None

def save_profile(email, profile):
    """Saves a user profile to Redis."""
    redis.set(email, json.dumps(profile))

def get_save_path(save_file):
    """Constructs the full path for a save file."""
    # Basic security check to prevent path traversal
    if ".." in save_file or save_file.startswith("/"):
        raise ValueError("Invalid save file name.")
    return os.path.join(SAVES_DIR, save_file)


# --- Game Interaction ---
def save_game(profile, save_file, game):
    """Saves the current game state."""
    print(f"Saving game to: {save_file}")
    full_save_path = get_save_path(save_file)
    game.sendline("save")
    game.expect(':')
    game.sendline(full_save_path)

    # If the save file already exists, the game will ask to overwrite.
    # We check if the save name is in the user's profile to decide.
    email = profile['email']
    title = save_file.split('.')[1]
    save_name = ".".join(save_file.split('.')[2:])

    if save_name in profile.get(title, []):
        game.expect(['\?', pexpect.EOF, pexpect.TIMEOUT], timeout=5)
        game.sendline("yes")

    game.expect(['>', pexpect.EOF, pexpect.TIMEOUT], timeout=0.2)


def restore_save(save_file, game):
    """Restores a game state from a save file."""
    print(f"Restoring game from: {save_file}")
    full_save_path = get_save_path(save_file)
    title_info, first_line = get_first_lines(game)
    game.sendline("restore")
    game.expect(':')
    game.sendline(full_save_path)
    game.expect(['>', pexpect.EOF, pexpect.TIMEOUT], timeout=0.2)
    return {"titleInfo": title_info, "firstLine": first_line}


def get_first_lines(game):
    """Gets the initial text from the game."""
    game.expect('Serial [n|N]umber [0-9]+')
    title_info = game.before.decode('utf-8') + game.after.decode('utf-8')
    game.expect(['>', pexpect.EOF, pexpect.TIMEOUT], timeout=0.2)
    first_line = game.before.decode('utf-8')
    return title_info, first_line


def start_game(title):
    """Spawns a new game process."""
    print(f"Starting game: {title}")
    game_files = {
        'hike': 'Games/HitchHikers/hhgg.z3',
        'spell': 'Games/Spellbreaker/spellbre.dat',
        'wish': 'Games/Wishbringer/wishbrin.dat',
        'zork1': 'Games/Zork1/zork1.z5',
        'zork2': 'Games/Zork2/zork2.dat',
        'zork3': 'Games/Zork3/ZORK3.DAT'
    }
    game_path = game_files.get(title, game_files['zork1'])
    if not title in game_files:
        title = 'zork1'

    command = f"/usr/games/dfrotz -mp {game_path}"
    game = pexpect.spawn(command)
    return game, title


# --- API Endpoints ---
@app.route("/user", methods=['GET', 'POST'])
def user():
    email = request.args.get('email')
    if not email:
        return jsonify({"error": "Email is required"}), 400

    profile = get_profile(email)
    response_obj = {}

    if not profile:
        print(f"Profile not found for: {email}. Creating new one.")
        profile = {
            "email": email, "hike": [], "spell": [], "wish": [],
            "zork1": [], "zork2": [], "zork3": [], "lastGame": None
        }
        response_obj["newUser"] = True
    else:
        print(f"Profile found for: {email}")
        response_obj["newUser"] = False

    save_profile(email, profile)
    response_obj["profile"] = profile
    return jsonify(response_obj)


@app.route("/newGame", methods=['GET', 'POST'])
def new_game():
    email = request.args.get('email')
    title = request.args.get('title')
    if not email or not title:
        return jsonify({"error": "Email and title are required"}), 400

    profile = get_profile(email)
    if not profile:
        return jsonify({"error": "User profile not found"}), 404

    game, title = start_game(title)
    autosave_file = f"{email}.{title}.AutoSave"
    
    if "AutoSave" in profile[title]:
        try:
            os.remove(get_save_path(autosave_file))
        except OSError as e:
            print(f"Error removing old autosave: {e}")

    title_info, first_line = get_first_lines(game)
    save_game(profile, autosave_file, game)

    profile["lastGame"] = title
    if "AutoSave" not in profile[title]:
        profile[title].append("AutoSave")
    save_profile(email, profile)

    game.terminate()
    return jsonify({
        "titleInfo": title_info,
        "firstLine": first_line,
        "userProfile": profile
    })


@app.route("/start", methods=['GET', 'POST'])
def start():
    email = request.args.get('email')
    title = request.args.get('title')
    save_file_name = request.args.get('save')
    if not email or not title or not save_file_name:
        return jsonify({"error": "Email, title, and save are required"}), 400

    profile = get_profile(email)
    if not profile:
        return jsonify({"error": "User profile not found"}), 404

    game, title = start_game(title)
    save_file = f"{email}.{title}.{save_file_name}"

    restore_obj = restore_save(save_file, game)

    profile["lastGame"] = title
    save_profile(email, profile)

    game.terminate()
    return jsonify({
        "titleInfo": restore_obj["titleInfo"],
        "firstLine": restore_obj["firstLine"],
        "userProfile": profile
    })


@app.route("/action", methods=['GET', 'POST'])
def action():
    email = request.args.get('email')
    title = request.args.get('title')
    action_cmd = request.args.get('action')
    if not email or not title or not action_cmd:
        return jsonify({"error": "Email, title, and action are required"}), 400

    profile = get_profile(email)
    if not profile:
        return jsonify({"error": "User profile not found"}), 404

    game, title = start_game(title)
    autosave_file = f"{email}.{title}.AutoSave"

    area_desc = restore_save(autosave_file, game)
    
    game.sendline(action_cmd)
    game.expect(['>', pexpect.EOF, pexpect.TIMEOUT], timeout=0.2)
    output = game.before.decode('utf-8')

    save_game(profile, autosave_file, game)

    profile["lastGame"] = title
    save_profile(email, profile)

    game.terminate()
    return jsonify({
        "cmdOutput": output,
        "lookOutput": area_desc,
        "userProfile": profile
    })


@app.route("/save", methods=['GET', 'POST'])
def save():
    email = request.args.get('email')
    title = request.args.get('title')
    save_file_name = request.args.get('save')
    if not email or not title or not save_file_name:
        return jsonify({"error": "Email, title, and save are required"}), 400

    profile = get_profile(email)
    if not profile:
        return jsonify({"error": "User profile not found"}), 404

    game, title = start_game(title)
    autosave_file = f"{email}.{title}.AutoSave"
    user_save_file = f"{email}.{title}.{save_file_name}"

    restore_save(autosave_file, game)
    save_game(profile, user_save_file, game)

    profile["lastGame"] = title
    if save_file_name not in profile[title]:
        profile[title].append(save_file_name)
    save_profile(email, profile)

    game.terminate()
    return jsonify(profile)
