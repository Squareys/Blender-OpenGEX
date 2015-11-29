__author__ = 'Eric Lengyel, aullik, Jonathan Hale'

from blenderOpenGEX.FlagContainer import *
from blenderOpenGEX.NodeWrapper import NodeWrapper
from blenderOpenGEX.ExportVertex import ExportVertex
from blenderOpenGEX.Writer import Writer
from blenderOpenGEX import debug
import bpy
import math
import time
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


class ProgressLog:

    def __init__(self):
        self.lastTime = 0
        pass

    def begin_task(self, message):
        print(message, end="", flush=True)
        self.lastTime = time.time()

    def end_task(self):
        print(" done! ({:.2f} ms)".format((time.time() - self.lastTime) * 1000))


class OpenGexExporter(bpy.types.Operator, ExportHelper, Writer):
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
        self.progress = ProgressLog()

    @staticmethod
    def get_shape_keys(mesh):
        debug()
        shapeKeys = mesh.shape_keys
        if shapeKeys and (len(shapeKeys.key_blocks) > 1):
            return shapeKeys

        return None

    def find_node(self, name):
        debug()
        for nodeRef in self.nodeArray.items():
            if nodeRef[0].name == name:
                return nodeRef
        return None

    # TODO: We can probably do without this method:
    @staticmethod
    def deindex_mesh(mesh, materialTable):
        debug()

        # This function deindexes all vertex positions, colors, and texcoords.
        # Three separate ExportVertex structures are created for each triangle.

        vertexArray = mesh.vertices
        exportVertexArray = []
        faceIndex = 0

        for face in mesh.tessfaces:

            list = [0, 1, 2]
            materialTable.append(face.material_index)

            if len(face.vertices) == 4:
                list = list + [0, 2, 3]
                materialTable.append(face.material_index)

            for i in list:
                vertex_index = face.vertices[i]
                vertex = vertexArray[vertex_index]

                exportVertex = ExportVertex()
                exportVertex.vertexIndex = vertex_index
                exportVertex.faceIndex = faceIndex
                exportVertex.position = vertex.co
                exportVertex.normal = vertex.normal if face.use_smooth else face.normal
                exportVertexArray.append(exportVertex)

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

        for texCoordIndex in range(0, texcoordCount):
            texcoord_attrib = "texcoord" + str(texCoordIndex)

            texcoordFace = active_tessface_uv_textures[texCoordIndex].data
            vertexIndex = 0
            faceIndex = 0

            for face in mesh.tessfaces:
                tf = texcoordFace[faceIndex]

                uvs = [tf.uv1, tf.uv2, tf.uv3]
                if len(face.vertices) == 4:
                    uvs = uvs + [tf.uv1, tf.uv3, tf.uv4]

                for uv in uvs:
                    setattr(exportVertexArray[vertexIndex], texcoord_attrib, uv)
                    vertexIndex += 1

                faceIndex += 1

        for ev in exportVertexArray:
            ev.get_hash()

        return exportVertexArray

    @staticmethod
    def find_export_vertex(bucket, exportVertexArray, vertex):
        debug()
        for index in bucket:
            if exportVertexArray[index] == vertex:
                return index

        return -1

    @staticmethod
    def unify_vertices(exportVertexArray, indexTable):
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
            bucket = ev.get_hash & (bucketCount - 1)
            index = OpenGexExporter.find_export_vertex(hashTable[bucket], exportVertexArray, ev)
            if index < 0:
                indexTable.append(len(unifiedVertexArray))
                unifiedVertexArray.append(ev)
                hashTable[bucket].append(i)
            else:
                indexTable.append(indexTable[index])

        return unifiedVertexArray

    @staticmethod
    def classify_animation_curve(fcurve):
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
    def animation_keys_differ(fcurve):
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
    def animation_tangents_nonzero(fcurve):
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
    def animation_present(fcurve, kind):
        debug()
        if kind != kAnimationBezier:
            return OpenGexExporter.animation_keys_differ(fcurve)

        return (OpenGexExporter.animation_keys_differ(fcurve)) or (OpenGexExporter.animation_tangents_nonzero(fcurve))

    @staticmethod
    def matrices_differ(m1, m2):
        debug()
        for i in range(4):
            for j in range(4):
                if math.fabs(m1[i][j] - m2[i][j]) > kExportEpsilon:
                    return True

        return False

    @staticmethod
    def export_bone_animation(armature, name):
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

    def export_key_times(self, fcurve):
        debug()
        self.IndentWrite(B"Key {float {")

        keyCount = len(fcurve.keyframe_points)
        for i in range(keyCount):
            if i > 0:
                self.file.write(B", ")

            time = fcurve.keyframe_points[i].co[0] - self.container.beginFrame
            self.WriteFloat(time * self.container.frameTime)

        self.file.write(B"}}\n")

    def export_key_time_control_points(self, fcurve):
        debug()
        self.IndentWrite(B"Key (kind = \"-control\") {float {")

        keyCount = len(fcurve.keyframe_points)
        for i in range(keyCount):
            if i > 0:
                self.file.write(B", ")

            ctrl = fcurve.keyframe_points[i].handle_left[0] - self.container.beginFrame
            self.WriteFloat(ctrl * self.container.frameTime)

        self.file.write(B"}}\n")
        self.IndentWrite(B"Key (kind = \"+control\") {float {")

        for i in range(keyCount):
            if i > 0:
                self.file.write(B", ")

            ctrl = fcurve.keyframe_points[i].handle_right[0] - self.container.beginFrame
            self.WriteFloat(ctrl * self.container.frameTime)

        self.file.write(B"}}\n")

    def export_key_values(self, fcurve):
        debug()
        self.IndentWrite(B"Key {float {")

        keyCount = len(fcurve.keyframe_points)
        for i in range(keyCount):
            if i > 0:
                self.file.write(B", ")

            value = fcurve.keyframe_points[i].co[1]
            self.WriteFloat(value)

        self.file.write(B"}}\n")

    def export_key_value_control_points(self, fcurve):
        debug()
        self.IndentWrite(B"Key (kind = \"-control\") {float {")

        keyCount = len(fcurve.keyframe_points)
        for i in range(keyCount):
            if i > 0:
                self.file.write(B", ")

            ctrl = fcurve.keyframe_points[i].handle_left[1]
            self.WriteFloat(ctrl)

        self.file.write(B"}}\n")
        self.IndentWrite(B"Key (kind = \"+control\") {float {")

        for i in range(keyCount):
            if i > 0:
                self.file.write(B", ")

            ctrl = fcurve.keyframe_points[i].handle_right[1]
            self.WriteFloat(ctrl)

        self.file.write(B"}}\n")

    def export_animation_track(self, fcurve, kind, target, newline):
        debug()

        # This function exports a single animation track. The curve types for the
        # Time and Value structures are given by the kind parameter.

        self.IndentWrite(B"Track (target = %", 0, newline)
        self.file.write(target)
        self.file.write(B")\n")
        self.IndentWrite(B"{\n")
        self.IncIndent()

        if kind != kAnimationBezier:
            self.IndentWrite(B"Time\n")
            self.IndentWrite(B"{\n")
            self.IncIndent()

            self.export_key_times(fcurve)

            self.IndentWrite(B"}\n\n", -1)
            self.IndentWrite(B"Value\n", -1)
            self.IndentWrite(B"{\n", -1)

            self.export_key_values(fcurve)

            self.DecIndent()
            self.IndentWrite(B"}\n")

        else:
            self.IndentWrite(B"Time (curve = \"bezier\")\n")
            self.IndentWrite(B"{\n")
            self.IncIndent()

            self.export_key_times(fcurve)
            self.export_key_time_control_points(fcurve)

            self.IndentWrite(B"}\n\n", -1)
            self.IndentWrite(B"Value (curve = \"bezier\")\n", -1)
            self.IndentWrite(B"{\n", -1)

            self.export_key_values(fcurve)
            self.export_key_value_control_points(fcurve)

            self.DecIndent()
            self.IndentWrite(B"}\n")

        self.DecIndent()
        self.IndentWrite(B"}\n")

    def export_node_sampled_animation(self, node, scene):
        debug()

        # This function exports animation as full 4x4 matrices for each frame.

        currentFrame = scene.frame_current
        currentSubframe = scene.frame_subframe

        animationFlag = False
        m1 = node.matrix_local.copy()

        for i in range(self.container.beginFrame, self.container.endFrame):
            scene.frame_set(i)
            m2 = node.matrix_local
            if OpenGexExporter.matrices_differ(m1, m2):
                animationFlag = True
                break

        if animationFlag:
            self.IndentWrite(B"Animation\n", 0, True)
            self.IndentWrite(B"{\n")
            self.IncIndent()

            self.IndentWrite(B"Track (target = %transform)\n")
            self.IndentWrite(B"{\n")
            self.IncIndent()

            self.IndentWrite(B"Time\n")
            self.IndentWrite(B"{\n")
            self.IncIndent()

            self.IndentWrite(B"Key {float {")

            for i in range(self.container.beginFrame, self.container.endFrame):
                self.WriteFloat((i - self.container.beginFrame) * self.container.frameTime)
                self.file.write(B", ")

            self.WriteFloat(self.container.endFrame * self.container.frameTime)
            self.file.write(B"}}\n")

            self.IndentWrite(B"}\n\n", -1)
            self.IndentWrite(B"Value\n", -1)
            self.IndentWrite(B"{\n", -1)

            self.IndentWrite(B"Key\n")
            self.IndentWrite(B"{\n")
            self.IncIndent()

            self.IndentWrite(B"float[16]\n")
            self.IndentWrite(B"{\n")

            for i in range(self.container.beginFrame, self.container.endFrame):
                scene.frame_set(i)
                self.WriteMatrixFlat(node.matrix_local)
                self.file.write(B",\n")

            scene.frame_set(self.container.endFrame)
            self.WriteMatrixFlat(node.matrix_local)
            self.IndentWrite(B"}\n", 0, True)

            self.DecIndent()
            self.IndentWrite(B"}\n")

            self.DecIndent()
            self.IndentWrite(B"}\n")

            self.DecIndent()
            self.IndentWrite(B"}\n")

            self.DecIndent()
            self.IndentWrite(B"}\n")

        scene.frame_set(currentFrame, currentSubframe)

    def export_bone_sampled_animation(self, poseBone, scene):
        debug()

        # This function exports bone animation as full 4x4 matrices for each frame.

        currentFrame = scene.frame_current
        currentSubframe = scene.frame_subframe

        animationFlag = False
        m1 = poseBone.matrix.copy()

        for i in range(self.container.beginFrame, self.container.endFrame):
            scene.frame_set(i)
            m2 = poseBone.matrix
            if OpenGexExporter.matrices_differ(m1, m2):
                animationFlag = True
                break

        if animationFlag:
            self.IndentWrite(B"Animation\n", 0, True)
            self.IndentWrite(B"{\n")
            self.IncIndent()

            self.IndentWrite(B"Track (target = %transform)\n")
            self.IndentWrite(B"{\n")
            self.IncIndent()

            self.IndentWrite(B"Time\n")
            self.IndentWrite(B"{\n")
            self.IncIndent()

            self.IndentWrite(B"Key {float {")

            for i in range(self.container.beginFrame, self.container.endFrame):
                self.WriteFloat((i - self.container.beginFrame) * self.container.frameTime)
                self.file.write(B", ")

            self.WriteFloat(self.container.endFrame * self.container.frameTime)
            self.file.write(B"}}\n")

            self.IndentWrite(B"}\n\n", -1)
            self.IndentWrite(B"Value\n", -1)
            self.IndentWrite(B"{\n", -1)

            self.IndentWrite(B"Key\n")
            self.IndentWrite(B"{\n")
            self.IncIndent()

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

                    self.file.write(B",\n")

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
                    self.file.write(B",\n")

                scene.frame_set(self.container.endFrame)
                self.WriteMatrixFlat(poseBone.matrix)
                self.IndentWrite(B"}\n", 0, True)

            self.DecIndent()
            self.IndentWrite(B"}\n")

            self.DecIndent()
            self.IndentWrite(B"}\n")

            self.DecIndent()
            self.IndentWrite(B"}\n")

            self.DecIndent()
            self.IndentWrite(B"}\n")

        scene.frame_set(currentFrame, currentSubframe)

    def export_morph_weight_sampled_animation_track(self, block, target, scene, newline):
        debug()
        currentFrame = scene.frame_current
        currentSubframe = scene.frame_subframe

        self.IndentWrite(B"Track (target = %", 0, newline)
        self.file.write(target)
        self.file.write(B")\n")
        self.IndentWrite(B"{\n")
        self.IncIndent()

        self.IndentWrite(B"Time\n")
        self.IndentWrite(B"{\n")
        self.IncIndent()

        self.IndentWrite(B"Key {float {")

        for i in range(self.container.beginFrame, self.container.endFrame):
            self.WriteFloat((i - self.container.beginFrame) * self.container.frameTime)
            self.file.write(B", ")

        self.WriteFloat(self.container.endFrame * self.container.frameTime)
        self.file.write(B"}}\n")

        self.IndentWrite(B"}\n\n", -1)
        self.IndentWrite(B"Value\n", -1)
        self.IndentWrite(B"{\n", -1)

        self.IndentWrite(B"Key {float {")

        for i in range(self.container.beginFrame, self.container.endFrame):
            scene.frame_set(i)
            self.WriteFloat(block.value)
            self.file.write(B", ")

        scene.frame_set(self.container.endFrame)
        self.WriteFloat(block.value)
        self.file.write(B"}}\n")

        self.DecIndent()
        self.IndentWrite(B"}\n")

        self.DecIndent()
        self.IndentWrite(B"}\n")

        scene.frame_set(currentFrame, currentSubframe)

    # FIXME Handle NodeWrapper
    def export_node_transformation(self, nw, scene):
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
                    kind = OpenGexExporter.classify_animation_curve(fcurve)
                    if kind != kAnimationSampled:
                        if fcurve.data_path == "location":
                            for i in range(3):
                                if (fcurve.array_index == i) and (not posAnimCurve[i]):
                                    posAnimCurve[i] = fcurve
                                    posAnimKind[i] = kind
                                    if OpenGexExporter.animation_present(fcurve, kind):
                                        posAnimated[i] = True
                        elif fcurve.data_path == "delta_location":
                            for i in range(3):
                                if (fcurve.array_index == i) and (not deltaPosAnimCurve[i]):
                                    deltaPosAnimCurve[i] = fcurve
                                    deltaPosAnimKind[i] = kind
                                    if OpenGexExporter.animation_present(fcurve, kind):
                                        deltaPosAnimated[i] = True
                        elif fcurve.data_path == "rotation_euler":
                            for i in range(3):
                                if (fcurve.array_index == i) and (not rotAnimCurve[i]):
                                    rotAnimCurve[i] = fcurve
                                    rotAnimKind[i] = kind
                                    if OpenGexExporter.animation_present(fcurve, kind):
                                        rotAnimated[i] = True
                        elif fcurve.data_path == "delta_rotation_euler":
                            for i in range(3):
                                if (fcurve.array_index == i) and (not deltaRotAnimCurve[i]):
                                    deltaRotAnimCurve[i] = fcurve
                                    deltaRotAnimKind[i] = kind
                                    if OpenGexExporter.animation_present(fcurve, kind):
                                        deltaRotAnimated[i] = True
                        elif fcurve.data_path == "scale":
                            for i in range(3):
                                if (fcurve.array_index == i) and (not sclAnimCurve[i]):
                                    sclAnimCurve[i] = fcurve
                                    sclAnimKind[i] = kind
                                    if OpenGexExporter.animation_present(fcurve, kind):
                                        sclAnimated[i] = True
                        elif fcurve.data_path == "delta_scale":
                            for i in range(3):
                                if (fcurve.array_index == i) and (not deltaSclAnimCurve[i]):
                                    deltaSclAnimCurve[i] = fcurve
                                    deltaSclAnimKind[i] = kind
                                    if OpenGexExporter.animation_present(fcurve, kind):
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
                self.file.write(B" %transform")

            self.IndentWrite(B"{\n", 0, True)
            self.IncIndent()

            self.IndentWrite(B"float[16]\n")
            self.IndentWrite(B"{\n")

            self.handle_offset(node.matrix_local, nw.offset)
            self.IndentWrite(B"}\n")

            self.DecIndent()
            self.IndentWrite(B"}\n")

            if sampledAnimation:
                self.export_node_sampled_animation(node, scene)

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
                        self.file.write(deltaSubtranslationName[i])
                        self.file.write(B" (kind = \"")
                        self.file.write(axisName[i])
                        self.file.write(B"\")\n")
                        self.IndentWrite(B"{\n")
                        self.IndentWrite(B"float {", 1)
                        self.WriteFloat(pos)
                        self.file.write(B"}")
                        self.IndentWrite(B"}\n", 0, True)

                        structFlag = True

            elif ((math.fabs(deltaTranslation[0]) > kExportEpsilon) or (
                        math.fabs(deltaTranslation[1]) > kExportEpsilon) or (
                        math.fabs(deltaTranslation[2]) > kExportEpsilon)):
                self.IndentWrite(B"Translation\n")
                self.IndentWrite(B"{\n")
                self.IndentWrite(B"float[3] {", 1)
                self.WriteVector3D(deltaTranslation)
                self.file.write(B"}")
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
                        self.file.write(subtranslationName[i])
                        self.file.write(B" (kind = \"")
                        self.file.write(axisName[i])
                        self.file.write(B"\")\n")
                        self.IndentWrite(B"{\n")
                        self.IndentWrite(B"float {", 1)
                        self.WriteFloat(pos)
                        self.file.write(B"}")
                        self.IndentWrite(B"}\n", 0, True)

                        structFlag = True

            elif ((math.fabs(translation[0]) > kExportEpsilon) or (math.fabs(translation[1]) > kExportEpsilon) or (
                        math.fabs(translation[2]) > kExportEpsilon)):
                self.IndentWrite(B"Translation\n")
                self.IndentWrite(B"{\n")
                self.IndentWrite(B"float[3] {", 1)
                self.WriteVector3D(translation)
                self.file.write(B"}")
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
                        self.file.write(deltaSubrotationName[axis])
                        self.file.write(B" (kind = \"")
                        self.file.write(axisName[axis])
                        self.file.write(B"\")\n")
                        self.IndentWrite(B"{\n")
                        self.IndentWrite(B"float {", 1)
                        self.WriteFloat(angle)
                        self.file.write(B"}")
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
                        self.file.write(B"}")
                        self.IndentWrite(B"}\n", 0, True)

                        structFlag = True

                else:
                    for i in range(3):
                        axis = ord(mode[2 - i]) - 0x58
                        angle = node.delta_rotation_euler[axis]
                        if math.fabs(angle) > kExportEpsilon:
                            self.IndentWrite(B"Rotation (kind = \"", 0, structFlag)
                            self.file.write(axisName[axis])
                            self.file.write(B"\")\n")
                            self.IndentWrite(B"{\n")
                            self.IndentWrite(B"float {", 1)
                            self.WriteFloat(angle)
                            self.file.write(B"}")
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
                        self.file.write(subrotationName[axis])
                        self.file.write(B" (kind = \"")
                        self.file.write(axisName[axis])
                        self.file.write(B"\")\n")
                        self.IndentWrite(B"{\n")
                        self.IndentWrite(B"float {", 1)
                        self.WriteFloat(angle)
                        self.file.write(B"}")
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
                        self.file.write(B"}")
                        self.IndentWrite(B"}\n", 0, True)

                        structFlag = True

                elif mode == "AXIS_ANGLE":
                    if math.fabs(node.rotation_axis_angle[0]) > kExportEpsilon:
                        self.IndentWrite(B"Rotation (kind = \"axis\")\n", 0, structFlag)
                        self.IndentWrite(B"{\n")
                        self.IndentWrite(B"float[4] {", 1)
                        self.WriteVector4D(node.rotation_axis_angle)
                        self.file.write(B"}")
                        self.IndentWrite(B"}\n", 0, True)

                        structFlag = True

                else:
                    for i in range(3):
                        axis = ord(mode[2 - i]) - 0x58
                        angle = node.rotation_euler[axis]
                        if math.fabs(angle) > kExportEpsilon:
                            self.IndentWrite(B"Rotation (kind = \"", 0, structFlag)
                            self.file.write(axisName[axis])
                            self.file.write(B"\")\n")
                            self.IndentWrite(B"{\n")
                            self.IndentWrite(B"float {", 1)
                            self.WriteFloat(angle)
                            self.file.write(B"}")
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
                        self.file.write(deltaSubscaleName[i])
                        self.file.write(B" (kind = \"")
                        self.file.write(axisName[i])
                        self.file.write(B"\")\n")
                        self.IndentWrite(B"{\n")
                        self.IndentWrite(B"float {", 1)
                        self.WriteFloat(scl)
                        self.file.write(B"}")
                        self.IndentWrite(B"}\n", 0, True)

                        structFlag = True

            elif ((math.fabs(deltaScale[0] - 1.0) > kExportEpsilon) or (
                        math.fabs(deltaScale[1] - 1.0) > kExportEpsilon) or (
                        math.fabs(deltaScale[2] - 1.0) > kExportEpsilon)):
                self.IndentWrite(B"Scale\n", 0, structFlag)
                self.IndentWrite(B"{\n")
                self.IndentWrite(B"float[3] {", 1)
                self.WriteVector3D(deltaScale)
                self.file.write(B"}")
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
                        self.file.write(subscaleName[i])
                        self.file.write(B" (kind = \"")
                        self.file.write(axisName[i])
                        self.file.write(B"\")\n")
                        self.IndentWrite(B"{\n")
                        self.IndentWrite(B"float {", 1)
                        self.WriteFloat(scl)
                        self.file.write(B"}")
                        self.IndentWrite(B"}\n", 0, True)

                        structFlag = True

            elif ((math.fabs(scale[0] - 1.0) > kExportEpsilon) or (math.fabs(scale[1] - 1.0) > kExportEpsilon) or (
                        math.fabs(scale[2] - 1.0) > kExportEpsilon)):
                self.IndentWrite(B"Scale\n", 0, structFlag)
                self.IndentWrite(B"{\n")
                self.IndentWrite(B"float[3] {", 1)
                self.WriteVector3D(scale)
                self.file.write(B"}")
                self.IndentWrite(B"}\n", 0, True)

                structFlag = True

            # Export the animation tracks.

            self.IndentWrite(B"Animation (begin = ", 0, True)
            self.WriteFloat((action.frame_range[0] - self.container.beginFrame) * self.container.frameTime)
            self.file.write(B", end = ")
            self.WriteFloat((action.frame_range[1] - self.container.beginFrame) * self.container.frameTime)
            self.file.write(B")\n")
            self.IndentWrite(B"{\n")
            self.IncIndent()

            structFlag = False

            if positionAnimated:
                for i in range(3):
                    if posAnimated[i]:
                        self.export_animation_track(posAnimCurve[i], posAnimKind[i], subtranslationName[i], structFlag)
                        structFlag = True

            if rotationAnimated:
                for i in range(3):
                    if rotAnimated[i]:
                        self.export_animation_track(rotAnimCurve[i], rotAnimKind[i], subrotationName[i], structFlag)
                        structFlag = True

            if scaleAnimated:
                for i in range(3):
                    if sclAnimated[i]:
                        self.export_animation_track(sclAnimCurve[i], sclAnimKind[i], subscaleName[i], structFlag)
                        structFlag = True

            if deltaPositionAnimated:
                for i in range(3):
                    if deltaPosAnimated[i]:
                        self.export_animation_track(deltaPosAnimCurve[i], deltaPosAnimKind[i], deltaSubtranslationName[i],
                                                  structFlag)
                        structFlag = True

            if deltaRotationAnimated:
                for i in range(3):
                    if deltaRotAnimated[i]:
                        self.export_animation_track(deltaRotAnimCurve[i], deltaRotAnimKind[i], deltaSubrotationName[i],
                                                  structFlag)
                        structFlag = True

            if deltaScaleAnimated:
                for i in range(3):
                    if deltaSclAnimated[i]:
                        self.export_animation_track(deltaSclAnimCurve[i], deltaSclAnimKind[i], deltaSubscaleName[i],
                                                  structFlag)
                        structFlag = True

            self.DecIndent()
            self.IndentWrite(B"}\n")

    def handle_offset(self, matrix, offset):
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

    def export_bone_transform(self, nw, bw, scene):  # armature, bone, scene):
        debug()

        curveArray = self.export_bone_animation(nw.item, bw.item.name)
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
            self.file.write(B" %transform")

        self.IndentWrite(B"{\n", 0, True)
        self.IncIndent()

        self.IndentWrite(B"float[16]\n")
        self.IndentWrite(B"{\n")
        self.WriteMatrix(transform)
        self.IndentWrite(B"}\n")

        self.DecIndent()
        self.IndentWrite(B"}\n")

        if animation and poseBone:
            self.export_bone_sampled_animation(poseBone, scene)

    def export_material_ref(self, material, index):
        debug()
        if material not in self.container.materialArray:
            self.container.materialArray[material] = \
                {"structName": bytes("material" + str(len(self.container.materialArray) + 1), "UTF-8")}

        self.IndentWrite(B"MaterialRef (index = ")
        self.WriteInt(index)
        self.file.write(B") {ref {$")
        self.file.write(self.container.materialArray[material]["structName"])
        self.file.write(B"}}\n")

    def export_morph_weights(self, node, shapeKeys, scene):
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
                self.file.write(B" %mw")
                self.WriteInt(k)

            self.file.write(B" (index = ")
            self.WriteInt(k)
            self.file.write(B") {float {")

            block = shapeKeys.key_blocks[k]
            self.WriteFloat(block.value if (block.name != referenceName) else 1.0)

            self.file.write(B"}}\n")

        if animated:
            self.IndentWrite(B"Animation (begin = ", 0, True)
            self.WriteFloat((action.frame_range[0] - self.container.beginFrame) * self.container.frameTime)
            self.file.write(B", end = ")
            self.WriteFloat((action.frame_range[1] - self.container.beginFrame) * self.container.frameTime)
            self.file.write(B")\n")
            self.IndentWrite(B"{\n")
            self.IncIndent()

            structFlag = False

            for a in range(len(curveArray)):
                k = indexArray[a]
                target = bytes("mw" + str(k), "UTF-8")

                fcurve = curveArray[a]
                kind = OpenGexExporter.classify_animation_curve(fcurve)
                if (kind != kAnimationSampled) and (not self.container.sampleAnimationFlag):
                    self.export_animation_track(fcurve, kind, target, structFlag)
                else:
                    self.export_morph_weight_sampled_animation_track(shapeKeys.key_blocks[k], target, scene, structFlag)

                structFlag = True

            self.DecIndent()
            self.IndentWrite(B"}\n")

    def export_bone(self, nw, bw, scene):  # armature, bone, scene):
        debug()
        if nw.nodeRef:
            self.IndentWrite(structIdentifier[nw.nodeRef["nodeType"]], 0, True)
            self.file.write(nw.nodeRef["structName"])

            self.IndentWrite(B"{\n", 0, True)
            self.IncIndent()

            name = bw.item.name
            if name != "":
                self.IndentWrite(B"Name {string {\"")
                self.file.write(bytes(name, "UTF-8"))
                self.file.write(B"\"}}\n\n")

            self.export_bone_transform(nw, bw, scene)

        for child in bw.children:
            self.export_bone(nw, child, scene)

        # Export any ordinary nodes that are parented to this bone.

        boneSubnodeArray = self.container.boneParentArray.get(bw.item.name)
        if boneSubnodeArray:
            poseBone = None
            if not bw.item.use_relative_parent:
                poseBone = nw.item.pose.bones.get(bw.item.name)

            for subnodeWrapper in boneSubnodeArray:
                self.export_node(subnodeWrapper, scene, poseBone)

        if nw.nodeRef:
            self.DecIndent()
            self.IndentWrite(B"}\n")

    def export_node(self, nw, scene, poseBone=None):
        debug()

        # This function exports a single node in the scene and includes its name,
        # object reference, material references (for geometries), and transform.
        # Subnodes are then exported recursively.

        if nw.nodeRef:
            type = nw.nodeRef["nodeType"]
            self.IndentWrite(structIdentifier[type], 0, True)
            self.file.write(nw.nodeRef["structName"])

            if type == kNodeTypeGeometry:
                if nw.item.hide_render:
                    self.file.write(B" (visible = false)")

            self.IndentWrite(B"{\n", 0, True)
            self.IncIndent()

            structFlag = False

            # Export the node's name if it has one.

            name = nw.item.name
            if name != "":
                self.IndentWrite(B"Name {string {\"")
                self.file.write(bytes(name, "UTF-8"))
                self.file.write(B"\"}}\n")
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
                self.file.write(self.container.geometryArray[object]["structName"])
                self.file.write(B"}}\n")

                for i in range(len(nw.item.material_slots)):
                    self.export_material_ref(nw.item.material_slots[i].material, i)

                shapeKeys = OpenGexExporter.get_shape_keys(object)
                if shapeKeys:
                    # FIXME Wrapper or item?
                    self.export_morph_weights(nw.item, shapeKeys, scene)

                structFlag = True

            elif type == kNodeTypeLight:
                if object not in self.container.lightArray:
                    self.container.lightArray[object] = \
                        {"structName": bytes("light" + str(len(self.container.lightArray) + 1), "UTF-8"),
                         "nodeTable": [nw.item]}
                else:
                    self.container.lightArray[object]["nodeTable"].append(nw.item)

                self.IndentWrite(B"ObjectRef {ref {$")
                self.file.write(self.container.lightArray[object]["structName"])
                self.file.write(B"}}\n")
                structFlag = True

            elif type == kNodeTypeCamera:
                if object not in self.container.cameraArray:
                    self.container.cameraArray[object] = \
                        {"structName": bytes("camera" + str(len(self.container.cameraArray) + 1), "UTF-8"),
                         "nodeTable": [nw.item]}
                else:
                    self.container.cameraArray[object]["nodeTable"].append(nw.item)

                self.IndentWrite(B"ObjectRef {ref {$")
                self.file.write(self.container.cameraArray[object]["structName"])
                self.file.write(B"}}\n")
                structFlag = True

            if structFlag:
                self.file.write(B"\n")

            if poseBone:
                # If the node is parented to a bone and is not relative, then undo the bone's transform.

                if math.fabs(poseBone.matrix.determinant()) > kExportEpsilon:
                    self.IndentWrite(B"Transform\n")
                    self.IndentWrite(B"{\n")
                    self.IncIndent()

                    self.IndentWrite(B"float[16]\n")
                    self.IndentWrite(B"{\n")
                    self.WriteMatrix(poseBone.matrix.inverted())
                    self.IndentWrite(B"}\n")

                    self.DecIndent()
                    self.IndentWrite(B"}\n\n")

            # Export the transform. If the node is animated, then animation tracks are exported here.

            self.export_node_transformation(nw, scene)

            if nw.bones:
                for bw in nw.bones:
                    self.export_bone(nw, bw, scene)

        for subnode in nw.children:
            if subnode.parent.item.type != "BONE":
                self.export_node(subnode, scene)

        if nw.nodeRef:
            self.DecIndent()
            self.IndentWrite(B"}\n")

    def export_skin(self, node, armature, exportVertexArray):
        debug()

        # This function exports all skinning data, which includes the skeleton
        # and per-vertex bone influence data.

        self.IndentWrite(B"Skin\n", 0, True)
        self.IndentWrite(B"{\n")
        self.IncIndent()

        # Write the skin bind pose transform.

        self.IndentWrite(B"Transform\n")
        self.IndentWrite(B"{\n")
        self.IncIndent()

        self.IndentWrite(B"float[16]\n")
        self.IndentWrite(B"{\n")
        self.WriteMatrix(node.matrix_world)
        self.IndentWrite(B"}\n")

        self.DecIndent()
        self.IndentWrite(B"}\n\n")

        # Export the skeleton, which includes an array of bone node references
        # and and array of per-bone bind pose transforms.

        self.IndentWrite(B"Skeleton\n")
        self.IndentWrite(B"{\n")
        self.IncIndent()

        # Write the bone node reference array.

        self.IndentWrite(B"BoneRefArray\n")
        self.IndentWrite(B"{\n")
        self.IncIndent()

        boneArray = armature.data.bones
        boneCount = len(boneArray)

        self.IndentWrite(B"ref\t\t\t// ")
        self.WriteInt(boneCount)
        self.IndentWrite(B"{\n", 0, True)
        self.IndentWrite(B"", 1)

        for i in range(boneCount):
            boneRef = self.find_node(boneArray[i].name)
            if boneRef:
                self.file.write(B"$")
                self.file.write(boneRef[1]["structName"])
            else:
                self.file.write(B"null")

            if i < boneCount - 1:
                self.file.write(B", ")
            else:
                self.file.write(B"\n")

        self.IndentWrite(B"}\n")

        self.DecIndent()
        self.IndentWrite(B"}\n\n")

        # Write the bind pose transform array.

        self.IndentWrite(B"Transform\n")
        self.IndentWrite(B"{\n")
        self.IncIndent()

        self.IndentWrite(B"float[16]\t// ")
        self.WriteInt(boneCount)
        self.IndentWrite(B"{\n", 0, True)

        for i in range(boneCount):
            self.WriteMatrixFlat(armature.matrix_world * boneArray[i].matrix_local)
            if i < boneCount - 1:
                self.file.write(B",\n")

        self.IndentWrite(B"}\n", 0, True)

        self.DecIndent()
        self.IndentWrite(B"}\n")

        self.DecIndent()
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
        self.IncIndent()

        self.IndentWrite(B"unsigned_int16\t\t// ")
        self.WriteInt(len(boneCountArray))
        self.IndentWrite(B"{\n", 0, True)
        self.WriteIntArray(boneCountArray)
        self.IndentWrite(B"}\n")

        self.DecIndent()
        self.IndentWrite(B"}\n\n")

        # Write the bone index array. The number of entries is the sum of the bone counts for all vertices.

        self.IndentWrite(B"BoneIndexArray\n")
        self.IndentWrite(B"{\n")
        self.IncIndent()

        self.IndentWrite(B"unsigned_int16\t\t// ")
        self.WriteInt(len(boneIndexArray))
        self.IndentWrite(B"{\n", 0, True)
        self.WriteIntArray(boneIndexArray)
        self.IndentWrite(B"}\n")

        self.DecIndent()
        self.IndentWrite(B"}\n\n")

        # Write the bone weight array. The number of entries is the sum of the bone counts for all vertices.

        self.IndentWrite(B"BoneWeightArray\n")
        self.IndentWrite(B"{\n")
        self.IncIndent()

        self.IndentWrite(B"float\t\t// ")
        self.WriteInt(len(boneWeightArray))
        self.IndentWrite(B"{\n", 0, True)
        self.WriteFloatArray(boneWeightArray)
        self.IndentWrite(B"}\n")

        self.DecIndent()
        self.IndentWrite(B"}\n")

        self.DecIndent()
        self.IndentWrite(B"}\n")

    def export_geometry(self, objectRef, scene):
        debug()

        self.progress.begin_task("Exporting geometry for " + objectRef[1]["nodeTable"][0].name + "...")

        # This function exports a single geometry object.

        self.file.write(B"\nGeometryObject $")
        self.file.write(objectRef[1]["structName"])
        self.WriteNodeTable(objectRef)

        self.file.write(B"\n{\n")
        self.IncIndent()

        node = objectRef[1]["nodeTable"][0]
        mesh = objectRef[0]

        structFlag = False

        # Save the morph state if necessary.

        activeShapeKeyIndex = node.active_shape_key_index
        showOnlyShapeKey = node.show_only_shape_key
        currentMorphValue = []

        shapeKeys = OpenGexExporter.get_shape_keys(mesh)
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
                        self.file.write(B", base = ")
                        self.WriteInt(baseIndex)

                    self.file.write(B")\n")
                    self.IndentWrite(B"{\n")
                    self.IndentWrite(B"Name {string {\"", 1)
                    self.file.write(bytes(block.name, "UTF-8"))
                    self.file.write(B"\"}}\n")
                    self.IndentWrite(B"}\n")
                    structFlag = True

                morphCount += 1

            shapeKeys.key_blocks[0].value = 1.0
            mesh.update()

        self.IndentWrite(B"Mesh (primitive = \"triangles\")\n", 0, structFlag)
        self.IndentWrite(B"{\n")
        self.IncIndent()

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
        exportVertexArray = OpenGexExporter.deindex_mesh(exportMesh, materialTable)
        triangleCount = len(materialTable)

        indexTable = []
        unifiedVertexArray = OpenGexExporter.unify_vertices(exportVertexArray, indexTable)
        vertexCount = len(unifiedVertexArray)

        # Write the position array.

        self.IndentWrite(B"VertexArray (attrib = \"position\")\n")
        self.IndentWrite(B"{\n")
        self.IncIndent()

        self.IndentWrite(B"float[3]\t\t// ")
        self.WriteInt(vertexCount)
        self.IndentWrite(B"{\n", 0, True)
        self.WriteVertexArray3D(unifiedVertexArray, "position")
        self.IndentWrite(B"}\n")

        self.DecIndent()
        self.IndentWrite(B"}\n\n")

        # Write the normal array.

        self.IndentWrite(B"VertexArray (attrib = \"normal\")\n")
        self.IndentWrite(B"{\n")
        self.IncIndent()

        self.IndentWrite(B"float[3]\t\t// ")
        self.WriteInt(vertexCount)
        self.IndentWrite(B"{\n", 0, True)
        self.WriteVertexArray3D(unifiedVertexArray, "normal")
        self.IndentWrite(B"}\n")

        self.DecIndent()
        self.IndentWrite(B"}\n")

        # Write the color array if it exists.

        colorCount = len(exportMesh.tessface_vertex_colors)
        if colorCount > 0:
            self.IndentWrite(B"VertexArray (attrib = \"color\")\n", 0, True)
            self.IndentWrite(B"{\n")
            self.IncIndent()

            self.IndentWrite(B"float[3]\t\t// ")
            self.WriteInt(vertexCount)
            self.IndentWrite(B"{\n", 0, True)
            self.WriteVertexArray3D(unifiedVertexArray, "color")
            self.IndentWrite(B"}\n")

            self.DecIndent()
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
                self.IncIndent()
                self.IndentWrite(B"float[2]\t\t// ")
                self.WriteInt(vertexCount)
                self.IndentWrite(B"{\n", 0, True)
                self.WriteVertexArray2D(unifiedVertexArray, "texcoord" + str(count))
                self.IndentWrite(B"}\n")

                self.DecIndent()
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
                self.file.write(B")\n")
                self.IndentWrite(B"{\n")
                self.IncIndent()

                self.IndentWrite(B"float[3]\t\t// ")
                self.WriteInt(vertexCount)
                self.IndentWrite(B"{\n", 0, True)
                self.WriteMorphPositionArray3D(unifiedVertexArray, morphMesh.vertices)
                self.IndentWrite(B"}\n")

                self.DecIndent()
                self.IndentWrite(B"}\n\n")

                # Write the morph target normal array.

                self.IndentWrite(B"VertexArray (attrib = \"normal\", morph = ")
                self.WriteInt(m)
                self.file.write(B")\n")
                self.IndentWrite(B"{\n")
                self.IncIndent()

                self.IndentWrite(B"float[3]\t\t// ")
                self.WriteInt(vertexCount)
                self.IndentWrite(B"{\n", 0, True)
                self.WriteMorphNormalArray3D(unifiedVertexArray, morphMesh.vertices, morphMesh.tessfaces)
                self.IndentWrite(B"}\n")

                self.DecIndent()
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
            self.IncIndent()

            self.IndentWrite(B"unsigned_int32[3]\t\t// ")
            self.WriteInt(triangleCount)
            self.IndentWrite(B"{\n", 0, True)
            self.WriteTriangleArray(triangleCount, indexTable)
            self.IndentWrite(B"}\n")

            self.DecIndent()
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
                    self.file.write(B")\n")
                    self.IndentWrite(B"{\n")
                    self.IncIndent()

                    self.IndentWrite(B"unsigned_int32[3]\t\t// ")
                    self.WriteInt(materialTriangleCount[m])
                    self.IndentWrite(B"{\n", 0, True)
                    self.WriteTriangleArray(materialTriangleCount[m], materialIndexTable)
                    self.IndentWrite(B"}\n")

                    self.DecIndent()
                    self.IndentWrite(B"}\n")

        # If the mesh is skinned, export the skinning data here.

        if armature:
            self.export_skin(node, armature, unifiedVertexArray)

        # Restore the morph state.

        if shapeKeys:
            node.active_shape_key_index = activeShapeKeyIndex
            node.show_only_shape_key = showOnlyShapeKey

            for m in range(len(currentMorphValue)):
                shapeKeys.key_blocks[m].value = currentMorphValue[m]

            mesh.update()

        # Delete the new mesh that we made earlier.

        bpy.data.meshes.remove(exportMesh)

        self.DecIndent()
        self.IndentWrite(B"}\n")

        self.DecIndent()
        self.file.write(B"}\n")

        self.progress.end_task()

    def export_light(self, objectRef):
        debug()

        # This function exports a single light object.

        self.file.write(B"\nLightObject $")
        self.file.write(objectRef[1]["structName"])

        object = objectRef[0]
        type = object.type

        self.file.write(B" (type = ")
        pointFlag = False
        spotFlag = False

        if type == "SUN":
            self.file.write(B"\"infinite\"")
        elif type == "POINT":
            self.file.write(B"\"point\"")
            pointFlag = True
        else:
            self.file.write(B"\"spot\"")
            pointFlag = True
            spotFlag = True

        if not object.use_shadow:
            self.file.write(B", shadow = false")

        self.file.write(B")")
        self.WriteNodeTable(objectRef)

        self.file.write(B"\n{\n")
        self.IncIndent()

        # Export the light's color, and include a separate intensity if necessary.

        self.IndentWrite(B"Color (attrib = \"light\") {float[3] {")
        self.WriteColor(object.color)
        self.file.write(B"}}\n")

        intensity = object.energy
        if intensity != 1.0:
            self.IndentWrite(B"Param (attrib = \"intensity\") {float {")
            self.WriteFloat(intensity)
            self.file.write(B"}}\n")

        if pointFlag:

            # Export a separate attenuation function for each type that's in use.

            falloff = object.falloff_type

            if falloff == "INVERSE_LINEAR":
                self.IndentWrite(B"Atten (curve = \"inverse\")\n", 0, True)
                self.IndentWrite(B"{\n")

                self.IndentWrite(B"Param (attrib = \"scale\") {float {", 1)
                self.WriteFloat(object.distance)
                self.file.write(B"}}\n")

                self.IndentWrite(B"}\n")

            elif falloff == "INVERSE_SQUARE":
                self.IndentWrite(B"Atten (curve = \"inverse_square\")\n", 0, True)
                self.IndentWrite(B"{\n")

                self.IndentWrite(B"Param (attrib = \"scale\") {float {", 1)
                self.WriteFloat(math.sqrt(object.distance))
                self.file.write(B"}}\n")

                self.IndentWrite(B"}\n")

            elif falloff == "LINEAR_QUADRATIC_WEIGHTED":
                if object.linear_attenuation != 0.0:
                    self.IndentWrite(B"Atten (curve = \"inverse\")\n", 0, True)
                    self.IndentWrite(B"{\n")

                    self.IndentWrite(B"Param (attrib = \"scale\") {float {", 1)
                    self.WriteFloat(object.distance)
                    self.file.write(B"}}\n")

                    self.IndentWrite(B"Param (attrib = \"constant\") {float {", 1)
                    self.WriteFloat(1.0)
                    self.file.write(B"}}\n")

                    self.IndentWrite(B"Param (attrib = \"linear\") {float {", 1)
                    self.WriteFloat(object.linear_attenuation)
                    self.file.write(B"}}\n")

                    self.IndentWrite(B"}\n\n")

                if object.quadratic_attenuation != 0.0:
                    self.IndentWrite(B"Atten (curve = \"inverse_square\")\n")
                    self.IndentWrite(B"{\n")

                    self.IndentWrite(B"Param (attrib = \"scale\") {float {", 1)
                    self.WriteFloat(object.distance)
                    self.file.write(B"}}\n")

                    self.IndentWrite(B"Param (attrib = \"constant\") {float {", 1)
                    self.WriteFloat(1.0)
                    self.file.write(B"}}\n")

                    self.IndentWrite(B"Param (attrib = \"quadratic\") {float {", 1)
                    self.WriteFloat(object.quadratic_attenuation)
                    self.file.write(B"}}\n")

                    self.IndentWrite(B"}\n")

            if object.use_sphere:
                self.IndentWrite(B"Atten (curve = \"linear\")\n", 0, True)
                self.IndentWrite(B"{\n")

                self.IndentWrite(B"Param (attrib = \"end\") {float {", 1)
                self.WriteFloat(object.distance)
                self.file.write(B"}}\n")

                self.IndentWrite(B"}\n")

            if spotFlag:
                # Export additional angular attenuation for spot lights.

                self.IndentWrite(B"Atten (kind = \"angle\", curve = \"linear\")\n", 0, True)
                self.IndentWrite(B"{\n")

                endAngle = object.spot_size * 0.5
                beginAngle = endAngle * (1.0 - object.spot_blend)

                self.IndentWrite(B"Param (attrib = \"begin\") {float {", 1)
                self.WriteFloat(beginAngle)
                self.file.write(B"}}\n")

                self.IndentWrite(B"Param (attrib = \"end\") {float {", 1)
                self.WriteFloat(endAngle)
                self.file.write(B"}}\n")

                self.IndentWrite(B"}\n")

        self.DecIndent()
        self.file.write(B"}\n")

    def export_camera(self, objectRef):
        debug()

        # This function exports a single camera object.

        self.file.write(B"\nCameraObject $")
        self.file.write(objectRef[1]["structName"])
        self.WriteNodeTable(objectRef)

        self.file.write(B"\n{\n")
        self.IncIndent()

        object = objectRef[0]

        self.IndentWrite(B"Param (attrib = \"fov\") {float {")
        self.WriteFloat(object.angle_x)
        self.file.write(B"}}\n")

        self.IndentWrite(B"Param (attrib = \"near\") {float {")
        self.WriteFloat(object.clip_start)
        self.file.write(B"}}\n")

        self.IndentWrite(B"Param (attrib = \"far\") {float {")
        self.WriteFloat(object.clip_end)
        self.file.write(B"}}\n")

        self.DecIndent()
        self.file.write(B"}\n")

    def export_objects(self, scene):
        debug()
        for objectRef in self.container.geometryArray.items():
            self.export_geometry(objectRef, scene)
        for objectRef in self.container.lightArray.items():
            self.export_light(objectRef)
        for objectRef in self.container.cameraArray.items():
            self.export_camera(objectRef)

    def export_texture(self, textureSlot, attrib):
        debug()

        if textureSlot.texture.type != 'IMAGE':
            return # only image textures supported.

        if textureSlot.texture.image is None:
            return # cannot export no image.

        # This function exports a single texture from a material.

        self.IndentWrite(B"Texture (attrib = \"", 0, True)
        self.file.write(attrib)
        self.file.write(B"\")\n")

        self.IndentWrite(B"{\n")
        self.IncIndent()

        self.IndentWrite(B"string {\"")
        self.WriteFileName(textureSlot.texture.image.filepath.replace("//", ""))
        self.file.write(B"\"}\n")

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
            self.IncIndent()

            self.IndentWrite(B"float[16]\n")
            self.IndentWrite(B"{\n")
            self.WriteMatrix(matrix)
            self.IndentWrite(B"}\n")

            self.DecIndent()
            self.IndentWrite(B"}\n")

        self.DecIndent()
        self.IndentWrite(B"}\n")

    def export_materials(self):
        # This function exports all of the materials used in the scene.

        for materialRef in self.container.materialArray.items():
            material = materialRef[0]

            self.file.write(B"\nMaterial $")
            self.file.write(materialRef[1]["structName"])
            self.file.write(B"\n{\n")
            self.IncIndent()

            if material.name != "":
                self.IndentWrite(B"Name {string {\"")
                self.file.write(bytes(material.name, "UTF-8"))
                self.file.write(B"\"}}\n\n")

            intensity = material.diffuse_intensity
            diffuse = [material.diffuse_color[0] * intensity, material.diffuse_color[1] * intensity,
                       material.diffuse_color[2] * intensity]

            self.IndentWrite(B"Color (attrib = \"diffuse\") {float[3] {")
            self.WriteColor(diffuse)
            self.file.write(B"}}\n")

            intensity = material.specular_intensity
            specular = [material.specular_color[0] * intensity, material.specular_color[1] * intensity,
                        material.specular_color[2] * intensity]

            if (specular[0] > 0.0) or (specular[1] > 0.0) or (specular[2] > 0.0):
                self.IndentWrite(B"Color (attrib = \"specular\") {float[3] {")
                self.WriteColor(specular)
                self.file.write(B"}}\n")

                self.IndentWrite(B"Param (attrib = \"specular_power\") {float {")
                self.WriteFloat(material.specular_hardness)
                self.file.write(B"}}\n")

            emission = material.emit
            if emission > 0.0:
                self.IndentWrite(B"Color (attrib = \"emission\") {float[3] {")
                self.WriteColor([emission, emission, emission])
                self.file.write(B"}}\n")

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
                self.export_texture(diffuseTexture, B"diffuse")
            if specularTexture:
                self.export_texture(specularTexture, B"specular")
            if emissionTexture:
                self.export_texture(emissionTexture, B"emission")
            if transparencyTexture:
                self.export_texture(transparencyTexture, B"transparency")
            if normalTexture:
                self.export_texture(normalTexture, B"normal")

            self.DecIndent()
            self.file.write(B"}\n")

    def export_metrics(self, scene):
        debug()
        scale = scene.unit_settings.scale_length

        if scene.unit_settings.system == "IMPERIAL":
            scale *= 0.3048

        self.file.write(B"Metric (key = \"distance\") {float {")
        self.WriteFloat(scale)
        self.file.write(B"}}\n")

        self.file.write(B"Metric (key = \"angle\") {float {1.0}}\n")
        self.file.write(B"Metric (key = \"time\") {float {1.0}}\n")
        self.file.write(B"Metric (key = \"up\") {string {\"z\"}}\n")

    def get_children_for_node(self, node):
        debug()
        if node in self.nodeChildren:
            return self.nodeChildren[node]
        else:
            return node.children

    def process_skinned_meshes(self):
        debug()
        for nw in self.container.nodes:
            if nw.nodeRef["nodeType"] == kNodeTypeGeometry:
                armature = nw.item.find_armature()
                if armature:
                    for bone in armature.data.bones:
                        boneRef = self.container.find_node_wrapper_by_name(bone.name)
                        if boneRef:
                            # If a node is used as a bone, then we force its type to be a bone.
                            boneRef.dict["nodeType"] = kNodeTypeBone

    def execute(self, context):
        debug()

        startTime = time.time()

        scene = context.scene
        exportAllFlag = not self.option_export_selection
        self.open(self.filepath)
        self.container = FlagContainer(exportAllFlag, self.option_sample_animation, scene)

        self.export_metrics(scene)

        originalFrame = scene.frame_current
        originalSubframe = scene.frame_subframe

        self.progress.begin_task("Preparing objects...")
        for obj in scene.objects:
            if not obj.parent:
                NodeWrapper(obj, self.container)

        self.process_skinned_meshes()

        self.progress.end_task()

        self.progress.begin_task("Exporting nodes...")
        lastTime = time.time()
        for obj in self.container.nodes:
            if not obj.parent:
                self.export_node(obj, scene)
        self.progress.end_task()

        # progress update is handled withing ExportObjects()
        self.export_objects(scene)


        self.progress.begin_task("Exporting materials...")
        self.export_materials()
        self.progress.end_task()

        restoreFrame = False
        if restoreFrame:
            scene.frame_set(originalFrame, originalSubframe)

        self.close()

        print('-- Successfully exported to "{}". ({:.2f} sec)'.format(self.filepath, time.time() - startTime))

        return {'FINISHED'}
