import argparse
import datetime
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
 
import openpyxl
from rdflib import Graph, Literal, Namespace, RDF, RDFS, URIRef
from rdflib.namespace import XSD
 
# ======================================================================
# 1. NAMESPACES  (à recopier depuis l'en-tête habituel de vos .ttl)
# ======================================================================
 
PREFIXES: Dict[str, str] = {
    "sf": "https://w3id.org/ontosf/ontology#",
    "dc": "http://purl.org/dc/elements/1.1/",
    "gc": "https://w3id.org/golem/ontology#",
    "vs": "http://www.w3.org/2003/06/sw-vocab-status/ns#",
    "dlpext": "http://www.ontologydesignpatterns.org/ont/dlp/ExtendedDnS.owl#",
    "dlpcom": "http://www.ontologydesignpatterns.org/ont/dlp/CommonSenseMapping.owl#",
    "dlpspa": "http://www.ontologydesignpatterns.org/ont/dlp/SpatialRelations.owl#",
    "dlptem": "http://www.ontologydesignpatterns.org/ont/dlp/TemporalRelations.owl#",
    "dlpfun": "http://www.ontologydesignpatterns.org/ont/dlp/FunctionalParticipation.owl#",
    "owl": "http://www.w3.org/2002/07/owl#",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "xsd": "http://www.w3.org/2001/XMLSchema#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "skos": "http://www.w3.org/2004/02/skos/core#",
    "vann": "http://purl.org/vocab/vann/",
    "dcterms": "http://purl.org/dc/terms/",
    "crm": "http://www.cidoc-crm.org/cidoc-crm/",
    "schema": "https://schema.org/",
    "lrmoo": "http://iflastandards.info/ns/lrm/lrmoo/",
    "dul": "http://www.ontologydesignpatterns.org/ont/dul/DUL.owl#",
    "dolce": "http://www.ontologydesignpatterns.org/ont/dlp/DOLCE-Lite.owl#",
    "xml": "http://www.w3.org/XML/1998/namespace",
}
 
DEFAULT_NS_PREFIX = "sf"  # namespace résolu pour toute valeur ":Xxx"
 
# ======================================================================
# 2. MÉTADONNÉES DU BLOC owl:Ontology répété en tête de chaque fichier
#    (constantes observées dans l'exemple ; à ajuster si besoin)
# ======================================================================
 
ONTOLOGY_METADATA = {
    "data_iri": "https://w3id.org/ontosf/data",
    "version_iri": "https://w3id.org/ontosf/data/",
    "imports": "https://w3id.org/ontosf/ontology",
    "creator": "Mathilde Ducos",
    "license": "https://creativecommons.org/licenses/by/4.0/",
    "title": "SFonto",
    "version": "0.1.0",
    "status": "unstable",
    "comment": (
        "SFonto is an ontology for the content of science-fiction "
        "narratives, adapted from the GOLEM ontology."
    ),
}
 
# ======================================================================
# 3. CLASS_MAP : "valeur de la colonne Class" -> classe RDF (curie)
#    /!\ Table à COMPLÉTER si de nouvelles classes apparaissent.
# ======================================================================
 
CLASS_MAP: Dict[str, str] = {
    "F1_Work": "lrmoo:F1_Work",
    "F2_Expression": "lrmoo:F2_Expression",
    "H3_Human_Character": "sf:H3_Human_Character",
    "H4_Non_Human_Character": "sf:H4_Non-human_Character",
    "H5_Personality_Assignment": "sf:H5_Personality_Assignment",
    "H7_Relationship_Assignment": "sf:H7_Relationship_Assignment",
    "G16_Object": "gc:G16_Object",
    "H1_Conceptual_Novum": "sf:H1_Conceptual_Novum",   # cf. avertissement (6) plus haut
    "H2_Concrete_Novum": "sf:H2_Concrete_Novum",        # cf. avertissement (6) plus haut
    "E28_Conceptual_Object": "crm:E28_Conceptual_Object",
    "Organization": "dul:Organization",
    "Community": "dul:Community",
    "Group": "dul:Group",
    "G12_Setting": "gc:G12_Setting",
    "G13_Narrative_Location": "gc:G13_Narrative_Location",
    "Geographical_Place": "dlpcom:geographical-place",
    "Time_Interval": "dolce:time-interval",
    "G5 Narrative Event": "gc:G5_Narrative_Event",
    "G5_Narrative_Event": "gc:G5_Narrative_Event",
    "G9 Narrative Unit": "gc:G9_Narrative_Unit",
    "G9_Narrative_Unit": "gc:G9_Narrative_Unit",
    "G3_Psychological_State": "gc:G3_Psychological_State",
    "G0_Character-Stoff": "gc:G0_Character-Stoff",
    "G14_Narrative-Stoff": "gc:G14_Narrative-Stoff",
    "G7_Narrative_Sequence": "gc:G7_Narrative_Sequence",
}
 
