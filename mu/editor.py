"""
Copyright (c) 2015-2016 Nicholas H.Tollervey and others (see the AUTHORS file).

Based upon work done for Puppy IDE by Dan Pope, Nicholas Tollervey and Damien
George.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
import os
import os.path
import sys
import json
from PyQt5.QtWidgets import QMessageBox
from mu.repl import find_microbit
from mu.contrib import uflash, appdirs


HOME_DIRECTORY = os.path.expanduser('~')
MICROPYTHON_DIRECTORY = os.path.join(HOME_DIRECTORY, 'micropython')
if not os.path.exists(MICROPYTHON_DIRECTORY):
    os.mkdir(MICROPYTHON_DIRECTORY)
DATA_DIR = appdirs.user_data_dir('mu', 'python')
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)
SESSION_FILE = os.path.join(DATA_DIR, 'tabs.json')


class REPL:
    """
    Read, Evaluate, Print, Loop.

    Represents the REPL. Since the logic for the REPL is simply a USB/serial
    based widget this class only contains a reference to the associated port.
    """

    def __init__(self, port):
        if os.name == 'posix':
            # If we're on Linux or OSX reference the port like this...
            self.port = "/dev/{}".format(port)
        elif os.name == 'nt':
            # On Windows do something related to an appropriate port name.
            self.port = port  # COMsomething-or-other.
        else:
            # No idea how to deal with other OS's so fail.
            raise NotImplementedError('OS not supported.')


class Editor:
    """
    Application logic for the editor itself.
    """

    def __init__(self, view):
        self._view = view
        self.repl = None
        self.theme = 'day'

    def restore_session(self):
        """
        Attempts to recreate the tab state from the last time the editor was
        run.
        """
        if os.path.exists(SESSION_FILE):
            with open(SESSION_FILE) as f:
                tabs = json.load(f)
                if tabs:
                    for tab in tabs:
                        try:
                            with open(tab) as f:
                                text = f.read()
                        except FileNotFoundError:
                            pass
                        else:
                            self._view.add_tab(tab, text)
        if not self._view.tab_count:
            py = 'from microbit import *\n\n# Write code here :-)'
            self._view.add_tab(None, py)

    def flash(self):
        """
        Takes the currently active tab, compiles the Python script therein into
        a hex file and flashes it all onto the connected device.
        """
        # Grab the Python script.
        tab = self._view.current_tab
        if tab is None:
            # There is no active text editor
            return
        python_script = tab.text().encode('utf-8')
        # Generate a hex file
        python_hex = uflash.hexlify(python_script)
        micropython_hex = uflash.embed_hex(uflash._RUNTIME, python_hex)
        path_to_microbit = uflash.find_microbit()
        if path_to_microbit:
            hex_file = os.path.join(path_to_microbit, 'micropython.hex')
            uflash.save_hex(micropython_hex, hex_file)
            message = 'Flashing "{}" onto the micro:bit.'.format(tab.label)
            information = ("When the yellow LED stops flashing the device"
                           " will restart and your script will run. If there"
                           " is an error, you'll see a helpful message scroll"
                           " across the device's display.")
            self._view.show_message(message, information, 'Information')
        else:
            message = 'Could not find an attached BBC micro:bit.'
            self._view.show_message(message)

    def add_repl(self):
        """
        Detect a connected BBC micro:bit and if found, connect to the
        MicroPython REPL and display it to the user.
        """
        if self.repl is not None:
            raise RuntimeError("REPL already running")
        mb_port = find_microbit()
        if mb_port:
            try:
                self.repl = REPL(port=mb_port)
                self._view.add_repl(self.repl)
            except IOError as ex:
                self.repl = None
                information = ("Click the device's reset button, wait a few"
                               " seconds and then try again.")
                self._view.show_message(str(ex), information)
        else:
            message = 'Could not find an attached BBC micro:bit.'
            information = ("Please make sure the device is plugged into this"
                           " computer.\n\nThe device must have MicroPython"
                           " flashed onto it before the REPL will work.\n\n"
                           "Finally, press the device's reset button and wait"
                           " a few seconds before trying again.")
            self._view.show_message(message, information)

    def remove_repl(self):
        """
        If there's an active REPL, disconnect and hide it.
        """
        if self.repl is None:
            raise RuntimeError("REPL not running")
        self._view.remove_repl()
        self.repl = None

    def toggle_repl(self):
        """
        If the REPL is active, close it; otherwise open the REPL.
        """
        if self.repl is None:
            self.add_repl()
        else:
            self.remove_repl()

    def toggle_theme(self):
        """
        Switches between themes (night or day).
        """
        if self.theme == 'day':
            self.theme = 'night'
        else:
            self.theme = 'day'
        self._view.set_theme(self.theme)

    def new(self):
        """
        Adds a new tab to the editor.
        """
        self._view.add_tab(None, '')

    def load(self):
        """
        Loads a Python file from the file system or extracts a Python sccript
        from a hex file.
        """
        path = self._view.get_load_path(MICROPYTHON_DIRECTORY)
        try:
            if path.endswith('.py'):
                # Open the file, read the textual content and set the name as
                # the path to the file.
                with open(path) as f:
                    text = f.read()
                name = path
            else:
                # Open the hex, extract the Python script therein and set the
                # name to None, thus forcing the user to work out what to name
                # the recovered script.
                with open(path) as f:
                    text = uflash.extract_script(f.read())
                name = None
        except FileNotFoundError:
            pass
        else:
            self._view.add_tab(name, text)

    def save(self):
        """
        Save the content of the currently active editor tab.
        """
        tab = self._view.current_tab
        if tab is None:
            # There is no active text editor so abort.
            return
        if tab.path is None:
            # Unsaved file.
            tab.path = self._view.get_save_path(MICROPYTHON_DIRECTORY)
        if tab.path:
            # The user specified a path to a file.

            if not os.path.basename(tab.path).endswith('.py'):
                # No extension given, default to .py
                tab.path += '.py'

            with open(tab.path, 'w') as f:
                f.write(tab.text())
            tab.modified = False
        else:
            # The user cancelled the filename selection.
            tab.path = None

    def zoom_in(self):
        """
        Make the editor's text bigger
        """
        self._view.zoom_in()

    def zoom_out(self):
        """
        Make the editor's text smaller.
        """
        self._view.zoom_out()

    def quit(self, *args, **kwargs):
        """
        Exit the application.
        """
        if self._view.modified:
            # Alert the user to handle unsaved work.
            result = self._view.show_confirmation('You have un-saved work!')
            if result == QMessageBox.Cancel:
                if args and hasattr(args[0], 'ignore'):
                    # The function is handling an event, so ignore it.
                    args[0].ignore()
                return
        widgets = []
        for widget in self._view.widgets:
            if widget.path:
                widgets.append(widget.path)
        with open(SESSION_FILE, 'w') as out:
            json.dump(widgets, out, indent=2)
        sys.exit(0)
