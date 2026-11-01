"""OWL ontology for Ezhuthu, built with rdflib.

The backbone is reused by IRI, never copied: CIDOC CRM (``crm:``), CRMtex (``crmtex:``, the
namespace EpOnt itself uses) and EpOnt (``epont:``). The Tamil epigraphy layer (``ez:``) adds
classes and properties for script stages, letters, rulers, places and the institutional vocabulary
of Tamil inscriptions, each declared as a subclass/subproperty of a backbone term.
Individuals use the same ids as the lookups: ``ez:ruler/rajaraja-i`` is
``https://w3id.org/ezhuthu/ruler/rajaraja-i``.
"""

from __future__ import annotations

from rdflib import OWL, RDF, RDFS, SKOS, XSD, Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS

EZ = Namespace("https://w3id.org/ezhuthu/")
CRM = Namespace("http://www.cidoc-crm.org/cidoc-crm/")
CRMTEX = Namespace("http://www.cidoc-crm.org/crmtex/")
EPONT = Namespace("https://w3id.org/epont/ontology/")
WD = Namespace("http://www.wikidata.org/entity/")
ONTOLOGY_IRI = URIRef("https://w3id.org/ezhuthu/ontology")

# class -> (superclass, English label, comment)
CLASSES: dict[str, tuple[URIRef, str, str]] = {
    "Inscription": (CRMTEX.TX1_Written_Text, "Inscription", "A written text on a stone, copper plate or other support, as edited by DHARMA."),
    "Line": (CRMTEX.TX7_Written_Text_Segment, "Line", "A line of an inscription as numbered in the edition (<lb n>)."),
    "Edition": (EPONT.Edition, "Edition", "A scholarly edition of an inscription (here a DHARMA TEI/EpiDoc file)."),
    "ScriptStage": (CRMTEX.TX3_Writing_System, "Script stage", "A historical stage of the scripts used to write Tamil."),
    "Letter": (CRMTEX.TX8_Grapheme, "Letter", "A base letter (independent vowel or consonant+a) valid in a script stage."),
    "Dynasty": (CRM.E74_Group, "Dynasty", "A ruling lineage (Pallava, Cōḻa, Pāṇḍya, ...)."),
    "Ruler": (CRM.E21_Person, "Ruler", "A king named in inscriptions; names that DHARMA does not disambiguate stay at name level."),
    "Title": (CRM.E41_Appellation, "Title or epithet", "A royal title or epithet (e.g. Parakēsarivarman) that does not by itself identify a king."),
    "Formula": (CRM.E90_Symbolic_Object, "Formula", "A recurring textual formula (invocation, regnal year, imprecation)."),
    "RoyalPraiseFormula": (EZ.Formula, "Royal praise (meykkīrtti)", "The incipit of a king's meykkīrtti, which identifies the king."),
    "Place": (CRM.E53_Place, "Place", "A place named in an inscription or its DHARMA title."),
    "AdministrativeUnit": (EZ.Place, "Administrative unit", "A unit of the territorial hierarchy (ūr, nāṭu, kōṭṭam, vaḷanāṭu, maṇṭalam)."),
    "Ur": (EZ.AdministrativeUnit, "ūr (village)", "Village."),
    "Caturvedimangalam": (EZ.AdministrativeUnit, "caturvēdimaṅkalam", "Brahmin village (brahmadeya) governed by a sabhā."),
    "Nadu": (EZ.AdministrativeUnit, "nāṭu", "District of villages."),
    "Kurram": (EZ.AdministrativeUnit, "kūṟṟam", "District (Cōḻa/Pāṇḍya country)."),
    "Kottam": (EZ.AdministrativeUnit, "kōṭṭam", "Division of Toṇṭaimaṇṭalam above the nāṭu."),
    "Valanadu": (EZ.AdministrativeUnit, "vaḷanāṭu", "Cōḻa division above the nāṭu."),
    "Mandalam": (EZ.AdministrativeUnit, "maṇṭalam", "Province."),
    "Temple": (CRM["E22_Human-Made_Object"], "Temple", "A temple (or cave shrine) carrying inscriptions."),
    "Deity": (CRM.E28_Conceptual_Object, "Deity", "A deity to whom a temple or gift is dedicated."),
    "Grant": (CRM.E7_Activity, "Grant", "A gift or endowment recorded by an inscription."),
    "GrantType": (CRM.E55_Type, "Grant type", "Kind of grant (dēvatāṉam, brahmadēyam, paḷḷiccantam, ...)."),
    "Assembly": (CRM.E74_Group, "Assembly", "A local corporate body (sabhai, ūr, nakaram, nāṭṭār, vāriyam)."),
    "Measure": (CRM.E58_Measurement_Unit, "Measure", "A unit of weight, capacity or land."),
    "Coin": (CRM.E58_Measurement_Unit, "Coin", "A coin or currency unit (kācu, poṉ, ...)."),
    "Tax": (CRM.E55_Type, "Tax or due", "A tax, due or obligation (iṟai, kaṭamai, veṭṭi, ...)."),
}
UNIT_CLASS = {
    "ur": "Ur", "caturvedimangalam": "Caturvedimangalam", "nadu": "Nadu", "kurram": "Kurram",
    "kottam": "Kottam", "valanadu": "Valanadu", "mandalam": "Mandalam",
}  # fmt: skip
KIND_CLASS = {
    "script_stage": "ScriptStage", "letter": "Letter", "dynasty": "Dynasty", "ruler": "Ruler", "title": "Title",
    "formula": "Formula", "place": "Place", "admin_unit": "AdministrativeUnit", "temple": "Temple", "deity": "Deity",
    "grant_type": "GrantType", "assembly": "Assembly", "measure": "Measure", "coin": "Coin", "tax": "Tax",
}  # fmt: skip