# ======================================================================
# 4. Prédicats déjà "prêts à l'emploi" par feuille : en-tête de colonne
#    -> prédicat RDF complet (curie). /!\ Table à COMPLÉTER au besoin.
#    Les colonnes "E55 Type"/"E55 Types" sont traitées à part (§6).
# ======================================================================
 
COLUMN_PREDICATE: Dict[str, Dict[str, str]] = {
    "Characters": {
        "GP1 is character in": "gc:GP1_is_character_in",
        "setting": "dlpext:setting",
        "plays": "dlpext:plays",
        "uses": "dlpext:uses",
        "HP9i is personality of": "sf:HP9i_is_personality_of",
        "HP7 has facet": "sf:HP7_has_facet",
        "HP8 has valence": "sf:HP8_has_valence",
    },
    "Objects": {
        "P67i is referred to": "crm:P67i_is_referred_to_by",
        "setting": "dlpext:setting",
    },
    "Organizations": {
        "has member": "dul:hasMember",
        "has location": "dul:hasLocation",
        "P67i is referred to by": "crm:P67i_is_referred_to_by",
    },
    "Settings": {
        "P67 refers to": "crm:P67_refers_to",
        "proper part": "dolce:proper-part",
    },
    "Narrative Events": {
        "follows": "dlptem:follows",
        "participant": "dolce:participant",
        "P16 used specific object": "crm:P16_used_specific_object",
        "participant place": "dlpspa:participant-place",
        "temporal location / duration": "dlptem:temporal-location",
        # "sequenced by" : volontairement absente, cf. limite (4) plus haut.
    },
    "Narrative Units": {
        "P67 refers to G5 Narrative Event": "crm:P67_refers_to",
        "plays G10 Narrative Function": "dlpext:plays",
        "proper part of": "dolce:proper-part-of",
    },
    "Relations": {
        "HP11_for_relationship G4_Social_Relationship": "sf:HP11_for_relationship",
        "d-uses G6_Relationship_Role": "dlpext:d-uses",
        "HP12i_is_relation_of G1_Character": "sf:HP12i_is_relation_of",
        "generic dependant on": "dolce:generic-dependant-on",
        "state of": "dlpfun:state-of",
        # "Temporality" : traitée à part, cf. §7 (motif inline "pred obj").
    },
    "Archetypes": {
        "P130i features are also found on": "crm:P130i_features_are_also_found_on",
    },
}
 
# Colonnes dont les valeurs (URI référencées) doivent en plus être
# déclarées comme instances d'une classe donnée, même si elles n'ont
# pas leur propre ligne "Class/Instance URI" ailleurs dans le classeur.
# Ex. : les G4_Social_Relationship ne sont créées nulle part ailleurs
# que par ce lien depuis un H7_Relationship_Assignment.
COLUMN_AUTO_DECLARE: Dict[str, Dict[str, str]] = {
    "Relations": {
        "HP11_for_relationship G4_Social_Relationship": "gc:G4_Social_Relationship",
    },
}
 
# Colonnes "E55 Type" / "E55 Types" par feuille -> systématiquement crm:P2_has_type
E55_TYPE_COLUMNS = {"E55 Type", "E55 Types"}
 
# Colonnes génériques "property"/"value" (Work, Characters) : le nom de
# propriété est déjà écrit dans la cellule, avec ou sans préfixe.
GENERIC_PROPERTY_COLUMNS = {("Property", "Value"), ("property", "value")}
 
# Préfixe à ajouter aux noms de propriété SANS ":" rencontrés dans une
# colonne générique property/value (Work) ou "Property" (bloc Work).
PROPERTY_PREFIX_MAP: Dict[str, str] = {
    "P2_has_type": "crm",
    "GP0_has_feature": "gc",
    "satisfied_by": "dlpext",
    "d-uses": "dlpext",
    "R3i_realises": "lrmoo",
    "temporally-overlaps": "dlptem",  # rencontré dans la colonne inline "Temporality"
    "follows": "dlptem",              # idem
}
 
