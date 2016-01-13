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
import keyword
import os
import sys
from PyQt5.QtCore import QSize, Qt, pyqtSignal
from PyQt5.QtWidgets import (QToolBar, QAction, QStackedWidget, QDesktopWidget,
                             QWidget, QVBoxLayout, QShortcut, QSplitter,
                             QTabWidget, QFileDialog, QMessageBox)
from PyQt5.QtGui import QKeySequence, QColor, QFont
from PyQt5.Qsci import QsciScintilla, QsciLexerPython
from mu.resources import load_icon
from mu.repl import REPLPane


# FONT related constants:
DEFAULT_FONT_SIZE = 14
DEFAULT_FONT = 'Bitstream Vera Sans Mono'
# Platform specific alternatives...
if sys.platform == 'win32':
    DEFAULT_FONT = 'Consolas'
elif sys.platform == 'darwin':
    DEFAULT_FONT = 'Monaco'


DARK_STYLE = """QStackedWidget, QWidget
{
    background-color: black;
    color: white;
}

QToolButton {
    min-width: 72px;
}

QToolButton:hover {
    color: red;
}
"""


LIGHT_STYLE = """QStackedWidget, QWidget
{
    background-color: #EEE;
    color: black;
}

QToolButton {
    min-width: 72px;
}
"""


class Font:
    """
    Utility class that makes it easy to set font related values within the
    editor.
    """
    def __init__(self, color='black', paper='white', bold=False, italic=False):
        self.color = color
        self.paper = paper
        self.bold = bold
        self.italic = italic


class Theme:
    """
    Defines a font and other theme related information.
    """

    @classmethod
    def apply_to(cls, lexer):
        # Apply a font for all styles
        font = QFont(DEFAULT_FONT, DEFAULT_FONT_SIZE)
        font.setBold(False)
        font.setItalic(False)
        lexer.setFont(font)

        for name, font in cls.__dict__.items():
            if not isinstance(font, Font):
                continue
            style_num = getattr(lexer, name)
            lexer.setColor(QColor(font.color), style_num)
            lexer.setEolFill(True, style_num)
            lexer.setPaper(QColor(font.paper), style_num)
            if font.bold or font.italic:
                f = QFont(DEFAULT_FONT, DEFAULT_FONT_SIZE)
                f.setBold(font.bold)
                f.setItalic(font.italic)
                lexer.setFont(f, style_num)


class DayTheme(Theme):
    """
    Defines a Python related theme including the various font colours for
    syntax highlighting.
    """
    FunctionMethodName = ClassName = Font(color='#0000a0')
    UnclosedString = Font(paper='#FFDDDD')
    Comment = CommentBlock = Font(color='gray')
    Keyword = Font(color='#008080', bold=True)
    SingleQuotedString = DoubleQuotedString = Font(color='#800000')
    TripleSingleQuotedString = TripleDoubleQuotedString = Font(color='#060')
    Number = Font(color='#00008B')
    Decorator = Font(color='#cc6600')
    Default = Identifier = Font()
    Operator = Font(color='#400040')
    HighlightedIdentifier = Font(color='#0000a0')
    Paper = QColor('white')
    Caret = QColor('black')
    Margin = QColor('#EEE')


class NightTheme(Theme):
    """
    Defines a Python related theme including the various font colours for
    syntax highlighting.
    """
    FunctionMethodName = ClassName = Font(color='#AAA', paper='black')
    UnclosedString = Font(paper='#666')
    Comment = CommentBlock = Font(color='#AAA', paper='black')
    Keyword = Font(color='#EEE', bold=True, paper='black')
    SingleQuotedString = DoubleQuotedString = Font(color='#AAA', paper='black')
    TripleSingleQuotedString = TripleDoubleQuotedString = Font(color='#AAA', paper='black')
    Number = Font(color='#AAA', paper='black')
    Decorator = Font(color='#cccccc', paper='black')
    Default = Identifier = Font(color='#fff', paper='black')
    Operator = Font(color='#CCC', paper='black')
    HighlightedIdentifier = Font(color='#ffffff', paper='black')
    Paper = QColor('black')
    Caret = QColor('white')
    Margin = QColor('#111')


