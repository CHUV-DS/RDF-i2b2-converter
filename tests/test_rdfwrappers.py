import os
import sys
import pytest
import random

myPath = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, myPath)

from initsts import *


def list_sparql_bnode_domains(uri=TEST_URI):
    """
    This should return all predicates for which the requested uri is a domain listed among other domains (in a blank node bag using owl:unionOf)
    """
    resp = ONTOLOGY_GRAPH.query(
        """
        SELECT ?p WHERE
                {
                ?p rdfs:domain [ a owl:Class ;
                                    owl:unionOf [ rdf:rest*/rdf:first ?self ]
                                    ]
                }
        """,
        initBindings={"self": uri},
    )
    rows = [ONTOLOGY_GRAPH.resource(e[0]) for e in resp]
    return rows


def test_list_properties():

    example_concept = random.choice(CONCEPT_LIST)
    fil = PropertyFilter(example_concept)
    fil.fetch_unique_properties()
    properties = fil.resources
    graph = example_concept.resource.graph

    # Other way around:
    other_props = [
        e for e in example_concept.resource.subjects(RDFS.domain)
    ] + list_sparql_bnode_domains(example_concept.resource.identifier)
    clean_props = []
    for candidate in other_props:
        add = True
        for child in other_props:
            if (
                child.identifier,
                RDFS.subPropertyOf * rdflib.paths.OneOrMore,
                candidate.identifier,
            ) in graph:
                add = False
                break
        if add:
            # No children found for this candidate so it's the most specific
            clean_props.append(candidate)
    assert len(clean_props) == len(properties)


def test_genericcode():
    res = ONTOLOGY_GRAPH.resource(
        rdflib.URIRef("https://biomedit.ch/rdf/sphn-ontology/sphn#NursingDiagnosis")
    )

    test_concept = Concept(res)
    test_concept.explore_children()
    assert (
        len(test_concept.properties) == 5
    )  # This is 5 if the unwanted elements are dropped in the i2b2 part


def test_unique_properties_specific():
    """
    Check if a concept has a "Code" property and a "XX Code" property (descendant of Code), only the latter is written in the concept class attribute.
    """
    res1 = ONTOLOGY_GRAPH.resource(
        "https://biomedit.ch/rdf/sphn-ontology/sphn#FOPHDiagnosis"
    )
    test_concept = Concept(res1)
    test_concept.explore_children()
    props_uris = [k.resource.identifier for k in test_concept.properties]
    doubles = []
    subprop = res1.graph.resource(
        rdflib.URIRef("http://www.w3.org/2000/01/rdf-schema#subPropertyOf")
    )
    for p in test_concept.properties:
        if subprop in p.resource.predicates():
            res = p.resource.value(subprop.identifier).identifier
            if res in props_uris:
                doubles.append((p, res))
    assert doubles == []


def test_explore_children():
    concept = CONCEPT_LIST[0]
    concept.explore_children()
    assert concept.subconcepts != [] or concept.properties != []


def test_extract_range_type_bnode():
    res = ONTOLOGY_GRAPH.resource(
        rdflib.URIRef(
            "https://biomedit.ch/rdf/sphn-ontology/sphn#hasCareHandlingTypeCode"
        )
    )
    handler = RangeFilter(res)
    reachable = handler.extract_range_type()
    assert len(reachable) > 1


def test_extract_range_type_plain():
    res = ONTOLOGY_GRAPH.resource(
        rdflib.URIRef("https://biomedit.ch/rdf/sphn-ontology/sphn#hasBiosample")
    )
    pro = RangeFilter(res)
    rnges = pro.extract_range_type()
    assert len(rnges) == 1


def nonblrng_props(reslist):
    """
    Return a list of instantiated Resources with their ranges filtered as non-blacklisted, from a list of resource uris
    """
    prop = PropertyFilter(None)
    prop.resources = reslist
    ranges = prop.filter_ranges()
    if len(ranges) != len(prop.resources):
        raise Exception("Bad property-range matching")
    return [Property(prop.resources[i], ranges[i]) for i in range(len(prop.resources))]


def test_mute_sameterminology():
    res1 = ONTOLOGY_GRAPH.resource(
        rdflib.URIRef(
            "https://biomedit.ch/rdf/sphn-ontology/sphn#hasAdministrativeGenderCode"
        )
    )
    res2 = ONTOLOGY_GRAPH.resource(
        rdflib.URIRef(
            "https://biomedit.ch/rdf/sphn-ontology/sphn#hasDiagnosticRadiologicExaminationCode"
        )
    )
    props = nonblrng_props([res1, res2])
    rnns = []
    for prop in props:
        prop.digin_ranges()
        rnns.extend(prop.ranges)
    assert all([rnn.subconcepts == [] for rnn in rnns])


def test_nomute_diffterminologies():
    res1 = ONTOLOGY_GRAPH.resource(
        rdflib.URIRef("https://biomedit.ch/rdf/sphn-ontology/sphn#hasSubstanceCode")
    )
    prop1 = nonblrng_props([res1])[0]
    prop1.digin_ranges()
    assert (
        sum([int(len(rnn.subconcepts) > 0) for rnn in prop1.ranges]) == 1
    )  # TODO change to True False True when including snomed


