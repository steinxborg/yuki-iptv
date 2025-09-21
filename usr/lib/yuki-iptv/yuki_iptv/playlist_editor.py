#
# Copyright (c) 2021, 2022 Astroncia
# Copyright (c) 2023-2025 liya <liyaliya@tutamail.com>
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
from pathlib import Path
from PyQt6 import QtCore, QtGui, QtWidgets
from yuki_iptv.i18n import _
from yuki_iptv.misc import YukiData
from yuki_iptv.playlist_m3u import M3UParser
from yuki_iptv.playlist_xspf import parse_xspf


class PlaylistEditor(QtWidgets.QMainWindow):
    def clear_table(self):
        self.statusBar().clearMessage()
        self.table.clear()
        self.table.setColumnCount(0)
        self.table.setRowCount(0)
        self.table.setHorizontalHeaderLabels([])

    def fill_table(self, m3u_data1):
        self.table.clear()
        self.table.setColumnCount(len(self.labels))
        self.table.setRowCount(len(m3u_data1))
        self.table.setHorizontalHeaderLabels(self.labels)
        i = -1
        for channel in m3u_data1:
            i += 1
            self.table.setItem(i, 0, QtWidgets.QTableWidgetItem(channel["title"]))
            self.table.setItem(i, 1, QtWidgets.QTableWidgetItem(channel["tvg-name"]))
            self.table.setItem(i, 2, QtWidgets.QTableWidgetItem(channel["tvg-ID"]))
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
                self.table.setItem(
                    i, 10, QtWidgets.QTableWidgetItem(channel["referer"])
                )
            else:
                self.table.setItem(i, 9, QtWidgets.QTableWidgetItem(""))
                self.table.setItem(i, 10, QtWidgets.QTableWidgetItem(""))
            self.table.setItem(i, 11, QtWidgets.QTableWidgetItem(channel["url"]))
        self.table.resizeColumnsToContents()

    def select_file(self):
        self.ask_changed(False)
        filename = QtWidgets.QFileDialog.getOpenFileName(
            self,
            _("Select playlist"),
            str(Path.home()),
            "All Files (*);;M3U (*.m3u *.m3u8);;XSPF (*.xspf)",
        )[0]
        if filename:
            m3u_parser = M3UParser(YukiData.settings["udp_proxy"])
            try:
                file0 = open(filename)
                filedata = file0.read()
                file0.close()
                is_xspf = '<?xml version="' in filedata and (
                    "http://xspf.org/" in filedata or "https://xspf.org/" in filedata
                )
                if not is_xspf:
                    m3u_data = m3u_parser.parse_m3u(filedata)[0]
                else:
                    m3u_data = parse_xspf(filedata)[0]
            except Exception:
                m3u_data = False
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

        save_fname = QtWidgets.QFileDialog.getSaveFileName(
            self, _("Save File"), str(Path.home()), _("Playlists (*.m3u *.m3u8)")
        )[0]
        if save_fname:
            try:
                save_file = open(save_fname, "w")
                save_file.write(m3u_str)
                save_file.close()
                self.table_changed = False
                self.statusBar().showMessage(_("Playlist successfully saved!"), 0)
            except Exception:
                self.statusBar().showMessage(_("Error"), 0)

        output = {}
        m3u_str = ""

    def populate_menubar(self):
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
        for row1 in range(self.table.rowCount()):
            item1 = self.table.item(row1, self.filter_selector.currentIndex())
            if item1:
                if (
                    self.groupfilter_edit.text().lower().strip()
                    in item1.text().lower().strip()
                ):
                    self.table.showRow(row1)
                else:
                    self.table.hideRow(row1)

    def move_row(self, direction):
        current_row2 = self.table.currentRow()
        # If row selected
        if current_row2 != -1:
            # Down
            if direction == 1:
                # If selected row is not last row
                check = current_row2 != self.table.rowCount() - 1
            # Up
            elif direction == -1:
                # If selected row is not first row
                check = current_row2 != 0
            if check:
                # Save current selected column
                current_column = self.table.currentColumn()
                # Save current row data
                current_row_data = []
                for i_0, _x_0 in enumerate(self.labels):
                    item2 = self.table.item(current_row2, i_0)
                    if item2:
                        current_row_data.append(item2.text())
                    else:
                        current_row_data.append("")
                # Delete current row
                self.table.removeRow(current_row2)
                # Create new empty row
                self.table.insertRow(current_row2 + direction)
                # Restore row data
                for i_1, x_1 in enumerate(current_row_data):
                    self.table.setItem(
                        current_row2 + direction, i_1, QtWidgets.QTableWidgetItem(x_1)
                    )
                # Set selection to new row
                self.table.setCurrentCell(current_row2 + direction, current_column)
                # Cleaning memory
                current_row_data = []
                # Mark table as changed
                self.table_changed = True

    def populate_toolbar(self):
        toolbar = QtWidgets.QToolBar()
        toolbar.setIconSize(QtCore.QSize(16, 16))

        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText(_("find"))
        self.search_edit.setFixedWidth(230)

        self.replace_edit = QtWidgets.QLineEdit()
        self.replace_edit.setPlaceholderText(_("replace with"))
        self.replace_edit.setFixedWidth(230)

        replaceall_btn = QtWidgets.QToolButton()
        replaceall_btn.setText(_("replace all"))
        replaceall_btn.clicked.connect(self.replace_all)

        delete_btn = QtWidgets.QToolButton()
        delete_btn.setIcon(
            QtGui.QIcon(str(Path(YukiData.YukiGUI.icons_folder, "trash.png")))
        )
        delete_btn.setToolTip(_("delete row"))
        delete_btn.clicked.connect(self.delete_row)

        add_btn = QtWidgets.QToolButton()
        add_btn.setIcon(
            QtGui.QIcon(str(Path(YukiData.YukiGUI.icons_folder, "plus.png")))
        )
        add_btn.setToolTip(_("add row"))
        add_btn.clicked.connect(self.add_row)

        down_btn = QtWidgets.QToolButton()
        down_btn.setIcon(
            QtGui.QIcon(str(Path(YukiData.YukiGUI.icons_folder, "arrow-down.png")))
        )
        down_btn.clicked.connect(lambda: self.move_row(1))

        up_btn = QtWidgets.QToolButton()
        up_btn.setIcon(
            QtGui.QIcon(str(Path(YukiData.YukiGUI.icons_folder, "arrow-up.png")))
        )
        up_btn.clicked.connect(lambda: self.move_row(-1))

        self.groupfilter_edit = QtWidgets.QLineEdit()
        self.groupfilter_edit.setPlaceholderText(_("filter group (press Enter)"))
        self.groupfilter_edit.setToolTip(
            _(
                "insert search term and press enter\n use "
                "Selector → to choose column to search"
            )
        )
        self.groupfilter_edit.returnPressed.connect(self.filter_table)

        self.filter_selector = QtWidgets.QComboBox()
        for group in self.labels:
            self.filter_selector.addItem(group)

        toolbar.addWidget(self.search_edit)
        toolbar.addSeparator()
        toolbar.addWidget(self.replace_edit)
        toolbar.addSeparator()
        toolbar.addWidget(replaceall_btn)
        toolbar.addSeparator()
        toolbar.addWidget(delete_btn)
        toolbar.addSeparator()
        toolbar.addWidget(add_btn)
        toolbar.addWidget(down_btn)
        toolbar.addWidget(up_btn)
        toolbar.addSeparator()
        toolbar.addWidget(self.groupfilter_edit)
        toolbar.addWidget(self.filter_selector)

        self.addToolBar(toolbar)

    def on_cell_changed(self, row, column):
        if self.file_opened:
            self.table_changed = True

    def __init__(self):
        super().__init__()
        self.file_opened = False
        self.table_changed = False

        self.labels = [
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

        self.setWindowTitle(_("Playlist editor"))
        self.setWindowIcon(YukiData.YukiGUI.main_icon)
        self.setGeometry(0, 0, 1200, 600)
        self.populate_menubar()
        self.populate_toolbar()

        self.table = QtWidgets.QTableWidget(self)
        self.table.cellChanged.connect(self.on_cell_changed)
        self.setCentralWidget(self.table)
        self.statusBar().showMessage(_("Ready"), 0)

    def ask_changed(self, callback=False):
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