class PythonLexer(QsciLexerPython):
    """
    A Python specific "lexer" that's used to identify keywords of the Python
    language so the editor can do syntax highlighting.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setHighlightSubidentifiers(False)

    def keywords(self, flag):
        """
        Returns a list of Python keywords.
        """
        if flag == 1:
            kws = keyword.kwlist + ['self', 'cls']
        elif flag == 2:
            kws = __builtins__.keys()
        else:
            return None
        return ' '.join(kws)


class EditorPane(QsciScintilla):
    """
    Represents the text editor.
    """

    def __init__(self, path, text):
        super().__init__()
        self.path = path
        self.setText(text)
        self.setModified(False)
        self.configure()

    @property
    def modified(self):
        """
        Returns if the code in the editor has been modified since last save.
        """
        return self.isModified()

    @modified.setter
    def modified(self, value):
        """
        Sets the modified flag.
        """
        self.setModified(value)

    def configure(self):
        """
        Set up the editor component.
        """
        # Font information
        font = QFont(DEFAULT_FONT)
        font.setFixedPitch(True)
        font.setPointSize(DEFAULT_FONT_SIZE)
        self.setFont(font)
        # Generic editor settings
        self.setUtf8(True)
        self.setAutoIndent(True)
        self.setIndentationsUseTabs(False)
        self.setIndentationWidth(4)
        self.setTabWidth(4)
        self.setEdgeColumn(79)
        self.setMarginLineNumbers(0, True)
        self.setMarginWidth(0, 50)
        self.setBraceMatching(QsciScintilla.SloppyBraceMatch)
        self.SendScintilla(QsciScintilla.SCI_SETHSCROLLBAR, 0)
        self.set_theme()

    def set_theme(self, theme=DayTheme):
        """
        Connect the theme and lexer and return the lexer for the editor to
        apply to the text in the editor.
        """
        self.lexer = PythonLexer()
        theme.apply_to(self.lexer)
        self.lexer.setDefaultPaper(theme.Paper)
        self.setCaretForegroundColor(theme.Caret)
        self.setMarginsBackgroundColor(theme.Margin)
        self.setMarginsForegroundColor(theme.Caret)
        self.setLexer(self.lexer)

    @property
    def label(self):
        """
        The label associated with this editor widget (usually the filename of
        the script we're editing).
        """
        if self.path:
            label = os.path.basename(self.path)
        else:
            label = 'untitled'
        # Add an asterisk to indicate that the file remains unsaved.
        if self.isModified():
            return label + ' *'
        else:
            return label


class ButtonBar(QToolBar):
    """
    Represents the bar of buttons across the top of the editor and defines
    their behaviour.
    """

    def __init__(self, parent):
        super().__init__(parent)
        self.slots = {}

        self.setMovable(False)
        self.setIconSize(QSize(64, 64))
        self.setToolButtonStyle(3)
        self.setContextMenuPolicy(Qt.PreventContextMenu)
        self.setObjectName("StandardToolBar")

        self.addAction(name="new",
                       tool_text="Create a new MicroPython script.")
        self.addAction(name="load", tool_text="Load a MicroPython script.")
        self.addAction(name="save",
                       tool_text="Save the current MicroPython script.")
        self.addSeparator()
        self.addAction(name="flash",
                       tool_text="Flash your code onto the micro:bit.")
        self.addAction(name="repl",
                       tool_text="Use the REPL to live code the micro:bit.")
        self.addSeparator()
        self.addAction(name="zoom-in",
                       tool_text="Zoom in (to make the text bigger).")
        self.addAction(name="zoom-out",
                       tool_text="Zoom out (to make the text smaller).")
        self.addAction(name="theme",
                       tool_text="Change theme between day or night.")
        self.addSeparator()
        self.addAction(name="quit", tool_text="Quit the application.")

    def addAction(self, name, tool_text):
        action = QAction(load_icon(name), name.capitalize(), self,
                         statusTip=tool_text)
        super().addAction(action)
        self.slots[name] = action

    def connect(self, name, slot, *shortcuts):
        self.slots[name].pyqtConfigure(triggered=slot)
        for shortcut in shortcuts:
            QShortcut(QKeySequence(shortcut),
                      self.parentWidget()).activated.connect(slot)


class Window(QStackedWidget):
    """
    Defines the look and characteristics of the application's main window.
    """

    title = "Mu"
    icon = "icon"

    _zoom_in = pyqtSignal(int)
    _zoom_out = pyqtSignal(int)

    def zoom_in(self):
        self._zoom_in.emit(2)

    def zoom_out(self):
        self._zoom_out.emit(2)

    def connect_zoom(self, widget):
        self._zoom_in.connect(widget.zoomIn)
        self._zoom_out.connect(widget.zoomOut)

    @property
    def current_tab(self):
        return self.tabs.currentWidget()

    def get_load_path(self, folder):
        path, _ = QFileDialog.getOpenFileName(self.widget,
                                              'Open file', folder,
                                              '*.py *.hex')
        return path

    def get_save_path(self, folder):
        path, _ = QFileDialog.getSaveFileName(self.widget,
                                              'Save file', folder)
        return path

    def add_tab(self, path, text):
        new_tab = EditorPane(path, text)
        new_tab_index = self.tabs.addTab(new_tab, new_tab.label)

        @new_tab.modificationChanged.connect
        def on_modified():
            self.tabs.setTabText(new_tab_index, new_tab.label)

        self.tabs.setCurrentIndex(new_tab_index)
        self.connect_zoom(new_tab)
        self.set_theme(self.theme)
        new_tab.setFocus()

    @property
    def tab_count(self):
        return self.tabs.count()

    @property
    def widgets(self):
        return [self.tabs.widget(i) for i in range(self.tab_count)]

    @property
    def modified(self):
        for widget in self.widgets:
            if widget.modified:
                return True
        return False

    def add_repl(self, repl):
        """
        Adds the REPL pane to the application.
        """
        replpane = REPLPane(port=repl.port, theme=self.theme)
        self.repl = replpane
        self.splitter.addWidget(replpane)
        self.splitter.setSizes([66, 33])
        self.repl.setFocus()
        self.connect_zoom(self.repl)

    def remove_repl(self):
        """
        Removes the REPL pane from the application.
        """
        self.repl.setParent(None)
        self.repl.deleteLater()
        self.repl = None

    def set_theme(self, theme):
        """
        Sets the theme for the REPL and editor tabs.
        """
        self.setStyleSheet(LIGHT_STYLE)
        self.theme = theme
        new_theme = DayTheme
        new_icon = 'theme'
        if theme == 'night':
            new_theme = NightTheme
            new_icon = 'theme_day'
            self.setStyleSheet(DARK_STYLE)
        for widget in self.widgets:
            widget.set_theme(new_theme)
        self.button_bar.slots['theme'].setIcon(load_icon(new_icon))
        if hasattr(self, 'repl') and self.repl:
            self.repl.set_theme(theme)

    def show_message(self, message, information=None, icon=None):
        """
        Displays a modal message to the user.

        If information is passed in this will be set as the additional
        informative text in the modal dialog.

        Since this mechanism will be used mainly for warning users that
        something is awry the default icon is set to "Warning". It's possible
        to override the icon to one of the following settings: NoIcon,
        Question, Information, Warning or Critical.
        """
        message_box = QMessageBox()
        message_box.setText(message)
        message_box.setWindowTitle('Mu')
        if information:
            message_box.setInformativeText(information)
        if icon and hasattr(message_box, icon):
            message_box.setIcon(getattr(message_box, icon))
        else:
            message_box.setIcon(message_box.Warning)
        message_box.exec()

    def show_confirmation(self, message, information=None, icon=None):
        """
        Displays a modal message to the user to which they need to confirm or
        cancel.

        If information is passed in this will be set as the additional
        informative text in the modal dialog.

        Since this mechanism will be used mainly for warning users that
        something is awry the default icon is set to "Warning". It's possible
        to override the icon to one of the following settings: NoIcon,
        Question, Information, Warning or Critical.
        """
        message_box = QMessageBox()
        message_box.setText(message)
        message_box.setWindowTitle('Mu')
        if information:
            message_box.setInformativeText(information)
        if icon and hasattr(message_box, icon):
            message_box.setIcon(getattr(message_box, icon))
        else:
            message_box.setIcon(message_box.Warning)
        message_box.setStandardButtons(message_box.Cancel | message_box.Ok)
        message_box.setDefaultButton(message_box.Cancel)
        return message_box.exec()

    def update_title(self, filename=None):
        """
        Updates the title bar of the application. If a filename (representing
        the name of the file currently the focus of the editor) is supplied,
        append it to the end of the title.
        """
        title = self.title
        if filename:
            title += ' - ' + filename
        self.setWindowTitle(title)

    def autosize_window(self):
        """
        Makes the editor 80% of the width*height of the screen and centres it.
        """
        screen = QDesktopWidget().screenGeometry()
        w = int(screen.width() * 0.8)
        h = int(screen.height() * 0.8)
        self.resize(w, h)
        size = self.geometry()
        self.move((screen.width() - size.width()) / 2,
                  (screen.height() - size.height()) / 2)

    def setup(self, theme):
        """
        Sets up the window.

        Defines the various attributes of the window and defines how the user
        interface is laid out.
        """
        self.theme = theme
        # Give the window a default icon, title and minimum size.
        self.setWindowIcon(load_icon(self.icon))
        self.update_title()
        self.setMinimumSize(800, 600)

        self.widget = QWidget()
        self.splitter = QSplitter(Qt.Vertical)

        widget_layout = QVBoxLayout()
        self.widget.setLayout(widget_layout)

        self.button_bar = ButtonBar(self.widget)
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.tabs.removeTab)

        widget_layout.addWidget(self.button_bar)
        widget_layout.addWidget(self.splitter)

        self.splitter.addWidget(self.tabs)

        self.addWidget(self.widget)
        self.setCurrentWidget(self.widget)

        self.set_theme(theme)
        self.show()
        self.autosize_window()
