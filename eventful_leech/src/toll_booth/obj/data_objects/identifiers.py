import json
import re
from collections import OrderedDict

from src.algernon import AlgObject


class InternalId:
    def __init__(self, internal_id):
        self._internal_id = internal_id

    @property
    def id_value(self):
        import hashlib

        return hashlib.md5(self._internal_id.encode('utf-8')).hexdigest()

    def __str__(self):
        return self.id_value


class IdentifierStem(AlgObject):
    def __init__(self, graph_type, object_type, paired_identifiers=None):
        if not paired_identifiers:
            paired_identifiers = OrderedDict()
        self._graph_type = graph_type
        self._object_type = object_type
        self._paired_identifiers = paired_identifiers

    @classmethod
    def from_raw(cls, identifier_stem):
        if isinstance(identifier_stem, IdentifierStem):
            return identifier_stem
        pieces = identifier_stem.split('#')
        graph_type = pieces[1]
        object_type = pieces[2]
        paired_identifiers = {}
        pattern = re.compile('({(.*?)})')
        potential_pairs = pattern.search(identifier_stem)
        if potential_pairs:
            paired_identifiers = json.loads(potential_pairs.group(0), object_pairs_hook=OrderedDict)
        return cls(graph_type, object_type, paired_identifiers)

    @classmethod
    def for_stub(cls, stub_vertex):
        identifier_stem = stub_vertex.identifier_stem
        try:
            identifier_stem = IdentifierStem.from_raw(identifier_stem)
            return identifier_stem
        except AttributeError:
            pass
        object_type = getattr(stub_vertex, 'object_type', 'UNKNOWN')
        paired_identifiers = {}
        for property_field in identifier_stem:
            property_value = stub_vertex.object_properties.get(property_field, None)
            if hasattr(property_value, 'is_missing'):
                property_value = None
            paired_identifiers[property_field] = property_value
        if not stub_vertex.is_properties_complete:
            object_type = object_type + '::stub'
        return cls('vertex', object_type, paired_identifiers)

    @classmethod
    def parse_json(cls, json_dict):
        return cls(
            json_dict['graph_type'], json_dict['object_type'],
            json_dict.get('paired_identifiers')
        )

    @property
    def object_type(self):
        return self._object_type

    @property
    def paired_identifiers(self):
        return self._paired_identifiers

    @property
    def is_edge(self):
        return self._graph_type == 'edge'

    @property
    def for_dynamo(self):
        return f'#SOURCE{str(self)}'

    @property
    def for_extractor(self):
        extractor_data = self._paired_identifiers.copy()
        extractor_data.update({
            'graph_type': self._graph_type,
            'object_type': self._object_type
        })
        return extractor_data

    @property
    def is_stub(self):
        return '::stub' in self._object_type

    @property
    def as_stub_for_object(self):
        return f'''#{self._graph_type}#{self._object_type}::stub#{self._string_paired_identifiers()}#'''

    def specify(self, identifier_stem, id_value):
        paired_identifiers = self._paired_identifiers.copy()
        paired_identifiers['identifier_stem'] = str(identifier_stem)
        paired_identifiers['id_value'] = int(id_value)
        return IdentifierStem(self._graph_type, self._object_type, paired_identifiers)

    def _string_paired_identifiers(self):
        return json.dumps(self._paired_identifiers)

    def get(self, item):
        if item == 'graph_type':
            return self._graph_type
        if item == 'object_type':
            return self._object_type
        if item in self._paired_identifiers.keys():
            return self._paired_identifiers[item]
        raise AttributeError

    def __getitem__(self, item):
        if item == 'graph_type':
            return self._graph_type
        if item == 'object_type':
            return self._object_type
        if item in self._paired_identifiers:
            return self._paired_identifiers[item]
        raise AttributeError

    def __str__(self):
        return f'''#{self._graph_type}#{self._object_type}#{self._string_paired_identifiers()}#'''


class MissingObjectProperty(AlgObject):
    @classmethod
    def is_missing(cls):
        return True

    @classmethod
    def parse_json(cls, json_dict):
        return cls()
