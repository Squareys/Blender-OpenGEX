from abc import abstractmethod
import math
from enum import Enum

__author__ = "Jonathan Hale"
__version__ = "0.1.0"


class DdlPrimitiveDataType(Enum):
    """
    Enum for primitive structure data types.

    For convenience use `import DdlPrimitiveDataType from pyddl as DataType`
    for example.
    """
    bool = 0
    int8 = 1
    int16 = 2
    int32 = 3
    int64 = 4
    unsigned_int8 = 5
    unsigned_int16 = 6
    unsigned_int32 = 7
    unsigned_int64 = 8
    half = 9
    float = 10
    double = 11
    string = 12
    ref = 13
    type = 14


class DdlPrimitive:
    """
    An OpenDDL primitive structure.
    """

    def __init__(self, data_type, data, name=None, vector_size=0):
        """
        Constructor
        :param data_type: primitive data type (see pyddl.enum.PrimitiveType)
        :param data: list of values. If vector_size != 0, the list should contain tuples
        :param name: name of the primitive structure
        :param vector_size: size of the contained vectors
        """
        self.data_type = data_type
        self.name = name
        self.vector_size = vector_size
        self.data = data

    def is_simple_primitive(self):
        return len(self.data) == 1 and self.vector_size <= 4


class DdlStructure:
    """
    An OpenDDL structure.
    """

    def __init__(self, identifier, name=None, children=[], props=dict()):
        """
        Constructor
        :param identifier: structure identifier
        :param name: optional name
        :param children: list of substructures
        """
        self.children = children
        self.properties = props
        self.identifier = identifier
        self.name = name if name != "" else None
        self.name_is_global = True

    def is_simple_structure(self):
        """
        A structure is simple if it contains exactly one primitive and has no properties or name.
        :return: true if this structure is simple
        """
        if len(self.children) != 1:
            # a simple structure may contain only one primitive substructure
            return False
        if len(self.properties) > 1:
            # a simple structure does not have more than one property
            return False
        if self.name is not None:
            # simple children don't have a name
            return False
        if not isinstance(self.children[0], DdlPrimitive):
            # the only substructure needs to be a primitive
            return False

        return self.children[0].is_simple_primitive()

    def add_structure(self, identifier, name=None, children=[], props=dict()):
        """
        Add a substructure
        :param identifier: structure identifier
        :param name: optional name
        :param children: list of substructures or primitives
        :param props: dict of properties
        :return: the created structure
        """
        s = DdlStructure(identifier, name, children, props)
        self.children.append(s)
        return s

    def add_primitive(self, data_type, data=[], name=None, vector_size=0):
        """
        Add a primitive substructure
        :param data_type: primitive data type (see pyddl.enum.PrimitiveType)
        :param data: list of values. If vector_size != 0, the list should contain tuples
        :param name: name of the primitive structure
        :param vector_size: size of the contained vectors
        :return: self (for method chaining)
        """
        self.children.append(DdlPrimitive(data_type, data, name, vector_size))
        return self


class DdlDocument:
    """
    An OpenDDL document.
    """

    def __init__(self):
        self.structures = []

    def add_structure(self, identifier, name=None, children=[], props=dict()):
        """
        Add a substructure
        :param identifier: structure identifier
        :param name: optional name
        :param children: list of substructures and primitives
        :param props: dict of properties
        :return: the created structure
        """
        s = DdlStructure(identifier, name, children, props)
        self.structures.append(s)
        return s


class DdlWriter:
    """
    Abstract class for classes responsible for writing OpenDdlDocuments.
    """

    def __init__(self, document):
        """
        Constructor
        :param document: document to write
        """
        self.doc = document

    def get_document(self):
        """
        :return: document to be written by this writer.
        """
        return self.doc

    @abstractmethod
    def write(self, filename):
        """
        Write the writers document to a specified file.
        :param filename: path to a file to write to
        :return: nothing
        """
        pass


