<p align="center"><img src="webui/thumbnail.svg" width="128" alt="Requesty Privacy Agent"></p>

# Requesty Privacy Agent für Agent Zero 2.13

Ein gemeinsamer Einstieg für EU-Privatanwender: Requesty-Routen, lokale Textmaskierung und lokale Embeddings einmal einrichten und als Mindestregeln für **alle Profile dieser Installation** verwenden. Version 0.2 verwendet native A0-Presets und ist keine vollständige Sicherheits-Sandbox.

Die bestehenden [Requesty](https://github.com/mgr-de/a0-requesty-privacy-guard) und [Local Privacy Guard](https://github.com/mgr-de/a0-local-privacy-guard) Plugins bleiben erhalten und einzeln nutzbar. Dieser Manager verwendet ihre Filter und Modellprüfung, statt sie zu kopieren.

## Einrichtung

1. ZIP über den nativen Agent-Zero-Installer installieren, Config öffnen. Installation allein aktiviert noch keine gemeinsame Policy.
2. Fehlende Komponenten installieren: fest gepinnte veröffentlichte ZIPs werden vor dem nativen Installer per SHA-256 geprüft. Vorhandene kompatible Plugins bleiben erhalten; ältere Versionen bewusst über die native Plugin-Verwaltung aktualisieren. Agent Zero neu starten.
3. Einen gemeinsamen Requesty-Schlüssel speichern. Optional die Requesty-Kontoeinstellungen in Requesty setzen und als **vom Nutzer bestätigt** vermerken. Das ist keine technische Kontoverifikation.
4. Die Umstellung von Default, Efficiency und Power ansehen, Modelle und Kosten prüfen und ausdrücklich übernehmen. Vorbelegungen starten keine Modellaufrufe; fehlende Modelle verlangen eine Ersatzwahl. Eine bisherige gemeinsame Auswahl kann als eigenes natives Preset erhalten bleiben. Gegebenenfalls lokale Erkennungsmodelle und Embedding-Gewichte vorbereiten; hierbei werden Pakete heruntergeladen, keine Chatdaten übertragen. Kein lokaler Chat-LLM ist erforderlich.
5. Nach geprüfter Migration **„Diese Installation schützen“** ausdrücklich bestätigen. Die Aktion betrifft alle bestehenden und neuen Profile; andere Installationen bleiben unverändert. Anschließend Modelle über den normalen A0-Preset-Editor bearbeiten, ohne den Schutz abzuschalten.

Die nummerierten Aktionen speichern und prüfen die Einrichtung. Der allgemeine native Save-Knopf aktiviert den Schutz nicht.

## Verhalten

- Gemeinsame Vorgaben: EU-Requesty und EU-Modellstandort, keine Anbieter-Speicherung und kein Training laut Katalog, lokale Textfilter sowie lokale sentence-transformers-Embeddings.
- Eigene aktive Profilsetups und eigene Schlüssel bleiben verwendbar. Ohne eigenen Schlüssel kann die gemeinsame Basis genutzt werden. Strengere Profilregeln gelten auch bei geerbten Modellen. Schwächere Einstellungen und profilbezogene Plugin-Schalter können die Mindestregeln nicht verlassen.
- Presets bleiben auswählbar, sofern ihre tatsächlichen Modelle und Transportparameter zulässig sind. Ablehnung erfolgt verständlich; es gibt keinen stillen Ersatz durch ein anderes Modell.
- Native Unteragenten, unabhängig gestartete Chats und Hintergrundaufrufe unterliegen denselben Mindestregeln. Externe Aufrufe ohne zuordenbaren geschützten Besitzer stoppen.
- Chat-Zuordnungen bleiben beim Profilwechsel stabil. Originalnamen bleiben in der lokalen Anzeige lesbar, Modellhistorie und Denktext behalten Platzhalter.
- Fehlende erforderliche Komponenten stoppen externe Aufrufe. Deaktivierung erfolgt zentral und bewusst; vorhandene Profile, Schlüssel und Presets werden nicht gelöscht oder umgeschrieben.

## Requesty zusätzlich absichern

Empfohlen: **Serving region EU only**, **Requesty Zero data retention**, **Zero-data-retention models only**, geprüfte **EU Approved Models**. Gateway-Region, Requesty-Speicherung und Anbieter-Speicherung sind getrennte Kontrollen. Metadaten bleiben erhalten, und Kontoregeln gelten auch für andere Anwendungen. Gesperrte Regeln können Support erfordern. [Anleitung mit Screenshot](https://github.com/mgr-de/a0-requesty-privacy-guard/blob/ux/private-user-setup/docs/REQUESTY-ACCOUNT-SETTINGS.md).

## Schutzgrenzen

Erkennung reduziert Risiken und garantiert keine vollständige Anonymisierung. Katalogangaben werden nicht unabhängig auditiert. Bilder werden beim ausgewählten Dienst verarbeitet; Textmaskierung schützt ihren Bildinhalt nicht. Webseiten, Formulare, Uploads und andere Werkzeugübertragungen werden nicht vollständig überwacht. Native Browser- und Dateifunktionen bleiben bedienbar.

Der Agent kann über Code-Ausführung oder fremde Clients außerhalb dieser Modellintegration arbeiten. Ein Plugin ist keine Sicherheitsgrenze gegen Administratoren, Schreibzugriffe auf Schutzdateien oder absichtliches Umgehen der Adapter. Für solche Grenzen braucht es eine separate gehärtete Instanz mit kontrolliertem Netzwerk.

## Technische Schnittstellen und Daten

`helpers.manager` stellt effektive Mindestpolicy, gemeinsame Modelle, Komponentenprüfung und Status bereit. Die aktivierte Basis liegt außerhalb der Plugin-ZIPs unter `usr/privacy-agent/`; Konfiguration und Schlüssel werden atomar mit eingeschränkten Dateirechten gespeichert, aber nicht verschlüsselt. Die PII-Zuordnungen bleiben bei Local Privacy Guard unter `usr/privacy-mappings`.

`POST /api/plugins/requesty_privacy_agent/setup` unterstützt `status`, `install_dependencies`, `key`, `account`, `catalog`, `prepare_local`, `configure`, `activate` und `deactivate`. Native Authentifizierung und CSRF gelten. API-Antworten geben keine Schlüsselwerte zurück. Die bestätigte Aktivierung ist die letzte Aktion; Fehler aktivieren keine teilweise eingerichtete Basis.

Eigene native Adapter erhalten die Regeln unabhängig von Profilschaltern. Ein reversibler Laufzeit-Guard schützt zusätzlich alte LangChain-Objekte ohne gemeinsame native Hooks. Filter- und Routingimplementierung verbleiben in den beiden Komponenten. Unbekannte oder veränderte fremde Adapterdateien werden erhalten und führen beim erforderlichen Schutzpfad zu einem Fehler.

## Tests

Die Python-Integrationstests laufen innerhalb Agent Zero 2.13 mit simulierten Modelltransporten: `python -m pytest usr/plugins/requesty_privacy_agent/tests`. Ohne Agent Zero werden diese Integrationstests ausdrücklich übersprungen. Frontend: `node --test tests/*.mjs`. Komponenten in getrennten Pytest-Läufen prüfen, da ältere Tests gleiche Modulnamen verwenden.

Der lokale Sprachkorpus der Filterkomponente umfasst 40 und 100 Nachrichten mit vier Personen in DE/EN/FR/ES/IT/NL/PL und gemischten Sitzungen. Er prüft bekannte synthetische Werte, Identitätskontinuität und Rückübersetzung. Freie Modellantworten und reale Erkennungsraten sind gesondert zu bewerten. Es wurden keine weiteren kostenpflichtigen Modellantworten für diese Einführung angefordert; vorhandene Budgetreservierungen bleiben erhalten.

[Einführung, Tests und Grenzen](docs/IMPLEMENTATION-RESULTS.md) · [Gehärteter Ausblick](docs/INSTANCE-PRIVACY-PLAN.md) · [MIT-Lizenz](LICENSE)


## Kurze Modellnamen und Routing-Policies

Die Auswahl zeigt zunächst kurze Requesty Managed Policies, sofern passende vorhanden sind. Anbieterspezifische IDs bleiben über den Schalter verfügbar; gespeicherte spezifische Auswahlen bleiben sichtbar. Namen werden unverändert gesendet, niemals durch Abschneiden eines Anbieterpräfixes erzeugt.

Der authentifizierte `/v1/models`-Katalog muss zuerst erfolgreich geladen werden. Der ergänzende öffentliche `/v1/models/managed`-Katalog enthält die dokumentierten aggregierten Datenschutz- und Fähigkeitsangaben der Managed Policies; diese werden gegen dieselben Mindestregeln geprüft. Er ist nicht auf den API-Schlüssel begrenzt: Requesty kann einen angezeigten Namen zusätzlich durch Schlüssel-/Kontoregeln ablehnen. Bei eigenen namensgleichen Policies werden öffentliche Angaben nicht als Nachweis verwendet. Eigene `policy/<name>`-Ziele sind derzeit nicht unabhängig prüfbar und bleiben gesperrt. Fehlende oder globale Standortangaben reichen nicht für EU-Schutz.

[Managed Policies](https://docs.requesty.ai/features/managed-policies), [Managed-Katalog](https://docs.requesty.ai/api-reference/endpoint/models-managed-list). Requesty kann Managed Policies ändern; die Prüfung verwendet aktuelle Katalogangaben mit höchstens 60 Sekunden Cache. Sie bestätigt Anbieterangaben, keine unabhängig auditierte Ausführung.


## Privacy-Auswahl im Chat und Profil-Editor

Nach der Migration zeigen Chat-Menü, Profil-Editor und Preset-Editor dieselben nativen Presets. Der frühere zusätzliche Menüeintrag „Privacy Agent · gemeinsam“ entfällt. Die native Auswahl für Chat, Profil, Projekt und globale Vorgabe bestimmt die tatsächlich verwendeten Modelle; unzulässige Presets bleiben gesperrt. Noch nicht migrierte ältere Einrichtungen behalten ihren bisherigen Menüeintrag bis zur ausdrücklichen Umstellung.

Der native Profil-Editor verwendet Lesekontexte ohne Chat-ID. Diese erhalten ihre eigene Profilkonfiguration, ohne Parent-Chat-Suche, Rücksetzen von Chat-Auswahlen oder Zugriff auf fremde Chat-Zuordnungen. Native Regressionen decken Editoröffnung sowie eine geprüfte gemeinsame Menüauswahl ohne Schlüsselwerte im API-Ergebnis ab.


## Native Requesty-Presets (Privacy Agent 0.2)

Der aktivierte Manager kann nach ausdrücklicher Migrationsvorschau A0s Default, Efficiency und Power auf geprüfte Requesty-EU-Modelle umstellen. Native Presets sind anschließend die einzige Quelle für Main, Utility und Vision; die Privacy-Policy und Schlüssel bleiben getrennt. Zulässige Modelländerungen im normalen A0-Preset-Editor erfordern keine Abschaltung. Der Provider ist Requesty, Embeddings bleiben auf dem eingerichteten lokalen Modell. Kurze Managed-Namen und mit einer Anbieterpräfix-Suche spezifische IDs bleiben möglich.

Neue Einrichtungen starten mit Default (Sol/Luna); Efficiency verwendet GLM/DeepSeek mit separatem DeepSeek-Vision-Modell, Power Opus/Luna. Diese Vorbelegung startet keine kostenpflichtigen Modelltests. Jede Migration validiert den aktuellen Katalog und verlangt Ersatz für fehlende Standardmodelle. Eine bereits ausdrücklich gewählte gemeinsame Einrichtung kann als eigenes natives Preset erhalten und ausgewählt bleiben. Vorhandene aktive Profilsetups werden als native Profil-Presets übertragen; Schlüssel werden nicht in Presets kopiert. Andere individuelle Presets bleiben erhalten, unzulässige davon gesperrt.

Sicherungen liegen ausschließlich lokal unter usr/privacy-agent/preset-backups. Veraltete Vorschauen werden abgelehnt. Eine fehlgeschlagene Übernahme stellt die vorherigen Presets und Zuordnungen wieder her. Die separate Wiederherstellung ist nach zentraler Deaktivierung möglich und verweigert das Überschreiben späterer Änderungen. Updates migrieren oder überschreiben Presets nicht automatisch. Erst nach Vorbereitung der Komponenten, bestätigter Migration und expliziter Aktivierung gelten die installationsweiten Regeln.

Die nativen Speicher- und Auswahladapter werden beim A0-Start eingerichtet, sind reversibel und verändern keine A0-Kerndateien. Direkte API-Eingaben werden ebenfalls geprüft; alte Modellwrapper mit abweichender Modellwahl müssen neu aufgebaut werden. Ohne Manager bleibt das eigenständige Verhalten dieses Plugins erhalten. Bildinhalte und beliebige Werkzeugübertragungen bleiben außerhalb der lokalen Textmaskierung.

New installations require Local Privacy Guard 1.7.4: the optimized spaCy/Regex pipeline is the sole production detector. Backend selection and optional detector installation have been removed. Existing mappings, presets and credentials remain intact. Detector experiments are retained on `archive/cpu-pii-evaluation-2026-10-13` in the companion repositories. Existing installations are updated through the native plugin manager; compatible plugins are not overwritten by dependency setup.
