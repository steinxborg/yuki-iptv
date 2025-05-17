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
import os
import sys
import time
import os.path
import logging
import datetime
import warnings
import traceback
import subprocess
from pathlib import Path
from PyQt6 import QtWidgets, QtCore, QtGui
from yuki_iptv.i18n import _, ngettext
from yuki_iptv.multi_epg import MultiEPGWindow
from yuki_iptv.playlist_editor import PlaylistEditor
from yuki_iptv.xdg import home_folder, SAVE_FOLDER_DEFAULT
from yuki_iptv.gui_playlists import create_playlists_window
from yuki_iptv.threads import idle_function, async_gui_blocking_function
from yuki_iptv.misc import (
    YukiData,
    BCOLOR,
    WINDOW_SIZE,
    QT_TIME_FORMAT,
    MPV_OPTIONS_LINK,
    get_current_time,
)

logger = logging.getLogger(__name__)


def yuki_app_exec(app):
    app_exit_code = app.exec()
    if YukiData.do_save_settings:
        start_args = sys.argv
        if "python" not in sys.executable:
            start_args.pop(0)
        # ResourceWarning: subprocess ? is still running
        warnings.simplefilter("ignore")
        subprocess.Popen([sys.executable] + start_args)
    sys.exit(app_exit_code)


def detect_qt_theme():
    # https://www.qt.io/blog/dark-mode-on-windows-11-with-qt-6.5#before-qt-65
    current_palette = QtGui.QPalette()
    YukiData.use_dark_icon_theme = (
        current_palette.color(QtGui.QPalette.ColorRole.WindowText).lightness()
        > current_palette.color(QtGui.QPalette.ColorRole.Window).lightness()
    )
    YukiData.icons_folder = (
        Path(os.path.dirname(os.path.abspath(__file__))).parent.parent.parent
        / "share"
        / "yuki-iptv"
        / ("icons_dark" if YukiData.use_dark_icon_theme else "icons")
    )


def moveWindowToCenter(window):
    screen = (
        YukiData.win.screen()
        if YukiData.win
        else QtWidgets.QApplication.primaryScreen()
    )
    if screen:
        qr = window.frameGeometry()
        qr.moveCenter(QtGui.QScreen.availableGeometry(screen).center())
        window.move(qr.topLeft())
    else:
        logger.warning("failed to determine main screen")


@async_gui_blocking_function
def open_recording_folder(*args, **kwargs):
    absolute_path = Path(YukiData.save_folder).absolute()
    xdg_open = subprocess.Popen(["xdg-open", str(absolute_path)])
    xdg_open.wait()


class PlaylistDockWidget(QtWidgets.QDockWidget):
    def enterEvent(self, event):
        YukiData.check_playlist_visible = True
        super().enterEvent(event)

    def leaveEvent(self, event):
        YukiData.check_playlist_visible = False
        super().leaveEvent(event)


