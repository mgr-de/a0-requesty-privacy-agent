# Developer ohne Maskierung – verbindlicher Umsetzungsplan

Überarbeitung vom 13. Oktober 2026 auf Grundlage des vorgelegten Konzepts.

Die optimierte spaCy-/Regex-Erkennung bleibt der einzige Standard. Eine ausdrücklich freigegebene Ausnahme gilt ausschließlich für neu über eine eigene Aktion angelegte Developer-Hauptchats. Secrets, Requesty-Routenregeln und lokale Embeddings bleiben verpflichtend. Code-Erkennung begründet keine Freigabe.

## Präzisierungen aus dem Review

1. Agent Zero besitzt aktuell keine getrennte Administratorrolle. Freigabe, Widerruf und Profilanlage verlangen deshalb eine konfigurierte Oberfläche-Anmeldung und deren authentifizierte Sitzung zusätzlich zu den vorhandenen CSRF-Prüfungen. Ohne Anmeldung bleiben diese Aktionen gesperrt. Die Testinstanz besitzt derzeit keine Anmeldung; Installation und simulierte Tests erfolgen geschützt.
2. Eine Profil-ID allein genügt nicht: die Freigabe bindet Profil-ID, tatsächlichen Definitionspfad, Profilgeneration und Definitionsidentität. Projektüberschreibungen, Löschung oder Neuanlage dürfen die Ausnahme nicht erben. Eine neue Freigabe hat eine neue Identität und reaktiviert keine alten Chats. Lokale Audit-Metadaten sind keine manipulationssichere Revisionshistorie gegenüber Host-Administratoren.
3. „Neuer Developer-Chat“ erzeugt einen neuen Hauptchat, setzt sein Profil und bindet die gültige Freigabe, bevor Nachrichten verarbeitet werden. Ein eigener serverseitiger Datensatz ist Voraussetzung; importierte Chat-Metadaten verleihen keine Berechtigung. Geschützte Alt-Chats bleiben bei Profilwechsel maskiert. Ein freigegebener Chat kann nicht als geschützter Chat weitergeführt werden: Profil-/Projektwechsel sperrt weitere Modellaufrufe und verlangt einen neuen Chat.
4. Jeder Provider-Versuch erhält unmittelbar an der kontrollierten Übergabe an LiteLLM eine neue Transportzulassung, nach Wartezeiten und auch bei Framework-Fallbacks. Interne Provider-Wiederholungen werden für unmaskierte Aufrufe deaktiviert. Die Zulassung ist der definierte Startzeitpunkt; ein danach widerrufener, bereits zugelassener Aufruf darf abschließen. Physische Netzwerkpakete lassen sich nicht rückwirkend zurückholen.
5. Widerruf sperrt weitere Modellaufrufe des betroffenen Developer-Chats. Es gibt keinen stillen Wechsel von Speicher oder Maskierungsmodus. Bereits zugelassene Antworten behalten ihren ursprünglichen PII-Modus und werden weiterhin auf Secrets geprüft.
6. Alt-Chats ohne neue Policy bleiben mit bestehender Mapping-Identität maskiert. Bestehende Speicherordner und SQLite-Zuordnungen werden nicht migriert. Developer-Speicher verwendet eine eigene Identität aus Projekt, freigegebener Profilgeneration und Modus; historische Tokens werden nicht rückübersetzt.

## Umsetzung und Abnahme

Separate Feature-Branches und PRs in den drei Repositories. Der Manager erhält Freigaberegister, Profil-/Chatanlage und Verwaltung. Local Privacy Guard erhält Secret-only-Verarbeitung, vollständige Trennung der Rückübersetzung und Speicher sowie die Transportprüfung. Requesty behält seine Routen und ergänzt nur die eindeutige Statusbeschreibung.

Tests mit ausschließlich synthetischen Daten: Authentifizierung/CSRF, Doppelanlage, Profilüberschreibung/-löschung, Widerruf und erneute Freigabe, manipulierte/importierte Chatdaten, Hauptchat-/Unteragenten-Vererbung, Alt-Chats, getrennte Memory-Identität, Eingangs-/Antwort-/Tool-/Streaming-Secrets sowie Widerruf während einer Transportwartezeit und zwischen Wiederholungen. Vorhandene Python-/Node-Prüfungen werden ausgeführt.

Die native Testinstanz wird erst nach bestandenen Prüfungen aktualisiert. Bestehende Schlüssel, Presets und Zuordnungen werden vor und nach dem Update verglichen. Keine kostenpflichtigen Requesty-Aufrufe. Ohne eingerichtete Anmeldung wird keine Ausnahme in der laufenden Instanz aktiviert. Nach Einrichtung der Anmeldung kann der Betreiber Profil und Ausnahme ausdrücklich freigeben und einen neuen Developer-Chat starten.

## Grenzen

Alle personenbezogenen Texte eines freigegebenen Modellkontexts können den zulässigen Anbieter unmaskiert erreichen. Secret-Erkennung erfasst nicht jedes unbekannte Geheimnis. Bilder, Browser, rohe Werkzeug-Netzwerkzugriffe und Host-Administratoren behalten ihre bisherigen Grenzen. Die neue Ausnahme ist keine vollständige Datenschutz- oder Rechtssicherheitsgarantie.