# Colonnes dont la valeur littérale suit une règle particulière
# (langue ou type XSD), indexées par prédicat complet (curie).
LITERAL_RULES: Dict[str, Tuple[Optional[str], Optional[str]]] = {
    # curie: (lang, datatype_curie)
    "dcterms:title": ("fr", None),
    "dcterms:alternative": ("fr", None),
    "dcterms:issued": (None, "xsd:gYear"),
}
 
# Colonnes/valeurs qui doivent être éclatées sur "," même si le résultat
# ne commence pas par ":" (aucune connue pour l'instant -> laisser vide).
FORCE_MULTIVALUE_COLUMNS: set = set()
 
LABEL_LANG = "en"  # langue par défaut de rdfs:label (Work fait exception : dcterms:title est en @fr)
 
 
# ======================================================================
# Fonctions utilitaires
# ======================================================================
 
def curie_to_uriref(curie: str, ns_map: Dict[str, Namespace]) -> URIRef:
    prefix, _, local = curie.partition(":")
    if prefix not in ns_map:
        raise KeyError(
            f"Préfixe inconnu '{prefix}' dans '{curie}'. "
            f"Ajoutez-le à PREFIXES en tête de script."
        )
    return ns_map[prefix][local]
 
 
def resolve_property_name(raw: str) -> str:
    """Renvoie un curie complet pour un nom de propriété éventuellement
    sans préfixe (colonnes génériques Property/Value)."""
    raw = raw.strip()
    if ":" in raw:
        return raw  # déjà préfixé, ex. "dcterms:title", "schema:gender"
    prefix = PROPERTY_PREFIX_MAP.get(raw)
    if not prefix:
        print(
            f"  [!] Propriété inconnue '{raw}' sans préfixe -> "
            f"utilisée telle quelle sous 'sf:'. Ajoutez-la à "
            f"PROPERTY_PREFIX_MAP si ce n'est pas le bon namespace.",
            file=sys.stderr,
        )
        prefix = "sf"
    return f"{prefix}:{raw}"
 
 
def split_multivalue(raw_value: str) -> List[str]:
    """Éclate 'valeurA,\\nvaleurB' -> ['valeurA', 'valeurB'].
    Ne coupe PAS une simple virgule à l'intérieur d'un texte libre : on
    ne split que si toutes les parties, une fois nettoyées, ressemblent
    à des références (commencent par ':') ou si la cellule contient un
    retour à la ligne (signe d'une liste dans ce classeur)."""
    text = str(raw_value)
    if "," not in text:
        return [text.strip()]
    parts = [p.strip().replace("\n", "").replace("\r", "") for p in text.split(",")]
    parts = [p for p in parts if p]
    looks_like_uri_list = all(p.startswith(":") for p in parts)
    has_newline = "\n" in text or "\r" in text
    if looks_like_uri_list or has_newline:
        return parts
    return [text.strip()]
 
 
def slug_to_label(local_name: str, strip_prefix: str = "type_") -> str:
    """'type_short_story' -> 'Short story' ; 'Sequence_Fabula' -> 'Sequence Fabula'"""
    name = local_name
    if strip_prefix and name.startswith(strip_prefix):
        name = name[len(strip_prefix):]
    name = name.replace("_", " ").replace("-", " ")
    name = re.sub(r"\s+", " ", name).strip()
    if not name:
        return name
    return name[0].upper() + name[1:].lower()
 
 
# ======================================================================
# Classe principale de conversion
# ======================================================================
 