class YukiGUIClass:
    m3u = ""
    epg = ""

    fullscreenPlaylistWidth = None
    fullscreenPlaylistHeight = None
    save_fullscreenPlaylistWidth = None
    save_fullscreenPlaylistHeight = None
    playlistFullscreenIsResized = False

    DEFAULT_OPACITY = 0.75
    FULLSCREEN_OPACITY = 0.55

    page_box = None
    of_lbl = None

    def __init__(self):
        self.main_icon = QtGui.QIcon(str(YukiData.icons_folder / "tv-blue.png"))

        self._tv_icon = QtGui.QIcon(str(YukiData.icons_folder / "tv.png"))
        self.tv_icon = self._tv_icon.pixmap(QtCore.QSize(32, 32))

        self.star_icon_pixmap = QtGui.QIcon(
            str(YukiData.icons_folder / "star.png")
        ).pixmap(QtCore.QSize(32, 32))

        self._search_icon = QtGui.QIcon(str(YukiData.icons_folder / "search.png"))
        self.search_icon_pixmap = self._search_icon.pixmap(QtCore.QSize(32, 32))
        self.search_icon_pixmap_small = self._search_icon.pixmap(QtCore.QSize(16, 16))

        self.plus_icon = QtGui.QIcon(str(YukiData.icons_folder / "plus.png"))
        self.minus_icon = QtGui.QIcon(str(YukiData.icons_folder / "minus.png"))

        self.tv_icon_small = QtGui.QIcon(self._tv_icon.pixmap(QtCore.QSize(16, 16)))
        self.loading_icon_small = QtGui.QIcon(
            QtGui.QIcon(str(YukiData.icons_folder / "loading.gif")).pixmap(16, 16)
        )
        self.movie_icon = QtGui.QIcon(str(YukiData.icons_folder / "movie.png")).pixmap(
            QtCore.QSize(32, 32)
        )

        class ScrollableLabel(QtWidgets.QScrollArea):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.setWidgetResizable(True)
                label_qwidget = QtWidgets.QWidget(self)
                bcolor_scrollabel = (
                    "white" if not YukiData.use_dark_icon_theme else "black"
                )
                label_qwidget.setStyleSheet("background-color: " + bcolor_scrollabel)
                self.setWidget(label_qwidget)
                label_layout = QtWidgets.QVBoxLayout(label_qwidget)
                self.label = QtWidgets.QLabel(label_qwidget)
                self.label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                self.label.setWordWrap(True)
                self.label.setStyleSheet("background-color: " + bcolor_scrollabel)
                label_layout.addWidget(self.label)

            def setText(self, text):
                self.label.setText(text)

        class SettingsScrollableWindow(QtWidgets.QMainWindow):
            def __init__(self):
                super().__init__()
                self.scroll = QtWidgets.QScrollArea()
                self.scroll.setVerticalScrollBarPolicy(
                    QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOn
                )
                self.scroll.setHorizontalScrollBarPolicy(
                    QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOn
                )
                self.scroll.setWidgetResizable(True)
                self.setCentralWidget(self.scroll)

        self.ScrollableLabel = ScrollableLabel
        self.SettingsScrollableWindow = SettingsScrollableWindow

        # Fonts
        self.font_bold = QtGui.QFont()
        self.font_bold.setBold(True)

        self.font_bold_medium = QtGui.QFont()
        self.font_bold_medium.setPointSize(11)
        self.font_bold_medium.setBold(True)

        self.font_italic = QtGui.QFont()
        self.font_italic.setItalic(True)

        self.font_italic_medium = QtGui.QFont()
        self.font_italic_medium.setPointSize(11)
        self.font_italic_medium.setItalic(True)

        self.font_11_bold = QtGui.QFont()
        self.font_11_bold.setPointSize(11)
        self.font_11_bold.setBold(True)

        self.font_12 = QtGui.QFont()
        self.font_12.setPointSize(12)

        self.font_12_bold = QtGui.QFont()
        self.font_12_bold.setPointSize(12)
        self.font_12_bold.setBold(True)

        class PlaylistWidget(QtWidgets.QWidget):
            def __init__(self):
                super().__init__()

                self.name_label = QtWidgets.QLabel()
                self.name_label.setFont(YukiData.YukiGUI.font_bold)
                self.description_label = QtWidgets.QLabel()

                self.icon = ""

                self.icon_label = QtWidgets.QLabel()
                self.icon_label.setFixedWidth(32)
                self.progress_label = QtWidgets.QLabel()
                self.progress_bar = QtWidgets.QProgressBar()
                self.progress_bar.setFormat("")
                self.progress_bar.setFixedHeight(15)
                self.end_label = QtWidgets.QLabel()

                self.layout = QtWidgets.QVBoxLayout()
                self.layout.addWidget(self.name_label)
                self.layout.addWidget(self.description_label)
                self.layout.setSpacing(5)

                self.layout1 = QtWidgets.QHBoxLayout()
                self.layout1.addWidget(self.progress_label)
                self.layout1.addWidget(self.progress_bar)
                self.layout1.addWidget(self.end_label)

                self.layout2 = QtWidgets.QGridLayout()
                self.layout2.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
                if not YukiData.settings["hidechannellogos"]:
                    self.layout2.addWidget(self.icon_label, 0, 0)
                self.layout2.addLayout(self.layout, 0, 1)
                self.layout2.setSpacing(10)

                self.layout3 = QtWidgets.QVBoxLayout()
                self.layout3.addLayout(self.layout2)
                self.layout3.addLayout(self.layout1)

                self.setLayout(self.layout3)

                self.progress_bar.setStyleSheet(
                    """
                  background-color: #C0C6CA;
                  border: 0px;
                  padding: 0px;
                  height: 5px;
                """
                )
                self.setStyleSheet(
                    """
                  QProgressBar::chunk {
                    background: #7D94B0;
                    width: 5px;
                  }
                """
                )

            def setDescription(self, text, tooltip):
                self.setToolTip(tooltip)
                self.description_label.setText(text)

            def setPixmap(self, pixmap):
                try:
                    self.icon_label.setPixmap(pixmap)
                    self.icon_label.setFixedWidth(32)
                except Exception:
                    pass

            def showDescription(self):
                self.description_label.show()
                self.progress_label.show()
                self.progress_bar.show()
                self.end_label.show()

            def hideDescription(self):
                self.description_label.hide()
                self.progress_label.hide()
                self.progress_bar.hide()
                self.end_label.hide()

            def destroy(self):
                for i in (
                    self.name_label,
                    self.description_label,
                    self.icon_label,
                    self.progress_label,
                    self.end_label,
                ):
                    i.setText("")
                    i.clear()
                self.layout3.deleteLater()
                self.layout2.deleteLater()
                self.layout1.deleteLater()
                self.layout.deleteLater()
                self.name_label.deleteLater()
                self.description_label.deleteLater()
                self.icon_label.deleteLater()
                self.progress_label.deleteLater()
                self.progress_bar.deleteLater()
                self.end_label.deleteLater()
                self.deleteLater()

        self.PlaylistWidget = PlaylistWidget

        self.btn_playpause = QtWidgets.QPushButton()
        self.btn_playpause.setIcon(
            QtGui.QIcon(str(YukiData.icons_folder / "pause.png"))
        )
        self.btn_playpause.setToolTip(_("Pause"))

        self.btn_stop = QtWidgets.QPushButton()
        self.btn_stop.setIcon(QtGui.QIcon(str(YukiData.icons_folder / "stop.png")))
        self.btn_stop.setToolTip(_("Stop"))

        self.btn_fullscreen = QtWidgets.QPushButton()
        self.btn_fullscreen.setIcon(
            QtGui.QIcon(str(YukiData.icons_folder / "fullscreen.png"))
        )
        self.btn_fullscreen.setToolTip(_("Fullscreen"))

        self.btn_open_recordings_folder = QtWidgets.QPushButton()
        self.btn_open_recordings_folder.setIcon(
            QtGui.QIcon(str(YukiData.icons_folder / "folder.png"))
        )
        self.btn_open_recordings_folder.setToolTip(_("Open recordings folder"))
        self.btn_open_recordings_folder.clicked.connect(open_recording_folder)

        self.record_icon = QtGui.QIcon(str(YukiData.icons_folder / "record.png"))
        self.record_stop_icon = QtGui.QIcon(
            str(YukiData.icons_folder / "stoprecord.png")
        )

        self.btn_record = QtWidgets.QPushButton()
        self.btn_record.setIcon(self.record_icon)
        self.btn_record.setToolTip(_("Record"))

        self.btn_show_scheduler = QtWidgets.QPushButton()
        self.btn_show_scheduler.setIcon(
            QtGui.QIcon(str(YukiData.icons_folder / "calendar.png"))
        )
        self.btn_show_scheduler.setToolTip(_("Recording scheduler"))

        self.btn_volume = QtWidgets.QPushButton()
        self.btn_volume.setIcon(QtGui.QIcon(str(YukiData.icons_folder / "volume.png")))
        self.btn_volume.setToolTip(_("Volume"))

        VOLUME_SLIDER_SET_WIDTH = 150
        self.volume_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.volume_slider.setMinimum(0)
        self.volume_slider.setMaximum(200)
        self.volume_slider.setFixedWidth(VOLUME_SLIDER_SET_WIDTH)

        self.btn_screenshot = QtWidgets.QPushButton()
        self.btn_screenshot.setIcon(
            QtGui.QIcon(str(YukiData.icons_folder / "screenshot.png"))
        )
        self.btn_screenshot.setToolTip(_("Screenshot").capitalize())

        self.btn_show_archive = QtWidgets.QPushButton()
        self.btn_show_archive.setIcon(
            QtGui.QIcon(str(YukiData.icons_folder / "timeshift.png"))
        )
        self.btn_show_archive.setToolTip(_("Archive"))

        self.btn_multi_epg = QtWidgets.QPushButton()
        self.btn_multi_epg.setIcon(QtGui.QIcon(str(YukiData.icons_folder / "bars.png")))
        self.btn_multi_epg.setToolTip(_("Multi-EPG"))

        self.btn_tv_guide = QtWidgets.QPushButton()
        self.btn_tv_guide.setIcon(
            QtGui.QIcon(str(YukiData.icons_folder / "tvguide.png"))
        )
        self.btn_tv_guide.setToolTip(_("TV guide"))

        self.btn_prev_channel = QtWidgets.QPushButton()
        self.btn_prev_channel.setIcon(
            QtGui.QIcon(str(YukiData.icons_folder / "prev.png"))
        )
        self.btn_prev_channel.setToolTip(_("Previous channel"))

        self.btn_next_channel = QtWidgets.QPushButton()
        self.btn_next_channel.setIcon(
            QtGui.QIcon(str(YukiData.icons_folder / "next.png"))
        )
        self.btn_next_channel.setToolTip(_("Next channel"))

        self.label_video_data = QtWidgets.QLabel("")
        self.label_volume = QtWidgets.QLabel("")
        self.label_volume.setMinimumWidth(50)
        self.label_video_data.setFont(self.font_12)
        self.label_volume.setFont(self.font_12)

        self.label_avsync = QtWidgets.QLabel("")
        self.label_avsync.setFont(self.font_12)

        self.label_avsync.setText("A-V -0.00")
        self.label_avsync.setMinimumSize(self.label_avsync.sizeHint())
        self.label_avsync.setText("")

        self.progress = QtWidgets.QProgressBar()
        self.progress.setValue(0)
        self.progress.hide()
        self.start_label = QtWidgets.QLabel()
        self.start_label.hide()
        self.stop_label = QtWidgets.QLabel()
        self.stop_label.hide()

        self.vlayout3 = QtWidgets.QVBoxLayout()
        self.hlayout1 = QtWidgets.QHBoxLayout()
        self.controlpanel_layout = QtWidgets.QHBoxLayout()

        self.hlayout1.addWidget(self.start_label)
        self.hlayout1.addWidget(self.progress)
        self.hlayout1.addWidget(self.stop_label)

        self.controlpanel_btns = [
            self.btn_playpause,
            self.btn_stop,
            self.btn_fullscreen,
            self.btn_record,
            self.btn_show_scheduler,
            self.btn_open_recordings_folder,
            self.btn_volume,
            self.volume_slider,
            self.label_volume,
            self.btn_screenshot,
            self.btn_show_archive,
            self.btn_tv_guide,
            self.btn_multi_epg,
            self.btn_prev_channel,
            self.btn_next_channel,
        ]

        self.show_lbls_fullscreen = [
            self.btn_playpause,
            self.btn_stop,
            self.btn_fullscreen,
            self.btn_record,
            self.btn_volume,
            self.volume_slider,
            self.label_volume,
            self.btn_screenshot,
            self.btn_show_archive,
            self.btn_tv_guide,
            self.btn_prev_channel,
            self.btn_next_channel,
        ]

        for controlpanel_btn in self.controlpanel_btns:
            self.controlpanel_layout.addWidget(controlpanel_btn)
        self.controlpanel_layout.addStretch(1000000)  # FIXME: find better solution
        self.controlpanel_layout.addWidget(self.label_video_data)
        self.controlpanel_layout.addWidget(self.label_avsync)

        self.vlayout3.addLayout(self.controlpanel_layout)
        self.controlpanel_layout.addStretch(1)
        self.vlayout3.addLayout(self.hlayout1)

        self.controlpanel_dock_widget = QtWidgets.QWidget()
        self.controlpanel_dock_widget.setLayout(self.vlayout3)

        self.playlist_widget = QtWidgets.QMainWindow()
        self.playlist_widget_orig = QtWidgets.QWidget(self.playlist_widget)
        self.playlist_widget.setCentralWidget(self.playlist_widget_orig)
        self.pl_layout = QtWidgets.QVBoxLayout()
        self.pl_layout.setContentsMargins(0, 0, 0, 0)
        self.pl_layout.setSpacing(0)
        self.playlist_widget_orig.setLayout(self.pl_layout)
        self.playlist_widget.hide()

        self.controlpanel_widget = QtWidgets.QWidget()
        self.cp_layout = QtWidgets.QVBoxLayout()
        self.controlpanel_widget.setLayout(self.cp_layout)
        self.controlpanel_widget.hide()

        self.license_btn = QtWidgets.QPushButton()
        self.license_btn.setText(_("License"))

        def show_license():
            if not self.license_win.isVisible():
                moveWindowToCenter(self.license_win)
                self.license_win.show()
            else:
                self.license_win.hide()

        self.license_btn.clicked.connect(show_license)

        self.about_qt_btn = QtWidgets.QPushButton()
        self.about_qt_btn.setText(_("About Qt"))
        self.about_qt_btn.clicked.connect(lambda: self.about_qt_show())

        self.close_btn = QtWidgets.QPushButton()
        self.close_btn.setText(_("Close"))
        self.close_btn.clicked.connect(lambda: self.help_win.close())

        self.textbox = QtWidgets.QTextBrowser()
        self.textbox.setOpenExternalLinks(True)
        self.textbox.setReadOnly(True)

        self.helpwin_widget_btns = QtWidgets.QWidget()
        self.helpwin_widget_btns_layout = QtWidgets.QHBoxLayout()
        self.helpwin_widget_btns_layout.addWidget(self.license_btn)
        self.helpwin_widget_btns_layout.addWidget(self.about_qt_btn)
        self.helpwin_widget_btns_layout.addWidget(self.close_btn)
        self.helpwin_widget_btns.setLayout(self.helpwin_widget_btns_layout)

        self.helpwin_widget = QtWidgets.QWidget()
        self.helpwin_layout = QtWidgets.QVBoxLayout()
        self.helpwin_layout.addWidget(self.textbox)
        self.helpwin_layout.addWidget(self.helpwin_widget_btns)
        self.helpwin_widget.setLayout(self.helpwin_layout)

        self.license_str = (
            "This program is free software: you can redistribute it and/or modify\n"
            "it under the terms of the GNU General Public License as published by\n"
            "the Free Software Foundation, either version 3 of the License, or\n"
            "(at your option) any later version.\n"
            "\n"
            "This program is distributed in the hope that it will be useful,\n"
            "but WITHOUT ANY WARRANTY; without even the implied warranty of\n"
            "MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the\n"
            "GNU General Public License for more details.\n"
            "\n"
            "You should have received a copy of the GNU General Public License\n"
            "along with this program.  If not, see <https://www.gnu.org/licenses/>.\n"
            "\n"
            "yuki-iptv is based on Astroncia IPTV code.\n"
            "\n"
            "Original Astroncia IPTV code is licensed under GPL-3.0-only.\n"
            "I have permission from original code author (Astroncia)\n"
            "to relicense code to GPL-3.0-or-later.\n"
            "\n"
            "The Font Awesome pictograms are licensed under the CC BY 4.0 License.\n"
            "Font Awesome Free 5.15.4 by @fontawesome - https://fontawesome.com\n"
            "https://creativecommons.org/licenses/by/4.0/\n"
        )

        if os.path.isfile("/usr/share/common-licenses/GPL"):
            with open(
                "/usr/share/common-licenses/GPL", encoding="utf8"
            ) as license_gpl_file:
                self.license_str += "\n" + license_gpl_file.read()

        self.licensebox = QtWidgets.QPlainTextEdit()
        self.licensebox.setReadOnly(True)
        self.licensebox.setPlainText(self.license_str)

        self.licensebox_close_btn = QtWidgets.QPushButton()
        self.licensebox_close_btn.setText(_("Close"))
        self.licensebox_close_btn.clicked.connect(lambda: self.license_win.close())

        self.licensewin_widget = QtWidgets.QWidget()
        self.licensewin_layout = QtWidgets.QVBoxLayout()
        self.licensewin_layout.addWidget(self.licensebox)
        self.licensewin_layout.addWidget(self.licensebox_close_btn)
        self.licensewin_widget.setLayout(self.licensewin_layout)

        self.streaminfo_widget = QtWidgets.QWidget()
        self.stream_information_win_layout = QtWidgets.QVBoxLayout()
        self.stream_information_layout = QtWidgets.QGridLayout()
        self.stream_information_layout_widget = QtWidgets.QWidget()
        self.stream_information_layout_widget.setLayout(self.stream_information_layout)

        self.url_data_widget = QtWidgets.QWidget()
        self.url_data_layout = QtWidgets.QVBoxLayout()
        self.url_data_widget.setLayout(self.url_data_layout)

        self.url_label = QtWidgets.QLabel(_("URL") + "\n")
        self.url_label.setStyleSheet("color:green")
        self.url_label.setFont(self.font_bold)

        self.url_data_layout.addWidget(self.url_label)

        self.url_text = QtWidgets.QLineEdit()
        self.url_text.setReadOnly(True)

        self.url_data_layout.addWidget(self.url_text)

        self.stream_information_win_layout.addWidget(self.url_data_widget)
        self.stream_information_win_layout.addWidget(
            self.stream_information_layout_widget
        )
        self.streaminfo_widget.setLayout(self.stream_information_win_layout)

        self.grid2 = QtWidgets.QGridLayout()
        self.grid2.setSpacing(0)

        self.ssave = QtWidgets.QPushButton(_("Save settings"))
        self.ssave.setFont(self.font_bold)

        self.sclose = QtWidgets.QPushButton(_("Close"))

        def close_settings(*args, **kwargs):
            self.settings_win.hide()

        self.sclose.clicked.connect(close_settings)

        self.sreset = QtWidgets.QPushButton(_("Reset channel settings"))

        self.clear_logo_cache = QtWidgets.QPushButton(_("Clear logo cache"))

        self.sort_widget = QtWidgets.QComboBox()
        self.sort_widget.addItem(_("as in playlist"))
        self.sort_widget.addItem(_("alphabetical order"))
        self.sort_widget.addItem(_("reverse alphabetical order"))
        self.sort_widget.addItem(_("custom"))

        self.sort_categories_widget = QtWidgets.QComboBox()
        self.sort_categories_widget.addItem(_("as in playlist"))
        self.sort_categories_widget.addItem(_("alphabetical order"))
        self.sort_categories_widget.addItem(_("reverse alphabetical order"))

        self.description_view_widget = QtWidgets.QComboBox()
        self.description_view_widget.addItem(_("Partial"))
        self.description_view_widget.addItem(_("Full"))
        self.description_view_widget.addItem(_("Hide"))

        self.sbtns = QtWidgets.QWidget()
        self.sbtns_layout = QtWidgets.QHBoxLayout()
        self.sbtns_layout.addWidget(self.ssave)
        self.sbtns_layout.addWidget(self.sclose)
        self.sbtns_layout.addWidget(self.sreset)
        self.sbtns_layout.addWidget(self.clear_logo_cache)
        self.sbtns.setLayout(self.sbtns_layout)

        self.grid2.addWidget(self.sbtns, 2, 1)

        self.donot_label = QtWidgets.QLabel(
            "{}:".format(_("Do not update\nEPG at boot"))
        )
        self.donotupdateepg_flag = QtWidgets.QCheckBox()

        self.openprevchannel_label = QtWidgets.QLabel(
            "{}:".format(_("Open previous channel\nat startup"))
        )
        self.hideepgpercentage_label = QtWidgets.QLabel(
            "{}:".format(_("Hide EPG percentage"))
        )
        self.hideepgfromplaylist_label = QtWidgets.QLabel(
            "{}:".format(_("Hide EPG from playlist"))
        )
        self.hidebitrateinfo_label = QtWidgets.QLabel(
            "{}:".format(_("Hide bitrate / video info"))
        )
        self.volumechangestep_label = QtWidgets.QLabel(
            "{}:".format(_("Volume change step"))
        )
        self.volumechangestep_percent = QtWidgets.QLabel("%")

        self.openprevchannel_flag = QtWidgets.QCheckBox()

        self.mpv_label = QtWidgets.QLabel(
            "{} ({}):".format(
                _("mpv options"),
                '<a href="' + MPV_OPTIONS_LINK + '">{}</a>'.format(_("list")),
            )
        )
        self.mpv_label.setOpenExternalLinks(True)
        self.mpv_label.setTextInteractionFlags(
            QtCore.Qt.TextInteractionFlag.LinksAccessibleByMouse
        )
        self.mpv_options = QtWidgets.QLineEdit()

        self.videoaspect_def_choose = QtWidgets.QComboBox()

        self.hideepgpercentage_flag = QtWidgets.QCheckBox()

        self.hideepgfromplaylist_flag = QtWidgets.QCheckBox()

        self.hidebitrateinfo_flag = QtWidgets.QCheckBox()

        self.volumechangestep_choose = QtWidgets.QSpinBox()
        self.volumechangestep_choose.setMinimum(1)
        self.volumechangestep_choose.setMaximum(50)

        self.panelposition_label = QtWidgets.QLabel(
            "{}:".format(_("Floating panel\nposition"))
        )
        self.panelposition_choose = QtWidgets.QComboBox()
        self.panelposition_choose.addItem(_("Right"))
        self.panelposition_choose.addItem(_("Left"))
        self.panelposition_choose.addItem(_("Separate window"))

        self.mouseswitchchannels_label = QtWidgets.QLabel(
            "{}:".format(_("Switch channels with\nthe mouse wheel"))
        )
        self.autoreconnection_label = QtWidgets.QLabel(
            "{}:".format(_("Automatic\nreconnection"))
        )
        self.lowlatency_label = QtWidgets.QLabel("{}:".format(_("Low latency mode")))
        self.defaultchangevol_label = QtWidgets.QLabel(
            "({})".format(_("by default:\nchange volume"))
        )

        self.mouseswitchchannels_flag = QtWidgets.QCheckBox()

        self.autoreconnection_flag = QtWidgets.QCheckBox()

        self.lowlatency_flag = QtWidgets.QCheckBox()

        self.showplaylistmouse_label = QtWidgets.QLabel(
            "{}:".format(_("Show playlist\non mouse move"))
        )
        self.showplaylistmouse_flag = QtWidgets.QCheckBox()

        self.showcontrolsmouse_label = QtWidgets.QLabel(
            "{}:".format(_("Show controls\non mouse move"))
        )
        self.showcontrolsmouse_flag = QtWidgets.QCheckBox()

        self.channellogos_label = QtWidgets.QLabel("{}:".format(_("Channel logos")))
        self.channellogos_select = QtWidgets.QComboBox()
        self.channellogos_select.addItem(_("Prefer M3U"))
        self.channellogos_select.addItem(_("Prefer EPG"))
        self.channellogos_select.addItem(_("Do not load from EPG"))
        self.channellogos_select.addItem(_("Do not load any logos"))

        self.nocacheepg_label = QtWidgets.QLabel("{}:".format(_("Do not cache EPG")))
        self.nocacheepg_flag = QtWidgets.QCheckBox()

        self.scrrecnosubfolders_label = QtWidgets.QLabel(
            "{}:".format(_("Do not create screenshots\nand recordings subfolders"))
        )
        self.scrrecnosubfolders_flag = QtWidgets.QCheckBox()

        self.hidetvprogram_label = QtWidgets.QLabel(
            "{}:".format(_("Hide the current television program"))
        )
        self.hidetvprogram_flag = QtWidgets.QCheckBox()

        self.videoaspectdef_label = QtWidgets.QLabel("{}:".format(_("Aspect ratio")))
        self.zoomdef_label = QtWidgets.QLabel("{}:".format(_("Scale / Zoom")))
        self.panscan_def_label = QtWidgets.QLabel("{}:".format(_("Pan and scan")))

        self.panscan_def_choose = QtWidgets.QDoubleSpinBox()
        self.panscan_def_choose.setMinimum(0)
        self.panscan_def_choose.setMaximum(1)
        self.panscan_def_choose.setSingleStep(0.1)
        self.panscan_def_choose.setDecimals(1)

        self.zoom_def_choose = QtWidgets.QComboBox()

        self.rewindenable_label = QtWidgets.QLabel("{}:".format(_("Enable rewind")))
        self.rewindenable_flag = QtWidgets.QCheckBox()

        self.hidechannellogos_label = QtWidgets.QLabel(
            "{}:".format(_("Hide channel logos"))
        )
        self.hidechannellogos_flag = QtWidgets.QCheckBox()

        self.hideplaylistbyleftmouseclick_label = QtWidgets.QLabel(
            "{}:".format(_("Show/hide playlist by left mouse click"))
        )
        self.hideplaylistbyleftmouseclick_flag = QtWidgets.QCheckBox()

        self.enabletransparency_label = QtWidgets.QLabel(
            "{}:".format(_("Enable transparency for floating panels"))
        )
        self.enabletransparency_flag = QtWidgets.QCheckBox()

        self.useragent_choose_2 = QtWidgets.QLineEdit()

        self.useragent_lbl_2 = QtWidgets.QLabel("{}:".format(_("User agent")))
        self.referer_lbl = QtWidgets.QLabel(_("HTTP Referer:"))
        self.referer_choose = QtWidgets.QLineEdit()

        self.cache_secs = QtWidgets.QSpinBox()
        self.cache_secs.setMinimum(0)
        self.cache_secs.setMaximum(120)

        self.epg_offset = QtWidgets.QDoubleSpinBox()
        self.epg_offset.setMinimum(-240)
        self.epg_offset.setMaximum(240)
        self.epg_offset.setSingleStep(1)
        self.epg_offset.setDecimals(1)

        def do_save_folder_select():
            folder_name = QtWidgets.QFileDialog.getExistingDirectory(
                self.settings_win,
                _("Select folder for recordings and screenshots"),
                options=QtWidgets.QFileDialog.Option.ShowDirsOnly,
            )
            if folder_name:
                self.save_folder.setText(folder_name)

        self.save_folder_select = QtWidgets.QPushButton()
        self.save_folder_select.setIcon(
            QtGui.QIcon(str(YukiData.icons_folder / "file.png"))
        )
        self.save_folder_select.clicked.connect(do_save_folder_select)

        self.scache = QtWidgets.QLabel(
            (ngettext("%d second", "%d seconds", 0) % 0).replace("0 ", "")
        )
        self.sselect = QtWidgets.QLabel("{}:".format(_("Or select provider")))
        self.sselect.setStyleSheet("color: #00008B;")

        self.save_folder = QtWidgets.QLineEdit()

        self.deinterlace = QtWidgets.QCheckBox()

        self.udp_proxy_edit_main = QtWidgets.QLineEdit()

        self.m3u_label = QtWidgets.QLabel("{}:".format(_("M3U / XSPF playlist")))
        self.update_label = QtWidgets.QLabel(
            "{}:".format(_("Update playlist\nat launch"))
        )
        self.epg_label = QtWidgets.QLabel("{}:".format(_("TV guide\naddress")))
        self.dei_label = QtWidgets.QLabel("{}:".format(_("Deinterlace")))
        self.sort_label = QtWidgets.QLabel("{}:".format(_("Channel\nsort")))
        self.sort_categories_label = QtWidgets.QLabel(
            "{}:".format(_("Categories\nsort"))
        )
        self.description_view_label = QtWidgets.QLabel(
            "{}:".format(_("EPG description view"))
        )
        self.cache_label = QtWidgets.QLabel("{}:".format(_("Cache")))
        self.udp_label = QtWidgets.QLabel("{}:".format(_("UDP proxy")))
        self.fld_label = QtWidgets.QLabel(
            "{}:".format(_("Folder for recordings\nand screenshots"))
        )

        self.tabs = QtWidgets.QTabWidget()

        self.tab_main = QtWidgets.QWidget()
        self.tab_video = QtWidgets.QWidget()
        self.tab_network = QtWidgets.QWidget()
        self.tab_other = QtWidgets.QWidget()
        self.tab_gui = QtWidgets.QWidget()
        self.tab_actions = QtWidgets.QWidget()
        self.tab_catchup = QtWidgets.QWidget()
        self.tab_debug = QtWidgets.QWidget()
        self.tab_epg = QtWidgets.QWidget()

        self.tabs.addTab(self.tab_main, _("Main"))
        self.tabs.addTab(self.tab_video, _("Video"))
        self.tabs.addTab(self.tab_network, _("Network"))
        self.tabs.addTab(self.tab_gui, _("GUI"))
        self.tabs.addTab(self.tab_actions, _("Actions"))
        self.tabs.addTab(self.tab_catchup, _("Catchup"))
        self.tabs.addTab(self.tab_epg, _("EPG"))
        self.tabs.addTab(self.tab_other, _("Other"))
        self.tabs.addTab(self.tab_debug, _("Debug"))

        self.tab_main.layout = QtWidgets.QGridLayout()
        self.tab_main.layout.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop
        )
        self.tab_main.layout.addWidget(self.fld_label, 0, 0)
        self.tab_main.layout.addWidget(self.save_folder, 0, 1)
        self.tab_main.layout.addWidget(self.save_folder_select, 0, 2)
        self.tab_main.layout.addWidget(self.scrrecnosubfolders_label, 1, 0)
        self.tab_main.layout.addWidget(self.scrrecnosubfolders_flag, 1, 1)
        self.tab_main.layout.addWidget(self.sort_label, 2, 0)
        self.tab_main.layout.addWidget(self.sort_widget, 2, 1)
        self.tab_main.layout.addWidget(self.sort_categories_label, 3, 0)
        self.tab_main.layout.addWidget(self.sort_categories_widget, 3, 1)
        self.tab_main.layout.addWidget(self.openprevchannel_label, 4, 0)
        self.tab_main.layout.addWidget(self.openprevchannel_flag, 4, 1)
        self.tab_main.setLayout(self.tab_main.layout)

        self.tab_video.layout = QtWidgets.QGridLayout()
        self.tab_video.layout.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop
        )
        self.tab_video.layout.addWidget(self.dei_label, 0, 0)
        self.tab_video.layout.addWidget(self.deinterlace, 0, 1)
        self.tab_video.layout.addWidget(self.videoaspectdef_label, 1, 0)
        self.tab_video.layout.addWidget(self.videoaspect_def_choose, 1, 1)
        self.tab_video.layout.addWidget(self.zoomdef_label, 2, 0)
        self.tab_video.layout.addWidget(self.zoom_def_choose, 2, 1)
        self.tab_video.layout.addWidget(self.panscan_def_label, 3, 0)
        self.tab_video.layout.addWidget(self.panscan_def_choose, 3, 1)
        self.tab_video.setLayout(self.tab_video.layout)

        self.tab_network.layout = QtWidgets.QGridLayout()
        self.tab_network.layout.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop
        )
        # self.tab_network.layout.addWidget(self.udp_label, 0, 0)
        # self.tab_network.layout.addWidget(self.udp_proxy_edit_main, 0, 1)
        self.tab_network.layout.addWidget(self.cache_label, 0, 0)
        self.tab_network.layout.addWidget(self.cache_secs, 0, 1)
        self.tab_network.layout.addWidget(self.scache, 0, 2)
        self.tab_network.layout.addWidget(self.useragent_lbl_2, 1, 0)
        self.tab_network.layout.addWidget(self.useragent_choose_2, 1, 1)
        self.tab_network.layout.addWidget(self.referer_lbl, 2, 0)
        self.tab_network.layout.addWidget(self.referer_choose, 2, 1)
        self.tab_network.setLayout(self.tab_network.layout)

        self.tab_gui.layout = QtWidgets.QGridLayout()
        self.tab_gui.layout.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop
        )
        self.tab_gui.layout.addWidget(self.panelposition_label, 0, 0)
        self.tab_gui.layout.addWidget(self.panelposition_choose, 0, 1)
        self.tab_gui.layout.addWidget(self.description_view_label, 1, 0)
        self.tab_gui.layout.addWidget(self.description_view_widget, 1, 1)
        self.tab_gui.layout.addWidget(self.enabletransparency_label, 2, 0)
        self.tab_gui.layout.addWidget(self.enabletransparency_flag, 2, 1)
        self.tab_gui.layout.addWidget(self.hideplaylistbyleftmouseclick_label, 3, 0)
        self.tab_gui.layout.addWidget(self.hideplaylistbyleftmouseclick_flag, 3, 1)
        self.tab_gui.layout.addWidget(self.hideepgfromplaylist_label, 4, 0)
        self.tab_gui.layout.addWidget(self.hideepgfromplaylist_flag, 4, 1)
        self.tab_gui.layout.addWidget(self.hideepgpercentage_label, 5, 0)
        self.tab_gui.layout.addWidget(self.hideepgpercentage_flag, 5, 1)
        self.tab_gui.layout.addWidget(self.hidebitrateinfo_label, 6, 0)
        self.tab_gui.layout.addWidget(self.hidebitrateinfo_flag, 6, 1)
        self.tab_gui.layout.addWidget(self.hidetvprogram_label, 7, 0)
        self.tab_gui.layout.addWidget(self.hidetvprogram_flag, 7, 1)
        self.tab_gui.layout.addWidget(self.hidechannellogos_label, 8, 0)
        self.tab_gui.layout.addWidget(self.hidechannellogos_flag, 8, 1)
        self.tab_gui.setLayout(self.tab_gui.layout)

        self.tab_actions.layout = QtWidgets.QGridLayout()
        self.tab_actions.layout.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop
        )
        self.tab_actions.layout.addWidget(self.mouseswitchchannels_label, 0, 0)
        self.tab_actions.layout.addWidget(self.mouseswitchchannels_flag, 0, 1)
        self.tab_actions.layout.addWidget(self.defaultchangevol_label, 1, 0)
        self.tab_actions.layout.addWidget(self.showplaylistmouse_label, 3, 0)
        self.tab_actions.layout.addWidget(self.showplaylistmouse_flag, 3, 1)
        self.tab_actions.layout.addWidget(self.showcontrolsmouse_label, 4, 0)
        self.tab_actions.layout.addWidget(self.showcontrolsmouse_flag, 4, 1)
        self.tab_actions.setLayout(self.tab_actions.layout)

        self.tab_catchup.layout = QtWidgets.QGridLayout()
        self.tab_catchup.layout.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop
        )
        self.tab_catchup.layout.addWidget(self.rewindenable_label, 0, 0)
        self.tab_catchup.layout.addWidget(self.rewindenable_flag, 0, 1)
        self.tab_catchup.setLayout(self.tab_catchup.layout)

        self.tab_epg.layout = QtWidgets.QGridLayout()
        self.tab_epg.layout.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop
        )
        self.tab_epg.layout.addWidget(self.donot_label, 0, 0)
        self.tab_epg.layout.addWidget(self.donotupdateepg_flag, 0, 1)
        self.tab_epg.layout.addWidget(self.nocacheepg_label, 1, 0)
        self.tab_epg.layout.addWidget(self.nocacheepg_flag, 1, 1)
        self.tab_epg.setLayout(self.tab_epg.layout)

        self.tab_other.layout = QtWidgets.QGridLayout()
        self.tab_other.layout.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop
        )
        self.tab_other.layout.addWidget(self.mpv_label, 0, 0)
        self.tab_other.layout.addWidget(self.mpv_options, 0, 1)
        self.tab_other.layout.addWidget(self.channellogos_label, 1, 0)
        self.tab_other.layout.addWidget(self.channellogos_select, 1, 1)
        self.tab_other.layout.addWidget(self.volumechangestep_label, 2, 0)
        self.tab_other.layout.addWidget(self.volumechangestep_choose, 2, 1)
        self.tab_other.layout.addWidget(self.volumechangestep_percent, 2, 2)
        self.tab_other.setLayout(self.tab_other.layout)

        self.tab_debug_warning = QtWidgets.QLabel(
            _("WARNING: experimental function, working with problems")
        )

        self.tab_debug_widget = QtWidgets.QWidget()
        self.tab_debug.layout = QtWidgets.QGridLayout()
        self.tab_debug.layout.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop
        )
        self.tab_debug.layout.addWidget(self.autoreconnection_label, 0, 0)
        self.tab_debug.layout.addWidget(self.autoreconnection_flag, 0, 1)
        self.tab_debug.layout.addWidget(self.lowlatency_label, 1, 0)
        self.tab_debug.layout.addWidget(self.lowlatency_flag, 1, 1)
        self.tab_debug_widget.setLayout(self.tab_debug.layout)
        self.tab_debug.layout1 = QtWidgets.QVBoxLayout()
        self.tab_debug.layout1.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop
        )
        self.tab_debug.layout1.addWidget(self.tab_debug_warning)
        self.tab_debug.layout1.addWidget(self.tab_debug_widget)
        self.tab_debug.setLayout(self.tab_debug.layout1)

        self.grid = QtWidgets.QVBoxLayout()
        self.grid.addWidget(self.tabs)

        self.layout2 = QtWidgets.QVBoxLayout()
        self.layout2.addLayout(self.grid)
        self.layout2.addLayout(self.grid2)

        self.settings_widget = QtWidgets.QWidget()
        self.settings_widget.setLayout(self.layout2)

        self.wid = QtWidgets.QWidget()

        self.title = QtWidgets.QLabel()
        self.title.setFont(self.font_bold)
        self.title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        self.deinterlace_lbl = QtWidgets.QLabel("{}:".format(_("Deinterlace")))
        self.useragent_lbl = QtWidgets.QLabel("{}:".format(_("User agent")))
        self.group_lbl = QtWidgets.QLabel("{}:".format(_("Group")))
        self.group_text = QtWidgets.QLineEdit()
        self.hidden_lbl = QtWidgets.QLabel("{}:".format(_("Hide")))
        self.deinterlace_chk = QtWidgets.QCheckBox()
        self.hidden_chk = QtWidgets.QCheckBox()
        self.useragent_choose = QtWidgets.QLineEdit()

        self.epgname_lbl = QtWidgets.QLabel()

        self.contrast_choose = QtWidgets.QSpinBox()
        self.contrast_choose.setMinimum(-100)
        self.contrast_choose.setMaximum(100)
        self.brightness_choose = QtWidgets.QSpinBox()
        self.brightness_choose.setMinimum(-100)
        self.brightness_choose.setMaximum(100)
        self.hue_choose = QtWidgets.QSpinBox()
        self.hue_choose.setMinimum(-100)
        self.hue_choose.setMaximum(100)
        self.saturation_choose = QtWidgets.QSpinBox()
        self.saturation_choose.setMinimum(-100)
        self.saturation_choose.setMaximum(100)
        self.gamma_choose = QtWidgets.QSpinBox()
        self.gamma_choose.setMinimum(-100)
        self.gamma_choose.setMaximum(100)
        self.videoaspect_vars = {
            _("Default"): -1,
            "16:9": "16:9",
            "16:10": "16:10",
            "1.85:1": "1.85:1",
            "2.21:1": "2.21:1",
            "2.35:1": "2.35:1",
            "2.39:1": "2.39:1",
            "4:3": "4:3",
            "5:4": "5:4",
            "5:3": "5:3",
            "1:1": "1:1",
        }
        self.videoaspect_choose = QtWidgets.QComboBox()
        for videoaspect_var in self.videoaspect_vars:
            self.videoaspect_choose.addItem(videoaspect_var)

        self.zoom_choose = QtWidgets.QComboBox()
        self.zoom_vars = {
            _("Default"): 0,
            "1.05": "1.05",
            "1.1": "1.1",
            "1.2": "1.2",
            "1.3": "1.3",
            "1.4": "1.4",
            "1.5": "1.5",
            "1.6": "1.6",
            "1.7": "1.7",
            "1.8": "1.8",
            "1.9": "1.9",
            "2": "2",
        }
        for zoom_var in self.zoom_vars:
            self.zoom_choose.addItem(zoom_var)

        self.panscan_choose = QtWidgets.QDoubleSpinBox()
        self.panscan_choose.setMinimum(0)
        self.panscan_choose.setMaximum(1)
        self.panscan_choose.setSingleStep(0.1)
        self.panscan_choose.setDecimals(1)

        self.contrast_lbl = QtWidgets.QLabel("{}:".format(_("Contrast")))
        self.brightness_lbl = QtWidgets.QLabel("{}:".format(_("Brightness")))
        self.hue_lbl = QtWidgets.QLabel("{}:".format(_("Hue")))
        self.saturation_lbl = QtWidgets.QLabel("{}:".format(_("Saturation")))
        self.gamma_lbl = QtWidgets.QLabel("{}:".format(_("Gamma")))
        self.videoaspect_lbl = QtWidgets.QLabel("{}:".format(_("Aspect ratio")))
        self.zoom_lbl = QtWidgets.QLabel("{}:".format(_("Scale / Zoom")))
        self.panscan_lbl = QtWidgets.QLabel("{}:".format(_("Pan and scan")))
        self.epgname_btn = QtWidgets.QPushButton(_("EPG name"))

        self.referer_lbl_custom = QtWidgets.QLabel(_("HTTP Referer:"))
        self.referer_choose_custom = QtWidgets.QLineEdit()

        self.save_btn = QtWidgets.QPushButton(_("Save settings"))
        self.save_btn.setFont(self.font_bold)

        self.horizontalLayout = QtWidgets.QHBoxLayout()
        self.horizontalLayout.addWidget(self.title)

        self.horizontalLayout2 = QtWidgets.QHBoxLayout()
        self.horizontalLayout2.addWidget(QtWidgets.QLabel("\n"))
        self.horizontalLayout2.addWidget(self.deinterlace_lbl)
        self.horizontalLayout2.addWidget(self.deinterlace_chk)
        self.horizontalLayout2.addWidget(QtWidgets.QLabel("\n"))
        self.horizontalLayout2.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        self.horizontalLayout2_1 = QtWidgets.QHBoxLayout()
        self.horizontalLayout2_1.addWidget(QtWidgets.QLabel("\n"))
        self.horizontalLayout2_1.addWidget(self.useragent_lbl)
        self.horizontalLayout2_1.addWidget(self.useragent_choose)
        self.horizontalLayout2_1.addWidget(QtWidgets.QLabel("\n"))
        self.horizontalLayout2_1.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        self.horizontalLayout2_13 = QtWidgets.QHBoxLayout()
        self.horizontalLayout2_13.addWidget(QtWidgets.QLabel("\n"))
        self.horizontalLayout2_13.addWidget(self.referer_lbl_custom)
        self.horizontalLayout2_13.addWidget(self.referer_choose_custom)
        self.horizontalLayout2_13.addWidget(QtWidgets.QLabel("\n"))
        self.horizontalLayout2_13.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        self.horizontalLayout2_2 = QtWidgets.QHBoxLayout()
        self.horizontalLayout2_2.addWidget(QtWidgets.QLabel("\n"))
        self.horizontalLayout2_2.addWidget(self.group_lbl)
        self.horizontalLayout2_2.addWidget(self.group_text)
        self.horizontalLayout2_2.addWidget(QtWidgets.QLabel("\n"))
        self.horizontalLayout2_2.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        self.horizontalLayout2_3 = QtWidgets.QHBoxLayout()
        self.horizontalLayout2_3.addWidget(QtWidgets.QLabel("\n"))
        self.horizontalLayout2_3.addWidget(self.hidden_lbl)
        self.horizontalLayout2_3.addWidget(self.hidden_chk)
        self.horizontalLayout2_3.addWidget(QtWidgets.QLabel("\n"))
        self.horizontalLayout2_3.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        self.horizontalLayout2_4 = QtWidgets.QHBoxLayout()
        self.horizontalLayout2_4.addWidget(QtWidgets.QLabel("\n"))
        self.horizontalLayout2_4.addWidget(self.contrast_lbl)
        self.horizontalLayout2_4.addWidget(self.contrast_choose)
        self.horizontalLayout2_4.addWidget(QtWidgets.QLabel("\n"))
        self.horizontalLayout2_4.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        self.horizontalLayout2_5 = QtWidgets.QHBoxLayout()
        self.horizontalLayout2_5.addWidget(QtWidgets.QLabel("\n"))
        self.horizontalLayout2_5.addWidget(self.brightness_lbl)
        self.horizontalLayout2_5.addWidget(self.brightness_choose)
        self.horizontalLayout2_5.addWidget(QtWidgets.QLabel("\n"))
        self.horizontalLayout2_5.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        self.horizontalLayout2_6 = QtWidgets.QHBoxLayout()
        self.horizontalLayout2_6.addWidget(QtWidgets.QLabel("\n"))
        self.horizontalLayout2_6.addWidget(self.hue_lbl)
        self.horizontalLayout2_6.addWidget(self.hue_choose)
        self.horizontalLayout2_6.addWidget(QtWidgets.QLabel("\n"))
        self.horizontalLayout2_6.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        self.horizontalLayout2_7 = QtWidgets.QHBoxLayout()
        self.horizontalLayout2_7.addWidget(QtWidgets.QLabel("\n"))
        self.horizontalLayout2_7.addWidget(self.saturation_lbl)
        self.horizontalLayout2_7.addWidget(self.saturation_choose)
        self.horizontalLayout2_7.addWidget(QtWidgets.QLabel("\n"))
        self.horizontalLayout2_7.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        self.horizontalLayout2_8 = QtWidgets.QHBoxLayout()
        self.horizontalLayout2_8.addWidget(QtWidgets.QLabel("\n"))
        self.horizontalLayout2_8.addWidget(self.gamma_lbl)
        self.horizontalLayout2_8.addWidget(self.gamma_choose)
        self.horizontalLayout2_8.addWidget(QtWidgets.QLabel("\n"))
        self.horizontalLayout2_8.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        self.horizontalLayout2_9 = QtWidgets.QHBoxLayout()
        self.horizontalLayout2_9.addWidget(QtWidgets.QLabel("\n"))
        self.horizontalLayout2_9.addWidget(self.videoaspect_lbl)
        self.horizontalLayout2_9.addWidget(self.videoaspect_choose)
        self.horizontalLayout2_9.addWidget(QtWidgets.QLabel("\n"))
        self.horizontalLayout2_9.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        self.horizontalLayout2_10 = QtWidgets.QHBoxLayout()
        self.horizontalLayout2_10.addWidget(QtWidgets.QLabel("\n"))
        self.horizontalLayout2_10.addWidget(self.zoom_lbl)
        self.horizontalLayout2_10.addWidget(self.zoom_choose)
        self.horizontalLayout2_10.addWidget(QtWidgets.QLabel("\n"))
        self.horizontalLayout2_10.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        self.horizontalLayout2_11 = QtWidgets.QHBoxLayout()
        self.horizontalLayout2_11.addWidget(QtWidgets.QLabel("\n"))
        self.horizontalLayout2_11.addWidget(self.panscan_lbl)
        self.horizontalLayout2_11.addWidget(self.panscan_choose)
        self.horizontalLayout2_11.addWidget(QtWidgets.QLabel("\n"))
        self.horizontalLayout2_11.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        self.horizontalLayout2_12 = QtWidgets.QHBoxLayout()
        self.horizontalLayout2_12.addWidget(QtWidgets.QLabel("\n"))
        self.horizontalLayout2_12.addWidget(self.epgname_btn)
        self.horizontalLayout2_12.addWidget(self.epgname_lbl)
        self.horizontalLayout2_12.addWidget(QtWidgets.QLabel("\n"))
        self.horizontalLayout2_12.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        self.horizontalLayout3 = QtWidgets.QHBoxLayout()
        self.horizontalLayout3.addWidget(self.save_btn)

        self.verticalLayout = QtWidgets.QVBoxLayout(self.wid)
        self.verticalLayout.addLayout(self.horizontalLayout)
        self.verticalLayout.addLayout(self.horizontalLayout2)
        self.verticalLayout.addLayout(self.horizontalLayout2_1)
        self.verticalLayout.addLayout(self.horizontalLayout2_13)
        self.verticalLayout.addLayout(self.horizontalLayout2_2)
        self.verticalLayout.addLayout(self.horizontalLayout2_3)
        self.verticalLayout.addLayout(self.horizontalLayout2_4)
        self.verticalLayout.addLayout(self.horizontalLayout2_5)
        self.verticalLayout.addLayout(self.horizontalLayout2_6)
        self.verticalLayout.addLayout(self.horizontalLayout2_7)
        self.verticalLayout.addLayout(self.horizontalLayout2_8)
        self.verticalLayout.addLayout(self.horizontalLayout2_9)
        self.verticalLayout.addLayout(self.horizontalLayout2_10)
        self.verticalLayout.addLayout(self.horizontalLayout2_11)
        self.verticalLayout.addLayout(self.horizontalLayout2_12)
        self.verticalLayout.addLayout(self.horizontalLayout3)
        self.verticalLayout.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignHCenter | QtCore.Qt.AlignmentFlag.AlignTop
        )

        self.wid.setLayout(self.verticalLayout)

    def show_playlist_editor(self):
        if self.playlist_editor.isVisible():
            self.playlist_editor.hide()
        else:
            moveWindowToCenter(self.playlist_editor)
            self.playlist_editor.show()

    def create_windows(self):
        self.playlist_editor = PlaylistEditor()

        self.settings_win = self.SettingsScrollableWindow()
        self.settings_win.resize(800, 600)
        self.settings_win.setWindowTitle(_("Settings"))
        self.settings_win.setWindowIcon(self.main_icon)
        self.settings_win.scroll.setWidget(self.settings_widget)

        self.shortcuts_win = QtWidgets.QMainWindow()
        self.shortcuts_win.resize(720, 500)
        self.shortcuts_win.setWindowTitle(_("Shortcuts"))
        self.shortcuts_win.setWindowIcon(self.main_icon)

        self.shortcuts_central_widget = QtWidgets.QWidget(self.shortcuts_win)
        self.shortcuts_win.setCentralWidget(self.shortcuts_central_widget)

        self.shortcuts_grid_layout = QtWidgets.QVBoxLayout()
        self.shortcuts_central_widget.setLayout(self.shortcuts_grid_layout)

        self.shortcuts_table = QtWidgets.QTableWidget(self.shortcuts_win)
        # self.shortcuts_table.setColumnCount(3)
        self.shortcuts_table.setColumnCount(2)

        # self.shortcuts_table.setHorizontalHeaderLabels(
        #     [_('Description'), _('Shortcut'), "Header 3"]
        # )
        self.shortcuts_table.setHorizontalHeaderLabels(
            [_("Description"), _("Shortcut")]
        )

        self.shortcuts_table.horizontalHeaderItem(0).setTextAlignment(
            QtCore.Qt.AlignmentFlag.AlignHCenter
        )
        self.shortcuts_table.horizontalHeaderItem(1).setTextAlignment(
            QtCore.Qt.AlignmentFlag.AlignHCenter
        )
        # self.shortcuts_table.horizontalHeaderItem(2).setTextAlignment(
        #     QtCore.Qt.AlignmentFlag.AlignHCenter
        # )

        self.resettodefaults_btn = QtWidgets.QPushButton()
        self.resettodefaults_btn.setText(_("Reset to defaults"))

        self.shortcuts_grid_layout.addWidget(self.shortcuts_table)
        self.shortcuts_grid_layout.addWidget(self.resettodefaults_btn)

        self.shortcuts_win_2 = QtWidgets.QMainWindow()
        self.shortcuts_win_2.resize(300, 100)
        self.shortcuts_win_2.setWindowTitle(_("Modify shortcut"))
        self.shortcuts_win_2.setWindowIcon(self.main_icon)

        self.help_win = QtWidgets.QMainWindow()
        self.help_win.resize(500, 600)
        self.help_win.setWindowTitle(_("&About yuki-iptv").replace("&", ""))
        self.help_win.setWindowIcon(self.main_icon)
        self.help_win.setCentralWidget(self.helpwin_widget)

        self.license_win = QtWidgets.QMainWindow()
        self.license_win.resize(600, 600)
        self.license_win.setWindowTitle(_("License"))
        self.license_win.setWindowIcon(self.main_icon)
        self.license_win.setCentralWidget(self.licensewin_widget)

        self.sort_win = QtWidgets.QMainWindow()
        self.sort_win.resize(400, 500)
        self.sort_win.setWindowTitle(_("Channel sort"))
        self.sort_win.setWindowIcon(self.main_icon)

        self.channels_win = QtWidgets.QMainWindow()
        self.channels_win.resize(400, 250)
        self.channels_win.setWindowTitle(_("Video settings"))
        self.channels_win.setWindowIcon(self.main_icon)

        self.ext_win = QtWidgets.QMainWindow()
        self.ext_win.resize(300, 60)
        self.ext_win.setWindowTitle(_("Open in external player"))
        self.ext_win.setWindowIcon(self.main_icon)

        self.epg_win = QtWidgets.QMainWindow()
        self.epg_win.resize(1000, 600)
        self.epg_win.setWindowTitle(_("TV guide"))
        self.epg_win.setWindowIcon(self.main_icon)

        self.multi_epg_win = MultiEPGWindow()
        self.multi_epg_win.resize(*WINDOW_SIZE)
        self.multi_epg_win.setWindowTitle(_("Multi-EPG"))
        self.multi_epg_win.setWindowIcon(self.main_icon)

        self.scheduler_win = QtWidgets.QMainWindow()
        self.scheduler_win.resize(*WINDOW_SIZE)
        self.scheduler_win.setWindowTitle(_("Recording scheduler"))
        self.scheduler_win.setWindowIcon(self.main_icon)

        self.epg_select_win = QtWidgets.QMainWindow()
        self.epg_select_win.resize(400, 500)
        self.epg_select_win.setWindowTitle(_("TV guide"))
        self.epg_select_win.setWindowIcon(self.main_icon)

        create_playlists_window()

    def get_settings(self):
        udp_proxy_text = self.udp_proxy_edit_main.text().strip()
        udp_proxy_starts = udp_proxy_text.startswith(
            "http://"
        ) or udp_proxy_text.startswith("https://")
        if udp_proxy_text and not udp_proxy_starts:
            udp_proxy_text = "http://" + udp_proxy_text

        save_folder_text = self.save_folder.text().strip()
        if save_folder_text:
            if save_folder_text[0] == "~":
                save_folder_text = save_folder_text.replace("~", home_folder, 1)
            elif save_folder_text.startswith("$HOME"):
                save_folder_text = save_folder_text.replace("$HOME", home_folder, 1)
            elif save_folder_text.startswith("${HOME}"):
                save_folder_text = save_folder_text.replace("${HOME}", home_folder, 1)

        settings_arr = {
            "m3u": self.m3u.strip(),
            "epg": self.epg.strip(),
            "deinterlace": self.deinterlace.isChecked(),
            "udp_proxy": udp_proxy_text,
            "save_folder": save_folder_text
            if save_folder_text
            else SAVE_FOLDER_DEFAULT,
            "epgoffset": self.epg_offset.value(),
            "sort": self.sort_widget.currentIndex(),
            "sort_categories": self.sort_categories_widget.currentIndex(),
            "description_view": self.description_view_widget.currentIndex(),
            "cache_secs": self.cache_secs.value(),
            "ua": self.useragent_choose_2.text().strip(),
            "mpv_options": self.mpv_options.text().strip(),
            "donotupdateepg": self.donotupdateepg_flag.isChecked(),
            "openprevchannel": self.openprevchannel_flag.isChecked(),
            "hideepgpercentage": self.hideepgpercentage_flag.isChecked(),
            "hideepgfromplaylist": self.hideepgfromplaylist_flag.isChecked(),
            "hidebitrateinfo": self.hidebitrateinfo_flag.isChecked(),
            "volumechangestep": self.volumechangestep_choose.value(),
            "mouseswitchchannels": self.mouseswitchchannels_flag.isChecked(),
            "autoreconnection": self.autoreconnection_flag.isChecked(),
            "showplaylistmouse": self.showplaylistmouse_flag.isChecked(),
            "channellogos": self.channellogos_select.currentIndex(),
            "nocacheepg": self.nocacheepg_flag.isChecked(),
            "scrrecnosubfolders": self.scrrecnosubfolders_flag.isChecked(),
            "hidetvprogram": self.hidetvprogram_flag.isChecked(),
            "showcontrolsmouse": self.showcontrolsmouse_flag.isChecked(),
            "hidechannellogos": self.hidechannellogos_flag.isChecked(),
            "hideplaylistbyleftmouseclick": self.hideplaylistbyleftmouseclick_flag.isChecked(),  # noqa: E501
            "enabletransparency": self.enabletransparency_flag.isChecked(),
            "rewindenable": self.rewindenable_flag.isChecked(),
            "panelposition": self.panelposition_choose.currentIndex(),
            "videoaspect": self.videoaspect_def_choose.currentIndex(),
            "zoom": self.zoom_def_choose.currentIndex(),
            "panscan": self.panscan_def_choose.value(),
            "referer": self.referer_choose.text().strip(),
            "lowlatency": self.lowlatency_flag.isChecked(),
            "playlist_useragent": YukiData.settings["playlist_useragent"].strip(),
            "playlist_referer": YukiData.settings["playlist_referer"].strip(),
            "playlist_udp_proxy": YukiData.settings["playlist_udp_proxy"].strip(),
        }

        return settings_arr

    def create_rewind(self, Slider):
        self.rewind = QtWidgets.QWidget(YukiData.win)
        self.rewind.setStyleSheet("background-color: " + BCOLOR)
        self.rewind.setFont(self.font_12_bold)
        self.rewind.move(50, 50)
        self.rewind.resize(self.rewind.width(), self.rewind.height() + 5)

        self.rewind_layout = QtWidgets.QVBoxLayout()
        self.rewind_layout.setContentsMargins(100, 0, 50, 0)
        self.rewind_layout.setSpacing(0)
        self.rewind_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        self.rewind_label = QtWidgets.QLabel(_("Rewind"))
        self.rewind_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.rewind_label.setFont(self.font_bold)
        self.rewind_label.setStyleSheet("color: pink")

        self.rewind_slider = Slider(QtCore.Qt.Orientation.Horizontal)
        self.rewind_slider.setTickInterval(1)

        self.rewind_layout.addWidget(self.rewind_label)
        self.rewind_layout.addWidget(self.rewind_slider)

        self.rewind.setLayout(self.rewind_layout)
        self.rewind.hide()

    def create2(
        self,
        page_count,
        channelfilter_clicked,
        channelfilter_do,
        page_change,
        MyLineEdit,
        playmode_selector,
        movies_combobox,
        loading,
    ):
        self.channelfilter = MyLineEdit()
        self.channelfilter.click_event.connect(channelfilter_clicked)
        self.channelfilter.setPlaceholderText(_("Search channel"))
        self.channelfiltersearch = QtWidgets.QPushButton()
        self.channelfiltersearch.setToolTip(_("Search"))
        self.channelfiltersearch.setIcon(
            QtGui.QIcon(str(YukiData.icons_folder / "search.png"))
        )
        self.channelfiltersearch.clicked.connect(channelfilter_do)
        self.channelfilter.returnPressed.connect(channelfilter_do)
        self.widget3 = QtWidgets.QWidget()
        self.layout3 = QtWidgets.QHBoxLayout()
        self.layout3.addWidget(self.channelfilter)
        self.layout3.addWidget(self.channelfiltersearch)
        self.widget3.setLayout(self.layout3)
        self.widget4 = QtWidgets.QWidget()
        self.layout4 = QtWidgets.QHBoxLayout()
        self.layout4.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop
        )
        self.page_lbl = QtWidgets.QLabel("{}:".format(_("Page")))
        self.of_lbl = QtWidgets.QLabel()
        self.page_box = QtWidgets.QSpinBox()
        self.page_box.setSuffix("        ")
        self.page_box.setMinimum(1)
        self.page_box.setMaximum(page_count)
        self.page_box.setStyleSheet(
            """
            QSpinBox::down-button  {
              subcontrol-origin: margin;
              subcontrol-position: center left;
              left: 1px;
              image: url("""
            + str(YukiData.icons_folder / "leftarrow.png")
            + """);
              height: 24px;
              width: 24px;
            }

            QSpinBox::up-button  {
              subcontrol-origin: margin;
              subcontrol-position: center right;
              right: 1px;
              image: url("""
            + str(YukiData.icons_folder / "rightarrow.png")
            + """);
              height: 24px;
              width: 24px;
            }
        """
        )
        self.page_box.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.page_box.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self.of_lbl.setText(f"/ {page_count}")

        self.page_box.valueChanged.connect(page_change)
        self.layout4.addWidget(self.page_lbl)
        self.layout4.addWidget(self.page_box)
        self.layout4.addWidget(self.of_lbl)
        self.widget4.setLayout(self.layout4)
        self.layout = QtWidgets.QGridLayout()
        self.layout.setVerticalSpacing(0)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        self.layout.setSpacing(0)
        self.widget = QtWidgets.QWidget()
        self.widget.setLayout(self.layout)
        self.widget.layout().addWidget(QtWidgets.QLabel())
        self.widget.layout().addWidget(playmode_selector)
        self.widget.layout().addWidget(YukiData.combobox)
        # == Movies start ==
        movies_combobox.hide()
        self.widget.layout().addWidget(movies_combobox)
        # == Movies end ==
        self.widget.layout().addWidget(self.widget3)
        self.widget.layout().addWidget(YukiData.win.listWidget)
        # Movies start
        YukiData.win.moviesWidget.hide()
        self.widget.layout().addWidget(YukiData.win.moviesWidget)
        # Movies end
        # Series start
        YukiData.win.seriesWidget.hide()
        self.widget.layout().addWidget(YukiData.win.seriesWidget)
        # Series end
        self.widget.layout().addWidget(self.widget4)
        self.widget.layout().addWidget(self.channel)
        self.widget.layout().addWidget(loading)

    def create3(self):
        self.channel = QtWidgets.QLabel()
        self.channel.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.channel.setFont(self.font_11_bold)
        self.channel.hide()

        self.loading1 = QtWidgets.QLabel(YukiData.win)
        self.loading_movie = QtGui.QMovie(str(YukiData.icons_folder / "loading.gif"))
        self.loading1.setMovie(self.loading_movie)
        self.loading1.resize(32, 32)
        self.loading1.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        centerwidget(self.loading1)
        self.loading1.hide()

        self.loading2 = QtWidgets.QLabel(YukiData.win)
        self.loading_movie2 = QtGui.QMovie(
            str(YukiData.icons_folder / "recordwait.gif")
        )
        self.loading2.setMovie(self.loading_movie2)
        self.loading2.setToolTip(_("Processing record..."))
        self.loading2.resize(32, 32)
        self.loading2.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        centerwidget(self.loading2, 50)
        self.loading2.hide()
        self.loading_movie2.stop()

        self.lbl2_offset = YukiData.win.menuBar().height()
        self.tvguide_lbl_offset = self.lbl2_offset

        self.lbl2 = QtWidgets.QLabel(YukiData.win)
        self.lbl2.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.lbl2.setStyleSheet("background-color: " + BCOLOR + "; color: #e0071a")
        self.lbl2.setWordWrap(True)
        self.lbl2.resize(230, 30)
        self.lbl2.move(0, self.lbl2_offset)
        self.lbl2.hide()

        self.set_widget_opacity(self.lbl2, self.DEFAULT_OPACITY)

    def create_scheduler_widgets(self):
        self.scheduler_widget = QtWidgets.QWidget()
        self.scheduler_layout = QtWidgets.QGridLayout()
        self.scheduler_clock = QtWidgets.QLabel(get_current_time())
        self.scheduler_clock.setFont(self.font_11_bold)
        self.scheduler_clock.setStyleSheet("color: green")
        self.plannedrec_lbl = QtWidgets.QLabel("{}:".format(_("Planned recordings")))
        self.activerec_lbl = QtWidgets.QLabel("{}:".format(_("Active recordings")))
        self.statusrec_lbl = QtWidgets.QLabel()
        self.statusrec_lbl.setFont(self.font_bold)
        self.choosechannel_lbl = QtWidgets.QLabel("{}:".format(_("Choose channel")))
        self.choosechannel_ch = QtWidgets.QComboBox()
        self.choosechannel_ch.setMaximumWidth(300)
        self.tvguide_sch = QtWidgets.QListWidget()
        self.tvguide_sch.setWordWrap(True)
        self.addrecord_btn = QtWidgets.QPushButton(_("Add"))
        self.delrecord_btn = QtWidgets.QPushButton(_("Remove"))

        self.schedulerchannelfilter = QtWidgets.QLineEdit()
        self.schedulerchannelfilter.setPlaceholderText(_("Search channel"))
        self.schedulerchannelfiltersearch = QtWidgets.QPushButton()
        self.schedulerchannelfiltersearch.setToolTip(_("Search"))
        self.schedulerchannelfiltersearch.setIcon(
            QtGui.QIcon(str(YukiData.icons_folder / "search.png"))
        )

        self.schedulerchannelwidget = QtWidgets.QWidget()
        self.schedulerchannellayout = QtWidgets.QHBoxLayout()
        self.schedulerchannellayout.addWidget(self.schedulerchannelfilter)
        self.schedulerchannellayout.addWidget(self.schedulerchannelfiltersearch)
        self.schedulerchannelwidget.setLayout(self.schedulerchannellayout)

        self.scheduler_layout.addWidget(self.scheduler_clock, 0, 0)
        self.scheduler_layout.addWidget(self.choosechannel_lbl, 1, 0)
        self.scheduler_layout.addWidget(self.schedulerchannelwidget, 2, 0)
        self.scheduler_layout.addWidget(self.choosechannel_ch, 3, 0)
        self.scheduler_layout.addWidget(self.tvguide_sch, 4, 0)

        self.starttime_lbl = QtWidgets.QLabel("{}:".format(_("Start record time")))
        self.endtime_lbl = QtWidgets.QLabel("{}:".format(_("End record time")))
        self.starttime_w = QtWidgets.QDateTimeEdit()
        self.starttime_w.setDateTime(
            QtCore.QDateTime.fromString(
                time.strftime("%d.%m.%Y %H:%M", time.localtime()), QT_TIME_FORMAT
            )
        )
        self.endtime_w = QtWidgets.QDateTimeEdit()
        self.endtime_w.setDateTime(
            QtCore.QDateTime.fromString(
                time.strftime("%d.%m.%Y %H:%M", time.localtime(time.time() + 60)),
                QT_TIME_FORMAT,
            )
        )

        self.praction_lbl = QtWidgets.QLabel("{}:".format(_("Post-recording\naction")))
        self.praction_choose = QtWidgets.QComboBox()
        self.praction_choose.addItem(_("Nothing to do"))
        self.praction_choose.addItem(_("Press Stop"))

        self.schedulers = QtWidgets.QListWidget()
        self.schedulers.setWordWrap(True)
        self.activerec_list = QtWidgets.QListWidget()
        self.activerec_list.setWordWrap(True)

        self.scheduler_layout_2 = QtWidgets.QGridLayout()
        self.scheduler_layout_2.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignHCenter | QtCore.Qt.AlignmentFlag.AlignTop
        )
        self.scheduler_layout_2.addWidget(self.starttime_lbl, 0, 0)
        self.scheduler_layout_2.addWidget(self.starttime_w, 1, 0)
        self.scheduler_layout_2.addWidget(self.endtime_lbl, 2, 0)
        self.scheduler_layout_2.addWidget(self.endtime_w, 3, 0)
        self.scheduler_layout_2.addWidget(self.addrecord_btn, 4, 0)
        self.scheduler_layout_2.addWidget(self.delrecord_btn, 5, 0)
        self.scheduler_layout_2.addWidget(QtWidgets.QLabel(), 6, 0)
        self.scheduler_layout_2.addWidget(self.praction_lbl, 7, 0)
        self.scheduler_layout_2.addWidget(self.praction_choose, 8, 0)

        self.scheduler_layout_3 = QtWidgets.QGridLayout()
        self.scheduler_layout_3.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignHCenter | QtCore.Qt.AlignmentFlag.AlignTop
        )
        self.scheduler_layout_3.addWidget(self.statusrec_lbl, 0, 0)
        self.scheduler_layout_3.addWidget(self.plannedrec_lbl, 1, 0)
        self.scheduler_layout_3.addWidget(self.schedulers, 2, 0)

        self.scheduler_layout_4 = QtWidgets.QGridLayout()
        self.scheduler_layout_4.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignHCenter | QtCore.Qt.AlignmentFlag.AlignTop
        )
        self.scheduler_layout_4.addWidget(self.activerec_lbl, 0, 0)
        self.scheduler_layout_4.addWidget(self.activerec_list, 1, 0)

        self.scheduler_layout_main_w = QtWidgets.QWidget()
        self.scheduler_layout_main_w.setLayout(self.scheduler_layout)

        self.scheduler_layout_main_w2 = QtWidgets.QWidget()
        self.scheduler_layout_main_w2.setLayout(self.scheduler_layout_2)

        self.scheduler_layout_main_w3 = QtWidgets.QWidget()
        self.scheduler_layout_main_w3.setLayout(self.scheduler_layout_3)

        self.scheduler_layout_main_w4 = QtWidgets.QWidget()
        self.scheduler_layout_main_w4.setLayout(self.scheduler_layout_4)

        self.scheduler_layout_main1 = QtWidgets.QHBoxLayout()
        self.scheduler_layout_main1.addWidget(self.scheduler_layout_main_w)
        self.scheduler_layout_main1.addWidget(self.scheduler_layout_main_w2)
        self.scheduler_layout_main1.addWidget(self.scheduler_layout_main_w3)
        self.scheduler_layout_main1.addWidget(self.scheduler_layout_main_w4)
        self.scheduler_widget.setLayout(self.scheduler_layout_main1)

        self.warning_lbl = QtWidgets.QLabel(
            _("Recording of two channels simultaneously is not available!")
        )
        self.warning_lbl.setFont(self.font_11_bold)
        self.warning_lbl.setStyleSheet("color: red")
        self.warning_lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        self.scheduler_layout_main = QtWidgets.QVBoxLayout()
        self.scheduler_layout_main.addWidget(self.scheduler_widget)
        self.scheduler_widget_main = QtWidgets.QWidget()
        self.scheduler_widget_main.setLayout(self.scheduler_layout_main)

        self.scheduler_win.setCentralWidget(self.scheduler_widget_main)

    def create4(self, keyseq):
        self.shortcuts_label = QtWidgets.QLabel()
        self.shortcuts_label.setFont(self.font_bold)
        self.shortcuts_label.setText(_("Press the key combination\nyou want to assign"))

        self.keyseq_cancel = QtWidgets.QPushButton(_("Cancel"))
        self.keyseq_ok = QtWidgets.QPushButton(_("OK"))

        self.shortcuts_win_2_widget_2 = QtWidgets.QWidget()
        self.shortcuts_win_2_layout_2 = QtWidgets.QHBoxLayout()
        self.shortcuts_win_2_layout_2.addWidget(self.keyseq_cancel)
        self.shortcuts_win_2_layout_2.addWidget(self.keyseq_ok)
        self.shortcuts_win_2_widget_2.setLayout(self.shortcuts_win_2_layout_2)

        self.shortcuts_win_2_widget = QtWidgets.QWidget()
        self.shortcuts_win_2_layout = QtWidgets.QVBoxLayout()
        self.shortcuts_win_2_layout.addWidget(self.shortcuts_label)
        self.shortcuts_win_2_layout.addWidget(keyseq)
        self.shortcuts_win_2_layout.addWidget(self.shortcuts_win_2_widget_2)
        self.shortcuts_win_2_widget.setLayout(self.shortcuts_win_2_layout)

        self.shortcuts_win_2.setCentralWidget(self.shortcuts_win_2_widget)

        class StreamInfoWin(QtWidgets.QMainWindow):
            def showEvent(self, event):
                YukiData.streaminfo_win_visible = True
                super().showEvent(event)

            def hideEvent(self, event):
                YukiData.streaminfo_win_visible = False
                super().hideEvent(event)

        self.streaminfo_win = StreamInfoWin()
        self.streaminfo_win.setWindowTitle(_("Stream Information"))
        self.streaminfo_win.setWindowIcon(self.main_icon)
        self.streaminfo_win.setCentralWidget(self.streaminfo_widget)

        self.tvguidechannelfilter = QtWidgets.QLineEdit()
        self.tvguidechannelfilter.setPlaceholderText(_("Search channel"))
        self.tvguidechannelfiltersearch = QtWidgets.QPushButton()
        self.tvguidechannelfiltersearch.setToolTip(_("Search"))
        self.tvguidechannelfiltersearch.setIcon(
            QtGui.QIcon(str(YukiData.icons_folder / "search.png"))
        )

        self.tvguidechannelwidget = QtWidgets.QWidget()
        self.tvguidechannellayout = QtWidgets.QHBoxLayout()
        self.tvguidechannellayout.addWidget(self.tvguidechannelfilter)
        self.tvguidechannellayout.addWidget(self.tvguidechannelfiltersearch)
        self.tvguidechannelwidget.setLayout(self.tvguidechannellayout)

        self.showonlychplaylist_lbl = QtWidgets.QLabel()
        self.showonlychplaylist_lbl.setText(
            "{}:".format(_("Show only channels in playlist"))
        )
        self.showonlychplaylist_chk = QtWidgets.QCheckBox()
        self.showonlychplaylist_chk.setChecked(True)
        self.epg_win_checkbox = QtWidgets.QComboBox()

        self.epg_win_count = QtWidgets.QLabel()
        self.epg_win_count.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        self.epg_select_date = QtWidgets.QCalendarWidget()
        self.epg_select_date.setDateRange(
            QtCore.QDate().currentDate().addDays(-31),
            QtCore.QDate().currentDate().addDays(31),
        )
        self.epg_select_date.setMaximumWidth(300)

        self.epg_win_1_widget = QtWidgets.QWidget()
        self.epg_win_1_layout = QtWidgets.QHBoxLayout()
        self.epg_win_1_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        self.epg_win_1_layout.addWidget(self.showonlychplaylist_lbl)
        self.epg_win_1_layout.addWidget(self.showonlychplaylist_chk)
        self.epg_win_1_widget.setLayout(self.epg_win_1_layout)

        self.tvguide_lbl_2 = self.ScrollableLabel()

        self.epg_win_widget2 = QtWidgets.QWidget()
        self.epg_win_layout2 = QtWidgets.QHBoxLayout()
        self.epg_win_layout2.addWidget(self.epg_select_date)
        self.epg_win_layout2.addWidget(self.tvguide_lbl_2)
        self.epg_win_widget2.setLayout(self.epg_win_layout2)

        self.epg_win_widget = QtWidgets.QWidget()
        self.epg_win_layout = QtWidgets.QVBoxLayout()
        self.epg_win_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.epg_win_layout.addWidget(self.epg_win_1_widget)
        self.epg_win_layout.addWidget(self.tvguidechannelwidget)
        self.epg_win_layout.addWidget(self.epg_win_checkbox)
        self.epg_win_layout.addWidget(self.epg_win_count)
        self.epg_win_layout.addWidget(self.epg_win_widget2)
        self.epg_win_widget.setLayout(self.epg_win_layout)
        self.epg_win.setCentralWidget(self.epg_win_widget)

        self.epg_custom_name_input = QtWidgets.QLineEdit()
        self.epg_custom_name_input.setPlaceholderText(_("Search"))
        self.epg_custom_name_button = QtWidgets.QPushButton()
        self.epg_custom_name_button.setToolTip(_("Search"))
        self.epg_custom_name_button.setIcon(
            QtGui.QIcon(str(YukiData.icons_folder / "search.png"))
        )
        self.epg_custom_name_select = QtWidgets.QListWidget()
        self.epg_custom_name_select.setWordWrap(True)

        self.epg_custom_name_widget = QtWidgets.QWidget()
        self.epg_custom_name_widget_layout = QtWidgets.QHBoxLayout()
        self.epg_custom_name_widget_layout.addWidget(self.epg_custom_name_input)
        self.epg_custom_name_widget_layout.addWidget(self.epg_custom_name_button)
        self.epg_custom_name_widget.setLayout(self.epg_custom_name_widget_layout)

        self.epg_select_win_widget = QtWidgets.QWidget()
        self.epg_select_win_layout = QtWidgets.QVBoxLayout()
        self.epg_select_win_layout.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignHCenter | QtCore.Qt.AlignmentFlag.AlignTop
        )
        self.epg_select_win_layout.addWidget(self.epg_custom_name_widget, 0)
        self.epg_select_win_layout.addWidget(self.epg_custom_name_select, 1)
        self.epg_select_win_widget.setLayout(self.epg_select_win_layout)
        self.epg_select_win.setCentralWidget(self.epg_select_win_widget)

        self.ext_player_txt = QtWidgets.QLineEdit()
        self.ext_open_btn = QtWidgets.QPushButton()
        self.ext_open_btn.setText(_("Open"))
        self.ext_widget = QtWidgets.QWidget()
        self.ext_layout = QtWidgets.QGridLayout()
        self.ext_layout.addWidget(self.ext_player_txt, 0, 0)
        self.ext_layout.addWidget(self.ext_open_btn, 0, 1)
        self.ext_layout.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignHCenter | QtCore.Qt.AlignmentFlag.AlignTop
        )
        self.ext_widget.setLayout(self.ext_layout)
        self.ext_win.setCentralWidget(self.ext_widget)

    def create_sort_widgets(self):
        self.close_sort_btn = QtWidgets.QPushButton(_("Close"))
        self.close_sort_btn.clicked.connect(self.sort_win.hide)

        self.save_sort_btn = QtWidgets.QPushButton(_("Save"))
        self.save_sort_btn.setFont(self.font_bold)

        self.sort_label = QtWidgets.QLabel(
            _("Do not forget\nto set custom sort order in settings!")
        )
        self.sort_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        self.sort_widget3 = QtWidgets.QWidget()

        self.sort_widget4 = QtWidgets.QWidget()
        self.sort_widget4_layout = QtWidgets.QHBoxLayout()
        self.sort_widget4_layout.addWidget(self.save_sort_btn)
        self.sort_widget4_layout.addWidget(self.close_sort_btn)
        self.sort_widget4.setLayout(self.sort_widget4_layout)

        self.sort_widget_main = QtWidgets.QWidget()
        self.sort_layout = QtWidgets.QVBoxLayout()
        self.sort_layout.addWidget(self.sort_label)
        self.sort_layout.addWidget(self.sort_widget3)
        self.sort_layout.addWidget(self.sort_widget4)
        self.sort_layout.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignHCenter | QtCore.Qt.AlignmentFlag.AlignTop
        )
        self.sort_widget_main.setLayout(self.sort_layout)
        self.sort_win.setCentralWidget(self.sort_widget_main)

    def create_sort_widgets2(self):
        def sort_upbtn_clicked():
            curIndex = self.sort_list.currentRow()
            if curIndex != -1 and curIndex > 0:
                curItem = self.sort_list.takeItem(curIndex)
                self.sort_list.insertItem(curIndex - 1, curItem)
                self.sort_list.setCurrentRow(curIndex - 1)

        self.sort_upbtn = QtWidgets.QPushButton()
        self.sort_upbtn.setIcon(
            QtGui.QIcon(str(YukiData.icons_folder / "arrow-up.png"))
        )
        self.sort_upbtn.clicked.connect(sort_upbtn_clicked)

        def sort_downbtn_clicked():
            curIndex1 = self.sort_list.currentRow()
            if curIndex1 != -1 and curIndex1 < self.sort_list.count() - 1:
                curItem1 = self.sort_list.takeItem(curIndex1)
                self.sort_list.insertItem(curIndex1 + 1, curItem1)
                self.sort_list.setCurrentRow(curIndex1 + 1)

        self.sort_downbtn = QtWidgets.QPushButton()
        self.sort_downbtn.setIcon(
            QtGui.QIcon(str(YukiData.icons_folder / "arrow-down.png"))
        )
        self.sort_downbtn.clicked.connect(sort_downbtn_clicked)

        self.sort_widget2 = QtWidgets.QWidget()
        self.sort_layout2 = QtWidgets.QVBoxLayout()
        self.sort_layout2.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.sort_layout2.addWidget(self.sort_upbtn)
        self.sort_layout2.addWidget(self.sort_downbtn)
        self.sort_widget2.setLayout(self.sort_layout2)

        self.sort_list = QtWidgets.QListWidget()
        self.sort_list.setWordWrap(True)
        self.sort_layout3 = QtWidgets.QHBoxLayout()
        self.sort_layout3.addWidget(self.sort_list)
        self.sort_layout3.addWidget(self.sort_widget2)
        self.sort_widget3.setLayout(self.sort_layout3)

    def open_external_player(self):
        moveWindowToCenter(self.ext_win)
        self.ext_win.show()

    def showLoading2(self):
        if not self.loading2.isVisible():
            centerwidget(self.loading2, 50)
            self.loading_movie2.stop()
            self.loading_movie2.start()
            self.loading2.show()

    def hideLoading2(self):
        if self.loading2.isVisible():
            self.loading2.hide()
            self.loading_movie2.stop()

    def set_widget_opacity(self, widget, opacity):
        opacity_effect = QtWidgets.QGraphicsOpacityEffect(widget)
        opacity_effect.setOpacity(opacity)
        widget.setGraphicsEffect(opacity_effect)
        widget.setAutoFillBackground(True)

    def set_from_settings(self):
        self.m3u = YukiData.settings["m3u"]
        self.epg = YukiData.settings["epg"]
        self.udp_proxy_edit_main.setText(YukiData.settings["udp_proxy"])
        self.deinterlace.setChecked(YukiData.settings["deinterlace"])
        self.save_folder.setText(YukiData.settings["save_folder"])
        self.epg_offset.setValue(YukiData.settings["epgoffset"])
        self.cache_secs.setValue(YukiData.settings["cache_secs"])
        self.referer_choose.setText(YukiData.settings["referer"])
        self.useragent_choose_2.setText(YukiData.settings["ua"])
        self.mpv_options.setText(YukiData.settings["mpv_options"])
        self.donotupdateepg_flag.setChecked(YukiData.settings["donotupdateepg"])
        self.openprevchannel_flag.setChecked(YukiData.settings["openprevchannel"])
        self.hideepgpercentage_flag.setChecked(YukiData.settings["hideepgpercentage"])
        self.hideepgfromplaylist_flag.setChecked(
            YukiData.settings["hideepgfromplaylist"]
        )
        self.hidebitrateinfo_flag.setChecked(YukiData.settings["hidebitrateinfo"])
        self.volumechangestep_choose.setValue(YukiData.settings["volumechangestep"])
        self.panelposition_choose.setCurrentIndex(YukiData.settings["panelposition"])
        self.mouseswitchchannels_flag.setChecked(
            YukiData.settings["mouseswitchchannels"]
        )
        self.autoreconnection_flag.setChecked(YukiData.settings["autoreconnection"])
        self.lowlatency_flag.setChecked(YukiData.settings["lowlatency"])
        self.showplaylistmouse_flag.setChecked(YukiData.settings["showplaylistmouse"])
        self.showcontrolsmouse_flag.setChecked(YukiData.settings["showcontrolsmouse"])
        self.channellogos_select.setCurrentIndex(YukiData.settings["channellogos"])
        self.nocacheepg_flag.setChecked(YukiData.settings["nocacheepg"])
        self.scrrecnosubfolders_flag.setChecked(YukiData.settings["scrrecnosubfolders"])
        self.hidetvprogram_flag.setChecked(YukiData.settings["hidetvprogram"])
        self.sort_widget.setCurrentIndex(YukiData.settings["sort"])
        self.sort_categories_widget.setCurrentIndex(
            YukiData.settings["sort_categories"]
        )
        self.description_view_widget.setCurrentIndex(
            YukiData.settings["description_view"]
        )

        for videoaspect_var in self.videoaspect_vars:
            self.videoaspect_def_choose.addItem(videoaspect_var)

        for zoom_var in self.zoom_vars:
            self.zoom_def_choose.addItem(zoom_var)

        self.videoaspect_def_choose.setCurrentIndex(YukiData.settings["videoaspect"])
        self.zoom_def_choose.setCurrentIndex(YukiData.settings["zoom"])
        self.panscan_def_choose.setValue(YukiData.settings["panscan"])
        self.rewindenable_flag.setChecked(YukiData.settings["rewindenable"])
        self.hidechannellogos_flag.setChecked(YukiData.settings["hidechannellogos"])
        self.enabletransparency_flag.setChecked(YukiData.settings["enabletransparency"])
        self.hideplaylistbyleftmouseclick_flag.setChecked(
            YukiData.settings["hideplaylistbyleftmouseclick"]
        )

    def about_qt_show(self):
        QtWidgets.QMessageBox.aboutQt(self.helpwin_widget, _("About Qt"))
        self.help_win.raise_()
        self.help_win.setFocus(QtCore.Qt.FocusReason.PopupFocusReason)
        self.help_win.activateWindow()

    def epg_custom_name_input_edit(self):
        epg_custom_name_input_text = self.epg_custom_name_input.text().lower()
        for est_w in range(0, self.epg_custom_name_select.count()):
            if (
                self.epg_custom_name_select.item(est_w)
                .text()
                .lower()
                .startswith(epg_custom_name_input_text)
            ):
                self.epg_custom_name_select.item(est_w).setHidden(False)
            else:
                self.epg_custom_name_select.item(est_w).setHidden(True)

    def epg_custom_name_select_clicked(self, item1):
        self.epg_select_win.hide()
        if item1.text():
            self.epgname_lbl.setText(item1.text())
        else:
            self.epgname_lbl.setText(_("Default"))

    def show_settings(self):
        if not self.settings_win.isVisible():
            moveWindowToCenter(self.settings_win)
            self.settings_win.show()
        else:
            self.settings_win.hide()

    def show_progress(self, prog):
        if not YukiData.settings["hidetvprogram"] and (
            prog and not YukiData.playing_archive
        ):
            prog_percentage = round(
                (time.time() - prog["start"]) / (prog["stop"] - prog["start"]) * 100,
                2,
            )
            prog_title = prog["title"]
            prog_start = prog["start"]
            prog_stop = prog["stop"]
            prog_start_time = datetime.datetime.fromtimestamp(prog_start).strftime(
                "%H:%M"
            )
            prog_stop_time = datetime.datetime.fromtimestamp(prog_stop).strftime(
                "%H:%M"
            )
            self.progress.setValue(int(prog_percentage))
            self.progress.setFormat(str(prog_percentage) + "% " + prog_title)
            self.progress.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
            self.start_label.setText(prog_start_time)
            self.stop_label.setText(prog_stop_time)
            if not YukiData.fullscreen:
                self.progress.show()
                self.start_label.show()
                self.stop_label.show()
        else:
            self.progress.hide()
            self.start_label.setText("")
            self.start_label.hide()
            self.stop_label.setText("")
            self.stop_label.hide()


