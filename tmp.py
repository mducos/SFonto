
import jpype
from owlapy.owl_ontology import SyncOntology
from owlapy.expressivity import get_dl_expressivity

paths = [
    "src/GOLEM/golem_v2-0.ttl",
    "src/SFonto.ttl",
]

for path in paths:
    ontology = SyncOntology(path)
    root = ontology.owlapi_ontology
    manager = root.getOWLOntologyManager()

    # Récupérer la fermeture transitive des imports
    imports_closure = manager.getImportsClosure(root)

    # Fusionner les axiomes de toutes les ontologies importées
    merged = manager.createOntology()

    for imported_ontology in imports_closure:
        AxiomType = jpype.JClass("org.semanticweb.owlapi.model.AxiomType")

        for axiom_type in AxiomType.AXIOM_TYPES:
            for axiom in imported_ontology.getAxioms(axiom_type):
                manager.addAxiom(merged, axiom)

    # Sauvegarder temporairement l'ontologie fusionnée
    output_path = path.replace(".ttl", "_merged.owl")
    iri = jpype.JClass("org.semanticweb.owlapi.model.IRI").create(
        "file:///" + output_path.replace("\\", "/")
    )
    fmt = jpype.JClass(
        "org.semanticweb.owlapi.formats.RDFXMLDocumentFormat"
    )()
    manager.saveOntology(merged, fmt, iri)

    # Calculer l'expressivité avec OWLapy
    merged_ontology = SyncOntology(output_path)
    print(f"{path} — DL (imports inclus) :",
          get_dl_expressivity(merged_ontology))
