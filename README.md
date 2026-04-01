# ZorkAPI

A stateless REST API for playing classic Infocom interactive fiction games (Zork I, II, III, Hitchhiker's Guide to the Galaxy, Spellbreaker, and Wishbringer) powered by [Frotz](https://davidgriffith.gitlab.io/frotz/).

All game state is encoded into a **game token** returned with each response. The server stores nothing — no database, no save files, no user accounts. Clients hold their own state and send it back with each request.

## How It Works

The game token is a compressed, signed snapshot of the Z-machine's memory at a given point in the game. It captures everything: position, inventory, score, puzzle progress, and world state. Each action returns a new game token representing the updated state.

```
Client                                Server
  |                                     |
  |  POST /new_game {title}             |
  |------------------------------------>|
  |                                     |  spawn dfrotz, capture intro
  |  {game_token, output}               |
  |<------------------------------------|
  |                                     |
  |  POST /action {game_token, action}  |
  |------------------------------------>|
  |                                     |  decode, restore, execute,
  |                                     |  save, encode new token
  |  {game_token, output}               |
  |<------------------------------------|
  |                                     |
```

Clients can store multiple game tokens in browser localStorage (or anywhere) to implement save slots, undo, branching — whatever they want.

## Running Locally

### Prerequisites
* Python 3.9+
* [dfrotz](https://davidgriffith.gitlab.io/frotz/) (the headless Frotz interpreter)

On Debian/Ubuntu:
```sh
sudo apt-get install frotz
```

On macOS:
```sh
brew install frotz
```

### Install and run

```sh
pip install -r requirements.txt
GAME_TOKEN_SECRET=your-secret-here gunicorn --bind 0.0.0.0:8000 app:app
```

Or for development with Flask's built-in server:
```sh
pip install -r requirements.txt
GAME_TOKEN_SECRET=your-secret-here flask run --port 8000
```

The API will be available at `http://localhost:8000`.

> **Note:** `dfrotz` must be installed at `/usr/games/dfrotz` (the default on Debian/Ubuntu). On macOS or other systems, you may need to symlink it or update the `DFROTZ_PATH` in `app.py`.

## Running with Docker

```sh
docker build -t zorkapi .
docker run -p 8000:8000 -e GAME_TOKEN_SECRET=your-secret-here zorkapi
```

This bundles Python, Frotz, and the game files into a single container — no system dependencies needed.

## Configuration

Set `GAME_TOKEN_SECRET` to any stable string — it's used to sign game tokens so they can't be tampered with. If you don't set it, an ephemeral key is generated (tokens won't survive a server restart).

## API Endpoints

### `GET /games`

List available games.

**Response:**
```json
{
  "games": ["hike", "spell", "wish", "zork1", "zork2", "zork3"]
}
```

### `POST /new_game`

Start a fresh game.

**Request:**
```json
{
  "title": "zork1"
}
```

**Response:**
```json
{
  "game_token": "AQV6b3JrMXjac_MP8mVgYHTx...",
  "output": "ZORK I: The Great Underground Empire\n\nWest of House\nYou are standing in an open field west of a white house...",
  "title": "zork1"
}
```

### `POST /action`

Execute a command in the game.

**Request:**
```json
{
  "game_token": "AQV6b3JrMXjac_MP8mVgYHTx...",
  "action": "open mailbox"
}
```

**Response:**
```json
{
  "game_token": "AQV6b3JrMXjalZDNSgJRFIC_...",
  "output": "Opening the small mailbox reveals a leaflet.",
  "title": "zork1"
}
```

If the game ends (player dies, quits, etc.), `game_token` will be `null` and `game_over` will be `true`.

## Available Games

| Title | Game |
|-------|------|
| `zork1` | Zork I: The Great Underground Empire |
| `zork2` | Zork II: The Wizard of Frobozz |
| `zork3` | Zork III: The Dungeon Master |
| `hike` | The Hitchhiker's Guide to the Galaxy |
| `spell` | Spellbreaker |
| `wish` | Wishbringer |

## Game Tokens

Game tokens are ~300-700 characters for early game states, growing to ~2,000-3,000 characters deep into a playthrough. They're URL-safe base64 strings containing:

- A version byte
- The game identifier
- zlib-compressed Quetzal save data (the Z-machine's native save format)
- An HMAC-SHA256 signature

Every game token is a self-contained, complete snapshot. Replaying an old token restores that exact moment — same room, same inventory, same score, same world state.
