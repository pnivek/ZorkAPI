Check out the [GitHub Site](https://aristoddle.github.io/ZorkAPI/) for this project.  The colors are bad but it's much more readable.
# ZorkAPI
This is the codebase for the flask-based server that serves ZorkBot, a Bot built on the Microsoft Bot Framework to modernize and make accessable Interactive Fiction games from the DOS era.

This page also works as a general API definition for the system that it powers.  Read below and [CHECK OUT THE GITHUB-GENERATED WEBSITE](https://aristoddle.github.io/ZorkAPI/) to read more about the system's functionality

## Running with Docker Compose

This project is configured to run in Docker containers managed by Docker Compose. This is the recommended way to run the application for development and production.

### Prerequisites
* [Docker](https://docs.docker.com/get-docker/)
* [Docker Compose](https://docs.docker.com/compose/install/)

### Instructions
1.  **Clone the repository:**
    ```sh
    git clone <repository-url>
    cd ZorkAPI
    ```

2.  **Start the application stack:**
    ```sh
    docker-compose up --build
    ```
    This command will build the Docker image for the API, download the Redis image, and start both containers. The API will be available at `http://localhost:8000`.

3.  **Stopping the application:**
    To stop the application, press `Ctrl+C` in the terminal where `docker-compose` is running, and then run:
    ```sh
    docker-compose down
    ```
    This will stop and remove the containers. The volumes for Redis data and game saves will be preserved.

## Core Profile Object
Each time we hit the endpoint an object of the following form is loaded into the Flask server from a pickly files named `profiles.pickle`. It is a general representation of user state, holding a list of save files for the 6 games emulated, a secondary reference to the email which is used as a key to find this object, and a record of the last game that the user was playing.  This object is returned by most endpoints (along with secondary payloads depending on the endpoint's function), and is used to ensure consistency between the client and the server.*

```python
profileObjectExample = {
    "hike": ["hike save files"],
    "spell": ["spell save files"],
    "wish": ["wish save files"],
    "zork1": ["zork1 files"],
    "zork2": ["zork2 files"],
    "zork3": ["zork3 files"],
    "email": "User Email",
    "lastGame": [None or "last_game_played"]
} 
```

# Core API Endpoints

## /user

### General Description:
 
This endpoint is called when a user first pings the server.   If a user profile object (as defined above) exists for that email or account name, it will be returned.

### Example Call:

`/user?email=user_email`

### Return Object:

```python
returnObject = { 
    'newUser': bool, #representing whether the user was already in the system 
    'profile': Object, #the core profile object described in the above section
}
```
 
### Arguments:

**email**: the email of the given user, will either be pulled directly from device that the user uses to access the API, or will be provided by the user after a short dialogue.  Used to organize persistent save files for a user, and allows them to user the system statelesslessly

## /start

### General Description:
 
This endpoint is called when a user tries to load a game other than the 'New Game' placeholder.  This will allow the user to write to from that save file forward  in later `/action` calls.

### Example Call:

`/start?email=user_email&title=game_title&save=safeFile`

### Return Object:

```python
returnObject = { 
    'titleInfo': String, # Represents the first few lines of the game, up until the licensing information, etc 
    'firstLine': String, # Represents the first actual line of gameplay Information.  THe text between the end of the title info, and the first `>` input prompt
    'profile': Object,   # The core profile object described in the above section
}
```

### Arguments:

**email**: the email of the given user, will either be pulled directly from device that the user uses to access the API, or will be provided by the user after a short dialogue.  Used to organize persistent save files for a user, and allows them to user the system statelesslessly
 
**title**: The title of the game that the user is playing.  Needed so that dfrotz can be used to spin up an instance of the right game for the user to play

**save**: The name of the specific saveFile that the user is trying to load.  After each turn in-game, the state is saved, the model object is updated, the game is closed, and the response is sent back to the user.  Normally, that most-recent save is stored at a  location called `AutoSave`, but through an explicit save dialog (see below), they can also set fixed save points within the story.  With the `/save` command, it is possible to create explicitly defined savefiles to load with this function.

## /newGame

### General Description:
 
This endpoint is called when a user tries to load a game titled with the'New Game' placeholder.  The server will init that game, delete any potential AutoSaves for the game, and move the AutoSave head to the first state in the game (move 0).  This will allow the user to write to from that save file forward  in later `/action` calls.

### Example Call:

`/newGame?email=user_email&title=game_title`

### Return Object:

```python
returnObject = { 
    'titleInfo': String,    # Represents the first few lines of the game, up until the licensing information, etc 
    'firstLine': String,    # Represents the first actual line of gameplay Information.  THe text between the end of the title info, and the first `>` input prompt
    'profile': Object,      # The core profile object described in the above section
}
```
 
### Arguments:

**email**: the email of the given user, will either be pulled directly from device that the user uses to access the API, or will be provided by the user after a short dialogue.  Used to organize persistent save files for a user, and allows them to user the system statelesslessly
 
**title**: The title of the game that the user is playing.  Needed so that dfrotz can be used to spin up an instance of the right game for the user to play

## /action

### General Description:

This call sits are the heart of the core gameplay loop for the server.  This is called after `/start` or `/newGame` have initialized a game state and set the position for the AutoSave.  It will load the AutoSave into the system, execute the given action, update the AutoSave, and then save the game before returning.  

### Example Call:

`/newGame?email=user_email&title=game_title`

### Return Object:

```python
returnObject = {
        "cmdOutput":        String,     # The game's response to the input user command
        "lookOutput":       String,     # The line returned upon loading the save to the user's expected state; unused, but may be of future value
        "userProfile":      Object,     # The core profile object described in the above section
    }
```

### Arguments: 

**email**: the email of the given user, will either be pulled directly from device that the user uses to access the API, or will be provided by the user after a short dialogue.  Used to organize persistent save files for a user, and allows them to user the system statelesslessly
 
**title**: The title of the game that the user is playing.  Needed so that dfrotz can be used to spin up an instance of the right game for the user to play

## /save

### General Description:

This endpoint allows the bot to create an explicit, uniquely named safefile.  This is done through sending a series of commands to the game client, but it was important to wrap the call uniquely, as the save interface is somewhat distinct from the interace leveraged by the `/action` pathway 

### Example Call:
`/save?email=user_email&title=game_title&save=safeFile`

### Return Object:
```python
# note that Save just returns the base ProfileObject.  After the Save command is submitted, the game 
# loops back to its core action loop, and doesn't take any response-specific actions.  The object is 
# primarly returned so that I can ensure consistency between the client and the server.
profileObjectExample = {
    "hike": ["hike save files"],
    "spell": ["spell save files"],
    "wish": ["wish save files"],
    "zork1": ["zork1 files"],
    "zork2": ["zork2 files"],
    "zork3": ["zork3 files"],
    "email": "User Email",
    "lastGame": [None or "last_game_played"]
} 
```

### Arguments: 

**email**: the email of the given user, will either be pulled directly from device that the user uses to access the API, or will be provided by the user after a short dialogue.  Used to organize persistent save files for a user, and allows them to user the system statelesslessly
 
**title**: The title of the game that the user is playing.  Needed so that dfrotz can be used to spin up an instance of the right game for the user to play

**save**: The name of the specific saveFile that the user hopes to create.  After each turn in-game, the state is saved, the model object is updated, the game is closed, and the response is sent back to the user.  After each turn, the game is saved by a non-public function as an overwrite of the AutoSave file, `AutoSave`, but through this dialog, it is possible to set a 'restore point' of sorts for you to return to in the future.
