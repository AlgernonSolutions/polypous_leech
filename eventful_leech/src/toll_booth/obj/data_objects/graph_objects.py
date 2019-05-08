from decimal import Decimal

from src.algernon import AlgObject, ajson

from src.toll_booth.obj.data_objects.identifiers import IdentifierStem


class GraphObject(AlgObject):
    def __init__(self, object_type, object_properties, internal_id, identifier_stem, id_value, id_value_field):
        self._object_type = object_type
        self._object_properties = object_properties
        self._internal_id = internal_id
        self._identifier_stem = identifier_stem
        self._id_value = id_value
        self._id_value_field = id_value_field
        self._graph_as_stub = False

    @classmethod
    def parse_json(cls, json_dict):
        return cls(
            json_dict['object_type'], json_dict['object_properties'], json_dict['internal_id'],
            json_dict['identifier_stem'], json_dict['id_value'], json_dict['id_value_field']
        )

    @property
    def object_type(self):
        return self._object_type

    @property
    def object_properties(self):
        return self._object_properties

    @property
    def internal_id(self):
        return self._internal_id

    @property
    def identifier_stem(self):
        return self._identifier_stem

    @property
    def id_value(self):
        return self._id_value

    @property
    def id_value_field(self):
        return self._id_value_field

    @property
    def graph_as_stub(self):
        return self._graph_as_stub

    @property
    def for_index(self):
        indexed_value = {
            'sid_value': str(self._id_value),
            'identifier_stem': str(self._identifier_stem),
            'internal_id': str(self._internal_id),
            'id_value': self._id_value,
            'object_type': self._object_type,
            'object_value': ajson.dumps(self),
            'object_properties': self._object_properties
        }
        if isinstance(self._id_value, int) or isinstance(self._id_value, Decimal):
            indexed_value['numeric_id_value'] = self._id_value
        for property_name, property_value in self._object_properties.items():
            indexed_value[property_name] = property_value
        return indexed_value

    @property
    def for_stub_index(self):
        return ajson.dumps(self)

    @property
    def is_edge(self):
        return '#edge#' in str(self._identifier_stem)

    @property
    def is_identifiable(self):
        try:
            identifier_stem = IdentifierStem.from_raw(self._identifier_stem)
        except AttributeError:
            return False
        if not self.is_internal_id_set:
            return False
        if not isinstance(identifier_stem, IdentifierStem):
            return False
        if not self.is_id_value_set:
            return False
        return True

    @property
    def is_identifier_stem_set(self):
        try:
            IdentifierStem.from_raw(self._identifier_stem)
            return True
        except AttributeError:
            return False

    @property
    def is_properties_complete(self):
        for property_name, object_property in self._object_properties.items():
            if hasattr(object_property, 'is_missing'):
                return False
        return True

    @property
    def is_id_value_set(self):
        return self._id_value != self._id_value_field

    @property
    def is_internal_id_set(self):
        return isinstance(self._internal_id, str)

    def __getitem__(self, item):
        try:
            return getattr(self, item)
        except AttributeError:
            return self._object_properties[item]


class PotentialVertex(GraphObject):
    def __init__(self, object_type, internal_id, object_properties, identifier_stem, id_value, id_value_field):
        super().__init__(object_type, object_properties, internal_id, identifier_stem, id_value, id_value_field)

    @classmethod
    def parse_json(cls, json_dict):
        return cls(
            json_dict['object_type'], json_dict.get('internal_id'),
            json_dict.get('object_properties', {}), json_dict['identifier_stem'],
            json_dict.get('id_value'), json_dict.get('id_value_field')
        )

    @property
    def graphed_object_type(self):
        return self._identifier_stem.object_type

    def __str__(self):
        return f'{self._object_type}-{self.id_value}'


class PotentialEdge(GraphObject):
    def __init__(self, object_type, internal_id, object_properties, from_object, to_object):
        identifier_stem = IdentifierStem.from_raw(f'#edge#{object_type}#')
        id_value = internal_id
        id_value_field = 'internal_id'
        super().__init__(object_type, object_properties, internal_id, identifier_stem, id_value, id_value_field)
        self._from_object = from_object
        self._to_object = to_object

    @classmethod
    def parse_json(cls, json_dict):
        return cls(
            json_dict['object_type'], json_dict['internal_id'],
            json_dict['object_properties'], json_dict['from_object'], json_dict['to_object']
        )

    @property
    def edge_label(self):
        return self._object_type

    @property
    def graphed_object_type(self):
        return self.edge_label

    @property
    def edge_properties(self):
        return self._object_properties

    @property
    def from_object(self):
        return self._from_object

    @property
    def to_object(self):
        return self._to_object
