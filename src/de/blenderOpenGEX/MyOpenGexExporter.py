__author__ = 'aullik'

from blenderOpenGEX.FlagContainer import *
from blenderOpenGEX.NodeWrapper import NodeWrapper
from blenderOpenGEX.ExportVertex import ExportVertex
from blenderOpenGEX import debug
import bpy
import math
from bpy_extras.io_utils import ExportHelper


kAnimationSampled = 0
kAnimationLinear = 1
kAnimationBezier = 2

kExportEpsilon = 1.0e-6

structIdentifier = [B"Node $", B"BoneNode $", B"GeometryNode $", B"LightNode $", B"CameraNode $"]

subtranslationName = [B"xpos", B"ypos", B"zpos"]
subrotationName = [B"xrot", B"yrot", B"zrot"]
subscaleName = [B"xscl", B"yscl", B"zscl"]
deltaSubtranslationName = [B"dxpos", B"dypos", B"dzpos"]
deltaSubrotationName = [B"dxrot", B"dyrot", B"dzrot"]
deltaSubscaleName = [B"dxscl", B"dyscl", B"dzscl"]
axisName = [B"x", B"y", B"z"]


class OpenGexExporter(bpy.types.Operator, ExportHelper):
    """Export to OpenGEX format"""
    bl_idname = "export_scene.ogex"
    bl_label = "Export OpenGEX"
    filename_ext = ".ogex"

    option_export_selection = bpy.props.BoolProperty(name="Export Selection Only",
                                                     description="Export only selected objects", default=False)
    option_sample_animation = bpy.props.BoolProperty(name="Force Sampled Animation",
                                                     description="Always export animation as per-frame samples",
                                                     default=False)

    def __init__(self):
        debug()
        super().__init__()

    def Write(self, text):
        debug()
        self.container.file.write(text)

    def IndentWrite(self, text, extra=0, newline=False):
        debug()
        if newline:
            self.container.file.write(B"\n")
        for i in range(self.container.indentLevel + extra):
            self.container.file.write(B"\t")
        self.container.file.write(text)

    def WriteInt(self, i):
        debug()
        self.container.file.write(bytes(str(i), "UTF-8"))

    def WriteFloat(self, f):
        debug()
        if (math.isinf(f)) or (math.isnan(f)):
            self.container.file.write(B"0.0")
        else:
            # TODO make float rounding optional
            self.container.file.write(bytes(str(round(f, 6)), "UTF-8"))

    def WriteMatrix(self, matrix):
        debug()
        self.IndentWrite(B"{", 1)
        self.WriteFloat(matrix[0][0])
        self.Write(B", ")
        self.WriteFloat(matrix[1][0])
        self.Write(B", ")
        self.WriteFloat(matrix[2][0])
        self.Write(B", ")
        self.WriteFloat(matrix[3][0])
        self.Write(B",\n")

        self.IndentWrite(B" ", 1)
        self.WriteFloat(matrix[0][1])
        self.Write(B", ")
        self.WriteFloat(matrix[1][1])
        self.Write(B", ")
        self.WriteFloat(matrix[2][1])
        self.Write(B", ")
        self.WriteFloat(matrix[3][1])
        self.Write(B",\n")

        self.IndentWrite(B" ", 1)
        self.WriteFloat(matrix[0][2])
        self.Write(B", ")
        self.WriteFloat(matrix[1][2])
        self.Write(B", ")
        self.WriteFloat(matrix[2][2])
        self.Write(B", ")
        self.WriteFloat(matrix[3][2])
        self.Write(B",\n")

        self.IndentWrite(B" ", 1)
        self.WriteFloat(matrix[0][3])
        self.Write(B", ")
        self.WriteFloat(matrix[1][3])
        self.Write(B", ")
        self.WriteFloat(matrix[2][3])
        self.Write(B", ")
        self.WriteFloat(matrix[3][3])
        self.Write(B"}\n")

    def WriteMatrixFlat(self, matrix):
        debug()
        self.IndentWrite(B"{", 1)
        self.WriteFloat(matrix[0][0])
        self.Write(B", ")
        self.WriteFloat(matrix[1][0])
        self.Write(B", ")
        self.WriteFloat(matrix[2][0])
        self.Write(B", ")
        self.WriteFloat(matrix[3][0])
        self.Write(B", ")
        self.WriteFloat(matrix[0][1])
        self.Write(B", ")
        self.WriteFloat(matrix[1][1])
        self.Write(B", ")
        self.WriteFloat(matrix[2][1])
        self.Write(B", ")
        self.WriteFloat(matrix[3][1])
        self.Write(B", ")
        self.WriteFloat(matrix[0][2])
        self.Write(B", ")
        self.WriteFloat(matrix[1][2])
        self.Write(B", ")
        self.WriteFloat(matrix[2][2])
        self.Write(B", ")
        self.WriteFloat(matrix[3][2])
        self.Write(B", ")
        self.WriteFloat(matrix[0][3])
        self.Write(B", ")
        self.WriteFloat(matrix[1][3])
        self.Write(B", ")
        self.WriteFloat(matrix[2][3])
        self.Write(B", ")
        self.WriteFloat(matrix[3][3])
        self.Write(B"}")

    def WriteColor(self, color):
        debug()
        self.Write(B"{")
        self.WriteFloat(color[0])
        self.Write(B", ")
        self.WriteFloat(color[1])
        self.Write(B", ")
        self.WriteFloat(color[2])
        self.Write(B"}")

    def WriteFileName(self, filename):
        debug()
        length = len(filename)
        if length != 0:
            if (length > 2) and (filename[1] == ":"):
                self.Write(B"//")
                self.Write(bytes(filename[0], "UTF-8"))
                self.Write(bytes(filename[2:length].replace("\\", "/"), "UTF-8"))
            else:
                self.Write(bytes(filename.replace("\\", "/"), "UTF-8"))

    def WriteIntArray(self, valueArray):
        debug()
        count = len(valueArray)
        k = 0

        lineCount = count >> 6
        for i in range(lineCount):
            self.IndentWrite(B"", 1)
            for j in range(63):
                self.WriteInt(valueArray[k])
                self.Write(B", ")
                k += 1

            self.WriteInt(valueArray[k])
            k += 1

            if i * 64 < count - 64:
                self.Write(B",\n")
            else:
                self.Write(B"\n")

        count &= 63
        if count != 0:
            self.IndentWrite(B"", 1)
            for j in range(count - 1):
                self.WriteInt(valueArray[k])
                self.Write(B", ")
                k += 1

            self.WriteInt(valueArray[k])
            self.Write(B"\n")

    def WriteFloatArray(self, valueArray):
        debug()
        count = len(valueArray)
        k = 0

        lineCount = count >> 4
        for i in range(lineCount):
            self.IndentWrite(B"", 1)
            for j in range(15):
                self.WriteFloat(valueArray[k])
                self.Write(B", ")
                k += 1

            self.WriteFloat(valueArray[k])
            k += 1

            if i * 16 < count - 16:
                self.Write(B",\n")
            else:
                self.Write(B"\n")

        count &= 15
        if count != 0:
            self.IndentWrite(B"", 1)
            for j in range(count - 1):
                self.WriteFloat(valueArray[k])
                self.Write(B", ")
                k += 1

            self.WriteFloat(valueArray[k])
            self.Write(B"\n")

    def WriteVector2D(self, vector):
        debug()
        self.Write(B"{")
        self.WriteFloat(vector[0])
        self.Write(B", ")
        self.WriteFloat(vector[1])
        self.Write(B"}")

    def WriteVector3D(self, vector):
        debug()
        self.Write(B"{")
        self.WriteFloat(vector[0])
        self.Write(B", ")
        self.WriteFloat(vector[1])
        self.Write(B", ")
        self.WriteFloat(vector[2])
        self.Write(B"}")

    def WriteVector4D(self, vector):
        debug()
        self.Write(B"{")
        self.WriteFloat(vector[0])
        self.Write(B", ")
        self.WriteFloat(vector[1])
        self.Write(B", ")
        self.WriteFloat(vector[2])
        self.Write(B", ")
        self.WriteFloat(vector[3])
        self.Write(B"}")

    def WriteQuaternion(self, quaternion):
        debug()
        self.Write(B"{")
        self.WriteFloat(quaternion[1])
        self.Write(B", ")
        self.WriteFloat(quaternion[2])
        self.Write(B", ")
        self.WriteFloat(quaternion[3])
        self.Write(B", ")
        self.WriteFloat(quaternion[0])
        self.Write(B"}")

    def WriteVertexArray2D(self, vertexArray, attrib):
        debug()
        count = len(vertexArray)
        k = 0

        lineCount = count >> 3
        for i in range(lineCount):
            self.IndentWrite(B"", 1)
            for j in range(7):
                self.WriteVector2D(getattr(vertexArray[k], attrib))
                self.Write(B", ")
                k += 1

            self.WriteVector2D(getattr(vertexArray[k], attrib))
            k += 1

            if i * 8 < count - 8:
                self.Write(B",\n")
            else:
                self.Write(B"\n")

        count &= 7
        if count != 0:
            self.IndentWrite(B"", 1)
            for j in range(count - 1):
                self.WriteVector2D(getattr(vertexArray[k], attrib))
                self.Write(B", ")
                k += 1

            self.WriteVector2D(getattr(vertexArray[k], attrib))
            self.Write(B"\n")

    def WriteVertexArray3D(self, vertexArray, attrib):
        debug()
        count = len(vertexArray)
        k = 0

        lineCount = count >> 3
        for i in range(lineCount):
            self.IndentWrite(B"", 1)
            for j in range(7):
                self.WriteVector3D(getattr(vertexArray[k], attrib))
                self.Write(B", ")
                k += 1

            self.WriteVector3D(getattr(vertexArray[k], attrib))
            k += 1

            if i * 8 < count - 8:
                self.Write(B",\n")
            else:
                self.Write(B"\n")

        count &= 7
        if count != 0:
            self.IndentWrite(B"", 1)
            for j in range(count - 1):
                self.WriteVector3D(getattr(vertexArray[k], attrib))
                self.Write(B", ")
                k += 1

            self.WriteVector3D(getattr(vertexArray[k], attrib))
            self.Write(B"\n")

    def WriteMorphPositionArray3D(self, vertexArray, meshVertexArray):
        debug()
        count = len(vertexArray)
        k = 0

        lineCount = count >> 3
        for i in range(lineCount):
            self.IndentWrite(B"", 1)
            for j in range(7):
                self.WriteVector3D(meshVertexArray[vertexArray[k].vertexIndex].co)
                self.Write(B", ")
                k += 1

            self.WriteVector3D(meshVertexArray[vertexArray[k].vertexIndex].co)
            k += 1

            if i * 8 < count - 8:
                self.Write(B",\n")
            else:
                self.Write(B"\n")

        count &= 7
        if count != 0:
            self.IndentWrite(B"", 1)
            for j in range(count - 1):
                self.WriteVector3D(meshVertexArray[vertexArray[k].vertexIndex].co)
                self.Write(B", ")
                k += 1

            self.WriteVector3D(meshVertexArray[vertexArray[k].vertexIndex].co)
            self.Write(B"\n")

    def WriteMorphNormalArray3D(self, vertexArray, meshVertexArray, tessFaceArray):
        debug()
        count = len(vertexArray)
        k = 0

        lineCount = count >> 3
        for i in range(lineCount):
            self.IndentWrite(B"", 1)
            for j in range(7):
                face = tessFaceArray[vertexArray[k].faceIndex]
                self.WriteVector3D(
                    meshVertexArray[vertexArray[k].vertexIndex].normal if face.use_smooth else face.normal)
                self.Write(B", ")
                k += 1

            face = tessFaceArray[vertexArray[k].faceIndex]
            self.WriteVector3D(meshVertexArray[vertexArray[k].vertexIndex].normal if face.use_smooth else face.normal)
            k += 1

            if i * 8 < count - 8:
                self.Write(B",\n")
            else:
                self.Write(B"\n")

        count &= 7
        if count != 0:
            self.IndentWrite(B"", 1)
            for j in range(count - 1):
                face = tessFaceArray[vertexArray[k].faceIndex]
                self.WriteVector3D(
                    meshVertexArray[vertexArray[k].vertexIndex].normal if face.use_smooth else face.normal)
                self.Write(B", ")
                k += 1

            face = tessFaceArray[vertexArray[k].faceIndex]
            self.WriteVector3D(meshVertexArray[vertexArray[k].vertexIndex].normal if face.use_smooth else face.normal)
            self.Write(B"\n")

    def WriteTriangle(self, triangleIndex, indexTable):
        debug()
        i = triangleIndex * 3
        self.Write(B"{")
        self.WriteInt(indexTable[i])
        self.Write(B", ")
        self.WriteInt(indexTable[i + 1])
        self.Write(B", ")
        self.WriteInt(indexTable[i + 2])
        self.Write(B"}")

    def WriteTriangleArray(self, count, indexTable):
        debug()
        triangleIndex = 0

        lineCount = count >> 4
        for i in range(lineCount):
            self.IndentWrite(B"", 1)
            for j in range(15):
                self.WriteTriangle(triangleIndex, indexTable)
                self.Write(B", ")
                triangleIndex += 1

            self.WriteTriangle(triangleIndex, indexTable)
            triangleIndex += 1

            if i * 16 < count - 16:
                self.Write(B",\n")
            else:
                self.Write(B"\n")

        count &= 15
        if count != 0:
            self.IndentWrite(B"", 1)
            for j in range(count - 1):
                self.WriteTriangle(triangleIndex, indexTable)
                self.Write(B", ")
                triangleIndex += 1

            self.WriteTriangle(triangleIndex, indexTable)
            self.Write(B"\n")

    def WriteNodeTable(self, objectRef):
        debug()
        first = True
        for node in objectRef[1]["nodeTable"]:
            if first:
                self.Write(B"\t\t// ")
            else:
                self.Write(B", ")
            self.Write(bytes(node.name, "UTF-8"))
            first = False

