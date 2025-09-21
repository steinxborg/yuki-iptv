#!/usr/bin/env python3
"""Generate desktop file for yuki-iptv"""
import glob
import gettext
import os

os.system("make")

PREFIX = """[Desktop Entry]
Type=Application
Name=yuki-iptv
Comment=IPTV player with EPG support
"""

SUFFIX = """Exec=yuki-iptv
Icon=yuki-iptv
Categories=AudioVideo;Video;Player;Recorder;TV;
Keywords=Television;Stream;
"""

FILE = open("./usr/share/applications/yuki-iptv.desktop", "w", encoding="utf8")
FILE.write(PREFIX)

for lang_file in glob.glob("./po/yuki-iptv-*.po"):
    lang = lang_file.replace(".po", "").split("yuki-iptv-")[1]
    try:
        translation = gettext.translation(
            "yuki-iptv", "./usr/share/locale/", languages=[lang]
        )
        playername = translation.gettext("IPTV player with EPG support")
        if playername != "IPTV player with EPG support":
            if "_" in lang and lang.split("_")[0] == lang.split("_")[1].lower():
                lang = lang.split("_")[0]
            FILE.write(f"Comment[{lang}]={playername}\n")
    except Exception:
        print(f"Failed for language {lang}")

FILE.write(SUFFIX)
FILE.close()
