#
# Copyright (c) 2021, 2022 Astroncia
# Copyright (c) 2023-2025 liya <liyaastrova@proton.me>
#
# This file is part of yuki-iptv.
#
# yuki-iptv is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# yuki-iptv is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with yuki-iptv. If not, see <https://www.gnu.org/licenses/>.
#
# The Font Awesome pictograms are licensed under the CC BY 4.0 License.
# Font Awesome Free 5.15.4 by @fontawesome - https://fontawesome.com
# https://creativecommons.org/licenses/by/4.0/
#
import traceback
from PyQt6 import QtCore, QtGui, QtWidgets
from yuki_iptv.i18n import _
from yuki_iptv.m3u import M3UParser
from yuki_iptv.xspf import parse_xspf
from yuki_iptv.xdg import home_folder
from yuki_iptv.misc import YukiData, WINDOW_SIZE
from yuki_iptv.exception_handler import show_exception

# Idea from https://github.com/Axel-Erfurt/m3uEdit/blob/main/m3uEditor.py
# Code was written from scratch while using similar design
# Also see https://github.com/Axel-Erfurt/m3uEdit/issues/1


class PlaylistEditor(QtWidgets.QMainWindow):
    file_opened = False
    table_changed = False

    labels = [
        "title",
        "tvg-name",
        "tvg-id",
        "tvg-logo",
        "tvg-group",
        "tvg-url",
        "catchup",
        "catchup-source",
        "catchup-days",
        "useragent",
        "referer",
        "url",
    ]

    def clear_table(self):
        self.statusBar().clearMessage()
        self.table.clear()
        self.table.setColumnCount(0)
        self.table.setRowCount(0)
        self.table.setHorizontalHeaderLabels([])

    def fill_table(self, m3u_data):
        self.table.clear()
        self.table.setColumnCount(len(self.labels))
        self.table.setRowCount(len(m3u_data))
        self.table.setHorizontalHeaderLabels(self.labels)
        i = -1
        for channel in m3u_data:
            i += 1
            self.table.setItem(i, 0, QtWidgets.QTableWidgetItem(channel["orig_title"]))
            self.table.setItem(i, 1, QtWidgets.QTableWidgetItem(channel["tvg-name"]))
            self.table.setItem(i, 2, QtWidgets.QTableWidgetItem(channel["tvg-id"]))
            self.table.setItem(i, 3, QtWidgets.QTableWidgetItem(channel["tvg-logo"]))
            self.table.setItem(i, 4, QtWidgets.QTableWidgetItem(channel["tvg-group"]))
            self.table.setItem(i, 5, QtWidgets.QTableWidgetItem(channel["tvg-url"]))
            if "catchup" in channel:
                self.table.setItem(i, 6, QtWidgets.QTableWidgetItem(channel["catchup"]))
                self.table.setItem(
                    i, 7, QtWidgets.QTableWidgetItem(channel["catchup-source"])
                )
                self.table.setItem(
                    i, 8, QtWidgets.QTableWidgetItem(channel["catchup-days"])
                )
            else:
                self.table.setItem(i, 6, QtWidgets.QTableWidgetItem(""))
                self.table.setItem(i, 7, QtWidgets.QTableWidgetItem(""))
                self.table.setItem(i, 8, QtWidgets.QTableWidgetItem(""))
            if "useragent" in channel:
                self.table.setItem(
                    i, 9, QtWidgets.QTableWidgetItem(channel["useragent"])
                )
            else:
                self.table.setItem(i, 9, QtWidgets.QTableWidgetItem(""))
            if "referer" in channel:
                self.table.setItem(
                    i, 10, QtWidgets.QTableWidgetItem(channel["referer"])
                )
            else:
                self.table.setItem(i, 10, QtWidgets.QTableWidgetItem(""))
            self.table.setItem(i, 11, QtWidgets.QTableWidgetItem(channel["url"]))
        self.table.resizeColumnsToContents()

    def select_file(self):
        self.ask_changed(False)
        filename = QtWidgets.QFileDialog.getOpenFileName(
            self,
            _("Select playlist"),
            home_folder,
            "All Files (*);;M3U (*.m3u *.m3u8);;XSPF (*.xspf)",
        )[0]
        if filename:
            m3u_parser = M3UParser(YukiData.settings["udp_proxy"])
            try:
                with open(filename) as file_:
                    filedata = file_.read()
                is_xspf = '<?xml version="' in filedata and (
                    "http://xspf.org/" in filedata or "https://xspf.org/" in filedata
                )
                if is_xspf:
                    m3u_data = parse_xspf(filedata)[0]
                else:
                    m3u_data = m3u_parser.parse_m3u(filedata)[0]
            except Exception:
                m3u_data = False
                show_exception(traceback.format_exc())
            if m3u_data:
                self.file_opened = False
                self.fill_table(m3u_data)
                self.statusBar().showMessage(str(filename) + " " + _("loaded"), 0)
                self.file_opened = True
                self.table_changed = False
            else:
                self.clear_table()
                self.statusBar().showMessage(_("Playlist loading error!"), 0)
                self.file_opened = True
                self.table_changed = False

    def save_file(self):
        m3u_str = "#EXTM3U\n"
        for row in range(self.table.rowCount()):
            output = {}
            for column in range(self.table.columnCount()):
                item = self.table.item(row, column)
                if item:
                    output[self.table.horizontalHeaderItem(column).text()] = item.text()
            m3u_str += "#EXTINF:0"
            if output["tvg-name"]:
                m3u_str += f' tvg-name="{output["tvg-name"]}"'
            if output["tvg-id"]:
                m3u_str += f' tvg-id="{output["tvg-id"]}"'
            if output["tvg-logo"]:
                m3u_str += f' tvg-logo="{output["tvg-logo"]}"'
            if output["tvg-group"]:
                m3u_str += f' tvg-group="{output["tvg-group"]}"'
            if output["tvg-url"]:
                m3u_str += f' tvg-url="{output["tvg-url"]}"'
            if output["catchup"]:
                m3u_str += f' catchup="{output["catchup"]}"'
            if output["catchup-source"]:
                m3u_str += f' catchup-source="{output["catchup-source"]}"'
            if output["catchup-days"]:
                m3u_str += f' catchup-days="{output["catchup-days"]}"'
            m3u_str += f',{output["title"]}\n'
            if output["useragent"]:
                m3u_str += f'#EXTVLCOPT:http-user-agent={output["useragent"]}\n'
            if output["referer"]:
                m3u_str += f'#EXTVLCOPT:http-referrer={output["referer"]}\n'
            m3u_str += f'{output["url"]}\n'
        # Writing to file
        save_fname = QtWidgets.QFileDialog.getSaveFileName(
            self, _("Save File"), home_folder, _("Playlists (*.m3u *.m3u8)")
        )[0]
        if save_fname:
            try:
                with open(save_fname, "w") as save_file:
                    save_file.write(m3u_str)
                self.table_changed = False
                self.statusBar().showMessage(_("Playlist successfully saved!"), 0)
            except Exception:
                self.statusBar().showMessage(_("Error"), 0)
                show_exception(traceback.format_exc())
        output = {}
        m3u_str = ""

    def populate_menubar(self):
        # Menubar
        open_action = QtGui.QAction(_("&Open file"), self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.select_file)

        save_action = QtGui.QAction(_("&Save as"), self)
        save_action.setShortcut("Ctrl+Shift+S")
        save_action.triggered.connect(self.save_file)

        menubar = self.menuBar()
        file_menu = menubar.addMenu(_("&File"))
        file_menu.addAction(open_action)
        file_menu.addAction(save_action)

    def delete_row(self):
        current_row1 = self.table.currentRow()
        if current_row1 != -1:
            self.table.removeRow(current_row1)
            self.table_changed = True

    def add_row(self):
        if not self.table.rowCount():
            self.table.setColumnCount(len(self.labels))
            self.table.setHorizontalHeaderLabels(self.labels)
            self.file_opened = True
        self.table.insertRow(self.table.currentRow() + 1)
        self.table_changed = True

    def replace_all(self):
        for row in range(self.table.rowCount()):
            for column in range(self.table.columnCount()):
                item = self.table.item(row, column)
                if item:
                    item.setText(
                        item.text().replace(
                            self.search_edit.text(),
                            self.replace_edit.text(),
                        )
                    )
                    self.table_changed = True

    def filter_table(self):
        for row in range(self.table.rowCount()):
            item = self.table.item(row, self.filter_selector.currentIndex())
            if item:
                if (
                    self.group_filter_edit.text().lower().strip()
                    in item.text().lower().strip()
                ):
                    self.table.showRow(row)
                else:
                    self.table.hideRow(row)

    def move_row(self, direction):
        current_row = self.table.currentRow()
        # If row selected
        if current_row != -1:
            # Down
            if direction == 1:
                # If selected row is not last row
                check = current_row != self.table.rowCount() - 1
            # Up
            elif direction == -1:
                # If selected row is not first row
                check = current_row != 0
            if check:
                # Save current selected column
                current_column = self.table.currentColumn()
                # Save current row data
                current_row_data = []
                for i, _x in enumerate(self.labels):
                    item = self.table.item(current_row, i)
                    if item:
                        current_row_data.append(item.text())
                    else:
                        current_row_data.append("")
                # Delete current row
                self.table.removeRow(current_row)
                # Create new empty row
                self.table.insertRow(current_row + direction)
                # Restore row data
                for i, x in enumerate(current_row_data):
                    self.table.setItem(
                        current_row + direction, i, QtWidgets.QTableWidgetItem(x)
                    )
                # Set selection to new row
                self.table.setCurrentCell(current_row + direction, current_column)
                current_row_data = []
                # Mark table as changed
                self.table_changed = True

    def populate_toolbar(self):
        # Toolbar
        self.toolbar = QtWidgets.QToolBar()
        self.toolbar.setIconSize(QtCore.QSize(16, 16))

        # Search
        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText(_("find"))
        self.search_edit.setFixedWidth(230)

        # Replace
        self.replace_edit = QtWidgets.QLineEdit()
        self.replace_edit.setPlaceholderText(_("replace with"))
        self.replace_edit.setFixedWidth(230)

        # Replace all
        self.replace_all_btn = QtWidgets.QToolButton()
        self.replace_all_btn.setText(_("replace all"))
        self.replace_all_btn.clicked.connect(self.replace_all)

        # Delete current row
        self.delete_btn = QtWidgets.QToolButton()
        self.delete_btn.setIcon(QtGui.QIcon(str(YukiData.icons_folder / "trash.png")))
        self.delete_btn.setToolTip(_("delete row"))
        self.delete_btn.clicked.connect(self.delete_row)

        # Add new empty row
        self.add_btn = QtWidgets.QToolButton()
        self.add_btn.setIcon(QtGui.QIcon(str(YukiData.icons_folder / "plus.png")))
        self.add_btn.setToolTip(_("add row"))
        self.add_btn.clicked.connect(self.add_row)

        # Down
        self.down_btn = QtWidgets.QToolButton()
        self.down_btn.setIcon(
            QtGui.QIcon(str(YukiData.icons_folder / "arrow-down.png"))
        )
        self.down_btn.clicked.connect(lambda: self.move_row(1))

        # Up
        self.up_btn = QtWidgets.QToolButton()
        self.up_btn.setIcon(QtGui.QIcon(str(YukiData.icons_folder / "arrow-up.png")))
        self.up_btn.clicked.connect(lambda: self.move_row(-1))

        # Group filter
        self.group_filter_edit = QtWidgets.QLineEdit()
        self.group_filter_edit.setPlaceholderText(_("filter group (press Enter)"))
        self.group_filter_edit.setToolTip(
            _(
                "insert search term and press enter\n use "
                "Selector → to choose column to search"
            )
        )
        self.group_filter_edit.returnPressed.connect(self.filter_table)

        # Filter selector
        self.filter_selector = QtWidgets.QComboBox()
        for group in self.labels:
            self.filter_selector.addItem(group)

        # Add widgets to toolbar
        self.toolbar.addWidget(self.search_edit)
        self.toolbar.addSeparator()
        self.toolbar.addWidget(self.replace_edit)
        self.toolbar.addSeparator()
        self.toolbar.addWidget(self.replace_all_btn)
        self.toolbar.addSeparator()
        self.toolbar.addWidget(self.delete_btn)
        self.toolbar.addSeparator()
        self.toolbar.addWidget(self.add_btn)
        self.toolbar.addWidget(self.down_btn)
        self.toolbar.addWidget(self.up_btn)
        self.toolbar.addSeparator()
        self.toolbar.addWidget(self.group_filter_edit)
        self.toolbar.addWidget(self.filter_selector)

        self.addToolBar(self.toolbar)

    def on_cell_changed(self, row, column):
        if self.file_opened:
            self.table_changed = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setWindowTitle(_("Playlist editor"))
        self.setWindowIcon(YukiData.YukiGUI.main_icon)
        self.setGeometry(0, 0, WINDOW_SIZE[0], WINDOW_SIZE[1])
        self.populate_menubar()
        self.populate_toolbar()

        # Table
        self.table = QtWidgets.QTableWidget(self)
        self.table.cellChanged.connect(self.on_cell_changed)
        self.setCentralWidget(self.table)
        self.statusBar().showMessage(_("Ready"), 0)

    def ask_changed(self, callback=None):
        if self.table_changed:
            reply = QtWidgets.QMessageBox.question(
                self,
                _("Save Confirmation"),
                "<b>{}</b>".format(
                    _("The document was changed.<br>Do you want to save the changes?")
                ),
                QtWidgets.QMessageBox.StandardButton.Yes
                | QtWidgets.QMessageBox.StandardButton.No,
                QtWidgets.QMessageBox.StandardButton.Yes,
            )
            if reply == QtWidgets.QMessageBox.StandardButton.Yes:
                if callback:
                    callback()
                self.save_file()

    def closeEvent(self, event):
        self.ask_changed(event.accept)

    def show(self):
        self.clear_table()
        self.file_opened = False
        self.table_changed = False
        self.statusBar().showMessage(_("Ready"), 0)
        super().show()
