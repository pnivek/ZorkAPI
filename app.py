#!/usr/bin/python3
import os
import zlib
import hmac
import hashlib
import base64
import tempfile
import pexpect
from flask import Flask, jsonify, request
from flask_cors import CORS

# --- Configuration ---
HMAC_SECRET = os.environ.get('GAME_TOKEN_SECRET', '').encode() or os.urandom(32)
if not os.environ.get('GAME_TOKEN_SECRET'):
    print("WARNING: GAME_TOKEN_SECRET not set. Generated ephemeral key. "
          "Tokens will not survive server restart, and may fail across workers "
          "unless gunicorn --preload is used.")

TOKEN_VERSION = 0x01
DFROTZ_PATH = '/usr/games/dfrotz'
PEXPECT_TIMEOUT = 5

GAME_FILES = {
    'hike':  'Games/HitchHikers/hhgg.z3',
    'spell': 'Games/Spellbreaker/spellbre.dat',
    'wish':  'Games/Wishbringer/wishbrin.dat',
    'zork1': 'Games/Zork1/zork1.z5',
    'zork2': 'Games/Zork2/zork2.dat',
    'zork3': 'Games/Zork3/ZORK3.DAT',
}

# --- Initialization ---
app = Flask(__name__)
CORS(app)


# --- Token Encoding/Decoding ---
def encode_game_token(game_id, save_bytes):
    """Encode a Quetzal save file into a signed, compressed game token string."""
    game_id_bytes = game_id.encode('ascii')
    payload = bytes([TOKEN_VERSION, len(game_id_bytes)]) + game_id_bytes + zlib.compress(save_bytes, 9)
    mac = hmac.new(HMAC_SECRET, payload, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(payload + mac).decode('ascii')


def decode_game_token(token):
    """Decode a game token string back into (game_id, save_bytes). Raises ValueError on invalid tokens."""
    try:
        raw = base64.urlsafe_b64decode(token)
    except Exception:
        raise ValueError("Invalid game token: bad encoding")

    if len(raw) < 36:  # 1 + 1 + 1 (min game_id) + 1 (min zlib) + 32 (hmac)
        raise ValueError("Invalid game token: too short")

    payload, received_mac = raw[:-32], raw[-32:]
    expected_mac = hmac.new(HMAC_SECRET, payload, hashlib.sha256).digest()
    if not hmac.compare_digest(received_mac, expected_mac):
        raise ValueError("Invalid game token: signature mismatch")

    version = payload[0]
    if version != TOKEN_VERSION:
        raise ValueError(f"Invalid game token: unsupported version {version}")

    game_id_len = payload[1]
    game_id = payload[2:2 + game_id_len].decode('ascii')
    compressed = payload[2 + game_id_len:]

    try:
        save_bytes = zlib.decompress(compressed)
    except zlib.error:
        raise ValueError("Invalid game token: corrupt data")

    return game_id, save_bytes


# --- Frotz Interaction Helpers ---
def spawn_game(game_id):
    """Spawn a new dfrotz process for the given game."""
    if game_id not in GAME_FILES:
        raise ValueError(f"Unknown game '{game_id}'. Available: {list(GAME_FILES.keys())}")
    game_path = GAME_FILES[game_id]
    return pexpect.spawn(f"{DFROTZ_PATH} -mp {game_path}", encoding=None)


def get_intro_text(game):
    """Consume and return the intro text dfrotz prints on startup."""
    game.expect('Serial [n|N]umber [0-9]+', timeout=PEXPECT_TIMEOUT)
    title_info = game.before.decode('utf-8', errors='replace') + game.after.decode('utf-8', errors='replace')
    index = game.expect(['>', pexpect.EOF, pexpect.TIMEOUT], timeout=PEXPECT_TIMEOUT)
    if index == 1:
        raise RuntimeError("Game process ended unexpectedly during intro")
    if index == 2:
        raise RuntimeError("Game did not produce a prompt after intro")
    first_line = game.before.decode('utf-8', errors='replace')
    return title_info, first_line


def save_to_file(game, save_path):
    """Send the save command to dfrotz and write the state to save_path."""
    game.sendline("save")
    game.expect(':', timeout=PEXPECT_TIMEOUT)
    game.sendline(save_path)
    # Handle both cases: overwrite prompt or direct success
    index = game.expect([r'\?', '>', pexpect.EOF, pexpect.TIMEOUT], timeout=PEXPECT_TIMEOUT)
    if index == 0:  # Overwrite prompt
        game.sendline("yes")
        idx2 = game.expect(['>', pexpect.EOF, pexpect.TIMEOUT], timeout=PEXPECT_TIMEOUT)
        if idx2 != 0:
            raise RuntimeError("Failed to save game after overwrite confirmation")
    elif index >= 2:
        raise RuntimeError("Failed to save game")


def restore_from_file(game, save_path):
    """Send the restore command to dfrotz to load state from save_path."""
    game.sendline("restore")
    game.expect(':', timeout=PEXPECT_TIMEOUT)
    game.sendline(save_path)
    index = game.expect(['>', pexpect.EOF, pexpect.TIMEOUT], timeout=PEXPECT_TIMEOUT)
    if index == 1:
        raise RuntimeError("Game process ended unexpectedly during restore")
    if index == 2:
        raise RuntimeError("Game did not respond after restore")


# --- API Endpoints ---
@app.route("/games", methods=["GET"])
def list_games():
    """List all available games."""
    return jsonify({"games": list(GAME_FILES.keys())})


@app.route("/new_game", methods=["POST"])
def new_game():
    """Start a fresh game and return the initial game token."""
    data = request.get_json(force=True)
    title = data.get("title", "").lower().strip()

    if title not in GAME_FILES:
        return jsonify({"error": f"Unknown game '{title}'", "available": list(GAME_FILES.keys())}), 400

    game = None
    save_path = None
    try:
        game = spawn_game(title)
        title_info, first_line = get_intro_text(game)

        # Save initial state to temp file, read it back as bytes
        fd, save_path = tempfile.mkstemp(suffix='.qzl')
        os.close(fd)
        os.unlink(save_path)  # Remove so dfrotz doesn't see an existing file
        save_to_file(game, save_path)

        with open(save_path, 'rb') as f:
            save_bytes = f.read()

        game_token = encode_game_token(title, save_bytes)

        return jsonify({
            "game_token": game_token,
            "output": (title_info + "\n" + first_line).strip(),
            "title": title,
        })
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if game:
            game.terminate(force=True)
        if save_path and os.path.exists(save_path):
            os.unlink(save_path)


@app.route("/action", methods=["POST"])
def action():
    """Execute a game command and return the new game token + output."""
    data = request.get_json(force=True)
    game_token = data.get("game_token", "")
    action_cmd = data.get("action", "").strip()

    if not game_token:
        return jsonify({"error": "game_token is required"}), 400
    if not action_cmd:
        return jsonify({"error": "action is required"}), 400

    game = None
    restore_path = None
    save_path = None
    try:
        # Decode the incoming game token
        title, save_bytes = decode_game_token(game_token)

        # Write save bytes to temp file for restore
        fd, restore_path = tempfile.mkstemp(suffix='.qzl')
        os.close(fd)
        with open(restore_path, 'wb') as f:
            f.write(save_bytes)

        # Spawn game, consume intro, restore state
        game = spawn_game(title)
        get_intro_text(game)  # must consume intro before restore
        restore_from_file(game, restore_path)

        # Execute the player's command
        game.sendline(action_cmd)
        index = game.expect(['>', pexpect.EOF, pexpect.TIMEOUT], timeout=PEXPECT_TIMEOUT)
        output = game.before.decode('utf-8', errors='replace').strip()

        # If the game ended (player died, quit, etc.), return output with no new game token
        if index == 1:  # EOF
            return jsonify({
                "game_token": None,
                "output": output,
                "title": title,
                "game_over": True,
            })

        if index == 2:  # TIMEOUT
            raise RuntimeError("Game did not respond to action in time")

        # Save new state to temp file, read back
        fd, save_path = tempfile.mkstemp(suffix='.qzl')
        os.close(fd)
        os.unlink(save_path)
        save_to_file(game, save_path)

        with open(save_path, 'rb') as f:
            new_save_bytes = f.read()

        new_game_token = encode_game_token(title, new_save_bytes)

        return jsonify({
            "game_token": new_game_token,
            "output": output,
            "title": title,
        })
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if game:
            game.terminate(force=True)
        for path in [restore_path, save_path]:
            if path and os.path.exists(path):
                os.unlink(path)
