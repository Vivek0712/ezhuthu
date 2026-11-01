# Ezhuthu Tamil epigraphy ontology (v0)

The knowledge layer behind the Ezhuthu tutor and restorer: who ruled, where a place sits in the
nāṭu/kōṭṭam/maṇṭalam hierarchy, which royal-praise formula belongs to which king, which letters
existed in which script stage. Built with rdflib and served to the agent over MCP
(`python -m ezhuthu.ontology.mcp_server`). Context Ontology Accelerator: attempted, not run (permission
policy); see [COA.md](COA.md), which also documents the MCP server and the AgentCore bundle needs.

## Files

| Path | What |
| --- | --- |
| `ezhuthu.ttl` | OWL ontology: 27 classes, 21 object properties, 1,958 named individuals (23,029 triples) |
| `lookups/<kind>.json` | Entity records, one file per kind, valid against `contracts/ontology-lookup.schema.json` |
| `letters_by_era.json` | Valid base letters per script stage, Unicode glyphs (Aksharamukha), documented exceptions, corpus counts, tutor levels L1–L5 |
| `coverage.json` | Counts per kind, Wikidata coverage, dropped seeds, unmatched title names, DHARMA commit pins, `splits` (benchmark split filter and the exact inscription ids used) |
| `hint_eval.json` | `hints_for_gap` hit@5: held-out on benchmark val/test items, plus in-corpus coverage |
| `seeds/*.yaml` | Curated seed lists (rulers, titles, formulas, grant types, assemblies, measures, coins, taxes, deities, unit types) |
| `wikidata/snapshot.json`, `wikidata/review.yaml` | Wikidata SPARQL results (all candidates) and the manual review applied to them |

Code: `src/ezhuthu/ontology/` (`tei.py` reader, `normalize.py`, `matcher.py`, `letters.py`, `build.py`,
`owl.py`, `wikidata.py`, `lookup.py`, `hint_eval.py`, `mcp_server.py`).

## Train split only (no benchmark leakage)

