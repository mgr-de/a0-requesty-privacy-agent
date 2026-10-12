<p align="center"><img src="webui/thumbnail.svg" width="128" alt="Requesty Privacy Agent"></p>

# Requesty Privacy Agent für Agent Zero 2.13

Ein gemeinsamer Einstieg für EU-Privatanwender: Requesty-Routen, lokale Textmaskierung und lokale Embeddings einmal einrichten und als Mindestregeln für **alle Profile dieser Installation** verwenden. Version 0.1.0 ist eine erste überprüfbare Einführung, keine vollständige Sicherheits-Sandbox.

Die bestehenden [Requesty](https://github.com/mgr-de/a0-requesty-privacy-guard) und [Local Privacy Guard](https://github.com/mgr-de/a0-local-privacy-guard) Plugins bleiben erhalten und einzeln nutzbar. Dieser Manager verwendet ihre Filter und Modellprüfung, statt sie zu kopieren.

## Einrichtung

1. ZIP über den nativen Agent-Zero-Installer installieren, Config öffnen. Installation allein aktiviert noch keine gemeinsame Policy.
2. Fehlende Komponenten installieren: fest gepinnte veröffentlichte ZIPs werden vor dem nativen Installer per SHA-256 geprüft. Vorhandene kompatible Plugins bleiben erhalten; ältere Versionen bewusst über die native Plugin-Verwaltung aktualisieren. Agent Zero neu starten.
3. Einen gemeinsamen Requesty-Schlüssel speichern. Optional die Requesty-Kontoeinstellungen in Requesty setzen und als **vom Nutzer bestätigt** vermerken. Das ist keine technische Kontoverifikation.
4. Den Modellkatalog laden und Main, Utility sowie ein bildfähiges Vision-Modell bewusst auswählen. Es werden keine Modelle automatisch ausgewählt und keine Modellantworten für diese Katalogprüfung angefordert. Gegebenenfalls lokale spaCy-Modelle und Embedding-Gewichte vorbereiten; hierfür werden nur Modellpakete heruntergeladen, keine Chatdaten übertragen. Kein lokaler Chat-LLM ist erforderlich.
5. Lokale Komponenten prüfen und die Einrichtung speichern. Erst danach **„Diese Installation schützen“** ausdrücklich bestätigen. Die Aktion betrifft alle bestehenden und neuen Profile; andere Installationen bleiben unverändert.

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