@idle_function
def set_record_icon(*args, **kwargs):
    YukiData.YukiGUI.btn_record.setIcon(YukiData.YukiGUI.record_icon)


@idle_function
def set_record_stop_icon(*args, **kwargs):
    YukiData.YukiGUI.btn_record.setIcon(YukiData.YukiGUI.record_stop_icon)


class ControlPanelDockWidget(QtWidgets.QDockWidget):
    def enterEvent(self, event):
        YukiData.check_controlpanel_visible = True
        super().enterEvent(event)

    def leaveEvent(self, event):
        YukiData.check_controlpanel_visible = False
        super().leaveEvent(event)


class SizeGrip(QtWidgets.QSizeGrip):
    def __init__(self, *args, **kwargs):
        super().__init__(YukiData.YukiGUI.playlist_widget)

    def mousePressEvent(self, event):
        YukiData.YukiGUI.playlistFullscreenIsResized = True
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, mouseEvent):
        YukiData.YukiGUI.playlistFullscreenIsResized = False
        super().mouseReleaseEvent(mouseEvent)
        YukiData.YukiGUI.fullscreenPlaylistWidth = (
            YukiData.YukiGUI.playlist_widget.width()
        )
        YukiData.YukiGUI.fullscreenPlaylistHeight = (
            YukiData.YukiGUI.playlist_widget.height()
        )
        YukiData.YukiGUI.save_fullscreenPlaylistWidth = (
            YukiData.YukiGUI.fullscreenPlaylistWidth
        )
        YukiData.YukiGUI.save_fullscreenPlaylistHeight = (
            YukiData.YukiGUI.fullscreenPlaylistHeight
        )