#########################################################
        # TODO Above: all Writing methods
#########################################################

    @staticmethod
    def GetShapeKeys(mesh):
        debug()
        shapeKeys = mesh.shape_keys
        if shapeKeys and (len(shapeKeys.key_blocks) > 1):
            return shapeKeys

        return None

    def FindNode(self, name):
        debug()
        for nodeRef in self.nodeArray.items():
            if nodeRef[0].name == name:
                return nodeRef
        return None

    @staticmethod
    def DeindexMesh(mesh, materialTable):
        debug()

        # This function deindexes all vertex positions, colors, and texcoords.
        # Three separate ExportVertex structures are created for each triangle.

        vertexArray = mesh.vertices
        exportVertexArray = []
        faceIndex = 0

        for face in mesh.tessfaces:
            k1 = face.vertices[0]
            k2 = face.vertices[1]
            k3 = face.vertices[2]

            v1 = vertexArray[k1]
            v2 = vertexArray[k2]
            v3 = vertexArray[k3]

            exportVertex = ExportVertex()
            exportVertex.vertexIndex = k1
            exportVertex.faceIndex = faceIndex
            exportVertex.position = v1.co
            exportVertex.normal = v1.normal if face.use_smooth else face.normal
            exportVertexArray.append(exportVertex)

            exportVertex = ExportVertex()
            exportVertex.vertexIndex = k2
            exportVertex.faceIndex = faceIndex
            exportVertex.position = v2.co
            exportVertex.normal = v2.normal if face.use_smooth else face.normal
            exportVertexArray.append(exportVertex)

            exportVertex = ExportVertex()
            exportVertex.vertexIndex = k3
            exportVertex.faceIndex = faceIndex
            exportVertex.position = v3.co
            exportVertex.normal = v3.normal if face.use_smooth else face.normal
            exportVertexArray.append(exportVertex)

            materialTable.append(face.material_index)

            if len(face.vertices) == 4:
                k1 = face.vertices[0]
                k2 = face.vertices[2]
                k3 = face.vertices[3]

                v1 = vertexArray[k1]
                v2 = vertexArray[k2]
                v3 = vertexArray[k3]

                exportVertex = ExportVertex()
                exportVertex.vertexIndex = k1
                exportVertex.faceIndex = faceIndex
                exportVertex.position = v1.co
                exportVertex.normal = v1.normal if face.use_smooth else face.normal
                exportVertexArray.append(exportVertex)

                exportVertex = ExportVertex()
                exportVertex.vertexIndex = k2
                exportVertex.faceIndex = faceIndex
                exportVertex.position = v2.co
                exportVertex.normal = v2.normal if face.use_smooth else face.normal
                exportVertexArray.append(exportVertex)

                exportVertex = ExportVertex()
                exportVertex.vertexIndex = k3
                exportVertex.faceIndex = faceIndex
                exportVertex.position = v3.co
                exportVertex.normal = v3.normal if face.use_smooth else face.normal
                exportVertexArray.append(exportVertex)

                materialTable.append(face.material_index)

            faceIndex += 1

        colorCount = len(mesh.tessface_vertex_colors)
        if colorCount > 0:
            colorFace = mesh.tessface_vertex_colors[0].data
            vertexIndex = 0
            faceIndex = 0

            for face in mesh.tessfaces:
                cf = colorFace[faceIndex]
                exportVertexArray[vertexIndex].color = cf.color1
                vertexIndex += 1
                exportVertexArray[vertexIndex].color = cf.color2
                vertexIndex += 1
                exportVertexArray[vertexIndex].color = cf.color3
                vertexIndex += 1

                if len(face.vertices) == 4:
                    exportVertexArray[vertexIndex].color = cf.color1
                    vertexIndex += 1
                    exportVertexArray[vertexIndex].color = cf.color3
                    vertexIndex += 1
                    exportVertexArray[vertexIndex].color = cf.color4
                    vertexIndex += 1

                faceIndex += 1
                
        # go through all UV maps and add all active_render to a list
        active_tessface_uv_textures = [] # the first two uv maps will be inserted into this array
        texcoordCount = 0 # number of UV maps, max 2
        
        # find first two active uv maps
        for index in range(len(mesh.tessface_uv_textures)):
            if mesh.uv_textures[index].active_render:
                active_tessface_uv_textures.append(mesh.tessface_uv_textures[index])
                texcoordCount += 1
                if texcoordCount == 1:
                    break
                    
        if texcoordCount > 0:
            texcoordFace = active_tessface_uv_textures[0].data
            vertexIndex = 0
            faceIndex = 0

            for face in mesh.tessfaces:
                tf = texcoordFace[faceIndex]
                exportVertexArray[vertexIndex].texcoord0 = tf.uv1
                vertexIndex += 1
                exportVertexArray[vertexIndex].texcoord0 = tf.uv2
                vertexIndex += 1
                exportVertexArray[vertexIndex].texcoord0 = tf.uv3
                vertexIndex += 1

                if len(face.vertices) == 4:
                    exportVertexArray[vertexIndex].texcoord0 = tf.uv1
                    vertexIndex += 1
                    exportVertexArray[vertexIndex].texcoord0 = tf.uv3
                    vertexIndex += 1
                    exportVertexArray[vertexIndex].texcoord0 = tf.uv4
                    vertexIndex += 1

                faceIndex += 1

            if texcoordCount > 1:
                texcoordFace = active_tessface_uv_textures[1].data
                vertexIndex = 0
                faceIndex = 0

                for face in mesh.tessfaces:
                    tf = texcoordFace[faceIndex]
                    exportVertexArray[vertexIndex].texcoord1 = tf.uv1
                    vertexIndex += 1
                    exportVertexArray[vertexIndex].texcoord1 = tf.uv2
                    vertexIndex += 1
                    exportVertexArray[vertexIndex].texcoord1 = tf.uv3
                    vertexIndex += 1

                    if len(face.vertices) == 4:
                        exportVertexArray[vertexIndex].texcoord1 = tf.uv1
                        vertexIndex += 1
                        exportVertexArray[vertexIndex].texcoord1 = tf.uv3
                        vertexIndex += 1
                        exportVertexArray[vertexIndex].texcoord1 = tf.uv4
                        vertexIndex += 1

                    faceIndex += 1

        for ev in exportVertexArray:
            ev.Hash()

        return exportVertexArray

    @staticmethod
    def FindExportVertex(bucket, exportVertexArray, vertex):
        debug()
        for index in bucket:
            if exportVertexArray[index] == vertex:
                return index

        return -1

    @staticmethod
    def UnifyVertices(exportVertexArray, indexTable):
        debug()

        # This function looks for identical vertices having exactly the same position, normal,
        # color, and texcoords. Duplicate vertices are unified, and a new index table is returned.

        bucketCount = len(exportVertexArray) >> 3
        if bucketCount > 1:

            # Round down to nearest power of two.

            while True:
                count = bucketCount & (bucketCount - 1)
                if count == 0:
                    break
                bucketCount = count
        else:
            bucketCount = 1

        hashTable = [[] for i in range(bucketCount)]
        unifiedVertexArray = []

        for i in range(len(exportVertexArray)):
            ev = exportVertexArray[i]
            bucket = ev.hash & (bucketCount - 1)
            index = OpenGexExporter.FindExportVertex(hashTable[bucket], exportVertexArray, ev)
            if index < 0:
                indexTable.append(len(unifiedVertexArray))
                unifiedVertexArray.append(ev)
                hashTable[bucket].append(i)
            else:
                indexTable.append(indexTable[index])

        return unifiedVertexArray

    @staticmethod
    def ClassifyAnimationCurve(fcurve):
        debug()
        linearCount = 0
        bezierCount = 0

        for key in fcurve.keyframe_points:
            interp = key.interpolation
            if interp == "LINEAR":
                linearCount += 1
            elif interp == "BEZIER":
                bezierCount += 1
            else:
                return kAnimationSampled

        if bezierCount == 0:
            return kAnimationLinear
        elif linearCount == 0:
            return kAnimationBezier

        return kAnimationSampled

    @staticmethod
    def AnimationKeysDifferent(fcurve):
        debug()
        keyCount = len(fcurve.keyframe_points)
        if keyCount > 0:
            key1 = fcurve.keyframe_points[0].co[1]

            for i in range(1, keyCount):
                key2 = fcurve.keyframe_points[i].co[1]
                if math.fabs(key2 - key1) > kExportEpsilon:
                    return True

        return False

    @staticmethod
    def AnimationTangentsNonzero(fcurve):
        debug()
        keyCount = len(fcurve.keyframe_points)
        if keyCount > 0:
            key = fcurve.keyframe_points[0].co[1]
            left = fcurve.keyframe_points[0].handle_left[1]
            right = fcurve.keyframe_points[0].handle_right[1]
            if (math.fabs(key - left) > kExportEpsilon) or (math.fabs(right - key) > kExportEpsilon):
                return True

            for i in range(1, keyCount):
                key = fcurve.keyframe_points[i].co[1]
                left = fcurve.keyframe_points[i].handle_left[1]
                right = fcurve.keyframe_points[i].handle_right[1]
                if (math.fabs(key - left) > kExportEpsilon) or (math.fabs(right - key) > kExportEpsilon):
                    return True

        return False

    @staticmethod
    def AnimationPresent(fcurve, kind):
        debug()
        if kind != kAnimationBezier:
            return OpenGexExporter.AnimationKeysDifferent(fcurve)

        return (OpenGexExporter.AnimationKeysDifferent(fcurve)) or (OpenGexExporter.AnimationTangentsNonzero(fcurve))

    @staticmethod
    def MatricesDifferent(m1, m2):
        debug()
        for i in range(4):
            for j in range(4):
                if math.fabs(m1[i][j] - m2[i][j]) > kExportEpsilon:
                    return True

        return False

    @staticmethod
    def CollectBoneAnimation(armature, name):
        debug()
        path = "pose.bones[\"" + name + "\"]."
        curveArray = []

        if armature.animation_data:
            action = armature.animation_data.action
            if action:
                for fcurve in action.fcurves:
                    if fcurve.data_path.startswith(path):
                        curveArray.append(fcurve)

        return curveArray

    def ExportKeyTimes(self, fcurve):
        debug()
        self.IndentWrite(B"Key {float {")

        keyCount = len(fcurve.keyframe_points)
        for i in range(keyCount):
            if i > 0:
                self.Write(B", ")

            time = fcurve.keyframe_points[i].co[0] - self.container.beginFrame
            self.WriteFloat(time * self.container.frameTime)

        self.Write(B"}}\n")

    def ExportKeyTimeControlPoints(self, fcurve):
        debug()
        self.IndentWrite(B"Key (kind = \"-control\") {float {")

        keyCount = len(fcurve.keyframe_points)
        for i in range(keyCount):
            if i > 0:
                self.Write(B", ")

            ctrl = fcurve.keyframe_points[i].handle_left[0] - self.container.beginFrame
            self.WriteFloat(ctrl * self.container.frameTime)

        self.Write(B"}}\n")
        self.IndentWrite(B"Key (kind = \"+control\") {float {")

        for i in range(keyCount):
            if i > 0:
                self.Write(B", ")

            ctrl = fcurve.keyframe_points[i].handle_right[0] - self.container.beginFrame
            self.WriteFloat(ctrl * self.container.frameTime)

        self.Write(B"}}\n")

    def ExportKeyValues(self, fcurve):
        debug()
        self.IndentWrite(B"Key {float {")

        keyCount = len(fcurve.keyframe_points)
        for i in range(keyCount):
            if i > 0:
                self.Write(B", ")

            value = fcurve.keyframe_points[i].co[1]
            self.WriteFloat(value)

        self.Write(B"}}\n")

    def ExportKeyValueControlPoints(self, fcurve):
        debug()
        self.IndentWrite(B"Key (kind = \"-control\") {float {")

        keyCount = len(fcurve.keyframe_points)
        for i in range(keyCount):
            if i > 0:
                self.Write(B", ")

            ctrl = fcurve.keyframe_points[i].handle_left[1]
            self.WriteFloat(ctrl)

        self.Write(B"}}\n")
        self.IndentWrite(B"Key (kind = \"+control\") {float {")

        for i in range(keyCount):
            if i > 0:
                self.Write(B", ")

            ctrl = fcurve.keyframe_points[i].handle_right[1]
            self.WriteFloat(ctrl)

        self.Write(B"}}\n")

    def ExportAnimationTrack(self, fcurve, kind, target, newline):
        debug()

        # This function exports a single animation track. The curve types for the
        # Time and Value structures are given by the kind parameter.

        self.IndentWrite(B"Track (target = %", 0, newline)
        self.Write(target)
        self.Write(B")\n")
        self.IndentWrite(B"{\n")
        self.container.indentLevel += 1

        if kind != kAnimationBezier:
            self.IndentWrite(B"Time\n")
            self.IndentWrite(B"{\n")
            self.container.indentLevel += 1

            self.ExportKeyTimes(fcurve)

            self.IndentWrite(B"}\n\n", -1)
            self.IndentWrite(B"Value\n", -1)
            self.IndentWrite(B"{\n", -1)

            self.ExportKeyValues(fcurve)

            self.container.indentLevel -= 1
            self.IndentWrite(B"}\n")

        else:
            self.IndentWrite(B"Time (curve = \"bezier\")\n")
            self.IndentWrite(B"{\n")
            self.container.indentLevel += 1

            self.ExportKeyTimes(fcurve)
            self.ExportKeyTimeControlPoints(fcurve)

            self.IndentWrite(B"}\n\n", -1)
            self.IndentWrite(B"Value (curve = \"bezier\")\n", -1)
            self.IndentWrite(B"{\n", -1)

            self.ExportKeyValues(fcurve)
            self.ExportKeyValueControlPoints(fcurve)

            self.container.indentLevel -= 1
            self.IndentWrite(B"}\n")

        self.container.indentLevel -= 1
        self.IndentWrite(B"}\n")

    def ExportNodeSampledAnimation(self, node, scene):
        debug()

        # This function exports animation as full 4x4 matrices for each frame.

        currentFrame = scene.frame_current
        currentSubframe = scene.frame_subframe

        animationFlag = False
        m1 = node.matrix_local.copy()

        for i in range(self.container.beginFrame, self.container.endFrame):
            scene.frame_set(i)
            m2 = node.matrix_local
            if OpenGexExporter.MatricesDifferent(m1, m2):
                animationFlag = True
                break

        if animationFlag:
            self.IndentWrite(B"Animation\n", 0, True)
            self.IndentWrite(B"{\n")
            self.container.indentLevel += 1

            self.IndentWrite(B"Track (target = %transform)\n")
            self.IndentWrite(B"{\n")
            self.container.indentLevel += 1

            self.IndentWrite(B"Time\n")
            self.IndentWrite(B"{\n")
            self.container.indentLevel += 1

            self.IndentWrite(B"Key {float {")

            for i in range(self.container.beginFrame, self.container.endFrame):
                self.WriteFloat((i - self.container.beginFrame) * self.container.frameTime)
                self.Write(B", ")

            self.WriteFloat(self.container.endFrame * self.container.frameTime)
            self.Write(B"}}\n")

            self.IndentWrite(B"}\n\n", -1)
            self.IndentWrite(B"Value\n", -1)
            self.IndentWrite(B"{\n", -1)

            self.IndentWrite(B"Key\n")
            self.IndentWrite(B"{\n")
            self.container.indentLevel += 1

            self.IndentWrite(B"float[16]\n")
            self.IndentWrite(B"{\n")

            for i in range(self.container.beginFrame, self.container.endFrame):
                scene.frame_set(i)
                self.WriteMatrixFlat(node.matrix_local)
                self.Write(B",\n")

            scene.frame_set(self.container.endFrame)
            self.WriteMatrixFlat(node.matrix_local)
            self.IndentWrite(B"}\n", 0, True)

            self.container.indentLevel -= 1
            self.IndentWrite(B"}\n")

            self.container.indentLevel -= 1
            self.IndentWrite(B"}\n")

            self.container.indentLevel -= 1
            self.IndentWrite(B"}\n")

            self.container.indentLevel -= 1
            self.IndentWrite(B"}\n")

        scene.frame_set(currentFrame, currentSubframe)

    def ExportBoneSampledAnimation(self, poseBone, scene):
        debug()

        # This function exports bone animation as full 4x4 matrices for each frame.

        currentFrame = scene.frame_current
        currentSubframe = scene.frame_subframe

        animationFlag = False
        m1 = poseBone.matrix.copy()

        for i in range(self.container.beginFrame, self.container.endFrame):
            scene.frame_set(i)
            m2 = poseBone.matrix
            if OpenGexExporter.MatricesDifferent(m1, m2):
                animationFlag = True
                break

        if animationFlag:
            self.IndentWrite(B"Animation\n", 0, True)
            self.IndentWrite(B"{\n")
            self.container.indentLevel += 1

            self.IndentWrite(B"Track (target = %transform)\n")
            self.IndentWrite(B"{\n")
            self.container.indentLevel += 1

            self.IndentWrite(B"Time\n")
            self.IndentWrite(B"{\n")
            self.container.indentLevel += 1

            self.IndentWrite(B"Key {float {")

            for i in range(self.container.beginFrame, self.container.endFrame):
                self.WriteFloat((i - self.container.beginFrame) * self.container.frameTime)
                self.Write(B", ")

            self.WriteFloat(self.container.endFrame * self.container.frameTime)
            self.Write(B"}}\n")

            self.IndentWrite(B"}\n\n", -1)
            self.IndentWrite(B"Value\n", -1)
            self.IndentWrite(B"{\n", -1)

            self.IndentWrite(B"Key\n")
            self.IndentWrite(B"{\n")
            self.container.indentLevel += 1

            self.IndentWrite(B"float[16]\n")
            self.IndentWrite(B"{\n")

            parent = poseBone.parent
            if parent:
                for i in range(self.container.beginFrame, self.container.endFrame):
                    scene.frame_set(i)
                    if math.fabs(parent.matrix.determinant()) > kExportEpsilon:
                        self.WriteMatrixFlat(parent.matrix.inverted() * poseBone.matrix)
                    else:
                        self.WriteMatrixFlat(poseBone.matrix)

                    self.Write(B",\n")

                scene.frame_set(self.container.endFrame)
                if math.fabs(parent.matrix.determinant()) > kExportEpsilon:
                    self.WriteMatrixFlat(parent.matrix.inverted() * poseBone.matrix)
                else:
                    self.WriteMatrixFlat(poseBone.matrix)

                self.IndentWrite(B"}\n", 0, True)

            else:
                for i in range(self.container.beginFrame, self.container.endFrame):
                    scene.frame_set(i)
                    self.WriteMatrixFlat(poseBone.matrix)
                    self.Write(B",\n")

                scene.frame_set(self.container.endFrame)
                self.WriteMatrixFlat(poseBone.matrix)
                self.IndentWrite(B"}\n", 0, True)

            self.container.indentLevel -= 1
            self.IndentWrite(B"}\n")

            self.container.indentLevel -= 1
            self.IndentWrite(B"}\n")

            self.container.indentLevel -= 1
            self.IndentWrite(B"}\n")

            self.container.indentLevel -= 1
            self.IndentWrite(B"}\n")

        scene.frame_set(currentFrame, currentSubframe)

    def ExportMorphWeightSampledAnimationTrack(self, block, target, scene, newline):
        debug()
        currentFrame = scene.frame_current
        currentSubframe = scene.frame_subframe

        self.IndentWrite(B"Track (target = %", 0, newline)
        self.Write(target)
        self.Write(B")\n")
        self.IndentWrite(B"{\n")
        self.container.indentLevel += 1

        self.IndentWrite(B"Time\n")
        self.IndentWrite(B"{\n")
        self.container.indentLevel += 1

        self.IndentWrite(B"Key {float {")

        for i in range(self.container.beginFrame, self.container.endFrame):
            self.WriteFloat((i - self.container.beginFrame) * self.container.frameTime)
            self.Write(B", ")

        self.WriteFloat(self.container.endFrame * self.container.frameTime)
        self.Write(B"}}\n")

        self.IndentWrite(B"}\n\n", -1)
        self.IndentWrite(B"Value\n", -1)
        self.IndentWrite(B"{\n", -1)

        self.IndentWrite(B"Key {float {")

        for i in range(self.container.beginFrame, self.container.endFrame):
            scene.frame_set(i)
            self.WriteFloat(block.value)
            self.Write(B", ")

        scene.frame_set(self.container.endFrame)
        self.WriteFloat(block.value)
        self.Write(B"}}\n")

        self.container.indentLevel -= 1
        self.IndentWrite(B"}\n")

        self.container.indentLevel -= 1
        self.IndentWrite(B"}\n")

        scene.frame_set(currentFrame, currentSubframe)

    # FIXME Handle NodeWrapper
    def ExportNodeTransform(self, nw, scene):
        node = nw.item
        debug()
        posAnimCurve = [None, None, None]
        rotAnimCurve = [None, None, None]
        sclAnimCurve = [None, None, None]
        posAnimKind = [0, 0, 0]
        rotAnimKind = [0, 0, 0]
        sclAnimKind = [0, 0, 0]

        deltaPosAnimCurve = [None, None, None]
        deltaRotAnimCurve = [None, None, None]
        deltaSclAnimCurve = [None, None, None]
        deltaPosAnimKind = [0, 0, 0]
        deltaRotAnimKind = [0, 0, 0]
        deltaSclAnimKind = [0, 0, 0]

        positionAnimated = False
        rotationAnimated = False
        scaleAnimated = False
        posAnimated = [False, False, False]
        rotAnimated = [False, False, False]
        sclAnimated = [False, False, False]

        deltaPositionAnimated = False
        deltaRotationAnimated = False
        deltaScaleAnimated = False
        deltaPosAnimated = [False, False, False]
        deltaRotAnimated = [False, False, False]
        deltaSclAnimated = [False, False, False]

        mode = node.rotation_mode
        sampledAnimation = (self.container.sampleAnimationFlag or (mode == "QUATERNION") or (mode == "AXIS_ANGLE"))

        if (not sampledAnimation) and node.animation_data:
            action = node.animation_data.action
            if action:
                for fcurve in action.fcurves:
                    kind = OpenGexExporter.ClassifyAnimationCurve(fcurve)
                    if kind != kAnimationSampled:
                        if fcurve.data_path == "location":
                            for i in range(3):
                                if (fcurve.array_index == i) and (not posAnimCurve[i]):
                                    posAnimCurve[i] = fcurve
                                    posAnimKind[i] = kind
                                    if OpenGexExporter.AnimationPresent(fcurve, kind):
                                        posAnimated[i] = True
                        elif fcurve.data_path == "delta_location":
                            for i in range(3):
                                if (fcurve.array_index == i) and (not deltaPosAnimCurve[i]):
                                    deltaPosAnimCurve[i] = fcurve
                                    deltaPosAnimKind[i] = kind
                                    if OpenGexExporter.AnimationPresent(fcurve, kind):
                                        deltaPosAnimated[i] = True
                        elif fcurve.data_path == "rotation_euler":
                            for i in range(3):
                                if (fcurve.array_index == i) and (not rotAnimCurve[i]):
                                    rotAnimCurve[i] = fcurve
                                    rotAnimKind[i] = kind
                                    if OpenGexExporter.AnimationPresent(fcurve, kind):
                                        rotAnimated[i] = True
                        elif fcurve.data_path == "delta_rotation_euler":
                            for i in range(3):
                                if (fcurve.array_index == i) and (not deltaRotAnimCurve[i]):
                                    deltaRotAnimCurve[i] = fcurve
                                    deltaRotAnimKind[i] = kind
                                    if OpenGexExporter.AnimationPresent(fcurve, kind):
                                        deltaRotAnimated[i] = True
                        elif fcurve.data_path == "scale":
                            for i in range(3):
                                if (fcurve.array_index == i) and (not sclAnimCurve[i]):
                                    sclAnimCurve[i] = fcurve
                                    sclAnimKind[i] = kind
                                    if OpenGexExporter.AnimationPresent(fcurve, kind):
                                        sclAnimated[i] = True
                        elif fcurve.data_path == "delta_scale":
                            for i in range(3):
                                if (fcurve.array_index == i) and (not deltaSclAnimCurve[i]):
                                    deltaSclAnimCurve[i] = fcurve
                                    deltaSclAnimKind[i] = kind
                                    if OpenGexExporter.AnimationPresent(fcurve, kind):
                                        deltaSclAnimated[i] = True
                        elif ((fcurve.data_path == "rotation_axis_angle") or (
                                    fcurve.data_path == "rotation_quaternion") or (
                                    fcurve.data_path == "delta_rotation_quaternion")):
                            sampledAnimation = True
                            break
                    else:
                        sampledAnimation = True
                        break

        positionAnimated = posAnimated[0] | posAnimated[1] | posAnimated[2]
        rotationAnimated = rotAnimated[0] | rotAnimated[1] | rotAnimated[2]
        scaleAnimated = sclAnimated[0] | sclAnimated[1] | sclAnimated[2]

        deltaPositionAnimated = deltaPosAnimated[0] | deltaPosAnimated[1] | deltaPosAnimated[2]
        deltaRotationAnimated = deltaRotAnimated[0] | deltaRotAnimated[1] | deltaRotAnimated[2]
        deltaScaleAnimated = deltaSclAnimated[0] | deltaSclAnimated[1] | deltaSclAnimated[2]

        if (sampledAnimation or ((not positionAnimated) and (not rotationAnimated) and (not scaleAnimated) and (
                not deltaPositionAnimated) and (not deltaRotationAnimated) and (not deltaScaleAnimated))):

            # If there's no keyframe animation at all, then write the node transform as a single 4x4 matrix.
            # We might still be exporting sampled animation below.

            self.IndentWrite(B"Transform")

            if sampledAnimation:
                self.Write(B" %transform")

            self.IndentWrite(B"{\n", 0, True)
            self.container.indentLevel += 1

            self.IndentWrite(B"float[16]\n")
            self.IndentWrite(B"{\n")

            self.handleOffset(node.matrix_local, nw.offset)
            self.IndentWrite(B"}\n")

            self.container.indentLevel -= 1
            self.IndentWrite(B"}\n")

            if sampledAnimation:
                self.ExportNodeSampledAnimation(node, scene)

        else:
            structFlag = False

            deltaTranslation = node.delta_location
            if deltaPositionAnimated:

                # When the delta location is animated, write the x, y, and z components separately
                # so they can be targeted by different tracks having different sets of keys.

                for i in range(3):
                    pos = deltaTranslation[i]
                    if (deltaPosAnimated[i]) or (math.fabs(pos) > kExportEpsilon):
                        self.IndentWrite(B"Translation %", 0, structFlag)
                        self.Write(deltaSubtranslationName[i])
                        self.Write(B" (kind = \"")
                        self.Write(axisName[i])
                        self.Write(B"\")\n")
                        self.IndentWrite(B"{\n")
                        self.IndentWrite(B"float {", 1)
                        self.WriteFloat(pos)
                        self.Write(B"}")
                        self.IndentWrite(B"}\n", 0, True)

                        structFlag = True

            elif ((math.fabs(deltaTranslation[0]) > kExportEpsilon) or (
                        math.fabs(deltaTranslation[1]) > kExportEpsilon) or (
                        math.fabs(deltaTranslation[2]) > kExportEpsilon)):
                self.IndentWrite(B"Translation\n")
                self.IndentWrite(B"{\n")
                self.IndentWrite(B"float[3] {", 1)
                self.WriteVector3D(deltaTranslation)
                self.Write(B"}")
                self.IndentWrite(B"}\n", 0, True)

                structFlag = True

            translation = node.location
            if positionAnimated:

                # When the location is animated, write the x, y, and z components separately
                # so they can be targeted by different tracks having different sets of keys.

                for i in range(3):
                    pos = translation[i]
                    if (posAnimated[i]) or (math.fabs(pos) > kExportEpsilon):
                        self.IndentWrite(B"Translation %", 0, structFlag)
                        self.Write(subtranslationName[i])
                        self.Write(B" (kind = \"")
                        self.Write(axisName[i])
                        self.Write(B"\")\n")
                        self.IndentWrite(B"{\n")
                        self.IndentWrite(B"float {", 1)
                        self.WriteFloat(pos)
                        self.Write(B"}")
                        self.IndentWrite(B"}\n", 0, True)

                        structFlag = True

            elif ((math.fabs(translation[0]) > kExportEpsilon) or (math.fabs(translation[1]) > kExportEpsilon) or (
                        math.fabs(translation[2]) > kExportEpsilon)):
                self.IndentWrite(B"Translation\n")
                self.IndentWrite(B"{\n")
                self.IndentWrite(B"float[3] {", 1)
                self.WriteVector3D(translation)
                self.Write(B"}")
                self.IndentWrite(B"}\n", 0, True)

                structFlag = True

            if deltaRotationAnimated:

                # When the delta rotation is animated, write three separate Euler angle rotations
                # so they can be targeted by different tracks having different sets of keys.

                for i in range(3):
                    axis = ord(mode[2 - i]) - 0x58
                    angle = node.delta_rotation_euler[axis]
                    if (deltaRotAnimated[axis]) or (math.fabs(angle) > kExportEpsilon):
                        self.IndentWrite(B"Rotation %", 0, structFlag)
                        self.Write(deltaSubrotationName[axis])
                        self.Write(B" (kind = \"")
                        self.Write(axisName[axis])
                        self.Write(B"\")\n")
                        self.IndentWrite(B"{\n")
                        self.IndentWrite(B"float {", 1)
                        self.WriteFloat(angle)
                        self.Write(B"}")
                        self.IndentWrite(B"}\n", 0, True)

                        structFlag = True

            else:

                # When the delta rotation is not animated, write it in the representation given by
                # the node's current rotation mode. (There is no axis-angle delta rotation.)

                if mode == "QUATERNION":
                    quaternion = node.delta_rotation_quaternion
                    if ((math.fabs(quaternion[0] - 1.0) > kExportEpsilon) or (
                                math.fabs(quaternion[1]) > kExportEpsilon) or (
                                math.fabs(quaternion[2]) > kExportEpsilon) or (
                                math.fabs(quaternion[3]) > kExportEpsilon)):
                        self.IndentWrite(B"Rotation (kind = \"quaternion\")\n", 0, structFlag)
                        self.IndentWrite(B"{\n")
                        self.IndentWrite(B"float[4] {", 1)
                        self.WriteQuaternion(quaternion)
                        self.Write(B"}")
                        self.IndentWrite(B"}\n", 0, True)

                        structFlag = True

                else:
                    for i in range(3):
                        axis = ord(mode[2 - i]) - 0x58
                        angle = node.delta_rotation_euler[axis]
                        if math.fabs(angle) > kExportEpsilon:
                            self.IndentWrite(B"Rotation (kind = \"", 0, structFlag)
                            self.Write(axisName[axis])
                            self.Write(B"\")\n")
                            self.IndentWrite(B"{\n")
                            self.IndentWrite(B"float {", 1)
                            self.WriteFloat(angle)
                            self.Write(B"}")
                            self.IndentWrite(B"}\n", 0, True)

                            structFlag = True

            if rotationAnimated:

                # When the rotation is animated, write three separate Euler angle rotations
                # so they can be targeted by different tracks having different sets of keys.

                for i in range(3):
                    axis = ord(mode[2 - i]) - 0x58
                    angle = node.rotation_euler[axis]
                    if (rotAnimated[axis]) or (math.fabs(angle) > kExportEpsilon):
                        self.IndentWrite(B"Rotation %", 0, structFlag)
                        self.Write(subrotationName[axis])
                        self.Write(B" (kind = \"")
                        self.Write(axisName[axis])
                        self.Write(B"\")\n")
                        self.IndentWrite(B"{\n")
                        self.IndentWrite(B"float {", 1)
                        self.WriteFloat(angle)
                        self.Write(B"}")
                        self.IndentWrite(B"}\n", 0, True)

                        structFlag = True

            else:

                # When the rotation is not animated, write it in the representation given by
                # the node's current rotation mode.

                if mode == "QUATERNION":
                    quaternion = node.rotation_quaternion
                    if ((math.fabs(quaternion[0] - 1.0) > kExportEpsilon) or (
                                math.fabs(quaternion[1]) > kExportEpsilon) or (
                                math.fabs(quaternion[2]) > kExportEpsilon) or (
                                math.fabs(quaternion[3]) > kExportEpsilon)):
                        self.IndentWrite(B"Rotation (kind = \"quaternion\")\n", 0, structFlag)
                        self.IndentWrite(B"{\n")
                        self.IndentWrite(B"float[4] {", 1)
                        self.WriteQuaternion(quaternion)
                        self.Write(B"}")
                        self.IndentWrite(B"}\n", 0, True)

                        structFlag = True

                elif mode == "AXIS_ANGLE":
                    if math.fabs(node.rotation_axis_angle[0]) > kExportEpsilon:
                        self.IndentWrite(B"Rotation (kind = \"axis\")\n", 0, structFlag)
                        self.IndentWrite(B"{\n")
                        self.IndentWrite(B"float[4] {", 1)
                        self.WriteVector4D(node.rotation_axis_angle)
                        self.Write(B"}")
                        self.IndentWrite(B"}\n", 0, True)

                        structFlag = True

                else:
                    for i in range(3):
                        axis = ord(mode[2 - i]) - 0x58
                        angle = node.rotation_euler[axis]
                        if math.fabs(angle) > kExportEpsilon:
                            self.IndentWrite(B"Rotation (kind = \"", 0, structFlag)
                            self.Write(axisName[axis])
                            self.Write(B"\")\n")
                            self.IndentWrite(B"{\n")
                            self.IndentWrite(B"float {", 1)
                            self.WriteFloat(angle)
                            self.Write(B"}")
                            self.IndentWrite(B"}\n", 0, True)

                            structFlag = True

            deltaScale = node.delta_scale
            if deltaScaleAnimated:

                # When the delta scale is animated, write the x, y, and z components separately
                # so they can be targeted by different tracks having different sets of keys.

                for i in range(3):
                    scl = deltaScale[i]
                    if (deltaSclAnimated[i]) or (math.fabs(scl) > kExportEpsilon):
                        self.IndentWrite(B"Scale %", 0, structFlag)
                        self.Write(deltaSubscaleName[i])
                        self.Write(B" (kind = \"")
                        self.Write(axisName[i])
                        self.Write(B"\")\n")
                        self.IndentWrite(B"{\n")
                        self.IndentWrite(B"float {", 1)
                        self.WriteFloat(scl)
                        self.Write(B"}")
                        self.IndentWrite(B"}\n", 0, True)

                        structFlag = True

            elif ((math.fabs(deltaScale[0] - 1.0) > kExportEpsilon) or (
                        math.fabs(deltaScale[1] - 1.0) > kExportEpsilon) or (
                        math.fabs(deltaScale[2] - 1.0) > kExportEpsilon)):
                self.IndentWrite(B"Scale\n", 0, structFlag)
                self.IndentWrite(B"{\n")
                self.IndentWrite(B"float[3] {", 1)
                self.WriteVector3D(deltaScale)
                self.Write(B"}")
                self.IndentWrite(B"}\n", 0, True)

                structFlag = True

            scale = node.scale
            if scaleAnimated:

                # When the scale is animated, write the x, y, and z components separately
                # so they can be targeted by different tracks having different sets of keys.

                for i in range(3):
                    scl = scale[i]
                    if (sclAnimated[i]) or (math.fabs(scl) > kExportEpsilon):
                        self.IndentWrite(B"Scale %", 0, structFlag)
                        self.Write(subscaleName[i])
                        self.Write(B" (kind = \"")
                        self.Write(axisName[i])
                        self.Write(B"\")\n")
                        self.IndentWrite(B"{\n")
                        self.IndentWrite(B"float {", 1)
                        self.WriteFloat(scl)
                        self.Write(B"}")
                        self.IndentWrite(B"}\n", 0, True)

                        structFlag = True

            elif ((math.fabs(scale[0] - 1.0) > kExportEpsilon) or (math.fabs(scale[1] - 1.0) > kExportEpsilon) or (
                        math.fabs(scale[2] - 1.0) > kExportEpsilon)):
                self.IndentWrite(B"Scale\n", 0, structFlag)
                self.IndentWrite(B"{\n")
                self.IndentWrite(B"float[3] {", 1)
                self.WriteVector3D(scale)
                self.Write(B"}")
                self.IndentWrite(B"}\n", 0, True)

                structFlag = True

            # Export the animation tracks.

            self.IndentWrite(B"Animation (begin = ", 0, True)
            self.WriteFloat((action.frame_range[0] - self.container.beginFrame) * self.container.frameTime)
            self.Write(B", end = ")
            self.WriteFloat((action.frame_range[1] - self.container.beginFrame) * self.container.frameTime)
            self.Write(B")\n")
            self.IndentWrite(B"{\n")
            self.container.indentLevel += 1

            structFlag = False

            if positionAnimated:
                for i in range(3):
                    if posAnimated[i]:
                        self.ExportAnimationTrack(posAnimCurve[i], posAnimKind[i], subtranslationName[i], structFlag)
                        structFlag = True

            if rotationAnimated:
                for i in range(3):
                    if rotAnimated[i]:
                        self.ExportAnimationTrack(rotAnimCurve[i], rotAnimKind[i], subrotationName[i], structFlag)
                        structFlag = True

            if scaleAnimated:
                for i in range(3):
                    if sclAnimated[i]:
                        self.ExportAnimationTrack(sclAnimCurve[i], sclAnimKind[i], subscaleName[i], structFlag)
                        structFlag = True

            if deltaPositionAnimated:
                for i in range(3):
                    if deltaPosAnimated[i]:
                        self.ExportAnimationTrack(deltaPosAnimCurve[i], deltaPosAnimKind[i], deltaSubtranslationName[i],
                                                  structFlag)
                        structFlag = True

            if deltaRotationAnimated:
                for i in range(3):
                    if deltaRotAnimated[i]:
                        self.ExportAnimationTrack(deltaRotAnimCurve[i], deltaRotAnimKind[i], deltaSubrotationName[i],
                                                  structFlag)
                        structFlag = True

            if deltaScaleAnimated:
                for i in range(3):
                    if deltaSclAnimated[i]:
                        self.ExportAnimationTrack(deltaSclAnimCurve[i], deltaSclAnimKind[i], deltaSubscaleName[i],
                                                  structFlag)
                        structFlag = True

            self.container.indentLevel -= 1
            self.IndentWrite(B"}\n")

    def handleOffset(self, matrix, offset):
        debug()
        if not offset:
            self.WriteMatrix(matrix)
            return

        line0 = (matrix[0][0], matrix[0][1], matrix[0][2], matrix[0][3] - offset[0])
        line1 = (matrix[1][0], matrix[1][1], matrix[1][2], matrix[1][3] - offset[1])
        line2 = (matrix[2][0], matrix[2][1], matrix[2][2], matrix[2][3] - offset[2])
        line3 = (matrix[3][0], matrix[3][1], matrix[3][2], matrix[3][3])

        matrix = (line0, line1, line2, line3)
        self.WriteMatrix(matrix)

    def ExportBoneTransform(self, nw, bw, scene):  # armature, bone, scene):
        debug()

        curveArray = self.CollectBoneAnimation(nw.item, bw.item.name)
        animation = ((len(curveArray) != 0) or self.container.sampleAnimationFlag)

        transform = bw.item.matrix_local.copy()
        parentBoneWrapper = bw.parent
        if parentBoneWrapper and (math.fabs(parentBoneWrapper.item.matrix_local.determinant()) > kExportEpsilon):
            transform = parentBoneWrapper.item.matrix_local.inverted() * transform

        poseBone = nw.item.pose.bones.get(bw.item.name)
        if poseBone:
            transform = poseBone.matrix.copy()
            parentPoseBone = poseBone.parent
            if parentPoseBone and (math.fabs(parentPoseBone.matrix.determinant()) > kExportEpsilon):
                transform = parentPoseBone.matrix.inverted() * transform

        self.IndentWrite(B"Transform")

        if animation:
            self.Write(B" %transform")

        self.IndentWrite(B"{\n", 0, True)
        self.container.indentLevel += 1

        self.IndentWrite(B"float[16]\n")
        self.IndentWrite(B"{\n")
        self.WriteMatrix(transform)
        self.IndentWrite(B"}\n")

        self.container.indentLevel -= 1
        self.IndentWrite(B"}\n")

        if animation and poseBone:
            self.ExportBoneSampledAnimation(poseBone, scene)

    def ExportMaterialRef(self, material, index):
        debug()
        if material not in self.container.materialArray:
            self.container.materialArray[material] = \
                {"structName": bytes("material" + str(len(self.container.materialArray) + 1), "UTF-8")}

        self.IndentWrite(B"MaterialRef (index = ")
        self.WriteInt(index)
        self.Write(B") {ref {$")
        self.Write(self.container.materialArray[material]["structName"])
        self.Write(B"}}\n")

    def ExportMorphWeights(self, node, shapeKeys, scene):
        debug()
        action = None
        curveArray = []
        indexArray = []

        if shapeKeys.animation_data:
            action = shapeKeys.animation_data.action
            if action:
                for fcurve in action.fcurves:
                    if (fcurve.data_path.startswith("key_blocks[")) and (fcurve.data_path.endswith("].value")):
                        keyName = fcurve.data_path.strip("abcdehklopstuvy[]_.")
                        if (keyName[0] == "\"") or (keyName[0] == "'"):
                            index = shapeKeys.key_blocks.find(keyName.strip("\"'"))
                            if index >= 0:
                                curveArray.append(fcurve)
                                indexArray.append(index)
                        else:
                            curveArray.append(fcurve)
                            indexArray.append(int(keyName))

        if (not action) and node.animation_data:
            action = node.animation_data.action
            if action:
                for fcurve in action.fcurves:
                    if ((fcurve.data_path.startswith("data.shape_keys.key_blocks[")) and (
                            fcurve.data_path.endswith("].value"))):
                        keyName = fcurve.data_path.strip("abcdehklopstuvy[]_.")
                        if (keyName[0] == "\"") or (keyName[0] == "'"):
                            index = shapeKeys.key_blocks.find(keyName.strip("\"'"))
                            if index >= 0:
                                curveArray.append(fcurve)
                                indexArray.append(index)
                        else:
                            curveArray.append(fcurve)
                            indexArray.append(int(keyName))

        animated = (len(curveArray) != 0)
        referenceName = shapeKeys.reference_key.name if shapeKeys.use_relative else ""

        for k in range(len(shapeKeys.key_blocks)):
            self.IndentWrite(B"MorphWeight", 0, (k == 0))

            if animated:
                self.Write(B" %mw")
                self.WriteInt(k)

            self.Write(B" (index = ")
            self.WriteInt(k)
            self.Write(B") {float {")

            block = shapeKeys.key_blocks[k]
            self.WriteFloat(block.value if (block.name != referenceName) else 1.0)

            self.Write(B"}}\n")

        if animated:
            self.IndentWrite(B"Animation (begin = ", 0, True)
            self.WriteFloat((action.frame_range[0] - self.container.beginFrame) * self.container.frameTime)
            self.Write(B", end = ")
            self.WriteFloat((action.frame_range[1] - self.container.beginFrame) * self.container.frameTime)
            self.Write(B")\n")
            self.IndentWrite(B"{\n")
            self.container.indentLevel += 1

            structFlag = False

            for a in range(len(curveArray)):
                k = indexArray[a]
                target = bytes("mw" + str(k), "UTF-8")

                fcurve = curveArray[a]
                kind = OpenGexExporter.ClassifyAnimationCurve(fcurve)
                if (kind != kAnimationSampled) and (not self.container.sampleAnimationFlag):
                    self.ExportAnimationTrack(fcurve, kind, target, structFlag)
                else:
                    self.ExportMorphWeightSampledAnimationTrack(shapeKeys.key_blocks[k], target, scene, structFlag)

                structFlag = True

            self.container.indentLevel -= 1
            self.IndentWrite(B"}\n")

    def ExportBone(self, nw, bw, scene):  # armature, bone, scene):
        debug()
        if nw.nodeRef:
            self.IndentWrite(structIdentifier[nw.nodeRef["nodeType"]], 0, True)
            self.Write(nw.nodeRef["structName"])

            self.IndentWrite(B"{\n", 0, True)
            self.container.indentLevel += 1

            name = bw.item.name
            if name != "":
                self.IndentWrite(B"Name {string {\"")
                self.Write(bytes(name, "UTF-8"))
                self.Write(B"\"}}\n\n")

            self.ExportBoneTransform(nw, bw, scene)

        for child in bw.children:
            self.ExportBone(nw, child, scene)

        # Export any ordinary nodes that are parented to this bone.

        boneSubnodeArray = self.container.boneParentArray.get(bw.item.name)
        if boneSubnodeArray:
            poseBone = None
            if not bw.item.use_relative_parent:
                poseBone = nw.item.pose.bones.get(bw.item.name)

            for subnodeWrapper in boneSubnodeArray:
                self.ExportNode(subnodeWrapper, scene, poseBone)

        if nw.nodeRef:
            self.container.indentLevel -= 1
            self.IndentWrite(B"}\n")

    def ExportNode(self, nw, scene, poseBone=None):
        debug()

        # This function exports a single node in the scene and includes its name,
        # object reference, material references (for geometries), and transform.
        # Subnodes are then exported recursively.

        if nw.nodeRef:
            type = nw.nodeRef["nodeType"]
            self.IndentWrite(structIdentifier[type], 0, True)
            self.Write(nw.nodeRef["structName"])

            if type == kNodeTypeGeometry:
                if nw.item.hide_render:
                    self.Write(B" (visible = false)")

            self.IndentWrite(B"{\n", 0, True)
            self.container.indentLevel += 1

            structFlag = False

            # Export the node's name if it has one.

            name = nw.item.name
            if name != "":
                self.IndentWrite(B"Name {string {\"")
                self.Write(bytes(name, "UTF-8"))
                self.Write(B"\"}}\n")
                structFlag = True

            # Export the object reference and material references.

            object = nw.item.data

            if type == kNodeTypeGeometry:
                if object not in self.container.geometryArray:
                    self.container.geometryArray[object] = {
                        "structName": bytes("geometry" + str(len(self.container.geometryArray) + 1), "UTF-8"),
                        "nodeTable": [nw.item]}
                else:
                    self.container.geometryArray[object]["nodeTable"].append(nw.item)

                self.IndentWrite(B"ObjectRef {ref {$")
                self.Write(self.container.geometryArray[object]["structName"])
                self.Write(B"}}\n")

                for i in range(len(nw.item.material_slots)):
                    self.ExportMaterialRef(nw.item.material_slots[i].material, i)

                shapeKeys = OpenGexExporter.GetShapeKeys(object)
                if shapeKeys:
                    # FIXME Wrapper or item?
                    self.ExportMorphWeights(nw.item, shapeKeys, scene)

                structFlag = True

            elif type == kNodeTypeLight:
                if object not in self.container.lightArray:
                    self.container.lightArray[object] = \
                        {"structName": bytes("light" + str(len(self.container.lightArray) + 1), "UTF-8"),
                         "nodeTable": [nw.item]}
                else:
                    self.container.lightArray[object]["nodeTable"].append(nw.item)

                self.IndentWrite(B"ObjectRef {ref {$")
                self.Write(self.container.lightArray[object]["structName"])
                self.Write(B"}}\n")
                structFlag = True

            elif type == kNodeTypeCamera:
                if object not in self.container.cameraArray:
                    self.container.cameraArray[object] = \
                        {"structName": bytes("camera" + str(len(self.container.cameraArray) + 1), "UTF-8"),
                         "nodeTable": [nw.item]}
                else:
                    self.container.cameraArray[object]["nodeTable"].append(nw.item)

                self.IndentWrite(B"ObjectRef {ref {$")
                self.Write(self.container.cameraArray[object]["structName"])
                self.Write(B"}}\n")
                structFlag = True

            if structFlag:
                self.Write(B"\n")

            if poseBone:
                # If the node is parented to a bone and is not relative, then undo the bone's transform.

                if math.fabs(poseBone.matrix.determinant()) > kExportEpsilon:
                    self.IndentWrite(B"Transform\n")
                    self.IndentWrite(B"{\n")
                    self.container.indentLevel += 1

                    self.IndentWrite(B"float[16]\n")
                    self.IndentWrite(B"{\n")
                    self.WriteMatrix(poseBone.matrix.inverted())
                    self.IndentWrite(B"}\n")

                    self.container.indentLevel -= 1
                    self.IndentWrite(B"}\n\n")

            # Export the transform. If the node is animated, then animation tracks are exported here.

            self.ExportNodeTransform(nw, scene)

            if nw.bones:
                for bw in nw.bones:
                    self.ExportBone(nw, bw, scene)

        for subnode in nw.children:
            if subnode.parent.item.type != "BONE":
                self.ExportNode(subnode, scene)

        if nw.nodeRef:
            self.container.indentLevel -= 1
            self.IndentWrite(B"}\n")

    def ExportSkin(self, node, armature, exportVertexArray):
        debug()

        # This function exports all skinning data, which includes the skeleton
        # and per-vertex bone influence data.

        self.IndentWrite(B"Skin\n", 0, True)
        self.IndentWrite(B"{\n")
        self.container.indentLevel += 1

        # Write the skin bind pose transform.

        self.IndentWrite(B"Transform\n")
        self.IndentWrite(B"{\n")
        self.container.indentLevel += 1

        self.IndentWrite(B"float[16]\n")
        self.IndentWrite(B"{\n")
        self.WriteMatrix(node.matrix_world)
        self.IndentWrite(B"}\n")

        self.container.indentLevel -= 1
        self.IndentWrite(B"}\n\n")

        # Export the skeleton, which includes an array of bone node references
        # and and array of per-bone bind pose transforms.

        self.IndentWrite(B"Skeleton\n")
        self.IndentWrite(B"{\n")
        self.container.indentLevel += 1

        # Write the bone node reference array.

        self.IndentWrite(B"BoneRefArray\n")
        self.IndentWrite(B"{\n")
        self.container.indentLevel += 1

        boneArray = armature.data.bones
        boneCount = len(boneArray)

        self.IndentWrite(B"ref\t\t\t// ")
        self.WriteInt(boneCount)
        self.IndentWrite(B"{\n", 0, True)
        self.IndentWrite(B"", 1)

        for i in range(boneCount):
            boneRef = self.FindNode(boneArray[i].name)
            if boneRef:
                self.Write(B"$")
                self.Write(boneRef[1]["structName"])
            else:
                self.Write(B"null")

            if i < boneCount - 1:
                self.Write(B", ")
            else:
                self.Write(B"\n")

        self.IndentWrite(B"}\n")

        self.container.indentLevel -= 1
        self.IndentWrite(B"}\n\n")

        # Write the bind pose transform array.

        self.IndentWrite(B"Transform\n")
        self.IndentWrite(B"{\n")
        self.container.indentLevel += 1

        self.IndentWrite(B"float[16]\t// ")
        self.WriteInt(boneCount)
        self.IndentWrite(B"{\n", 0, True)

        for i in range(boneCount):
            self.WriteMatrixFlat(armature.matrix_world * boneArray[i].matrix_local)
            if i < boneCount - 1:
                self.Write(B",\n")

        self.IndentWrite(B"}\n", 0, True)

        self.container.indentLevel -= 1
        self.IndentWrite(B"}\n")

        self.container.indentLevel -= 1
        self.IndentWrite(B"}\n\n")

        # Export the per-vertex bone influence data.

        groupRemap = []

        for group in node.vertex_groups:
            groupName = group.name
            for i in range(boneCount):
                if boneArray[i].name == groupName:
                    groupRemap.append(i)
                    break
            else:
                groupRemap.append(-1)

        boneCountArray = []
        boneIndexArray = []
        boneWeightArray = []

        meshVertexArray = node.data.vertices
        for ev in exportVertexArray:
            boneCount = 0
            totalWeight = 0.0
            for element in meshVertexArray[ev.vertexIndex].groups:
                boneIndex = groupRemap[element.group]
                boneWeight = element.weight
                if (boneIndex >= 0) and (boneWeight != 0.0):
                    boneCount += 1
                    totalWeight += boneWeight
                    boneIndexArray.append(boneIndex)
                    boneWeightArray.append(boneWeight)
            boneCountArray.append(boneCount)

            if totalWeight != 0.0:
                normalizer = 1.0 / totalWeight
                for i in range(-boneCount, 0):
                    boneWeightArray[i] *= normalizer

        # Write the bone count array. There is one entry per vertex.

        self.IndentWrite(B"BoneCountArray\n")
        self.IndentWrite(B"{\n")
        self.container.indentLevel += 1

        self.IndentWrite(B"unsigned_int16\t\t// ")
        self.WriteInt(len(boneCountArray))
        self.IndentWrite(B"{\n", 0, True)
        self.WriteIntArray(boneCountArray)
        self.IndentWrite(B"}\n")

        self.container.indentLevel -= 1
        self.IndentWrite(B"}\n\n")

        # Write the bone index array. The number of entries is the sum of the bone counts for all vertices.

        self.IndentWrite(B"BoneIndexArray\n")
        self.IndentWrite(B"{\n")
        self.container.indentLevel += 1

        self.IndentWrite(B"unsigned_int16\t\t// ")
        self.WriteInt(len(boneIndexArray))
        self.IndentWrite(B"{\n", 0, True)
        self.WriteIntArray(boneIndexArray)
        self.IndentWrite(B"}\n")

        self.container.indentLevel -= 1
        self.IndentWrite(B"}\n\n")

        # Write the bone weight array. The number of entries is the sum of the bone counts for all vertices.

        self.IndentWrite(B"BoneWeightArray\n")
        self.IndentWrite(B"{\n")
        self.container.indentLevel += 1

        self.IndentWrite(B"float\t\t// ")
        self.WriteInt(len(boneWeightArray))
        self.IndentWrite(B"{\n", 0, True)
        self.WriteFloatArray(boneWeightArray)
        self.IndentWrite(B"}\n")

        self.container.indentLevel -= 1
        self.IndentWrite(B"}\n")

        self.container.indentLevel -= 1
        self.IndentWrite(B"}\n")

    def ExportGeometry(self, objectRef, scene):
        debug()

        # This function exports a single geometry object.

        self.Write(B"\nGeometryObject $")
        self.Write(objectRef[1]["structName"])
        self.WriteNodeTable(objectRef)

        self.Write(B"\n{\n")
        self.container.indentLevel += 1

        node = objectRef[1]["nodeTable"][0]
        mesh = objectRef[0]

        structFlag = False

        # Save the morph state if necessary.

        activeShapeKeyIndex = node.active_shape_key_index
        showOnlyShapeKey = node.show_only_shape_key
        currentMorphValue = []

        shapeKeys = OpenGexExporter.GetShapeKeys(mesh)
        if shapeKeys:
            node.active_shape_key_index = 0
            node.show_only_shape_key = True

            baseIndex = 0
            relative = shapeKeys.use_relative
            if relative:
                morphCount = 0
                baseName = shapeKeys.reference_key.name
                for block in shapeKeys.key_blocks:
                    if block.name == baseName:
                        baseIndex = morphCount
                        break
                    morphCount += 1

            morphCount = 0
            for block in shapeKeys.key_blocks:
                currentMorphValue.append(block.value)
                block.value = 0.0

                if block.name != "":
                    self.IndentWrite(B"Morph (index = ", 0, structFlag)
                    self.WriteInt(morphCount)

                    if relative and (morphCount != baseIndex):
                        self.Write(B", base = ")
                        self.WriteInt(baseIndex)

                    self.Write(B")\n")
                    self.IndentWrite(B"{\n")
                    self.IndentWrite(B"Name {string {\"", 1)
                    self.Write(bytes(block.name, "UTF-8"))
                    self.Write(B"\"}}\n")
                    self.IndentWrite(B"}\n")
                    structFlag = True

                morphCount += 1

            shapeKeys.key_blocks[0].value = 1.0
            mesh.update()

        self.IndentWrite(B"Mesh (primitive = \"triangles\")\n", 0, structFlag)
        self.IndentWrite(B"{\n")
        self.container.indentLevel += 1

        armature = node.find_armature()
        applyModifiers = (not armature)

        # Apply all modifiers to create a new mesh with tessfaces.

        # We don't apply modifiers for a skinned mesh because we need the vertex positions
        # before they are deformed by the armature modifier in order to export the proper
        # bind pose. This does mean that modifiers preceding the armature modifier are ignored,
        # but the Blender API does not provide a reasonable way to retrieve the mesh at an
        # arbitrary stage in the modifier stack.

        exportMesh = node.to_mesh(scene, applyModifiers, "RENDER", True, False)

        # Triangulate mesh and remap vertices to eliminate duplicates.

        materialTable = []
        exportVertexArray = OpenGexExporter.DeindexMesh(exportMesh, materialTable)
        triangleCount = len(materialTable)

        indexTable = []
        unifiedVertexArray = OpenGexExporter.UnifyVertices(exportVertexArray, indexTable)
        vertexCount = len(unifiedVertexArray)

        # Write the position array.

        self.IndentWrite(B"VertexArray (attrib = \"position\")\n")
        self.IndentWrite(B"{\n")
        self.container.indentLevel += 1

        self.IndentWrite(B"float[3]\t\t// ")
        self.WriteInt(vertexCount)
        self.IndentWrite(B"{\n", 0, True)
        self.WriteVertexArray3D(unifiedVertexArray, "position")
        self.IndentWrite(B"}\n")

        self.container.indentLevel -= 1
        self.IndentWrite(B"}\n\n")

        # Write the normal array.

        self.IndentWrite(B"VertexArray (attrib = \"normal\")\n")
        self.IndentWrite(B"{\n")
        self.container.indentLevel += 1

        self.IndentWrite(B"float[3]\t\t// ")
        self.WriteInt(vertexCount)
        self.IndentWrite(B"{\n", 0, True)
        self.WriteVertexArray3D(unifiedVertexArray, "normal")
        self.IndentWrite(B"}\n")

        self.container.indentLevel -= 1
        self.IndentWrite(B"}\n")

        # Write the color array if it exists.

        colorCount = len(exportMesh.tessface_vertex_colors)
        if colorCount > 0:
            self.IndentWrite(B"VertexArray (attrib = \"color\")\n", 0, True)
            self.IndentWrite(B"{\n")
            self.container.indentLevel += 1

            self.IndentWrite(B"float[3]\t\t// ")
            self.WriteInt(vertexCount)
            self.IndentWrite(B"{\n", 0, True)
            self.WriteVertexArray3D(unifiedVertexArray, "color")
            self.IndentWrite(B"}\n")

            self.container.indentLevel -= 1
            self.IndentWrite(B"}\n")

        # Write the texcoord arrays.
        count = 0
        for i in range(len(exportMesh.uv_textures)):
            if exportMesh.uv_textures[i].active_render:
                name = B'texcoord'
                if count > 0:
                    name += B'[' + bytes(str(count)) + B']'
                self.IndentWrite(B"VertexArray (attrib = \"" + name + B"\")\n", 0, True)
                self.IndentWrite(B"{\n")
                self.container.indentLevel += 1
                self.IndentWrite(B"float[2]\t\t// ")
                self.WriteInt(vertexCount)
                self.IndentWrite(B"{\n", 0, True)
                self.WriteVertexArray2D(unifiedVertexArray, "texcoord" + str(count))
                self.IndentWrite(B"}\n")
                
                self.container.indentLevel -= 1
                self.IndentWrite(B"}\n")
                
                count += 1
                
                if count > 2:
                    break

        # If there are multiple morph targets, export them here.

        if shapeKeys:
            shapeKeys.key_blocks[0].value = 0.0
            for m in range(1, len(currentMorphValue)):
                shapeKeys.key_blocks[m].value = 1.0
                mesh.update()

                node.active_shape_key_index = m
                morphMesh = node.to_mesh(scene, applyModifiers, "RENDER", True, False)

                # Write the morph target position array.

                self.IndentWrite(B"VertexArray (attrib = \"position\", morph = ", 0, True)
                self.WriteInt(m)
                self.Write(B")\n")
                self.IndentWrite(B"{\n")
                self.container.indentLevel += 1

                self.IndentWrite(B"float[3]\t\t// ")
                self.WriteInt(vertexCount)
                self.IndentWrite(B"{\n", 0, True)
                self.WriteMorphPositionArray3D(unifiedVertexArray, morphMesh.vertices)
                self.IndentWrite(B"}\n")

                self.container.indentLevel -= 1
                self.IndentWrite(B"}\n\n")

                # Write the morph target normal array.

                self.IndentWrite(B"VertexArray (attrib = \"normal\", morph = ")
                self.WriteInt(m)
                self.Write(B")\n")
                self.IndentWrite(B"{\n")
                self.container.indentLevel += 1

                self.IndentWrite(B"float[3]\t\t// ")
                self.WriteInt(vertexCount)
                self.IndentWrite(B"{\n", 0, True)
                self.WriteMorphNormalArray3D(unifiedVertexArray, morphMesh.vertices, morphMesh.tessfaces)
                self.IndentWrite(B"}\n")

                self.container.indentLevel -= 1
                self.IndentWrite(B"}\n")

                bpy.data.meshes.remove(morphMesh)

        # Write the index arrays.

        maxMaterialIndex = 0
        for i in range(len(materialTable)):
            index = materialTable[i]
            if index > maxMaterialIndex:
                maxMaterialIndex = index

        if maxMaterialIndex == 0:

            # There is only one material, so write a single index array.

            self.IndentWrite(B"IndexArray\n", 0, True)
            self.IndentWrite(B"{\n")
            self.container.indentLevel += 1

            self.IndentWrite(B"unsigned_int32[3]\t\t// ")
            self.WriteInt(triangleCount)
            self.IndentWrite(B"{\n", 0, True)
            self.WriteTriangleArray(triangleCount, indexTable)
            self.IndentWrite(B"}\n")

            self.container.indentLevel -= 1
            self.IndentWrite(B"}\n")

        else:

            # If there are multiple material indexes, then write a separate index array for each one.

            materialTriangleCount = [0 for i in range(maxMaterialIndex + 1)]
            for i in range(len(materialTable)):
                materialTriangleCount[materialTable[i]] += 1

            for m in range(maxMaterialIndex + 1):
                if materialTriangleCount[m] != 0:
                    materialIndexTable = []
                    for i in range(len(materialTable)):
                        if materialTable[i] == m:
                            k = i * 3
                            materialIndexTable.append(indexTable[k])
                            materialIndexTable.append(indexTable[k + 1])
                            materialIndexTable.append(indexTable[k + 2])

                    self.IndentWrite(B"IndexArray (material = ", 0, True)
                    self.WriteInt(m)
                    self.Write(B")\n")
                    self.IndentWrite(B"{\n")
                    self.container.indentLevel += 1

                    self.IndentWrite(B"unsigned_int32[3]\t\t// ")
                    self.WriteInt(materialTriangleCount[m])
                    self.IndentWrite(B"{\n", 0, True)
                    self.WriteTriangleArray(materialTriangleCount[m], materialIndexTable)
                    self.IndentWrite(B"}\n")

                    self.container.indentLevel -= 1
                    self.IndentWrite(B"}\n")

        # If the mesh is skinned, export the skinning data here.

        if armature:
            self.ExportSkin(node, armature, unifiedVertexArray)

        # Restore the morph state.

        if shapeKeys:
            node.active_shape_key_index = activeShapeKeyIndex
            node.show_only_shape_key = showOnlyShapeKey

            for m in range(len(currentMorphValue)):
                shapeKeys.key_blocks[m].value = currentMorphValue[m]

            mesh.update()

        # Delete the new mesh that we made earlier.

        bpy.data.meshes.remove(exportMesh)

        self.container.indentLevel -= 1
        self.IndentWrite(B"}\n")

        self.container.indentLevel -= 1
        self.Write(B"}\n")

    def ExportLight(self, objectRef):
        debug()

        # This function exports a single light object.

        self.Write(B"\nLightObject $")
        self.Write(objectRef[1]["structName"])

        object = objectRef[0]
        type = object.type

        self.Write(B" (type = ")
        pointFlag = False
        spotFlag = False

        if type == "SUN":
            self.Write(B"\"infinite\"")
        elif type == "POINT":
            self.Write(B"\"point\"")
            pointFlag = True
        else:
            self.Write(B"\"spot\"")
            pointFlag = True
            spotFlag = True

        if not object.use_shadow:
            self.Write(B", shadow = false")

        self.Write(B")")
        self.WriteNodeTable(objectRef)

        self.Write(B"\n{\n")
        self.container.indentLevel += 1

        # Export the light's color, and include a separate intensity if necessary.

        self.IndentWrite(B"Color (attrib = \"light\") {float[3] {")
        self.WriteColor(object.color)
        self.Write(B"}}\n")

        intensity = object.energy
        if intensity != 1.0:
            self.IndentWrite(B"Param (attrib = \"intensity\") {float {")
            self.WriteFloat(intensity)
            self.Write(B"}}\n")

        if pointFlag:

            # Export a separate attenuation function for each type that's in use.

            falloff = object.falloff_type

            if falloff == "INVERSE_LINEAR":
                self.IndentWrite(B"Atten (curve = \"inverse\")\n", 0, True)
                self.IndentWrite(B"{\n")

                self.IndentWrite(B"Param (attrib = \"scale\") {float {", 1)
                self.WriteFloat(object.distance)
                self.Write(B"}}\n")

                self.IndentWrite(B"}\n")

            elif falloff == "INVERSE_SQUARE":
                self.IndentWrite(B"Atten (curve = \"inverse_square\")\n", 0, True)
                self.IndentWrite(B"{\n")

                self.IndentWrite(B"Param (attrib = \"scale\") {float {", 1)
                self.WriteFloat(math.sqrt(object.distance))
                self.Write(B"}}\n")

                self.IndentWrite(B"}\n")

            elif falloff == "LINEAR_QUADRATIC_WEIGHTED":
                if object.linear_attenuation != 0.0:
                    self.IndentWrite(B"Atten (curve = \"inverse\")\n", 0, True)
                    self.IndentWrite(B"{\n")

                    self.IndentWrite(B"Param (attrib = \"scale\") {float {", 1)
                    self.WriteFloat(object.distance)
                    self.Write(B"}}\n")

                    self.IndentWrite(B"Param (attrib = \"constant\") {float {", 1)
                    self.WriteFloat(1.0)
                    self.Write(B"}}\n")

                    self.IndentWrite(B"Param (attrib = \"linear\") {float {", 1)
                    self.WriteFloat(object.linear_attenuation)
                    self.Write(B"}}\n")

                    self.IndentWrite(B"}\n\n")

                if object.quadratic_attenuation != 0.0:
                    self.IndentWrite(B"Atten (curve = \"inverse_square\")\n")
                    self.IndentWrite(B"{\n")

                    self.IndentWrite(B"Param (attrib = \"scale\") {float {", 1)
                    self.WriteFloat(object.distance)
                    self.Write(B"}}\n")

                    self.IndentWrite(B"Param (attrib = \"constant\") {float {", 1)
                    self.WriteFloat(1.0)
                    self.Write(B"}}\n")

                    self.IndentWrite(B"Param (attrib = \"quadratic\") {float {", 1)
                    self.WriteFloat(object.quadratic_attenuation)
                    self.Write(B"}}\n")

                    self.IndentWrite(B"}\n")

            if object.use_sphere:
                self.IndentWrite(B"Atten (curve = \"linear\")\n", 0, True)
                self.IndentWrite(B"{\n")

                self.IndentWrite(B"Param (attrib = \"end\") {float {", 1)
                self.WriteFloat(object.distance)
                self.Write(B"}}\n")

                self.IndentWrite(B"}\n")

            if spotFlag:
                # Export additional angular attenuation for spot lights.

                self.IndentWrite(B"Atten (kind = \"angle\", curve = \"linear\")\n", 0, True)
                self.IndentWrite(B"{\n")

                endAngle = object.spot_size * 0.5
                beginAngle = endAngle * (1.0 - object.spot_blend)

                self.IndentWrite(B"Param (attrib = \"begin\") {float {", 1)
                self.WriteFloat(beginAngle)
                self.Write(B"}}\n")

                self.IndentWrite(B"Param (attrib = \"end\") {float {", 1)
                self.WriteFloat(endAngle)
                self.Write(B"}}\n")

                self.IndentWrite(B"}\n")

        self.container.indentLevel -= 1
        self.Write(B"}\n")

    def ExportCamera(self, objectRef):
        debug()

        # This function exports a single camera object.

        self.Write(B"\nCameraObject $")
        self.Write(objectRef[1]["structName"])
        self.WriteNodeTable(objectRef)

        self.Write(B"\n{\n")
        self.container.indentLevel += 1

        object = objectRef[0]

        self.IndentWrite(B"Param (attrib = \"fov\") {float {")
        self.WriteFloat(object.angle_x)
        self.Write(B"}}\n")

        self.IndentWrite(B"Param (attrib = \"near\") {float {")
        self.WriteFloat(object.clip_start)
        self.Write(B"}}\n")

        self.IndentWrite(B"Param (attrib = \"far\") {float {")
        self.WriteFloat(object.clip_end)
        self.Write(B"}}\n")

        self.container.indentLevel -= 1
        self.Write(B"}\n")

    def ExportObjects(self, scene):
        debug()
        for objectRef in self.container.geometryArray.items():
            self.ExportGeometry(objectRef, scene)
        for objectRef in self.container.lightArray.items():
            self.ExportLight(objectRef)
        for objectRef in self.container.cameraArray.items():
            self.ExportCamera(objectRef)

    def ExportTexture(self, textureSlot, attrib):
        debug()

        # This function exports a single texture from a material.

        self.IndentWrite(B"Texture (attrib = \"", 0, True)
        self.Write(attrib)
        self.Write(B"\")\n")

        self.IndentWrite(B"{\n")
        self.container.indentLevel += 1

        self.IndentWrite(B"string {\"")
        self.WriteFileName(textureSlot.texture.image.filepath)
        self.Write(B"\"}\n")

        # If the texture has a scale and/or offset, then export a coordinate transform.

        uscale = textureSlot.scale[0]
        vscale = textureSlot.scale[1]
        uoffset = textureSlot.offset[0]
        voffset = textureSlot.offset[1]

        if (uscale != 1.0) or (vscale != 1.0) or (uoffset != 0.0) or (voffset != 0.0):
            matrix = [[uscale, 0.0, 0.0, 0.0], [0.0, vscale, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0],
                      [uoffset, voffset, 0.0, 1.0]]

            self.IndentWrite(B"Transform\n", 0, True)
            self.IndentWrite(B"{\n")
            self.container.indentLevel += 1

            self.IndentWrite(B"float[16]\n")
            self.IndentWrite(B"{\n")
            self.WriteMatrix(matrix)
            self.IndentWrite(B"}\n")

            self.container.indentLevel -= 1
            self.IndentWrite(B"}\n")

        self.container.indentLevel -= 1
        self.IndentWrite(B"}\n")

    def ExportMaterials(self):
        debug()

        # This function exports all of the materials used in the scene.

        for materialRef in self.container.materialArray.items():
            material = materialRef[0]

            self.Write(B"\nMaterial $")
            self.Write(materialRef[1]["structName"])
            self.Write(B"\n{\n")
            self.container.indentLevel += 1

            if material.name != "":
                self.IndentWrite(B"Name {string {\"")
                self.Write(bytes(material.name, "UTF-8"))
                self.Write(B"\"}}\n\n")

            intensity = material.diffuse_intensity
            diffuse = [material.diffuse_color[0] * intensity, material.diffuse_color[1] * intensity,
                       material.diffuse_color[2] * intensity]

            self.IndentWrite(B"Color (attrib = \"diffuse\") {float[3] {")
            self.WriteColor(diffuse)
            self.Write(B"}}\n")

            intensity = material.specular_intensity
            specular = [material.specular_color[0] * intensity, material.specular_color[1] * intensity,
                        material.specular_color[2] * intensity]

            if (specular[0] > 0.0) or (specular[1] > 0.0) or (specular[2] > 0.0):
                self.IndentWrite(B"Color (attrib = \"specular\") {float[3] {")
                self.WriteColor(specular)
                self.Write(B"}}\n")

                self.IndentWrite(B"Param (attrib = \"specular_power\") {float {")
                self.WriteFloat(material.specular_hardness)
                self.Write(B"}}\n")

            emission = material.emit
            if emission > 0.0:
                self.IndentWrite(B"Color (attrib = \"emission\") {float[3] {")
                self.WriteColor([emission, emission, emission])
                self.Write(B"}}\n")

            diffuseTexture = None
            specularTexture = None
            emissionTexture = None
            transparencyTexture = None
            normalTexture = None

            for textureSlot in material.texture_slots:
                if textureSlot and textureSlot.use and (textureSlot.texture.type == "IMAGE"):
                    if (textureSlot.use_map_color_diffuse or textureSlot.use_map_diffuse and (
                            not diffuseTexture)):
                        diffuseTexture = textureSlot
                    elif (
                                textureSlot.use_map_color_spec or textureSlot.use_map_specular and (
                                    not specularTexture)):
                        specularTexture = textureSlot
                    elif textureSlot.use_map_emit and (not emissionTexture):
                        emissionTexture = textureSlot
                    elif textureSlot.use_map_translucency and (not transparencyTexture):
                        transparencyTexture = textureSlot
                    elif textureSlot.use_map_normal and (not normalTexture):
                        normalTexture = textureSlot

            if diffuseTexture:
                self.ExportTexture(diffuseTexture, B"diffuse")
            if specularTexture:
                self.ExportTexture(specularTexture, B"specular")
            if emissionTexture:
                self.ExportTexture(emissionTexture, B"emission")
            if transparencyTexture:
                self.ExportTexture(transparencyTexture, B"transparency")
            if normalTexture:
                self.ExportTexture(normalTexture, B"normal")

            self.container.indentLevel -= 1
            self.Write(B"}\n")

    def ExportMetrics(self, scene):
        debug()
        scale = scene.unit_settings.scale_length

        if scene.unit_settings.system == "IMPERIAL":
            scale *= 0.3048

        self.Write(B"Metric (key = \"distance\") {float {")
        self.WriteFloat(scale)
        self.Write(B"}}\n")

        self.Write(B"Metric (key = \"angle\") {float {1.0}}\n")
        self.Write(B"Metric (key = \"time\") {float {1.0}}\n")
        self.Write(B"Metric (key = \"up\") {string {\"z\"}}\n")

    def getChildrenForNode(self, node):
        debug()
        if node in self.nodeChildren:
            return self.nodeChildren[node]
        else:
            return node.children

    def processSkinnedMeshes(self):
        debug()
        for nw in self.container.nodes:
            if nw.nodeRef["nodeType"] == kNodeTypeGeometry:
                armature = nw.item.find_armature()
                if armature:
                    for bone in armature.data.bones:
                        boneRef = self.container.findNodeWrapperByName(bone.name)
                        if boneRef:
                            # If a node is used as a bone, then we force its type to be a bone.
                            boneRef.dict["nodeType"] = kNodeTypeBone

    def execute(self, context):
        debug()

        scene = context.scene
        exportAllFlag = not self.option_export_selection
        file = open(self.filepath, "wb")
        self.container = FlagContainer(exportAllFlag, self.option_sample_animation, scene, file)

        self.ExportMetrics(scene)

        originalFrame = scene.frame_current
        originalSubframe = scene.frame_subframe

        for obj in scene.objects:
            if not obj.parent:
                NodeWrapper(obj, self.container)

        self.processSkinnedMeshes()

        for obj in self.container.nodes:
            if not obj.parent:
                self.ExportNode(obj, scene)

        self.ExportObjects(scene)
        self.ExportMaterials()

        restoreFrame = False
        if restoreFrame:
            scene.frame_set(originalFrame, originalSubframe)

        file.close()
        return {'FINISHED'}
