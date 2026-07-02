import rdflib
from rdflib import RDF, RDFS, OWL, URIRef, Literal, Namespace
import networkx as nx

# ── Namespaces ──────────────────────────────────────────────────────────────
SF   = Namespace("https://w3id.org/ontosf/ontology#")
GOLEM = Namespace("https://w3id.org/golem/ontology#")
CIDOC = Namespace("http://www.cidoc-crm.org/cidoc-crm/")
DLP  = Namespace("http://www.ontologydesignpatterns.org/ont/dlp/")
DUL = Namespace("http://www.ontologydesignpatterns.org/ont/dul/DUL.owl#")

# ── Chargement ──────────────────────────────────────────────────────────────

# 1. Charger data.ttl et récupérer les URIs des instances
data = rdflib.Graph()
data.parse("Capus_LHommeBicycle_1893\Capus_LHommeBicycle_1893.ttl", format="turtle")

# Garder la liste des sujets présents dans data.ttl
# Instances locales = tout URI présent dans data.ttl (sujet OU objet)
instances_locales = set()
for s, p, o in data:
    if isinstance(s, rdflib.URIRef):
        instances_locales.add(str(s))
    if isinstance(o, rdflib.URIRef):
        instances_locales.add(str(o))

print(f"{len(instances_locales)} URIs locaux dans data.ttl")

# 2. Charger les ontologies externes dans un graphe combiné
g = rdflib.Graph()
g += data  # copie data dans g

ONTOLOGIES_EXTERNES = [
    "https://raw.githubusercontent.com/mducos/OntoSF/main/SF_ontology.ttl",
    "https://raw.githubusercontent.com/mducos/OntoSF/main/golem_cleaned.ttl",
]

for url in ONTOLOGIES_EXTERNES:
    try:
        g.parse(url, format="turtle")
    except Exception as e:
        print(f"  Erreur : {e}")

# Suivre aussi les owl:imports déclarés dans data.ttl
for imported_uri in data.objects(None, OWL.imports):
    if str(imported_uri) not in ONTOLOGIES_EXTERNES:
        try:
            print(f"owl:imports : {imported_uri}")
            g.parse(str(imported_uri), format="turtle")
        except Exception as e:
            print(f"  Erreur : {e}")

print(f"Total triplets : {len(g)} (dont {len(data)} dans data.ttl)")

# Ajouter les namespaces pour hasParticipant et hasLocation
HAS_PARTICIPANT = DUL.hasParticipant
HAS_LOCATION    = DUL.hasLocation

# ── Utilitaires ─────────────────────────────────────────────────────────────
def local(uri):
    """Extrait la partie locale d'un URI (après # ou /)."""
    return str(uri).split("#")[-1].split("/")[-1]

def get_label(node):
    """Retourne le rdfs:label français si disponible, sinon local name."""
    for label in g.objects(node, RDFS.label):
        if isinstance(label, Literal) and label.language == "fr":
            return str(label)
    for label in g.objects(node, RDFS.label):
        return str(label)
    return local(node)

def get_type(node):
    """Retourne la classe principale d'un nœud (local name)."""
    for t in g.objects(node, RDF.type):
        return local(t)
    return "Unknown"

def est_instance(node, g):
    """Retourne True si le nœud est une instance narrative pertinente."""
    for t in g.objects(node, RDF.type):
        # Exclure les classes OWL/RDFS
        if t in (OWL.Class, RDFS.Class, OWL.ObjectProperty,
                 OWL.DatatypeProperty, OWL.AnnotationProperty,
                 OWL.Ontology, RDF.Property):
            return False

    # Exclure les E55_Type (pred_*, Function_*, type_*)
    if get_type(node) == "E55_Type":
        return False
    # Exclure les nœuds sans type connu (probablement des classes orphelines)
    if get_type(node) == "Unknown":
        return False
    return True

# ── Classes à exclure des nœuds (types purement typologiques) ───────────────
CLASSES_EXCLUES = {
    "E55_Type",           # les prédicats narratifs et types
}

def est_exclu(node):
    for t in g.objects(node, RDF.type):
        if local(t) in CLASSES_EXCLUES:
            return True
    return False

# ── Label : priorité @en, puis autres langues, puis local name ──────────────
def get_label(node):
    # 1. label@en
    for label in g.objects(node, RDFS.label):
        if isinstance(label, rdflib.Literal) and label.language == "en":
            return str(label)
    # 2. label@fr
    for label in g.objects(node, RDFS.label):
        if isinstance(label, rdflib.Literal) and label.language == "fr":
            return str(label)
    # 3. n'importe quel label
    for label in g.objects(node, RDFS.label):
        return str(label)
    # 4. local name
    return local(node)