class WorkbookConverter:
    def __init__(self, created_date: Optional[str] = None):
        self.g = Graph()
        self.ns: Dict[str, Namespace] = {}
        for prefix, uri in PREFIXES.items():
            ns = Namespace(uri)
            self.ns[prefix] = ns
            self.g.bind(prefix, ns)
        self.default_ns = self.ns[DEFAULT_NS_PREFIX]
        self.created_date = created_date or datetime.date.today().isoformat()
        # NU_URI -> événement référencé (crm:P67_refers_to), pour dériver
        # ensuite dlpext:sequences sur les G7_Narrative_Sequence.
        self._nu_to_event: Dict[URIRef, URIRef] = {}
 
    # ---- résolution de valeurs -----------------------------------
    def resolve_ref(self, token: str) -> URIRef:
        token = token.strip()
        if token.startswith(":"):
            return self.default_ns[token[1:]]
        if ":" in token:
            return curie_to_uriref(token, self.ns)
        return self.default_ns[token]
 
    def make_literal(self, text: str, predicate_curie: str) -> Literal:
        lang, dtype = LITERAL_RULES.get(predicate_curie, (None, None))
        if dtype:
            return Literal(str(text).strip(), datatype=curie_to_uriref(dtype, self.ns))
        if lang:
            return Literal(str(text).strip(), lang=lang)
        return Literal(str(text).strip())
 
    def add_value(self, subject: URIRef, predicate_curie: str, raw_value) -> None:
        if raw_value is None or str(raw_value).strip() == "":
            return
        predicate = curie_to_uriref(predicate_curie, self.ns)
        for part in split_multivalue(raw_value):
            if not part:
                continue
            if part.startswith(":"):
                self.g.add((subject, predicate, self.resolve_ref(part)))
            else:
                self.g.add((subject, predicate, self.make_literal(part, predicate_curie)))
 
    # ---- E55 Type -> rattachement uniquement (jamais de déclaration) --
    def add_e55_type(self, subject: URIRef, raw_value) -> None:
        # Les types E55 sont tous supposés déjà déclarés dans la TBox
        # (SF_ontology.ttl) : on ne crée ici QUE le lien crm:P2_has_type,
        # jamais de triplet `sf:type_xxx a crm:E55_Type ; rdfs:label ...`.
        if raw_value is None or str(raw_value).strip() == "":
            return
        crm = self.ns["crm"]
        for part in split_multivalue(raw_value):
            if not part.startswith(":"):
                continue
            self.g.add((subject, crm.P2_has_type, self.resolve_ref(part)))
 
    # ---- lecture générique d'une feuille "Class/Instance/Label/…" -
    def process_generic_sheet(self, ws, sheet_name: str) -> None:
        rows = list(ws.iter_rows(values_only=True))
        if len(rows) < 2:
            return
        header = [str(h).strip() if h is not None else "" for h in rows[1]]
        col_index = {name: i for i, name in enumerate(header) if name}
 
        try:
            idx_class = col_index["Class"]
            idx_uri = col_index["Instance URI"]
        except KeyError:
            print(f"  [!] Feuille '{sheet_name}' ignorée (pas de colonnes Class/Instance URI).", file=sys.stderr)
            return
        idx_label = col_index.get("Label")
 
        predicate_cols = COLUMN_PREDICATE.get(sheet_name, {})
        generic_pair = next(
            ((col_index[p], col_index[v]) for p, v in GENERIC_PROPERTY_COLUMNS
             if p in col_index and v in col_index),
            None,
        )
        e55_col = next((col_index[c] for c in E55_TYPE_COLUMNS if c in col_index), None)
        temporality_col = col_index.get("Temporality")  # motif inline spécial (Relations)
 
        # Colonnes couvertes par un mécanisme quelconque (prédicat direct,
        # E55 Type, paire générique property/value, ou motif inline).
        accounted = {"Class", "Instance URI", "Label"} | set(predicate_cols)
        accounted |= {c for c in E55_TYPE_COLUMNS if c in col_index}
        if generic_pair is not None:
            accounted |= {p for p, v in GENERIC_PROPERTY_COLUMNS if p in col_index} | \
                         {v for p, v in GENERIC_PROPERTY_COLUMNS if v in col_index}
        if temporality_col is not None:
            accounted.add("Temporality")
        unrecognized = [h for h in header if h and h not in accounted]
        if unrecognized:
            print(f"  [!] Feuille '{sheet_name}' : colonne(s) non reconnue(s), ignorée(s) : "
                  f"{unrecognized}. Ajoutez-les à COLUMN_PREDICATE si elles doivent être converties.",
                  file=sys.stderr)
 
        current_class = current_subject = None
 
        for row in rows[2:]:
            if row is None or all(c is None for c in row):
                continue
 
            raw_class = row[idx_class] if idx_class < len(row) else None
            raw_uri = row[idx_uri] if idx_uri < len(row) else None
            raw_label = row[idx_label] if (idx_label is not None and idx_label < len(row)) else None
 
            if raw_class not in (None, ""):
                current_class = str(raw_class).strip()
            if raw_uri not in (None, ""):
                current_subject = self.resolve_ref(str(raw_uri))
                # La colonne Class peut contenir plusieurs classes séparées
                # par une virgule (et un retour à la ligne), ex.
                # "H3_Human_Character,\nH4_Non_Human_Character".
                class_names = [c.strip() for c in str(current_class).replace("\r", "").replace("\n", "").split(",")]
                class_names = [c for c in class_names if c]
                for class_name in class_names:
                    class_curie = CLASS_MAP.get(class_name)
                    if class_curie is None:
                        print(f"  [!] Classe inconnue '{class_name}' (feuille {sheet_name}) "
                              f"-> ajoutée telle quelle sous 'sf:'. Complétez CLASS_MAP.", file=sys.stderr)
                        class_curie = f"sf:{class_name.replace(' ', '_')}"
                    # déclare le type (peut être appelé plusieurs fois pour la
                    # même instance -> pas de problème, rdflib dédoublonne)
                    self.g.add((current_subject, RDF.type, curie_to_uriref(class_curie, self.ns)))
                if raw_label not in (None, ""):
                    self.g.add((current_subject, RDFS.label, Literal(str(raw_label).strip(), lang=LABEL_LANG)))
 
            if current_subject is None:
                continue  # ligne orpheline (pas encore d'instance courante)
 
            # colonnes à prédicat direct
            for header_name, predicate_curie in predicate_cols.items():
                ci = col_index.get(header_name)
                if ci is None or ci >= len(row):
                    continue
                self.add_value(current_subject, predicate_curie, row[ci])
                # certaines colonnes déclarent en plus la classe de la
                # ressource qu'elles référencent (ex. G4_Social_Relationship
                # créées uniquement via HP11_for_relationship, sans ligne
                # Class/Instance URI à elles)
                auto_class_curie = COLUMN_AUTO_DECLARE.get(sheet_name, {}).get(header_name)
                if auto_class_curie and row[ci] not in (None, ""):
                    auto_class_uri = curie_to_uriref(auto_class_curie, self.ns)
                    for part in split_multivalue(row[ci]):
                        if part.startswith(":"):
                            self.g.add((self.resolve_ref(part), RDF.type, auto_class_uri))
 
            # colonne(s) E55 Type / E55 Types
            if e55_col is not None and e55_col < len(row):
                self.add_e55_type(current_subject, row[e55_col])
 
            # colonne générique property/value (Characters : schema:gender, schema:birthPlace…)
            if generic_pair is not None:
                pi, vi = generic_pair
                if pi < len(row) and row[pi] not in (None, ""):
                    predicate_curie = resolve_property_name(str(row[pi]))
                    self.add_value(current_subject, predicate_curie, row[vi] if vi < len(row) else None)
 
            # motif inline "Temporality" (Relations) : une ou plusieurs
            # paires ":predicat :objet" séparées par des virgules, ex.
            # ":temporally-overlaps :Event_A,\n:temporally-overlaps :Event_B"
            if temporality_col is not None and temporality_col < len(row):
                raw = row[temporality_col]
                if raw not in (None, ""):
                    for pair in str(raw).split(","):
                        tokens = pair.split()
                        if len(tokens) == 2 and tokens[0].startswith(":") and tokens[1].startswith(":"):
                            pred_curie = resolve_property_name(tokens[0][1:])
                            self.g.add((current_subject, curie_to_uriref(pred_curie, self.ns),
                                        self.resolve_ref(tokens[1])))
                        elif pair.strip():
                            print(f"  [!] Cellule 'Temporality' non reconnue : {pair!r} "
                                  f"(attendu ':predicat :objet').", file=sys.stderr)
 
            # mémorise Narrative Unit -> Narrative Event pour dériver les séquences ensuite
            if sheet_name == "Narrative Units":
                ci = col_index.get("P67 refers to G5 Narrative Event")
                if ci is not None and ci < len(row) and row[ci]:
                    ev = str(row[ci]).strip()
                    if ev.startswith(":"):
                        self._nu_to_event[current_subject] = self.resolve_ref(ev)
 
    # ---- feuille "Work" (générique Property/Value pur) ------------
    def process_work_sheet(self, ws) -> None:
        self.process_generic_sheet(ws, "Work")
 
    # ---- feuille "Narrative Sequences" (rdf:_n + dlpext:sequences) -
    def process_sequences_sheet(self, ws) -> None:
        rows = list(ws.iter_rows(values_only=True))
        if len(rows) < 2:
            return
        header = [str(h).strip() if h is not None else "" for h in rows[1]]
        col_index = {name: i for i, name in enumerate(header) if name}
        idx_class = col_index.get("Classe", col_index.get("Class"))
        idx_uri = col_index["Instance URI"]
        idx_type = next((col_index[c] for c in E55_TYPE_COLUMNS if c in col_index), None)
        idx_rel = col_index["rdf: relation"]
        idx_range = col_index["rdf: range"]
        idx_sequences = col_index.get("sequences")  # colonne explicite optionnelle
 
        rdf_ns = self.ns["rdf"]
        dlpext = self.ns["dlpext"]
        current_subject = None
        current_local = None
        sequence_members: Dict[URIRef, List[URIRef]] = {}
        explicit_sequences: set = set()  # sujets pour lesquels 'sequences' a été renseignée explicitement
 
        for row in rows[2:]:
            if row is None or all(c is None for c in row):
                continue
            raw_class = row[idx_class] if idx_class is not None and idx_class < len(row) else None
            raw_uri = row[idx_uri] if idx_uri < len(row) else None
 
            if raw_uri not in (None, ""):
                current_local = str(raw_uri).strip()
                current_subject = self.resolve_ref(current_local)
                class_curie = CLASS_MAP.get(str(raw_class).strip()) if raw_class else CLASS_MAP.get("G7_Narrative_Sequence")
                self.g.add((current_subject, RDF.type, curie_to_uriref(class_curie, self.ns)))
                # Pas de colonne Label dans cette feuille -> libellé par défaut (cf. limite 2)
                self.g.add((current_subject, RDFS.label,
                            Literal(slug_to_label(current_local.lstrip(":"), strip_prefix=""), lang="en")))
                if idx_type is not None and idx_type < len(row):
                    self.add_e55_type(current_subject, row[idx_type])
                sequence_members[current_subject] = []
 
            if current_subject is None:
                continue
 
            # colonne "sequences" explicite : prioritaire sur la dérivation
            # automatique depuis les Narrative Units (plus fiable).
            if idx_sequences is not None and idx_sequences < len(row) and row[idx_sequences] not in (None, ""):
                explicit_sequences.add(current_subject)
                for part in split_multivalue(row[idx_sequences]):
                    if part.startswith(":"):
                        self.g.add((current_subject, dlpext.sequences, self.resolve_ref(part)))
 
            rel = row[idx_rel] if idx_rel < len(row) else None
            rng = row[idx_range] if idx_range < len(row) else None
            if rel not in (None, "") and rng not in (None, ""):
                rel = str(rel).strip()  # ex. "_1"
                local = rel[1:] if rel.startswith("_") else rel
                self.g.add((current_subject, rdf_ns[f"_{local}"], self.resolve_ref(str(rng))))
                if str(rng).strip().startswith(":"):
                    sequence_members[current_subject].append(self.resolve_ref(str(rng)))
 
        # dérivation dlpext:sequences UNIQUEMENT pour les séquences qui n'ont
        # pas de colonne "sequences" explicite (cf. limite 3 : approximatif,
        # mais documenté — préférez la colonne explicite si possible).
        for seq_subject, nus in sequence_members.items():
            if seq_subject in explicit_sequences:
                continue
            seen: List[URIRef] = []
            for nu_uri in nus:
                event = self._nu_to_event.get(nu_uri)
                if event and event not in seen:
                    seen.append(event)
            for event in seen:
                self.g.add((seq_subject, dlpext.sequences, event))
 
    # ---- métadonnées du fichier ------------------------------------
    def add_ontology_header(self) -> None:
        dc = self.ns["dc"]
        dcterms = self.ns["dcterms"]
        owl = self.ns["owl"]
        vann = self.ns["vann"]
        rdfs = self.ns["rdfs"]
        xsd_date = XSD.date
        data_iri = URIRef(ONTOLOGY_METADATA["data_iri"])
        m = ONTOLOGY_METADATA
 
        self.g.add((data_iri, RDF.type, owl.Ontology))
        self.g.add((data_iri, owl.versionIRI, URIRef(m["version_iri"])))
        self.g.add((data_iri, owl.imports, URIRef(m["imports"])))
        self.g.add((data_iri, dc.created, Literal(self.created_date, datatype=xsd_date)))
        self.g.add((data_iri, dc.creator, Literal(m["creator"])))
        self.g.add((data_iri, dc.license, URIRef(m["license"])))
        self.g.add((data_iri, dc.title, Literal(m["title"])))
        self.g.add((data_iri, dcterms.bibliographicCitation, Literal("")))
        self.g.add((data_iri, dcterms.created, Literal(self.created_date, datatype=xsd_date)))
        self.g.add((data_iri, dcterms.creator, Literal(m["creator"])))
        self.g.add((data_iri, dcterms.hasVersion, Literal(m["version"])))
        self.g.add((data_iri, dcterms.identifier, URIRef(ONTOLOGY_METADATA["imports"])))
        self.g.add((data_iri, dcterms.issued, Literal(self.created_date, datatype=xsd_date)))
        self.g.add((data_iri, dcterms.license, URIRef(m["license"])))
        self.g.add((data_iri, dcterms.publisher, Literal("")))
        self.g.add((data_iri, dcterms.status, Literal(m["status"])))
        self.g.add((data_iri, vann.preferredNamespacePrefix, Literal("sf")))
        self.g.add((data_iri, vann.preferredNamespaceUri, Literal(PREFIXES["sf"])))
        self.g.add((data_iri, rdfs.comment, Literal(m["comment"], lang="en")))
 
    # ---- point d'entrée : convertit tout le classeur ---------------
    def convert(self, xlsx_path: Path) -> Graph:
        wb = openpyxl.load_workbook(xlsx_path, data_only=True)
        self.add_ontology_header()
 
        # ordre important : Narrative Units doit être lue avant Narrative
        # Sequences pour pouvoir dériver dlpext:sequences.
        sheet_order = [
            "Work", "Settings", "Characters", "Objects", "Organizations",
            "Narrative Events", "Narrative Units", "Relations", "Archetypes",
            "Narrative Sequences",
        ]
        available = set(wb.sheetnames)
        for name in sheet_order:
            if name not in available:
                continue
            ws = wb[name]
            if name == "Narrative Sequences":
                self.process_sequences_sheet(ws)
            else:
                self.process_generic_sheet(ws, name)
 
        extra = available - set(sheet_order)
        for name in extra:
            print(f"  [!] Feuille '{name}' non reconnue et ignorée. "
                  f"Ajoutez-la à sheet_order/COLUMN_PREDICATE si besoin.", file=sys.stderr)
 
        return self.g
 
 
