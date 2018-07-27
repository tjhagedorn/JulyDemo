# -*- coding: utf-8 -*-
# import packages
import owlready2 as owl
import rdflib as rdf
import pandas as pd
import json as json
import types as types
import os as os

class OntoDAA():
    # implements a generic form of the parser / mapping functions for 
    # receiving data from a JSON source file
    def __init__(self, projectId, iri, pathIn, files):
        
        self.iri = iri
        self.pIRI = iri +"/"+projectId
        self.projectId = projectId
        self.qMgr = QueryManager(iri, owl.Thing, owl.World())

        # populate dictionary
        for f in files:
            self.qMgr.getOntologyFile(pathIn,f) 
            
    def parseJSON(self, jsonString, idkwd, typekwd, speckwd):
        jp = JsonParser(self.qMgr, idkwd, typekwd, speckwd)
        parse = jp.getParsedJSON(jsonString, "elements")
        [onto, instances, triples] = jp.toOntology(self.iri)
        return onto

    def queryTableOut(self, df, graph, q, suffix):            
        r = graph.query(self.qMgr.prefix+q)
        for i in r:
                try:
                    df.loc[str(i[0]), str(i[1])+suffix] = float(str(i[2]))
                except Exception:
                    df.loc[str(i[0]), str(i[1])+suffix] = str(i[2])
        # sort output to control end position
        cols =  df.columns.tolist()
        cols.sort()
        df = df[cols]
        
        return df


