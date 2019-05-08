from datetime import datetime
from decimal import Decimal
from typing import Union

import dateutil

from src.toll_booth import MissingObjectProperty, InternalId, IdentifierStem, SensitiveData
from src.toll_booth.obj.schemata.entry_property import SchemaPropertyEntry
from src.toll_booth import SchemaVertexEntry, SchemaEdgeEntry


class ObjectRegulator:
    def __init__(self, schema_entry: Union[SchemaVertexEntry, SchemaEdgeEntry]):
        self._schema_entry = schema_entry
        self._internal_id_key = schema_entry.internal_id_key
        self._entry_properties_schema = schema_entry.entry_properties

    @property
    def schema_entry(self):
        return self._schema_entry

    def create_potential_vertex_data(self,
                                     object_data: dict,
                                     internal_id: InternalId = None,
                                     identifier_stem: IdentifierStem = None,
                                     id_value: Union[str, int, float, Decimal] = None):
        """

        Args:
            object_data:
            internal_id:
            identifier_stem:
            id_value:

        Returns:

        """
        object_properties = self._standardize_object_properties(object_data)
        if internal_id is None:
            internal_id = self._create_internal_id(object_properties)
        if identifier_stem is None:
            identifier_stem = self._create_identifier_stem(object_properties, object_data)
        if id_value is None:
            id_value = self._create_id_value(object_properties)
        object_properties = self._obfuscate_sensitive_data(internal_id, object_properties)
        return {
            'object_type': self._schema_entry.object_type,
            'internal_id': internal_id,
            'identifier_stem': identifier_stem,
            'id_value': id_value,
            'id_value_field': self._schema_entry.id_value_field,
            'object_properties': object_properties,
        }

    def _obfuscate_sensitive_data(self, internal_id: InternalId, object_properties: dict):
        returned_data = {}
        for property_name, entry_property in self._entry_properties_schema.items():
            property_value = object_properties[property_name]
            if property_value and entry_property.sensitive:
                if hasattr(property_value, 'is_missing'):
                    property_value = 'AlgernonSensitiveDataFieldMissingValue'
                    returned_data[property_name] = property_value
                    continue
                if not isinstance(internal_id, str):
                    raise RuntimeError(
                        f'object property named {property_name} is listed as being sensitive, but the parent object '
                        f'could not be uniquely identified. sensitive properties use their parent objects identifier '
                        f'to guarantee uniqueness. object containing sensitive properties generally can not be stubbed'
                    )
                sensitive_data = SensitiveData(property_value, property_name, internal_id)
                property_value = str(sensitive_data)
            returned_data[property_name] = property_value
        return returned_data

    def _standardize_object_properties(self, object_data: dict):
        returned_properties = {}
        for property_name, entry_property in self._entry_properties_schema.items():
            try:
                test_property = object_data[property_name]
            except KeyError:
                returned_properties[property_name] = MissingObjectProperty()
                continue
            test_property = self._set_property_data_type(property_name, entry_property, test_property)
            returned_properties[property_name] = test_property
        return returned_properties

    def _create_internal_id(self, object_properties: dict, for_known: bool = False):
        static_key_fields = {
            'object_type': self._schema_entry.entry_name,
            'id_value_field': self._schema_entry.id_value_field
        }
        try:
            key_values = []
            internal_id_key = self._schema_entry.internal_id_key
            for field_name in internal_id_key:
                if field_name in static_key_fields:
                    key_values.append(str(static_key_fields[field_name]))
                    continue
                if hasattr(field_name, 'is_missing'):
                    key_values.append('MISSING_OBJECT_PROPERTY')
                key_value = object_properties[field_name]
                key_values.append(str(key_value))
            id_string = ''.join(key_values)
            internal_id = InternalId(id_string).id_value
            return internal_id
        except KeyError:
            if for_known:
                raise RuntimeError(
                    f'could not calculate internal id for a source/known object, this generally indicates that the '
                    f'extraction for that object was flawed. error for graph object: {object_properties}'
                )
            return self._internal_id_key

    def _create_identifier_stem(self, object_properties: dict, object_data: dict):
        try:
            paired_identifiers = {}

            identifier_stem_key = self._schema_entry.identifier_stem
            object_type = self._schema_entry.object_type
            for field_name in identifier_stem_key:
                try:
                    key_value = object_properties[field_name]
                except KeyError:
                    key_value = object_data[field_name]
                if isinstance(key_value, MissingObjectProperty):
                    return self._schema_entry.identifier_stem
                if key_value is None and '::stub' not in object_type:
                    object_type = object_type + '::stub'
                paired_identifiers[field_name] = key_value
            return IdentifierStem('vertex', object_type, paired_identifiers)
        except KeyError:
            return self._schema_entry.identifier_stem

    def _create_id_value(self, object_properties: dict):
        try:
            id_value = object_properties[self._schema_entry.id_value_field]
            vertex_properties = self._schema_entry.vertex_properties
            id_value_properties = vertex_properties[self._schema_entry.id_value_field]
            if id_value_properties.property_data_type == 'DateTime':
                remade_date_value = dateutil.parser.parse(id_value)
                id_value = Decimal(remade_date_value.timestamp())
            return id_value
        except KeyError:
            return self._schema_entry.id_value_field

    @classmethod
    def _set_property_data_type(cls,
                                property_name: str,
                                entry_property: Union[SchemaPropertyEntry, SchemaPropertyEntry],
                                test_property):
        property_data_type = entry_property.property_data_type
        if not test_property:
            return None
        if test_property == '':
            return None
        if property_data_type == 'Number':
            try:
                return Decimal(test_property)
            except TypeError:
                return Decimal(test_property.timestamp())
        if property_data_type == 'String':
            return str(test_property)
        if property_data_type == 'DateTime':
            return cls._convert_python_datetime_to_gremlin(test_property)
        raise NotImplementedError(
            f'data type {property_data_type} for property named: {property_name} is unknown to the system')

    @classmethod
    def _convert_python_datetime_to_gremlin(cls, python_datetime: datetime):
        from pytz import timezone
        gremlin_format = '%Y-%m-%dT%H:%M:%S%z'
        if isinstance(python_datetime, str):
            python_datetime = datetime.strptime(python_datetime, gremlin_format)
        if not python_datetime.tzinfo:
            naive_datetime = python_datetime.replace(tzinfo=None)
            utc_datetime = timezone('UTC').localize(naive_datetime)
            return utc_datetime.strftime(gremlin_format)
        return python_datetime.strftime(gremlin_format)
