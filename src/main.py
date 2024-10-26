#!/usr/bin/env python3

# main.py

import curses
import time
from local_music import LocalMusicPlayer
from local_media import LocalMediaPlayer
from spotify_player import SpotifyPlayer
from radio_player import RadioPlayer

class MediaDashboardApp:
    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.monocle_mode = False
        self.active_window = 0
        self.windows = [
            LocalMusicPlayer(self.stdscr),
            LocalMediaPlayer(self.stdscr),  
            SpotifyPlayer(self.stdscr),
            RadioPlayer(self.stdscr)
        ]
        self.window_titles = ["Local Music", "Local Media", "Spotify", "Radio"]
        self.setup_curses()

    def setup_curses(self):
        curses.curs_set(0)  # Hide the cursor
        self.stdscr.nodelay(1)
        self.stdscr.timeout(100)
        curses.mousemask(curses.ALL_MOUSE_EVENTS | curses.REPORT_MOUSE_POSITION)

    def draw_tiling(self):
        self.stdscr.clear()
        height, width = self.stdscr.getmaxyx()
        mid_y = height // 2
        mid_x = width // 2

        # Define windows (quadrants), ensuring they fit within the screen dimensions
        for idx, module in enumerate(self.windows):
            if not module:
                continue
            # Calculate positions for quadrants
            if idx == 0:
                row, col = 0, 0
                win_height = mid_y
                win_width = mid_x
            elif idx == 1:
                row, col = 0, mid_x
                win_height = mid_y
                win_width = width - mid_x
            elif idx == 2:
                row, col = mid_y, 0
                win_height = height - mid_y
                win_width = mid_x
            elif idx == 3:
                row, col = mid_y, mid_x
                win_height = height - mid_y
                win_width = width - mid_x

            # Sub-window for each quadrant
            subwin = self.stdscr.subwin(win_height, win_width, row, col)
            subwin.box()
            subwin.addstr(1, 2, self.window_titles[idx] + ":")

            # Only render Spotify quadrant if it is the active window
            if isinstance(module, SpotifyPlayer) and self.active_window != 2:
                continue  # Skip rendering Spotify unless it’s active in monocle

            module.render(subwin)

        # Draw lines separating the windows
        self.stdscr.vline(0, mid_x, curses.ACS_VLINE, height)
        self.stdscr.hline(mid_y, 0, curses.ACS_HLINE, width)

        self.stdscr.refresh()

    def draw_monocle(self):
        self.stdscr.clear()
        width = self.stdscr.getmaxyx()[1]  # Only get the width, as height is not needed

        # Draw the active window in monocle mode
        module = self.windows[self.active_window]
        if not module:
            return

        title = self.window_titles[self.active_window]
        self.stdscr.addstr(0, (width // 2) - (len(title) // 2), f"{title}:", curses.A_BOLD)

        try:
            module.render(self.stdscr)
        except Exception as e:
            self.stdscr.addstr(1, 1, f"Error loading {title}: {str(e)}")
            logging.error(f"Error rendering module {title}: {str(e)}")
        self.stdscr.refresh()

    def handle_mouse(self, event):
        """Handle mouse clicks and interactions."""
        if self.monocle_mode: #and self.active_window is not None:
            module = self.windows[self.active_window]
            if module and hasattr(module, 'handle_mouse'):
                module.handle_mouse(event)
                return

        _, x, y, _, button = event

        # Basic idea - Determine the clicked quadrant based on coordinates
        height, width = self.stdscr.getmaxyx()
        mid_y = height // 2
        mid_x = width // 2

        if button == curses.BUTTON1_CLICKED:
            if y < mid_y and x < mid_x:
                self.active_window = 0  # Local Music
            elif y < mid_y and x >= mid_x:
                self.active_window = 1  # Local Media
            elif y >= mid_y and x < mid_x:
                self.active_window = 2  # Spotify
            elif y >= mid_y and x >= mid_x:
                self.active_window = 3  # Radio
            else:
                return
            
            module = self.windows[self.active_window]
            if module is not None:
                self.monocle_mode = True
                # Set current_view to "explorer" for the active windows
                module.current_view = "radio" if isinstance(module, RadioPlayer) else "explorer"
                # Reset any selection indices if needed
                module.selected_index = 0
                if isinstance(module, SpotifyPlayer):
                    module.current_playlist = None
                self.draw_monocle()
            else:
                # Display a message
                self.stdscr.addstr(0, 0, "This quadrant is not implemented yet.", curses.A_BOLD)
                self.stdscr.refresh()
                time.sleep(1)
                #pass

    def cleanup(self):
        """Clean up resources before exiting."""
        for module in self.windows:
            if module and hasattr(module, 'stop_media'):
                module.stop_media()
            if module and hasattr(module, 'stop_station'):
                module.stop_station()

    def handle_keypress(self, key):
        """Handle keypress actions globally and pass them to active modules."""
        module = self.windows[self.active_window]
        key_handled = False
        if self.monocle_mode and module:
            # If module handles the key, skip global handling
            key_handled = module.handle_keypress(key)

            # Check if the active window wants to exit monocle mode
            if hasattr(module, 'current_view') and module.current_view == "exit":
                self.monocle_mode = False
                self.draw_tiling()
                return True

        if not key_handled:
            if key == ord('q') or key == 27:  # Quit on 'q' or 'Esc'
                self.cleanup()
                return True
            elif key == ord('m'):  # Monocle mode
                self.monocle_mode = True
                self.draw_monocle()
                return True
            elif key == ord('t'):  # Tiling mode
                self.monocle_mode = False
                self.draw_tiling()
            elif self.monocle_mode and key == ord('j'):
                # Only change monocle window if module is in 'dashboard' view
                if module.current_view == 'dashboard' and self.active_window < len(self.windows) - 1:
                    self.active_window += 1
                    self.draw_monocle()
            elif self.monocle_mode and key == ord('k'):
                if module.current_view == 'dashboard' and self.active_window > 0:
                    self.active_window -= 1
                    self.draw_monocle()
            elif key == curses.KEY_MOUSE:
                self.handle_mouse(curses.getmouse())

        # Handle back to tiling mode directly if module is in 'dashboard' view
        if key in (curses.KEY_BACKSPACE, ord('\b'), 127) and self.monocle_mode:
            if module.current_view == 'dashboard':
                self.monocle_mode = False
                self.draw_tiling()

    def main_loop(self):
        while True:
            key = self.stdscr.getch()

            if self.handle_keypress(key):
                break

            if self.monocle_mode and self.active_window is not None:
                module = self.windows[self.active_window]
                if module and hasattr(module, 'check_playback_status'):
                    module.check_playback_status()

            if self.monocle_mode:
                self.draw_monocle()
            else:
                self.draw_tiling()

            time.sleep(0.1)  

def main(stdscr):
    app = MediaDashboardApp(stdscr)
    app.main_loop()

if __name__ == "__main__":
    curses.wrapper(main)