class SysMLDAA(OntoDAA):
    
    def __init__(self, projectId):
        # get the ontology files, assumed to be in a subdirectory

        self.iri =  "https://www.raw.githubusers.com/UMassCenterforeDesign/decision/master/SysML.owl"
        self.qMgr = QueryManager(self.iri, owl.Thing, owl.World())
        
        
        cwd = os.getcwd()
        pathIn = cwd+"\\ontologies"
        files = os.listdir(pathIn)
        for f in files:
            self.qMgr.getOntologyFile(pathIn,f)
        # tool ontology iri - this is important
        super().__init__(projectId, self.iri, pathIn, files)
        
    def populateTripleStore(self, jsonString):

        # JUST FOR DEMO - Forget the old manager, repopulate ontology
        self.qMgr = QueryManager(self.iri, owl.Thing, owl.World())
        
        # populate dictionary
        cwd = os.getcwd()
        pathIn = cwd+"\\ontologies"        
        files = os.listdir(pathIn)
        for f in files:
            self.qMgr.getOntologyFile(pathIn,f)
            
        ##########################################
        # Run the parser / mapping
        self.onto = self.parseJson(jsonString)
        decGraph = self.mapSysML(self.qMgr.toGraph())
        df = self.demoQuery(decGraph)
        return decGraph
    
    def parseJson(self, jsonString):  
        idkwd = "id"
        typekwd = "type"
        speckwd = ["typeId",
                   "definingFeatureId",
                   "slotIds", "ownerId",
                   "instanceId",
                   "classifierIds"]
        onto = super().parseJSON(jsonString, idkwd, typekwd, speckwd)
        return onto
       
    def demoQuery(self, decGraph):
        
        df = pd.DataFrame()
        # Retrieve Engine Type 
        q = """
        SELECT ?SysName ?engName ?engType
        WHERE {
            ?system regulation:specifies ?engine .
            ?engine regulation:is_specification_for 
                            / SysML:name_dp "engine"^^xsd:string .
            ?engine regulation:is_specification_for 
                                / SysML:name_dp ?engName .
            ?engine model:specifies_value ?engType .
            ?system SysML:name_dp ?SysName . 
            }"""
    
        df = self.queryTableOut( df, decGraph, q, "")
        
        q = """
            SELECT DISTINCT ?sysName ?traitName ?value
            WHERE { 
                ?est InformationEntityOntology:is_a_measurement_of ?pref .
                ?inst ExtendedRelationOntology:has_part ?est .
                ?inst model:has_basis ?mInst .
                ?mInst InformationEntityOntology:is_about ?system .
                ?system SysML:name_dp ?sysName .
                ?pref SysML:name_dp ?traitName .
                ?est model:has_value ?value .
                
            }"""
        df = self.queryTableOut( df, decGraph, q, "")
        Ex = pd.ExcelWriter("DecisionOut.xlsx")
        df.to_excel(Ex, sheet_name="Values")
        Ex.save()
        return df
    
    def mapSysML(self, ograph):

        qMgr= self.qMgr
        decGraph = rdf.Graph()
        q = """
        SELECT ?a ?b
        WHERE {
        ?a SysML:endIds / SysML:ownerId / SysML:endIds/ SysML:roleId ?b .
        }
        """
        tgraph=rdf.Graph()
        r = ograph.query(qMgr.prefix+q)
        for i in r:
            tgraph.add((i[0], qMgr.uriDict["is_connected_to"], i[1]))
        
        q = """
        SELECT ?a ?b 
        WHERE {
        ?a SysML:endIds / SysML:ownerId / SysML:endIds / SysML:partWithPortId ?b .
        }
        """
        r=ograph.query(qMgr.prefix+q)
        for i in r:
            tgraph.add((i[0], qMgr.uriDict["is_related_to"], i[1]))
        
        # recreate ograph as the enhanced graph    
        ograph = ograph+tgraph
        
        # Get key performance parameters used in the model
        # Assert this property represents a trait:
        # add a designation for KPPs
        des = qMgr.addInstance(qMgr.iri,
                               'kpp_designation',
                               qMgr.uriDict['Designative Name'],
                               decGraph)
        
        # Create alternatives, and a link to the measure data set
        
        alt =qMgr.addInstance(qMgr.iri,
                              "#decision_alternative",
                              qMgr.uriDict["decision_alternative_classificaiton"],
                              decGraph)
        
        classes = [[0, "Artifact Design"],
                   [1, "DirectiveInformationContentEntity"],
                   [3, "entity"],
                   [4, "IAO_0000100"]]
        
        ids = ["_alternative", "_spec", "_trait", "_dset"]
        
        qProps = []
        
        bProps = [[0, 1, "has part"], 
                  [1, 2, "is specification for"],
                  [3, 0, "is about"]]
        
        cProps = [[0, 0, "represents"],
                  [1, 1, "represents"],
                  [3, 2, "represents"],
                  [4, 3, "represents"]]
        
        outer = [[0, "designates" , alt]]
        
        dp = [[1, 2, "specifies_value"],
              [2, 5, "name_dp"]]
        
        q = """
        SELECT ?system ?sysSlot ?value ?class ?inst ?name
        WHERE 
        {
            ?sysSlot SysML:ownerId ?system .
            ?sysLit SysML:ownerId ?sysSlot .
            ?sysLit SysML:value_dp ?value .
            ?sysSlot SysML:definingFeatureId ?class .
            ?class SysML:name_dp ?name
            
            {SELECT ?system ?lit ?inst ?slot 
            WHERE {
                ?slot SysML:ownerId ?inst .
                ?lit SysML:ownerId ?slot .
                ?lit SysML:instanceId ?system .
                ?system SysML:classifierIds / SysML:name_dp "UASystem"^^xsd:string .
                ?system SysML:ownerId / SysML:name_dp "UA Systems"^^xsd:string .
                }
            }
        } """
        decGraph = qMgr.graphBranchQuery(q, ograph, decGraph, 
                                         classes, ids, qProps, 
                                         bProps, cProps, outer, dp)
        # Get info on the system parts that are sub-specs
        classes = [[0, "Artifact Design"],
                   [1, "DirectiveInformationContentEntity"],
                   [3, "entity"],
                   [4, "IAO_0000100"],
                   [6, "Artifact Design"]]
        
        ids = ["_alternative", "_spec", "_trait", "_dset", "_part"]
        
        qProps = []
        
        bProps = [[0, 1, "has part"], 
                  [1, 2, "is specification for"],
                  [3, 0, "is about"],
                  [1, 4, "specifies"],
                  [1, 4, "has part"]]
        
        cProps = [[0, 0, "represents"],
                  [1, 1, "represents"],
                  [3, 2, "represents"],
                  [4, 3, "represents"],
                  [6, 4, "represents"]]
        
        outer = [[0, "designates" , alt]]
        
        dp = [[2, 5, "name_dp"],
              [4, 7, "name_dp"]]
        
        
        
        q = """
        SELECT ?system ?sysSlot ?value ?class ?inst ?name ?subinst ?subname
        WHERE 
        {
            ?sysSlot SysML:ownerId ?system .
            ?sysLit SysML:ownerId ?sysSlot .  
            ?subinst SysML:name_dp ?subname .
            ?sysLit SysML:instanceId ?subinst .
            ?sysSlot SysML:definingFeatureId ?class .
            ?class SysML:name_dp ?name
            
            {SELECT ?system ?lit ?inst ?slot 
            WHERE {
                ?slot SysML:ownerId ?inst .
                ?lit SysML:ownerId ?slot .
                ?lit SysML:instanceId ?system .
                ?system SysML:classifierIds / SysML:name_dp "UASystem"^^xsd:string .
                ?system SysML:ownerId / SysML:name_dp "UA Systems"^^xsd:string .
            }
            }
        } """
        decGraph = qMgr.graphBranchQuery(q, ograph, decGraph, 
                                         classes, ids, qProps, 
                                         bProps, cProps, outer, dp)

        ## get sub-parts of system sub-parts
        classes = [[0, "Artifact Design"],
                   [1, "Artifact Design"],
                   [2, "DirectiveInformationContentEntity"],
                   [3, "Artifact Design"],
                   [4, "entity"]]
        
        ids = ["_alternative", "_part", "_spec", "_part", "_trait"]
        
        qProps = []
        
        bProps = [[0, 1, "has part"], 
                  [1, 2, "has part"],
                  [2, 3, "specifies"],
                  [1, 3, "has part"],
                  [2, 4, "is about"],
                  [0, 3, "has part"],
                  [3, 4, "is specification for"]]
        
        cProps = [[0, 0, "represents"],
                  [1, 1, "represents"],
                  [2, 2, "represents"],
                  [3, 3, "represents"],
                  [4, 4, "represents"]]
        
        outer = []
        
        dp = [[4, 5, "name_dp"], [3, 6, "name_dp"]]
        q = """
        SELECT ?system ?pinst ?slot ?eng ?class ?name ?engName
        WHERE 
        {
          ?slot SysML:ownerId ?pinst .
          ?lit SysML:ownerId ?slot .
          ?slot SysML:definingFeatureId ?class .
          ?class SysML:name_dp ?name .
          ?lit SysML:instanceId ?eng .
          ?eng SysML:name_dp ?engName
          
            {SELECT DISTINCT ?system ?pinst 
            WHERE {
                ?lslot SysML:ownerId / SysML:ownerId ?system .
                ?lslot SysML:instanceId ?pinst .
                ?system SysML:classifierIds / SysML:name_dp "UASystem"^^xsd:string .
                }
            }
        } """
        decGraph = qMgr.graphBranchQuery(q, ograph, decGraph, 
                                         classes, ids, qProps, 
                                         bProps, cProps, outer, dp)
        
        ## get sub-parts attributes of system sub-sub-parts
        
        classes = [[0, "Artifact Design"],
                   [1, "Artifact Design"],
                   [2, "DirectiveInformationContentEntity"],
                   [3, "Artifact Design"],
                   [4, "entity"],
                   [8, "DirectiveInformationContentEntity"],
                   [9, "entity"]]
        
        ids = ["_alternative", "_part", "_spec", "_part", "_trait", "_spec", "_trait"]
        
        qProps = []
        
        bProps = [[0, 1, "has part"], 
                  [1, 2, "has part"],
                  [2, 3, "specifies"],
                  [1, 3, "has part"],
                  [2, 4, "is about"],
                  [0, 3, "has part"],
                  [3, 4, "is specification for"],
                  [3, 5, "has part"],
                  [5, 6, "is specification for"],
                  [0, 5, "specifies"]]
        
        cProps = [[0, 0, "represents"],
                  [1, 1, "represents"],
                  [2, 2, "represents"],
                  [3, 3, "represents"],
                  [4, 4, "represents"]]
        
        outer = []
        
        dp = [[4, 5, "name_dp"], [3, 6, "name_dp"],  [5, 7,"specifies value"], [6, 10, "name_dp"]]
        q = """
        SELECT ?system ?pinst ?slot ?eng ?class ?name ?engName ?prop ?pslot ?ptype ?pname
        WHERE 
        { ?plit SysML:ownerId ?pslot .
          ?pslot SysML:ownerId ?eng .
          ?pslot SysML:definingFeatureId ?ptype .
          ?ptype SysML:name_dp ?pname .
          ?plit SysML:instanceId / SysML:name_dp ?prop .
          {SELECT ?slot ?eng ?system ?pinst ?class ?name ?engName
          WHERE {
                  ?slot SysML:ownerId ?pinst .
                  ?lit SysML:ownerId ?slot .
                  ?slot SysML:definingFeatureId ?class .
                  ?class SysML:name_dp ?name .
                  ?lit SysML:instanceId ?eng .
                  ?eng SysML:name_dp ?engName .
          
                    {SELECT DISTINCT ?system ?pinst 
                    WHERE {
                        ?lslot SysML:ownerId / SysML:ownerId ?system .
                        ?lslot SysML:instanceId ?pinst .
                        ?system SysML:classifierIds / SysML:name_dp "UASystem"^^xsd:string .
                        }
            }}}
        } """
        decGraph = qMgr.graphBranchQuery(q, ograph, decGraph, 
                                         classes, ids, qProps, 
                                         bProps, cProps, outer, dp)

        # get sub-parts attributes of system sub-sub-parts
        classes = [[0, "Artifact Design"],
                   [1, "Artifact Design"],
                   [2, "DirectiveInformationContentEntity"],
                   [3, "Artifact Design"],
                   [4, "entity"],
                   [8, "DirectiveInformationContentEntity"],
                   [9, "entity"]]
        
        ids = ["_alternative", "_part", "_spec", "_part", "_trait", "_spec", "_trait"]
        
        qProps = []
        
        bProps = [[0, 1, "has part"], 
                  [1, 2, "has part"],
                  [2, 3, "specifies"],
                  [1, 3, "has part"],
                  [2, 4, "is about"],
                  [0, 3, "has part"],
                  [3, 4, "is specification for"],
                  [3, 5, "has part"],
                  [5, 6, "is specification for"],
                  [0, 5, "specifies"]]
        
        cProps = [[0, 0, "represents"],
                  [1, 1, "represents"],
                  [2, 2, "represents"],
                  [3, 3, "represents"],
                  [4, 4, "represents"]]
        
        outer = []
        
        dp = [[4, 5, "name_dp"], [3, 6, "name_dp"],  [5, 7,"specifies value"], [6, 10, "name_dp"]]
        q = """
        SELECT ?system ?pinst ?slot ?eng ?class ?name ?engName ?prop ?pslot ?ptype ?pname
        WHERE 
        { ?plit SysML:ownerId ?pslot .
          ?pslot SysML:ownerId ?eng .
          ?pslot SysML:definingFeatureId ?ptype .
          ?ptype SysML:name_dp ?pname .
          ?plit SysML:value_dp ?prop .
          {SELECT ?slot ?eng ?system ?pinst ?class ?name ?engName
          WHERE {
                  ?slot SysML:ownerId ?pinst .
                  ?lit SysML:ownerId ?slot .
                  ?slot SysML:definingFeatureId ?class .
                  ?class SysML:name_dp ?name .
                  ?lit SysML:instanceId ?eng .
                  ?eng SysML:name_dp ?engName .
          
                    {SELECT DISTINCT ?system ?pinst 
                    WHERE {
                        ?lslot SysML:ownerId / SysML:ownerId ?system .
                        ?lslot SysML:instanceId ?pinst .
                        ?system SysML:classifierIds / SysML:name_dp "UASystem"^^xsd:string .
                        }
            }}}
        } """
        decGraph = qMgr.graphBranchQuery(q, ograph, decGraph, 
                                         classes, ids, qProps, 
                                         bProps, cProps, outer, dp)

        # get sub-attributes of system sub-parts
        classes = [[0, "Artifact Design"],
                   [1, "Artifact Design"],
                   [2, "DirectiveInformationContentEntity"],
                   [3, "specifically dependent continuant"]]
        
        ids = ["_alternative", "_part", "_spec", "_trait"]
        
        qProps = []
        
        bProps = [[0, 1, "has part"],
                  [1, 2, "has part"],
                  [2, 3, "specifies"],
                  [1, 3, "bearer of"]]

        cProps = [[0, 0, "represents"],
                  [1, 1, "represents"],
                  [2, 2, "represents"],
                  [3, 3, "represents"]]
        
        outer = []
        
        dp = [[3, 3, "name_dp"], [2, 4, "specifies_value"]]
        q = """
        SELECT ?system ?pinst ?slot ?class ?name ?value
        WHERE 
        {
          ?slot SysML:ownerId ?pinst .
          ?lit SysML:ownerId ?slot .
          ?slot SysML:definingFeatureId ?class .
          ?class SysML:name_dp ?name .
          ?lit SysML:value_dp ?value .
          
            {SELECT DISTINCT ?system ?pinst 
            WHERE {
                ?lslot SysML:ownerId / SysML:ownerId ?system .
                ?lslot SysML:instanceId ?pinst .
                ?system SysML:classifierIds / SysML:name_dp "UASystem"^^xsd:string .
                }
            }
        } """
        
        decGraph = qMgr.graphBranchQuery(q, ograph, decGraph, 
                                         classes, ids, qProps, 
                                         bProps, cProps, outer, dp)
        # add measures values
        
        classes = [[1, "model"],
                   [2, "IAO_0000100"],
                   [3, "estimate"],
                   [4, "IAO_0000100"],
                   [0, "measurement type specification"]] 
        
        ids = ["_model", "_dset", "_est", "_dset", "_spec"]
        
        qProps = []
        
        bProps = [[2, 0, "has basis"], 
                  [3, 1, "has basis"],
                  [1, 2, "has part"],
                  [4, 0, "specifies"]]
        
        cProps = [[0, 4, "represents"],
                  [1, 0, "represents"],
                  [2, 1, "represents"],
                  [3, 2, "represents"],
                  [4, 3, "represents"]]
        
        outer = []
        
        dp = [[2, 5, "has_value"]]
        q="""
        SELECT ?class ?prop ?mInst ?mSlot ?vInst ?value 
        WHERE	
        {
            ?mSlot SysML:ownerId ?mInst .
            ?lit SysML:ownerId ?mSlot .
            ?lit SysML:value_dp ?value .
            ?mSlot SysML:definingFeatureId ?prop	.
            ?prop  SysML:typeId ?class 
            {SELECT ?vLit ?mInst ?vSlot ?vInst
            WHERE {
                ?vSlot SysML:ownerId ?vInst .
                ?vLit SysML:ownerId ?vSlot .
                ?vLit SysML:instanceId ?mInst .
                ?mInst SysML:ownerId / SysML:name_dp "Measures"^^xsd:string .}}
        }"""
            
        decGraph = qMgr.graphBranchQuery(q, ograph, decGraph, 
                                         classes, ids, qProps, 
                                         bProps, cProps, outer, dp)
        
        # Initial map of measure space, mark KPPs
        
        classes = [[0, "measurement type specification"],
                   [1, "model"],
                   [2, "process profile"],
                   [3, "IAO_0000100"],
                   [4, "estimate"],
                   [2, "specifically dependent continuant"]]
        
        ids = ["_spec", "_model", "_metric", "_dset", "_est", "_trait"]
        
        qProps = []
        
        bProps = [[0, 1, "specifies"], 
                  [1, 2, "is model of"],
                  [3, 4, "has part"],
                  [0, 5, "is about"],
                  [4, 2, "is a measurement of"],
                  [4, 5, "is_metric_of"]]
        
        cProps = [[0, 0, "represents"],
                  [1, 1, "represents"],
                  [2, 2, "represents"],
                  [3, 3, "represents"],
                  [4, 4, "represents"]]
        
        outer = []
        dp = [[4, 6, "has_value"], [2, 5, "name_dp"]]
        
        q="""
        SELECT ?mclass ?modprop ?mprop ?minst ?mslot ?name ?value
        WHERE {
               ?minst SysML:slotIds ?mslot .
               ?mslot SysML:definingFeatureId ?mprop .
               ?lit SysML:ownerId ?mslot .
               ?lit SysML:value_dp ?value .
               ?mprop SysML:name_dp ?name .
                {SELECT ?minst WHERE {
                    ?minst SysML:ownerId / SysML:name_dp "Measures"^^xsd:string .
                    ?vlit SysML:instanceId ?minst .
                }}        
                {SELECT ?mclass ?mprop ?modprop WHERE {            
                    ?mprop SysML:ownerId / SysML:name_dp "Measures"^^xsd:string .
                    ?mprop SysML:is_related_to ?modprop . 
                    ?modprop SysML:typeId ?mclass . 
                }}
        }
        """
        
        decGraph = qMgr.graphBranchQuery(q, ograph, decGraph, 
                                         classes, ids, qProps, 
                                         bProps, cProps, outer, dp)          
        
        # Add KPP  designation
        qProps, bProps, cProps, dp = [], [], [], []
        classes = [[0, "specifically dependent continuant"]]
        ids = ["_trait"]
        outer = [[0, "designates", des]]
        dp = []
        
        q="""
        SELECT ?mprop 
        WHERE {
               ?mprop SysML:is_connected_to / SysML:name_dp "measure"^^xsd:string .
               ?mprop SysML:ownerId / SysML:name_dp "Measures"^^xsd:string .
               }
        """
        decGraph = qMgr.graphBranchQuery(q, ograph, decGraph, 
                                         classes, ids, qProps, 
                                         bProps, cProps, outer) 
          
        # Link Measure data set back to teh specific Alternatives
        classes = [[0, "Artifact Design"],
                   [1, "IAO_0000100"]]
        ids = ["_alternative", "_dset"]
        qProps = []
        bProps = [[1, 0, "is about"]]
        cProps = []
        outer = []
        dp = [[0, 2, "name_dp"]]
        
        q="""SELECT ?system ?inst ?name WHERE {
        ?lit SysML:instanceId ?system .
        ?system SysML:name_dp ?name .
        ?system SysML:classifierIds / SysML:name_dp "UASystem"^^xsd:string .
        ?lit SysML:ownerId ?slot .
        ?slot SysML:ownerId ?inst .
        ?inst SysML:ownerId / SysML:name_dp "Measures"^^xsd:string .}"""
        
        decGraph = qMgr.graphBranchQuery(q, ograph, decGraph, 
                                         classes, ids, qProps, 
                                         bProps, cProps, outer, dp)
        
        # Read out the INTERMEDIATE Value Results - these don't link to measure space
        
        classes = [[0, "measurement type specification"],
                   [0, "model"],
                   [0, "preference"],
                   [1, "model"],
                   [1, "preference"],
                   [2, "IAO_0000100"],
                   [3, "estimate"],
                   [4, "IAO_0000100"]]
        
        ids = ["_spec", "_model", "_pref", "_model", "_pref", "_dset", "_est", "_dset"]
        
        qProps = []
        
        bProps = [[0, 1, "specifies"],
                  [0, 2, "is about"],
                  [1, 2, "is model of"],
                  [2, 4, "has part"],
                  [3, 4, "is model of"],
                  [0, 3, "specifies"],
                  [6, 3, "has basis"],
                  [5, 6, "has part"],
                  [6, 4, "is a measurement of"],
                  [5, 7, "has basis"]]
        
        cProps = []
        
        outer = []
        
        dp = [[6, 5, "has_value"], [4, 6, "name_dp"]]
        q = """
        SELECT ?class ?prop ?inst ?slot ?mInst ?value ?name
        WHERE
        {	?slot SysML:ownerId ?inst .
            ?lit SysML:ownerId ?slot .
            ?lit SysML:value_dp ?value .
            ?slot SysML:definingFeatureId ?prop.
            ?prop SysML:is_connected_to / SysML:ownerId ?class .
            ?prop SysML:name_dp ?name .
            {SELECT ?inst ?mInst
            WHERE {
                ?vSlot SysML:ownerId ?inst .
                ?vLit SysML:ownerId ?vSlot .
                ?vLit SysML:instanceId ?mInst .
                ?mInst SysML:ownerId / SysML:name_dp "Measures"^^xsd:string .
                {
                SELECT ?inst 
                WHERE {
                    ?inst SysML:classifierIds / SysML:name_dp "Values"^^xsd:string .
                }
                }
            }
            }
        }
        """
        decGraph = qMgr.graphBranchQuery(q, ograph, decGraph, 
                                         classes, ids, qProps, 
                                         bProps, cProps, outer, dp)
        
        # Extract the value measures directly related to the kpp measures  
        classes = [[0, "measurement type specification"],
                   [1, "IAO_0000100"],
                   [2, "IAO_0000100"],
                   [0, "preference"],
                   [0, "model"],
                   [3, "estimate"]]
        
        ids = ["_spec", "_dset", "_dset", "_pref", "_model", "_est"]
        
        qProps = [[1, 2, "is_related_to"],
                  [2, 1, "is_related_to"]]
        
        bProps = [[1, 0, "conforms_to"],
                  [2, 0, "conforms_to"],
                  [2, 3, "is about"],
                  [2, 4, "has basis"],
                  [5, 4, "has basis"],
                  [4, 3, "is model of"],
                  [0, 4, "specifies"],
                  [5, 3, "is a measurement of"],
                  [1, 2, "has part"],
                  [1, 5, "has part"]]
        
        cProps = [[0, 0, "represents"],
                  [1, 1, "represents"],
                  [2, 2, "represents"],
                  [3, 5, "represents"]]
        outer = []
        dp = [[5, 4, "has_value"], [2, 5, "name_dp"]]
        
        q="""
        SELECT ?class ?inst ?vinst ?vslot ?value ?name
        WHERE {
            ?vlit SysML:value_dp ?value .
            ?vlit SysML:ownerId ?vslot .
            ?vslot SysML:definingFeatureId / SysML:name_dp "value"^^xsd:string .
            ?vslot SysML:ownerId ?vinst .
            ?vinst SysML:classifierIds ?class .
            ?class SysML:name_dp ?name
            {SELECT ?inst ?vinst 
             WHERE {
                   ?inst SysML:classifierIds / SysML:name_dp "Values"^^xsd:string .
                   ?lit SysML:ownerId / SysML:ownerId ?inst .
                   ?lit SysML:instanceId ?vinst .            
            }}
        }
        """
        decGraph = qMgr.graphBranchQuery(q, ograph, decGraph, 
                                         classes, ids, qProps, 
                                         bProps, cProps, outer, dp)
        
        return decGraph


