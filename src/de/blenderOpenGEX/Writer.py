
__author__ = 'Jonathan Hale, Eric Lengyel'


class Writer():
    """Class to help with writing certain structures like matrices, vectors etc"""

    def __init__(self):
        self.file = None
        self.indentLevel = 0
        pass
     
    def open(self, filename):
        self.file = open(filename, "wb")
        
    def close(self):
        self.file.close()
     
    def setFile(self, file):
        self.file = file
        
    def Write(self, data):
        self.file.write(data) # TODO inline later!
        
    def IncIndent(self):
        self.indentLevel += 1
     
    def DecIndent(self):
        self.indentLevel -= 1
        
    def IndentWrite(self, text, extra=0, newline=False):
        if newline:
            self.file.write(B"\n")
        for i in range(self.indentLevel + extra):
            self.file.write(B"\t")
        self.file.write(text)
        
    def WriteInt(self, i):
        self.file.write(bytes(str(i), "UTF-8"))

    def ToFloatByte(self, f):
        if (math.isinf(f)) or (math.isnan(f)):
            return B"0.0"
        else:
            # TODO make float rounding optional
            return bytes(str(round(f, 6)), "UTF-8")
            
    def WriteFloat(self, f):
        self.file.write(self.ToFloatByte(f))
     
    def WriteMatrixRow(self, matrix, i):
        self.WriteFloat(matrix[0][i])
        self.file.write(B", ")
        self.WriteFloat(matrix[1][i])
        self.file.write(B", ")
        self.WriteFloat(matrix[2][i])
        self.file.write(B", ")
        self.WriteFloat(matrix[3][i])
        
    def WriteMatrix(self, matrix):
        self.IndentWrite(B"{", 1)
        self.WriteMatrixRow(matrix, 0)
        self.file.write(B",\n")
        self.WriteMatrixRow(matrix, 1)
        self.file.write(B",\n")
        self.WriteMatrixRow(matrix, 2)
        self.file.write(B",\n")
        self.WriteMatrixRow(matrix, 3)
        self.file.write(B"}\n")
        
    def WriteMatrixFlat(self, matrix):
        self.IndentWrite(B"{", 1)
        self.WriteMatrixRow(matrix, 0)
        self.file.write(B", ")
        self.WriteMatrixRow(matrix, 1)
        self.file.write(B", ")
        self.WriteMatrixRow(matrix, 2)
        self.file.write(B", ")
        self.WriteMatrixRow(matrix, 3)
        self.file.write(B"}")
        
    def WriteColor(self, color):
        self.file.write(B"{")
        self.WriteFloat(color[0])
        self.file.write(B", ")
        self.WriteFloat(color[1])
        self.file.write(B", ")
        self.WriteFloat(color[2])
        self.file.write(B"}")
        
    def WriteFileName(self, filename):
        length = len(filename)
        if (length > 2) and (filename[1] == ":"):
            self.file.write(B"//")
            self.file.write(bytes(filename[0], "UTF-8"))
            self.file.write(bytes(filename[2:length].replace("\\", "/"), "UTF-8"))
        elif length != 0:
            self.file.write(bytes(filename.replace("\\", "/"), "UTF-8"))
                
    def WriteIntArray(self, valueArray):
        count = len(valueArray)
        k = 0

        lineCount = count >> 6
        for i in range(lineCount):
            self.IndentWrite(B"", 1)
            for j in range(63):
                self.WriteInt(valueArray[k])
                self.file.write(B", ")
                k += 1

            self.WriteInt(valueArray[k])
            k += 1

            if i * 64 < count - 64:
                self.file.write(B",\n")
            else:
                self.file.write(B"\n")

        count &= 63
        if count != 0:
            self.IndentWrite(B"", 1)
            for j in range(count - 1):
                self.WriteInt(valueArray[k])
                self.file.write(B", ")
                k += 1

            self.WriteInt(valueArray[k])
            self.file.write(B"\n")
            
    def WriteFloatArray(self, valueArray):
        count = len(valueArray)
        k = 0

        lineCount = count >> 4
        for i in range(lineCount):
            self.IndentWrite(B"", 1)
            for j in range(15):
                self.WriteFloat(valueArray[k])
                self.file.write(B", ")
                k += 1

            self.WriteFloat(valueArray[k])
            k += 1

            if i * 16 < count - 16:
                self.file.write(B",\n")
            else:
                self.file.write(B"\n")

        count &= 15
        if count != 0:
            self.IndentWrite(B"", 1)
            for j in range(count - 1):
                self.WriteFloat(valueArray[k])
                self.file.write(B", ")
                k += 1

            self.WriteFloat(valueArray[k])
            self.file.write(B"\n")

    def WriteVector2D(self, vector):
        self.file.write(B"{")
        self.WriteFloat(vector[0])
        self.file.write(B", ")
        self.WriteFloat(vector[1])
        self.file.write(B"}")

    def WriteVector3D(self, vector):
        self.file.write(B"{")
        self.WriteFloat(vector[0])
        self.file.write(B", ")
        self.WriteFloat(vector[1])
        self.file.write(B", ")
        self.WriteFloat(vector[2])
        self.file.write(B"}")

    def WriteVector4D(self, vector):
        self.file.write(B"{")
        self.WriteFloat(vector[0])
        self.file.write(B", ")
        self.WriteFloat(vector[1])
        self.file.write(B", ")
        self.WriteFloat(vector[2])
        self.file.write(B", ")
        self.WriteFloat(vector[3])
        self.file.write(B"}")

    def WriteQuaternion(self, quaternion):
        self.file.write(B"{")
        self.WriteFloat(quaternion[1])
        self.file.write(B", ")
        self.WriteFloat(quaternion[2])
        self.file.write(B", ")
        self.WriteFloat(quaternion[3])
        self.file.write(B", ")
        self.WriteFloat(quaternion[0])
        self.file.write(B"}")

    def WriteVertexArray2D(self, vertexArray, attrib):
        count = len(vertexArray)
        k = 0

        lineCount = count >> 3
        for i in range(lineCount):
            self.IndentWrite(B"", 1)
            for j in range(7):
                self.WriteVector2D(getattr(vertexArray[k], attrib))
                self.file.write(B", ")
                k += 1

            self.WriteVector2D(getattr(vertexArray[k], attrib))
            k += 1

            if i * 8 < count - 8:
                self.file.write(B",\n")
            else:
                self.file.write(B"\n")

        count &= 7
        if count != 0:
            self.IndentWrite(B"", 1)
            for j in range(count - 1):
                self.WriteVector2D(getattr(vertexArray[k], attrib))
                self.file.write(B", ")
                k += 1

            self.WriteVector2D(getattr(vertexArray[k], attrib))
            self.file.write(B"\n")

    def WriteVertexArray3D(self, vertexArray, attrib):
        count = len(vertexArray)
        k = 0

        lineCount = count >> 3
        for i in range(lineCount):
            self.IndentWrite(B"", 1)
            for j in range(7):
                self.WriteVector3D(getattr(vertexArray[k], attrib))
                self.file.write(B", ")
                k += 1

            self.WriteVector3D(getattr(vertexArray[k], attrib))
            k += 1

            if i * 8 < count - 8:
                self.file.write(B",\n")
            else:
                self.file.write(B"\n")

        count &= 7
        if count != 0:
            self.IndentWrite(B"", 1)
            for j in range(count - 1):
                self.WriteVector3D(getattr(vertexArray[k], attrib))
                self.file.write(B", ")
                k += 1

            self.WriteVector3D(getattr(vertexArray[k], attrib))
            self.file.write(B"\n")

    def WriteMorphPositionArray3D(self, vertexArray, meshVertexArray):
        count = len(vertexArray)
        k = 0

        lineCount = count >> 3
        for i in range(lineCount):
            self.IndentWrite(B"", 1)
            for j in range(7):
                self.WriteVector3D(meshVertexArray[vertexArray[k].vertexIndex].co)
                self.file.write(B", ")
                k += 1

            self.WriteVector3D(meshVertexArray[vertexArray[k].vertexIndex].co)
            k += 1

            if i * 8 < count - 8:
                self.file.write(B",\n")
            else:
                self.file.write(B"\n")

        count &= 7
        if count != 0:
            self.IndentWrite(B"", 1)
            for j in range(count - 1):
                self.WriteVector3D(meshVertexArray[vertexArray[k].vertexIndex].co)
                self.file.write(B", ")
                k += 1

            self.WriteVector3D(meshVertexArray[vertexArray[k].vertexIndex].co)
            self.file.write(B"\n")

    def WriteMorphNormalArray3D(self, vertexArray, meshVertexArray, tessFaceArray):
        count = len(vertexArray)
        k = 0

        lineCount = count >> 3
        for i in range(lineCount):
            self.IndentWrite(B"", 1)
            for j in range(7):
                face = tessFaceArray[vertexArray[k].faceIndex]
                self.WriteVector3D(
                    meshVertexArray[vertexArray[k].vertexIndex].normal if face.use_smooth else face.normal)
                self.file.write(B", ")
                k += 1

            face = tessFaceArray[vertexArray[k].faceIndex]
            self.WriteVector3D(meshVertexArray[vertexArray[k].vertexIndex].normal if face.use_smooth else face.normal)
            k += 1

            if i * 8 < count - 8:
                self.file.write(B",\n")
            else:
                self.file.write(B"\n")

        count &= 7
        if count != 0:
            self.IndentWrite(B"", 1)
            for j in range(count - 1):
                face = tessFaceArray[vertexArray[k].faceIndex]
                self.WriteVector3D(
                    meshVertexArray[vertexArray[k].vertexIndex].normal if face.use_smooth else face.normal)
                self.file.write(B", ")
                k += 1

            face = tessFaceArray[vertexArray[k].faceIndex]
            self.WriteVector3D(meshVertexArray[vertexArray[k].vertexIndex].normal if face.use_smooth else face.normal)
            self.file.write(B"\n")

    def WriteTriangle(self, triangleIndex, indexTable):
        i = triangleIndex * 3
        self.file.write(B"{")
        self.WriteInt(indexTable[i])
        self.file.write(B", ")
        self.WriteInt(indexTable[i + 1])
        self.file.write(B", ")
        self.WriteInt(indexTable[i + 2])
        self.file.write(B"}")

    def WriteTriangleArray(self, count, indexTable):
        debug()
        triangleIndex = 0

        lineCount = count >> 4
        for i in range(lineCount):
            self.IndentWrite(B"", 1)
            for j in range(15):
                self.WriteTriangle(triangleIndex, indexTable)
                self.file.write(B", ")
                triangleIndex += 1

            self.WriteTriangle(triangleIndex, indexTable)
            triangleIndex += 1

            if i * 16 < count - 16:
                self.file.write(B",\n")
            else:
                self.file.write(B"\n")

        count &= 15
        if count != 0:
            self.IndentWrite(B"", 1)
            for j in range(count - 1):
                self.WriteTriangle(triangleIndex, indexTable)
                self.file.write(B", ")
                triangleIndex += 1

            self.WriteTriangle(triangleIndex, indexTable)
            self.file.write(B"\n")

    def WriteNodeTable(self, objectRef):
        debug()
        first = True
        for node in objectRef[1]["nodeTable"]:
            if first:
                self.file.write(B"\t\t// ")
            else:
                self.file.write(B", ")
            self.file.write(bytes(node.name, "UTF-8"))
            first = False