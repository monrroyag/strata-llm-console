# Strata LLM Console — Deutsch

[English](README.en.md) · [Español](README.es.md) · [Português](README.pt.md) · [Français](README.fr.md) · [Deutsch](README.de.md)

Englisch ist die Standardsprache und Referenzdokumentation von Strata LLM Console. Die Sprache kann im Kopfbereich oder unter Einstellungen geändert werden.

## Herkunft der Engine

Diese Konsole ist eine Betriebsschicht für die [offizielle Strata-Inferenz-Engine](https://github.com/Niko1221/Strata). Das Ursprungsrepository ist `https://github.com/Niko1221/Strata.git`. Die Konsole verwaltet Katalog, Parameter, Lebenszyklus, Netzwerkfreigabe, Beobachtung und Updates.

## Hauptbereiche

- **Bedienen** — Modelle registrieren, auswählen, laden, entladen, stoppen und aus dem Katalog entfernen; Parameter ändern; Speicher und Kontext analysieren.
- **Beobachten** — VRAM/RAM, historische Leistung, Traces, von der Engine ausgegebenes Reasoning, Tools, Token, Latenz und Fehler prüfen.
- **Verbinden** — API lokal halten, LAN ausdrücklich aktivieren, Bearer/CORS konfigurieren und einen verschlüsselten Tunnel verwenden.
- **System** — Strata-Version prüfen, Updates suchen, Backends erkennen und die Oberfläche anpassen.

## API

- OpenAI-Gateway: `http://127.0.0.1:8090/v1`
- Steuerungs-API: `http://127.0.0.1:8090/api`
- Der Fernzugriff erfordert `Authorization: Bearer <console-token>`.
- Standardmäßig wird nur Loopback verwendet; LAN und CORS sind optional.

## Optimierer

Er kombiniert echten GPU/RAM-Speicher, gewünschten Kontext, KV-Quantisierung, Experten-Cache, MTP/Lookup-Einstellungen, aktuelle Konfiguration, Verlauf und Risikoreserven. Er liefert Empfehlung, Alternativen und Vertrauensniveau. Statische Analyse wird klar gekennzeichnet und nicht als Benchmark ausgegeben.

## Telegram

Der Bot mit Allowlist steuert Status, Modellauswahl, Stoppen, Entladen, Bestätigungen, Traces, Fehler, Optimierung, Verbindung und Strata-Updates. Neue Chats beginnen auf Englisch und können eine andere Sprache auswählen.

## Screenshots

![Gruppierte Navigation](../screenshots/models-grouped-en-final2.png)
![Leistung](../screenshots/performance.png)
![Traces](../screenshots/traces-errors.png)
![Verbindung](../screenshots/connection-final.png)
![Einstellungen](../screenshots/preferences-latest.png)
![Parameter](../screenshots/parameters.png)
![Optimierer](../screenshots/optimizer-analysis.png)
![Updates](../screenshots/update.png)
![Tunnel](../screenshots/tunnel.png)
![Modellregistrierung](../screenshots/add.png)
![Aktivität](../screenshots/activity.png)

## Sicherheit des Repositorys

Tokens, Umgebungsdateien, Traces, Logs, GGUF, Packs, Binärdateien und computerspezifische Pfade bleiben außerhalb von Git. Das Entfernen eines Katalogeintrags löscht niemals die ursprünglichen Modelldateien.