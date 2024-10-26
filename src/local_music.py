# local_music.py

import curses
import os
import subprocess
from pathlib import Path
import logging
import time
from mutagen import File as MutagenFile
import signal
from mutagen.id3 import ID3, APIC
from mutagen.mp4 import MP4Cover
from PIL import Image
import io

logging.basicConfig(
    filename="local_music_debug.log",
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

class LocalMusicPlayer:
    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.music_dir = Path.home() / "Music"
        self.selected_index = 0
        self.file_list = self.get_music_directories()  # Start with directories only
        self.player_process = None
        self.current_view = "dashboard"  # Options: dashboard, explorer, player
        self.button_regions = {}
        self.player_paused = False
        self.current_track_info = {}
        self.playback_start_time = None
        self.pause_time = None
        self.playlist = []
        self.current_track_index = None

    def get_music_directories(self):
        """Fetch a list of directories in the Music folder, excluding hidden ones."""
        if not self.music_dir.exists():
            return []

        directories = sorted([f for f in self.music_dir.iterdir() if f.is_dir() and not f.name.startswith('.')])
        return directories

    def get_directory_content(self):
        """Fetch a list of directories and music files in the current folder."""
        if not self.music_dir.exists():
            return []

        files = sorted([f for f in self.music_dir.iterdir() if (f.is_dir() or f.suffix in ['.mp3', '.flac', '.wav']) and not f.name.startswith('.')])
        return files

    def render(self, window):
        """Render different views based on the current state."""
        self.window = window  # Store the current window
        if self.current_view == "dashboard":
            self.render_dashboard(window)
        elif self.current_view == "explorer":
            self.render_file_explorer(window)
        elif self.current_view == "player":
            self.render_player(window)

    def render_dashboard(self, window):
        """Render the Music directories in the dashboard view."""
        window.clear()
        window.box()
        window.addstr(1, 2, "Music Directories:")

        # Show directories without selection
        start_y = 3
        for idx, item in enumerate(self.file_list):
            display_text = f"{item.name}"
            window.addstr(start_y + idx, 2, display_text)

        window.refresh()
        logging.debug(f"Rendered Dashboard with directories: {self.file_list}")
    
    def stop_media(self):
        """Stop the currently playing music."""
        if self.player_process and self.player_process.poll() is None:
            self.player_process.terminate()
            self.player_process.wait()
            self.player_process = None
        self.playback_start_time = None
        self.player_paused = False
        self.current_track_index = None
        self.current_track_info = {}


    def render_file_explorer(self, window):
        """Render the file explorer view, allowing navigation through the Music directory."""
        window.clear()
        window.box()
        window.addstr(1, 2, "File Explorer - Navigate using j/k, Enter to open/play, Backspace to go back")

        max_y, max_x = window.getmaxyx()
        start_y = 3
        visible_items = max_y - start_y - 2  # Account for window borders and title

        # Calculate the visible slice of file list based on selected_index
        start_index = max(0, self.selected_index - (visible_items // 2))
        end_index = min(len(self.file_list), start_index + visible_items)

        # Render only the visible portion of the file list
        for idx in range(start_index, end_index):
            item = self.file_list[idx]
            display_text = f"{item.name}"
            if idx == self.selected_index:
                window.addstr(start_y + (idx - start_index), 2, display_text, curses.A_REVERSE)
            else:
                window.addstr(start_y + (idx - start_index), 2, display_text)

        window.refresh()

    def render_player(self, window):
        """Render the music player interface in player mode."""
        window.clear()
        window.box()
        height, width = window.getmaxyx()

        # Get track info
        track_title = self.current_track_info.get('title', 'Unknown Track')
        album_name = self.current_track_info.get('album', 'Unknown Album')
        track_length = self.current_track_info.get('length', 0)
        album_art_image = self.current_track_info.get('album_art_image', None)
        elapsed_time = time.time() - self.playback_start_time if self.playback_start_time else 0
        if self.player_paused and self.pause_time:
            elapsed_time = self.pause_time - self.playback_start_time

        # Format times
        def format_time(seconds):
            mins = int(seconds) // 60
            secs = int(seconds) % 60
            return f"{mins}:{secs:02d}"

        elapsed_str = format_time(elapsed_time)
        total_str = format_time(track_length)

        # Progress Bar
        progress_bar_length = width - 4
        progress = elapsed_time / track_length if track_length else 0
        filled_length = int(progress_bar_length * progress)
        progress_bar = '[' + '#' * filled_length + ' ' * (progress_bar_length - filled_length) + ']'

        # Album Art Display
        album_art_width = min(40, width - 4)  # Adjust width as needed
        art_x = 2
        art_y = 2

        if album_art_image:
            ascii_art = self.get_ascii_art(album_art_image, album_art_width)
            for i, line in enumerate(ascii_art):
                if art_y + i < height - 10:
                    window.addstr(art_y + i, art_x, line)
        else:
            # Placeholder for no album art
            window.addstr(art_y + 5, art_x + album_art_width // 2 - 5, "No Album Art")

        # Now Playing Info
        info_x = art_x
        info_y = art_y + (len(ascii_art) if album_art_image else 10) + 1
        if info_y + 5 < height - 5:
            window.addstr(info_y, info_x, f"Now Playing: {track_title}")
            window.addstr(info_y + 1, info_x, f"Album: {album_name}")
            # Display progress bar and times
            window.addstr(info_y + 3, info_x, progress_bar)
            window.addstr(info_y + 4, info_x, f"{elapsed_str} / {total_str}")

        # Display controls
        controls_text = " [B] Back  [P] Play/Pause  [N] Next "
        controls_y = height - 3
        controls_x = (width // 2) - (len(controls_text) // 2)
        window.addstr(controls_y, controls_x, controls_text, curses.A_BOLD)

        # Store button positions for mouse interaction
        self.button_regions.clear()
        button_labels = ["[B]", "[P]", "[N]"]
        button_actions = ["back", "play_pause", "next"]
        for label, action in zip(button_labels, button_actions):
            idx = controls_text.find(label)
            btn_x = controls_x + idx
            btn_y = controls_y
            btn_width = len(label)
            self.button_regions[action] = (btn_y, btn_x, btn_width)

        window.refresh()

    def handle_keypress(self, key):
        """Handle keypress actions based on current view."""
        if self.current_view == "dashboard" and key == ord('\n'):
            # Switch to explorer when Enter is pressed
            self.current_view = "explorer"
            self.music_dir = Path.home() / "Music"
            self.file_list = self.get_directory_content()
            self.selected_index = 0
            return True
        elif self.current_view == "explorer":
            return self.handle_explorer_keypress(key)
        elif self.current_view == "player":
            return self.handle_player_keypress(key)
        return False

    def handle_explorer_keypress(self, key):
        """Handle keypress actions in the file explorer."""
        logging.debug(f"Key Pressed: {key}, Current View: {self.current_view}, Selected Index: {self.selected_index}, Current Directory: {self.music_dir}")
        handled = False
        if key == ord('j'):
            if self.selected_index < len(self.file_list) - 1:
                self.selected_index += 1
                logging.debug(f"Moved down to index: {self.selected_index}")
            else:
                logging.debug("Reached the end of the list, cannot move down.")
            self.render_file_explorer(self.window)
            handled = True

        elif key == ord('k'):
            if self.selected_index > 0:
                self.selected_index -= 1
                logging.debug(f"Moved up to index: {self.selected_index}")
            else:
                logging.debug("Reached the top of the list, cannot move up.")
            self.render_file_explorer(self.window)
            handled = True

        elif key == ord('\n'):  # Enter key to open directory or play file
            selected_item = self.file_list[self.selected_index]
            logging.debug(f"Selected Item: {selected_item}")
            if selected_item.is_dir():
                self.music_dir = selected_item
                self.file_list = self.get_directory_content()
                self.selected_index = 0
                logging.debug(f"Opened directory: {self.music_dir}")
            else:
                # build a fucking playlist
                self.playlist = [f for f in self.file_list if f.is_file() and f.suffix in ['.mp3', '.flac', '.wav']]
                # Find index of selected item in the fucking playlist
                self.current_track_index = self.playlist.index(selected_item)
                self.play_music_file(self.playlist[self.current_track_index])
                self.current_view = "player"
                logging.debug(f"Playing file: {selected_item}")
            self.render(self.window)
            handled = True

        #elif key == curses.KEY_BACKSPACE:
        #    logging.debug(f"Backspace pressed. Current Directory: {self.music_dir}")
        #    if self.music_dir == Path.home() / "Music":
        #        self.current_view = "dashboard"
        #        self.file_list = self.get_music_directories()
        #        logging.debug("Back to dashboard view (root Music directory).")
        #    else:
        #        self.music_dir = self.music_dir.parent
        #        self.file_list = self.get_directory_content()
        #        self.selected_index = 0
        #        if self.player_process:
        #            self.stop_music()
        #        logging.debug(f"Moved up to parent directory: {self.music_dir}")
        #    self.render_file_explorer(self.stdscr)
        elif key in (curses.KEY_BACKSPACE, ord('\b'), 127):
            logging.debug(f"Backspace pressed. Current Directory: {self.music_dir}")
            if self.music_dir == Path.home() / "Music":
                self.current_view = "dashboard"
                self.file_list = self.get_music_directories()
                logging.debug("Back to dashboard view (root Music directory).")
                self.render(self.window)  # Render dashboard view
            else:
                self.music_dir = self.music_dir.parent
                self.file_list = self.get_directory_content()
                self.selected_index = 0
                if self.player_process:
                    self.stop_music()
                logging.debug(f"Moved up to parent directory: {self.music_dir}")
                self.render_file_explorer(self.window)
            handled = True
        return handled

    def handle_mouse(self, event):
        """Handle mouse clicks in the player view."""
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
                    break

    def handle_player_keypress(self, key):
        """Handle keypress actions in the player view."""
        if key == ord('p'):  # Play/Pause
            self.toggle_playback()
            return True
        elif key == ord('n'):  # Next (Placeholder)
            self.next_track()
            return True
        elif key == ord('b'):  # Back (Placeholder)
            self.previous_track()
            return True
        elif key == curses.KEY_BACKSPACE:
            self.stop_music()
            self.current_view = "explorer"
            self.render(self.window)
            return True
        return False

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

    def play_music_file(self, file_path):
        """Play the selected music file using MPV."""
        if self.player_process and self.player_process.poll() is None:
            self.player_process.terminate()  # Stop any currently playing music

        # Use MPV to play the file
        self.player_process = subprocess.Popen(
            ["mpv", "--no-video", "--quiet", str(file_path)],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        # Extract metadata
        audio = MutagenFile(str(file_path))
        track_length = audio.info.length if audio.info else None
        tags = audio.tags

        album_art_image = None  # Initialize album art image

        if tags:
            # Get track title and album name
            track_title = tags.get('TIT2', tags.get('title', file_path.stem))
            album_name = tags.get('TALB', tags.get('album', file_path.parent.name))

            # Attempt to extract album art
            album_art_data = None

            if file_path.suffix.lower() in ['.mp3']:
                # For MP3 files with ID3 tags
                if 'APIC:' in tags:
                    # Get the first APIC frame
                    apic = tags.getall('APIC')[0]
                    album_art_data = apic.data
                elif any(isinstance(tag, APIC) for tag in tags.values()):
                    # Alternate way to get APIC frames
                    for tag in tags.values():
                        if isinstance(tag, APIC):
                            album_art_data = tag.data
                            break

            elif file_path.suffix.lower() in ['.m4a', '.mp4']:
                # For MP4/M4A files
                if 'covr' in tags:
                    album_art_data = tags['covr'][0]
            elif file_path.suffix.lower() in ['.flac']:
                # For FLAC files
                if 'METADATA_BLOCK_PICTURE' in tags:
                    pic = tags['METADATA_BLOCK_PICTURE'][0]
                    album_art_data = pic.data

            # Process album art data if available
            if album_art_data:
                try:
                    album_art_image = Image.open(io.BytesIO(album_art_data))
                except Exception as e:
                    logging.error(f"Error processing album art: {e}")
                    album_art_image = None
        else:
            track_title = file_path.stem
            album_name = file_path.parent.name
            album_art_image = None

        self.current_track_info = {
            'title': str(track_title),
            'album': str(album_name),
            'length': track_length,
            'album_art_image': album_art_image,
            'file_path': file_path
        }

        self.playback_start_time = time.time()
        self.player_paused = False

    def next_track(self):
        """Skip to the next track in the playlist."""
        if self.playlist and self.current_track_index is not None:
            self.current_track_index = (self.current_track_index + 1) % len(self.playlist)
            self.play_music_file(self.playlist[self.current_track_index])
            self.render(self.window)

    def previous_track(self):
        """Go back to the previous track in the playlist."""
        if self.playlist and self.current_track_index is not None:
            self.current_track_index = (self.current_track_index - 1) % len(self.playlist)
            self.play_music_file(self.playlist[self.current_track_index])
            self.render(self.window)

    def toggle_playback(self):
        """Toggle play/pause of the current track."""
        if self.player_process and self.player_process.poll() is None:
            if self.player_paused:
                self.player_process.send_signal(signal.SIGCONT)
                self.playback_start_time += time.time() - self.pause_time  # Adjust playback time
                self.player_paused = False
            else:
                self.player_process.send_signal(signal.SIGSTOP)
                self.pause_time = time.time()
                self.player_paused = True

    def stop_music(self):
        """Stop the currently playing music."""
        if self.player_process and self.player_process.poll() is None:
            self.player_process.terminate()
            self.player_process = None
