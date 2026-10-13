> **A0 Privacy Suite 0.9.3 - community beta.** Independently developed for local Agent Zero installations. Not a Requesty product; not affiliated with or endorsed by Requesty. Requesty is the external routing service used by the Model Gateway. All three components share version 0.9.3. Older numbers in historical reports document previous tests, not current requirements.

<p align="center"><img src="webui/thumbnail.svg" width="128" alt="A0 Privacy Suite - Manager"></p>

# A0 Privacy Suite - Manager für Agent Zero 2.13

Ein gemeinsamer Einstieg für EU-Privatanwender: Requesty-Routen, lokale Textmaskierung und lokale Embeddings einmal einrichten und als Mindestregeln für **alle Profile dieser Installation** verwenden. Version 0.9.3 verlangt A0 Privacy Suite - Local Guard 0.9.3 und A0 Privacy Suite - Model Gateway 0.9.3, verwendet native A0-Presets und ist keine vollständige Sicherheits-Sandbox.

Die bestehenden [A0 Privacy Suite - Model Gateway](https://github.com/mgr-de/a0-requesty-privacy-guard) und [A0 Privacy Suite - Local Guard](https://github.com/mgr-de/a0-local-privacy-guard) Plugins bleiben erhalten und einzeln nutzbar. Dieser Manager verwendet ihre Filter und Modellprüfung, statt sie zu kopieren.


## Developer ohne Maskierung

1. **Benutzername und Passwort für die Agent-Zero-Oberfläche dringend empfohlen.** Das Plugin ist primär für eine lokale Installation ohne externen Zugang vorgesehen; dort ist die Anmeldung optional. Ohne Anmeldung kann jeder mit Zugriff auf die Oberfläche Profilausnahmen verwalten. Sobald andere Personen oder ein Netzwerk Zugriff haben, Anmeldung und Zugangsschutz dringend einrichten. Ist eine Anmeldung konfiguriert, muss ihre authentifizierte Sitzung verwendet werden. Die ausdrückliche Freigabe und die native CSRF-Prüfung bleiben immer bestehen; das Plugin erzwingt keine zusätzliche Netzwerk- oder IP-Sperre.
2. **Eigenes Developer-Profil anlegen** erstellt ein neues Profil ausschließlich aus dem eingebauten Developer-Profil. Bestehende eigene Profile werden nicht kopiert oder überschrieben. Die Anlage erteilt noch keine Ausnahme.
3. Die Übertragung personenbezogener Daten aus dem gesamten Modellkontext einschließlich Memory und Unteragenten ausdrücklich bestätigen und **Ausnahme ausdrücklich freigeben** wählen.
4. **Neuer Developer-Chat** erstellt einen eigenen leeren Hauptchat. Sein Status lautet **PII-Maskierung aus · Secret-Prüfung aktiv**. Die Requesty-Route wird separat geprüft; lokale Embeddings bleiben vorgeschrieben. Antworten werden gepuffert und auf Secrets geprüft. Ein lokales Chatmodell ist nicht erforderlich.

Bestehende Chats bleiben maskiert, auch nach Wahl dieses Profils. Unteragenten erben die Hauptchat-Policy. Profil-ID, tatsächliche Definition, Profilgeneration und serverseitiger Chatdatensatz müssen zusammenpassen. Projektüberschreibungen und importierte Chat-Metadaten begründen keine Ausnahme. Bearbeitung/Löschung des freigegebenen Profils widerruft die Freigabe. Profil- oder Projektwechsel eines unmaskierten Chats sperrt ihn dauerhaft für weitere Modellaufrufe.

**Widerruf** stoppt weitere Aufrufe dieser Developer-Chats; eine erneute Freigabe entsperrt sie nicht. Einen neuen geschützten Chat beginnen. Jeder Provider-Versuch wird unmittelbar an der Übergabe an LiteLLM erneut zugelassen, nach Wartezeiten und bei Framework-Fallbacks. Interne LiteLLM-/SDK-Wiederholungen werden für unmaskierte Aufrufe deaktiviert. Diese kontrollierte Zulassung ist der Startzeitpunkt: ein bereits zugelassener Aufruf kann nach Widerruf noch abschließen. Seine Antwort behält den ursprünglichen PII-Modus und wird weiterhin auf Secrets geprüft.

Developer-Memory ist nach Projekt, freigegebener Profilgeneration und Modus getrennt. Geschützte Speicher und Zuordnungen werden nicht übernommen oder rückübersetzt. Lokale Audit-Metadaten sind keine manipulationssichere Historie gegenüber Host-Administratoren. **Der gesamte freigegebene Modellkontext kann personenbezogene Daten unmaskiert an den Modellanbieter übertragen.** Secret-Prüfung, EU-Routing und ZDR ersetzen keine PII-Maskierung.

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

Empfohlen: **Serving region EU only**, **Requesty Zero data retention**, **Zero-data-retention models only**, geprüfte **EU Approved Models**. Gateway-Region, Requesty-Speicherung und Anbieter-Speicherung sind getrennte Kontrollen. Metadaten bleiben erhalten, und Kontoregeln gelten auch für andere Anwendungen. Gesperrte Regeln können Support erfordern. [Anleitung mit Screenshot](https://github.com/mgr-de/a0-requesty-privacy-guard/blob/main/docs/REQUESTY-ACCOUNT-SETTINGS.md).

## Schutzgrenzen

Erkennung reduziert Risiken und garantiert keine vollständige Anonymisierung. Katalogangaben werden nicht unabhängig auditiert. Bilder werden beim ausgewählten Dienst verarbeitet; Textmaskierung schützt ihren Bildinhalt nicht. Webseiten, Formulare, Uploads und andere Werkzeugübertragungen werden nicht vollständig überwacht. Native Browser- und Dateifunktionen bleiben bedienbar.

Der Agent kann über Code-Ausführung oder fremde Clients außerhalb dieser Modellintegration arbeiten. Ein Plugin ist keine Sicherheitsgrenze gegen Administratoren, Schreibzugriffe auf Schutzdateien oder absichtliches Umgehen der Adapter. Für solche Grenzen braucht es eine separate gehärtete Instanz mit kontrolliertem Netzwerk.

## Technische Schnittstellen und Daten

`helpers.manager` stellt effektive Mindestpolicy, gemeinsame Modelle, Komponentenprüfung und Status bereit. Die aktivierte Basis liegt außerhalb der Plugin-ZIPs unter `usr/privacy-agent/`; Konfiguration und Schlüssel werden atomar mit eingeschränkten Dateirechten gespeichert, aber nicht verschlüsselt. Die PII-Zuordnungen bleiben bei A0 Privacy Suite - Local Guard unter `usr/privacy-mappings`.

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

Nach der Migration zeigen Chat-Menü, Profil-Editor und Preset-Editor dieselben nativen Presets. Der frühere zusätzliche Menüeintrag „A0 Privacy · gemeinsam“ entfällt. Die native Auswahl für Chat, Profil, Projekt und globale Vorgabe bestimmt die tatsächlich verwendeten Modelle; unzulässige Presets bleiben gesperrt. Noch nicht migrierte ältere Einrichtungen behalten ihren bisherigen Menüeintrag bis zur ausdrücklichen Umstellung.

Der native Profil-Editor verwendet Lesekontexte ohne Chat-ID. Diese erhalten ihre eigene Profilkonfiguration, ohne Parent-Chat-Suche, Rücksetzen von Chat-Auswahlen oder Zugriff auf fremde Chat-Zuordnungen. Native Regressionen decken Editoröffnung sowie eine geprüfte gemeinsame Menüauswahl ohne Schlüsselwerte im API-Ergebnis ab.


## Native Requesty-Presets (Privacy Agent 0.2)

Der aktivierte Manager kann nach ausdrücklicher Migrationsvorschau A0s Default, Efficiency und Power auf geprüfte Requesty-EU-Modelle umstellen. Native Presets sind anschließend die einzige Quelle für Main, Utility und Vision; die Privacy-Policy und Schlüssel bleiben getrennt. Zulässige Modelländerungen im normalen A0-Preset-Editor erfordern keine Abschaltung. Der Provider ist Requesty, Embeddings bleiben auf dem eingerichteten lokalen Modell. Kurze Managed-Namen und mit einer Anbieterpräfix-Suche spezifische IDs bleiben möglich.

Neue Einrichtungen starten mit Default (Sol/Luna); Efficiency verwendet GLM/DeepSeek mit separatem DeepSeek-Vision-Modell, Power Opus/Luna. Diese Vorbelegung startet keine kostenpflichtigen Modelltests. Jede Migration validiert den aktuellen Katalog und verlangt Ersatz für fehlende Standardmodelle. Eine bereits ausdrücklich gewählte gemeinsame Einrichtung kann als eigenes natives Preset erhalten und ausgewählt bleiben. Vorhandene aktive Profilsetups werden als native Profil-Presets übertragen; Schlüssel werden nicht in Presets kopiert. Andere individuelle Presets bleiben erhalten, unzulässige davon gesperrt.

Sicherungen liegen ausschließlich lokal unter usr/privacy-agent/preset-backups. Veraltete Vorschauen werden abgelehnt. Eine fehlgeschlagene Übernahme stellt die vorherigen Presets und Zuordnungen wieder her. Die separate Wiederherstellung ist nach zentraler Deaktivierung möglich und verweigert das Überschreiben späterer Änderungen. Updates migrieren oder überschreiben Presets nicht automatisch. Erst nach Vorbereitung der Komponenten, bestätigter Migration und expliziter Aktivierung gelten die installationsweiten Regeln.

Die nativen Speicher- und Auswahladapter werden beim A0-Start eingerichtet, sind reversibel und verändern keine A0-Kerndateien. Direkte API-Eingaben werden ebenfalls geprüft; alte Modellwrapper mit abweichender Modellwahl müssen neu aufgebaut werden. Ohne Manager bleibt das eigenständige Verhalten dieses Plugins erhalten. Bildinhalte und beliebige Werkzeugübertragungen bleiben außerhalb der lokalen Textmaskierung.

New installations require A0 Privacy Suite - Local Guard 0.9.3: the optimized spaCy/Regex pipeline is the sole production detector. Backend selection and optional detector installation have been removed. Existing mappings, presets and credentials remain intact. Detector experiments are retained on `archive/cpu-pii-evaluation-2026-10-13` in the companion repositories. Existing installations are updated through the native plugin manager; compatible plugins are not overwritten by dependency setup.

## Code bei der Softwareentwicklung

A0 Privacy Suite - Local Guard 0.9.3 erkennt vollständige Python-Ausschnitte sowie konservativ JavaScript/TypeScript. Erkannte Syntax, Bezeichner und numerische Code-Konstanten bleiben erhalten; Kommentare, Zeichenketten und Secrets werden weiter geprüft. Unterstützte Umgebungsreferenzen werden von tatsächlichen Zugangsdaten unterschieden. Unvollständige oder nicht unterstützte Ausschnitte bleiben in der normalen Prüfung. [Verhalten und Grenzen](https://github.com/mgr-de/a0-local-privacy-guard/blob/main/docs/CODE-FILTERING.md).

Es gibt keine pauschale Code-Ausnahme und keinen weiteren Erkennungsbackend. Die Mindestregeln und Requesty-Routen bleiben aktiv. Für eigenständige lokale Modelltests kann A0 Privacy Suite - Local Guard ohne aktivierten zentralen Manager genutzt werden; die zentrale Requesty-Einrichtung verlangt weiterhin ihre geprüften Routen.

Die [Prüfung des festen Detektors](docs/SINGLE-DETECTOR-VALIDATION.md) dokumentiert die vorherige Veröffentlichung 0.2.7/1.7.4. Aktuelle Code-Regressionen stehen bei A0 Privacy Suite - Local Guard; historische Sprach-/Modellvergleiche bleiben im Archiv-Branch.

## Suite versioning and existing installations

All three components use the same suite version. 0.9.3 starts the unified community beta numbering and replaces the former Local Guard 1.9.0, Model Gateway 0.6.1 and Manager 0.3.3; it does not remove their functionality. Patch versions (0.9.x) cover fixes, later 0.x minor versions cover feature or compatibility changes, and 1.0 is reserved for a separately decided stable release. Versions below 1.0 do not promise a stable public API. Update all three components together through the native Git plugin updater and restart Agent Zero; older Local Guard metadata has a higher number, so an installer that refuses downgrades may require the explicit Git update. Do not uninstall or delete user data to change the name. Existing internal IDs, repository URLs, keys, mappings and stored presets remain valid. Historical tags and reports remain unchanged; new packages are marked as pre-releases.

## Community beta 0.9.3: compatibility and installation

Test target: Agent Zero 2.13 on Linux Docker, framework Python 3.12, CPU-only privacy detection. The exact image/framework commit and observed cold-install/download measurements are recorded in `docs/COMMUNITY-BETA-VALIDATION.md`. Other versions and deployment types have not been certified. This is independent community software, not an official Requesty product.

Install all three components on the same version through the native Plugin Hub, Git or the published ZIPs. Start with the Manager; its configuration provides an explicit button to install missing pinned companion packages. Installation does not activate central policy and does not invoke a paid model. Configure the Requesty key/routing and local languages deliberately before activating. Restart A0 after all component updates. An active policy must be deactivated centrally before using ordinary plugin-disable or uninstall actions; profile toggles cannot override it.

Local Guard downloads missing English/German spaCy models during installation. Additional languages require their corresponding model downloads. The configured local embedding model (`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`) may download on first use; model files need disk space and network access during setup, then inference is local. Ollama is optional and is not used by the PII detector. CPU time and memory depend on language models, text length and parallel chats; reserve additional host RAM/disk capacity and consult the measured beta report rather than treating development measurements as universal minimums. Missing required NER models block supported external calls.

See [security reporting and deployment limits](SECURITY.md). Current beta screenshots and test scope are linked in the validation report. No claim of complete anonymization or unrestricted protection of images/tools is made.

## Activation state and recovery (0.9.3)

The ordinary plugin toggle does not override an active central policy. The Manager shows plugin enablement, central activation and integrity of its own native adapters separately. A boolean `active: false` in the state file represents deliberate central deactivation. A new installation with no activation history is unconfigured. Invalid/missing activation fields, unreadable JSON, unsafe paths, or a missing `active.json` where an activation record or Manager ownership journal remains are errors: supported enforcement paths block rather than interpreting this as intentional disablement. An activation receipt contains only schema/managed status, no keys, PII or mappings.

Restore damaged `usr/privacy-agent/active.json` (and a damaged activation record, if present) from a trusted backup with its original state; do not replace it with an empty object, string or guessed `false` to clear an error. No automatic activation/deactivation is performed by repair. Keep model requests paused during maintenance; then restart A0 and check central status before use. The plugin is not an access-control boundary against an administrator who deliberately deletes all state and enforcement files.

For intact activation state, use **Eigene Prüfhaken wiederherstellen** to restore missing known Manager adapters; conflicting modified files require manual review and are not overwritten. After explicit central deactivation, **Inaktive Prüfhaken bereinigen** removes only hash-matching owned files and preserves modified/foreign files and their ownership evidence. This maintenance and normal Manager uninstall do not require either companion plugin to be available. Keys, presets, profiles and mappings are retained. Restoring hooks does not reinstall companion plugins or models; complete those separately through the native installer.