class OntoDataInterface(object):

    def __init__(self, mgr):
        self.mgr = mgr

    def getBaseOntology(self, onto, classes, properties):
        # extract the mapping from the data
        # create the new classes
        for c in classes:
            if c not in self.mgr.ontodict.ontology["Classes"]:
                self.mgr.constructTerm(onto, c, None, "Class")

        # create new properties for each field in the mapping
        for p in properties:
            if p not in self.mgr.ontodict.ontology["termDict"]:
                    if p +"_dp" in self.mgr.ontodict.ontology["termDict"]:  
                        self.mgr.ontodict.ontology["DataProperties"][p]=self.mgr.ontodict.ontology["DataProperties"][p+"_dp"]
                    else:
                        self.mgr.constructTerm(onto,
                                               p,
                                               "owl.ObjectProperty",
                                               "ObjectProperty")
                        
    def createInstances(self, onto, instances):
        # construct all individuals having an id field
        for inst in instances:
            instname = inst[0]
            instclass = inst[1]

            # Fill in any missing classes on the fly
            if instclass not in self.mgr.ontodict.ontology["Classes"]: 
                self.mgr.constructTerm(onto, str(instclass), None, "Class")
                            
            if instname is not None:
                self.mgr.constructTerm(onto, instname, instclass, "Individual")

    def createTriples(self, onto, triples, spec):

        for t in triples:
            # subject is the elements
            # object is the ontology object corresponding to the ke
            subject = t[0]
            obj = t[1]
            predicate = t[2]

            # double check the subject is actually in the dictionary
            if subject in self.mgr.ontodict.ontology["Individuals"]:

                # Same for the predicate - check if predicate is an individual
                # or if object is a data property
                if type(predicate) != list and type(predicate) != dict:
                    if predicate in self.mgr.ontodict.ontology["Individuals"]:
                        # construct the triple with an object property
                        self.mgr.constructTriple(subject, obj, predicate)

                    # If not object property, make a data property
                    elif obj in self.mgr.ontodict.ontology["DataProperties"]:
                        self.mgr.constructTriple(subject, obj, predicate)

                    else:
                        # Otherwise fix the relation and create the triples
                        self.mgr.fixProperty(onto, obj, spec)

                        # then build the triple using teh new data property
                        self.mgr.constructTriple(subject, obj, predicate)

    def cleanTriples(self, instances, triples):
        for index, element in reversed(list(enumerate(triples))):
            pr = element[2]

            # skip empty fields ( majority of many files)
            if (pr is None) or (pr == ''):
                del triples[index]

            # populate axioms
            elif type(pr) == list:
                del triples[index]
                for entry in pr:
                    if entry != '' and entry is not None:
                        triples.append([element[0], element[1], entry])
        return triples