class DdlTextWriter(DdlWriter):
    """
    OpenDdlWriter which writes OpenDdlDocuments in human-readable text form.
    """

    def __init__(self, document, rounding=6):
        """
        Constructor
        :param document: document to write
        :param rounding: number of decimal places to keep or None to keep all
        """
        DdlWriter.__init__(self, document)

        self.file = None
        self.indent = B""
        self.rounding = rounding

    def to_float_byte_rounded(self, f):
        if (math.isinf(f)) or (math.isnan(f)):
            return B"0.0"
        else:
            return bytes(str(round(f, self.rounding)), "UTF-8")

    @staticmethod
    def to_float_byte(f):
        if (math.isinf(f)) or (math.isnan(f)):
            return B"0.0"
        else:
            return bytes(str(f), "UTF-8")

    @staticmethod
    def to_int_byte(i):
        return bytes(str(i), "UTF-8")

    @staticmethod
    def to_string_byte(s):
        return B"\"" + bytes(s, "UTF-8") + B"\""

    @staticmethod
    def to_bool_byte(b):
        return B"true" if b else B"false"

    @staticmethod
    def to_ref_byte(structure):
        if structure is None:
            return B"null"
        return (B"$" if structure.name_is_global else B"%") + structure.name

    @staticmethod
    def id(val):
        return val

    def inc_indent(self):
        """
        Increase the current line indent.
        """
        self.indent = self.indent + B"\t"

    def dec_indent(self):
        """
        Decrease the current line indent.
        """
        self.indent = self.indent[:-1]

    def write(self, filename):
        self.file = open(filename, "wb")

        if len(self.get_document().structures) != 0:
            # first element will never prepend a empty line
            structure = self.get_document().structures[0]
            self.file.write(self.structure_as_text(structure))
            previous_was_simple = structure.is_simple_structure()

            for structure in self.get_document().structures[1:]:
                if not (previous_was_simple and structure.is_simple_structure()):
                    self.file.write(B"\n")
                    previous_was_simple = structure.is_simple_structure()

                self.file.write(self.structure_as_text(structure))

        self.file.close()

    def property_as_text(self, prop):
        """
        Create a text representation for a key-value-pair. E.g.: "key = value".
        :param prop: a pair to represent as text
        :return: a byte-string in the form "key = value"
        """
        value = prop[1]
        if isinstance(value, bool):
            value_bytes = self.to_bool_byte(value)
        elif isinstance(value, int):
            value_bytes = self.to_int_byte(value)
        elif isinstance(value, float):
            value_bytes = self.to_float_byte(value)
        elif isinstance(value, str):
            value_bytes = B"\"" + bytes(value, "UTF-8") + B"\""
        elif isinstance(value, bytes):
            value_bytes = B"\"" + value + B"\""
        else:
            raise TypeError("ERROR: Unknown property type for property \"{}\"".format(prop[0]))

        return prop[0] + B" = " + value_bytes

    def primitive_as_text(self, primitive, no_indent=False):
        """
        Get a text representation of the given primitive structure
        :param primitive: primitive structure to get the text representation for
        :param no_indent: if true will skip adding the first indent
        :return: a byte string representing the primitive structure
        """
        lines = [(B"" if no_indent else self.indent) + bytes(primitive.data_type.name, "UTF-8")]

        if primitive.vector_size > 0:
            lines.append(B"[" + self.to_int_byte(primitive.vector_size) + B"]")

        if primitive.name is not None:
            lines.append(B" $" + primitive.name + B" ")

        has_comment = hasattr(primitive, 'comment')
        if has_comment:
            lines.append(B"\t\t// " + primitive.comment)

        # find appropriate conversion function
        if primitive.data_type in [DdlPrimitiveDataType.bool]:
            # bool
            to_bytes = self.to_bool_byte
        elif primitive.data_type in [DdlPrimitiveDataType.double, DdlPrimitiveDataType.float]:
            # float/double
            to_bytes = self.to_float_byte if self.rounding is None else self.to_float_byte_rounded
        elif primitive.data_type in [DdlPrimitiveDataType.int8, DdlPrimitiveDataType.int16, DdlPrimitiveDataType.int32,
                                     DdlPrimitiveDataType.int64, DdlPrimitiveDataType.unsigned_int8,
                                     DdlPrimitiveDataType.unsigned_int16, DdlPrimitiveDataType.unsigned_int32,
                                     DdlPrimitiveDataType.unsigned_int64, DdlPrimitiveDataType.half]:
            # integer types
            to_bytes = self.to_int_byte
        elif primitive.data_type in [DdlPrimitiveDataType.string]:
            # string
            if primitive.vector_size == 0 and len(primitive.data) > 0:
                to_bytes = self.id if isinstance(primitive.data[0], bytes) else self.to_string_byte
            else:
                if len(primitive.data) > 0:
                    to_bytes = self.id if isinstance(primitive.data[0][0], bytes) else self.to_string_byte
        elif primitive.data_type in [DdlPrimitiveDataType.ref]:
            to_bytes = self.to_ref_byte
        else:
            raise TypeError("Encountered unknown primitive type.")

        if len(primitive.data) == 0:
            lines.append(B"\n" if has_comment else B" ")
            lines.append(B"{ }")
        elif primitive.is_simple_primitive():
            lines.append(B"\n" if has_comment else B" ")
            if primitive.vector_size == 0:
                lines.append(B"{" + to_bytes(primitive.data[0]) + B"}")
            else:
                lines.append(B"{{" + (B", ".join(map(to_bytes, primitive.data[0]))) + B"}}")
        else:
            lines.append(B"\n" + self.indent + B"{\n")
            self.inc_indent()

            if primitive.vector_size == 0:
                if hasattr(primitive, 'max_elements_per_line'):
                    n = primitive.max_elements_per_line
                    data = primitive.data
                    lines.append(self.indent + ((B",\n" + self.indent).join(
                        [B", ".join(group) for group in
                         [map(to_bytes, data[i:i + n]) for i in range(0, len(data), n)]])) + B"\n")
                else:
                    lines.append(self.indent + (B", ".join(map(to_bytes, primitive.data))) + B"\n")
            else:
                if hasattr(primitive, 'max_elements_per_line'):
                    n = primitive.max_elements_per_line
                    data = primitive.data

                    if len(data) == 1:
                        data = data[0]
                        # there is exactly one vector, we will handle its components for formatting with
                        # max_elements_per_line.
                        lines.append(self.indent + B"{" + ((B",\n" + self.indent + B" ").join(
                            [(B", ".join(map(to_bytes, line))) for line in
                             [data[i:i + n] for i in range(0, len(data), n)]  # group generator
                             ]) + B"}\n"))
                    else:
                        lines.append(self.indent + B"{" + ((B"},\n" + self.indent + B"{").join(
                            [(B"}, {".join(B", ".join(map(to_bytes, vec)) for vec in group)) for group in
                             [data[i:i + n] for i in range(0, len(data), n)]])) + B"}\n")
                else:
                    lines.append(self.indent + B"{" + (B"}, {".join(
                        B", ".join(map(to_bytes, vec)) for vec in primitive.data)) + B"}\n")

            self.dec_indent()
            lines.append(self.indent + B"}")

        return lines

    def structure_as_text(self, structure):
        """
        Get a text representation of the given structure
        :param structure: structure to get the text representation for
        :return: a byte string representing the structure
        """
        lines = [self.indent + structure.identifier]

        if structure.name:
            lines.append(B" $" if structure.name_is_global else B" %")
            lines.append(structure.name)

        if len(structure.properties) != 0:
            lines.append(B" (" + B", ".join(self.property_as_text(prop) for prop in structure.properties.items()) + B")")

        has_comment = hasattr(structure, 'comment')
        if has_comment:
            lines.append(B"\t\t// " + structure.comment)

        if structure.is_simple_structure() and not has_comment:
            lines.append(B" {")
            lines.extend(self.primitive_as_text(structure.children[0], True))
            lines.append(B"}\n")
        else:
            lines.append(B"\n" + self.indent + B"{\n")

            previous_was_simple = False
            first = structure.children[0]

            self.inc_indent()
            for sub in structure.children:
                if isinstance(sub, DdlPrimitive):
                    lines.extend(self.primitive_as_text(sub))
                    lines.append(B"\n")
                    previous_was_simple = False
                else:
                    if not (previous_was_simple and sub.is_simple_structure()) and not sub == first:
                        lines.append(B"\n")

                    lines.append(self.structure_as_text(sub))
                    previous_was_simple = sub.is_simple_structure()

            self.dec_indent()

            lines.append(self.indent + B"}\n")

        return B''.join(lines)

    @staticmethod
    def set_max_elements_per_line(primitive, elements):
        """
        Set how many elements should be displayed per line for a primitive structure.
        When there is more than one element, every vector is handled as one element.
        If there is merely one element in the primitive data and this element is a vector,
        the components of the vector are treated as the elements.
        :param primitive: the primitive
        :param elements: max amount of elements per line
        :return: the provided primitive with an added `max_elements_per_line` attribute
        """
        if isinstance(primitive, DdlPrimitive):
            primitive.max_elements_per_line = elements
            return primitive
        else:
            raise TypeError("max_elements_per_line can only be set for DdlPrimitive")

    @staticmethod
    def set_comment(structure, comment):
        """
        Set a one-line comment to a structure or primitive structure
        :param structure: the structure to add the one-line comment to
        :param comment: the comment to add
        :return: the provided structure with an added `comment` attribute
        """
        if isinstance(structure, DdlStructure) or isinstance(structure, DdlPrimitive):

            if isinstance(comment, bytes):
                structure.comment = comment
            else:
                structure.comment = bytes(str(comment), "UTF-8")
            return structure
        else:
            raise TypeError("set_comment can only be set for DdlPrimitive or DdlStructure")


