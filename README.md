# ZorkAPI

A RESTful **GET-based** API server for playing classic Infocom text adventure games (Z-machine format), with robust support for persistent save files, sessionless user state, and bot/web integration.

---

## Table of Contents

- [Overview](#overview)
- [Installation & Deployment](#installation--deployment)
- [Supported Games](#supported-games)
- [API Lifecycle: How to Play](#api-lifecycle-how-to-play)
- [Endpoints Reference](#endpoints-reference)
- [Save, Restore, and Persistence](#save-restore-and-persistence)
- [Example Walkthroughs (with GET requests)](#example-walkthroughs-with-get-requests)
- [Game-Specific Notes](#game-specific-notes)
- [FAQ](#faq)

---

## Overview

ZorkAPI exposes a web API for playing classic Infocom games (Zork I/II/III, etc.) with persistent, per-user state. All access is via HTTP GET requests—perfect for low-friction bot, assistant, and web integration.  
_Game state and saves are tracked per user (by email) for each game title._

---

## Installation & Deployment

### Prerequisites

- Docker + Docker Compose (recommended)
- Redis (managed by Compose for fast state access)

### Quickstart

```

git clone https://github.com/pnivek/ZorkAPI.git
cd ZorkAPI
docker-compose up --build

```

The API will be available at:  
`http://localhost:8000`

To stop:
```

Ctrl+C \# in the running window
docker-compose down

```

---

## Supported Games

- zork1 (ZORK I)
- zork2 (ZORK II)
- zork3 (ZORK III)
- spell, hike, wish* (other compatible Z-machine story files)

---

## API Lifecycle: How to Play

**All API calls use HTTP GET with query parameters.**

### 1. User Profile

Initialize or retrieve your profile:
```

GET /user?email=your_email

```

---

### 2. Start a New Game

Begin a new adventure and reset progress:
```

GET /newGame?email=your_email\&title=zork1

```

- 'title' is the game name (e.g., zork1, zork2, ...)

---

### 3. Core Gameplay Loop: Take Actions

For each move, call:
```

GET /action?email=your_email\&title=zork1\&action=open mailbox
GET /action?email=your_email\&title=zork1\&action=take leaflet
GET /action?email=your_email\&title=zork1\&action=inventory
GET /action?email=your_email\&title=zork1\&action=look

```
- Each call updates game state and persists progress (AutoSave).

---

### 4. Save & Restore (Named Save Points)

Save to a named checkpoint:
```

GET /save?email=your_email\&title=zork1\&save=SafePoint1

```
Resume from a named save:
```

GET /start?email=your_email\&title=zork1\&save=SafePoint1

```
- Resumes and future `/action` calls will persist from that point.

---

## Endpoints Reference

### `/user`
**GET /user?email=your_email**  
- Returns your profile and save slots.

---
### `/newGame`
**GET /newGame?email=your_email&title=game_title**  
- Starts a fresh game, wipes progress for that title, creates a new AutoSave.

---
### `/action`
**GET /action?email=your_email&title=game_title&action=your_command**  
- Submits a Zork command (turn), updates state, and returns prompt/game response.

---
### `/save`
**GET /save?email=your_email&title=game_title&save=save_name**  
- Saves your current spot under the given name.

---
### `/start`
**GET /start?email=your_email&title=game_title&save=save_name**  
- Loads a named save and sets it as AutoSave for future play.

---

## Save, Restore, and Persistence

- **AutoSave**: Each `/action` rewrites your per-user/game “AutoSave” (autosave progress).
- **Explicit named saves**: Use `/save` and `/start` for custom restore points, great for tricky sections or backtracking.

---

## Example Walkthroughs (with GET requests)

### Zork I (Mailbox & Leaflet)

```

curl "http://localhost:8000/user?email=foo@bar.com"
curl "http://localhost:8000/newGame?email=foo@bar.com\&title=zork1"
curl "http://localhost:8000/action?email=foo@bar.com\&title=zork1\&action=open mailbox"
curl "http://localhost:8000/action?email=foo@bar.com\&title=zork1\&action=take leaflet"
curl "http://localhost:8000/action?email=foo@bar.com\&title=zork1\&action=inventory"
curl "http://localhost:8000/action?email=foo@bar.com\&title=zork1\&action=look"
curl "http://localhost:8000/save?email=foo@bar.com\&title=zork1\&save=LeafletCheckpoint"

```

### Zork II (Lantern)

```

curl "http://localhost:8000/newGame?email=foo@bar.com\&title=zork2"
curl "http://localhost:8000/action?email=foo@bar.com\&title=zork2\&action=take lantern"
curl "http://localhost:8000/action?email=foo@bar.com\&title=zork2\&action=inventory"

```

---

## Game-Specific Notes

- **title** must match a supported game (e.g., zork1, zork2).
- Objects available for actions depend on the selected game; e.g., 'mailbox' exists only in Zork I.
- All your state is managed by your email as your unique ID—no cookies or sessions required.

---

## FAQ

**Q: Are saves/turns persisted between sessions or browsers?**  
A: Yes. All progress is by email+game, and the API is stateless.

**Q: Can I play multiple games at once?**  
A: Yes, every game’s state is saved independently.

**Q: What if I use the wrong object/action?**  
A: The game’s own parser will respond (e.g., “I don’t know the word...” or similar). Refer to Infocom documentation for vocabulary.

**Q: Are all client/server actions GET?**  
A: Yes. All endpoints respond to GET requests using query parameters.

---

## Credits

- **Original Author:** [Aristoddle/ZorkAPI](https://github.com/Aristoddle/ZorkAPI)

---