@idle_function
def thread_tvguide_update_start(*args, **kwargs):
    YukiData.state.setStaticYuki(True)
    YukiData.state.show()
    YukiData.static_text = _("Updating TV guide...")
    YukiData.state.setTextYuki("")
    YukiData.time_stop = time.time() + 3


@idle_function
def thread_tvguide_update_error(*args, **kwargs):
    YukiData.static_text = ""
    YukiData.state.setStaticYuki(False)
    YukiData.state.show()
    YukiData.state.setTextYuki(_("TV guide update error!"))
    YukiData.time_stop = time.time() + 3


@idle_function
def thread_tvguide_update_outdated(*args, **kwargs):
    YukiData.static_text = ""
    YukiData.state.setStaticYuki(False)
    YukiData.state.show()
    YukiData.state.setTextYuki(_("EPG is outdated!"))
    YukiData.time_stop = time.time() + 3


@idle_function
def thread_tvguide_update_end(*args, **kwargs):
    YukiData.static_text = ""
    YukiData.state.setStaticYuki(False)
    YukiData.state.show()
    YukiData.state.setTextYuki(_("TV guide update done!"))
    YukiData.time_stop = time.time() + 0.5


def destroy_listwidget_items(listwidget):
    try:
        for x in range(listwidget.count()):
            try:
                item = listwidget.item(x)
                if item:
                    itemWidget = listwidget.itemWidget(item)
                    if itemWidget:
                        itemWidget.destroy()
            except Exception:
                logger.warning(traceback.format_exc())
    except Exception:
        logger.warning(traceback.format_exc())


def centerwidget(wdg3, offset1=0):
    fg1 = YukiData.win.container.frameGeometry()
    xg1 = (fg1.width() - wdg3.width()) / 2
    yg1 = (fg1.height() - wdg3.height()) / 2
    wdg3.move(int(xg1), int(yg1) + int(offset1))


def tvguide_hide():
    if YukiData.tvguide_lbl.isVisible():
        YukiData.tvguide_lbl.setText("")
        YukiData.tvguide_lbl.hide()
        YukiData.tvguide_close_lbl.hide()


class TVguideCloseLabel(QtWidgets.QLabel):
    def mouseReleaseEvent(self, event):
        tvguide_hide()
        super().mouseReleaseEvent(event)


def win_show_raise():
    YukiData.win.show()
    YukiData.win.raise_()
    YukiData.win.setFocus(QtCore.Qt.FocusReason.PopupFocusReason)
    YukiData.win.activateWindow()
