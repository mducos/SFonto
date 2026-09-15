import rdflib
from rdflib import RDF, RDFS, OWL, URIRef, Literal, Namespace
import networkx as nx
from pathlib import Path

# ── Namespaces ──────────────────────────────────────────────────────────────
SF   = Namespace("https://w3id.org/ontosf/ontology#")
GOLEM = Namespace("https://w3id.org/golem/ontology#")
CIDOC = Namespace("http://www.cidoc-crm.org/cidoc-crm/")
DLP  = Namespace("http://www.ontologydesignpatterns.org/ont/dlp/")
DUL = Namespace("http://www.ontologydesignpatterns.org/ont/dul/DUL.owl#")

# ── Chemins ─────────────────────────────────────────────────────────────────

DATA_DIR = Path("data")

ONTOLOGIES_EXTERNES = [
    Path("src/SFonto.ttl"),
    Path("src/golem_v1-1.ttl"),
]

HAS_PARTICIPANT = DUL.hasParticipant
HAS_LOCATION    = DUL.hasLocation


# ════════════════════════════════════════════════════════════════════════════
# UTILITAIRES
# ════════════════════════════════════════════════════════════════════════════

def local(uri):
    """Extrait la partie locale d'un URI."""
    return str(uri).split("#")[-1].split("/")[-1]


def get_label(node, g):
    """Label : priorité @en, puis @fr, puis autre label, puis URI."""
    
    # 1. label@en
    for label in g.objects(node, RDFS.label):
        if isinstance(label, Literal) and label.language == "en":
            return str(label)

    # 2. label@fr
    for label in g.objects(node, RDFS.label):
        if isinstance(label, Literal) and label.language == "fr":
            return str(label)

    # 3. n'importe quel label
    for label in g.objects(node, RDFS.label):
        return str(label)

    # 4. local name
    return local(node)


def get_type(node, g):
    """Retourne la classe principale d'un nœud."""
    for t in g.objects(node, RDF.type):
        return local(t)
    return "Unknown"


def est_instance(node, g):
    """Retourne True si le nœud est une instance narrative pertinente."""
    
    for t in g.objects(node, RDF.type):

        # Exclure les classes/propriétés OWL/RDFS
        if t in (
            OWL.Class,
            RDFS.Class,
            OWL.ObjectProperty,
            OWL.DatatypeProperty,
            OWL.AnnotationProperty,
            OWL.Ontology,
            RDF.Property
        ):
            return False

    # Exclure les nœuds sans type connu
    if get_type(node, g) == "Unknown":
        return False

    return True


# ── Classes à exclure ───────────────────────────────────────────────────────

CLASSES_EXCLUES = {
    # Ajouter ici si nécessaire
    # "G17_Feature",
}


def est_exclu(node, g):
    for t in g.objects(node, RDF.type):
        if local(t) in CLASSES_EXCLUES:
            return True
    return False


# ════════════════════════════════════════════════════════════════════════════
# CONSTRUCTION DU GRAPHE
# ════════════════════════════════════════════════════════════════════════════

def build_full_graph(g, instances_locales):

    G = nx.DiGraph()

    PREDICATS_IGNORES = {
        str(RDF.type),
        str(CIDOC.P2_has_type),
        str(DLP.subject),
        str(DLP.object),
    }

    # ────────────────────────────────────────────────────────────────────────
    # Passe 1 : arêtes structurelles
    # ────────────────────────────────────────────────────────────────────────

    for s, p, o in g:

        # Ignorer les littéraux
        if isinstance(o, Literal):
            continue

        # Ignorer certains prédicats
        if str(p) in PREDICATS_IGNORES:
            continue

        # Ne conserver que les URIs présentes dans le fichier data.ttl
        if str(s) not in instances_locales:
            continue

        if str(o) not in instances_locales:
            continue

        # Ne conserver que les instances
        if not est_instance(s, g) or not est_instance(o, g):
            continue

        # Classes explicitement exclues
        if est_exclu(s, g) or est_exclu(o, g):
            continue

        s_id = str(s)
        o_id = str(o)

        if s_id not in G:
            G.add_node(
                s_id,
                label=get_label(s, g),
                classe=get_type(s, g)
            )

        if o_id not in G:
            G.add_node(
                o_id,
                label=get_label(o, g),
                classe=get_type(o, g)
            )

        G.add_edge(
            s_id,
            o_id,
            label=local(p)
        )

    # ────────────────────────────────────────────────────────────────────────
    # Passe 2 : Narrative Unit → sujet/objet
    # ────────────────────────────────────────────────────────────────────────

    for nu in g.subjects(RDF.type, GOLEM.G9_Narrative_Unit):

        subj = next(g.objects(nu, DLP.subject), None)
        obj  = next(g.objects(nu, DLP.object), None)

        if not subj or not obj:
            continue

        if isinstance(obj, Literal):
            continue

        if str(subj) not in instances_locales:
            continue

        if str(obj) not in instances_locales:
            continue

        if not est_instance(subj, g) or not est_instance(obj, g):
            continue

        if est_exclu(subj, g) or est_exclu(obj, g):
            continue

        # Récupération du prédicat narratif
        pred_label = None
        fonction = None

        for t in g.objects(nu, CIDOC.P2_has_type):

            l = local(t)

            if l.startswith("pred_"):
                pred_label = get_label(t, g)

            elif l.startswith("Function_"):
                fonction = get_label(t, g)

        s_id = str(subj)
        o_id = str(obj)

        if s_id not in G:
            G.add_node(
                s_id,
                label=get_label(subj, g),
                classe=get_type(subj, g)
            )

        if o_id not in G:
            G.add_node(
                o_id,
                label=get_label(obj, g),
                classe=get_type(obj, g)
            )

        G.add_edge(
            s_id,
            o_id,
            label=pred_label or local(nu),
            fonction=fonction or "",
            nu=local(nu)
        )

    # ────────────────────────────────────────────────────────────────────────
    # Passe 3 : G5 Narrative Event → participants + lieux
    # ────────────────────────────────────────────────────────────────────────

    G5 = GOLEM.G5_Narrative_Event

    for event in g.subjects(RDF.type, G5):

        if str(event) not in instances_locales:
            continue

        e_id = str(event)

        if e_id not in G:
            G.add_node(
                e_id,
                label=get_label(event, g),
                classe="G5_Narrative_Event"
            )

        # Participants
        for participant in g.objects(event, HAS_PARTICIPANT):

            if str(participant) not in instances_locales:
                continue

            if not est_instance(participant, g):
                continue

            if est_exclu(participant, g):
                continue

            p_id = str(participant)

            if p_id not in G:
                G.add_node(
                    p_id,
                    label=get_label(participant, g),
                    classe=get_type(participant, g)
                )

            G.add_edge(
                e_id,
                p_id,
                label="hasParticipant"
            )

        # Lieux
        for location in g.objects(event, HAS_LOCATION):

            if str(location) not in instances_locales:
                continue

            if not est_instance(location, g):
                continue

            if est_exclu(location, g):
                continue

            l_id = str(location)

            if l_id not in G:
                G.add_node(
                    l_id,
                    label=get_label(location, g),
                    classe=get_type(location, g)
                )

            G.add_edge(
                e_id,
                l_id,
                label="hasLocation"
            )

    return G


