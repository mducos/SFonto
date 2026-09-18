import sys
from rdflib import Graph, RDF, RDFS, OWL, URIRef

VISITED = set()


def get_named_classes(g: Graph):
    return {c for c in g.subjects(RDF.type, OWL.Class) if isinstance(c, URIRef)}


def load_with_imports(path_or_url: str, graph: Graph, follow_imports: bool = True, depth: int = 0):
    if path_or_url in VISITED:
        return
    VISITED.add(path_or_url)

    indent = "  " * depth
    print(f"{indent}→ Download : {path_or_url}")

    g = Graph()
    last_error = None
    loaded = False
    for fmt in ("turtle", "xml", "n3", "nt"):
        try:
            g.parse(path_or_url, format=fmt)
            loaded = True
            break
        except Exception as e:
            last_error = e
            g = Graph()
    if not loaded:
        print(f"{indent}  Loading FAILED; all formats tested ({last_error})")
        return

    graph += g
    print(f"{indent}  {len(g)} triplets added (cumulative total: {len(graph)})")

    if follow_imports:
        for imp in g.objects(None, OWL.imports):
            load_with_imports(str(imp), graph, follow_imports, depth + 1)


def inheritance_richness(g: Graph):
    classes = get_named_classes(g)
    if not classes:
        return 0.0, 0, 0
    total_subclasses = 0
    for c in classes:
        subs = set(g.subjects(RDFS.subClassOf, c)) & classes
        total_subclasses += len(subs)
    return total_subclasses / len(classes), total_subclasses, len(classes)


def relationship_richness(g: Graph):
    object_properties = set(g.subjects(RDF.type, OWL.ObjectProperty))
    data_properties = set(g.subjects(RDF.type, OWL.DatatypeProperty))
    non_taxonomic = len(object_properties) + len(data_properties)

    classes = get_named_classes(g)
    subclass_relations = 0
    for c in classes:
        subclass_relations += len(set(g.subjects(RDFS.subClassOf, c)) & classes)

    denom = subclass_relations + non_taxonomic
    rr = non_taxonomic / denom if denom > 0 else 0.0
    return rr, non_taxonomic, subclass_relations


def attribute_richness(g: Graph):
    data_properties = set(g.subjects(RDF.type, OWL.DatatypeProperty))
    classes = get_named_classes(g)
    ar = len(data_properties) / len(classes) if classes else 0.0
    return ar, len(data_properties), len(classes)


def class_relation_ratio(g: Graph):
    classes = get_named_classes(g)
    object_properties = set(g.subjects(RDF.type, OWL.ObjectProperty))
    ratio = len(classes) / len(object_properties) if object_properties else float("inf")
    return ratio, len(classes), len(object_properties)


def average_population(g: Graph):
    classes = get_named_classes(g)
    individuals = set()
    for c in classes:
        individuals |= set(g.subjects(RDF.type, c))
    ap = len(individuals) / len(classes) if classes else 0.0
    return ap, len(individuals), len(classes)


def dl_expressivity_hint(g: Graph):
    hints = []
    if len(set(g.subjects(RDF.type, OWL.TransitiveProperty))) > 0:
        hints.append("transitive properties (S)")
    if len(set(g.subjects(RDF.type, OWL.FunctionalProperty))) > 0:
        hints.append("functional properties (F)")
    if len(set(g.triples((None, OWL.inverseOf, None)))) > 0:
        hints.append("inverse properties (I)")
    if len(set(g.subjects(RDF.type, OWL.SymmetricProperty))) > 0:
        hints.append("symmetric properties")
    if len(set(g.triples((None, OWL.minCardinality, None)))) + \
       len(set(g.triples((None, OWL.maxCardinality, None)))) + \
       len(set(g.triples((None, OWL.cardinality, None)))) > 0:
        hints.append("unqualified cardinalities (N)")
    if len(set(g.triples((None, OWL.minQualifiedCardinality, None)))) + \
       len(set(g.triples((None, OWL.maxQualifiedCardinality, None)))) > 0:
        hints.append("qualified cardinalities (Q)")
    if len(set(g.subjects(RDF.type, OWL.DatatypeProperty))) > 0:
        hints.append("data types (D)")
    return hints


def main():
    args = sys.argv[1:]
    follow_imports = "--no-imports" not in args
    files = [a for a in args if a != "--no-imports"]
    source = files[0] if files else "SFonto.ttl"

    print(f"Import Resolution : {'ENABLED' if follow_imports else 'DISABLED'}\n")

    graph = Graph()
    load_with_imports(source, graph, follow_imports=follow_imports)

    all_class_nodes = set(graph.subjects(RDF.type, OWL.Class))
    named = get_named_classes(graph)
    anon = all_class_nodes - named

    print(f"\nFinal graph: {len(graph)} triplets, "
          f"{len(VISITED)} file(s) loaded")
    print(f"""Classes: {len(named)} named classes + {len(anon)} anonymous classes
          (restriction/union/intersection expressions, excluded from the metrics below)\n""")

    print("=" * 60)
    print("ONTOQA METRICS")
    print("=" * 60)

    ir, total_sub, n_classes = inheritance_richness(graph)
    print(f"\nInheritance Richness (IR)     : {ir:.3f}")
    print(f"  -> {total_sub} direct subClassOf relationships / {n_classes} classes")

    rr, non_tax, sub_rel = relationship_richness(graph)
    print(f"\nRelationship Richness (RR)    : {rr:.3f}")
    print(f"  -> {non_tax} non-taxonomic properties / ({sub_rel} is-a relations + {non_tax} properties)")

    ar, n_dp, n_cls = attribute_richness(graph)
    print(f"\nAttribute Richness (AR)       : {ar:.3f}")
    print(f"  -> {n_dp} data properties / {n_cls} classes")

    ratio, n_c, n_op = class_relation_ratio(graph)
    print(f"\nClass/Relation Ratio          : {ratio:.3f}")
    print(f"  -> {n_c} classes / {n_op} object properties")

    ap, n_ind, n_cls2 = average_population(graph)
    print(f"\nAverage Population            : {ap:.3f}")
    print(f"  -> {n_ind} individuals / {n_cls2} classes")

    print(f"\nDetected DL Constructions    : {', '.join(dl_expressivity_hint(graph)) or 'none'}")

if __name__ == "__main__":
    main()