class JsonParser(OntoDataInterface):
    # parses raw json string into a dictionary
    # secodnary function pulls sub=elements up to higher levles for easy access
    # contains a map of all fields in all json files read in, as well as all
    # elements

    def __init__(self, mgr, idkwd, typekwd, speckwd):

        # call superclass __init__ function
        super().__init__(mgr)

        # populate sub-class specific instance level variables
        self.parsed = {}
        self.fields = []
        self.typeList = []
        self.idkwd = idkwd
        self.typekwd = typekwd
        self.speckwd = speckwd

    def parseFile(self, pathIn, fileIn, kwd):
        # reads a JSON file into the JsonParser object, appends its elements to
        # the internal element list "parsed"
        with open(pathIn + "\\" + fileIn) as file:
            jsonString = file.read()
        parse = JsonParser.getParsedJSON(self, jsonString, kwd)
        return parse

    def getParsedJSON(self, jsonString, kwd):
        # takes a string formatted in JSON syntax and parses it into
        # a dictionary of elements. Also searches down several levels
        # future versions should include recursive searches

        # built in extracts the top of the file
        if jsonString:
            parse = json.loads(jsonString)
            count = 0
    
            # iterate over all keys, assume multi-level structure
            for key in parse.keys():
                clength = len(parse[key]) - 1
                count = 0
                # use count to understand current length
                for count in range(len(parse[key])):
                    ob = parse[key][count]
    
                    for obj in ob.keys():
                        if type(ob[obj]) is dict:
                            parse[key].append(ob[obj])
                            clength += 1
    
                        elif type(ob[obj]) is list:
                            for l in ob[obj]:
                                if type(l) is dict:
                                    parse[key].append(l)
                                    clength += 1
    
            # pass to internal repository of parsed JSON elements
            parse = parse[kwd]
            for element in parse:
                self.parsed.update({str(element): element})
            return self.parsed

    def getFields(self, parse):
        # pushes a set of parsed elements into a instance level map
        fields = []
        for el in parse:
            for key in parse[el]:
                if (key not in fields and
                    key != self.typekwd and
                        key != self.idkwd):

                    fields.append(key)
        return fields

    def getTypes(self, parse):
        # updates individaul list of types and returns the internal variable
        typeList = []
        for e in parse:
            try:
                if parse[e][self.typekwd] not in typeList:
                    typeList.append(parse[e][self.typekwd])
            except Exception:
                pass
        return typeList

    def getJsonTriples(self, elements):
        # formats the current repository of the parsed  json dictionary
        # into a standard triple format
        instance = []
        instname = []
        triples = []
        newElements = {}
        for e in elements:
            if self.idkwd in elements[e] and self.typekwd in elements[e]:

                instance.append([elements[e][self.idkwd],
                                 elements[e][self.typekwd]])
                # keep track of instance names
                instname.append(elements[e][self.idkwd])
                for key in elements[e]:

                    # define subject, object, predicate (su, ob, pr)
                    su = elements[e][self.idkwd]
                    ob = key
                    pr = elements[e][key]

                    # screen dictionaries (full elements)
                    if type(pr) == dict:
                        newElements[str(pr)] = pr

                    elif type(pr) == list:
                        for l in pr:
                            if l is not None:
                                if (type(l) is not dict and type(l) is not list
                                        and "{" not in str(l)):
                                    # for normal list entries append to triples
                                    triples.append([su, ob, l])
                                else:
                                    # otherwise add on another new element
                                    newElements[str(l)] = l
                                    # try to assert a link
                                    try:
                                        triples.append([su, ob, l[self.idkwd]])
                                    except Exception:
                                        pass