def convert_file(xlsx_path: Path, out_dir: Path, created_date: Optional[str]) -> Path:
    converter = WorkbookConverter(created_date=created_date)
    graph = converter.convert(xlsx_path)
    out_path = out_dir / (xlsx_path.stem + ".ttl")
    graph.serialize(destination=str(out_path), format="turtle")
    print(f"[OK] {xlsx_path.name} -> {out_path}  ({len(graph)} triplets)")
    return out_path
 
 
def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("input", type=Path, help="Fichier .xlsx ou dossier de fichiers .xlsx")
    parser.add_argument("-o", "--output", type=Path, default=None,
                         help="Dossier de sortie (défaut : même dossier que l'entrée)")
    parser.add_argument("--created-date", type=str, default=None,
                         help="Date ISO (YYYY-MM-DD) pour dc:created/dcterms:created (défaut : aujourd'hui)")
    args = parser.parse_args()
 
    if not args.input.exists():
        sys.exit(f"Introuvable : {args.input}")
 
    if args.input.is_dir():
        xlsx_files = sorted(args.input.glob("*.xlsx"))
        if not xlsx_files:
            sys.exit(f"Aucun .xlsx trouvé dans {args.input}")
        out_dir = args.output or args.input
        out_dir.mkdir(parents=True, exist_ok=True)
        for f in xlsx_files:
            convert_file(f, out_dir, args.created_date)
    else:
        out_dir = args.output or args.input.parent
        out_dir.mkdir(parents=True, exist_ok=True)
        convert_file(args.input, out_dir, args.created_date)
 
 
if __name__ == "__main__":
    main()