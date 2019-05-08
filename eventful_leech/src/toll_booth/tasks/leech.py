import logging
import os
from copy import deepcopy
from decimal import Decimal
from typing import Union, List, Dict

from src.algernon import queued, ajson
from src.algernon import lambda_logged, Bullhorn

from src.toll_booth import PotentialVertex, InternalId, IdentifierStem, PotentialEdge
from src.toll_booth import Ogm
from src.toll_booth.obj.index_manager import IndexManager
from src.toll_booth.obj.index_manager import UniqueIndexViolationException
from src.toll_booth import EdgeRegulator
from src.toll_booth import RuleArbiter
from src.toll_booth import ObjectRegulator
from src.toll_booth import VertexLinkRuleEntry
from src.toll_booth import Schema
from src.toll_booth import SchemaEdgeEntry, SchemaVertexEntry


@lambda_logged
@queued
def task(event, context):
    logging.info(f'started a call for a borg task, event: {event}, context: {context}')
    task_name = event['task_name']
    task_kwargs = event.get('task_kwargs', {})
    if task_kwargs is None:
        task_kwargs = {}
    task_function = getattr(LeechTasks, f'_{task_name}')
    results = task_function(**task_kwargs)
    logging.info(f'completed a call for borg task, event: {event}, results: {results}')
    return ajson.dumps(results)


class LeechTasks:
    @classmethod
    def _generate_source_vertex(cls,
                                schema: Schema,
                                schema_entry: SchemaVertexEntry,
                                extracted_data: Dict,
                                internal_id: InternalId = None,
                                identifier_stem: IdentifierStem = None,
                                id_value: Union[str, int, float, Decimal] = None) -> PotentialVertex:
        """Generates a source vertex from data extracted from a remote source per a schema entry

        Args:
            schema_entry: the SchemaEntry which specifies the integration of the data into the graph
            extracted_data: the data extracted from the
            internal_id: if the internal_id has been previously calculated, we can bypass it's creation
            identifier_stem: if the identifier_stem has been previously created, we can include it here
            id_value: if the id_value is already known, we can skip deriving it

        Returns:
            a PotentialVertex object which represents the data organized and parsed per the SchemaEntry
        """
        regulator = ObjectRegulator(schema_entry)
        object_data = extracted_data['source']
        source_vertex_data = regulator.create_potential_vertex_data(object_data, internal_id, identifier_stem, id_value)
        source_vertex = PotentialVertex(**source_vertex_data)
        Announcer.announce_derive_potential_connections(source_vertex, schema, schema_entry, extracted_data)
        Announcer.announce_index_and_graph(schema, source_vertex)
        return source_vertex

    @classmethod
    def _derive_potential_connections(cls,
                                      schema: Schema,
                                      schema_entry: Union[SchemaVertexEntry, SchemaEdgeEntry],
                                      source_vertex: PotentialVertex,
                                      extracted_data: Dict) -> [PotentialVertex]:
        """Generate a list of PotentialVertex objects indicated by the schema_entry

        Args:
            schema: the entire schema object that governs the data space
            schema_entry: the isolated entry for the source_vertex extracted from the remote space
            source_vertex: the PotentialVertex generated for the extracted object
            extracted_data: all the data extracted from the remote system

        Returns:

        """
        arbiter = RuleArbiter(source_vertex, schema, schema_entry)
        potential_vertexes = arbiter.process_rules(extracted_data)
        for vertex_entry in potential_vertexes:
            vertex = vertex_entry[0]
            rule_entry = vertex_entry[1]
            Announcer.announce_check_for_existing_vertexes(
                source_vertex, vertex, rule_entry, schema_entry, extracted_data)
        return potential_vertexes

    @classmethod
    def _check_for_existing_vertexes(cls,
                                     schema: Schema,
                                     schema_entry: Union[SchemaVertexEntry, SchemaEdgeEntry],
                                     source_vertex: PotentialVertex,
                                     potential_vertex: PotentialVertex,
                                     rule_entry: VertexLinkRuleEntry,
                                     extracted_data: Dict) -> List:
        """check to see if vertex specified by potential_vertex and rule_entry exists

        Args:
            schema: the graph schema that governs the data space
            rule_entry: the vertex_link_rule that specified the potential connection
            potential_vertex: the potential vertex that is being checked against the index

        Returns:
            a tuple containing a list of vertexes to connect the source_vertex to

        """
        index_manager = IndexManager.from_graph_schema(schema)
        found_vertexes = index_manager.find_potential_vertexes(
            potential_vertex.object_type, potential_vertex.object_properties)
        if potential_vertex.is_properties_complete and potential_vertex.is_identifiable:
            Announcer.announce_generate_potential_edge(
                schema, source_vertex, potential_vertex, rule_entry, schema_entry, extracted_data)
            return [potential_vertex]
        if found_vertexes:
            for identified_vertex in found_vertexes:
                Announcer.announce_generate_potential_edge(
                    schema, source_vertex, identified_vertex, rule_entry, schema_entry, extracted_data)
            return found_vertexes
        if rule_entry.is_stub:
            Announcer.announce_generate_potential_edge(
                schema, source_vertex, potential_vertex, rule_entry, schema_entry, extracted_data)
            return [potential_vertex]
        return []

    @classmethod
    def _generate_potential_edge(cls,
                                 schema: Schema,
                                 schema_entry: Union[SchemaVertexEntry, SchemaEdgeEntry],
                                 source_vertex: PotentialVertex,
                                 identified_vertex: PotentialVertex,
                                 rule_entry: VertexLinkRuleEntry,
                                 extracted_data: Dict) -> PotentialEdge:
        """Generate a PotentialEdge object between a known source object and a potential vertex

        Args:
            schema: the schema governing the data space
            schema_entry: the SchemaEntry which specifies how the data should be integrated
            source_vertex: the PotentialVertex generated from the extracted data
            identified_vertex: the vertex present in the data space to attach the source_vertex to
            rule_entry: the rule used to generate the expected link
            extracted_data: the data extracted from the remote source

        Returns:
            a PotentialEdge object for the potential connection between the source vertex and the potential other
        """
        edge_regulator = EdgeRegulator(schema_entry)
        inbound = rule_entry.inbound
        edge_data = edge_regulator.generate_potential_edge_data(source_vertex, source_vertex, extracted_data, inbound)
        potential_edge = PotentialEdge(**edge_data)
        Announcer.announce_index_and_graph(schema, source_vertex, identified_vertex, potential_edge)
        return potential_edge

    @classmethod
    def _graph(cls,
               schema: Schema,
               source_vertex: PotentialVertex,
               vertex: PotentialVertex = None,
               edge: PotentialEdge = None) -> List[str]:
        """Graphs objects to the graph space

        Args:
            schema: the schema governing the graph data space
            source_vertex: the potential vertex generated from the remote system
            vertex: a potential vertex, if present, to connect the source
            edge: a potential edge, if needed, to join the source_vertex to the potential vertex

        Returns:
            a list of all the commands executed against the graph database

        """
        ogm = Ogm(schema)
        graph_results = ogm.graph_objects(source_vertex, vertex, edge)
        return graph_results

    @classmethod
    def _index(cls,
               schema: Schema,
               source_vertex: PotentialVertex,
               vertex: PotentialVertex = None,
               edge: PotentialEdge = None):
        """Writes objects to the index

        Args:
            schema: the schema governing the graph system
            source_vertex: the vertex representing the data extracted from the remote system
            vertex: if the source_vertex assimilates to the graph, it will connect on this vertex
            edge: if the source_vertex is assimilated, connect using this edge

        Returns: None

        """
        index_manager = IndexManager.from_graph_schema(schema)
        try:
            index_manager.index_object(source_vertex)
        except UniqueIndexViolationException as e:
            logging.warning(f'tried to index source_vertex: {source_vertex}, seems it has already been graphed: {e} '
                            f'this is not likely not a problem, but logging it just in case')
        if vertex:
            try:
                index_manager.index_object(vertex)
            except UniqueIndexViolationException as e:
                logging.warning(
                    f'tried to index potential_vertex: {vertex}, seems it has already been graphed: {e} '
                    f'this is not likely not a problem, but logging it just in case')
        if edge:
            try:
                index_manager.index_object(edge)
            except UniqueIndexViolationException as e:
                logging.warning(
                    f'tried to graph edge: {edge}, seems it has already been graphed: {e} '
                    f'this is not likely not a problem, but logging it just in case')