#                    elif "{" in str(pr):
#                        continue # not sure how protege is handling these

                    # avoid instantiating identifier as a triple
                    elif ob == self.idkwd or ob == self.typekwd:
                        continue
                    # create the triple
                    else:
                        triples.append([su, ob, pr])

                # add in any special keywoads
                # these treat the field as an instance name, assert a relation
                # to that instance.
            for sp in self.speckwd:

                # only update for cases where eelment has keyword, and
                # instance doesn't already exist
                if sp in elements[e]:
                    if elements[e][sp] not in instname:
                        if type(elements[e][sp]) != list and type(elements[e][sp]) != None:
                            instname.append(elements[e][sp])
                            instance.append([elements[e][sp],
                                            str(self.mgr.defaultClass)])

                        else:
                            for i in elements[e][sp]:
                                if type(i) != None:
                                    instname.append(i)
                                    instance.append([i,
                                                 str(self.mgr.defaultClass)])
                    # construct triple every time special keyword appears
                    su = elements[e][self.idkwd]
                    ob = sp
                    pr = elements[e][sp]
                    triples.append([su, ob, pr])

        return instance, triples, newElements

    def toOntology(self, iriA):

        # Generate teh triples to be added to the triplestore
        # Keep going until we have all the elements
        instances, triples = [], []
        newElements = self.parsed

        # search down elements and sub-elements
        while newElements:
            [ninst, ntriple, newElements] = self.getJsonTriples(newElements)
            for i in ninst:
                instances.append(i)
            for i in ntriple:
                triples.append(i)

        # extract classes from self.parsed
        classes = self.getTypes(self.parsed)

        # extract field information
        fields = self.getFields(self.parsed)

        # first generate the object from the superclass manager object

        onto = self.mgr.world.get_ontology(iriA)

        # populate ontology with the local classes and properties
        self.getBaseOntology(onto, classes, fields)
        
        # double check all the properties are created (they can get missed)
        # future versions should parse better to remove this possiblity
        for t in triples:
            if type(t[1]) == list:
                print("\n\n"+t[2])
            if t[1] not in self.mgr.ontodict.ontology["ObjectProperties"]:
                self.mgr.constructTerm(onto,
                                       t[1],
                                       "owl.ObjectProperty",
                                       "ObjectProperty")
        # prepare URIDict for population
        self.mgr.uriOntoDict()         
        # create instances in the ontology file **consider separate file

        self.createInstances(onto, instances)

        # Get rid of empty fields in the triples
        self.cleanTriples(instances, triples)
        # build the triples
        self.createTriples(onto, triples, self.speckwd)

        return [onto, instances, triples]
    
    
