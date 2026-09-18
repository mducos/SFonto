import argparse
import datetime
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
 
import openpyxl
from rdflib import Graph, Literal, Namespace, RDF, RDFS, URIRef
from rdflib.namespace import XSD
 
# 1. NAMESPACES
 
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
    "lrm": "http://iflastandards.info/ns/lrm/lrmoo/",
    "dul": "http://www.ontologydesignpatterns.org/ont/dul/DUL.owl#",
    "dolce": "http://www.ontologydesignpatterns.org/ont/dlp/DOLCE-Lite.owl#",
    "xml": "http://www.w3.org/XML/1998/namespace",
}
 
DEFAULT_NS_PREFIX = "sf"  # namespace resolved for any value ":Xxx"
 
# 2. METADATA FROM THE owl:Ontology BLOCK REPEATED AT THE TOP OF EACH FILE
 
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
 
# 3. CLASS_MAP
 
CLASS_MAP: Dict[str, str] = {
    "F1_Work": "lrm:F1_Work",
    "F2_Expression": "lrm:F2_Expression",
    "H3_Human_Character": "sf:H3_Human_Character",
    "H4_Non-Human_Character": "sf:H4_Non-human_Character",
    "H5_Personality_Assignment": "sf:H5_Personality_Assignment",
    "H7_Relationship_Assignment": "sf:H7_Relationship_Assignment",
    "G16_Object": "gc:G16_Object",
    "H1_Conceptual_Novum": "sf:H1_Conceptual_Novum",
    "H2_Concrete_Novum": "sf:H2_Concrete_Novum",
    "E28_Conceptual_Object": "crm:E28_Conceptual_Object",
    "Organization": "dul:Organization",
    "Community": "dul:Community",
    "Group": "dul:Group",
    "G12_Setting": "gc:G12_Setting",
    "G13_Narrative_Location": "gc:G13_Narrative_Location",
    "Geographical_Place": "dlpcom:geographical-place",
    "Time_Interval": "dolce:time-interval",
    "G5_Narrative_Event": "gc:G5_Narrative_Event",
    "G9_Narrative_Unit": "gc:G9_Narrative_Unit",
    "G3_Psychological_State": "gc:G3_Psychological_State",
    "G0_Character-Stoff": "gc:G0_Character-Stoff",
    "G14_Narrative-Stoff": "gc:G14_Narrative-Stoff",
    "G7_Narrative_Sequence": "gc:G7_Narrative_Sequence",
}
 
# 4. Predicates that are already ready to use
 
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
    },
    "Archetypes": {
        "P130i features are also found on": "crm:P130i_features_are_also_found_on",
    },
}
 
# Columns whose values (referenced URIs) must also be
# declared as instances of a given class, even if they do not
# have their own "Class/Instance URI" row elsewhere in the xlsx.
COLUMN_AUTO_DECLARE: Dict[str, Dict[str, str]] = {
    "Relations": {
        "HP11_for_relationship G4_Social_Relationship": "gc:G4_Social_Relationship",
    },
}
 
# Columns "E55 Type"
E55_TYPE_COLUMNS = {"E55 Type"}
 
# Generic "property"/"value" columns (Work, Characters):
# The property name is already entered in the cell, with or without a prefix.
GENERIC_PROPERTY_COLUMNS = {("Property", "Value"), ("property", "value")}
 
# Prefix to add to property names WITHOUT a "":"" found in a
# generic property/value column (Work) or "Property" (Work block).
PROPERTY_PREFIX_MAP: Dict[str, str] = {
    "P2_has_type": "crm",
    "GP0_has_feature": "gc",
    "satisfied_by": "dlpext",
    "d-uses": "dlpext",
    "R3i_realises": "lrm",
    "temporally-overlaps": "dlptem",
    "follows": "dlptem",
    "precedes": "dlptem",
    "temporally-included-in": "dlptem",
    "temporally-includes": "dlptem",
    "HP3i_novum_introduced_by": "sf",
    "HP4i_is_made_by": "sf",
    "HP5i_is_invented_by": "sf",
    "HP6i_is_discovered_by": "sf",
}
 
# "Inline" columns: the cell itself contains the predicate, not
# just the object (one or more pairs separated by commas).
# - "colon_pred": both tokens in the pair begin with ":"
#   e.g., Temporality -> "":temporally-overlaps :Event_A"
# - "bare_pred": the predicate does NOT have a ":"; only the object has one
#   e.g., Objects/"novum introduced by" -> "HP4i_is_made_by :Lemice-Terrieux"
INLINE_COLUMNS: Dict[str, Dict[str, str]] = {
    "Relations": {"Temporality": "colon_pred"},
    "Objects": {"novum introduced by": "colon_pred"},
}
 
