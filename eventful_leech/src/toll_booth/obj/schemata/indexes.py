from src.algernon import AlgObject


class SchemaIndexEntry(AlgObject):
    """

    """
    def __init__(self, index_name: str, index_type: str, is_unique: bool, indexed_fields: [str]):
        """

        Args:
            index_name:
            index_type:
            is_unique:
            indexed_fields:
        """
        self._index_name = index_name
        self._index_type = index_type
        self._is_unique = is_unique
        self._indexed_fields = indexed_fields

    @classmethod
    def parse_json(cls, json_dict: dict):
        return cls(
            json_dict['index_name'], json_dict.get('index_type', 'unspecified'),
            json_dict['is_unique'], json_dict['indexed_fields']
        )

    @property
    def index_name(self):
        return self._index_name

    @property
    def index_type(self):
        return self._index_type

    @property
    def is_unique(self):
        return self._is_unique

    @property
    def indexed_fields(self):
        return self._indexed_fields


class SortedSetIndexEntry(SchemaIndexEntry):
    """

    """
    def __init__(self, index_name: str, score_field: str, key_fields: [str]):
        super().__init__(index_name, 'sorted_set', False, {'score': score_field, 'key': key_fields})
        self._score = score_field
        self._key = key_fields

    @classmethod
    def parse(cls, index_dict: dict):
        try:
            return cls(index_dict['index_name'], index_dict['score'], index_dict['key'])
        except KeyError:
            index_properties = index_dict['index_properties']
            return cls(index_dict['index_name'], index_properties['score'], index_properties['key'])

    @property
    def score_field(self):
        return self._score

    @property
    def key_fields(self):
        return self._key


class UniqueIndexEntry(SchemaIndexEntry):
    """

    """
    def __init__(self, index_name: str, key_fields: [str]):
        super().__init__(index_name, 'unique', True, {'key': key_fields})
        self._key = key_fields

    @classmethod
    def parse(cls, index_dict: dict):
        try:
            return cls(index_dict['index_name'], index_dict['key'])
        except KeyError:
            index_properties = index_dict['index_properties']
            return cls(index_dict['index_name'], index_properties['key'])

    @property
    def key_fields(self):
        return self._key