DHARMA editions keep the expert `<supplied>` restorations inline, and the ontology takes place, temple
and admin-unit names (and their spellings) from edition titles and text. Built from every edition, it
would offer val/test answers as `hints_for_gap` fills (QA on PR #9 found two such test hits). The
shipped artefacts are therefore built with `--splits train`: an edition is used only when the data
team's `benchmark/inscriptions.jsonl` lists it in the train split. The v0 build was run against both
the PR #6 benchmark and the data team's newer local regeneration, and an edition had to be train in
**both** (so it stays leak-free whichever lands). Editions a benchmark does not list (102 `~`-prefixed
DHARMA drafts) are left out too, since they may be another edition of a held-out stone. Result: 862 of
1,193 editions used, 229 held out, 102 unlisted (`coverage.json` -> `splits`, with every id used).
`tests/ontology/test_artefacts.py` fails if any val/test edition of `benchmark/inscriptions.jsonl` (once
it is on main) is among them: rebuild with `--splits train` whenever the splits change.

## Using it (agent and app teams)

```python
from ezhuthu.ontology import find_entities, valid_letters, formulas_for, entity, hints_for_gap

find_entities("svasti śrī maturai koṇṭa kō-p-parakēcari-varmmarkku yāṇṭu")
# -> [{id: ez:formula/svasti-sri, ...}, {id: ez:formula/matirai-konta}, {id: ez:title/parakesarivarman}, ...]
#    each with kind, label (ISO), label_ta, start/end char span, surface
valid_letters("L2")            # or a stage id, e.g. "chola-tamil", "vatteluttu", "tamil-brahmi-1"
formulas_for("ez:ruler/rajaraja-i")   # own meykkīrtti/epithets, then dynasty formulas, then common ones
entity("ez:ruler/rajaraja-i")         # full lookup record (wikidata Q2128757, attested_in, era, ...)
hints_for_gap("svasti śrī maturai koṇṭa kō-p-para", "rkku yāṇṭu", gap_chars=7)
# -> [{id: ez:title/parakesarivarman, kind: title, label: Parakēsarivarman, fill: "kecarivarma",
#      alt_fills: [...], score, reason: "overlap"}, ...]
```

Over MCP (stdio, official `mcp` SDK) the same five functions are tools with the same arguments; results are
JSON objects (`{"entities": [...]}`, `{"letters": [...]}`, `{"formulas": [...]}`, `{"entity": ...}`,
`{"hints": [...]}`). The agent uses it through a Strands `MCPClient` (`ezhuthu.agent.ontology_mcp`); see
[COA.md](COA.md) section 3:

```python
from mcp import StdioServerParameters
from mcp.client.stdio import stdio_client
from strands.tools.mcp import MCPClient
client = MCPClient(lambda: stdio_client(StdioServerParameters(
    command=sys.executable, args=["-m", "ezhuthu.ontology.mcp_server"])))
with client:
    client.call_tool_sync("t1", "hints_for_gap", {"left": "cantirātittavar", "right": " ivai"})
```

Each hint has `id`, `kind` and `label`, the shape of `ontology_hints` in `contracts/restore-api.md`.
`fill` is in folded key form (see Normalisation), so compare with `ezhuthu.ontology.normalize.key(candidate)`.
`gap_chars` counts Tamil letters (uyir, mey, uyirmey), the unit of the benchmark's `gap_chars` and of
DHARMA's `<gap unit="character">` (`ezhuthu.ontology.letters.letter_count`). Hints also get a boost
when their dynasty matches an entity named in `left`/`right`.
A gap right before `-kku yāṇṭu` (regnal-year formula) also returns `reason: "regnal_slot"` hints: the
rulers and titles of the dynasty named in the context, with `fill: null`.

Input rules (all raise `ValueError`): text must be ISO-15919, not Tamil script (transliterate first
with `ezhuthu.corpus.script`); `gap_chars` is `None` or an int >= 1; `find_entities` takes at most
50,000 chars (`MAX_TEXT_CHARS`). `hints_for_gap` reads only the 2,000 chars (`CONTEXT_CHARS`) nearest
the gap on each side, so huge payloads cost no more than normal ones. Every result is a fresh copy;
mutating it does not change the cached ontology.

All text is ISO-15919. `label_ta` is Aksharamukha's faithful ISO→Tamil mapping of `label_iso`
(`nativize=False`, no superscript digits, so n→ந and ṉ→ன as DHARMA writes them; word-final ந் is
written ன்; Sanskrit sounds in Grantha letters; regnal numerals kept as I/II/III). The data team's
`ezhuthu.corpus.script.iso_to_tamil` is the reference renderer for running text. When a label is not
ISO-15919 (an English DHARMA title such as "Tiruveḷḷaṟai’s well") and the rendering would keep Latin
letters, `label_ta` is `null` rather than a mixed-script string.

## Scope and model

Backbone reused by IRI, never copied (the TTL makes no statements about backbone terms):

| Ezhuthu class | Subclass of |
| --- | --- |
| `ez:Inscription` | `crmtex:TX1_Written_Text` |
| `ez:Line` | `crmtex:TX7_Written_Text_Segment` |
| `ez:Edition` | `epont:Edition` (EpOnt, `https://w3id.org/epont/ontology/`) |
| `ez:ScriptStage` | `crmtex:TX3_Writing_System` |
| `ez:Letter` | `crmtex:TX8_Grapheme` |
| `ez:Dynasty`, `ez:Assembly` | `crm:E74_Group` |
| `ez:Ruler` | `crm:E21_Person` |
| `ez:Title` (title/epithet/biruda) | `crm:E41_Appellation` |
| `ez:Formula` ⊃ `ez:RoyalPraiseFormula` (meykkīrtti) | `crm:E90_Symbolic_Object` |
| `ez:Place` ⊃ `ez:AdministrativeUnit` ⊃ `Ur`, `Caturvedimangalam`, `Nadu`, `Kurram`, `Kottam`, `Valanadu`, `Mandalam` | `crm:E53_Place` |
| `ez:Temple` | `crm:E22_Human-Made_Object` |
| `ez:Deity` | `crm:E28_Conceptual_Object` |
| `ez:Grant` / `ez:GrantType` | `crm:E7_Activity` / `crm:E55_Type` |
| `ez:Measure`, `ez:Coin` | `crm:E58_Measurement_Unit` |
| `ez:Tax` | `crm:E55_Type` |

Properties include `ez:fallsWithin` (⊑ `crm:P89_falls_within`), `ez:hasMember` (⊑ `crm:P107`),
`ez:bearsTitle` (⊑ `crm:P1`), `ez:mentions` (⊑ `crm:P67`), `ez:hasLine` (⊑ `crm:P106`),
`ez:hasEdition` (⊑ `epont:hasEdition`), `ez:locatedAt` (⊑ `crm:P55`), `ez:grantType` (⊑ `crm:P2`),
plus `ez:attestedIn`, `ez:writtenIn`, `ez:letterOf`, `ez:memberOfDynasty`, `ez:praiseOf`, `ez:dedicatedTo`.
Labels: `skos:prefLabel@ta-Latn` (ISO), `skos:altLabel@ta` / `@en`, variants as `skos:hiddenLabel`,
Wikidata as `skos:exactMatch`. The grant properties (`recordsGrant`, `grantedTo`, `paidIn`,
`exemptFrom`, `witnessedBy`) are declared for the agent team; v0 has no grant *instances*.

Namespace: `https://w3id.org/ezhuthu/` (`ez:ruler/rajaraja-i` → `https://w3id.org/ezhuthu/ruler/rajaraja-i`).
The w3id redirect is not registered yet.

## Where instances come from

* **DHARMA header titles** (`<place>, <temple>, time of <ruler>, year N`): places, temples, ruler and
  title attestations. 88 distinct title names (97 inscriptions) did not match a seed and are listed in
  `coverage.json` (`title_names_unmatched`), e.g. bare "Rājarāja" (I or II?) is left unmatched on purpose.
* **DHARMA `<placeName>`/`<persName>`**: DHARMA marks very few entities in edition text (14 `placeName`,
  14 unreferenced `persName` across the six collections; most `persName` elements are editors), so
  this adds only 4 places (train split). `<rs>` is not used.
* **Corpus scan of curated seed variants** (rulers, titles, formulas, grant types, assemblies,
  measures, coins, taxes, deities): `attested_in` lists `<inscription_id>:<line_n>` refs. A seed with
  no attestation is dropped and listed in `coverage.json` (v0 train build: Vijayālaya, Śrīraṅga, `kō`,
  `paṭṭam`, `tiramam`, `īḻakkācu`, bare `ūr`).
* **Administrative units** are extracted from edition text by their oblique-case suffixes
  (`-nāṭṭu`, `-kūṟṟattu`, `-kōṭṭattu`, `-vaḷanāṭṭu`, `-maṇṭalattu`, `-caturvēdimaṅkalattu`), and
  `broader` comes from address chains (inscriptions name units big-to-small, e.g.
  `jayaṅ-koṇṭa-cōḻa-maṇṭalattu kāliyūr-k-kōṭṭattu …`): the nearest preceding higher-rank unit,
  majority vote. Fragments next to gaps are skipped and one-off short names dropped (37 dropped).
* **Script stage** per inscription: DHARMA `rendition="class:…"` (`tamil`, `vaṭṭeḻuttu`, `grantha`)
  plus the ruler/dynasty for Tamil script (Pallava → Pallava Tamil, Cōḻa → Chola Tamil, Vijayanagara →
  Later Tamil; Pāṇḍya by the ruler's era).
* **Wikidata** (SPARQL, `python -m ezhuthu.ontology.wikidata --refresh`, then `review.yaml`): a QID is
  assigned only when exactly one item matches an English label form under a kind filter (human for
  rulers; located in Tamil Nadu for places; temple class + Tamil Nadu for temples). Names DHARMA does
  not disambiguate (Mahendravarman, Nandivarman, Sundara Pāṇḍya …) intentionally have no QID.

## Coverage (v0, train split, DHARMA commits pinned in `coverage.json`)

Corpus: 6 DHARMA collections (`tfa-pallava`, `tfa-cempiyan-mahadevi`, `tfa-pandya`, `tfa-sii`,
`tfa-tamilnadu`, `tfa-uttiramerur`), 1,193 editions, of which the 862 train-split editions
(10,564 edition lines) are used.

| Kind | Entities | With Wikidata QID |
| --- | ---: | ---: |
| script_stage | 8 | |
| letter | 262 | |
| dynasty | 6 | 6 (100%) |
| ruler | 42 | 19 (45.2%) |
| title | 13 | |
| formula | 14 | |
| place | 357 | 35 (9.8%) |
| admin_unit | 200 (6 unit types + 194 named units) | |
| temple | 139 | 8 (5.8%) |
| deity | 13 | |
| grant_type | 10 | |
| assembly | 6 | |
| measure | 14 | |
| coin | 4 | |
| tax | 8 | |

Inscriptions per script stage (train split): Pallava Tamil 268, Chola Tamil 196, Vaṭṭeḻuttu 61,
Grantha 56, Later Tamil 6, **Tamil-Brāhmī 0**: none of the six collections contains Tamil-Brāhmī, so its letters
(Aksharamukha + Mahadevan 2003 exceptions) have no corpus attestation yet. Unmapped DHARMA script
classes (Southern Brāhmī 17, Siddhamātr̥kā 2, numeric class codes 7) are counted in `coverage.json`.

`hints_for_gap` (`python -m ezhuthu.ontology.hint_eval --items ...`, `hint_eval.json`), top-5 exact match
of `fill`/`alt_fills` against the folded expert restoration, items with a target of 2+ key characters:

| Set | Scored | Hits | hit@5 |
| --- | ---: | ---: | ---: |
| val (held-out, PR #6 benchmark) | 345 | 16 | 4.6% |
| test (held-out, PR #6 benchmark) | 253 | 16 | 6.3% |
| in-corpus (lost `<supplied>` spans of the 862 train editions; upper bound, not held-out) | 1,450 | 96 | 6.6% |

For comparison, an ontology built from every edition scores 18/345 on val and 17/253 on test: that gap
is the leakage the train-only build removes. On the data team's newer local regeneration of the
benchmark the train-only build scores 14/344 (val) and 18/280 (test). `hint_eval` refuses to score
items whose inscription was used to build the ontology. These are hint-coverage numbers, not
restoration accuracy: hints are one input to the agent's restorer.

## Normalisation

Matching compares folded keys (`normalize.key`): lower-case, editorial marks removed (`- ’ · = …`),
e/ē and o/ō merged (no length contrast in Tamil script before the 18th c.), ś/ṣ/s → c (Tamil spelling of
Sanskrit sibilants), gemination after r collapsed (`varmma` = `varma`), spaces removed. A match must
start at a word or compound-member boundary and may end anywhere, so stems match case forms.

## Known limitations

* `attested_in` in the lookups lists at most 40 refs (sorted by id); `inscription_count` and
  `attestation_count` give the totals and the TTL has every `ez:attestedIn` link.
* Short glossary stems can over-match (e.g. `poṉ` "gold" also starts personal names; `kalam` is
  restricted to `nel kalam`/`kalam nel`/`kalamum` because it also means "ship"). Counts are
  attestations of the string, not hand-verified senses.
* Place labels follow DHARMA titles, which mix ISO and English forms (Tanjore and Thanjavur are two
  place records, both with Q41496).
* Era strings are conventional, approximate regnal dates; the curated glosses (`label_en`) are short
  handbook glosses, not quotations from DHARMA translations.

## Licence and citation

DHARMA repositories carry a CC BY 4.0 `LICENCE.txt`, while 1,127 of the 1,128 edition files that declare a licence declare
CC BY-SA 4.0 in their TEI header. Because the lookups and individuals are derived from those files,
the derived data (`lookups/`, `letters_by_era.json`, individuals in `ezhuthu.ttl`) is released under
**CC BY-SA 4.0** (`dcterms:license` in the TTL); the class/property model and the curated seeds are
offered under CC BY 4.0. The lead should confirm this with the charter's "CC BY 4.0" wording.

Cite DHARMA for the source texts:

> DHARMA project (ERC grant 809994), *Tamil and Pallava epigraphy* collections, https://dharmalekha.info,
> CC BY 4.0 / CC BY-SA 4.0, commits as pinned in `ontology/coverage.json`.

and this ontology as: *Ezhuthu Tamil epigraphy ontology v0 (2026), built with rdflib on CIDOC CRM,
CRMtex and EpOnt; instances from DHARMA.* Letter renderings: Aksharamukha (V. Rajan). Tamil-Brāhmī
exceptions: I. Mahadevan, *Early Tamil Epigraphy* (2003).

## Rebuild

```bash
make setup
# DHARMA clones under data/raw/dharma/<collection>/ (gitignored; `make data` once the data team lands it)
.venv/bin/python -m ezhuthu.ontology.wikidata --refresh   # optional, network; then review wikidata/review.yaml
.venv/bin/python -m ezhuthu.ontology.build --splits train  # offline, deterministic; needs benchmark/inscriptions.jsonl
#   (--benchmark PATH is repeatable; --splits all builds from every edition, for local exploration only)
.venv/bin/python -m ezhuthu.ontology.hint_eval --items benchmark/items.val.jsonl --items benchmark/items.test.jsonl
```