# property -> (domain, range, superproperty or None, label)
OBJECT_PROPERTIES: dict[str, tuple[URIRef, URIRef, URIRef | None, str]] = {
    "attestedIn": (OWL.Thing, EZ.Inscription, None, "attested in"),
    "mentions": (EZ.Inscription, OWL.Thing, CRM.P67_refers_to, "mentions"),
    "hasLine": (EZ.Inscription, EZ.Line, CRM.P106_is_composed_of, "has line"),
    "hasEdition": (EZ.Inscription, EZ.Edition, EPONT.hasEdition, "has edition"),
    "writtenIn": (EZ.Inscription, EZ.ScriptStage, None, "written in script stage"),
    "letterOf": (EZ.Letter, EZ.ScriptStage, None, "letter of script stage"),
    "memberOfDynasty": (EZ.Ruler, EZ.Dynasty, None, "member of dynasty"),
    "hasMember": (EZ.Dynasty, EZ.Ruler, CRM.P107_has_current_or_former_member, "has member"),
    "bearsTitle": (EZ.Ruler, EZ.Title, CRM.P1_is_identified_by, "bears title"),
    "titleOfDynasty": (EZ.Title, EZ.Dynasty, None, "title used by dynasty"),
    "praiseOf": (EZ.Formula, EZ.Ruler, None, "praise formula of"),
    "formulaOfDynasty": (EZ.Formula, EZ.Dynasty, None, "formula used by dynasty"),
    "fallsWithin": (EZ.Place, EZ.Place, CRM.P89_falls_within, "falls within"),
    "locatedAt": (EZ.Temple, EZ.Place, CRM.P55_has_current_location, "located at"),
    "dedicatedTo": (EZ.Temple, EZ.Deity, None, "dedicated to"),
    "grantType": (EZ.Grant, EZ.GrantType, CRM.P2_has_type, "grant type"),
    "recordsGrant": (EZ.Inscription, EZ.Grant, CRM.P67_refers_to, "records grant"),
    "grantedTo": (EZ.Grant, OWL.Thing, None, "granted to (temple, assembly or person)"),
    "witnessedBy": (EZ.Grant, EZ.Assembly, None, "witnessed or administered by assembly"),
    "paidIn": (EZ.Grant, OWL.Thing, None, "paid in (coin or measure)"),
    "exemptFrom": (EZ.Grant, EZ.Tax, None, "exempt from tax"),
}
DATA_PROPERTIES: dict[str, tuple[URIRef, str]] = {
    "isoValue": (XSD.string, "ISO-15919 value"),
    "glyph": (XSD.string, "Unicode glyph"),
    "era": (XSD.string, "approximate era"),
    "stageOrder": (XSD.integer, "chronological order of the script stage"),
    "attestationCount": (XSD.integer, "number of attestations in the corpus"),
    "corpusCount": (XSD.integer, "letter occurrences in the corpus"),
    "regnalTitle": (XSD.string, "DHARMA header title"),
}


