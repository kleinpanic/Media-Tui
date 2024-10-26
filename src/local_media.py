# local_media.py

import curses
import os
import subprocess
from pathlib import Path
import logging
import time
import socket
import json
import threading
from pymediainfo import MediaInfo

logging.basicConfig(
    filename="local_media_debug.log",
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

class LocalMediaPlayer:
    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.media_dir = Path.home() / "Videos"
        self.selected_index = 0
        self.file_list = self.get_media_directories()
        self.player_process = None
        self.current_view = "dashboard"
        self.window = None
        self.current_media_info = {}
        self.playback_start_time = None
        self.pause_time = None
        self.playlist = []
        self.current_media_index = None
        self.ipc_socket = None
        self.mpv_event_thread = None
        self.monitoring_mpv = False

    def get_media_directories(self):
        """Fetch a list of directories in the Videos folder, excluding hidden ones."""
        if not self.media_dir.exists():
            return []

        directories = sorted([f for f in self.media_dir.iterdir() if f.is_dir() and not f.name.startswith('.')])
        return directories

    def get_directory_content(self):
        """Fetch a list of directories and media files in the current folder."""
        if not self.media_dir.exists():
            return []

        files = sorted([f for f in self.media_dir.iterdir() if (f.is_dir() or f.suffix.lower() in ['.mp4', '.mkv', '.avi', '.mov']) and not f.name.startswith('.')])
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
        """Render the Videos directories in the dashboard view."""
        window.clear()
        window.box()
        window.addstr(1, 2, "Video Directories:")

        # Show directories without selection
        start_y = 3
        for idx, item in enumerate(self.file_list):
            display_text = f"{item.name}"
            window.addstr(start_y + idx, 2, display_text)

        window.refresh()
        logging.debug(f"Rendered Dashboard with directories: {self.file_list}")

    def render_file_explorer(self, window):
        """Render the file explorer view, allowing navigation through the Videos directory."""
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
        """Render the media player interface in player mode."""
        window.clear()
        window.box()
        height, width = window.getmaxyx()

        # Display video information and metadata
        title = self.current_media_info.get('title', 'Unknown Video')
        file_path = self.current_media_info.get('file_path', '')
        general_track = self.current_media_info.get('general_track', {})
        video_track = self.current_media_info.get('video_track', {})
        audio_track = self.current_media_info.get('audio_track', {})

        window.addstr(2, 2, f"Now Playing: {title}")
        window.addstr(3, 2, f"File: {file_path}")

        y = 5  # Starting y position for metadata

        # General metadata
        duration = general_track.get('duration')
        file_size = general_track.get('file_size')
        if duration:
            duration_sec = float(duration) / 1000
            window.addstr(y, 2, f"Duration: {duration_sec:.2f} sec")
            y += 1
        if file_size:
            window.addstr(y, 2, f"File Size: {int(file_size) / (1024 * 1024):.2f} MB")
            y += 1

        # Video metadata
        width_v = video_track.get('width')
        height_v = video_track.get('height')
        frame_rate = video_track.get('frame_rate')
        codec = video_track.get('format')
        if codec:
            window.addstr(y, 2, f"Video Codec: {codec}")
            y += 1
        if width_v and height_v:
            window.addstr(y, 2, f"Resolution: {width_v}x{height_v}")
            y += 1
        if frame_rate:
            window.addstr(y, 2, f"Frame Rate: {frame_rate} fps")
            y += 1

        # Audio metadata
        audio_codec = audio_track.get('format')
        channels = audio_track.get('channel_s')
        sample_rate = audio_track.get('sampling_rate')
        if audio_codec:
            window.addstr(y, 2, f"Audio Codec: {audio_codec}")
            y += 1
        if channels:
            window.addstr(y, 2, f"Channels: {channels}")
            y += 1
        if sample_rate:
            window.addstr(y, 2, f"Sample Rate: {sample_rate} Hz")
            y += 1

        window.addstr(height - 3, 2, "Press Backspace to return to File Explorer")
        window.refresh()

    def handle_keypress(self, key):
        """Handle keypress actions based on current view."""
        if self.current_view == "dashboard" and key == ord('\n'):
            # Switch to explorer when Enter is pressed
            self.current_view = "explorer"
            self.media_dir = Path.home() / "Videos"
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
        handled = False
        if key == ord('j'):
            if self.selected_index < len(self.file_list) - 1:
                self.selected_index += 1
            self.render_file_explorer(self.window)
            handled = True
        elif key == ord('k'):
            if self.selected_index > 0:
                self.selected_index -= 1
            self.render_file_explorer(self.window)
            handled = True
        elif key == ord('\n'):  # Enter key to open directory or play file
            selected_item = self.file_list[self.selected_index]
            logging.debug(f"Selected Item: {selected_item}")
            if selected_item.is_dir():
                self.media_dir = selected_item
                self.file_list = self.get_directory_content()
                self.selected_index = 0
                logging.debug(f"Opened directory: {self.media_dir}")
                self.render(self.window)
            else:
                # Build playlist
                self.playlist = [f for f in self.file_list if f.is_file() and f.suffix.lower() in ['.mp4', '.mkv', '.avi', '.mov']]
                # Find index of selected item in playlist
                self.current_media_index = self.playlist.index(selected_item)
                self.play_media_file(self.playlist[self.current_media_index])
                self.current_view = "player"
                logging.debug(f"Playing file: {selected_item}")
                self.render(self.window)
            handled = True
        elif key in (curses.KEY_BACKSPACE, ord('\b'), 127):
            if self.media_dir == Path.home() / "Videos":
                self.current_view = "dashboard"
                self.file_list = self.get_media_directories()
            else:
                self.media_dir = self.media_dir.parent
                self.file_list = self.get_directory_content()
                self.selected_index = 0
            self.render(self.window)
            handled = True
        return handled

    def handle_player_keypress(self, key):
        """Handle keypress actions in the player view."""
        if key in (curses.KEY_BACKSPACE, ord('\b'), 127):
            self.current_view = "explorer"
            self.render(self.window)
            return True
        return False

    def play_media_file(self, file_path):
        """Play the selected media file using MPV."""
        if self.player_process and self.player_process.poll() is None:
            self.player_process.terminate()  # Stop any currently playing media

        # Generate a unique IPC socket path
        self.ipc_socket = f"/tmp/mpv_socket_{os.getpid()}"

        # Use MPV to play the file with IPC enabled and full-screen mode
        self.player_process = subprocess.Popen(
            ["mpv", "--fs", "--quiet", f"--input-ipc-server={self.ipc_socket}", str(file_path)],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        # **Ensure media_title is defined here**
        media_title = file_path.stem  # Extract the file name without extension

        # Extract media info using pymediainfo
        try:
            media_info = MediaInfo.parse(str(file_path))
            general_track = media_info.general_tracks[0] if media_info.general_tracks else None
            video_track = next((t for t in media_info.video_tracks), None)
            audio_track = next((t for t in media_info.audio_tracks), None)
        except Exception as e:
            logging.error(f"Error extracting media info: {e}")
            general_track = video_track = audio_track = None

        # Store metadata
        self.current_media_info = {
            'title': str(media_title),
            'file_path': str(file_path),
            'general_track': general_track.to_data() if general_track else {},
            'video_track': video_track.to_data() if video_track else {},
            'audio_track': audio_track.to_data() if audio_track else {},
        }

        self.playback_start_time = time.time()
        self.player_paused = False

        # Start monitoring MPV events
        self.monitoring_mpv = True
        self.mpv_event_thread = threading.Thread(target=self.monitor_mpv_events)
        self.mpv_event_thread.start()

    def monitor_mpv_events(self):
        """Monitor MPV events to detect playback completion or user quit."""
        if not self.ipc_socket:
            return

        # Wait for the IPC socket to be available and ready
        timeout = 10  # Increase timeout to 10 seconds
        start_time = time.time()
        while time.time() - start_time < timeout:
            if os.path.exists(self.ipc_socket):
                try:
                    test_client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    test_client.connect(self.ipc_socket)
                    test_client.close()
                    break  # Connection successful
                except ConnectionRefusedError:
                    time.sleep(0.1)
            else:
                time.sleep(0.1)
        else:
            logging.error("MPV IPC socket not available or connection refused.")
            return

        try:
            client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            client.connect(self.ipc_socket)
            client.settimeout(1.0)

            # Send a request to observe property changes
            #command = {'command': ['observe_property', 1, 'eof-reached']}
            #client.sendall((json.dumps(command) + '\n').encode('utf-8'))

            buffer = ''
            while self.monitoring_mpv:
                try:
                    data = client.recv(4096).decode('utf-8')
                    if data:
                        buffer += data
                        while '\n' in buffer:
                            line, buffer = buffer.split('\n', 1)
                            if line.strip() == '':
                                continue
                            try:
                                message = json.loads(line.strip())
                            except json.JSONDecodeError as e:
                                logging.error(f"JSON decode error: {e}")
                                continue
                            event = message.get('event')
                            if event == 'idle':
                                # Playback ended naturally
                                self.handle_playback_end()
                                return  # Exit the thread
                    else:
                        time.sleep(0.1)
                except socket.timeout:
                    continue
                except Exception as e:
                    logging.error(f"Error in MPV event monitoring: {e}")
                    break

            client.close()
        except Exception as e:
            logging.error(f"Error connecting to MPV IPC socket: {e}")

    def handle_playback_end(self):
        """Handle actions after playback ends naturally."""
        # Clean up current playback
        self.stop_media(clean_ipc=False)  # We will reuse the IPC socket

        if self.playlist and self.current_media_index is not None:
            if self.current_media_index + 1 < len(self.playlist):
                self.current_media_index += 1
                self.play_media_file(self.playlist[self.current_media_index])
            else:
                # No more media in playlist, return to player view
                self.current_view = "player"
                self.render(self.window)
        else: 
            self.current_view = "player"
            self.render(self.window)

    def check_playback_status(self):
        """Check if the media has finished playing or was stopped by the user."""
        if self.player_process and self.player_process.poll() is not None:
            # Player exited
            self.monitoring_mpv = False
            if self.mpv_event_thread and self.mpv_event_thread.is_alive():
                self.mpv_event_thread.join()
            return_code = self.player_process.returncode
            self.player_process = None
            self.playback_start_time = None
            self.player_paused = False

            if return_code == 0:
                # Assume natural end (since we handle natural end via events)
                #self.current_view = "player"
                #self.render(self.window)
                pass
            else:
                # User quit MPV
                self.current_view = "player"
                self.render(self.window)

    def stop_media(self, clean_ipc=True):
        """Stop the currently playing media."""
        if self.player_process and self.player_process.poll() is None:
            self.player_process.terminate()
            self.player_process.wait()
            self.player_process = None
        if clean_ipc and self.ipc_socket and os.path.exists(self.ipc_socket):
            os.remove(self.ipc_socket)
        self.playback_start_time = None
        self.player_paused = False
        self.current_media_info = {}
        self.monitoring_mpv = False
        if self.mpv_event_thread and self.mpv_event_thread.is_alive():
            self.mpv_event_thread.join()

    def cleanup(self):
        """Clean up resources before exiting."""
        self.stop_media()