class OntoDict(object):

    def __init__(self):

        # initialize internal variables
        ontology = {
                    'Classes': {},
                    'termDict': {},
                    'ObjectProperties': {},
                    'DataProperties': {},
                    'Individuals': {},
                    'labDict': {},
                    'included': []
                    }
        ontology["Classes"]["owl.Thing"] = owl.Thing
        ontology["ObjectProperties"]["owl.ObjectProperty"] = owl.ObjectProperty
        ontology["DataProperties"]["owl.DataProperty"] = owl.DataProperty
        self.ontology = ontology

    def populateDict(self, onto):
        # roll out ontology generators into searchable dictionaries

        # setup local version of ontology dictionary variable
        ontology = self.ontology

        # extract class dictionary
        ontology['Classes'].update(OntoDict.extractDict(onto.classes()))
        # update all-term dict with classes.
        ontology['termDict'].update(OntoDict.extractDict(onto.classes()))

        # objet property dictionary
        ontology['ObjectProperties'].update(OntoDict.extractDict(
                                            onto.object_properties()))
        ontology['termDict'].update(ontology['ObjectProperties'])

        # data property dictionary
        ontology['DataProperties'].update(OntoDict.extractDict(
                                            onto.data_properties()))
        ontology['termDict'].update(ontology['DataProperties'])

        # also populate individuals, though this is unliekly to be used
        ontology['Individuals'].update(OntoDict.extractDict(
                                            onto.individuals()))

        # use all-term dict to allow access through term labels
        ontology['labDict'].update(OntoDict.getLabDict(ontology['termDict']))

        # add ontology to teh "included" ontology list
        ontology['included'].append(onto)

        # pass updated ontology dictionary to instance level variable
        self.ontology.update(ontology)

    def getLabDict(termDict):
        # uses instance variable termDict to allow access by labels
        labDict = {}
        # create in-function copy for ease of calling
        # iterate over all terms
        for i in termDict:
            # check for a label
            try:
                if termDict[i].label:
                    # label dict for label key = term dict for classname key
                
                    labDict[termDict[i].label[0]] = termDict[i]
            except:
                pass
        return labDict

    def parseTerm(term):
        # convert generator names to strings, parse out nspace.term to just
        # term strings
        stTerm = str(term)
        count = 0

        # iterate over string and find "."
        for i in stTerm:
            count += 1
            if i == '.':
                break
        # subset the string to take everything right of "."
        stTerm = stTerm[count:]
        return stTerm

    def extractDict(genTerms):
        # Takes a generator from ontology to populate ontology dictionary
        # method allows ontology objects to be selected via user input strings

        dictOut = {}

        # move through term generator from ontology
        for obj in genTerms:
            # build the key
            key = OntoDict.parseTerm(obj)

            # create a dictionary entry for each term
            dictOut[key] = obj
        return dictOut


class OntoManager(object):

    # class used to start using ontologies, load / import new ontologies from
    # file locations

    def __init__(self, iri, defaultClass, world):
        # new ontology iri
        self.iri = iri
        # manager dictionary
        self.ontodict = OntoDict()
        # add default class to manager dictionary
        self.ontodict.ontology["Classes"][str(defaultClass)] = defaultClass
        # internal list of loaded ontologies
        self.ontoList = []
        # default values to be used if no others are specified.
        self.defaultClass = defaultClass
        self.defaultProperty = owl.ObjectProperty
        self.defaultDataProperty = owl.DataProperty
        
        # world object used within the manager
        self.world = world
        # initialize the manager dicitonary
        self.ontodict.populateDict(self.world) 
        
        # Note reserved keywords from owl / api
        self.reserved=["name", "value", "class"]

    def getOntologyFile(self, pathIn, fileIn):
        # pass the path to the triplestore manager
        owl.onto_path.append(pathIn)
        onto = self.world.get_ontology(pathIn+"\\"+fileIn)

        try:  # attempt to load file
            # load ontology terms into dictionary
            onto.load()
            self.ontodict.populateDict(onto)

        except Exception:
            pass
        # pass back ontology object
        return onto
     
    def destroyOntology(self, onto):
        for i in onto.classes():
            owl.destroy_entity(i)
        for i in onto.object_properties():
            owl.destroy_entity(i)
        for i in onto.individuals():
            owl.destroy_entity(i)
        for i in onto.data_properties():
            owl.destroy_entity(i)
        self.ontodict = OntoDict()

    def constructTerm(self, onto, term, superClass, termType):
        # interfaces with the OntoConstructor class to add terms to the
        # ontology. Allows single function call to appropriate constructor

        # create a new constructor object
        c = OntoConstructor(self.defaultClass, self.reserved)

        ontodict = self.ontodict
        # Use string input "termType" to identify the correct method to call
        if term not in self.ontodict.ontology["termDict"]:
            if termType == "Class":
                # if superclass is defined, use as the term superclass
                if superClass:
                    ontodict = c.constructClass(onto, term, superClass,
                                                self.ontodict)
                # otherwise, call the default top class
                else:
                    ontodict = c.constructClass(onto, term,
                                                self.defaultClass,
                                                self.ontodict)

            elif termType == "ObjectProperty":
                # if super property is specified, use that as the superproperty
                if superClass:
                    superClass = self.ontodict.ontology["ObjectProperties"
                                                        ][superClass]
                    ontodict = c.constructObjectProperty(onto,
                                                         term,
                                                         superClass,
                                                         self.ontodict)
                # otherwise just put under the top object property
                else:
                    ontodict = c.constructObjectProperty(onto,
                                                         term,
                                                         self.defaultProperty,
                                                         self.ontodict)

            elif termType == "DataProperty":
                if superClass:
                    superClass = self.ontodict.ontology["DataProperties"
                                                        ][superClass]
                    ontodict = c.constructDataProperty(onto,
                                                       term,
                                                       superClass,
                                                       self.ontodict)
                else:
                    ontodict = c.constructDataProperty(onto,
                                                       term,
                                                       self.defaultDataProperty,
                                                       self.ontodict)
        if termType == "Individual":
            # instantiate as member of specified class (superclass variable)
            if superClass:
                try:
                    superClass = self.ontodict.ontology["Classes"][superClass]
                except:
                     superClass = self.ontodict.ontology["labDict"][superClass]
                ontodict = c.constructIndividual(onto,
                                                 term,
                                                 superClass,
                                                 self.ontodict)
            # or if not available instantiate as a member of the default class
            else:
                ontodict = c.constructIndividual(onto,
                                                 term,
                                                 self.defaultClass,
                                                 self.ontodict)
            # update instance dictionary to updated version
        self.ontodict = ontodict

    def constructTriple(self, subject, obj, predicate):
        c = OntoConstructor(self.defaultClass, self.reserved)