# ════════════════════════════════════════════════════════════════════════════
# MODE 2 — Graphe complet avec toutes les instances
# Inclut personnages, lieux, features, séquences, NU comme nœuds.
# Les arêtes = toutes les object properties (hors rdf:type).
# Idéal pour une vue structurelle de l'ontologie peuplée.
# ════════════════════════════════════════════════════════════════════════════

# Prédicats à ignorer (trop bruités ou redondants)
PREDICATS_IGNORES = {
    str(RDF.type),
    str(CIDOC.P2_has_type),   # met en commentaire si tu veux les types comme arêtes
}

# Prédicats à garder comme arêtes (liste blanche — laisse vide pour tout garder)
PREDICATS_BLANCS = set()  # ex: {str(GOLEM.GP0_has_feature), str(GOLEM.GP1_is_character_in)}

def build_full_graph(g, instances_locales):
    G = nx.DiGraph()

    PREDICATS_IGNORES = {
        str(RDF.type),
        str(CIDOC.P2_has_type),
        str(DLP.subject),
        str(DLP.object),
    }

    # ── Passe 1 : arêtes structurelles entre instances ───────────────────────
    for s, p, o in g:
        if isinstance(o, rdflib.Literal):
            continue
        if str(p) in PREDICATS_IGNORES:
            continue
        if str(s) not in instances_locales or str(o) not in instances_locales:
            continue
        if not est_instance(s, g) or not est_instance(o, g):
            continue

        s_id = str(s)
        o_id = str(o)

        if s_id not in G:
            G.add_node(s_id, label=get_label(s), classe=get_type(s))
        if o_id not in G:
            G.add_node(o_id, label=get_label(o), classe=get_type(o))

        G.add_edge(s_id, o_id, label=local(p))

    # ── Passe 2 : arêtes narratives sujet → objet avec label pred ────────────
    for nu in g.subjects(RDF.type, GOLEM.G9_Narrative_Unit):
        subj = next(g.objects(nu, DLP.subject), None)
        obj  = next(g.objects(nu, DLP.object),  None)

        if not subj or not obj or isinstance(obj, rdflib.Literal):
            continue
        if str(subj) not in instances_locales or str(obj) not in instances_locales:
            continue
        if not est_instance(subj, g) or not est_instance(obj, g):
            continue

        pred_label = None
        fonction   = None
        for t in g.objects(nu, CIDOC.P2_has_type):
            l = local(str(t))
            if l.startswith("pred_"):
                pred_label = get_label(t)
            elif l.startswith("Function_"):
                fonction = get_label(t)

        s_id = str(subj)
        o_id = str(obj)

        if s_id not in G:
            G.add_node(s_id, label=get_label(subj), classe=get_type(subj))
        if o_id not in G:
            G.add_node(o_id, label=get_label(obj), classe=get_type(obj))

        if s_id in G and o_id in G:
            G.add_edge(s_id, o_id,
                       label=pred_label or local(nu),
                       fonction=fonction or "",
                       nu=local(nu))
            
    # ── Passe 3 : G5_Narrative_Event → participants et lieux ─────────────────
    G5 = GOLEM.G5_Narrative_Event  # adapte si défini dans SF

    for event in g.subjects(RDF.type, G5):
        if str(event) not in instances_locales:
            continue

        e_id = str(event)
        if e_id not in G:
            G.add_node(e_id, label=get_label(event), classe="G5_Narrative_Event")

        # Participants
        for participant in g.objects(event, HAS_PARTICIPANT):
            if str(participant) not in instances_locales:
                continue
            if not est_instance(participant, g):
                continue
            p_id = str(participant)
            if p_id not in G:
                G.add_node(p_id, label=get_label(participant), classe=get_type(participant))
            G.add_edge(e_id, p_id, label="hasParticipant")

        # Lieux
        for location in g.objects(event, HAS_LOCATION):
            if str(location) not in instances_locales:
                continue
            if not est_instance(location, g):
                continue
            l_id = str(location)
            if l_id not in G:
                G.add_node(l_id, label=get_label(location), classe=get_type(location))
            G.add_edge(e_id, l_id, label="hasLocation")

    return G

# ── Export ───────────────────────────────────────────────────────────────────
if __name__ == "__main__":

    G_full = build_full_graph(g, instances_locales)
    print(f"  {G_full.number_of_nodes()} nœuds, {G_full.number_of_edges()} arêtes")
    nx.write_gexf(G_full, "Capus_LHommeBicycle_1893\complet.gexf")
    nx.write_graphml(G_full, "Capus_LHommeBicycle_1893\complet.graphml")