def _iri(eid: str) -> URIRef:
    """``ez:ruler/rajaraja-i`` -> ``https://w3id.org/ezhuthu/ruler/rajaraja-i``."""
    return URIRef(str(EZ) + eid.split(":", 1)[1])


def tbox() -> Graph:
    g = Graph()
    for prefix, ns in (("ez", EZ), ("crm", CRM), ("crmtex", CRMTEX), ("epont", EPONT), ("wd", WD), ("skos", SKOS),
                       ("dcterms", DCTERMS), ("owl", OWL)):
        g.bind(prefix, ns)
    g.add((ONTOLOGY_IRI, RDF.type, OWL.Ontology))
    g.add((ONTOLOGY_IRI, RDFS.label, Literal("Ezhuthu Tamil epigraphy ontology", lang="en")))
    g.add((ONTOLOGY_IRI, DCTERMS.license, URIRef("https://creativecommons.org/licenses/by-sa/4.0/")))
    g.add((ONTOLOGY_IRI, DCTERMS.source, URIRef("https://dharmalekha.info")))
    g.add((ONTOLOGY_IRI, RDFS.comment, Literal(
        "Tamil epigraphy layer over CIDOC CRM, CRMtex and EpOnt (reused by IRI). Instances derived from DHARMA "
        "editions (CC BY 4.0 repositories; file headers declare CC BY-SA 4.0) and curated seed lists.", lang="en")))
    for ext in (URIRef("http://www.cidoc-crm.org/cidoc-crm/"), URIRef("http://www.cidoc-crm.org/crmtex/"),
                URIRef("https://w3id.org/epont/ontology/")):
        g.add((ONTOLOGY_IRI, RDFS.seeAlso, ext))
    for name, (sup, label, comment) in CLASSES.items():
        c = EZ[name]
        g.add((c, RDF.type, OWL.Class))
        g.add((c, RDFS.subClassOf, sup))
        g.add((c, RDFS.label, Literal(label, lang="en")))
        g.add((c, RDFS.comment, Literal(comment, lang="en")))
        g.add((c, RDFS.isDefinedBy, ONTOLOGY_IRI))
    for name, (dom, rng, sup, label) in OBJECT_PROPERTIES.items():
        p = EZ[name]
        g.add((p, RDF.type, OWL.ObjectProperty))
        if dom != OWL.Thing:
            g.add((p, RDFS.domain, dom))
        if rng != OWL.Thing:
            g.add((p, RDFS.range, rng))
        if sup is not None:
            g.add((p, RDFS.subPropertyOf, sup))
        g.add((p, RDFS.label, Literal(label, lang="en")))
        g.add((p, RDFS.isDefinedBy, ONTOLOGY_IRI))
    g.add((EZ.memberOfDynasty, OWL.inverseOf, EZ.hasMember))
    for name, (rng, label) in DATA_PROPERTIES.items():
        p = EZ[name]
        g.add((p, RDF.type, OWL.DatatypeProperty))
        g.add((p, RDFS.range, rng))
        g.add((p, RDFS.label, Literal(label, lang="en")))
    return g


