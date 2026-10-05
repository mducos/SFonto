"""Module Metadata de SFonto : génère un TTL par récit à partir de metadata_complete.json.

Sortie : <out-dir>/<clé>/<clé>.ttl
Champs ignorés volontairement : nb_tokens (sauf pour déduire le type), src, disciplines.

Usage :
    python metadata_module.py --metadata metadata_complete.json \
        --ontology src/SFonto.ttl --out-dir data
"""
import argparse
import json
import re
import sys
from pathlib import Path

from rdflib import RDF, RDFS, XSD, Graph, Literal, Namespace, URIRef

CRM = Namespace("http://www.cidoc-crm.org/cidoc-crm/")
DC = Namespace("http://purl.org/dc/elements/1.1/")
DCTERMS = Namespace("http://purl.org/dc/terms/")
GC = Namespace("https://w3id.org/golem/ontology#")
LRM = Namespace("http://iflastandards.info/ns/lrm/lrmoo/")
SF = Namespace("https://w3id.org/ontosf/ontology#")

UNKNOWN = "unknown"

# SPÉCIFIQUE À CE CORPUS : tous les titres et sous-titres sont en français, donc
# les littéraux dcterms:title / dcterms:alternative sont toujours balisés @fr.
# À rendre dynamique (selon le champ "language") si le corpus devient multilingue.
TEXT_LANG = "fr"

NARRATORS = {1: "first_person", 2: "second_person", 3: "third_person"}

HEADER = """\
@prefix crm: <http://www.cidoc-crm.org/cidoc-crm/> .
@prefix dc: <http://purl.org/dc/elements/1.1/> .
@prefix dcterms: <http://purl.org/dc/terms/> .
@prefix dlpcom: <http://www.ontologydesignpatterns.org/ont/dlp/CommonSenseMapping.owl#> .
@prefix dlpext: <http://www.ontologydesignpatterns.org/ont/dlp/ExtendedDnS.owl#> .
@prefix dlpfun: <http://www.ontologydesignpatterns.org/ont/dlp/FunctionalParticipation.owl#> .
@prefix dlpspa: <http://www.ontologydesignpatterns.org/ont/dlp/SpatialRelations.owl#> .
@prefix dlptem: <http://www.ontologydesignpatterns.org/ont/dlp/TemporalRelations.owl#> .
@prefix dolce: <http://www.ontologydesignpatterns.org/ont/dlp/DOLCE-Lite.owl#> .
@prefix dul: <http://www.ontologydesignpatterns.org/ont/dul/DUL.owl#> .
@prefix gc: <https://w3id.org/golem/ontology#> .
@prefix lrm: <http://iflastandards.info/ns/lrm/lrmoo/> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix schema: <https://schema.org/> .
@prefix sf: <https://w3id.org/ontosf/ontology#> .
@prefix vann: <http://purl.org/vocab/vann/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

<https://w3id.org/ontosf/data> a owl:Ontology ;
    dc:created "2026-10-01"^^xsd:date ;
    dc:creator "Mathilde Ducos" ;
    dc:license <https://creativecommons.org/licenses/by/4.0/> ;
    dc:title "SFonto" ;
    dcterms:bibliographicCitation "" ;
    dcterms:created "2026-10-01"^^xsd:date ;
    dcterms:creator "Mathilde Ducos" ;
    dcterms:hasVersion "0.1.0" ;
    dcterms:identifier <https://w3id.org/ontosf/ontology> ;
    dcterms:issued "2026-10-01"^^xsd:date ;
    dcterms:license <https://creativecommons.org/licenses/by/4.0/> ;
    dcterms:publisher "" ;
    dcterms:status "unstable" ;
    vann:preferredNamespacePrefix "sf" ;
    vann:preferredNamespaceUri "https://w3id.org/ontosf/ontology#" ;
    rdfs:comment "SFonto is an ontology for the content of science-fiction narratives, adapted from the GOLEM ontology. This knowledge graph has been generated for the story '[title]' from '[author]'."@en ;
    owl:imports <https://w3id.org/ontosf/ontology> ;
    owl:versionIRI <https://w3id.org/ontosf/data/> .
"""


def clean(value):
    """Valeur JSON -> chaîne nettoyée ('' si vide)."""
    return "" if value is None else str(value).strip()


def ttl_escape(text):
    return text.replace("\\", "\\\\").replace('"', '\\"')


def slugify_feature(name):
    return re.sub(r"\s+", "_", name.strip().lower())


def work_slug(key):
    """Capus_LHommeBicycle_1893 -> Capus_LHommeBicycle (retire seulement l'année)."""
    parts = key.split("_")
    if len(parts) < 3:
        raise ValueError(f"clé inattendue (attendu Auteur_Titre_Année) : {key!r}")
    return "_".join(parts[:-1])


def work_type(nb_tokens):
    """short story < 17000 <= novella < 40000 <= novel."""
    n = int(nb_tokens)
    if n < 17000:
        return SF.type_short_story
    if n < 40000:
        return SF.type_novella
    return SF.type_novel


def load_vocabulary(ontology_path):
    g = Graph().parse(ontology_path)
    return {s for s in g.subjects() if isinstance(s, URIRef) and str(s).startswith(str(SF))}