def test_mute_sameterm_differentfiles():
    res1 = ONTOLOGY_GRAPH.resource(rdflib.URIRef("http://snomed.info/id/105590001"))
    res2 = ONTOLOGY_GRAPH.resource(rdflib.URIRef("http://snomed.info/id/118169006"))
    prop = Property(ONTOLOGY_GRAPH.resource(RDF.toto), [res1, res2])
    prop.digin_ranges()
    assert all([rnn.subconcepts == [] for rnn in prop.ranges])
    # use <http://snomed.info/id/105590001> (extracted from the sphn ttl) vs any other snomed node from the snomed file


def test_valueset_structure():
    resp = ONTOLOGY_GRAPH.query(
        """
        SELECT ?s 
        where {
            ?s owl:equivalentClass [ a owl:Class ;
                                    owl:oneOf ?k
                ]
            filter not exists {
                ?s rdfs:subClassOf ?v
            }
        }
        """,
        initBindings={"v": rdflib.URIRef(VALUESET_MARKER_URI)},
    )
    assert len(resp) == 0


def test_namedindividual_structure():
    ind = ONTOLOGY_GRAPH.resource(
        rdflib.URIRef(
            "https://biomedit.ch/rdf/sphn-ontology/sphn#CongenitalAbnormality"
        )
    )
    res = ONTOLOGY_GRAPH.query(
        """
        select ?o
        where {
            ?s rdf:type ?o
        }
    """,
        initBindings={"s": ind.identifier},
    )
    assert len(res) == 2


def test_implicitlist():
    uri = ONTOLOGY_GRAPH.resource(
        rdflib.URIRef(
            "https://biomedit.ch/rdf/sphn-ontology/sphn#hasDrugPrescriptionIndicationToStart"
        )
    )
    res = ONTOLOGY_GRAPH.query(
        """
        select ?o
        where {
            ?s rdfs:range ?o
        }
    """,
        initBindings={"s": uri.identifier},
    )

    assert len(res) == 1


def test_explorevalueset():
    vst = ONTOLOGY_GRAPH.resource(VALUESET_MARKER_URI)
    candids = [e for e in vst.subjects(RDFS.subClassOf)]
    cur = random.choice(candids)
    conc = Concept(cur)
    upp = [k for k in conc.resource.subjects(RDFS.range)]
    prop = Property(upp[0], [conc.resource])
    prop.digin_ranges()

    res = ONTOLOGY_GRAPH.query(
        """
        select ?o
        where {
            ?s owl:equivalentClass [ a owl:Class ;
                                        owl:oneOf [ rdf:rest*/rdf:first ?o ]
                                    ]
        }
    """,
        initBindings={"s": cur.identifier},
    )
    elems = [LeafConcept(ONTOLOGY_GRAPH.resource(e[0])) for e in res]
    assert set([e.resource.identifier.toPython() for e in elems]) == set(
        [k.resource.identifier.toPython() for k in prop.ranges]
    )


def test_datatype():
    # Check the datatype properties correctly instantiate their range objects as ChildfreeConcepts
    res = ONTOLOGY_GRAPH.query(
        """
        select ?r 
        where {
            ?r rdf:type owl:DatatypeProperty
        }
    """
    )
    dattp = [k[0] for k in res]
    totest = random.choices(dattp, k=min(10, len(dattp)))
    prop = PropertyFilter(None)
    prop.resources = [ONTOLOGY_GRAPH.resource(tot) for tot in totest]
    properties = prop.get_properties()
    rngs = []
    for pp in properties:
        pp.digin_ranges()
        rngs.extend(pp.ranges)
    assert len(rngs) > 0 and all([type(rn) == LeafConcept for rn in rngs])


def test_valueset():
    # Check valueset elements do span a valueset of LeafConcepts and have no properties
    res = ONTOLOGY_GRAPH.query(
        """
        select ?s 
        where {
            ?s rdfs:range ?o .
            ?o rdfs:subClassOf ?vs
        }
    """,
        initBindings={"vs": VALUESET_MARKER_URI},
    )
    dattp = [k[0] for k in res]
    totest = random.choices(dattp, k=min(10, len(dattp)))
    prop = PropertyFilter(None)
    prop.resources = [ONTOLOGY_GRAPH.resource(tot) for tot in totest]
    properties = prop.get_properties()
    rngs = []
    for pp in properties:
        pp.digin_ranges()
        rngs.extend(pp.ranges)
    assert len(rngs) > 0 and all([type(rn) == LeafConcept for rn in rngs])


def test_sparql():
    res = ONTOLOGY_GRAPH.query(
        """
        select distinct ?cl
        where {
            ?prop rdfs:domain ?cl .
            ?other rdfs:subClassOf ?cl
        }
        """
    )
    rows = [k[0] for k in res]
