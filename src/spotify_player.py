import curses
import os
import time
import logging
from spotipy.oauth2 import SpotifyOAuth
import spotipy
from dotenv import load_dotenv
import threading
import requests
import io
from PIL import Image

logging.basicConfig(
    filename="spotify_player_debug.log",
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

class SpotifyPlayer:
    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.sp = self.authenticate()
        self.current_view = "explorer"  # views: explorer, tracks, player, devices
        self.explorer_mode = "playlists"  # modes: playlists, albums
        self.window = None
        self.playlists = []
        self.albums = []
        self.items = []  # will hold either playlists or albums depending on mode
        self.tracks = []
        self.selected_index = 0
        self.current_playlist = None
        self.current_album = None
        self.current_track = None
        self.current_track_info = {}
        self.playback_start_time = None
        self.player_paused = False
        self.button_regions = {}
        self.volume = 50  # Default volume at 50%
        self.devices = []
        self.current_device = None
        self.update_playback_thread = threading.Thread(target=self.update_playback_info)
        self.update_playback_thread.daemon = True
        self.update_playback_thread.start()

    def authenticate(self):
        """Authenticate with Spotify using OAuth."""
        load_dotenv()  # Load credentials from .env file
        client_id = os.getenv('SPOTIPY_CLIENT_ID')
        client_secret = os.getenv('SPOTIPY_CLIENT_SECRET')
        redirect_uri = os.getenv('SPOTIPY_REDIRECT_URI')

        if not client_id or not client_secret or not redirect_uri:
            raise Exception("Spotify client credentials are not set properly.")

        scope = "user-library-read playlist-read-private user-read-playback-state user-modify-playback-state"
        try:
            sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
                client_id=client_id,
                client_secret=client_secret,
                redirect_uri=redirect_uri,
                scope=scope
            ))
            return sp
        except Exception as e:
            logging.error(f"Error during Spotify OAuth: {e}")
            return None

    def get_user_playlists(self):
        """Fetch the user's playlists (only those created by the user)."""
        playlists = []
        user_id = self.sp.current_user()['id']
        results = self.sp.current_user_playlists()
        while results:
            for item in results['items']:
                if item['owner']['id'] == user_id:
                    playlists.append(item)
            if results['next']:
                results = self.sp.next(results)
            else:
                results = None
        self.playlists = playlists

    def get_user_albums(self):
        """Fetch the user's saved albums (liked albums)."""
        albums = []
        results = self.sp.current_user_saved_albums()
        while results:
            albums.extend([item['album'] for item in results['items']])
            if results['next']:
                results = self.sp.next(results)
            else:
                results = None
        self.albums = albums

    def get_playlist_tracks(self, playlist_id):
        """Fetch tracks from a playlist."""
        tracks = []
        results = self.sp.playlist_tracks(playlist_id)
        while results:
            tracks.extend(results['items'])
            if results['next']:
                results = self.sp.next(results)
            else:
                results = None
        self.tracks = tracks

    def get_album_tracks(self, album_id):
        """Fetch tracks from an album."""
        tracks = []
        results = self.sp.album_tracks(album_id)
        while results:
            tracks.extend(results['items'])
            if results['next']:
                results = self.sp.next(results)
            else:
                results = None
        self.tracks = tracks

    def render(self, window):
        """Render different views based on the current state."""
        self.window = window
        if self.current_view == "explorer":
            self.render_explorer(window)
        elif self.current_view == "tracks":
            self.render_tracks(window)
        elif self.current_view == "player":
            self.render_player(window)
        elif self.current_view == "devices":
            self.render_devices(window)

    def render_explorer(self, window):
        """Render the explorer view showing playlists or albums based on mode."""
        window.clear()
        window.box()
        if self.explorer_mode == 'playlists':
            header = "Your Playlists (Press 'A' for Albums):"
            if not self.playlists:
                self.get_user_playlists()
            self.items = self.playlists
        elif self.explorer_mode == 'albums':
            header = "Your Liked Albums (Press 'P' for Playlists):"
            if not self.albums:
                self.get_user_albums()
            self.items = self.albums
        window.addstr(1, 2, header)
        max_y, max_x = window.getmaxyx()
        start_y = 3
        visible_items = max_y - start_y - 2  # Account for window borders and title
        start_index = max(0, self.selected_index - (visible_items // 2))
        end_index = min(len(self.items), start_index + visible_items)
        for idx in range(start_index, end_index):
            item = self.items[idx]
            if self.explorer_mode == 'playlists':
                display_text = f"{item['name']}"
            elif self.explorer_mode == 'albums':
                display_text = f"{item['name']} - {item['artists'][0]['name']}"
            truncated_text = display_text[:max_x - 4]
            if idx == self.selected_index:
                window.addstr(start_y + (idx - start_index), 2, truncated_text, curses.A_REVERSE)
            else:
                window.addstr(start_y + (idx - start_index), 2, truncated_text)
        if self.current_track:
            prompt = "Press [C] to view the currently playing song"
            window.addstr(max_y - 2, 2, prompt[:max_x - 4])  # Truncate if necessary
        window.refresh()

    def render_tracks(self, window):
        """Render the tracks view showing tracks in a playlist or album."""
        window.clear()
        window.box()
        if self.explorer_mode == 'playlists':
            header = f"Playlist: {self.current_playlist['name']}"
        elif self.explorer_mode == 'albums':
            header = f"Album: {self.current_album['name']}"
        window.addstr(1, 2, header)
        max_y, max_x = window.getmaxyx()
        start_y = 3
        visible_items = max_y - start_y - 2
        start_index = max(0, self.selected_index - (visible_items // 2))
        end_index = min(len(self.tracks), start_index + visible_items)
        for idx in range(start_index, end_index):
            if self.explorer_mode == 'playlists':
                track = self.tracks[idx]['track']
            elif self.explorer_mode == 'albums':
                track = self.tracks[idx]
            display_text = f"{track['name']} - {', '.join(artist['name'] for artist in track['artists'])}"
            truncated_text = display_text[:max_x - 4]
            if idx == self.selected_index:
                window.addstr(start_y + (idx - start_index), 2, truncated_text, curses.A_REVERSE)
            else:
                window.addstr(start_y + (idx - start_index), 2, truncated_text)
        if self.current_track:
            prompt = "Press [C] to view the currently playing song"
            window.addstr(max_y - 2, 2, prompt[:max_x - 4])  # Truncate if necessary
        window.refresh()

    def render_player(self, window):
        """Render the player view with track info and controls."""
        window.clear()
        window.box()
        height, width = window.getmaxyx()
        # Get track info
        track = self.current_track
        if not track:
            window.addstr(2, 2, "No track is currently playing.")
            window.refresh()
            return
        track_name = track['name']
        artist_names = ', '.join(artist['name'] for artist in track['artists'])
        album_name = track['album']['name']
        track_length = track['duration_ms'] / 1000  # Convert to seconds
        album_art_url = track['album']['images'][0]['url'] if track['album']['images'] else None

        # Check if volume control is allowed
        volume_control_allowed = True
        if self.current_device and not self.current_device.get('volume_percent'):
            volume_control_allowed = False

        # Download album art
        album_art_image = None
        if album_art_url:
            album_art_image = self.get_album_art_image(album_art_url)
        # Format times
        def format_time(seconds):
            mins = int(seconds) // 60
            secs = int(seconds) % 60
            return f"{mins}:{secs:02d}"
        # Get playback position
        playback_info = self.sp.current_playback()
        elapsed_time = playback_info['progress_ms'] / 1000 if playback_info and playback_info['progress_ms'] else 0
        elapsed_str = format_time(elapsed_time)
        total_str = format_time(track_length)
        # Progress Bar
        progress_bar_length = width - 4
        progress = elapsed_time / track_length if track_length else 0
        filled_length = int(progress_bar_length * progress)
        progress_bar = '[' + '#' * filled_length + ' ' * (progress_bar_length - filled_length) + ']'
        # Album Art Display
        album_art_width = min(40, width - 4)
        art_x = 2
        art_y = 2
        ascii_art = []
        if album_art_image:
            ascii_art = self.get_ascii_art(album_art_image, album_art_width)
            for i, line in enumerate(ascii_art):
                if art_y + i < height - 10:
                    window.addstr(art_y + i, art_x, line)
        else:
            window.addstr(art_y + 5, art_x + album_art_width // 2 - 5, "No Album Art")

        # Now Playing Info
        info_x = art_x
        info_y = art_y + (len(ascii_art) if album_art_image else 10) + 1
        if info_y + 7 < height - 5:
            window.addstr(info_y, info_x, f"Now Playing: {track_name}")
            window.addstr(info_y + 1, info_x, f"Artist(s): {artist_names}")
            window.addstr(info_y + 2, info_x, f"Album: {album_name}")
            if volume_control_allowed:
                window.addstr(info_y + 3, info_x, f"Volume: {self.volume}%")
            else:
                window.addstr(info_y + 3, info_x, "Volume: N/A (Cannot control device volume)")
            window.addstr(info_y + 5, info_x, progress_bar)
            window.addstr(info_y + 6, info_x, f"{elapsed_str} / {total_str}")
        # Controls
        controls = [
            {"label": "[B] Back", "action": "back"},
            {"label": "[P] Play/Pause", "action": "play_pause"},
            {"label": "[N] Next", "action": "next"},
        ]

        if volume_control_allowed:
            controls.extend([
                {"label": "[+] Vol Up", "action": "vol_up"},
                {"label": "[-] Vol Down", "action": "vol_down"},
            ])

        controls.append({"label": "[D] Devices", "action": "devices"})

        # Build controls_text and store button positions
        controls_text = ""
        self.button_regions.clear()
        controls_y = height -3
        controls_x = 2

        for idx, control in enumerate(controls):
            label = control["label"]
            action = control["action"]

            if controls_text:
                controls_text += "  "  # Add spaces between labels
                controls_x += 2  # Account for spaces

            window.addstr(controls_y, controls_x, label, curses.A_BOLD)
            self.button_regions[action] = (controls_y, controls_x, len(label))
            controls_text += label
            controls_x += len(label)

        window.refresh()

    def render_devices(self, window):
        """Render the device selection view."""
        window.clear()
        window.box()
        window.addstr(1, 2, "Available Devices:")
        self.get_available_devices()
        max_y, max_x = window.getmaxyx()
        start_y = 3
        visible_items = max_y - start_y - 2
        start_index = max(0, self.selected_index - (visible_items // 2))
        end_index = min(len(self.devices), start_index + visible_items)
        for idx in range(start_index, end_index):
            device = self.devices[idx]
            display_text = f"{device['name']} ({device['type']})"
            truncated_text = display_text[:max_x - 4]
            if idx == self.selected_index:
                window.addstr(start_y + (idx - start_index), 2, truncated_text, curses.A_REVERSE)
            else:
                window.addstr(start_y + (idx - start_index), 2, truncated_text)
        window.refresh()

    def get_available_devices(self):
        """Fetch the list of available devices."""
        devices_info = self.sp.devices()
        self.devices = devices_info['devices']
        logging.debug(f"Available devices: {self.devices}")

    def play_track(self, track_uri):
        """Play a track using Spotify."""
        try:
            devices = self.sp.devices()
            active_devices = devices['devices']
            logging.debug(f"Active devices: {active_devices}")

            if not active_devices:
                # No active devices, display a message
                self.window.clear()
                self.window.addstr(2, 2, "No active Spotify devices found.")
                self.window.addstr(3, 2, "Please open Spotify on a device to play music.")
                self.window.refresh()
                time.sleep(3)
                self.current_view = "tracks"
                self.render(self.window)
                return
            else:
                spotifyd_device = next((device for device in active_devices if device['name'].lower() == 'spotifyd'), None)
                if spotifyd_device:
                    self.current_device = spotifyd_device
                elif not self.current_device:
                    # Default to the first available device
                    self.current_device = active_devices[0]

                self.sp.start_playback(device_id=self.current_device['id'], uris=[track_uri])
                try:
                    self.sp.volume(self.volume, device_id=self.current_device['id'])
                except spotipy.exceptions.SpotifyException as e:
                    logging.error(f"Error setting volume: {e}")
                    # Handle VOLUME_CONTROL_DISALLOW gracefully
                    if 'VOLUME_CONTROL_DISALLOW' in str(e):
                        logging.info("Volume control is not allowed on this device.")
                    else:
                        # For other exceptions, re-raise the error
                        raise e

                self.current_track = self.sp.track(track_uri)
                self.current_view = "player"
                self.playback_start_time = time.time()
                self.player_paused = False
                self.render(self.window)


        except spotipy.exceptions.SpotifyException as e:
            logging.error(f"Error playing track: {e}")
            self.current_track = None
            self.window.clear()
            self.window.addstr(2, 2, "Error playing track.")
            self.window.addstr(3, 2, "Ensure you have an active Spotify device.")
            self.window.refresh()
            time.sleep(3)
            self.current_view = "tracks"
            self.render(self.window)

    def toggle_playback(self):
        """Toggle play/pause."""
        try:
            playback_info = self.sp.current_playback()
            if playback_info and playback_info['is_playing']:
                self.sp.pause_playback(device_id=self.current_device['id'])
                self.player_paused = True
            else:
                self.sp.start_playback(device_id=self.current_device['id'])
                self.player_paused = False
            self.render(self.window)
        except spotipy.exceptions.SpotifyException as e:
            logging.error(f"Error toggling playback: {e}")
            self.window.addstr(2, 2, "Error toggling playback.")
            self.window.refresh()
            time.sleep(1)

    def next_track(self):
        """Skip to the next track."""
        try:
            self.sp.next_track(device_id=self.current_device['id'])
            self.update_current_track_info()
        except spotipy.exceptions.SpotifyException as e:
            logging.error(f"Error skipping to next track: {e}")
            self.window.addstr(2, 2, "Error skipping to next track.")
            self.window.refresh()
            time.sleep(1)

    def previous_track(self):
        """Go back to the previous track."""
        try:
            self.sp.previous_track(device_id=self.current_device['id'])
            self.update_current_track_info()
        except spotipy.exceptions.SpotifyException as e:
            logging.error(f"Error going to previous track: {e}")
            self.window.addstr(2, 2, "Error going to previous track.")
            self.window.refresh()
            time.sleep(1)

    def increase_volume(self):
        """Increase the playback volume."""
        self.volume = min(100, self.volume + 10)
        try:
            if self.current_device:
                self.sp.volume(self.volume, device_id=self.current_device['id'])
            else:
                self.sp.volume(self.volume)
        except spotipy.exceptions.SpotifyException as e:
            logging.error(f"Error setting volume: {e}")
            # Handle VOLUME_CONTROL_DISALLOW gracefully
            if 'VOLUME_CONTROL_DISALLOW' in str(e):
                logging.info("Volume control is not allowed on this device.")
                # Inform the user
                self.window.addstr(2, 2, "Cannot control device volume.")
                self.window.refresh()
                time.sleep(1)
            else:
                # For other exceptions, re-raise the error
                raise e
        self.render(self.window)

    def decrease_volume(self):
        """Decrease the playback volume."""
        self.volume = max(0, self.volume - 10)
        try:
            if self.current_device:
                self.sp.volume(self.volume, device_id=self.current_device['id'])
            else:
                self.sp.volume(self.volume)
        except spotipy.exceptions.SpotifyException as e:
            logging.error(f"Error setting volume: {e}")
            # Handle VOLUME_CONTROL_DISALLOW gracefully
            if 'VOLUME_CONTROL_DISALLOW' in str(e):
                logging.info("Volume control is not allowed on this device.")
                # Inform the user
                self.window.addstr(2, 2, "Cannot control device volume.")
                self.window.refresh()
                time.sleep(1)
            else:
                # For other exceptions, re-raise the error
                raise e
        self.render(self.window)

    def update_current_track_info(self):
        """Update the current track information."""
        try:
            playback_info = self.sp.current_playback()
            if playback_info and playback_info['item']:
                self.current_track = playback_info['item']
                if 'device' in playback_info and playback_info['device']:
                    self.current_device = playback_info['device']
            else:
                self.current_track = None
                self.current_device = None
        except spotipy.exceptions.SpotifyException as e:
            logging.error(f"Error updating current track info: {e}")
            self.current_track = None
            self.current_device = None
        self.render(self.window)

    def handle_keypress(self, key):
        """Handle keypress actions based on current view."""
        if self.current_view == "explorer":
            return self.handle_explorer_keypress(key)
        elif self.current_view == "tracks":
            return self.handle_tracks_keypress(key)
        elif self.current_view == "player":
            return self.handle_player_keypress(key)
        elif self.current_view == "devices":
            return self.handle_devices_keypress(key)
        return False

    def handle_explorer_keypress(self, key):
        handled = False
        if key == ord('j'):
            if self.selected_index < len(self.items) - 1:
                self.selected_index += 1
            self.render_explorer(self.window)
            handled = True
        elif key == ord('k'):
            if self.selected_index > 0:
                self.selected_index -= 1
            self.render_explorer(self.window)
            handled = True
        elif key == ord('a') or key == ord('A'):
            # Switch to albums mode
            self.explorer_mode = 'albums'
            self.selected_index = 0
            self.render_explorer(self.window)
            handled = True
        elif key == ord('p') or key == ord('P'):
            # Switch to playlists mode
            self.explorer_mode = 'playlists'
            self.selected_index = 0
            self.render_explorer(self.window)
            handled = True
        elif key == ord('\n'):
            if self.explorer_mode == 'playlists':
                self.current_playlist = self.items[self.selected_index]
                self.get_playlist_tracks(self.current_playlist['id'])
                self.selected_index = 0
                self.current_view = "tracks"
                self.render(self.window)
            elif self.explorer_mode == 'albums':
                self.current_album = self.items[self.selected_index]
                self.get_album_tracks(self.current_album['id'])
                self.selected_index = 0
                self.current_view = "tracks"
                self.render(self.window)
            handled = True
        elif key == ord('c') or key == ord('C'):
            if self.current_track:
                self.current_view = "player"
                self.render(self.window)
            else:
                # Optionally display a message
                self.window.addstr(2, 2, "No song is currently playing.")
                self.window.refresh()
                time.sleep(1)
                self.render_explorer(self.window)
            handled = True
        elif key in (curses.KEY_BACKSPACE, ord('\b'), 127):
            # Back to quadrants
            # Signal to main application to exit monocle mode
            self.current_view = "dashboard"
            handled = True
        return handled

    def handle_tracks_keypress(self, key):
        handled = False
        if key == ord('j'):
            if self.selected_index < len(self.tracks) - 1:
                self.selected_index += 1
            self.render_tracks(self.window)
            handled = True
        elif key == ord('k'):
            if self.selected_index > 0:
                self.selected_index -= 1
            self.render_tracks(self.window)
            handled = True
        elif key == ord('\n'):
            if self.explorer_mode == 'playlists':
                track = self.tracks[self.selected_index]['track']
            elif self.explorer_mode == 'albums':
                track = self.tracks[self.selected_index]
            track_uri = track['uri']
            self.play_track(track_uri)
            handled = True
        elif key == ord('d') or key == ord('D'):
            self.current_view = "devices"
            self.selected_index = 0
            self.render(self.window)
            handled = True
        elif key == ord('c') or key == ord('C'):
            if self.current_track:
                self.current_view = "player"
                self.render(self.window)
            else:
                # Optionally display a message
                self.window.addstr(2, 2, "No song is currently playing.")
                self.window.refresh()
                time.sleep(1)
                self.render_tracks(self.window)
            handled = True
        elif key in (curses.KEY_BACKSPACE, ord('\b'), 127):
            # Back to explorer (playlists or albums)
            self.current_view = "explorer"
            self.selected_index = 0
            self.render_explorer(self.window)
            handled = True
        return handled

    def handle_player_keypress(self, key):
        handled = False
        if key in (ord('p'), ord('P')):
            self.toggle_playback()
            handled = True
        elif key in (ord('n'), ord('N')):
            self.next_track()
            handled = True
        elif key in (ord('b'), ord('B')):
            self.previous_track()
            handled = True
        elif key == ord('+'):
            self.increase_volume()
            handled = True
        elif key == ord('-'):
            self.decrease_volume()
            handled = True
        elif key in (ord('d'), ord('D')):
            self.current_view = "devices"
            self.selected_index = 0
            self.render(self.window)
            handled = True
        elif key in (curses.KEY_BACKSPACE, ord('\b'), 127):
            self.sp.pause_playback()
            self.current_view = "tracks"
            self.render(self.window)
            handled = True
        return handled

    def handle_devices_keypress(self, key):
        handled = False
        if key == ord('j'):
            if self.selected_index < len(self.devices) - 1:
                self.selected_index += 1
            self.render_devices(self.window)
            handled = True
        elif key == ord('k'):
            if self.selected_index > 0:
                self.selected_index -= 1
            self.render_devices(self.window)
            handled = True
        elif key == ord('\n'):
            device = self.devices[self.selected_index]
            self.sp.transfer_playback(device['id'], force_play=False)
            self.current_device = device
            # Return to player view
            self.current_view = "player"
            self.render(self.window)
            handled = True
        elif key in (curses.KEY_BACKSPACE, ord('\b'), 127):
            # Back to player view
            self.current_view = "player"
            self.render(self.window)
            handled = True
        return handled

    def handle_mouse(self, event):
        _, x, y, _, button = event
        if button == curses.BUTTON1_CLICKED:
            for action, (btn_y, btn_x, btn_width) in self.button_regions.items():
                if y == btn_y and btn_x <= x < btn_x + btn_width:
                    if action == "back":
                        self.previous_track()
                    elif action == "play_pause":
                        self.toggle_playback()
                    elif action == "next":
                        self.next_track()
                    elif action == "vol_up":
                        self.increase_volume()
                    elif action == "vol_down":
                        self.decrease_volume()
                    elif action == "devices":
                        self.current_view = "devices"
                        self.selected_index = 0
                        self.render(self.window)
                    break

    def update_playback_info(self):
        """Continuously update playback information."""
        while True:
            #if self.current_view == "player":
            self.update_current_track_info()
            time.sleep(1)

    def get_album_art_image(self, url):
        """Download and return the album art image."""
        try:
            response = requests.get(url)
            if response.status_code != 200:
                logging.error(f"Failed to download album art, status code: {response.status_code}")
                return None
            img_data = response.content
            image = Image.open(io.BytesIO(img_data))
            logging.debug("Album art image downloaded successfully")
            return image
        except Exception as e:
            logging.error(f"Error downloading album art: {e}")
            return None

    def get_ascii_art(self, img, width):
        """Convert an image to ASCII art."""
        # Resize image maintaining aspect ratio
        aspect_ratio = img.height / img.width
        new_height = int(aspect_ratio * width * 0.55)  # Adjust for terminal character dimensions
        img = img.resize((width, new_height))
        img = img.convert('L')  # Convert to grayscale
        pixels = img.getdata()
        chars = ["@", "#", "S", "%", "?", "*", "+", ";", ":", ",", "."]
        new_pixels = [chars[int(pixel / 255 * (len(chars) - 1))] for pixel in pixels]
        ascii_art = [''.join(new_pixels[i:i+width]) for i in range(0, len(new_pixels), width)]
        return ascii_art

    def cleanup(self):
        """Clean up resources before exiting."""
        self.sp.pause_playback()