class DdlCompressedTextWriter(DdlTextWriter):
    """
    OpenDdlWriter which writes OpenDdlDocuments in compressed (probably not human-readable) text form.

    Making use of "Whitespace never has any meaning, so OpenDDL files can be formatted in any manner preferred.", see
    OpenDDL specification.

    Faster than DdlTextWriter and produces smaller files.
    """

    def __init__(self, document, rounding=6):
        """
        Constructor
        :param document: document to write
        :param rounding: number of decimal places to keep or None to keep all
        """
        super().__init__(document, rounding)

    def write(self, filename):
        self.file = open(filename, "wb")

        if len(self.get_document().structures) != 0:
            for structure in self.get_document().structures:
                self.file.write(self.structure_as_text(structure))

        self.file.close()

    def property_as_text(self, prop):
        """
        Create a text representation for a key-value-pair. E.g.: "key=value".
        :param prop: a pair to represent as text
        :return: a byte-string in the form "key=value"
        """
        value = prop[1]
        if isinstance(value, bool):
            value_bytes = self.to_bool_byte(value)
        elif isinstance(value, int):
            value_bytes = self.to_int_byte(value)
        elif isinstance(value, float):
            value_bytes = self.to_float_byte(value)
        elif isinstance(value, str):
            value_bytes = B"\"" + bytes(value, "UTF-8") + B"\""
        elif isinstance(value, bytes):
            value_bytes = B"\"" + value + B"\""
        else:
            raise TypeError("ERROR: Unknown property type for property \"{}\"".format(prop[0]))

        return prop[0] + B"=" + value_bytes

    def primitive_as_text(self, primitive):
        """
        Get a text representation of the given primitive structure
        :param primitive: primitive structure to get the text representation for
        :return: a byte string representing the primitive structure
        """
        lines = [bytes(primitive.data_type.name, "UTF-8")]

        if primitive.vector_size > 0:
            lines.append(B"[" + self.to_int_byte(primitive.vector_size) + B"]")

        if primitive.name is not None:
            lines.append(B"$"+ primitive.name)

        # find appropriate conversion function
        if primitive.data_type in [DdlPrimitiveDataType.bool]:
            # bool
            to_bytes = self.to_bool_byte
        elif primitive.data_type in [DdlPrimitiveDataType.double, DdlPrimitiveDataType.float]:
            # float/double
            to_bytes = self.to_float_byte if self.rounding is None else self.to_float_byte_rounded
        elif primitive.data_type in [DdlPrimitiveDataType.int8, DdlPrimitiveDataType.int16, DdlPrimitiveDataType.int32,
                                     DdlPrimitiveDataType.int64, DdlPrimitiveDataType.unsigned_int8,
                                     DdlPrimitiveDataType.unsigned_int16, DdlPrimitiveDataType.unsigned_int32,
                                     DdlPrimitiveDataType.unsigned_int64, DdlPrimitiveDataType.half]:
            # integer types
            to_bytes = self.to_int_byte
        elif primitive.data_type in [DdlPrimitiveDataType.string]:
            # string
            if primitive.vector_size == 0 and len(primitive.data) > 0:
                to_bytes = self.id if isinstance(primitive.data[0], bytes) else self.to_string_byte
            else:
                if len(primitive.data) > 0:
                    to_bytes = self.id if isinstance(primitive.data[0][0], bytes) else self.to_string_byte
        elif primitive.data_type in [DdlPrimitiveDataType.ref]:
            to_bytes = self.to_ref_byte
        else:
            raise TypeError("Encountered unknown primitive type.")

        if len(primitive.data) == 0:
            lines.append(B"{}")
        elif primitive.is_simple_primitive():
            if primitive.vector_size == 0:
                lines.append(B"{" + to_bytes(primitive.data[0]) + B"}")
            else:
                lines.append(B"{{" + (B",".join(map(to_bytes, primitive.data[0]))) + B"}}")
        else:
            if primitive.vector_size == 0:
                lines.append(B"{" + B",".join(map(to_bytes, primitive.data)) + B"}")
            else:
                lines.append(B"{{" + (B"},{".join(B",".join(map(to_bytes, vec)) for vec in primitive.data)) + B"}}")

        return lines

    def structure_as_text(self, structure):
        """
        Get a text representation of the given structure
        :param structure: structure to get the text representation for
        :return: a byte string representing the structure
        """
        lines = [structure.identifier]

        if structure.name:
            lines.append(B"$" if structure.name_is_global else B"%")
            lines.append(structure.name)

        if len(structure.properties) != 0:
            lines.append(B"(" + B",".join(self.property_as_text(prop) for prop in structure.properties.items()) + B")")

        lines.append(B"{")

        for sub in structure.children:
            if isinstance(sub, DdlPrimitive):
                lines.extend(self.primitive_as_text(sub))
            else:
                lines.append(self.structure_as_text(sub))

        lines.append(B"}")

        return B''.join(lines)


# Space reserved for a specification based OpenDdlBinaryWriter ;)
# Hope there will be some specification for it some day.
