# radio_player.py

import curses
import os
import subprocess
import time
import requests
import threading

CHANNELS_FILE = os.path.expanduser("~/.local/share/media-dashboard/channels.json")

class RadioPlayer:
    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.window = None
        self.current_view = "radio"  # views: radio, favorites, stations
        self.volume = self.get_volume()  # Get current system volume
        self.stations = []  # List of stations fetched from API
        self.favorites = self.load_favorites()
        self.selected_index = 0  # For navigating lists
        self.current_station = None  # Currently playing station
        self.player_process = None  # mpv subprocess
        self.update_thread = threading.Thread(target=self.update_volume)
        self.update_thread.daemon = True
        self.update_thread.start()

    def render(self, window):
        self.window = window
        if self.current_view == "radio":
            self.render_radio(window)
        elif self.current_view == "favorites":
            self.render_favorites(window)
        elif self.current_view == "stations":
            self.render_stations(window)

    def render_radio(self, window):
        window.clear()
        window.box()
        height, width = window.getmaxyx()
        # Title
        title = "RadioPlayer"
        window.addstr(1, (width - len(title)) // 2, title, curses.A_BOLD)

        # Display current station
        if self.current_station:
            station_str = f"Station: {self.current_station['name']}"
            window.addstr(3, 2, station_str[:width - 4])
        else:
            window.addstr(3, 2, "No station selected.")

        # Volume
        volume_str = f"Volume: {self.volume}%"
        window.addstr(4, 2, volume_str)

        # Instructions
        instructions = "[S] Search Stations  [F] Favorites  [+/-] Volume  [Backspace] Exit"
        window.addstr(height - 2, 2, instructions[:width - 4])

        window.refresh()

    def render_stations(self, window):
        window.clear()
        window.box()
        height, width = window.getmaxyx()
        title = "Available Stations"
        window.addstr(1, (width - len(title)) // 2, title, curses.A_BOLD)

        if not self.stations:
            window.addstr(3, 2, "No stations found. Press [S] to search.")
        else:
            start_y = 3
            visible_items = height - start_y - 3
            start_index = max(0, self.selected_index - visible_items // 2)
            end_index = min(len(self.stations), start_index + visible_items)

            for idx in range(start_index, end_index):
                station = self.stations[idx]
                display_text = station['name'][:width - 4]
                if idx == self.selected_index:
                    window.addstr(start_y + idx - start_index, 2, display_text, curses.A_REVERSE)
                else:
                    window.addstr(start_y + idx - start_index, 2, display_text)

        # Instructions
        instructions = "[Enter] Play  [F] Add to Favorites  [Backspace] Back"
        window.addstr(height - 2, 2, instructions[:width - 4])

        window.refresh()

    def render_favorites(self, window):
        window.clear()
        window.box()
        height, width = window.getmaxyx()
        title = "Favorite Stations"
        window.addstr(1, (width - len(title)) // 2, title, curses.A_BOLD)

        if not self.favorites:
            window.addstr(3, 2, "No favorite stations.")
        else:
            start_y = 3
            visible_items = height - start_y - 2
            start_index = max(0, self.selected_index - visible_items // 2)
            end_index = min(len(self.favorites), start_index + visible_items)

            for idx in range(start_index, end_index):
                station = self.favorites[idx]
                display_text = station['name'][:width - 4]
                if idx == self.selected_index:
                    window.addstr(start_y + idx - start_index, 2, display_text, curses.A_REVERSE)
                else:
                    window.addstr(start_y + idx - start_index, 2, display_text)

        # Instructions
        instructions = "[Enter] Play  [D] Delete  [Backspace] Back"
        window.addstr(height - 2, 2, instructions[:width - 4])

        window.refresh()

    def handle_keypress(self, key):
        if self.current_view == "radio":
            return self.handle_radio_keypress(key)
        elif self.current_view == "stations":
            return self.handle_stations_keypress(key)
        elif self.current_view == "favorites":
            return self.handle_favorites_keypress(key)
        return False

    def handle_radio_keypress(self, key):
        handled = False
        if key == ord('s') or key == ord('S'):
            self.search_stations()
            self.current_view = "stations"
            self.selected_index = 0
            self.render(self.window)
            handled = True
        elif key == ord('f') or key == ord('F'):
            self.current_view = "favorites"
            self.selected_index = 0
            self.render(self.window)
            handled = True
        elif key == ord('+'):
            self.change_volume(5)
            handled = True
        elif key == ord('-'):
            self.change_volume(-5)
            handled = True
        elif key in (curses.KEY_BACKSPACE, ord('\b'), 127):
            # Exit to dashboard
            self.stop_station()
            self.current_view = "dashboard"
            handled = True
        return handled

    def handle_stations_keypress(self, key):
        handled = False
        if key == ord('j') or key == curses.KEY_DOWN:
            if self.selected_index < len(self.stations) - 1:
                self.selected_index += 1
            self.render_stations(self.window)
            handled = True
        elif key == ord('k') or key == curses.KEY_UP:
            if self.selected_index > 0:
                self.selected_index -= 1
            self.render_stations(self.window)
            handled = True
        elif key == ord('\n'):
            # Play selected station
            station = self.stations[self.selected_index]
            self.current_station = station
            self.play_station(station['url_resolved'])
            self.current_view = "radio"
            self.render(self.window)
            handled = True
        elif key == ord('f') or key == ord('F'):
            # Add to favorites
            station = self.stations[self.selected_index]
            if station not in self.favorites:
                self.favorites.append(station)
                self.save_favorites()
                # Display confirmation message briefly
                height, width = self.window.getmaxyx()
                confirmation_message = f"Added {station['name']} to favorites."
                self.window.addstr(height - 2, 2, confirmation_message[:width - 4])
                self.window.refresh()
                curses.napms(1500)  # Pause for 1.5 seconds
                self.render_stations(self.window)  # Re-render stations to clear message
            handled = True
        elif key in (curses.KEY_BACKSPACE, ord('\b'), 127):
            self.current_view = "radio"
            self.render(self.window)
            handled = True
        return handled

    def handle_favorites_keypress(self, key):
        handled = False
        if key == ord('j') or key == curses.KEY_DOWN:
            if self.selected_index < len(self.favorites) - 1:
                self.selected_index += 1
            self.render_favorites(self.window)
            handled = True
        elif key == ord('k') or key == curses.KEY_UP:
            if self.selected_index > 0:
                self.selected_index -= 1
            self.render_favorites(self.window)
            handled = True
        elif key == ord('\n'):
            # Play selected favorite station
            station = self.favorites[self.selected_index]
            self.current_station = station
            self.play_station(station['url_resolved'])
            self.current_view = "radio"
            self.render(self.window)
            handled = True
        elif key == ord('d') or key == ord('D'):
            # Delete favorite
            del self.favorites[self.selected_index]
            self.save_favorites()
            if self.selected_index >= len(self.favorites) and self.selected_index > 0:
                self.selected_index -= 1
            self.render_favorites(self.window)
            handled = True
        elif key in (curses.KEY_BACKSPACE, ord('\b'), 127):
            self.current_view = "radio"
            self.render(self.window)
            handled = True
        return handled

    def search_stations(self):
        # Fetch top 50 stations from Radio Browser API
        try:
            response = requests.get("http://de1.api.radio-browser.info/json/stations/topclick/50")
            if response.status_code == 200:
                self.stations = response.json()
            else:
                self.stations = []
        except Exception as e:
            print(f"Error fetching stations: {e}")
            self.stations = []

    def play_station(self, stream_url):
        self.stop_station()
        # Start mpv to play the stream
        self.player_process = subprocess.Popen(['mpv', '--no-video', stream_url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def stop_station(self):
        if self.player_process:
            self.player_process.terminate()
            self.player_process = None

    def change_volume(self, delta):
        self.volume = max(0, min(100, self.volume + delta))
        # Use amixer to change volume
        subprocess.call(["amixer", "set", "Master", f"{self.volume}%"])
        self.render(self.window)

    def get_volume(self):
        # Get current system volume using amixer
        try:
            output = subprocess.check_output(["amixer", "get", "Master"]).decode()
            # Parse the output to find the volume percentage
            import re
            matches = re.findall(r"\[(\d+)%\]", output)
            if matches:
                return int(matches[0])
        except Exception as e:
            print(f"Error getting volume: {e}")
        return 50  # Default value if unable to get volume

    def update_volume(self):
        while True:
            self.volume = self.get_volume()
            time.sleep(5)  # Update every 5 seconds

    def load_favorites(self):
        if not os.path.exists(os.path.dirname(CHANNELS_FILE)):
            os.makedirs(os.path.dirname(CHANNELS_FILE))
        if os.path.isfile(CHANNELS_FILE):
            import json
            with open(CHANNELS_FILE, "r") as f:
                return json.load(f)
        else:
            return []

    def save_favorites(self):
        with open(CHANNELS_FILE, "w") as f:
            import json
            json.dump(self.favorites, f)

    def handle_mouse(self, event):
        pass  # Implement mouse handling if desired