class Announcer:
    _bullhorn = Bullhorn()
    _topic_arn = os.environ['LEECH_LISTENER_ARN']
    _vpc_topic_arn = os.environ['VPC_LEECH_LISTENER_ARN']

    @classmethod
    def _send_message(cls, message: Dict, is_vpc: bool = False):
        topic_arn = cls._topic_arn
        if is_vpc:
            topic_arn = cls._vpc_topic_arn
        cls._bullhorn.publish('new_event', topic_arn, ajson.dumps(message))

    @classmethod
    def announce_check_for_existing_vertexes(cls,
                                             source_vertex: PotentialVertex,
                                             vertex: PotentialVertex,
                                             rule_entry: VertexLinkRuleEntry,
                                             schema_entry: Union[SchemaVertexEntry, SchemaEdgeEntry],
                                             extracted_data: Dict):
        message = {
            'task_name': 'check_for_existing_vertexes',
            'task_kwargs': {
                'source_vertex': source_vertex,
                'potential_vertex': vertex,
                'rule_entry': rule_entry,
                'schema_entry': schema_entry,
                'extracted_data': extracted_data,

            }
        }
        cls._send_message(message)

    @classmethod
    def announce_derive_potential_connections(cls,
                                              source_vertex: PotentialVertex,
                                              schema: Schema,
                                              schema_entry: Union[SchemaVertexEntry, SchemaEdgeEntry],
                                              extracted_data: Dict):
        message = {
            'task_name': 'derive_potential_connections',
            'task_kwargs': {
                'source_vertex': source_vertex,
                'schema': schema,
                'schema_entry': schema_entry,
                'extracted_data': extracted_data
            }
        }
        cls._send_message(message)

    @classmethod
    def announce_generate_potential_edge(cls,
                                         schema: Schema,
                                         source_vertex: PotentialVertex,
                                         identifier_vertex: PotentialVertex,
                                         rule_entry: VertexLinkRuleEntry,
                                         schema_entry: Union[SchemaVertexEntry, SchemaEdgeEntry],
                                         extracted_data: Dict):
        message = {
            'task_name': 'generate_potential_edge',
            'task_kwargs': {
                'schema': schema,
                'source_vertex': source_vertex,
                'identified_vertex': identifier_vertex,
                'rule_entry': rule_entry,
                'schema_entry': schema_entry,
                'extracted_data': extracted_data
            }
        }
        cls._send_message(message)

    @classmethod
    def announce_index_and_graph(cls,
                                 schema: Schema,
                                 source_vertex: PotentialVertex,
                                 identified_vertex: PotentialVertex = None,
                                 potential_edge: PotentialEdge = None):
        message = {
            'task_name': 'index',
            'task_kwargs': {
                'schema': schema,
                'vertex': identified_vertex,
                'source_vertex': source_vertex,
                'edge': potential_edge
            }
        }
        graph_message = deepcopy(message)
        graph_message['task_name'] = 'graph'
        cls._send_message(message)
        cls._send_message(graph_message, True)