def build(key, rec, slug):
    """Retourne (graphe, titre, auteur, erreurs de construction)."""
    errors = []
    g = Graph()
    for prefix, ns in (("crm", CRM), ("dc", DC), ("dcterms", DCTERMS), ("gc", GC),
                       ("lrm", LRM), ("sf", SF), ("xsd", XSD), ("rdfs", RDFS)):
        g.bind(prefix, ns)

    work, expr = SF[f"Work_{slug}"], SF[f"Expr_FR_{slug}"]

    title = clean(rec.get("title")) or UNKNOWN
    subtitle = clean(rec.get("subtitle"))
    author = clean(rec.get("author")) or UNKNOWN
    date = clean(rec.get("date"))
    language = clean(rec.get("language"))

    # --- F1 Work ---
    g.add((work, RDF.type, LRM.F1_Work))
    g.add((work, RDFS.label, Literal(f"{title} (work)")))  # sans balise de langue
    if subtitle:
        g.add((work, DCTERMS.alternative, Literal(subtitle, lang=TEXT_LANG)))
    g.add((work, DCTERMS.creator, Literal(author)))
    g.add((work, DCTERMS.title, Literal(title, lang=TEXT_LANG)))
    g.add((work, CRM.P2_has_type, work_type(rec["nb_tokens"])))

    for genre in rec.get("genres") or []:
        g.add((work, GC.GP0_has_feature, SF[f"Feature_{slugify_feature(genre)}_genre"]))
    for register in rec.get("registers") or []:
        g.add((work, GC.GP0_has_feature, SF[f"Feature_{slugify_feature(register)}_register"]))
    for n in rec.get("narrative") or []:
        if n not in NARRATORS:
            errors.append(f"valeur de narrative inconnue : {n!r}")
            continue
        g.add((work, GC.GP0_has_feature, SF[f"Feature_{NARRATORS[n]}_narrator"]))

    # --- F2 Expression ---
    g.add((expr, RDF.type, LRM.F2_Expression))
    g.add((expr, RDFS.label, Literal(f"French Expression of {title}")))  # sans balise de langue
    g.add((expr, LRM.R3i_realises, work))
    g.add((expr, DC.language, Literal(language)))
    if re.fullmatch(r"\d{4}", date):
        g.add((expr, DCTERMS.issued, Literal(date, datatype=XSD.gYear)))
    elif not date:
        g.add((expr, DCTERMS.issued, Literal(UNKNOWN)))
    else:
        errors.append(f"date non convertible en année : {date!r}")
    g.add((expr, CRM.P2_has_type, SF.type_written_text))  # tout le corpus
    return g, work, expr, title, author, errors


def validate(g, work, expr, vocab):
    errors = []
    f1s = set(g.subjects(RDF.type, LRM.F1_Work))
    for f1 in f1s:
        if not any(g.triples((None, LRM.R3i_realises, f1))):
            errors.append(f"{f1} : aucune F2 associée")
        for prop, name in ((DCTERMS.title, "titre"), (DCTERMS.creator, "auteur")):
            if not any(g.triples((f1, prop, None))):
                errors.append(f"{f1} : {name} manquant")
    for f2 in g.subjects(RDF.type, LRM.F2_Expression):
        if not any(g.triples((f2, DCTERMS.issued, None))):
            errors.append(f"{f2} : date manquante")
    # Tout IRI sf: utilisé (type, feature...) doit exister dans SFonto.ttl
    for o in set(g.objects()):
        if isinstance(o, URIRef) and str(o).startswith(str(SF)) and o not in (work, expr):
            if o not in vocab:
                errors.append(f"absent du vocabulaire SFonto.ttl : {o}")
    return errors


def render(g, title, author):
    body = g.serialize(format="turtle")
    body = "\n".join(l for l in body.splitlines() if not l.startswith("@prefix")).strip()
    header = HEADER.replace("[title]", ttl_escape(title)).replace("[author]", ttl_escape(author))
    text = f"{header}\n{body}\n"
    Graph().parse(data=text, format="turtle")  # contrôle de syntaxe
    return text


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--metadata", default="src/metadata_complete.json")
    ap.add_argument("--ontology", default="src/SFonto.ttl")
    ap.add_argument("--out-dir", default="data")
    args = ap.parse_args()

    metadata = json.loads(Path(args.metadata).read_text(encoding="utf-8"))
    vocab = load_vocabulary(args.ontology)

    failures, seen_slugs, written = {}, {}, 0
    for key, rec in metadata.items():
        try:
            slug = work_slug(key)
            if slug in seen_slugs:
                failures.setdefault(key, []).append(f"collision d'IRI Work_{slug} avec {seen_slugs[slug]}")
                continue
            seen_slugs[slug] = key
            g, work, expr, title, author, errs = build(key, rec, slug)
            errs += validate(g, work, expr, vocab)
            if errs:
                failures[key] = errs
                continue
            out = Path(args.out_dir) / key / f"{key}.ttl"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(render(g, title, author), encoding="utf-8")
            written += 1
        except Exception as exc:  # une clé défaillante ne bloque pas les autres
            failures.setdefault(key, []).append(f"{type(exc).__name__}: {exc}")

    print(f"{written}/{len(metadata)} fichiers écrits dans {args.out_dir}/")
    for key, errs in failures.items():
        print(f"\n[ÉCHEC] {key}")
        for e in errs:
            print(f"  - {e}")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()