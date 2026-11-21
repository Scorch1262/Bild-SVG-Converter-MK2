"""Erzeugt build/version_info.txt (Windows-Versionsangaben der exe) aus freisteller/version.py."""

from __future__ import annotations

import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))

from freisteller.version import APP_BESCHREIBUNG, APP_NAME, APP_VERSION  # noqa: E402

teile = [int(x) for x in (APP_VERSION.split(".") + ["0", "0", "0"])[:4]]
tupel = ", ".join(str(t) for t in teile)

inhalt = f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({tupel}),
    prodvers=({tupel}),
    mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable('040704B0', [
        StringStruct('CompanyName', 'Scorch1262'),
        StringStruct('FileDescription', '{APP_BESCHREIBUNG}'),
        StringStruct('FileVersion', '{APP_VERSION}'),
        StringStruct('InternalName', '{APP_NAME}'),
        StringStruct('OriginalFilename', '{APP_NAME}.exe'),
        StringStruct('ProductName', '{APP_NAME}'),
        StringStruct('ProductVersion', '{APP_VERSION}')
      ])
    ]),
    VarFileInfo([VarStruct('Translation', [0x0407, 1200])])
  ]
)
"""

ziel = WURZEL / "build" / "version_info.txt"
ziel.write_text(inhalt, encoding="utf-8")
print(f"{ziel} geschrieben ({APP_NAME} {APP_VERSION})")
