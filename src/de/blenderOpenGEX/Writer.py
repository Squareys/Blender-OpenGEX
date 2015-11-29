
import math

__author__ = 'Jonathan Hale, Eric Lengyel'


class Writer:
    """Class to help with writing certain structures like matrices, vectors etc"""

    def __init__(self):
        self.file = None
        self.indentLevel = 0
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
        self.indentLevel += 1
     
    def dec_indent(self):
        self.indentLevel -= 1
        
    def indent_write(self, text, extra=0, newline=False):
        if newline:
            self.file.write(B"\n")
        for i in range(self.indentLevel + extra):
            self.file.write(B"\t")
        self.file.write(text)
        
    def write_int(self, i):
        self.file.write(bytes(str(i), "UTF-8"))

    @staticmethod
    def to_float_byte(f):
        if (math.isinf(f)) or (math.isnan(f)):
            return B"0.0"
        else:
            # TODO make float rounding optional
            return bytes(str(round(f, 6)), "UTF-8")
            
    def write_float(self, f):
        self.file.write(self.to_float_byte(f))
     
    def write_matrix_row(self, matrix, i):
        self.write_float(matrix[0][i])
        self.file.write(B", ")
        self.write_float(matrix[1][i])
        self.file.write(B", ")
        self.write_float(matrix[2][i])
        self.file.write(B", ")
        self.write_float(matrix[3][i])
        
    def write_matrix(self, matrix):
        self.indent_write(B"{", 1)
        self.write_matrix_row(matrix, 0)
        self.file.write(B",\n")
        self.write_matrix_row(matrix, 1)
        self.file.write(B",\n")
        self.write_matrix_row(matrix, 2)
        self.file.write(B",\n")
        self.write_matrix_row(matrix, 3)
        self.file.write(B"}\n")
        
    def write_matrix_flat(self, matrix):
        self.indent_write(B"{", 1)
        self.write_matrix_row(matrix, 0)
        self.file.write(B", ")
        self.write_matrix_row(matrix, 1)
        self.file.write(B", ")
        self.write_matrix_row(matrix, 2)
        self.file.write(B", ")
        self.write_matrix_row(matrix, 3)
        self.file.write(B"}")
        
    def write_color(self, color):
        self.file.write(B"{")
        self.write_float(color[0])
        self.file.write(B", ")
        self.write_float(color[1])
        self.file.write(B", ")
        self.write_float(color[2])
        self.file.write(B"}")
        
    def write_file_name(self, filename):
        length = len(filename)
        if (length > 2) and (filename[1] == ":"):
            self.file.write(B"//")
            self.file.write(bytes(filename[0], "UTF-8"))
            self.file.write(bytes(filename[2:length].replace("\\", "/"), "UTF-8"))
        elif length != 0:
            self.file.write(bytes(filename.replace("\\", "/"), "UTF-8"))
                
    def write_int_array(self, value_array):
        count = len(value_array)
        k = 0

        line_count = count >> 6
        for i in range(line_count):
            self.indent_write(B"", 1)
            for j in range(63):
                self.write_int(value_array[k])
                self.file.write(B", ")
                k += 1

            self.write_int(value_array[k])
            k += 1

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
        count = len(value_array)
        k = 0

        line_count = count >> 4
        for i in range(line_count):
            self.indent_write(B"", 1)
            for j in range(15):
                self.write_float(value_array[k])
                self.file.write(B", ")
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
                self.write_float(value_array[k])
                self.file.write(B", ")
                k += 1

            self.write_float(value_array[k])
            self.file.write(B"\n")

    def write_vector2d(self, vector):
        self.file.write(B"{")
        self.write_float(vector[0])
        self.file.write(B", ")
        self.write_float(vector[1])
        self.file.write(B"}")

    def write_vector3d(self, vector):
        self.file.write(B"{")
        self.write_float(vector[0])
        self.file.write(B", ")
        self.write_float(vector[1])
        self.file.write(B", ")
        self.write_float(vector[2])
        self.file.write(B"}")

    def write_vector4d(self, vector):
        self.file.write(B"{")
        self.write_float(vector[0])
        self.file.write(B", ")
        self.write_float(vector[1])
        self.file.write(B", ")
        self.write_float(vector[2])
        self.file.write(B", ")
        self.write_float(vector[3])
        self.file.write(B"}")

    def write_quaternion(self, quaternion):
        self.file.write(B"{")
        self.write_float(quaternion[1])
        self.file.write(B", ")
        self.write_float(quaternion[2])
        self.file.write(B", ")
        self.write_float(quaternion[3])
        self.file.write(B", ")
        self.write_float(quaternion[0])
        self.file.write(B"}")

    def write_vertex_array2d(self, vertex_array, attrib):
        count = len(vertex_array)
        k = 0

        line_count = count >> 3
        for i in range(line_count):
            self.indent_write(B"", 1)
            for j in range(7):
                self.write_vector2d(getattr(vertex_array[k], attrib))
                self.file.write(B", ")
                k += 1

            self.write_vector2d(getattr(vertex_array[k], attrib))
            k += 1

            if i * 8 < count - 8:
                self.file.write(B",\n")
            else:
                self.file.write(B"\n")

        count &= 7
        if count != 0:
            self.indent_write(B"", 1)
            for j in range(count - 1):
                self.write_vector2d(getattr(vertex_array[k], attrib))
                self.file.write(B", ")
                k += 1

            self.write_vector2d(getattr(vertex_array[k], attrib))
            self.file.write(B"\n")

    def write_vertex_array3d(self, vertex_array, attrib):
        count = len(vertex_array)
        k = 0

        line_count = count >> 3
        for i in range(line_count):
            self.indent_write(B"", 1)
            for j in range(7):
                self.write_vector3d(getattr(vertex_array[k], attrib))
                self.file.write(B", ")
                k += 1

            self.write_vector3d(getattr(vertex_array[k], attrib))
            k += 1

            if i * 8 < count - 8:
                self.file.write(B",\n")
            else:
                self.file.write(B"\n")

        count &= 7
        if count != 0:
            self.indent_write(B"", 1)
            for j in range(count - 1):
                self.write_vector3d(getattr(vertex_array[k], attrib))
                self.file.write(B", ")
                k += 1

            self.write_vector3d(getattr(vertex_array[k], attrib))
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

    def write_triangle(self, triangleIndex, indexTable):
        i = triangleIndex * 3
        self.file.write(B"{")
        self.write_int(indexTable[i])
        self.file.write(B", ")
        self.write_int(indexTable[i + 1])
        self.file.write(B", ")
        self.write_int(indexTable[i + 2])
        self.file.write(B"}")

    def write_triangle_array(self, count, indexTable):
        triangle_index = 0

        line_count = count >> 4
        for i in range(line_count):
            self.indent_write(B"", 1)
            for j in range(15):
                self.write_triangle(triangle_index, indexTable)
                self.file.write(B", ")
                triangle_index += 1

            self.write_triangle(triangle_index, indexTable)
            triangle_index += 1

            if i * 16 < count - 16:
                self.file.write(B",\n")
            else:
                self.file.write(B"\n")

        count &= 15
        if count != 0:
            self.indent_write(B"", 1)
            for j in range(count - 1):
                self.write_triangle(triangle_index, indexTable)
                self.file.write(B", ")
                triangle_index += 1

            self.write_triangle(triangle_index, indexTable)
            self.file.write(B"\n")

    def write_node_table(self, objectRef):
        first = True
        for node in objectRef[1]["nodeTable"]:
            if first:
                self.file.write(B"\t\t// ")
            else:
                self.file.write(B", ")
            self.file.write(bytes(node.name, "UTF-8"))
            first = False