def build_graph(
    lookups: dict[str, list[dict]], inscriptions: dict[str, dict], url_tmpl: str,
    attestations: dict[str, set[str]] | None = None,
) -> Graph:
    """``attestations`` maps entity id -> all attesting inscription ids (lookups cap attested_in)."""
    g = tbox()
    for kind, recs in lookups.items():
        for r in recs:
            s = _iri(r["id"])
            cls = KIND_CLASS[kind]
            if kind == "admin_unit" and r.get("unit_type") and not r.get("is_type"):
                cls = UNIT_CLASS.get(r["unit_type"], cls)
            if kind == "formula" and r.get("ruler"):
                cls = "RoyalPraiseFormula"
            g.add((s, RDF.type, OWL.NamedIndividual))
            g.add((s, RDF.type, EZ[cls]))
            g.add((s, SKOS.prefLabel, Literal(r["label_iso"], lang="ta-Latn")))
            if r.get("label_ta"):
                g.add((s, SKOS.altLabel, Literal(r["label_ta"], lang="ta")))
            if r.get("label_en"):
                g.add((s, SKOS.altLabel, Literal(r["label_en"], lang="en")))
            for v in r.get("variants") or []:
                g.add((s, SKOS.hiddenLabel, Literal(v, lang="ta-Latn")))
            if r.get("era"):
                g.add((s, EZ.era, Literal(r["era"])))
            if r.get("wikidata"):
                g.add((s, SKOS.exactMatch, WD[r["wikidata"]]))
            if r.get("note"):
                g.add((s, SKOS.scopeNote, Literal(r["note"], lang="en")))
            g.add((s, EZ.attestationCount, Literal(r.get("attestation_count", 0), datatype=XSD.integer)))
            all_ins = (attestations or {}).get(r["id"]) or {a.split(":")[0] for a in r["attested_in"]}
            for ins_id in sorted(all_ins):
                g.add((s, EZ.attestedIn, EZ["inscription/" + ins_id]))
            b = r.get("broader")
            if kind == "ruler" and r.get("dynasty"):
                g.add((s, EZ.memberOfDynasty, _iri(r["dynasty"])))
            elif kind == "title" and r.get("dynasty"):
                g.add((s, EZ.titleOfDynasty, _iri(r["dynasty"])))
            elif kind == "formula":
                if r.get("ruler"):
                    g.add((s, EZ.praiseOf, _iri(r["ruler"])))
                if r.get("dynasty"):
                    g.add((s, EZ.formulaOfDynasty, _iri(r["dynasty"])))
            elif kind in ("place", "admin_unit") and b:
                g.add((s, EZ.fallsWithin, _iri(b)))
            elif kind == "temple":
                if b:
                    g.add((s, EZ.locatedAt, _iri(b)))
                if r.get("deity"):
                    g.add((s, EZ.dedicatedTo, _iri(r["deity"])))
            elif kind == "letter":
                g.add((s, EZ.letterOf, _iri(b)))
                for v in r.get("iso_values") or [r["label_iso"]]:
                    g.add((s, EZ.isoValue, Literal(v)))
                if r.get("glyph"):
                    g.add((s, EZ.glyph, Literal(r["glyph"])))
                g.add((s, EZ.corpusCount, Literal(r.get("corpus_count", 0), datatype=XSD.integer)))
            elif kind == "script_stage" and r.get("order"):
                g.add((s, EZ.stageOrder, Literal(r["order"], datatype=XSD.integer)))
    for ins_id, m in sorted(inscriptions.items()):
        s = EZ["inscription/" + ins_id]
        g.add((s, RDF.type, OWL.NamedIndividual))
        g.add((s, RDF.type, EZ.Inscription))
        g.add((s, RDFS.label, Literal(m["title"])))
        g.add((s, DCTERMS.identifier, Literal(ins_id)))
        g.add((s, DCTERMS.source, URIRef(url_tmpl.format(ins_id))))
        g.add((s, DCTERMS.isPartOf, Literal(m["collection"])))
        for st in m["stages"]:
            g.add((s, EZ.writtenIn, EZ["script_stage/" + st]))
        for eid in m["mentions"]:
            g.add((s, EZ.mentions, _iri(eid)))
    return g