# Columns whose literal values follow a specific rule
# (language or XSD type), indexed by full predicate (curie).
LITERAL_RULES: Dict[str, Tuple[Optional[str], Optional[str]]] = {
    "dcterms:title": ("fr", None),
    "dcterms:alternative": ("fr", None),
    "dcterms:issued": (None, "xsd:gYear"),
}
 
# Columns/values that should be split by "," even if the result
# does not begin with ":"
FORCE_MULTIVALUE_COLUMNS: set = set()
 
LABEL_LANG = "en"  # default language for rdfs:label (Work is an exception: dcterms:title is set to @fr)
 
 
# Utility Functions
 
def curie_to_uriref(curie: str, ns_map: Dict[str, Namespace]) -> URIRef:
    prefix, _, local = curie.partition(":")
    if prefix not in ns_map:
        raise KeyError(
            f"""Unknown prefix '{prefix}' in '{curie}'. Add it to PREFIXES at the top of the script."""
        )
    return ns_map[prefix][local]
 
 
def resolve_property_name(raw: str) -> str:
    raw = raw.strip()
    if ":" in raw:
        return raw
    prefix = PROPERTY_PREFIX_MAP.get(raw)
    if not prefix:
        print(
            f"""  [!] Unknown property '{raw}' without a prefix -> used as-is under 'sf:'. 
            Add it to PROPERTY_PREFIX_MAP if this is not the correct namespace.""",
            file=sys.stderr,
        )
        prefix = "sf"
    return f"{prefix}:{raw}"
 
 
