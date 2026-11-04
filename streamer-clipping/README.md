# Streamer-Clipping – Plan + automatisches Clip-Tool

Du schneidest Highlights aus Streams zu kurzen Hochformat-Clips, postest sie auf TikTok / YouTube Shorts und wirst **vom Streamer oder der Marke pro Aufruf bezahlt** (Clipping-Kampagnen, z. B. auf Whop).

| Datei | Inhalt |
|---|---|
| [01-plan.md](01-plan.md) | Wie Clipping-Kampagnen funktionieren, Kampagnen finden, Tagesroutine, Rechnung |
| [02-hooks-und-clip-regeln.md](02-hooks-und-clip-regeln.md) | Was einen Clip viral macht + 20 Hook-Vorlagen |
| [clipper/](clipper/) | Das Tool, das Streams automatisch analysiert und Clips schneidet |
| [../.github/workflows/clipper.yml](../.github/workflows/clipper.yml) | Startet das Tool in der Cloud (GitHub), auch vom iPad aus |

## Was automatisch läuft – und was du machst

| Schritt | Wer |
|---|---|
| Stream-VOD laden, Lautstärke + Chat analysieren | 🤖 Tool |
| Beste Momente finden, transkribieren | 🤖 Tool |
| Clips auswählen, Titel + Hook + Caption schreiben | 🤖 Tool (mit Claude, wenn API-Key hinterlegt) |
| 9:16 schneiden, Untertitel, Hook-Text, Lautstärke angleichen | 🤖 Tool |
| Clips ansehen, schlechte aussortieren | 👤 du (5 Min.) |
| In TikTok Studio / YouTube Studio planen | 👤 du (10 Min.) |
| Links bei der Kampagne einreichen | 👤 du (5 Min.) |

**Posten wird absichtlich nicht automatisiert:** Inoffizielle Upload-Bots verstoßen gegen die Regeln von TikTok und führen zu Sperren – dann ist das Geld weg.

---

## Tool vom iPad aus starten (GitHub Actions)

Einmalig:
1. Auf github.com dieses Repository öffnen → **Settings → Secrets and variables → Actions → New repository secret**
   - Name: `ANTHROPIC_API_KEY`, Wert: dein API-Key von console.anthropic.com
   - *Optional.* Ohne Key funktioniert alles, nur Auswahl und Titel sind dann einfacher. Kosten mit Key: wenige Cent pro Stream.
2. Diesen Branch in den Standard-Branch des Repositories übernehmen (Pull Request mergen) – GitHub zeigt manuelle Workflows erst an, wenn die Workflow-Datei im Standard-Branch liegt. Danach kannst du beim Starten trotzdem jeden Branch auswählen.

Jedes Mal:
1. Repository → **Actions → Stream-Clipper → Run workflow**
2. VOD-Link einfügen, Anzahl Clips wählen → **Run**
3. Warten (ca. 10–40 Min., je nach Stream-Länge)
4. Auf den fertigen Lauf tippen → unten bei **Artifacts** → `clips` herunterladen (ZIP mit MP4 + Texten)

**Hinweise**
- Private Repositories haben bei GitHub ein kostenloses Kontingent an Actions-Minuten pro Monat; ein 3-Stunden-Stream braucht grob 20–60 Minuten.
- Twitch-VODs funktionieren in der Regel gut. **YouTube blockiert Downloads von Cloud-Servern oft** („Sign in to confirm you're not a bot") – dann das Tool auf einem eigenen PC/Mac laufen lassen.
- Twitch löscht VODs nach einiger Zeit (je nach Kanal 7–60 Tage) – zeitnah clippen.

## Tool auf einem PC/Mac starten

```bash
# einmalig: Python 3.10+ und ffmpeg installieren, dann:
pip install -r streamer-clipping/clipper/requirements.txt

# Clips erstellen
python streamer-clipping/clipper/clipper.py --url "https://www.twitch.tv/videos/123456789" --clips 6

# Mit Facecam oben + Gameplay unten (Bereich der Facecam im Original-Video: x:y:breite:höhe)
python streamer-clipping/clipper/clipper.py --url "..." --layout facecam --cam 1500:780:420:300

# Lokale Datei statt Link
python streamer-clipping/clipper/clipper.py --file stream.mp4 --clips 4
```

Optional vorher: `export ANTHROPIC_API_KEY=...` für KI-Auswahl und bessere Titel.

| Option | Bedeutung | Standard |
|---|---|---|
| `--clips` | Anzahl fertiger Clips | 6 |
| `--length` | Länge der Kandidaten in Sekunden (die KI kürzt passend) | 45 |
| `--layout` | `blur` (ganzes Bild, unscharfer Hintergrund) oder `facecam` (Cam oben, Spiel unten) | blur |
| `--lang` | Sprache für Untertitel (`de`, `en`, `auto`) | de |
| `--whisper` | Genauigkeit der Untertitel: `tiny`, `base`, `small`, `medium` | small |
| `--no-chat` / `--no-ai` / `--no-transcribe` | Teile abschalten | – |
| `--chat-delay` | Wie viele Sekunden der Chat hinterherhinkt | 5 |

Ausgabe im Ordner `clips/`: `clip_01.mp4`, `clip_01.txt` (Titel, Caption, Hashtags, Zeitstempel), `clips.json`.

## So findet das Tool Highlights

1. **Lautstärke:** Schreien, Lachen, laute Spielmomente → Ausschläge im Pegel.
2. **Chat:** Plötzlich viele Nachrichten und Emotes wie `KEKW`, `LUL`, `W`, `💀`, `Clip it` → etwas ist passiert. Der Chat reagiert ein paar Sekunden später, das wird ausgeglichen.
3. **Score:** beides kombiniert, die stärksten Momente mit Abstand zueinander werden Kandidaten.
4. **KI-Auswahl:** Claude liest die Transkripte der doppelten Anzahl Kandidaten, wählt die besten, schneidet Anfang/Ende genauer zu und schreibt Titel, Hook und Caption. Clips, die ohne Kontext unverständlich sind oder den Streamer bloßstellen, werden aussortiert.
