import sys
import uuid

import pytest

from pypsrp.complex_objects import ComplexObject, GenericComplexObject, \
    ListMeta, ObjectMeta, StackMeta
from pypsrp.exceptions import SerializationError
from pypsrp.serializer import Serializer
from pypsrp._utils import to_string, to_unicode

try:  # pragma: no cover
    from queue import Queue, Empty
except ImportError:  # pragma: no cover
    from Queue import Queue, Empty

if sys.version_info[0] == 2 and sys.version_info[1] < 7:  # pragma: no cover
    # ElementTree in Python 2.6 does not support namespaces so we need to use
    # lxml instead for this version
    from lxml import etree as ET
    element_type = ET._Element
else:  # pragma: no cover
    import xml.etree.ElementTree as ET
    element_type = ET.Element


class TestSerializer(object):

    @pytest.mark.parametrize('input_val, expected', [
        ["0123456789abcdefghijklmnopqrstuvwxyz_",
         "0123456789abcdefghijklmnopqrstuvwxyz_"],
        ["actual_x000A_string\nnewline",
         "actual_x005F_x000A_string_x000A_newline"],
        ["treble clef %s" % b"\xd8\x34\xdd\x1e".decode('utf-16-be'),
         "treble clef _xD834__xDD1E_"],
        [None, None]
    ])
    def test_serialize_string(self, input_val, expected):
        serializer = Serializer()

        actual_serial = serializer._serialize_string(input_val)
        assert actual_serial == expected
        actual_deserial = serializer._deserialize_string(actual_serial)
        assert actual_deserial == (input_val or "")

    @pytest.mark.parametrize('data, expected', [
        [u"a", "<S>a</S>"],
        ["a", "<S>a</S>"],
        [1, "<I32>1</I32>"],
        [True, "<B>true</B>"],
        [False, "<B>false</B>"],
        [10.0323, "<Sg>10.0323</Sg>"],
        [uuid.UUID(bytes=b"\x00" * 16),
         "<G>00000000-0000-0000-0000-000000000000</G>"]
    ])
    def test_serialize_primitives(self, data, expected):
        serializer = Serializer()

        actual = serializer.serialize(data)
        actual_xml = to_unicode(ET.tostring(actual))
        expected_xml = to_unicode(expected)
        assert actual_xml == expected_xml

        deserial_actual = serializer.deserialize(actual)
        assert deserial_actual == data

    @pytest.mark.skipif(sys.version_info < (3, 4),
                        reason="Byte string is designed to only work on py3")
    def test_serialize_byte_string_py3(self):
        serialzier = Serializer()
        expected = "<BA>YWJj</BA>"
        actual = serialzier.serialize(b"abc")
        actual_xml = to_unicode(ET.tostring(actual))
        expected_xml = to_unicode(expected)
        assert actual_xml == expected_xml

    def test_serialize_queue(self):
        serializer = Serializer()
        data = Queue()
        data.put("0")
        data.put("1")
        data.put("2")
        expected = \
            '<Obj RefId="0"><TN RefId="0"><T>System.Collections.Queue</T>' \
            '<T>System.Object</T></TN>' \
            '<QUE><S>0</S><S>1</S><S>2</S></QUE></Obj>'
        actual = serializer.serialize(data)
        actual_xml = to_string(ET.tostring(actual))
        assert actual_xml == expected

        deserial_actual = serializer.deserialize(actual)
        assert isinstance(deserial_actual, Queue)
        assert deserial_actual.get() == "0"
        assert deserial_actual.get() == "1"
        assert deserial_actual.get() == "2"
        with pytest.raises(Empty):
            deserial_actual.get(block=False)

    def test_serialize_stack(self):
        # Python doesn't have a native type so serializing a list will reverse
        # the entries as a stack is last in first out. When deserializing we
        # don't reverse the entries as .pop(0) should return the last entry
        serializer = Serializer()
        data = []
        data.append("0")
        data.append("1")
        data.append("2")
        expected = \
            '<Obj RefId="0"><TN RefId="0"><T>System.Collections.Stack</T>' \
            '<T>System.Object</T></TN>' \
            '<STK><S>2</S><S>1</S><S>0</S></STK></Obj>'

        actual = serializer.serialize(data, StackMeta())
        actual_xml = to_string(ET.tostring(actual))
        assert actual_xml == expected

        deserial_actual = serializer.deserialize(actual)
        assert deserial_actual == [
            "2",
            "1",
            "0"
        ]

    def test_serialize_list(self):
        serializer = Serializer()
        data = []
        data.append("0")
        data.append("1")
        data.append("2")
        expected = \
            '<Obj RefId="0"><TN RefId="0"><T>System.Object[]</T>' \
            '<T>System.Array</T><T>System.Object</T></TN>' \
            '<LST><S>0</S><S>1</S><S>2</S></LST></Obj>'

        actual = serializer.serialize(data)
        actual_xml = to_string(ET.tostring(actual))
        assert actual_xml == expected

        deserial_actual = serializer.deserialize(actual)
        assert deserial_actual == [
            "0",
            "1",
            "2"
        ]

    def test_serialize_list_as_ie(self):
        serializer = Serializer()
        data = []
        data.append("0")
        data.append("1")
        data.append("2")
        expected = \
            '<Obj RefId="0"><TN RefId="0"><T>System.Object[]</T>' \
            '<T>System.Array</T><T>System.Object</T></TN>' \
            '<IE><S>0</S><S>1</S><S>2</S></IE></Obj>'

        actual = serializer.serialize(data, ListMeta("IE"))
        actual_xml = to_string(ET.tostring(actual))
        assert actual_xml == expected

    def test_serialize_secure_string_no_cipher(self):
        serializer = Serializer()
        with pytest.raises(SerializationError) as err:
            serializer._serialize_secure_string("")
        assert str(err.value) == \
            "Cannot generate secure string as cipher is not initialised"

    def test_deserialize_secure_string_no_cipher(self):
        serializer = Serializer()
        # should just return the input var
        actual = serializer._deserialize_secure_string("a")
        assert actual == "a"

    def test_serialize_dynamic_obj(self):
        serializer = Serializer()
        expected = '<Obj RefId="0"><MS><S N="key">value</S></MS></Obj>'
        obj = GenericComplexObject()
        obj.extended_properties['key'] = "value"
        actual = serializer.serialize(obj)
        actual_xml = to_string(ET.tostring(actual))
        assert actual_xml == expected

    def test_serialize_dynamic_complex(self):
        serializer = Serializer()
        expected = \
            '<Obj RefId="0"><TN RefId="0">' \
            '<T>System.Management.Automation.PSCustomObject</T>' \
            '<T>System.Object</T></TN><ToString>to string value</ToString>' \
            '<I32>1</I32><S>2</S><MS><S N="extended_key">extended</S></MS>' \
            '<Props><S N="adapted_key">adapted</S></Props></Obj>'

        obj = GenericComplexObject()
        obj.types = ["System.Management.Automation.PSCustomObject",
                     "System.Object"]
        obj.extended_properties['extended_key'] = 'extended'
        obj.adapted_properties['adapted_key'] = 'adapted'
        obj.property_sets = [1, "2"]
        obj.to_string = "to string value"

        actual = serializer.serialize(obj)
        actual_xml = to_string(ET.tostring(actual))
        assert actual_xml == expected

    def test_deserialize_obj_no_types(self):
        serializer = Serializer()
        xml = '<Obj RefId="0"><MS><S N="key">value</S></MS></Obj>'
        actual = serializer.deserialize(xml)
        assert isinstance(actual, GenericComplexObject)
        assert actual.adapted_properties == {}
        assert actual.extended_properties == {"key": "value"}
        assert actual.property_sets == []
        assert actual.to_string is None
        assert actual.types == []

    def test_deserialize_obj_missing_prop(self):
        class SerialObject(ComplexObject):
            def __init__(self, **kwargs):
                super(SerialObject, self).__init__()
                self._types = [
                    "System.Test",
                    "System.Object"
                ]
                self._extended_properties = (
                    ('man_prop', ObjectMeta("S", optional=False)),
                )
                self.man_prop = kwargs.get('man_prop')

        serializer = Serializer()
        xml = '<Obj RefId="0"><TN RefId="0"><T>System.Test</T>' \
              '<T>System.Object</T></TN><MS /></Obj>'
        with pytest.raises(SerializationError) as err:
            serializer.deserialize(xml, ObjectMeta("Obj", object=SerialObject))
        assert str(err.value) == \
            "Mandatory return value for 'Unknown' was not found on object " \
            "Unknown"

    def test_deserialize_obj_missing_prop_names(self):
        class SerialObject(ComplexObject):
            def __init__(self, **kwargs):
                super(SerialObject, self).__init__()
                self._types = [
                    "System.Test",
                    "System.Object"
                ]
                self._extended_properties = (
                    ('man_prop', ObjectMeta("S", name="key", optional=False)),
                )
                self.man_prop = kwargs.get('man_prop')

        serializer = Serializer()
        xml = '<Obj RefId="0"><TN RefId="0"><T>System.Test</T>' \
              '<T>System.Object</T></TN><ToString>obj</ToString><MS /></Obj>'
        with pytest.raises(SerializationError) as err:
            serializer.deserialize(xml, ObjectMeta("Obj", object=SerialObject))
        assert str(err.value) == \
            "Mandatory return value for 'key' was not found on object obj"

    def test_deserialize_dynamic_obj_type_ref(self):
        serializer = Serializer()
        xml1 = \
            '<Obj RefId="0"><TN RefId="0">' \
            '<T>System.Management.Automation.PSCustomObject</T>' \
            '<T>System.Object</T></TN><ToString>to string value</ToString>' \
            '<I32>1</I32><S>2</S><MS><S N="extended_key">extended</S></MS>' \
            '<Props><S N="adapted_key">adapted</S></Props></Obj>'
        xml2 = \
            '<Obj RefId="2"><TNRef RefId="0" />' \
            '<ToString>to string value 2</ToString>' \
            '<I32>1</I32><S>2</S><MS><S N="extended_key">extended</S></MS>' \
            '<Props><S N="adapted_key">adapted</S></Props></Obj>'
        serializer.deserialize(xml1)
        actual = serializer.deserialize(xml2, clear=False)
        assert str(actual) == "to string value 2"
        assert actual.types == [
            "System.Management.Automation.PSCustomObject",
            "System.Object"
        ]