#        print(subject)
#        print(obj)
#        print(predicate)
        subject = self.ontodict.ontology["Individuals"][subject]

        if (obj in self.ontodict.ontology["ObjectProperties"]
                and predicate in self.ontodict.ontology["Individuals"]):
            # confirmed object property, terms met to instantiate

            # extract object property and predicate instance
            obj = self.ontodict.ontology["ObjectProperties"][obj]
            predicate = self.ontodict.ontology["Individuals"][predicate]

            # build the property
            c.constructTriple(subject, obj, predicate)

#        elif (obj in self.ontodict.ontology["ObjectProperties"]
#             and predicate not in self.ontodict.ontology["Individuals"]):

#            obj = self.ontodict.ontology["ObjectProperties"][obj]
#            predicate = self.ontodict.ontology["Individuals"][predicate]

        elif obj in self.ontodict.ontology["DataProperties"]:
            # extract the data proeprty instance
            obj = self.ontodict.ontology["DataProperties"][obj]
            c.constructTriple(subject, obj, predicate)
        else:
            print("\nInvalid property Input: Input not in ontology dictionary")
            print(obj)
            print(predicate)
#            pass

    def fixProperty(self, onto, obj, spec):
        # destroym the original property:

        # fetch teh property
        if (obj in self.ontodict.ontology["ObjectProperties"] and
                obj not in spec):

            # recreate the property as a data property
            with onto:
                new = types.new_class(obj+"_dp",
                                      bases=(owl.DataProperty,),
                                      kwds=None,
                                      exec_body=None)
                self.ontodict.ontology["DataProperties"].update({obj: new})



class QueryManager(OntoManager):
    
    def __init__(self, iri, defaultClass, world):
        # run an OntoManager Initialization
        OntoManager.__init__(self, iri, defaultClass, world)
        
        # create an object level conjunctive graph
        self.TopGraph = rdf.ConjunctiveGraph()
        #set up uriDict
        self.uriDict= {}
        # create a local world
        self.objWorld = owl.World()
        # add on a query prefix
        self.prefix = """PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> 
                        PREFIX owl: <http://www.w3.org/2002/07/owl#> 
                        PREFIX bfo: <http://purl.obolibrary.org/obo/bfo/2.0/bfo.owl>
                        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
                        PREFIX obo: <http://purl.obolibrary.org/obo/>
                    """
        self.nspace = ["rdf", "owl", "bfo", "xsd", "obo"]
      
    def toGraph(self):        
        for ont in self.world.ontologies:
            # Extract the ontology Name:
            pos = 0
            for letter in ont:    
                if letter == "/" or letter == "\\":
                    flag = pos
                pos += 1
            nspace = ont[flag+1:]  
            
            if "\\" not in ont:
                nspace = nspace.replace("#","")    
                nspace = nspace.replace(".owl","")
                nspace = nspace.replace("%20","_")
                nspace = nspace.replace(".","")
                prefix = "PREFIX "+nspace+": <"+ont+">\n"
                if nspace not in self.nspace:
                    self.prefix += prefix
                    self.nspace.append(nspace)
        
        # send world to an rdflib graph
        qGraph = self.world.as_rdflib_graph()
        
        # update the uriDict to reflect world
        self.uriOntoDict()
        return qGraph

    def getURIRef(self, term):
        # takes in a generic term string, returns a URIRef object for use in 
        # triple creation with rdflib
        
        iri = self.ontodict.ontology.termDict[term].iri
        newRef = rdf.URIRef(iri)
        return newRef
        
    def addInstance(self, iri, iName, iClass, graph):
        # adds a new named individaul to the graph having name iName and class
        # iClass  
        namedIndividual = rdf.URIRef('http://www.w3.org/2002/07/owl#NamedIndividual')
        rdftype = rdf.URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#type")

        nInst = rdf.URIRef(iri+iName)
        graph.add((nInst, rdftype, namedIndividual))
        graph.add((nInst, rdftype, iClass))
        
        # return instance URIRef
        return nInst 
        
    def addTriples(self, graph, s, p, o):
        # asserts all triples in an array of subjects, objects, and predicates
        if len(s) > len(o):
            for i in s:
                graph.add((i, p, o))
        else:
            for i in p:
                graph.add((s, p, i))
    
    def uriOntoDict(self):        
        #create URIRef lookup dict and save us all a lot of effort
        for i in self.ontodict.ontology["termDict"]:
            self.uriDict[i]=rdf.URIRef(self.ontodict.ontology["termDict"][i].iri)
        for i in self.ontodict.ontology["labDict"]:
            self.uriDict[i]=rdf.URIRef(self.ontodict.ontology["labDict"][i].iri)
            
    def graphBranchQuery(self,
                         query,
                         qGraph,
                         bGraph,
                         classes,
                         ids,
                         qProps,
                         bProps,
                         cProps,
                         outer,
                         *args):
        # query: SELECT SPARQL Query
        # qGraph: graph over which the query will be run
        # bGraph: branch graph where new assertions placed
        # classes = names of classes of new instnaces in the branch
        # ids: suffixes to form new instances in teh branch
        # format: [relation, domain index, range index]
        # qProps - asserted relations bewteen 2 terms in results
        # bProps - asserted relations between new instances in branch graph
        # asserted relations between query result and branch instance
        # outer is a reference to outside uriRefs [nInst loc, relation, uriRef]
        # run the query
        r = qGraph.query(self.prefix+query)
        
        # create temporary (tgraph) graph
        
      
        # iterate over the query results
        for result in r:
            # prepare instance creation in tgraph
            newInst = []
            for i, c in enumerate(classes):
                if classes[i]:
                    newInst.append([str(result[classes[i][0]])+ids[i], self.uriDict[classes[i][1]]])

            nInst=[]       
            # add the new instances to tgraph
            for i in newInst:
                nInst.append(self.addInstance("", i[0], i[1], bGraph))
            # assert relations between query results         
            for i in qProps:
                bGraph.add((result[i[0]],
                            self.uriDict[i[2]], 
                            result[i[1]]
                            ))
            # assert relations between branch graph instances
            for i in bProps:
                bGraph.add((nInst[i[0]],
                            self.uriDict[i[2]], 
                            nInst[i[1]]
                            ))
            # assert relations between query result andbranch graph instances        
            for i in cProps:
                bGraph.add((result[i[0]],
                            self.uriDict[i[2]], 
                            nInst[i[1]]
                            ))
            # assert out of query references
            for i in outer:
                bGraph.add((i[2], self.uriDict[i[1]], nInst[i[0]]))
            
            # assert data properties
            if args:
                for i in args:
                    for j in i:
                        bGraph.add((nInst[j[0]], 
                                    self.uriDict[j[2]],
                                    result[j[1]]))
                    
        
        return bGraph
        
    def graphBranchQuery2(self,
                         ontoD,
                         query,
                         qGraph,
                         classes,
                         ids,
                         qProps,
                         bProps,
                         cProps,
                         outer,
                         *args):
        # query: SELECT SPARQL Query
        # qGraph: graph over which the query will be run
        # bGraph: branch graph where new assertions placed
        # classes = names of classes of new instnaces in the branch
        # ids: suffixes to form new instances in teh branch
        # format: [relation, domain index, range index]
        # qProps - asserted relations bewteen 2 terms in results
        # bProps - asserted relations between new instances in branch graph
        # asserted relations between query result and branch instance
        # outer is a reference to outside uriRefs [nInst loc, relation, uriRef]
        # run the query
        
        result = qGraph.query(self.prefix + query)
        # iterate over the query results
        for r  in result:
            # prepare instance creation in tgraph
            newInst = []
            for i, c in enumerate(classes):
                if classes[i]:
                    newInst.append([str(r[classes[i][0]])+ids[i],
                                    classes[i][1]])

            nInst=[]       
            # add the new instances to tgraph
            for i in newInst:
                self.constructTerm(ontoD, i[0], i[1], "Individual")
                
                # make a URIRef so we can access the term later
                nInst.append(rdf.URIRef(i[0]))
       
            for i in qProps:
                ontoD.add_triple(r[i[0]], self.uriDict[i[2]], r[i[1]])

            # assert relations between branch graph instances
            for i in bProps:

                ontoD.add_triple(nInst[i[0]],
                                 self.uriDict[i[2]], 
                                 nInst[i[1]])
         
            # assert relations between query result andbranch graph instances        
            
            for i in cProps:
                ontoD.add_triple(r[i[0]],
                                 self.uriDict[i[2]], 
                                 nInst[i[1]]
                                 )
            # assert out of query references
            for i in outer:
                ontoD.add_triple(i[2], self.uriDict[i[1]], nInst[i[0]])
            
            # assert data properties
            if args:
                for i in args:
                    for j in i:
                        ontoD.add_triple(nInst[j[0]], 
                                    self.uriDict[j[2]],
                                    r[j[1]])           
        
        return ontoD

        
