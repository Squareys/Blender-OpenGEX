import math
from itertools import zip_longest

__author__ = 'Eric Lengyel, Jonathan Hale, Nicolas Wehrle'


class Writer:
    """Class to help with writing certain structures like matrices, vectors etc"""

    def __init__(self):
        self.file = None
        self.indent = B""
        pass

    def open(self, filename):
        self.file = open(filename, "wb")

    def close(self):
        self.file.close()

    def set_file(self, file):
        self.file = file

    def write(self, data):
        self.file.write(data)  # TODO inline later!

    def inc_indent(self):
        self.indent = self.indent + B"\t"

    def dec_indent(self):
        self.indent = self.indent[:-1]

    def indent_write(self, text, extra=0, newline=False) -> None:
        """
        Write text indented with the current indentation amount
        :rtype: None
        :param text text to write
        :param extra Additional indent
        :param newline (default `False`) Whether to add a newline at the beginning.
        """
        if newline:
            self.file.write(B"\n")
        self.file.write(self.indent + B"\t" * extra + text)

    def get_indent(self, extra=0):
        """
        Get bytestring containing the current amount of indent tabs
        :param extra Additional indent
        :return: bytestring for the indentation
        """
        return self.indent + B"\t" * extra

    def write_int(self, i):
        self.file.write(bytes(str(i), "UTF-8"))

    @staticmethod
    def to_float_byte(f):
        if (math.isinf(f)) or (math.isnan(f)):
            return B"0.0"
        else:
            # TODO make float rounding optional
            return bytes(str(round(f, 6)), "UTF-8")

    @staticmethod
    def to_int_byte(i):
        return bytes(str(i), "UTF-8")

    def write_float(self, f):
        self.file.write(self.to_float_byte(f))

    @staticmethod
    def to_matrix_row_byte(matrix, i):
        to_f = Writer.to_float_byte
        return (
            to_f(matrix[0][i]) + B", " +
            to_f(matrix[1][i]) + B", " +
            to_f(matrix[2][i]) + B", " +
            to_f(matrix[3][i]))

    def write_matrix(self, matrix):
        indent = B",\n" + self.get_indent(1) + B" "
        self.indent_write(B"{" + self.to_matrix_row_byte(matrix, 0) +
                          indent + self.to_matrix_row_byte(matrix, 1) +
                          indent + self.to_matrix_row_byte(matrix, 2) +
                          indent + self.to_matrix_row_byte(matrix, 3) + B"}\n",
                          extra=1)

    def write_matrix_flat(self, matrix):
        self.indent_write(B"{" + self.to_matrix_row_byte(matrix, 0) + B", " +
                          self.to_matrix_row_byte(matrix, 1) + B", " +
                          self.to_matrix_row_byte(matrix, 2) + B", " +
                          self.to_matrix_row_byte(matrix, 3) + B"}", 1)

    def write_color(self, color):
        self.write_vector3d(color)

    def write_filename(self, filename):
        length = len(filename)
        if (length > 2) and (filename[1] == ":"):
            self.file.write(B"//")
            self.file.write(bytes(filename[0], "UTF-8"))
            self.file.write(bytes(filename[2:length].replace("\\", "/"), "UTF-8"))
        elif length != 0:
            self.file.write(bytes(filename.replace("\\", "/"), "UTF-8"))

    def write_int_array(self, value_array):
        to_i = self.to_int_byte
        count = len(value_array)
        k = 0

        line_count = count >> 6
        for i in range(line_count):
            self.indent_write(B"" + (B", ".join(map(to_i, value_array[k:k+64]))), 1)
            k += 64

            if i * 64 < count - 64:
                self.file.write(B",\n")
            else:
                self.file.write(B"\n")

        count &= 63
        if count != 0:
            self.indent_write(B"", 1)
            for j in range(count - 1):
                self.write_int(value_array[k])
                self.file.write(B", ")
                k += 1

            self.write_int(value_array[k])
            self.file.write(B"\n")

    def write_float_array(self, value_array):
        to_f = Writer.to_float_byte
        count = len(value_array)
        k = 0

        line_count = count >> 4
        for i in range(line_count):
            self.indent_write(B"", 1)
            for j in range(15):
                self.file.write(to_f(value_array[k]) + B", ")
                k += 1

            self.write_float(value_array[k])
            k += 1

            if i * 16 < count - 16:
                self.file.write(B",\n")
            else:
                self.file.write(B"\n")

        count &= 15
        if count != 0:
            self.indent_write(B"", 1)
            for j in range(count - 1):
                self.file.write(to_f(value_array[k]) + B", ")
                k += 1

            self.write_float(value_array[k])
            self.file.write(B"\n")

    def write_vector2d(self, vector):
        to_f = Writer.to_float_byte
        self.file.write(B"{" + to_f(vector[0]) + B", " +
                        to_f(vector[1]) + B"}")

    def write_vector3d(self, vector):
        to_f = Writer.to_float_byte
        self.file.write(B"{" +
                        to_f(vector[0]) + B", " +
                        to_f(vector[1]) + B", " +
                        to_f(vector[2]) + B"}")

    def write_vector4d(self, vector):
        to_f = Writer.to_float_byte
        self.file.write(B"{" +
                        to_f(vector[0]) + B", " +
                        to_f(vector[1]) + B", " +
                        to_f(vector[2]) + B", " +
                        to_f(vector[3]) + B"}")

    def write_quaternion(self, quaternion):
        self.write_vector4d(quaternion)

    def write_vertex_array2d(self, vertex_array):
        count = len(vertex_array)
        k = 0

        line_count = count >> 3
        for i in range(line_count):
            self.indent_write(B"", 1)
            for j in range(7):
                self.write_vector2d(vertex_array[k])
                self.file.write(B", ")
                k += 1

            self.write_vector2d(vertex_array[k])
            k += 1

            if i * 8 < count - 8:
                self.file.write(B",\n")
            else:
                self.file.write(B"\n")

        count &= 7
        if count != 0:
            self.indent_write(B"", 1)
            for j in range(count - 1):
                self.write_vector2d(vertex_array[k])
                self.file.write(B", ")
                k += 1

            self.write_vector2d(vertex_array[k])
            self.file.write(B"\n")

    def write_vertex_array3d(self, vertex_array):
        count = len(vertex_array)
        k = 0

        line_count = count >> 3
        for i in range(line_count):
            self.indent_write(B"", 1)
            for j in range(7):
                self.write_vector3d(vertex_array[k])
                self.file.write(B", ")
                k += 1

            self.write_vector3d(vertex_array[k])
            k += 1

            if i * 8 < count - 8:
                self.file.write(B",\n")
            else:
                self.file.write(B"\n")

        count &= 7
        if count != 0:
            self.indent_write(B"", 1)
            for j in range(count - 1):
                self.write_vector3d(vertex_array[k])
                self.file.write(B", ")
                k += 1

            self.write_vector3d(vertex_array[k])
            self.file.write(B"\n")

    def write_morph_position_array3d(self, vertex_array, mesh_vertex_array):
        count = len(vertex_array)
        k = 0

        line_count = count >> 3
        for i in range(line_count):
            self.indent_write(B"", 1)
            for j in range(7):
                self.write_vector3d(mesh_vertex_array[vertex_array[k].vertexIndex].co)
                self.file.write(B", ")
                k += 1

            self.write_vector3d(mesh_vertex_array[vertex_array[k].vertexIndex].co)
            k += 1

            if i * 8 < count - 8:
                self.file.write(B",\n")
            else:
                self.file.write(B"\n")

        count &= 7
        if count != 0:
            self.indent_write(B"", 1)
            for j in range(count - 1):
                self.write_vector3d(mesh_vertex_array[vertex_array[k].vertexIndex].co)
                self.file.write(B", ")
                k += 1

            self.write_vector3d(mesh_vertex_array[vertex_array[k].vertexIndex].co)
            self.file.write(B"\n")

    def write_morph_normal_array3d(self, vertex_array, mesh_vertex_array, tessface_array):
        count = len(vertex_array)
        k = 0

        line_count = count >> 3
        for i in range(line_count):
            self.indent_write(B"", 1)
            for j in range(7):
                face = tessface_array[vertex_array[k].faceIndex]
                self.write_vector3d(
                    mesh_vertex_array[vertex_array[k].vertexIndex].normal if face.use_smooth else face.normal)
                self.file.write(B", ")
                k += 1

            face = tessface_array[vertex_array[k].faceIndex]
            self.write_vector3d(mesh_vertex_array[vertex_array[k].vertexIndex].normal if face.use_smooth else face.normal)
            k += 1

            if i * 8 < count - 8:
                self.file.write(B",\n")
            else:
                self.file.write(B"\n")

        count &= 7
        if count != 0:
            self.indent_write(B"", 1)
            for j in range(count - 1):
                face = tessface_array[vertex_array[k].faceIndex]
                self.write_vector3d(
                    mesh_vertex_array[vertex_array[k].vertexIndex].normal if face.use_smooth else face.normal)
                self.file.write(B", ")
                k += 1

            face = tessface_array[vertex_array[k].faceIndex]
            self.write_vector3d(mesh_vertex_array[vertex_array[k].vertexIndex].normal if face.use_smooth else face.normal)
            self.file.write(B"\n")

    # Write a triangle array
    # @param indices list of triple of int
    def write_triangle_array(self, triangles):
        to_i = self.to_int_byte
        i = 0  # index of fist index of current triangle

        count = len(triangles)
        line_count = count >> 4
        for x in range(line_count):
            self.indent_write(B"", 1)

            self.write(B", ".join([(B"{" + (B", ".join(map(to_i, tri))) + B"}")
                                   for tri in triangles[i:i + 16]]))
            i += 16

            if x * 16 < count - 16:
                self.file.write(B",\n")
            else:
                self.file.write(B"\n")

        count &= 15
        if count != 0:
            self.indent_write(B"", 1)
            self.write(B", ".join([(B"{" + (B", ".join(map(to_i, tri))) + B"}")
                                   for tri in triangles[i:i + count]]))

    def write_node_table(self, object_ref):
        first = True
        for node in object_ref[1]["nodeTable"]:
            if first:
                self.file.write(B"\t\t// ")
            else:
                self.file.write(B", ")
            self.file.write(bytes(node.name, "UTF-8"))
            first = False