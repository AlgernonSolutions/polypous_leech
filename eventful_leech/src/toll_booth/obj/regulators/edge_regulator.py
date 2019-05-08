from src.toll_booth import PotentialEdge, InternalId, PotentialVertex
from src.toll_booth import ObjectRegulator
from src.toll_booth import SchemaEdgeEntry
from src.toll_booth import EdgePropertyEntry


class EdgeRegulator(ObjectRegulator):
    def generate_potential_edge_data(self,
                                     source_vertex: PotentialVertex,
                                     potential_other: PotentialVertex,
                                     extracted_data: dict,
                                     inbound: bool) -> dict:
        """Generates the data required to construct a potential edge

        Args:
            source_vertex: the known vertex, which was extracted from the remote system
            potential_other: the potential vertex, which is specified by the schema
            extracted_data: data returned from the extraction in addition to the source data
            inbound: if the edge terminates at the source vertex, instead of originating from it

        Returns:
            A dict containing the generated data for the potential edge between
            the source vertex and the potential other vertex
        """
        edge_properties = self._generate_edge_properties(source_vertex, potential_other, extracted_data, inbound)
        edge_properties = self._standardize_edge_properties(edge_properties, source_vertex, potential_other, inbound)
        try:
            edge_internal_id = self._create_edge_internal_id(source_vertex, potential_other, edge_properties, inbound)
        except KeyError:
            edge_internal_id = self._schema_entry.internal_id_key_fields
        source_internal_id = source_vertex.internal_id
        potential_other_id = potential_other.internal_id
        edge_data = {
            'edge_label': self._schema_entry.edge_label,
            'edge_internal_id': edge_internal_id,
            'edge_properties': edge_properties,
            'source_internal_id': source_internal_id,
            'potential_other_id': potential_other_id
        }
        if inbound:
            edge_data.update({
                'source_internal_id': potential_other_id,
                'potential_other_id': source_internal_id
            })
        return edge_data

    def generate_stubbed_edge(self,
                              source_vertex: PotentialVertex,
                              stubbed_other,
                              extracted_data: dict,
                              inbound: bool):
        edge_label = self._schema_entry.edge_label
        edge_properties = self._generate_edge_properties(
            source_vertex, stubbed_other, extracted_data, inbound, True)
        source_vertex_internal_id = source_vertex.internal_id
        stub_properties = stubbed_other.vertex_properties
        if inbound:
            return PotentialEdge(edge_label, None, edge_properties, stub_properties, source_vertex_internal_id)
        return PotentialEdge(edge_label, None, edge_properties, source_vertex_internal_id, stub_properties)

    def _standardize_edge_properties(self,
                                     edge_properties: dict,
                                     source_vertex: PotentialVertex,
                                     potential_other: PotentialVertex,
                                     inbound: bool):
        returned_properties = self._standardize_object_properties(edge_properties)
        accepted_source_vertexes = self._schema_entry.from_types
        accepted_target_vertexes = self._schema_entry.to_types
        source_object_type = source_vertex.object_type
        potential_other_type = potential_other.object_type
        try:
            self._validate_edge_origins(accepted_source_vertexes, source_object_type, potential_other_type, inbound)
            self._validate_edge_origins(accepted_target_vertexes, potential_other_type, source_object_type, inbound)
        except RuntimeError:
            raise RuntimeError(
                f'error trying to build a {self._schema_entry.edge_label} edge between '
                f'{source_vertex} and {potential_other}, '
                f'schema constraint fails, accepted vertexes: {accepted_source_vertexes}/{accepted_target_vertexes}'
            )
        return returned_properties

    def _validate_edge_origins(self,
                               accepted_vertex_types: [str],
                               test_vertex: PotentialVertex,
                               other_vertex: PotentialVertex,
                               inbound: bool):
        if '*' in accepted_vertex_types:
            return
        if inbound:
            if other_vertex in accepted_vertex_types:
                return
        if test_vertex in accepted_vertex_types:
            return
        raise RuntimeError(f'attempted to create a {self._schema_entry.edge_label} edge '
                           f'between {test_vertex} and {other_vertex}, '
                           f'but failed constraint for edge origins, accepted types: {accepted_vertex_types}')

    def _create_edge_internal_id(self,
                                 source_vertex: PotentialVertex,
                                 potential_other: PotentialVertex,
                                 edge_properties: dict,
                                 inbound: bool):
        key_values = []
        for key_field in self._schema_entry.internal_id_key:
            if 'to.' in key_field:
                source_key_field = key_field.replace('to.', '')
                source_object = potential_other
                if inbound:
                    source_object = source_vertex
                key_value = source_object[source_key_field]
                key_values.append(key_value)
                continue
            if 'from.' in key_field:
                source_key_field = key_field.replace('from.', '')
                source_object = source_vertex
                if inbound:
                    source_object = potential_other
                key_value = source_object[source_key_field]
                key_values.append(key_value)
                continue
            if 'schema.' in key_field:
                key_field = key_field.replace('schema.', '')
                key_value = getattr(self._schema_entry, key_field)
                key_values.append(key_value)
                continue
            key_value = edge_properties[key_field]
            key_values.append(key_value)
        internal_id = InternalId(''.join(key_values))
        return internal_id.id_value

    def _generate_edge_properties(self,
                                  source_vertex: PotentialVertex,
                                  potential_other: PotentialVertex,
                                  extracted_data: dict,
                                  inbound: bool,
                                  for_stub=False):
        """

        Args:
            source_vertex:
            potential_other:
            extracted_data:
            inbound:
            for_stub:

        Returns:

        """
        edge_properties = {}
        for edge_property_name, edge_property in self._entry_properties_schema.items():
            try:
                edge_value = self._generate_edge_property(
                    edge_property_name, edge_property, source_vertex,
                    potential_other, extracted_data, inbound)
            except KeyError:
                if for_stub:
                    edge_value = None
                else:
                    raise RuntimeError(
                        'could not derive value for edge property: %s, %s' % (edge_property_name, edge_property))
            edge_properties[edge_property_name] = edge_value
        return edge_properties

    def _generate_edge_property(self,
                                edge_property_name: str,
                                property_schema: EdgePropertyEntry,
                                source_vertex: PotentialVertex,
                                potential_other: PotentialVertex,
                                extracted_data: dict,
                                inbound: bool) -> dict:
        """

        Args:
            edge_property_name:
            property_schema:
            source_vertex:
            potential_other:
            extracted_data:
            inbound:

        Returns:

        """
        property_source = property_schema.property_source
        source_type = property_source['source_type']
        if source_type == 'source_vertex':
            return self._generate_vertex_held_property(property_source, source_vertex, potential_other, inbound)
        if source_type == 'target_vertex':
            return self._generate_vertex_held_property(property_source, potential_other, source_vertex, inbound)
        if source_type == 'extraction':
            return self._derive_extracted_property(
                edge_property_name, property_source['extraction_name'], extracted_data)
        if source_type == 'function':
            return self._execute_property_function(
                property_source['function_name'], source_vertex, potential_other, extracted_data, self._schema_entry,
                inbound
            )
        raise NotImplementedError('edge property source: %s is not registered with the system' % source_type)

    @staticmethod
    def derive_source_internal_id(source_vertex: PotentialVertex,
                                  potential_other: PotentialVertex,
                                  inbound: bool):
        if inbound:
            return potential_other.internal_id
        return source_vertex.internal_id

    @staticmethod
    def _generate_vertex_held_property(property_source: dict,
                                       holding_vertex: PotentialVertex,
                                       other_vertex: PotentialVertex,
                                       inbound: bool):
        vertex_property_name = property_source['vertex_property_name']
        if inbound:
            return other_vertex[vertex_property_name]
        return holding_vertex[vertex_property_name]

    @staticmethod
    def _derive_extracted_property(property_name: str,
                                   extraction_name: str,
                                   extracted_data: dict):
        potential_properties = set()
        try:
            target_extraction = extracted_data[extraction_name]
        except KeyError:
            raise RuntimeError(f'during the extraction derivation of an edge property, a KeyError was encountered, '
                               f'extraction data source named: {extraction_name} was not found in the extracted data: '
                               f'{extracted_data}')
        for extraction in target_extraction:
            potential_properties.add(extraction[property_name])
        if len(potential_properties) > 1:
            raise RuntimeError(
                'attempted to derive an edge property from an extraction, but the extraction yielded multiple '
                'potential values, currently only one extracted value per extraction is supported, '
                'property_name: %s, extraction_name: %s, extracted_data: %s' % (
                    property_name, extraction_name, extracted_data)
            )
        for _ in potential_properties:
            return _

    @staticmethod
    def _execute_property_function(function_name: str,
                                   source_vertex: PotentialVertex,
                                   ruled_target: PotentialVertex,
                                   extracted_data: dict,
                                   schema_entry: SchemaEdgeEntry,
                                   inbound: bool):
        from src.toll_booth import specifiers
        try:
            specifier_function = getattr(specifiers, function_name)
        except AttributeError:
            raise NotImplementedError('specifier function named: %s is not registered with the system' % function_name)
        return specifier_function(
            source_vertex=source_vertex, ruled_target=ruled_target, extracted_data=extracted_data,
            schema_entry=schema_entry, inbound=inbound)
