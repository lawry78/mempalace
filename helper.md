# MemPalace — Felhasználói kézikönyv

## Mi ez?

A MemPalace egy lokális AI memóriarendszer, amely beszélgetéseket és projektfájlokat tárol **szó szerint** (nem összegzi őket), és egy ókori "emlékezet palota" metaforára épülő struktúrában szervezi. A rendszer 96.6%-ot ér el a LongMemEval benchmarkon, nulla API-hívással.

**Alapelvek:**
- Mindent tárol, szó szerint — nem dönt helyetted, mi fontos
- Teljesen lokális — nincs felhő, nincs API-kulcs szükséges
- Szemantikus keresés ChromaDB-vel
- Strukturált szervezés: wing → room → hall → drawer

---

## A "Palota" struktúra

A MemPalace az adatokat egy hierarchikus metafora szerint szervezi:

```
Wing (szárny)         — személy, projekt, vagy téma
  └─ Room (szoba)     — konkrét altéma (pl. "backend", "auth-migration")
      └─ Hall (terem) — memória típus (tények, események, felfedezések, stb.)
          └─ Drawer (fiók) — az eredeti, szó szerinti szöveg
```

**Wing**: A legfelső szint. Minden személy, projekt vagy téma egy külön "szárny". Pl. `wing_alice`, `project_mempalace`, `wing_hardware`.

**Room**: Egy wing-en belüli altéma. Pl. a `project_mempalace` wing-ben lehet `backend`, `frontend`, `planning` room.

**Hall**: A memória típusa:
- `hall_facts` — tények, döntések
- `hall_events` — események, mérföldkövek
- `hall_discoveries` — felfedezések, áttörések
- `hall_preferences` — preferenciák, szokások
- `hall_advice` — tanácsok, best practice-ek

**Drawer**: Az eredeti szöveg, változtatás nélkül. Ez az alapegység — minden keresés, minden vizualizáció drawer-ekre épül.

**Tunnel**: Automatikus kapcsolat két wing között, ha ugyanaz a room név mindkettőben megjelenik. Pl. ha a `benchmarks` room megjelenik `wing_ai_research`-ben és `wing_hardware`-ben is, az egy tunnel.

---

## A 4 rétegű memória stack

A MemPalace egy intelligens réteges rendszert használ a kontextus betöltéséhez:

| Réteg | Tartalom | Méret | Mikor töltődik |
|---|---|---|---|
| **L0** | Identitás (`~/.mempalace/identity.txt`) | ~100 token | Mindig |
| **L1** | Legfontosabb emlékek összefoglalója | ~500-800 token | Mindig (wake-up) |
| **L2** | Wing/room szűrt visszahívás | ~200-500 token | Igény szerint |
| **L3** | Teljes szemantikus keresés | Korlátlan | Igény szerint |

A wake-up (~600-900 token) betöltése után a kontextus 95%-a szabad marad beszélgetésre.

---

## Telepítés

```bash
pip install mempalace
```

Vagy fejlesztői módban:
```bash
git clone https://github.com/lawry78/mempalace.git
cd mempalace
pip install -e .
```

---

## Első lépések

### 1. Projekt inicializálása

```bash
mempalace init ~/projects/my_app
```

Átvizsgálja a mappastruktúrát, felismeri a személyeket és projekteket, és létrehozza a wing/room konfigurációt.

**Kapcsolók:**
- `--yes` — automatikusan elfogadja az összes felismert entitást (nem-interaktív mód)

### 2. Fájlok beolvasása (mining)

```bash
# Projektfájlok (kód, dokumentáció)
mempalace mine ~/projects/my_app

# Beszélgetés-exportok (Claude, ChatGPT, Slack)
mempalace mine ~/chats/ --mode convos
```

**Kapcsolók:**
- `--mode projects|convos` — beolvasási mód (alapértelmezett: projects)
- `--wing <név>` — wing név felülírása (alapértelmezett: mappa neve)
- `--no-gitignore` — `.gitignore` figyelmen kívül hagyása
- `--include-ignored <útvonal>` — ignorált fájl/mappa mégis beolvasása
- `--agent <név>` — a beolvasó neve (alapértelmezett: mempalace)
- `--limit <N>` — max N fájl feldolgozása
- `--dry-run` — csak mutatja mit csinálna, nem ír
- `--extract exchange|general` — kivonási stratégia beszélgetéseknél

