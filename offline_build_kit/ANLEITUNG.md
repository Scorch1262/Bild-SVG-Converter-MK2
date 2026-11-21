# Bild-SVG Converter MK2 — Windows-exe bauen: Mac lädt, Win10 baut

**Offline-Build-Kit v1.0.0**

Drei Skripte, drei Schritte. Python 3.11 (64-Bit) ist auf dem
Windows-10-PC bereits installiert — dieses Kit kümmert sich um die
Pakete, das KI-Modell und den eigentlichen exe-Build. Der Windows-PC
braucht **keine Internetverbindung**. Das Ergebnis ist dieselbe exe,
die sonst GitHub Actions baut:
`Bild-SVG-Converter-MK2-v<Version>-windows.exe`.

```
offline_build_kit/
├── 1_mac_pakete_herunterladen.sh      <- läuft auf dem Mac (mit Internet)
├── 2_win10_pakete_installieren.bat    <- läuft auf dem Win10-PC
├── 3_win10_exe_aus_zip_bauen.bat      <- läuft auf dem Win10-PC
└── ANLEITUNG.md                       <- diese Datei
```

Das Kit liegt im Repo im Ordner `offline_build_kit/`. Es funktioniert
auf zwei Arten:

| Art | Was auf den Win10-PC kommt |
|---|---|
| **A – im Projektordner** | der komplette Projektordner (Repo-Klon oder entpackte Projekt-ZIP), das Kit liegt darin unter `offline_build_kit\` |
| **B – Kit einzeln** | nur der Kit-Ordner, dazu die Projekt-`.zip` daneben |

---

## Schritt 1 — auf dem Mac

1. **Art A:** Projekt klonen bzw. die Projekt-ZIP entpacken und im
   Terminal in den Kit-Ordner wechseln:
   ```bash
   cd ~/Desktop/Bild-SVG-Converter-MK2/offline_build_kit
   ```
   **Art B:** den Ordner `offline_build_kit` irgendwohin kopieren und
   die Projekt-`.zip` (z. B. „Download ZIP" von GitHub) hineinlegen.
2. Skript ausführbar machen und starten:
   ```bash
   chmod +x 1_mac_pakete_herunterladen.sh
   ./1_mac_pakete_herunterladen.sh
   ```
3. Es entstehen
   - der Ordner **`offline_pakete`** mit
     - den `.whl`-Dateien für `PySide6-Essentials`, `onnxruntime`,
       `numpy`, `scipy`, `Pillow`, `vtracer`, `pyinstaller` und deren
       Abhängigkeiten — passend für **Windows 64-Bit / Python 3.11**,
       egal welches Python auf dem Mac läuft (auf dem Mac wird nichts
       installiert),
     - `modell/isnet-general-use.onnx` — das KI-Modell (ca. 178 MB),
       Prüfsumme wird beim Laden kontrolliert,
     - `extras/vc_redist.x64.exe` — Microsoft Visual C++ Laufzeit, nur
       nötig, falls onnxruntime auf dem PC nicht startet,
     - `SHA256SUMS.txt` — Prüfsummen aller Dateien,
   - die Datei **`paketliste.txt`**.

   > Die Paketliste kommt aus dem Projekt selbst: `requirements.txt`
   > und `build/requirements-build.txt` (PyInstaller-Version), dazu
   > Adresse und Prüfsumme des Modells aus `build/modell_laden.py`.
   > Damit baut das Kit mit denselben Versionen wie GitHub Actions.

   Insgesamt etwa 350 MB.

**Danach auf den Windows-10-PC kopieren** (USB-Stick, Kabel — egal wie):
- **Art A:** den kompletten Projektordner.
- **Art B:** den kompletten Kit-Ordner (inkl. `offline_pakete` und
  `paketliste.txt`) mit der Projekt-`.zip` darin.

---

## Schritt 2 — auf dem Windows-10-PC: Pakete installieren

1. Doppelklick auf **`2_win10_pakete_installieren.bat`**.
2. Das Skript
   - sucht ein passendes Python 3.11 (64-Bit): erst `python`, sonst
     den Python-Launcher `py -3.11`,
   - prüft per SHA256, dass beim Kopieren keine Datei (auch nicht das
     KI-Modell) beschädigt wurde,
   - legt die virtuelle Umgebung `venv` an und installiert alle Pakete
     **ausschließlich** aus `offline_pakete` (`--no-index`, kein
     Internet),
   - prüft, ob sich alle Pakete laden lassen.
3. Am Ende erscheint `FERTIG.`.

---

## Schritt 3 — auf dem Windows-10-PC: exe bauen

1. **Art A:** nichts weiter nötig — es darf aber **keine** `.zip` im
   Kit-Ordner liegen, sonst wird die `.zip` gebaut.
   **Art B:** die Projekt-`.zip` liegt im Kit-Ordner (nicht von Hand
   entpacken). Es darf nur **eine** `.zip` im Ordner liegen.
2. Doppelklick auf **`3_win10_exe_aus_zip_bauen.bat`**.
3. Das Skript
   - entpackt bei Art B die `.zip` nach `projekt`,
   - sucht `freisteller\version.py` des Bild-SVG Converter MK2
     (egal in welchem Unterordner) und liest daraus `APP_VERSION`,
   - legt das KI-Modell nach `modelle\` und erzeugt die
     Windows-Versionsangaben,
   - baut mit PyInstaller und `build\build.spec` genau wie der
     GitHub-Workflow eine **einzelne exe** mit eingebautem KI-Modell
     und Programmsymbol,
   - startet die fertige exe mit `--selftest` und bricht ab, wenn der
     Test fehlschlägt.
4. Ergebnis liegt in **`fertige_exe`**:
   ```
   fertige_exe/
   └── Bild-SVG-Converter-MK2-v2.0.0-windows.exe
   ```
   Der Build dauert einige Minuten.

**Neue Projektversion später bauen:** Art A: neuen Projektstand in den
Ordner kopieren, Art B: neue `.zip` gegen die alte austauschen — dann
`3_win10_exe_aus_zip_bauen.bat` erneut starten. Schritt 1/2 müssen
nicht wiederholt werden, solange sich `requirements.txt` und
`build/requirements-build.txt` nicht ändern.

---

## exe benutzen

1. Die exe in einen **eigenen Ordner** legen (z. B.
   `C:\Programme_eigene\Bild-SVG-Converter\`) und starten.
2. Daneben entsteht `Bild-SVG-Converter-MK2.ini` mit den Einstellungen.
3. Der Start dauert einige Sekunden, weil die exe sich (inkl. KI-Modell)
   entpackt. Das Programm arbeitet komplett offline.

---

## Fehlerbehebung

- **„Kein passendes Python 3.11 (64-Bit) gefunden"** (Schritt 2) →
  `python --version` bzw. `py --list` prüfen. Die Pakete aus Schritt 1
  passen nur zu 3.11 / 64-Bit. Ein anderes Python (3.12)? Dann im
  Mac-Skript oben `PY_VER="3.11"` anpassen und Schritt 1 wiederholen.
- **„DEFEKT"/„FEHLT" bei der Prüfung** → Kopiervorgang unvollständig;
  `offline_pakete` erneut auf den PC kopieren.
- **„onnxruntime lässt sich nicht laden"** → die Microsoft Visual C++
  Laufzeit fehlt: `offline_pakete\extras\vc_redist.x64.exe`
  installieren, dann Schritt 2 erneut starten.
- **„venv mit PyInstaller wurde nicht gefunden"** (Schritt 3) → erst
  Schritt 2 erfolgreich durchlaufen lassen, im selben Ordner.
- **„mehrere .zip-Dateien"** → nur eine `.zip` neben die Skripte legen
  (das Kit selbst vorher entpacken, dessen ZIP nicht danebenlegen).
- **„kein Bild-SVG Converter MK2 gefunden"** → falsches Archiv; das
  Skript zeigt den gefundenen Inhalt an.
- **Selbsttest schlägt fehl** → das Protokoll wird direkt darüber
  angezeigt; die Zeile mit `[FEHLER]` nennt den Teil, der nicht geht.
- **Windows Defender meldet die neue exe** → normal bei frisch
  gebauten, unsignierten PyInstaller-exe-Dateien: „Trotzdem ausführen"
  bzw. Ausnahme eintragen.

## Was dieses Kit nicht baut

- Keine Mac-App — das Projekt baut nur eine Windows-exe.
