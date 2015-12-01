import math
import time
import bpy

from blenderOpenGEX.FlagContainer import *
from blenderOpenGEX.NodeWrapper import NodeWrapper
from blenderOpenGEX.Writer import Writer
from bpy_extras.io_utils import ExportHelper
from blenderOpenGEX.ExportVertex import ExportVertex

__author__ = 'Eric Lengyel, aullik, Jonathan Hale'

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
delta_subscale_name = [B"dxscl", B"dyscl", B"dzscl"]
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

        super().__init__()
        self.progress = ProgressLog()
        self.container = None

    @staticmethod
    def get_shape_keys(mesh):

        shape_keys = mesh.shape_keys
        if shape_keys and (len(shape_keys.key_blocks) > 1):
            return shape_keys

        return None

    def find_node(self, name):

        for nodeRef in self.nodeArray.items():
            if nodeRef[0].name == name:
                return nodeRef
        return None

    # TODO: We can probably do without this method:
    @staticmethod
    def deindex_mesh(mesh, material_table):

        # This function deindexes all vertex positions, colors, and texcoords.
        # Three separate ExportVertex structures are created for each triangle.

        vertex_array = mesh.vertices
        export_vertex_array = []
        face_index = 0

        for face in mesh.tessfaces:

            list = [0, 1, 2]
            material_table.append(face.material_index)

            if len(face.vertices) == 4:
                list = list + [0, 2, 3]
                material_table.append(face.material_index)

            for i in list:
                vertex_index = face.vertices[i]
                vertex = vertex_array[vertex_index]

                export_vertex = ExportVertex()
                export_vertex.vertexIndex = vertex_index
                export_vertex.faceIndex = face_index
                export_vertex.position = vertex.co
                export_vertex.normal = vertex.normal if face.use_smooth else face.normal
                export_vertex_array.append(export_vertex)

            face_index += 1

        color_count = len(mesh.tessface_vertex_colors)
        if color_count > 0:
            color_face = mesh.tessface_vertex_colors[0].data
            vertex_index = 0
            face_index = 0

            for face in mesh.tessfaces:
                cf = color_face[face_index]
                export_vertex_array[vertex_index].color = cf.color1
                vertex_index += 1
                export_vertex_array[vertex_index].color = cf.color2
                vertex_index += 1
                export_vertex_array[vertex_index].color = cf.color3
                vertex_index += 1

                if len(face.vertices) == 4:
                    export_vertex_array[vertex_index].color = cf.color1
                    vertex_index += 1
                    export_vertex_array[vertex_index].color = cf.color3
                    vertex_index += 1
                    export_vertex_array[vertex_index].color = cf.color4
                    vertex_index += 1

                face_index += 1

        # go through all UV maps and add all active_render to a list
        active_tessface_uv_textures = []  # the first two uv maps will be inserted into this array
        texcoord_count = 0  # number of UV maps, max 2

        # find first two active uv maps
        for index in range(len(mesh.tessface_uv_textures)):
            if mesh.uv_textures[index].active_render:
                active_tessface_uv_textures.append(mesh.tessface_uv_textures[index])
                texcoord_count += 1
                if texcoord_count == 1:
                    break

        for texCoordIndex in range(0, texcoord_count):
            texcoord_attrib = "texcoord" + str(texCoordIndex)

            texcoord_face = active_tessface_uv_textures[texCoordIndex].data
            vertex_index = 0
            face_index = 0

            for face in mesh.tessfaces:
                tf = texcoord_face[face_index]

                uvs = [tf.uv1, tf.uv2, tf.uv3]
                if len(face.vertices) == 4:
                    uvs = uvs + [tf.uv1, tf.uv3, tf.uv4]

                for uv in uvs:
                    setattr(export_vertex_array[vertex_index], texcoord_attrib, uv)
                    vertex_index += 1

                face_index += 1

        for ev in export_vertex_array:
            ev.get_hash()

        return export_vertex_array

    @staticmethod
    def find_export_vertex(bucket, export_vertex_array, vertex):

        for index in bucket:
            if export_vertex_array[index] == vertex:
                return index

        return -1

    @staticmethod
    def unify_vertices(export_vertex_array, index_table):

        # This function looks for identical vertices having exactly the same position, normal,
        # color, and texcoords. Duplicate vertices are unified, and a new index table is returned.

        bucket_count = len(export_vertex_array) >> 3
        if bucket_count > 1:

            # Round down to nearest power of two.

            while True:
                count = bucket_count & (bucket_count - 1)
                if count == 0:
                    break
                bucket_count = count
        else:
            bucket_count = 1

        hash_table = [[] for i in range(bucket_count)]
        unified_vertex_array = []

        for i in range(len(export_vertex_array)):
            ev = export_vertex_array[i]
            bucket = ev.get_hash & (bucket_count - 1)
            index = OpenGexExporter.find_export_vertex(hash_table[bucket], export_vertex_array, ev)
            if index < 0:
                index_table.append(len(unified_vertex_array))
                unified_vertex_array.append(ev)
                hash_table[bucket].append(i)
            else:
                index_table.append(index_table[index])

        return unified_vertex_array

    @staticmethod
    def classify_animation_curve(fcurve):

        linear_count = 0
        bezier_count = 0

        for key in fcurve.keyframe_points:
            interp = key.interpolation
            if interp == "LINEAR":
                linear_count += 1
            elif interp == "BEZIER":
                bezier_count += 1
            else:
                return kAnimationSampled

        if bezier_count == 0:
            return kAnimationLinear
        elif linear_count == 0:
            return kAnimationBezier

        return kAnimationSampled

    @staticmethod
    def animation_keys_differ(fcurve):

        key_count = len(fcurve.keyframe_points)
        if key_count > 0:
            key1 = fcurve.keyframe_points[0].co[1]

            for i in range(1, key_count):
                key2 = fcurve.keyframe_points[i].co[1]
                if math.fabs(key2 - key1) > kExportEpsilon:
                    return True

        return False

    @staticmethod
    def animation_tangents_nonzero(fcurve):

        key_count = len(fcurve.keyframe_points)
        if key_count > 0:
            key = fcurve.keyframe_points[0].co[1]
            left = fcurve.keyframe_points[0].handle_left[1]
            right = fcurve.keyframe_points[0].handle_right[1]
            if (math.fabs(key - left) > kExportEpsilon) or (math.fabs(right - key) > kExportEpsilon):
                return True

            for i in range(1, key_count):
                key = fcurve.keyframe_points[i].co[1]
                left = fcurve.keyframe_points[i].handle_left[1]
                right = fcurve.keyframe_points[i].handle_right[1]
                if (math.fabs(key - left) > kExportEpsilon) or (math.fabs(right - key) > kExportEpsilon):
                    return True

        return False

    @staticmethod
    def animation_present(fcurve, kind):

        if kind != kAnimationBezier:
            return OpenGexExporter.animation_keys_differ(fcurve)

        return (OpenGexExporter.animation_keys_differ(fcurve)) or (OpenGexExporter.animation_tangents_nonzero(fcurve))

    @staticmethod
    def matrices_differ(m1, m2):

        for i in range(4):
            for j in range(4):
                if math.fabs(m1[i][j] - m2[i][j]) > kExportEpsilon:
                    return True

        return False

    @staticmethod
    def export_bone_animation(armature, name):

        path = "pose.bones[\"" + name + "\"]."
        curve_array = []

        if armature.animation_data:
            action = armature.animation_data.action
            if action:
                for fcurve in action.fcurves:
                    if fcurve.data_path.startswith(path):
                        curve_array.append(fcurve)

        return curve_array

    def export_key_times(self, fcurve):

        self.IndentWrite(B"Key {float {")

        key_count = len(fcurve.keyframe_points)
        for i in range(key_count):
            if i > 0:
                self.file.write(B", ")

            time = fcurve.keyframe_points[i].co[0] - self.container.beginFrame
            self.WriteFloat(time * self.container.frameTime)

        self.file.write(B"}}\n")

    def export_key_time_control_points(self, fcurve):

        self.IndentWrite(B"Key (kind = \"-control\") {float {")

        key_count = len(fcurve.keyframe_points)
        for i in range(key_count):
            if i > 0:
                self.file.write(B", ")

            ctrl = fcurve.keyframe_points[i].handle_left[0] - self.container.beginFrame
            self.WriteFloat(ctrl * self.container.frameTime)

        self.file.write(B"}}\n")
        self.IndentWrite(B"Key (kind = \"+control\") {float {")

        for i in range(key_count):
            if i > 0:
                self.file.write(B", ")

            ctrl = fcurve.keyframe_points[i].handle_right[0] - self.container.beginFrame
            self.WriteFloat(ctrl * self.container.frameTime)

        self.file.write(B"}}\n")

    def export_key_values(self, fcurve):

        self.IndentWrite(B"Key {float {")

        key_count = len(fcurve.keyframe_points)
        for i in range(key_count):
            if i > 0:
                self.file.write(B", ")

            value = fcurve.keyframe_points[i].co[1]
            self.WriteFloat(value)

        self.file.write(B"}}\n")

    def export_key_value_control_points(self, fcurve):

        self.IndentWrite(B"Key (kind = \"-control\") {float {")

        key_count = len(fcurve.keyframe_points)
        for i in range(key_count):
            if i > 0:
                self.file.write(B", ")

            ctrl = fcurve.keyframe_points[i].handle_left[1]
            self.WriteFloat(ctrl)

        self.file.write(B"}}\n")
        self.IndentWrite(B"Key (kind = \"+control\") {float {")

        for i in range(key_count):
            if i > 0:
                self.file.write(B", ")

            ctrl = fcurve.keyframe_points[i].handle_right[1]
            self.WriteFloat(ctrl)

        self.file.write(B"}}\n")

    def export_animation_track(self, fcurve, kind, target, newline):
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
        # This function exports animation as full 4x4 matrices for each frame.

        current_frame = scene.frame_current
        current_subframe = scene.frame_subframe

        has_animation = False
        m1 = node.matrix_local.copy()

        for i in range(self.container.beginFrame, self.container.endFrame):
            scene.frame_set(i)
            m2 = node.matrix_local
            if OpenGexExporter.matrices_differ(m1, m2):
                has_animation = True
                break

        if has_animation:
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

        scene.frame_set(current_frame, current_subframe)

    def export_bone_sampled_animation(self, pose_bone, scene):
        # This function exports bone animation as full 4x4 matrices for each frame.

        current_frame = scene.frame_current
        current_subframe = scene.frame_subframe

        has_animation = False
        m1 = pose_bone.matrix.copy()

        for i in range(self.container.beginFrame, self.container.endFrame):
            scene.frame_set(i)
            m2 = pose_bone.matrix
            if OpenGexExporter.matrices_differ(m1, m2):
                has_animation = True
                break

        if has_animation:
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

            parent = pose_bone.parent
            if parent:
                for i in range(self.container.beginFrame, self.container.endFrame):
                    scene.frame_set(i)
                    if math.fabs(parent.matrix.determinant()) > kExportEpsilon:
                        self.WriteMatrixFlat(parent.matrix.inverted() * pose_bone.matrix)
                    else:
                        self.WriteMatrixFlat(pose_bone.matrix)

                    self.file.write(B",\n")

                scene.frame_set(self.container.endFrame)
                if math.fabs(parent.matrix.determinant()) > kExportEpsilon:
                    self.WriteMatrixFlat(parent.matrix.inverted() * pose_bone.matrix)
                else:
                    self.WriteMatrixFlat(pose_bone.matrix)

                self.IndentWrite(B"}\n", 0, True)

            else:
                for i in range(self.container.beginFrame, self.container.endFrame):
                    scene.frame_set(i)
                    self.WriteMatrixFlat(pose_bone.matrix)
                    self.file.write(B",\n")

                scene.frame_set(self.container.endFrame)
                self.WriteMatrixFlat(pose_bone.matrix)
                self.IndentWrite(B"}\n", 0, True)

            self.DecIndent()
            self.IndentWrite(B"}\n")

            self.DecIndent()
            self.IndentWrite(B"}\n")

            self.DecIndent()
            self.IndentWrite(B"}\n")

            self.DecIndent()
            self.IndentWrite(B"}\n")

        scene.frame_set(current_frame, current_subframe)

    def export_morph_weight_sampled_animation_track(self, block, target, scene, newline):

        current_frame = scene.frame_current
        current_subframe = scene.frame_subframe

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

        scene.frame_set(current_frame, current_subframe)

    # FIXME Handle NodeWrapper
    def export_node_transformation(self, nw, scene):
        node = nw.item

        pos_anim_curve = [None, None, None]
        rot_anim_curve = [None, None, None]
        scale_anim_curve = [None, None, None]
        pos_anim_kind = [0, 0, 0]
        rot_anim_kind = [0, 0, 0]
        scale_anim_kind = [0, 0, 0]

        delta_pos_anim_curve = [None, None, None]
        delta_rot_anim_curve = [None, None, None]
        delta_scale_anim_curve = [None, None, None]
        delta_pos_anim_kind = [0, 0, 0]
        delta_rot_anim_kind = [0, 0, 0]
        delta_scale_anim_kind = [0, 0, 0]

        pos_animated = [False, False, False]
        rot_animated = [False, False, False]
        scl_animated = [False, False, False]

        delta_pos_animated = [False, False, False]
        delta_rot_animated = [False, False, False]
        delta_scl_animated = [False, False, False]

        mode = node.rotation_mode
        sampled_animation = (self.container.sampleAnimationFlag or (mode == "QUATERNION") or (mode == "AXIS_ANGLE"))

        if (not sampled_animation) and node.animation_data:
            action = node.animation_data.action
            if action:
                for fcurve in action.fcurves:
                    kind = OpenGexExporter.classify_animation_curve(fcurve)
                    if kind != kAnimationSampled:
                        if fcurve.data_path == "location":
                            for i in range(3):
                                if (fcurve.array_index == i) and (not pos_anim_curve[i]):
                                    pos_anim_curve[i] = fcurve
                                    pos_anim_kind[i] = kind
                                    if OpenGexExporter.animation_present(fcurve, kind):
                                        pos_animated[i] = True
                        elif fcurve.data_path == "delta_location":
                            for i in range(3):
                                if (fcurve.array_index == i) and (not delta_pos_anim_curve[i]):
                                    delta_pos_anim_curve[i] = fcurve
                                    delta_pos_anim_kind[i] = kind
                                    if OpenGexExporter.animation_present(fcurve, kind):
                                        delta_pos_animated[i] = True
                        elif fcurve.data_path == "rotation_euler":
                            for i in range(3):
                                if (fcurve.array_index == i) and (not rot_anim_curve[i]):
                                    rot_anim_curve[i] = fcurve
                                    rot_anim_kind[i] = kind
                                    if OpenGexExporter.animation_present(fcurve, kind):
                                        rot_animated[i] = True
                        elif fcurve.data_path == "delta_rotation_euler":
                            for i in range(3):
                                if (fcurve.array_index == i) and (not delta_rot_anim_curve[i]):
                                    delta_rot_anim_curve[i] = fcurve
                                    delta_rot_anim_kind[i] = kind
                                    if OpenGexExporter.animation_present(fcurve, kind):
                                        delta_rot_animated[i] = True
                        elif fcurve.data_path == "scale":
                            for i in range(3):
                                if (fcurve.array_index == i) and (not scale_anim_curve[i]):
                                    scale_anim_curve[i] = fcurve
                                    scale_anim_kind[i] = kind
                                    if OpenGexExporter.animation_present(fcurve, kind):
                                        scl_animated[i] = True
                        elif fcurve.data_path == "delta_scale":
                            for i in range(3):
                                if (fcurve.array_index == i) and (not delta_scale_anim_curve[i]):
                                    delta_scale_anim_curve[i] = fcurve
                                    delta_scale_anim_kind[i] = kind
                                    if OpenGexExporter.animation_present(fcurve, kind):
                                        delta_scl_animated[i] = True
                        elif ((fcurve.data_path == "rotation_axis_angle") or (
                                    fcurve.data_path == "rotation_quaternion") or (
                                    fcurve.data_path == "delta_rotation_quaternion")):
                            sampled_animation = True
                            break
                    else:
                        sampled_animation = True
                        break

        position_animated = pos_animated[0] | pos_animated[1] | pos_animated[2]
        rotation_animated = rot_animated[0] | rot_animated[1] | rot_animated[2]
        scale_animated = scl_animated[0] | scl_animated[1] | scl_animated[2]

        delta_position_animated = delta_pos_animated[0] | delta_pos_animated[1] | delta_pos_animated[2]
        delta_rotation_animated = delta_rot_animated[0] | delta_rot_animated[1] | delta_rot_animated[2]
        delta_scale_animated = delta_scl_animated[0] | delta_scl_animated[1] | delta_scl_animated[2]

        if (sampled_animation or ((not position_animated) and (not rotation_animated) and (not scale_animated) and (
                not delta_position_animated) and (not delta_rotation_animated) and (not delta_scale_animated))):

            # If there's no keyframe animation at all, then write the node transform as a single 4x4 matrix.
            # We might still be exporting sampled animation below.

            self.IndentWrite(B"Transform")

            if sampled_animation:
                self.file.write(B" %transform")

            self.IndentWrite(B"{\n", 0, True)
            self.IncIndent()

            self.IndentWrite(B"float[16]\n")
            self.IndentWrite(B"{\n")

            self.handle_offset(node.matrix_local, nw.offset)
            self.IndentWrite(B"}\n")

            self.DecIndent()
            self.IndentWrite(B"}\n")

            if sampled_animation:
                self.export_node_sampled_animation(node, scene)

        else:
            struct_flag = False

            delta_translation = node.delta_location
            if delta_position_animated:

                # When the delta location is animated, write the x, y, and z components separately
                # so they can be targeted by different tracks having different sets of keys.

                for i in range(3):
                    pos = delta_translation[i]
                    if (delta_pos_animated[i]) or (math.fabs(pos) > kExportEpsilon):
                        self.IndentWrite(B"Translation %", 0, struct_flag)
                        self.file.write(deltaSubtranslationName[i])
                        self.file.write(B" (kind = \"")
                        self.file.write(axisName[i])
                        self.file.write(B"\")\n")
                        self.IndentWrite(B"{\n")
                        self.IndentWrite(B"float {", 1)
                        self.WriteFloat(pos)
                        self.file.write(B"}")
                        self.IndentWrite(B"}\n", 0, True)

                        struct_flag = True

            elif ((math.fabs(delta_translation[0]) > kExportEpsilon) or (
                        math.fabs(delta_translation[1]) > kExportEpsilon) or (
                        math.fabs(delta_translation[2]) > kExportEpsilon)):
                self.IndentWrite(B"Translation\n")
                self.IndentWrite(B"{\n")
                self.IndentWrite(B"float[3] {", 1)
                self.WriteVector3D(delta_translation)
                self.file.write(B"}")
                self.IndentWrite(B"}\n", 0, True)

                struct_flag = True

            translation = node.location
            if position_animated:

                # When the location is animated, write the x, y, and z components separately
                # so they can be targeted by different tracks having different sets of keys.

                for i in range(3):
                    pos = translation[i]
                    if (pos_animated[i]) or (math.fabs(pos) > kExportEpsilon):
                        self.IndentWrite(B"Translation %", 0, struct_flag)
                        self.file.write(subtranslationName[i])
                        self.file.write(B" (kind = \"")
                        self.file.write(axisName[i])
                        self.file.write(B"\")\n")
                        self.IndentWrite(B"{\n")
                        self.IndentWrite(B"float {", 1)
                        self.WriteFloat(pos)
                        self.file.write(B"}")
                        self.IndentWrite(B"}\n", 0, True)

                        struct_flag = True

            elif ((math.fabs(translation[0]) > kExportEpsilon) or (math.fabs(translation[1]) > kExportEpsilon) or (
                        math.fabs(translation[2]) > kExportEpsilon)):
                self.IndentWrite(B"Translation\n")
                self.IndentWrite(B"{\n")
                self.IndentWrite(B"float[3] {", 1)
                self.WriteVector3D(translation)
                self.file.write(B"}")
                self.IndentWrite(B"}\n", 0, True)

                struct_flag = True

            if delta_rotation_animated:

                # When the delta rotation is animated, write three separate Euler angle rotations
                # so they can be targeted by different tracks having different sets of keys.

                for i in range(3):
                    axis = ord(mode[2 - i]) - 0x58
                    angle = node.delta_rotation_euler[axis]
                    if (delta_rot_animated[axis]) or (math.fabs(angle) > kExportEpsilon):
                        self.IndentWrite(B"Rotation %", 0, struct_flag)
                        self.file.write(deltaSubrotationName[axis])
                        self.file.write(B" (kind = \"")
                        self.file.write(axisName[axis])
                        self.file.write(B"\")\n")
                        self.IndentWrite(B"{\n")
                        self.IndentWrite(B"float {", 1)
                        self.WriteFloat(angle)
                        self.file.write(B"}")
                        self.IndentWrite(B"}\n", 0, True)

                        struct_flag = True

            else:

                # When the delta rotation is not animated, write it in the representation given by
                # the node's current rotation mode. (There is no axis-angle delta rotation.)

                if mode == "QUATERNION":
                    quaternion = node.delta_rotation_quaternion
                    if ((math.fabs(quaternion[0] - 1.0) > kExportEpsilon) or (
                                math.fabs(quaternion[1]) > kExportEpsilon) or (
                                math.fabs(quaternion[2]) > kExportEpsilon) or (
                                math.fabs(quaternion[3]) > kExportEpsilon)):
                        self.IndentWrite(B"Rotation (kind = \"quaternion\")\n", 0, struct_flag)
                        self.IndentWrite(B"{\n")
                        self.IndentWrite(B"float[4] {", 1)
                        self.WriteQuaternion(quaternion)
                        self.file.write(B"}")
                        self.IndentWrite(B"}\n", 0, True)

                        struct_flag = True

                else:
                    for i in range(3):
                        axis = ord(mode[2 - i]) - 0x58
                        angle = node.delta_rotation_euler[axis]
                        if math.fabs(angle) > kExportEpsilon:
                            self.IndentWrite(B"Rotation (kind = \"", 0, struct_flag)
                            self.file.write(axisName[axis])
                            self.file.write(B"\")\n")
                            self.IndentWrite(B"{\n")
                            self.IndentWrite(B"float {", 1)
                            self.WriteFloat(angle)
                            self.file.write(B"}")
                            self.IndentWrite(B"}\n", 0, True)

                            struct_flag = True

            if rotation_animated:

                # When the rotation is animated, write three separate Euler angle rotations
                # so they can be targeted by different tracks having different sets of keys.

                for i in range(3):
                    axis = ord(mode[2 - i]) - 0x58
                    angle = node.rotation_euler[axis]
                    if (rot_animated[axis]) or (math.fabs(angle) > kExportEpsilon):
                        self.IndentWrite(B"Rotation %", 0, struct_flag)
                        self.file.write(subrotationName[axis])
                        self.file.write(B" (kind = \"")
                        self.file.write(axisName[axis])
                        self.file.write(B"\")\n")
                        self.IndentWrite(B"{\n")
                        self.IndentWrite(B"float {", 1)
                        self.WriteFloat(angle)
                        self.file.write(B"}")
                        self.IndentWrite(B"}\n", 0, True)

                        struct_flag = True

            else:

                # When the rotation is not animated, write it in the representation given by
                # the node's current rotation mode.

                if mode == "QUATERNION":
                    quaternion = node.rotation_quaternion
                    if ((math.fabs(quaternion[0] - 1.0) > kExportEpsilon) or (
                                math.fabs(quaternion[1]) > kExportEpsilon) or (
                                math.fabs(quaternion[2]) > kExportEpsilon) or (
                                math.fabs(quaternion[3]) > kExportEpsilon)):
                        self.IndentWrite(B"Rotation (kind = \"quaternion\")\n", 0, struct_flag)
                        self.IndentWrite(B"{\n")
                        self.IndentWrite(B"float[4] {", 1)
                        self.WriteQuaternion(quaternion)
                        self.file.write(B"}")
                        self.IndentWrite(B"}\n", 0, True)

                        struct_flag = True

                elif mode == "AXIS_ANGLE":
                    if math.fabs(node.rotation_axis_angle[0]) > kExportEpsilon:
                        self.IndentWrite(B"Rotation (kind = \"axis\")\n", 0, struct_flag)
                        self.IndentWrite(B"{\n")
                        self.IndentWrite(B"float[4] {", 1)
                        self.WriteVector4D(node.rotation_axis_angle)
                        self.file.write(B"}")
                        self.IndentWrite(B"}\n", 0, True)

                        struct_flag = True

                else:
                    for i in range(3):
                        axis = ord(mode[2 - i]) - 0x58
                        angle = node.rotation_euler[axis]
                        if math.fabs(angle) > kExportEpsilon:
                            self.IndentWrite(B"Rotation (kind = \"", 0, struct_flag)
                            self.file.write(axisName[axis])
                            self.file.write(B"\")\n")
                            self.IndentWrite(B"{\n")
                            self.IndentWrite(B"float {", 1)
                            self.WriteFloat(angle)
                            self.file.write(B"}")
                            self.IndentWrite(B"}\n", 0, True)

                            struct_flag = True

            delta_scale = node.delta_scale
            if delta_scale_animated:

                # When the delta scale is animated, write the x, y, and z components separately
                # so they can be targeted by different tracks having different sets of keys.

                for i in range(3):
                    scl = delta_scale[i]
                    if (delta_scl_animated[i]) or (math.fabs(scl) > kExportEpsilon):
                        self.IndentWrite(B"Scale %", 0, struct_flag)
                        self.file.write(delta_subscale_name[i])
                        self.file.write(B" (kind = \"")
                        self.file.write(axisName[i])
                        self.file.write(B"\")\n")
                        self.IndentWrite(B"{\n")
                        self.IndentWrite(B"float {", 1)
                        self.WriteFloat(scl)
                        self.file.write(B"}")
                        self.IndentWrite(B"}\n", 0, True)

                        struct_flag = True

            elif ((math.fabs(delta_scale[0] - 1.0) > kExportEpsilon) or (
                        math.fabs(delta_scale[1] - 1.0) > kExportEpsilon) or (
                        math.fabs(delta_scale[2] - 1.0) > kExportEpsilon)):
                self.IndentWrite(B"Scale\n", 0, struct_flag)
                self.IndentWrite(B"{\n")
                self.IndentWrite(B"float[3] {", 1)
                self.WriteVector3D(delta_scale)
                self.file.write(B"}")
                self.IndentWrite(B"}\n", 0, True)

                struct_flag = True

            scale = node.scale
            if scale_animated:

                # When the scale is animated, write the x, y, and z components separately
                # so they can be targeted by different tracks having different sets of keys.

                for i in range(3):
                    scl = scale[i]
                    if (scl_animated[i]) or (math.fabs(scl) > kExportEpsilon):
                        self.IndentWrite(B"Scale %", 0, struct_flag)
                        self.file.write(subscaleName[i])
                        self.file.write(B" (kind = \"")
                        self.file.write(axisName[i])
                        self.file.write(B"\")\n")
                        self.IndentWrite(B"{\n")
                        self.IndentWrite(B"float {", 1)
                        self.WriteFloat(scl)
                        self.file.write(B"}")
                        self.IndentWrite(B"}\n", 0, True)

                        struct_flag = True

            elif ((math.fabs(scale[0] - 1.0) > kExportEpsilon) or (math.fabs(scale[1] - 1.0) > kExportEpsilon) or (
                        math.fabs(scale[2] - 1.0) > kExportEpsilon)):
                self.IndentWrite(B"Scale\n", 0, struct_flag)
                self.IndentWrite(B"{\n")
                self.IndentWrite(B"float[3] {", 1)
                self.WriteVector3D(scale)
                self.file.write(B"}")
                self.IndentWrite(B"}\n", 0, True)

                struct_flag = True

            # Export the animation tracks.

            self.IndentWrite(B"Animation (begin = ", 0, True)
            self.WriteFloat((action.frame_range[0] - self.container.beginFrame) * self.container.frameTime)
            self.file.write(B", end = ")
            self.WriteFloat((action.frame_range[1] - self.container.beginFrame) * self.container.frameTime)
            self.file.write(B")\n")
            self.IndentWrite(B"{\n")
            self.IncIndent()

            struct_flag = False

            if position_animated:
                for i in range(3):
                    if pos_animated[i]:
                        self.export_animation_track(pos_anim_curve[i], pos_anim_kind[i], subtranslationName[i],
                                                    struct_flag)
                        struct_flag = True

            if rotation_animated:
                for i in range(3):
                    if rot_animated[i]:
                        self.export_animation_track(rot_anim_curve[i], rot_anim_kind[i], subrotationName[i],
                                                    struct_flag)
                        struct_flag = True

            if scale_animated:
                for i in range(3):
                    if scl_animated[i]:
                        self.export_animation_track(scale_anim_curve[i], scale_anim_kind[i], subscaleName[i],
                                                    struct_flag)
                        struct_flag = True

            if delta_position_animated:
                for i in range(3):
                    if delta_pos_animated[i]:
                        self.export_animation_track(delta_pos_anim_curve[i], delta_pos_anim_kind[i],
                                                    deltaSubtranslationName[i],
                                                    struct_flag)
                        struct_flag = True

            if delta_rotation_animated:
                for i in range(3):
                    if delta_rot_animated[i]:
                        self.export_animation_track(delta_rot_anim_curve[i], delta_rot_anim_kind[i],
                                                    deltaSubrotationName[i],
                                                    struct_flag)
                        struct_flag = True

            if delta_scale_animated:
                for i in range(3):
                    if delta_scl_animated[i]:
                        self.export_animation_track(delta_scale_anim_curve[i], delta_scale_anim_kind[i],
                                                    delta_subscale_name[i],
                                                    struct_flag)
                        struct_flag = True

            self.DecIndent()
            self.IndentWrite(B"}\n")

    def handle_offset(self, matrix, offset):

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

        curve_array = self.export_bone_animation(nw.item, bw.item.name)
        animation = ((len(curve_array) != 0) or self.container.sampleAnimationFlag)

        transform = bw.item.matrix_local.copy()
        parent_bone_wrapper = bw.parent
        if parent_bone_wrapper and (math.fabs(parent_bone_wrapper.item.matrix_local.determinant()) > kExportEpsilon):
            transform = parent_bone_wrapper.item.matrix_local.inverted() * transform

        pose_bone = nw.item.pose.bones.get(bw.item.name)
        if pose_bone:
            transform = pose_bone.matrix.copy()
            parent_pose_bone = pose_bone.parent
            if parent_pose_bone and (math.fabs(parent_pose_bone.matrix.determinant()) > kExportEpsilon):
                transform = parent_pose_bone.matrix.inverted() * transform

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

        if animation and pose_bone:
            self.export_bone_sampled_animation(pose_bone, scene)

    def export_material_ref(self, material, index):

        if material not in self.container.materialArray:
            self.container.materialArray[material] = \
                {"structName": bytes("material" + str(len(self.container.materialArray) + 1), "UTF-8")}

        self.IndentWrite(B"MaterialRef (index = ")
        self.WriteInt(index)
        self.file.write(B") {ref {$")
        self.file.write(self.container.materialArray[material]["structName"])
        self.file.write(B"}}\n")

    def export_morph_weights(self, node, shape_keys, scene):

        action = None
        curve_array = []
        index_array = []

        if shape_keys.animation_data:
            action = shape_keys.animation_data.action
            if action:
                for fcurve in action.fcurves:
                    if (fcurve.data_path.startswith("key_blocks[")) and (fcurve.data_path.endswith("].value")):
                        key_name = fcurve.data_path.strip("abcdehklopstuvy[]_.")
                        if (key_name[0] == "\"") or (key_name[0] == "'"):
                            index = shape_keys.key_blocks.find(key_name.strip("\"'"))
                            if index >= 0:
                                curve_array.append(fcurve)
                                index_array.append(index)
                        else:
                            curve_array.append(fcurve)
                            index_array.append(int(key_name))

        if (not action) and node.animation_data:
            action = node.animation_data.action
            if action:
                for fcurve in action.fcurves:
                    if ((fcurve.data_path.startswith("data.shape_keys.key_blocks[")) and (
                            fcurve.data_path.endswith("].value"))):
                        key_name = fcurve.data_path.strip("abcdehklopstuvy[]_.")
                        if (key_name[0] == "\"") or (key_name[0] == "'"):
                            index = shape_keys.key_blocks.find(key_name.strip("\"'"))
                            if index >= 0:
                                curve_array.append(fcurve)
                                index_array.append(index)
                        else:
                            curve_array.append(fcurve)
                            index_array.append(int(key_name))

        animated = (len(curve_array) != 0)
        reference_name = shape_keys.reference_key.name if shape_keys.use_relative else ""

        for k in range(len(shape_keys.key_blocks)):
            self.IndentWrite(B"MorphWeight", 0, (k == 0))

            if animated:
                self.file.write(B" %mw")
                self.WriteInt(k)

            self.file.write(B" (index = ")
            self.WriteInt(k)
            self.file.write(B") {float {")

            block = shape_keys.key_blocks[k]
            self.WriteFloat(block.value if (block.name != reference_name) else 1.0)

            self.file.write(B"}}\n")

        if animated:
            self.IndentWrite(B"Animation (begin = ", 0, True)
            self.WriteFloat((action.frame_range[0] - self.container.beginFrame) * self.container.frameTime)
            self.file.write(B", end = ")
            self.WriteFloat((action.frame_range[1] - self.container.beginFrame) * self.container.frameTime)
            self.file.write(B")\n")
            self.IndentWrite(B"{\n")
            self.IncIndent()

            struct_flag = False

            for a in range(len(curve_array)):
                k = index_array[a]
                target = bytes("mw" + str(k), "UTF-8")

                fcurve = curve_array[a]
                kind = OpenGexExporter.classify_animation_curve(fcurve)
                if (kind != kAnimationSampled) and (not self.container.sampleAnimationFlag):
                    self.export_animation_track(fcurve, kind, target, struct_flag)
                else:
                    self.export_morph_weight_sampled_animation_track(shape_keys.key_blocks[k], target, scene, struct_flag)

                struct_flag = True

            self.DecIndent()
            self.IndentWrite(B"}\n")

    def export_bone(self, nw, bw, scene):  # armature, bone, scene):

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

        bone_subnode_array = self.container.boneParentArray.get(bw.item.name)
        if bone_subnode_array:
            pose_bone = None
            if not bw.item.use_relative_parent:
                pose_bone = nw.item.pose.bones.get(bw.item.name)

            for subnode_wrapper in bone_subnode_array:
                self.export_node(subnode_wrapper, scene, pose_bone)

        if nw.nodeRef:
            self.DecIndent()
            self.IndentWrite(B"}\n")

    def export_node(self, nw, scene, pose_bone=None):

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

            struct_flag = False

            # Export the node's name if it has one.

            name = nw.item.name
            if name != "":
                self.IndentWrite(B"Name {string {\"")
                self.file.write(bytes(name, "UTF-8"))
                self.file.write(B"\"}}\n")
                struct_flag = True

            # Export the object reference and material references.

            obj = nw.item.data

            if type == kNodeTypeGeometry:
                if obj not in self.container.geometryArray:
                    self.container.geometryArray[obj] = {
                        "structName": bytes("geometry" + str(len(self.container.geometryArray) + 1), "UTF-8"),
                        "nodeTable": [nw.item]}
                else:
                    self.container.geometryArray[obj]["nodeTable"].append(nw.item)

                self.IndentWrite(B"ObjectRef {ref {$")
                self.file.write(self.container.geometryArray[obj]["structName"])
                self.file.write(B"}}\n")

                for i in range(len(nw.item.material_slots)):
                    self.export_material_ref(nw.item.material_slots[i].material, i)

                shape_keys = OpenGexExporter.get_shape_keys(obj)
                if shape_keys:
                    # FIXME Wrapper or item?
                    self.export_morph_weights(nw.item, shape_keys, scene)

                struct_flag = True

            elif type == kNodeTypeLight:
                if obj not in self.container.lightArray:
                    self.container.lightArray[obj] = \
                        {"structName": bytes("light" + str(len(self.container.lightArray) + 1), "UTF-8"),
                         "nodeTable": [nw.item]}
                else:
                    self.container.lightArray[obj]["nodeTable"].append(nw.item)

                self.IndentWrite(B"ObjectRef {ref {$")
                self.file.write(self.container.lightArray[obj]["structName"])
                self.file.write(B"}}\n")
                struct_flag = True

            elif type == kNodeTypeCamera:
                if obj not in self.container.cameraArray:
                    self.container.cameraArray[obj] = \
                        {"structName": bytes("camera" + str(len(self.container.cameraArray) + 1), "UTF-8"),
                         "nodeTable": [nw.item]}
                else:
                    self.container.cameraArray[obj]["nodeTable"].append(nw.item)

                self.IndentWrite(B"ObjectRef {ref {$")
                self.file.write(self.container.cameraArray[obj]["structName"])
                self.file.write(B"}}\n")
                struct_flag = True

            if struct_flag:
                self.file.write(B"\n")

            if pose_bone:
                # If the node is parented to a bone and is not relative, then undo the bone's transform.

                if math.fabs(pose_bone.matrix.determinant()) > kExportEpsilon:
                    self.IndentWrite(B"Transform\n")
                    self.IndentWrite(B"{\n")
                    self.IncIndent()

                    self.IndentWrite(B"float[16]\n")
                    self.IndentWrite(B"{\n")
                    self.WriteMatrix(pose_bone.matrix.inverted())
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

    def export_skin(self, node, armature, export_vertex_array):

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

        self.IndentWrite(B"bone_refArray\n")
        self.IndentWrite(B"{\n")
        self.IncIndent()

        bone_array = armature.data.bones
        bone_count = len(bone_array)

        self.IndentWrite(B"ref\t\t\t// ")
        self.WriteInt(bone_count)
        self.IndentWrite(B"{\n", 0, True)
        self.IndentWrite(B"", 1)

        for i in range(bone_count):
            bone_ref = self.find_node(bone_array[i].name)
            if bone_ref:
                self.file.write(B"$")
                self.file.write(bone_ref[1]["structName"])
            else:
                self.file.write(B"null")

            if i < bone_count - 1:
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
        self.WriteInt(bone_count)
        self.IndentWrite(B"{\n", 0, True)

        for i in range(bone_count):
            self.WriteMatrixFlat(armature.matrix_world * bone_array[i].matrix_local)
            if i < bone_count - 1:
                self.file.write(B",\n")

        self.IndentWrite(B"}\n", 0, True)

        self.DecIndent()
        self.IndentWrite(B"}\n")

        self.DecIndent()
        self.IndentWrite(B"}\n\n")

        # Export the per-vertex bone influence data.

        group_remap = []

        for group in node.vertex_groups:
            groupName = group.name
            for i in range(bone_count):
                if bone_array[i].name == groupName:
                    group_remap.append(i)
                    break
            else:
                group_remap.append(-1)

        bone_count_array = []
        bone_index_array = []
        bone_weight_array = []

        mesh_vertex_array = node.data.vertices
        for ev in export_vertex_array:
            bone_count = 0
            total_weight = 0.0
            for element in mesh_vertex_array[ev.vertexIndex].groups:
                bone_index = group_remap[element.group]
                bone_weight = element.weight
                if (bone_index >= 0) and (bone_weight != 0.0):
                    bone_count += 1
                    total_weight += bone_weight
                    bone_index_array.append(bone_index)
                    bone_weight_array.append(bone_weight)
            bone_count_array.append(bone_count)

            if total_weight != 0.0:
                normalizer = 1.0 / total_weight
                for i in range(-bone_count, 0):
                    bone_weight_array[i] *= normalizer

        # Write the bone count array. There is one entry per vertex.

        self.IndentWrite(B"bone_countArray\n")
        self.IndentWrite(B"{\n")
        self.IncIndent()

        self.IndentWrite(B"unsigned_int16\t\t// ")
        self.WriteInt(len(bone_count_array))
        self.IndentWrite(B"{\n", 0, True)
        self.WriteIntArray(bone_count_array)
        self.IndentWrite(B"}\n")

        self.DecIndent()
        self.IndentWrite(B"}\n\n")

        # Write the bone index array. The number of entries is the sum of the bone counts for all vertices.

        self.IndentWrite(B"BoneIndexArray\n")
        self.IndentWrite(B"{\n")
        self.IncIndent()

        self.IndentWrite(B"unsigned_int16\t\t// ")
        self.WriteInt(len(bone_index_array))
        self.IndentWrite(B"{\n", 0, True)
        self.WriteIntArray(bone_index_array)
        self.IndentWrite(B"}\n")

        self.DecIndent()
        self.IndentWrite(B"}\n\n")

        # Write the bone weight array. The number of entries is the sum of the bone counts for all vertices.

        self.IndentWrite(B"BoneWeightArray\n")
        self.IndentWrite(B"{\n")
        self.IncIndent()

        self.IndentWrite(B"float\t\t// ")
        self.WriteInt(len(bone_weight_array))
        self.IndentWrite(B"{\n", 0, True)
        self.WriteFloatArray(bone_weight_array)
        self.IndentWrite(B"}\n")

        self.DecIndent()
        self.IndentWrite(B"}\n")

        self.DecIndent()
        self.IndentWrite(B"}\n")

    def export_geometry(self, object_ref, scene):

        self.progress.begin_task("Exporting geometry for " + object_ref[1]["nodeTable"][0].name + "...")

        # This function exports a single geometry object.

        self.file.write(B"\nGeometryObject $")
        self.file.write(object_ref[1]["structName"])
        self.WriteNodeTable(object_ref)

        self.file.write(B"\n{\n")
        self.IncIndent()

        node = object_ref[1]["nodeTable"][0]
        mesh = object_ref[0]

        struct_flag = False

        # Save the morph state if necessary.

        active_shape_key_index = node.active_shape_key_index
        show_only_shape_key = node.show_only_shape_key
        current_morph_value = []

        shape_keys = OpenGexExporter.get_shape_keys(mesh)
        if shape_keys:
            node.active_shape_key_index = 0
            node.show_only_shape_key = True

            base_index = 0
            relative = shape_keys.use_relative
            if relative:
                morph_count = 0
                base_name = shape_keys.reference_key.name
                for block in shape_keys.key_blocks:
                    if block.name == base_name:
                        base_index = morph_count
                        break
                    morph_count += 1

            morph_count = 0
            for block in shape_keys.key_blocks:
                current_morph_value.append(block.value)
                block.value = 0.0

                if block.name != "":
                    self.IndentWrite(B"Morph (index = ", 0, struct_flag)
                    self.WriteInt(morph_count)

                    if relative and (morph_count != base_index):
                        self.file.write(B", base = ")
                        self.WriteInt(base_index)

                    self.file.write(B")\n")
                    self.IndentWrite(B"{\n")
                    self.IndentWrite(B"Name {string {\"", 1)
                    self.file.write(bytes(block.name, "UTF-8"))
                    self.file.write(B"\"}}\n")
                    self.IndentWrite(B"}\n")
                    struct_flag = True

                morph_count += 1

            shape_keys.key_blocks[0].value = 1.0
            mesh.update()

        self.IndentWrite(B"Mesh (primitive = \"triangles\")\n", 0, struct_flag)
        self.IndentWrite(B"{\n")
        self.IncIndent()

        armature = node.find_armature()
        apply_modifiers = (not armature)

        # Apply all modifiers to create a new mesh with tessfaces.

        # We don't apply modifiers for a skinned mesh because we need the vertex positions
        # before they are deformed by the armature modifier in order to export the proper
        # bind pose. This does mean that modifiers preceding the armature modifier are ignored,
        # but the Blender API does not provide a reasonable way to retrieve the mesh at an
        # arbitrary stage in the modifier stack.

        export_mesh = node.to_mesh(scene, apply_modifiers, "RENDER", True, False)

        # Triangulate mesh and remap vertices to eliminate duplicates.

        material_table = []
        export_vertex_array = OpenGexExporter.deindex_mesh(export_mesh, material_table)
        triangle_count = len(material_table)

        index_table = []
        unified_vertex_array = OpenGexExporter.unify_vertices(export_vertex_array, index_table)
        vertex_count = len(unified_vertex_array)

        # Write the position array.

        self.IndentWrite(B"VertexArray (attrib = \"position\")\n")
        self.IndentWrite(B"{\n")
        self.IncIndent()

        self.IndentWrite(B"float[3]\t\t// ")
        self.WriteInt(vertex_count)
        self.IndentWrite(B"{\n", 0, True)
        self.WriteVertexArray3D(unified_vertex_array, "position")
        self.IndentWrite(B"}\n")

        self.DecIndent()
        self.IndentWrite(B"}\n\n")

        # Write the normal array.

        self.IndentWrite(B"VertexArray (attrib = \"normal\")\n")
        self.IndentWrite(B"{\n")
        self.IncIndent()

        self.IndentWrite(B"float[3]\t\t// ")
        self.WriteInt(vertex_count)
        self.IndentWrite(B"{\n", 0, True)
        self.WriteVertexArray3D(unified_vertex_array, "normal")
        self.IndentWrite(B"}\n")

        self.DecIndent()
        self.IndentWrite(B"}\n")

        # Write the color array if it exists.

        color_count = len(export_mesh.tessface_vertex_colors)
        if color_count > 0:
            self.IndentWrite(B"VertexArray (attrib = \"color\")\n", 0, True)
            self.IndentWrite(B"{\n")
            self.IncIndent()

            self.IndentWrite(B"float[3]\t\t// ")
            self.WriteInt(vertex_count)
            self.IndentWrite(B"{\n", 0, True)
            self.WriteVertexArray3D(unified_vertex_array, "color")
            self.IndentWrite(B"}\n")

            self.DecIndent()
            self.IndentWrite(B"}\n")

        # Write the texcoord arrays.
        count = 0
        for i in range(len(export_mesh.uv_textures)):
            if export_mesh.uv_textures[i].active_render:
                name = B'texcoord'
                if count > 0:
                    name += B'[' + bytes(str(count)) + B']'
                self.IndentWrite(B"VertexArray (attrib = \"" + name + B"\")\n", 0, True)
                self.IndentWrite(B"{\n")
                self.IncIndent()
                self.IndentWrite(B"float[2]\t\t// ")
                self.WriteInt(vertex_count)
                self.IndentWrite(B"{\n", 0, True)
                self.WriteVertexArray2D(unified_vertex_array, "texcoord" + str(count))
                self.IndentWrite(B"}\n")

                self.DecIndent()
                self.IndentWrite(B"}\n")

                count += 1

                if count > 2:
                    break

        # If there are multiple morph targets, export them here.

        if shape_keys:
            shape_keys.key_blocks[0].value = 0.0
            for m in range(1, len(current_morph_value)):
                shape_keys.key_blocks[m].value = 1.0
                mesh.update()

                node.active_shape_key_index = m
                morph_mesh = node.to_mesh(scene, apply_modifiers, "RENDER", True, False)

                # Write the morph target position array.

                self.IndentWrite(B"VertexArray (attrib = \"position\", morph = ", 0, True)
                self.WriteInt(m)
                self.file.write(B")\n")
                self.IndentWrite(B"{\n")
                self.IncIndent()

                self.IndentWrite(B"float[3]\t\t// ")
                self.WriteInt(vertex_count)
                self.IndentWrite(B"{\n", 0, True)
                self.WriteMorphPositionArray3D(unified_vertex_array, morph_mesh.vertices)
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
                self.WriteInt(vertex_count)
                self.IndentWrite(B"{\n", 0, True)
                self.WriteMorphNormalArray3D(unified_vertex_array, morph_mesh.vertices, morph_mesh.tessfaces)
                self.IndentWrite(B"}\n")

                self.DecIndent()
                self.IndentWrite(B"}\n")

                bpy.data.meshes.remove(morph_mesh)

        # Write the index arrays.

        max_material_index = 0
        for i in range(len(material_table)):
            index = material_table[i]
            if index > max_material_index:
                max_material_index = index

        if max_material_index == 0:

            # There is only one material, so write a single index array.

            self.IndentWrite(B"IndexArray\n", 0, True)
            self.IndentWrite(B"{\n")
            self.IncIndent()

            self.IndentWrite(B"unsigned_int32[3]\t\t// ")
            self.WriteInt(triangle_count)
            self.IndentWrite(B"{\n", 0, True)
            self.WriteTriangleArray(triangle_count, index_table)
            self.IndentWrite(B"}\n")

            self.DecIndent()
            self.IndentWrite(B"}\n")

        else:

            # If there are multiple material indexes, then write a separate index array for each one.

            material_triangle_count = [0 for i in range(max_material_index + 1)]
            for i in range(len(material_table)):
                material_triangle_count[material_table[i]] += 1

            for m in range(max_material_index + 1):
                if material_triangle_count[m] != 0:
                    material_index_table = []
                    for i in range(len(material_table)):
                        if material_table[i] == m:
                            k = i * 3
                            material_index_table.append(index_table[k])
                            material_index_table.append(index_table[k + 1])
                            material_index_table.append(index_table[k + 2])

                    self.IndentWrite(B"IndexArray (material = ", 0, True)
                    self.WriteInt(m)
                    self.file.write(B")\n")
                    self.IndentWrite(B"{\n")
                    self.IncIndent()

                    self.IndentWrite(B"unsigned_int32[3]\t\t// ")
                    self.WriteInt(material_triangle_count[m])
                    self.IndentWrite(B"{\n", 0, True)
                    self.WriteTriangleArray(material_triangle_count[m], material_index_table)
                    self.IndentWrite(B"}\n")

                    self.DecIndent()
                    self.IndentWrite(B"}\n")

        # If the mesh is skinned, export the skinning data here.

        if armature:
            self.export_skin(node, armature, unified_vertex_array)

        # Restore the morph state.

        if shape_keys:
            node.active_shape_key_index = active_shape_key_index
            node.show_only_shape_key = show_only_shape_key

            for m in range(len(current_morph_value)):
                shape_keys.key_blocks[m].value = current_morph_value[m]

            mesh.update()

        # Delete the new mesh that we made earlier.

        bpy.data.meshes.remove(export_mesh)

        self.DecIndent()
        self.IndentWrite(B"}\n")

        self.DecIndent()
        self.file.write(B"}\n")

        self.progress.end_task()

    def export_light(self, object_ref):

        # This function exports a single light object.

        self.file.write(B"\nLightObject $")
        self.file.write(object_ref[1]["structName"])

        obj = object_ref[0]

        self.file.write(B" (type = ")
        is_point = False
        is_spot = False

        if obj.type == "SUN":
            self.file.write(B"\"infinite\"")
        elif obj.type == "POINT":
            self.file.write(B"\"point\"")
            is_point = True
        else:
            self.file.write(B"\"spot\"")
            is_point = True
            is_spot = True

        if not obj.use_shadow:
            self.file.write(B", shadow = false")

        self.file.write(B")")
        self.WriteNodeTable(object_ref)

        self.file.write(B"\n{\n")
        self.IncIndent()

        # Export the light's color, and include a separate intensity if necessary.

        self.IndentWrite(B"Color (attrib = \"light\") {float[3] {")
        self.WriteColor(obj.color)
        self.file.write(B"}}\n")

        intensity = obj.energy
        if intensity != 1.0:
            self.IndentWrite(B"Param (attrib = \"intensity\") {float {")
            self.WriteFloat(intensity)
            self.file.write(B"}}\n")

        if is_point:

            # Export a separate attenuation function for each type that's in use.

            falloff = obj.falloff_type

            if falloff == "INVERSE_LINEAR":
                self.IndentWrite(B"Atten (curve = \"inverse\")\n", 0, True)
                self.IndentWrite(B"{\n")

                self.IndentWrite(B"Param (attrib = \"scale\") {float {", 1)
                self.WriteFloat(obj.distance)
                self.file.write(B"}}\n")

                self.IndentWrite(B"}\n")

            elif falloff == "INVERSE_SQUARE":
                self.IndentWrite(B"Atten (curve = \"inverse_square\")\n", 0, True)
                self.IndentWrite(B"{\n")

                self.IndentWrite(B"Param (attrib = \"scale\") {float {", 1)
                self.WriteFloat(math.sqrt(obj.distance))
                self.file.write(B"}}\n")

                self.IndentWrite(B"}\n")

            elif falloff == "LINEAR_QUADRATIC_WEIGHTED":
                if obj.linear_attenuation != 0.0:
                    self.IndentWrite(B"Atten (curve = \"inverse\")\n", 0, True)
                    self.IndentWrite(B"{\n")

                    self.IndentWrite(B"Param (attrib = \"scale\") {float {", 1)
                    self.WriteFloat(obj.distance)
                    self.file.write(B"}}\n")

                    self.IndentWrite(B"Param (attrib = \"constant\") {float {", 1)
                    self.WriteFloat(1.0)
                    self.file.write(B"}}\n")

                    self.IndentWrite(B"Param (attrib = \"linear\") {float {", 1)
                    self.WriteFloat(obj.linear_attenuation)
                    self.file.write(B"}}\n")

                    self.IndentWrite(B"}\n\n")

                if obj.quadratic_attenuation != 0.0:
                    self.IndentWrite(B"Atten (curve = \"inverse_square\")\n")
                    self.IndentWrite(B"{\n")

                    self.IndentWrite(B"Param (attrib = \"scale\") {float {", 1)
                    self.WriteFloat(obj.distance)
                    self.file.write(B"}}\n")

                    self.IndentWrite(B"Param (attrib = \"constant\") {float {", 1)
                    self.WriteFloat(1.0)
                    self.file.write(B"}}\n")

                    self.IndentWrite(B"Param (attrib = \"quadratic\") {float {", 1)
                    self.WriteFloat(obj.quadratic_attenuation)
                    self.file.write(B"}}\n")

                    self.IndentWrite(B"}\n")

            if obj.use_sphere:
                self.IndentWrite(B"Atten (curve = \"linear\")\n", 0, True)
                self.IndentWrite(B"{\n")

                self.IndentWrite(B"Param (attrib = \"end\") {float {", 1)
                self.WriteFloat(obj.distance)
                self.file.write(B"}}\n")

                self.IndentWrite(B"}\n")

            if is_spot:
                # Export additional angular attenuation for spot lights.

                self.IndentWrite(B"Atten (kind = \"angle\", curve = \"linear\")\n", 0, True)
                self.IndentWrite(B"{\n")

                end_angle = obj.spot_size * 0.5
                begin_angle = end_angle * (1.0 - obj.spot_blend)

                self.IndentWrite(B"Param (attrib = \"begin\") {float {", 1)
                self.WriteFloat(begin_angle)
                self.file.write(B"}}\n")

                self.IndentWrite(B"Param (attrib = \"end\") {float {", 1)
                self.WriteFloat(end_angle)
                self.file.write(B"}}\n")

                self.IndentWrite(B"}\n")

        self.DecIndent()
        self.file.write(B"}\n")

    def export_camera(self, object_ref):

        # This function exports a single camera object.

        self.file.write(B"\nCameraObject $")
        self.file.write(object_ref[1]["structName"])
        self.WriteNodeTable(object_ref)

        self.file.write(B"\n{\n")
        self.IncIndent()

        obj = object_ref[0]

        self.IndentWrite(B"Param (attrib = \"fov\") {float {")
        self.WriteFloat(obj.angle_x)
        self.file.write(B"}}\n")

        self.IndentWrite(B"Param (attrib = \"near\") {float {")
        self.WriteFloat(obj.clip_start)
        self.file.write(B"}}\n")

        self.IndentWrite(B"Param (attrib = \"far\") {float {")
        self.WriteFloat(obj.clip_end)
        self.file.write(B"}}\n")

        self.DecIndent()
        self.file.write(B"}\n")

    def export_objects(self, scene):

        for objectRef in self.container.geometryArray.items():
            self.export_geometry(objectRef, scene)
        for objectRef in self.container.lightArray.items():
            self.export_light(objectRef)
        for objectRef in self.container.cameraArray.items():
            self.export_camera(objectRef)

    def export_texture(self, texture_slot, attrib):

        if texture_slot.texture.type != 'IMAGE':
            return  # only image textures supported.

        if texture_slot.texture.image is None:
            return  # cannot export no image.

        # This function exports a single texture from a material.

        self.IndentWrite(B"Texture (attrib = \"", 0, True)
        self.file.write(attrib)
        self.file.write(B"\")\n")

        self.IndentWrite(B"{\n")
        self.IncIndent()

        self.IndentWrite(B"string {\"")
        self.WriteFileName(texture_slot.texture.image.filepath.replace("//", ""))
        self.file.write(B"\"}\n")

        # If the texture has a scale and/or offset, then export a coordinate transform.

        uscale = texture_slot.scale[0]
        vscale = texture_slot.scale[1]
        uoffset = texture_slot.offset[0]
        voffset = texture_slot.offset[1]

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

            diffuse_texture = None
            specular_texture = None
            emission_texture = None
            transparency_texture = None
            normal_texture = None

            for textureSlot in material.texture_slots:
                if textureSlot and textureSlot.use and (textureSlot.texture.type == "IMAGE"):
                    if (textureSlot.use_map_color_diffuse or textureSlot.use_map_diffuse and (
                            not diffuse_texture)):
                        diffuse_texture = textureSlot
                    elif (
                                textureSlot.use_map_color_spec or textureSlot.use_map_specular and (
                                    not specular_texture)):
                        specular_texture = textureSlot
                    elif textureSlot.use_map_emit and (not emission_texture):
                        emission_texture = textureSlot
                    elif textureSlot.use_map_translucency and (not transparency_texture):
                        transparency_texture = textureSlot
                    elif textureSlot.use_map_normal and (not normal_texture):
                        normal_texture = textureSlot

            if diffuse_texture:
                self.export_texture(diffuse_texture, B"diffuse")
            if specular_texture:
                self.export_texture(specular_texture, B"specular")
            if emission_texture:
                self.export_texture(emission_texture, B"emission")
            if transparency_texture:
                self.export_texture(transparency_texture, B"transparency")
            if normal_texture:
                self.export_texture(normal_texture, B"normal")

            self.DecIndent()
            self.file.write(B"}\n")

    def export_metrics(self, scene):

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

        if node in self.nodeChildren:
            return self.nodeChildren[node]
        else:
            return node.children

    def process_skinned_meshes(self):

        for nw in self.container.nodes:
            if nw.nodeRef["nodeType"] == kNodeTypeGeometry:
                armature = nw.item.find_armature()
                if armature:
                    for bone in armature.data.bones:
                        bone_ref = self.container.find_node_wrapper_by_name(bone.name)
                        if bone_ref:
                            # If a node is used as a bone, then we force its type to be a bone.
                            bone_ref.dict["nodeType"] = kNodeTypeBone

    def execute(self, context):

        start_time = time.time()

        scene = context.scene
        export_all_flag = not self.option_export_selection
        self.open(self.filepath)
        self.container = FlagContainer(export_all_flag, self.option_sample_animation, scene)

        self.export_metrics(scene)

        original_frame = scene.frame_current
        original_subframe = scene.frame_subframe

        self.progress.begin_task("Preparing objects...")
        for obj in scene.objects:
            if not obj.parent:
                NodeWrapper(obj, self.container)

        self.process_skinned_meshes()

        self.progress.end_task()

        self.progress.begin_task("Exporting nodes...")
        for obj in self.container.nodes:
            if not obj.parent:
                self.export_node(obj, scene)
        self.progress.end_task()

        # progress update is handled withing ExportObjects()
        self.export_objects(scene)

        self.progress.begin_task("Exporting materials...")
        self.export_materials()
        self.progress.end_task()

        restore_frame = False
        if restore_frame:
            scene.frame_set(original_frame, original_subframe)

        self.close()

        print('-- Successfully exported to "{}". ({:.2f} sec)'.format(self.filepath, time.time() - start_time))

        return {'FINISHED'}
