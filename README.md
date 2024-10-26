# Media-TUI

**Media-TUI** is a terminal-based media player built using Python. It integrates with services such as **Spotify** and provides a simple, curses-based user interface to browse, play, and control music. It also supports local file navigation and playback.

## Features

- **Spotify Integration**: Authenticate with Spotify to control your playlists, albums, and songs directly from the terminal.
- **Curses-based UI**: Browse playlists, tracks, albums, and control playback using a keyboard-driven terminal interface.
- **ASCII Art**: Displays album art in the form of ASCII art for currently playing tracks.
- **Device Management**: View and switch between available Spotify devices for playback.
- **Playback Controls**: Control volume, skip tracks, play/pause functionality, and more directly from the terminal.

## Requirements

- Python 3.7+
- Spotipy (Spotify API Python client)
- Pillow (Python Imaging Library for handling images)
- Curses (terminal UI library)
- Requests (for making HTTP requests)
- dotenv (for loading environment variables)

### Python Libraries

Install the dependencies using `pip`:

```bash
pip install spotipy pillow python-dotenv requests
```

## Installation

1. **Clone the Repository**:

   ```bash
   git clone https://github.com/your-username/media-tui.git
   cd media-tui
   ```

2. **Set up Spotify Credentials**:

   To authenticate with Spotify, you'll need to set up a Spotify developer application. Follow these steps:

   - Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard/applications) and create a new application.
   - Add a redirect URI like `http://localhost:8888/callback` to your application settings.

   Create a `.env` file in the project root and add your credentials:

   ```env
   SPOTIPY_CLIENT_ID=your-client-id
   SPOTIPY_CLIENT_SECRET=your-client-secret
   SPOTIPY_REDIRECT_URI=http://localhost:8888/callback
   ```

3. **Activate Virtual Environment (Optional but recommended)**:

   If you'd like to use a virtual environment:

   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

4. **Install Dependencies**:

   Inside your virtual environment (if you're using one), install the dependencies:

   ```bash
   pip install -r requirements.txt
   ```

5. **Run the Application**:

   ```bash
   python main.py
   ```

## How to Use

### Keybindings:

- **Explorer Mode**:
  - `j` / `k`: Navigate up and down in the playlists or albums.
  - `a`: Switch to albums view.
  - `p`: Switch to playlists view.
  - `Enter`: Select a playlist or album and view its tracks.
  - `c`: View the currently playing song.
  - `Backspace`: Exit the current view.

- **Tracks View**:
  - `j` / `k`: Navigate through tracks.
  - `Enter`: Play the selected track.
  - `c`: View the currently playing song.
  - `d`: Open device management view.
  - `Backspace`: Return to the explorer view.

- **Player View**:
  - `p`: Toggle Play/Pause.
  - `n`: Next track.
  - `b`: Previous track.
  - `+` / `-`: Increase or decrease volume.
  - `d`: Open device management view.
  - `Backspace`: Return to the tracks view.

- **Device Management**:
  - `j` / `k`: Navigate through available devices.
  - `Enter`: Switch playback to the selected device.
  - `Backspace`: Return to the player view.

### Features in Detail

- **Spotify Authentication**: Media-TUI authenticates with Spotify using OAuth and provides access to your personal Spotify playlists, albums, and playback devices.
- **ASCII Art**: Album art for the currently playing track is converted into ASCII art and displayed in the player view.
- **Device Management**: Easily switch between your available Spotify devices such as phones, computers, and smart speakers for playback.
  
## Troubleshooting

### Common Errors

1. **Spotify Authentication Error**:
   - Make sure you've correctly set the environment variables for Spotify credentials in the `.env` file.
   - Ensure the redirect URI in the `.env` matches the one in your Spotify Developer Dashboard.

2. **No Active Device Found**:
   - If no active device is found, make sure you have the Spotify app open on one of your devices and logged in with the same account.

3. **Album Art Not Displaying**:
   - If album art does not appear as ASCII, ensure you have a stable internet connection, and the required libraries (`requests`, `Pillow`) are installed.

## Contributing

If you'd like to contribute to this project:

1. Fork the repository.
2. Create a new branch for your feature/bugfix.
3. Submit a pull request.

## License

This project is licensed under the MIT License.