# ════════════════════════════════════════════════════════════════════════════
# TRAITEMENT D'UN DOSSIER
# ════════════════════════════════════════════════════════════════════════════

def traiter_dossier(dossier):

    print("\n" + "=" * 70)
    print(f"Dossier : {dossier}")
    print("=" * 70)

    # ────────────────────────────────────────────────────────────────────────
    # 1. Chercher les fichiers TTL du dossier
    # ────────────────────────────────────────────────────────────────────────

    fichiers_ttl = list(dossier.glob("*.ttl"))

    if not fichiers_ttl:
        print("  Aucun fichier .ttl trouvé.")
        return

    print(f"  Fichiers TTL trouvés : {len(fichiers_ttl)}")

    # ────────────────────────────────────────────────────────────────────────
    # 2. Charger les données locales
    # ────────────────────────────────────────────────────────────────────────

    data = rdflib.Graph()

    for fichier in fichiers_ttl:

        print(f"    Chargement : {fichier.name}")

        try:
            data.parse(fichier, format="turtle")

        except Exception as e:
            print(f"    ERREUR : {e}")

    if len(data) == 0:
        print("  Aucun triplet chargé.")
        return

    # ────────────────────────────────────────────────────────────────────────
    # 3. Récupérer les URIs locales
    # ────────────────────────────────────────────────────────────────────────

    instances_locales = set()

    for s, p, o in data:

        if isinstance(s, URIRef):
            instances_locales.add(str(s))

        if isinstance(o, URIRef):
            instances_locales.add(str(o))

    print(f"  URIs locales : {len(instances_locales)}")
    print(f"  Triplets locaux : {len(data)}")

    # ────────────────────────────────────────────────────────────────────────
    # 4. Charger les ontologies externes
    # ────────────────────────────────────────────────────────────────────────

    g = rdflib.Graph()

    # Données locales
    g += data

    # Ontologies externes
    for ontology in ONTOLOGIES_EXTERNES:

        try:
            print(f"  Chargement ontologie : {ontology}")
            g.parse(ontology, format="turtle")

        except Exception as e:
            print(f"  Erreur ontologie {ontology} : {e}")

    # ────────────────────────────────────────────────────────────────────────
    # 5. Charger les owl:imports
    # ────────────────────────────────────────────────────────────────────────

    for imported_uri in data.objects(None, OWL.imports):

        print(f"  owl:imports : {imported_uri}")

        try:
            g.parse(str(imported_uri))

        except Exception as e:
            print(f"    Erreur import : {e}")

    print(f"  Total triplets : {len(g)}")

    # ────────────────────────────────────────────────────────────────────────
    # 6. Construire le graphe
    # ────────────────────────────────────────────────────────────────────────

    G_full = build_full_graph(
        g,
        instances_locales
    )

    print(
        f"  Graphe : "
        f"{G_full.number_of_nodes()} nœuds, "
        f"{G_full.number_of_edges()} arêtes"
    )

    # ────────────────────────────────────────────────────────────────────────
    # 7. Export dans le même dossier
    # ────────────────────────────────────────────────────────────────────────

    sortie_gexf = dossier / "complet.gexf"
    sortie_graphml = dossier / "complet.graphml"

    nx.write_gexf(
        G_full,
        sortie_gexf
    )

    nx.write_graphml(
        G_full,
        sortie_graphml
    )

    print(f"  → {sortie_gexf}")
    print(f"  → {sortie_graphml}")


# ════════════════════════════════════════════════════════════════════════════
# PARCOURIR DATA ET TOUS SES SOUS-DOSSIERS
# ════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":

    # rglob("*") permet de descendre dans tous les niveaux
    # de sous-dossiers.
    dossiers = sorted(
        p for p in DATA_DIR.rglob("*")
        if p.is_dir()
    )

    # Ajouter également data/ lui-même
    dossiers.insert(0, DATA_DIR)

    print(f"{len(dossiers)} dossiers à examiner.")

    for dossier in dossiers:
        traiter_dossier(dossier)

    print("\nTraitement terminé.")