### 3. Keresés

```bash
mempalace search "JWT authentication tokens"
mempalace search "pricing discussion" --wing my_app --room costs
```

**Kapcsolók:**
- `--wing <név>` — keresés szűkítése egy wing-re
- `--room <név>` — keresés szűkítése egy room-ra
- `--results <N>` — találatok száma (alapértelmezett: 5)

---

## Parancsok részletes leírása

### `mempalace init <dir>`

Inicializálja a projektet: átvizsgálja a fájlokat, felismeri a személyeket és projekteket, létrehozza a konfigurációt.

### `mempalace mine <dir>`

Beolvassa a fájlokat a palotába. Kétféle módban működik:
- **projects**: kódfájlok, dokumentáció, jegyzetek — mappa-struktúra alapján rendezi room-okba
- **convos**: beszélgetés-exportok (Claude.ai JSON, ChatGPT, Claude Code JSONL, Codex JSONL, Slack JSON, plain text) — csevegéspár-alapú chunkolás

### `mempalace search "query"`

Szemantikus keresés a palotában. ChromaDB vektoros hasonlóság alapján találja meg a releváns drawer-eket. Wing és room szűrőkkel szűkíthető.

### `mempalace status`

Megmutatja a palota aktuális állapotát: összes drawer, wing-ek és room-ok darabszámmal.

### `mempalace wake-up`

Kiírja az L0 (identitás) + L1 (lényeges történet) kontextust. Ez az, amit egy AI session elején be kell tölteni.

**Kapcsolók:**
- `--wing <név>` — projekt-specifikus wake-up

### `mempalace split <dir>`

Összefűzött beszélgetés-fájlokat bont szét session-önkénti fájlokra. A `mine --mode convos` előtt érdemes futtatni, ha a forrásfájlok több beszélgetést tartalmaznak.

**Kapcsolók:**
- `--output-dir <mappa>` — kimeneti mappa
- `--dry-run` — csak mutatja mit bontana szét
- `--min-sessions <N>` — minimum N session legyen a fájlban (alapértelmezett: 2)

### `mempalace compress`

Tömöríti a drawer-eket az AAAK dialektussal. Ez egy **kísérleti, veszteséges** tömörítés, ami ismétlődő entitásokat rövidít le. Csak nagy wing-ek esetén (500+ drawer) ajánlott.

**Kapcsolók:**
- `--wing <név>` — csak egy wing tömörítése
- `--dry-run` — előnézet tárolás nélkül
- `--config <fájl>` — entitás konfiguráció JSON

### `mempalace repair`

Újraépíti a ChromaDB vektorindexet a tárolt adatokból. Akkor hasznos, ha a palace megsérül (pl. segfault után).

### `mempalace doctor`

Átfogó egészségügyi vizsgálat a palotán. Hat különböző ellenőrzést futtat:

| Vizsgálat | Mit keres | Súlyosság |
|---|---|---|
| **Orphans** | Hiányzó wing/room metaadatú drawer-ek | Figyelmeztetés |
| **Duplicates** | Majdnem azonos drawer párok (>95% hasonlóság) | Információ |
| **Tiny rooms** | Room-ok 1-2 drawer-rel | Információ |
| **Conflicts** | Ellentmondó drawer-ek (pl. "váltottunk X-ről Y-ra" vs régi állapot) | Kritikus |
| **Stale KG** | 365+ napos aktív Knowledge Graph tények lejárat nélkül | Információ |
| **KG conflicts** | Ugyanaz a subject+predicate több aktív értékkel | Kritikus |

**Kapcsolók:**
- `--wing <név>` — vizsgálat szűkítése egy wing-re
- `--verbose` — részletes issue kiírás

### `mempalace deep-dive "topic"`

Kimerítő téma-export: **mindent** összegyűjt amit a palota tud egy adott témáról, és strukturált Markdown fájlba menti.

Három stratégiát használ:
1. **Szemantikus keresés** — ChromaDB vektor-hasonlóság
2. **Room név egyezés** — room-ok amik nevében szerepel a keresett szó
3. **Knowledge Graph** — entitás kapcsolatok és idővonal

**Kapcsolók:**
- `--wing <név>` — szűkítés egy wing-re
- `--output <fájl>` — kimeneti fájl (alapértelmezett: `deep_dive_<topic>.md`)
- `--limit <N>` — max szemantikus találat (alapértelmezett: 100)