def split_multivalue(raw_value: str) -> List[str]:
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
 
 
# Primary conversion class
 
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
        self._nu_to_event: Dict[URIRef, URIRef] = {}
 
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
 
    def add_e55_type(self, subject: URIRef, raw_value) -> None:
        if raw_value is None or str(raw_value).strip() == "":
            return
        crm = self.ns["crm"]
        for part in split_multivalue(raw_value):
            if not part.startswith(":"):
                continue
            self.g.add((subject, crm.P2_has_type, self.resolve_ref(part)))
 
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
            print(f"  [!] Sheet '{sheet_name}' ignored (no Class/Instance URI columns).", file=sys.stderr)
            return
        idx_label = col_index.get("Label")
 
        predicate_cols = COLUMN_PREDICATE.get(sheet_name, {})
        generic_pair = next(
            ((col_index[p], col_index[v]) for p, v in GENERIC_PROPERTY_COLUMNS
             if p in col_index and v in col_index),
            None,
        )
        e55_col = next((col_index[c] for c in E55_TYPE_COLUMNS if c in col_index), None)
        inline_cols = {
            header_name: mode
            for header_name, mode in INLINE_COLUMNS.get(sheet_name, {}).items()
            if header_name in col_index
        }
 
        accounted = {"Class", "Instance URI", "Label"} | set(predicate_cols)
        accounted |= {c for c in E55_TYPE_COLUMNS if c in col_index}
        if generic_pair is not None:
            accounted |= {p for p, v in GENERIC_PROPERTY_COLUMNS if p in col_index} | \
                         {v for p, v in GENERIC_PROPERTY_COLUMNS if v in col_index}
        accounted |= set(inline_cols)
        unrecognized = [h for h in header if h and h not in accounted]
        if unrecognized:
            print(f"""  [!] Sheet '{sheet_name}': unrecognized column(s), ignored: 
                  {unrecognized}. Add them to COLUMN_PREDICATE if they need to be converted.""",
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
                class_names = [c.strip() for c in str(current_class).replace("\r", "").replace("\n", "").split(",")]
                class_names = [c for c in class_names if c]
                for class_name in class_names:
                    class_curie = CLASS_MAP.get(class_name)
                    if class_curie is None:
                        print(f"""  [!] Unknown class '{class_name}' (sheet {sheet_name})
                              -> added as-is under 'sf:'. Complete CLASS_MAP.""", file=sys.stderr)
                        class_curie = f"sf:{class_name.replace(' ', '_')}"
                    self.g.add((current_subject, RDF.type, curie_to_uriref(class_curie, self.ns)))
                if raw_label not in (None, ""):
                    self.g.add((current_subject, RDFS.label, Literal(str(raw_label).strip(), lang=LABEL_LANG)))
 
            if current_subject is None:
                continue
 
            for header_name, predicate_curie in predicate_cols.items():
                ci = col_index.get(header_name)
                if ci is None or ci >= len(row):
                    continue
                self.add_value(current_subject, predicate_curie, row[ci])
                auto_class_curie = COLUMN_AUTO_DECLARE.get(sheet_name, {}).get(header_name)
                if auto_class_curie and row[ci] not in (None, ""):
                    auto_class_uri = curie_to_uriref(auto_class_curie, self.ns)
                    for part in split_multivalue(row[ci]):
                        if part.startswith(":"):
                            self.g.add((self.resolve_ref(part), RDF.type, auto_class_uri))
 
            if e55_col is not None and e55_col < len(row):
                self.add_e55_type(current_subject, row[e55_col])
 
            if generic_pair is not None:
                pi, vi = generic_pair
                if pi < len(row) and row[pi] not in (None, ""):
                    predicate_curie = resolve_property_name(str(row[pi]))
                    self.add_value(current_subject, predicate_curie, row[vi] if vi < len(row) else None)
 
            for header_name, mode in inline_cols.items():
                ci = col_index.get(header_name)
                if ci is None or ci >= len(row) or row[ci] in (None, ""):
                    continue
                for pair in str(row[ci]).split(","):
                    tokens = pair.split()
                    if len(tokens) != 2:
                        if pair.strip():
                            print(f"""  [!] Cell '{header_name}' not recognized: {pair!r}
                                  (expected a pair of 'predicate object').""", file=sys.stderr)
                        continue
                    pred_token, obj_token = tokens
                    if mode == "colon_pred":
                        if not pred_token.startswith(":") or not obj_token.startswith(":"):
                            print(f"""  [!] Cell '{header_name}' not recognized: {pair!r}
                                  (expected ':predicate :object').""", file=sys.stderr)
                            continue
                        pred_name = pred_token[1:]
                    else:  # bare_pred
                        if pred_token.startswith(":") or not obj_token.startswith(":"):
                            print(f"""  [!] Cell '{header_name}' not recognized: {pair!r}
                                  (expected 'predicate:object').""", file=sys.stderr)
                            continue
                        pred_name = pred_token
                    pred_curie = resolve_property_name(pred_name)
                    self.g.add((current_subject, curie_to_uriref(pred_curie, self.ns),
                                self.resolve_ref(obj_token)))
 
            if sheet_name == "Narrative Units":
                ci = col_index.get("P67 refers to G5 Narrative Event")
                if ci is not None and ci < len(row) and row[ci]:
                    ev = str(row[ci]).strip()
                    if ev.startswith(":"):
                        self._nu_to_event[current_subject] = self.resolve_ref(ev)
 
    # "Work"
    def process_work_sheet(self, ws) -> None:
        self.process_generic_sheet(ws, "Work")
 
    # "Narrative Sequences"
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
        idx_sequences = col_index.get("sequences")
 
        rdf_ns = self.ns["rdf"]
        dlpext = self.ns["dlpext"]
        current_subject = None
        current_local = None
        sequence_members: Dict[URIRef, List[URIRef]] = {}
        explicit_sequences: set = set()
 
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
                self.g.add((current_subject, RDFS.label,
                            Literal(slug_to_label(current_local.lstrip(":"), strip_prefix=""), lang="en")))
                if idx_type is not None and idx_type < len(row):
                    self.add_e55_type(current_subject, row[idx_type])
                sequence_members[current_subject] = []
 
            if current_subject is None:
                continue
 
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
 
    # metadata
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
 
    def convert(self, xlsx_path: Path) -> Graph:
        wb = openpyxl.load_workbook(xlsx_path, data_only=True)
        self.add_ontology_header()
 
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
            print(f"""  [!] Sheet '{name}' not recognized and ignored.
                  Add it to sheet_order/COLUMN_PREDICATE if necessary.""", file=sys.stderr)
 
        return self.g
 
 
def convert_file(xlsx_path: Path, out_dir: Path, created_date: Optional[str]) -> Path:
    converter = WorkbookConverter(created_date=created_date)
    graph = converter.convert(xlsx_path)
    out_path = out_dir / (xlsx_path.stem + ".ttl")
    graph.serialize(destination=str(out_path), format="turtle")
    print(f"[OK] {xlsx_path.name} -> {out_path}  ({len(graph)} triplets)")
    return out_path
 
 
def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("input", type=Path, help=".xlsx file or folder containing .xlsx files")
    parser.add_argument("-o", "--output", type=Path, default=None,
                         help="Output folder (default: same folder as the input)")
    parser.add_argument("--created-date", type=str, default=None,
                         help="ISO date (YYYY-MM-DD) for dc:created/dcterms:created (default: today)")
    args = parser.parse_args()
 
    if not args.input.exists():
        sys.exit(f"Unfindable : {args.input}")
 
    if args.input.is_dir():
        xlsx_files = sorted(args.input.glob("*.xlsx"))
        if not xlsx_files:
            sys.exit(f"No .xlsx found in {args.input}")
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