class OntoConstructor(object):
    # Class that interacts directly with ontologies the OntoManager using
    # the manager's ontoDict class or via objecs

    def __init__(self, defaultClass, reserved):
        # set instance defaults
        if defaultClass:
            self.defaultClass = defaultClass
        else:
            self.defaultClass = owl.Thing
        # add reserved terms that can break functions. These will be sanitized
        self.reserved = reserved

    def __enter__(self):
        return self

    def constructClass(self, onto, term, SuperClass, ontodict):
        # create the class object in the ontology namespace
        if term in self.reserved:
            suffix = "_term"
        else:
            suffix = ''
        # detect if SuperClass is populated, if not use default
        if not SuperClass:
            SuperClass = self.defaultClass

        # create the class in the ontology object onto
        with onto:
            New = types.new_class(
                                  term+suffix,
                                  bases=(SuperClass,),
                                  kwds=None,
                                  exec_body=None)

        # add the new class to the ontology dictionary
        ontodict.ontology['Classes'].update({term: New})
        ontodict.ontology['termDict'].update({term: New})

        # pass back the dictionary
        return ontodict

    def constructObjectProperty(self, onto, term, SuperProperty, ontodict):
        # constructs a new object property object, adds it to the dicitonary

        # sanitize the term if necessary
        if term in self.reserved:
            suffix = '_term'
        else:
            suffix = ''

        # check if superproperty is defined, use owl.ObjectProperty if no
        if not SuperProperty:
            SuperProperty = owl.ObjectProperty

        # create the new object property
        with onto:
            try:
                New = types.new_class(term+suffix,
                                      bases=(SuperProperty,),
                                      kwds=None,
                                      exec_body=None)
                # update ontology dictionary
                ontodict.ontology['ObjectProperties'].update({term: New})
                ontodict.ontology['termDict'].update({term: New})

            except Exception:
                nterm = term+suffix
                New = types.new_class(nterm, bases=(SuperProperty,),
                                      kwds=None, exec_body=None)
                ontodict.ontology['ObjectProperties'].update({term: New})
                ontodict.ontology['termDict'].update({term: New})

        # return the dictionary
        return ontodict

    def constructDataProperty(self, onto, term, SuperProperty, ontodict):
        # create a new data property under top-data property

        # sanitize the term if necessary
        if term in self.reserved:
            suffix = "_term"
        else:
            suffix = ''

        # check for a super property; if none use owl.DataProperty as default
        if not SuperProperty:
            SuperProperty = owl.DataProperty

        # add the data property to the onto ontology object
        with onto:
            New = types.new_class(term + suffix,
                                  (SuperProperty,),
                                  None, None)

        # update the ontology dictionary
        ontodict.ontology['DataProperties'].update({term: New})
        ontodict.ontology['termDict'].update({term: New})

        # pass back the dictionary
        return ontodict

    def constructIndividual(self, onto, term, termType, ontodict):
        # creates a new individual of type classname in the ontology

        # sanitize the term if necessary
        if term in self.reserved:
            suffix = '_term'
        # make sure we don't write over an existing term. Owlready can't have
        # multiple terms under the same identifying name
        elif term in ontodict.ontology["termDict"]:
            suffix = "_inst"
        else:
            suffix = ''

        # check to see if classname is defined. if no, use default
        if not termType:
            termType = self.defaultClass

        # add the individaul to the onto object
        NewIndividual = termType(name=term+suffix, namespace=onto)

        # add the term to the dictionary. Terms are assumed to be unique
        ontodict.ontology["Individuals"].update({term: NewIndividual})

        # return the dictionary.
        return ontodict

    def constructTriple(self, subject, obj, predicate):
        # creates a triple from a subject, object, and predicate
        # create a custom command. Owlready2 is tricky with properties

        command = "subject."+obj.name+".append(predicate)"
        # This is highly non-ideal. Look into better means to assert property
        try:
            eval(command)
        except Exception:
            print(obj)
        # this method is an alternative, but also problematic:
#        subject.is_a.append(obj.value(predicate))

    def constructDefault(defaultClass):
        pass