**Kimenet példa:**
```markdown
# Deep Dive: authentication
*12 drawers collected, 3 knowledge graph facts*

## Knowledge Graph
### Current Facts
- **Alice** works_at **NewCo** (since 2025-01-01)

## Memories
### project / backend
**auth.py — 2026-01-01** (sim: 0.89)
> The authentication module uses JWT tokens...
```

### `mempalace visualize`

Interaktív palota-térkép és dashboard generálása egyetlen önálló HTML fájlként. Külső dependency nélkül működik, teljesen offline.

**Kapcsolók:**
- `--output <fájl>` — kimeneti HTML fájl (alapértelmezett: `palace_map.html`)
- `--no-open` — ne nyissa meg automatikusan a böngészőben
- `--demo` — demo adatokkal generál (nem kell valódi palota)

A vizualizáció részletes leírását lásd lentebb.

---

## A vizuális megjelenítő

A `mempalace visualize` parancs egy önálló HTML fájlt generál, ami a böngészőben nyílik meg. Nem igényel szervert, nincs külső függőség — minden benne van egyetlen fájlban.

### Dashboard (felső sáv)

Hat statisztikai kártya:
- **Total Drawers** — összes drawer a palotában
- **Wings** — wing-ek száma
- **Rooms** — room-ok száma
- **Tunnels** — wing-ek közötti tunnel kapcsolatok száma
- **KG Entities** — Knowledge Graph entitások száma
- **KG Active Facts** — aktív KG tények száma

### Palace Graph (középső rész)

Interaktív force-directed gráf:
- **Node-ok** = room-ok. Méretük a drawer-szám függvénye.
- **Színek** = wing-ek. Minden wing saját színt kap, a jelmagyarázat a gráf felett látható.
- **Élek** = tunnel-ek (wing-eket átkötő room-ok) vagy azonos wing-en belüli kapcsolatok.
- **Hover** = részletes tooltip: room név, drawer szám, wing badge-ek, hall badge-ek, relatív méret progressbar.
- **Kattintás** = jobb oldali detail panelen megjelennek a room drawer-ei.
- **Drag** = node-ok szabadon mozgathatók.

### Keresés

A gráf felett található keresőmező komplex szűrési nyelvet támogat:

| Szintaxis | Jelentés | Példa |
|---|---|---|
| `szó` | Tartalmazza (kis/nagybetű mindegy) | `JWT` |
| `"több szó"` | Pontos kifejezés | `"session management"` |
| `AND` | Mindkettő szükséges | `JWT AND cookie` |
| `OR` | Bármelyik elég | `PostgreSQL OR MongoDB` |
| `NOT` | Kizárás | `auth NOT deprecated` |
| `(...)` | Csoportosítás | `(JWT OR token) AND NOT expired` |
| `wing:név` | Wing szűrő | `wing:project` |
| `hall:név` | Hall szűrő | `hall:hall_facts` |

Keresés közben:
- A nem-illeszkedő node-ok elhalványulnak a gráfon
- A találatszám megjelenik a kereső mellett
- Ha egy node ki van választva, a detail panel csak a szűrt drawer-eket mutatja

### Detail Panel (jobb oldal)

A gráf területének jobb 1/3-a. Egy room node-ra kattintva megjelennek a drawer-ek:
- **Zárt állapot**: forrásfájl, dátum, hall badge, rövid előnézet (80 karakter)
- **Lenyitott állapot** (kattintásra): teljes metaadat sor (Wing, Hall, Date, Source) + teljes szöveg

### Export gomb

Az "Export .md" gomb a kereső mellett:
- **Szűrés nélkül**: a teljes palota tartalma → `palace_export.md`
- **Aktív kereséssel**: csak az illeszkedő drawer-ek → `<keresés_slug>.md`
- A Markdown wing/room-onként csoportosít, minden drawer-nél teljes szöveg és metaadat

### Wing / Room Breakdown (alul)

Összecsukható accordion tábla: wing-ek és room-ok darabszámmal, csökkenő sorrendben, színes sávokkal.

---

## MCP szerver (Claude Code integráció)

A MemPalace MCP szerverként is használható, ami 22 eszközt ad a Claude Code-nak:

**Telepítés:**
```bash
claude mcp add mempalace -- python -m mempalace.mcp_server
```

### Olvasási eszközök

| Eszköz | Leírás |
|---|---|
| `mempalace_status` | Palota áttekintés + memória protokoll |
| `mempalace_list_wings` | Wing-ek listája darabszámmal |
| `mempalace_list_rooms` | Room-ok listája (opcionális wing szűrő) |
| `mempalace_get_taxonomy` | Teljes wing → room → count fa |
| `mempalace_search` | Szemantikus keresés |
| `mempalace_check_duplicate` | Duplikátum ellenőrzés tartalom alapján |
| `mempalace_get_aaak_spec` | AAAK dialektus specifikáció |
| `mempalace_deep_dive` | Kimerítő téma-export |

### Írási eszközök

| Eszköz | Leírás |
|---|---|
| `mempalace_add_drawer` | Drawer hozzáadása wing/room-ba |
| `mempalace_delete_drawer` | Drawer törlése ID alapján |

### Knowledge Graph eszközök

| Eszköz | Leírás |
|---|---|
| `mempalace_kg_query` | Entitás kapcsolatainak lekérdezése |
| `mempalace_kg_add` | Új tény hozzáadása |
| `mempalace_kg_invalidate` | Tény lejáratának beállítása |
| `mempalace_kg_timeline` | Kronológiai idővonal |
| `mempalace_kg_stats` | KG statisztikák |

### Navigációs eszközök

| Eszköz | Leírás |
|---|---|
| `mempalace_traverse` | BFS bejárás egy room-ból kiindulva |
| `mempalace_find_tunnels` | Két wing közötti tunnel room-ok keresése |
| `mempalace_graph_stats` | Gráf kapcsolati statisztikák |

### Egészségügyi eszközök

| Eszköz | Leírás |
|---|---|
| `mempalace_doctor` | Palota egészségügyi vizsgálat |
| `mempalace_merge_drawers` | Duplikált drawer-ek összevonása |

### Agent napló

| Eszköz | Leírás |
|---|---|
| `mempalace_diary_write` | Naplóbejegyzés írása |
| `mempalace_diary_read` | Napló olvasása |

---

## Knowledge Graph

A MemPalace egy temporális tudásgráfot is tartalmaz SQLite-ban:

- **Entitások**: személyek, projektek, eszközök, koncepciók
- **Triple-ök**: subject → predicate → object (pl. "Alice works_at NewCo")
- **Temporális érvényesség**: minden ténynek van `valid_from` és opcionális `valid_to` dátuma
- Lekérdezés adott időpontra: "Mi volt igaz 2025. januárban?"
- Invalidálás: régi tények lejáratának beállítása törlés nélkül

---

## Konfiguráció

A konfiguráció a `~/.mempalace/` mappában található:

| Fájl | Tartalom |
|---|---|
| `config.json` | Palota útvonal, collection név, wing-ek, hall kulcsszavak |
| `identity.txt` | L0 identitás szöveg (plain text) |
| `people_map.json` | Név-variánsok leképezése |
| `entity_registry.json` | Felismert entitások regisztere |

A konfiguráció betöltési sorrendje:
1. Környezeti változók (`MEMPALACE_PALACE_PATH`)
2. `config.json` fájl
3. Beépített alapértelmezések

A rendszer validálja a konfigurációt: sérült JSON-nál figyelmeztet és alapértelmezéseket használ.

---

## Tipikus munkafolyamatok

### Új projekt beüzemelése
```bash
mempalace init ~/projects/my_app
mempalace mine ~/projects/my_app
mempalace status
```

### Beszélgetés-exportok beolvasása
```bash
mempalace split ~/chats/claude-sessions
mempalace mine ~/chats/claude-sessions --mode convos
```

### Napi használat AI-val
```bash
# Session elején
mempalace wake-up --wing my_app

# Keresés
mempalace search "miért váltottunk GraphQL-re" --wing my_app

# Téma összefoglaló
mempalace deep-dive "authentication" --wing my_app
```

### Palota karbantartás
```bash
# Egészségügyi vizsgálat
mempalace doctor --verbose

# Vizualizáció
mempalace visualize

# Javítás (sérülés után)
mempalace repair
```

---

*MemPalace v3.0.0 — Adj emlékezetet az AI-dnak.*
