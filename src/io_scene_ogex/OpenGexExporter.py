import bpy
import bmesh
import math
from mathutils import Matrix
import time

from bpy_extras.io_utils import ExportHelper
from io_scene_ogex.NodeWrapper import NodeWrapper
from io_scene_ogex.Writer import Writer

from io_scene_ogex.ExporterState import *

__author__ = 'Eric Lengyel, Jonathan Hale, Nicolas Wehrle'

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

    export_selection = bpy.props.BoolProperty(name="Export Selection Only",
                                              description="Export only selected objects", default=False)
    sample_animation = bpy.props.BoolProperty(name="Force Sampled Animation",
                                              description="Always export animation as per-frame samples",
                                              default=False)

    export_custom_properties = bpy.props.BoolProperty(name="Export Custom Properties",
                                                      description="Export object custom properties to an OGEX" +
                                                                  "Extension structure",
                                                      default=False)
    export_physics = bpy.props.BoolProperty(name="Export Game Physics",
                                            description="Export game physics to an OGEX Extension structure",
                                            default=False)
    export_ambient = bpy.props.BoolProperty(name="Export Ambient Color",
                                            description="Export world ambient color and material ambient factors as a"\
                                                        "not officially specified Param.",
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

    @staticmethod
    def find_export_vertex(bucket, export_vertex_array, vertex):

        for index in bucket:
            if export_vertex_array[index] == vertex:
                return index

        return -1

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

        self.indent_write(B"Key {float {")

        key_count = len(fcurve.keyframe_points)
        for i in range(key_count):
            if i > 0:
                self.file.write(B", ")

            time = fcurve.keyframe_points[i].co[0] - self.container.beginFrame
            self.write_float(time * self.container.frameTime)

        self.file.write(B"}}\n")

    def export_key_time_control_points(self, fcurve):

        self.indent_write(B"Key (kind = \"-control\") {float {")

        key_count = len(fcurve.keyframe_points)
        for i in range(key_count):
            if i > 0:
                self.file.write(B", ")

            ctrl = fcurve.keyframe_points[i].handle_left[0] - self.container.beginFrame
            self.write_float(ctrl * self.container.frameTime)

        self.file.write(B"}}\n")
        self.indent_write(B"Key (kind = \"+control\") {float {")

        for i in range(key_count):
            if i > 0:
                self.file.write(B", ")

            ctrl = fcurve.keyframe_points[i].handle_right[0] - self.container.beginFrame
            self.write_float(ctrl * self.container.frameTime)

        self.file.write(B"}}\n")

    def export_key_values(self, fcurve):

        self.indent_write(B"Key {float {")

        key_count = len(fcurve.keyframe_points)
        for i in range(key_count):
            if i > 0:
                self.file.write(B", ")

            value = fcurve.keyframe_points[i].co[1]
            self.write_float(value)

        self.file.write(B"}}\n")

    def export_key_value_control_points(self, fcurve):

        self.indent_write(B"Key (kind = \"-control\") {float {")

        key_count = len(fcurve.keyframe_points)
        for i in range(key_count):
            if i > 0:
                self.file.write(B", ")

            ctrl = fcurve.keyframe_points[i].handle_left[1]
            self.write_float(ctrl)

        self.file.write(B"}}\n")
        self.indent_write(B"Key (kind = \"+control\") {float {")

        for i in range(key_count):
            if i > 0:
                self.file.write(B", ")

            ctrl = fcurve.keyframe_points[i].handle_right[1]
            self.write_float(ctrl)

        self.file.write(B"}}\n")

    def export_animation_track(self, fcurve, kind, target, newline):
        # This function exports a single animation track. The curve types for the
        # Time and Value structures are given by the kind parameter.

        self.indent_write(B"Track (target = %", 0, newline)
        self.file.write(target)
        self.file.write(B")\n")
        self.indent_write(B"{\n")
        self.inc_indent()

        if kind != kAnimationBezier:
            self.indent_write(B"Time\n")
            self.indent_write(B"{\n")
            self.inc_indent()

            self.export_key_times(fcurve)

            self.indent_write(B"}\n\n", -1)
            self.indent_write(B"Value\n", -1)
            self.indent_write(B"{\n", -1)

            self.export_key_values(fcurve)

            self.dec_indent()
            self.indent_write(B"}\n")

        else:
            self.indent_write(B"Time (curve = \"bezier\")\n")
            self.indent_write(B"{\n")
            self.inc_indent()

            self.export_key_times(fcurve)
            self.export_key_time_control_points(fcurve)

            self.indent_write(B"}\n\n", -1)
            self.indent_write(B"Value (curve = \"bezier\")\n", -1)
            self.indent_write(B"{\n", -1)

            self.export_key_values(fcurve)
            self.export_key_value_control_points(fcurve)

            self.dec_indent()
            self.indent_write(B"}\n")

        self.dec_indent()
        self.indent_write(B"}\n")

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
            self.indent_write(B"Animation\n", 0, True)
            self.indent_write(B"{\n")
            self.inc_indent()

            self.indent_write(B"Track (target = %transform)\n")
            self.indent_write(B"{\n")
            self.inc_indent()

            self.indent_write(B"Time\n")
            self.indent_write(B"{\n")
            self.inc_indent()

            self.indent_write(B"Key {float {")

            for i in range(self.container.beginFrame, self.container.endFrame):
                self.write_float((i - self.container.beginFrame) * self.container.frameTime)
                self.file.write(B", ")

            self.write_float(self.container.endFrame * self.container.frameTime)
            self.file.write(B"}}\n")

            self.indent_write(B"}\n\n", -1)
            self.indent_write(B"Value\n", -1)
            self.indent_write(B"{\n", -1)

            self.indent_write(B"Key\n")
            self.indent_write(B"{\n")
            self.inc_indent()

            self.indent_write(B"float[16]\n")
            self.indent_write(B"{\n")

            for i in range(self.container.beginFrame, self.container.endFrame):
                scene.frame_set(i)
                self.write_matrixFlat(node.matrix_local)
                self.file.write(B",\n")

            scene.frame_set(self.container.endFrame)
            self.write_matrixFlat(node.matrix_local)
            self.indent_write(B"}\n", 0, True)

            self.dec_indent()
            self.indent_write(B"}\n")

            self.dec_indent()
            self.indent_write(B"}\n")

            self.dec_indent()
            self.indent_write(B"}\n")

            self.dec_indent()
            self.indent_write(B"}\n")

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
            self.indent_write(B"Animation\n", 0, True)
            self.indent_write(B"{\n")
            self.inc_indent()

            self.indent_write(B"Track (target = %transform)\n")
            self.indent_write(B"{\n")
            self.inc_indent()

            self.indent_write(B"Time\n")
            self.indent_write(B"{\n")
            self.inc_indent()

            self.indent_write(B"Key {float {")

            for i in range(self.container.beginFrame, self.container.endFrame):
                self.write_float((i - self.container.beginFrame) * self.container.frameTime)
                self.file.write(B", ")

            self.write_float(self.container.endFrame * self.container.frameTime)
            self.file.write(B"}}\n")

            self.indent_write(B"}\n\n", -1)
            self.indent_write(B"Value\n", -1)
            self.indent_write(B"{\n", -1)

            self.indent_write(B"Key\n")
            self.indent_write(B"{\n")
            self.inc_indent()

            self.indent_write(B"float[16]\n")
            self.indent_write(B"{\n")

            parent = pose_bone.parent
            if parent:
                for i in range(self.container.beginFrame, self.container.endFrame):
                    scene.frame_set(i)
                    if math.fabs(parent.matrix.determinant()) > kExportEpsilon:
                        self.write_matrixFlat(parent.matrix.inverted() * pose_bone.matrix)
                    else:
                        self.write_matrixFlat(pose_bone.matrix)

                    self.file.write(B",\n")

                scene.frame_set(self.container.endFrame)
                if math.fabs(parent.matrix.determinant()) > kExportEpsilon:
                    self.write_matrixFlat(parent.matrix.inverted() * pose_bone.matrix)
                else:
                    self.write_matrixFlat(pose_bone.matrix)

                self.indent_write(B"}\n", 0, True)

            else:
                for i in range(self.container.beginFrame, self.container.endFrame):
                    scene.frame_set(i)
                    self.write_matrixFlat(pose_bone.matrix)
                    self.file.write(B",\n")

                scene.frame_set(self.container.endFrame)
                self.write_matrixFlat(pose_bone.matrix)
                self.indent_write(B"}\n", 0, True)

            self.dec_indent()
            self.indent_write(B"}\n")

            self.dec_indent()
            self.indent_write(B"}\n")

            self.dec_indent()
            self.indent_write(B"}\n")

            self.dec_indent()
            self.indent_write(B"}\n")

        scene.frame_set(current_frame, current_subframe)

    def export_morph_weight_sampled_animation_track(self, block, target, scene, newline):

        current_frame = scene.frame_current
        current_subframe = scene.frame_subframe

        self.indent_write(B"Track (target = %", 0, newline)
        self.file.write(target)
        self.file.write(B")\n")
        self.indent_write(B"{\n")
        self.inc_indent()

        self.indent_write(B"Time\n")
        self.indent_write(B"{\n")
        self.inc_indent()

        self.indent_write(B"Key {float {")

        for i in range(self.container.beginFrame, self.container.endFrame):
            self.write_float((i - self.container.beginFrame) * self.container.frameTime)
            self.file.write(B", ")

        self.write_float(self.container.endFrame * self.container.frameTime)
        self.file.write(B"}}\n")

        self.indent_write(B"}\n\n", -1)
        self.indent_write(B"Value\n", -1)
        self.indent_write(B"{\n", -1)

        self.indent_write(B"Key {float {")

        for i in range(self.container.beginFrame, self.container.endFrame):
            scene.frame_set(i)
            self.write_float(block.value)
            self.file.write(B", ")

        scene.frame_set(self.container.endFrame)
        self.write_float(block.value)
        self.file.write(B"}}\n")

        self.dec_indent()
        self.indent_write(B"}\n")

        self.dec_indent()
        self.indent_write(B"}\n")

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
        sampled_animation = (self.container.sampleAnimation or (mode == "QUATERNION") or (mode == "AXIS_ANGLE"))

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

            self.indent_write(B"Transform")

            if sampled_animation:
                self.file.write(B" %transform")

            self.indent_write(B"{\n", 0, True)
            self.inc_indent()

            self.indent_write(B"float[16]\n")
            self.indent_write(B"{\n")

            transformation = node.matrix_local
            if node.type == 'CAMERA':
                # handle Blenders unusual downward-facing camera rest pose
                transformation = transformation * Matrix.Rotation(math.radians(-90.0), 4, 'X')

            # FIXME: Pretty bad workaround for blender using scale as half extents
            # if we export a rigid body later, which uses the scale as half extents,
            # we need to make sure the scale is cancelled out. This is not the case
            # for mesh shapes.
            # This needs to be done for the object itself on the one hand and its
            # children on the other
            if self.export_physics and (node.parent is not None)\
                    and node.parent.game.physics_type != 'NO_COLLISION':
                # a child of a scale as half extent object
                parent_props = node.parent.game
                if parent_props.use_collision_bounds and parent_props.collision_bounds_type not in\
                        ['CONVEX_HULL', 'TRIANGLE_MESH']:
                    inverted_scale = Matrix()
                    scale = node.parent.scale
                    inverted_scale[0][0] = scale[0]
                    inverted_scale[1][1] = scale[1]
                    inverted_scale[2][2] = scale[2]
                    transformation = inverted_scale * transformation
            if self.export_physics and node.game.physics_type != 'NO_COLLISION':
                # a child of a scale as half extent object
                if node.game.use_collision_bounds and node.game.collision_bounds_type not in\
                        ['CONVEX_HULL', 'TRIANGLE_MESH']:
                    # simply remove scale
                    transformation = Matrix.Translation(transformation.translation)\
                                     * transformation.to_quaternion().to_matrix().to_4x4()

            self.handle_offset(transformation, nw.offset)
            self.indent_write(B"}\n")

            self.dec_indent()
            self.indent_write(B"}\n")

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
                        self.indent_write(B"Translation %", 0, struct_flag)
                        self.file.write(deltaSubtranslationName[i])
                        self.file.write(B" (kind = \"")
                        self.file.write(axisName[i])
                        self.file.write(B"\")\n")
                        self.indent_write(B"{\n")
                        self.indent_write(B"float {", 1)
                        self.write_float(pos)
                        self.file.write(B"}")
                        self.indent_write(B"}\n", 0, True)

                        struct_flag = True

            elif ((math.fabs(delta_translation[0]) > kExportEpsilon) or (
                        math.fabs(delta_translation[1]) > kExportEpsilon) or (
                        math.fabs(delta_translation[2]) > kExportEpsilon)):
                self.indent_write(B"Translation\n")
                self.indent_write(B"{\n")
                self.indent_write(B"float[3] {", 1)
                self.write_vector3d(delta_translation)
                self.file.write(B"}")
                self.indent_write(B"}\n", 0, True)

                struct_flag = True

            translation = node.location
            if position_animated:

                # When the location is animated, write the x, y, and z components separately
                # so they can be targeted by different tracks having different sets of keys.

                for i in range(3):
                    pos = translation[i]
                    if (pos_animated[i]) or (math.fabs(pos) > kExportEpsilon):
                        self.indent_write(B"Translation %", 0, struct_flag)
                        self.file.write(subtranslationName[i])
                        self.file.write(B" (kind = \"")
                        self.file.write(axisName[i])
                        self.file.write(B"\")\n")
                        self.indent_write(B"{\n")
                        self.indent_write(B"float {", 1)
                        self.write_float(pos)
                        self.file.write(B"}")
                        self.indent_write(B"}\n", 0, True)

                        struct_flag = True

            elif ((math.fabs(translation[0]) > kExportEpsilon) or (math.fabs(translation[1]) > kExportEpsilon) or (
                        math.fabs(translation[2]) > kExportEpsilon)):
                self.indent_write(B"Translation\n")
                self.indent_write(B"{\n")
                self.indent_write(B"float[3] {", 1)
                self.write_vector3d(translation)
                self.file.write(B"}")
                self.indent_write(B"}\n", 0, True)

                struct_flag = True

            if delta_rotation_animated:

                # When the delta rotation is animated, write three separate Euler angle rotations
                # so they can be targeted by different tracks having different sets of keys.

                for i in range(3):
                    axis = ord(mode[2 - i]) - 0x58
                    angle = node.delta_rotation_euler[axis]
                    if (delta_rot_animated[axis]) or (math.fabs(angle) > kExportEpsilon):
                        self.indent_write(B"Rotation %", 0, struct_flag)
                        self.file.write(deltaSubrotationName[axis])
                        self.file.write(B" (kind = \"")
                        self.file.write(axisName[axis])
                        self.file.write(B"\")\n")
                        self.indent_write(B"{\n")
                        self.indent_write(B"float {", 1)
                        self.write_float(angle)
                        self.file.write(B"}")
                        self.indent_write(B"}\n", 0, True)

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
                        self.indent_write(B"Rotation (kind = \"quaternion\")\n", 0, struct_flag)
                        self.indent_write(B"{\n")
                        self.indent_write(B"float[4] {", 1)
                        self.write_quaternion(quaternion)
                        self.file.write(B"}")
                        self.indent_write(B"}\n", 0, True)

                        struct_flag = True

                else:
                    for i in range(3):
                        axis = ord(mode[2 - i]) - 0x58
                        angle = node.delta_rotation_euler[axis]
                        if math.fabs(angle) > kExportEpsilon:
                            self.indent_write(B"Rotation (kind = \"", 0, struct_flag)
                            self.file.write(axisName[axis])
                            self.file.write(B"\")\n")
                            self.indent_write(B"{\n")
                            self.indent_write(B"float {", 1)
                            self.write_float(angle)
                            self.file.write(B"}")
                            self.indent_write(B"}\n", 0, True)

                            struct_flag = True

            if rotation_animated:

                # When the rotation is animated, write three separate Euler angle rotations
                # so they can be targeted by different tracks having different sets of keys.

                for i in range(3):
                    axis = ord(mode[2 - i]) - 0x58
                    angle = node.rotation_euler[axis]
                    if (rot_animated[axis]) or (math.fabs(angle) > kExportEpsilon):
                        self.indent_write(B"Rotation %", 0, struct_flag)
                        self.file.write(subrotationName[axis])
                        self.file.write(B" (kind = \"")
                        self.file.write(axisName[axis])
                        self.file.write(B"\")\n")
                        self.indent_write(B"{\n")
                        self.indent_write(B"float {", 1)
                        self.write_float(angle)
                        self.file.write(B"}")
                        self.indent_write(B"}\n", 0, True)

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
                        self.indent_write(B"Rotation (kind = \"quaternion\")\n", 0, struct_flag)
                        self.indent_write(B"{\n")
                        self.indent_write(B"float[4] {", 1)
                        self.write_quaternion(quaternion)
                        self.file.write(B"}")
                        self.indent_write(B"}\n", 0, True)

                        struct_flag = True

                elif mode == "AXIS_ANGLE":
                    if math.fabs(node.rotation_axis_angle[0]) > kExportEpsilon:
                        self.indent_write(B"Rotation (kind = \"axis\")\n", 0, struct_flag)
                        self.indent_write(B"{\n")
                        self.indent_write(B"float[4] {", 1)
                        self.write_vector4d(node.rotation_axis_angle)
                        self.file.write(B"}")
                        self.indent_write(B"}\n", 0, True)

                        struct_flag = True

                else:
                    for i in range(3):
                        axis = ord(mode[2 - i]) - 0x58
                        angle = node.rotation_euler[axis]
                        if math.fabs(angle) > kExportEpsilon:
                            self.indent_write(B"Rotation (kind = \"", 0, struct_flag)
                            self.file.write(axisName[axis])
                            self.file.write(B"\")\n")
                            self.indent_write(B"{\n")
                            self.indent_write(B"float {", 1)
                            self.write_float(angle)
                            self.file.write(B"}")
                            self.indent_write(B"}\n", 0, True)

                            struct_flag = True

            delta_scale = node.delta_scale
            if delta_scale_animated:

                # When the delta scale is animated, write the x, y, and z components separately
                # so they can be targeted by different tracks having different sets of keys.

                for i in range(3):
                    scl = delta_scale[i]
                    if (delta_scl_animated[i]) or (math.fabs(scl) > kExportEpsilon):
                        self.indent_write(B"Scale %", 0, struct_flag)
                        self.file.write(delta_subscale_name[i])
                        self.file.write(B" (kind = \"")
                        self.file.write(axisName[i])
                        self.file.write(B"\")\n")
                        self.indent_write(B"{\n")
                        self.indent_write(B"float {", 1)
                        self.write_float(scl)
                        self.file.write(B"}")
                        self.indent_write(B"}\n", 0, True)

                        struct_flag = True

            elif ((math.fabs(delta_scale[0] - 1.0) > kExportEpsilon) or (
                        math.fabs(delta_scale[1] - 1.0) > kExportEpsilon) or (
                        math.fabs(delta_scale[2] - 1.0) > kExportEpsilon)):
                self.indent_write(B"Scale\n", 0, struct_flag)
                self.indent_write(B"{\n")
                self.indent_write(B"float[3] {", 1)
                self.write_vector3d(delta_scale)
                self.file.write(B"}")
                self.indent_write(B"}\n", 0, True)

                struct_flag = True

            scale = node.scale
            if scale_animated:

                # When the scale is animated, write the x, y, and z components separately
                # so they can be targeted by different tracks having different sets of keys.

                for i in range(3):
                    scl = scale[i]
                    if (scl_animated[i]) or (math.fabs(scl) > kExportEpsilon):
                        self.indent_write(B"Scale %", 0, struct_flag)
                        self.file.write(subscaleName[i])
                        self.file.write(B" (kind = \"")
                        self.file.write(axisName[i])
                        self.file.write(B"\")\n")
                        self.indent_write(B"{\n")
                        self.indent_write(B"float {", 1)
                        self.write_float(scl)
                        self.file.write(B"}")
                        self.indent_write(B"}\n", 0, True)

                        struct_flag = True

            elif ((math.fabs(scale[0] - 1.0) > kExportEpsilon) or (math.fabs(scale[1] - 1.0) > kExportEpsilon) or (
                        math.fabs(scale[2] - 1.0) > kExportEpsilon)):
                self.indent_write(B"Scale\n", 0, struct_flag)
                self.indent_write(B"{\n")
                self.indent_write(B"float[3] {", 1)
                self.write_vector3d(scale)
                self.file.write(B"}")
                self.indent_write(B"}\n", 0, True)

                struct_flag = True

            # Export the animation tracks.

            self.indent_write(B"Animation (begin = ", 0, True)
            self.write_float((action.frame_range[0] - self.container.beginFrame) * self.container.frameTime)
            self.file.write(B", end = ")
            self.write_float((action.frame_range[1] - self.container.beginFrame) * self.container.frameTime)
            self.file.write(B")\n")
            self.indent_write(B"{\n")
            self.inc_indent()

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

            self.dec_indent()
            self.indent_write(B"}\n")

    def handle_offset(self, matrix, offset):

        if not offset:
            self.write_matrix(matrix)
            return

        m = matrix.copy()
        m.translation -= offset
        self.write_matrix(m)

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

        self.indent_write(B"Transform")

        if animation:
            self.file.write(B" %transform")

        self.indent_write(B"{\n", 0, True)
        self.inc_indent()

        self.indent_write(B"float[16]\n")
        self.indent_write(B"{\n")
        self.write_matrix(transform)
        self.indent_write(B"}\n")

        self.dec_indent()
        self.indent_write(B"}\n")

        if animation and pose_bone:
            self.export_bone_sampled_animation(pose_bone, scene)

    def export_material_ref(self, material, index):

        if material not in self.container.materialArray:
            self.container.materialArray[material] = \
                {"structName": bytes("material" + str(len(self.container.materialArray) + 1), "UTF-8")}

        self.indent_write(B"MaterialRef (index = ")
        self.write_int(index)
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
            self.indent_write(B"MorphWeight", 0, (k == 0))

            if animated:
                self.file.write(B" %mw")
                self.write_int(k)

            self.file.write(B" (index = ")
            self.write_int(k)
            self.file.write(B") {float {")

            block = shape_keys.key_blocks[k]
            self.write_float(block.value if (block.name != reference_name) else 1.0)

            self.file.write(B"}}\n")

        if animated:
            self.indent_write(B"Animation (begin = ", 0, True)
            self.write_float((action.frame_range[0] - self.container.beginFrame) * self.container.frameTime)
            self.file.write(B", end = ")
            self.write_float((action.frame_range[1] - self.container.beginFrame) * self.container.frameTime)
            self.file.write(B")\n")
            self.indent_write(B"{\n")
            self.inc_indent()

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

            self.dec_indent()
            self.indent_write(B"}\n")

    def export_bone(self, nw, bw, scene):  # armature, bone, scene):

        if nw.nodeRef:
            self.indent_write(structIdentifier[nw.nodeRef["nodeType"]], 0, True)
            self.file.write(nw.nodeRef["structName"])

            self.indent_write(B"{\n", 0, True)
            self.inc_indent()

            name = bw.item.name
            if name != "":
                self.indent_write(B"Name {string {\"")
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
            self.dec_indent()
            self.indent_write(B"}\n")

    def export_node(self, nw, scene, pose_bone=None):

        # This function exports a single node in the scene and includes its name,
        # object reference, material references (for geometries), and transform.
        # Subnodes are then exported recursively.

        if nw.nodeRef:
            type = nw.nodeRef["nodeType"]
            self.indent_write(structIdentifier[type], 0, True)
            self.file.write(nw.nodeRef["structName"])

            if type == NodeType.geometry:
                if nw.item.hide_render:
                    self.file.write(B" (visible = false)")

            self.indent_write(B"{\n", 0, True)
            self.inc_indent()

            struct_flag = False

            # Export the node's name if it has one.

            name = nw.item.name
            if name != "":
                self.indent_write(B"Name {string {\"")
                self.file.write(bytes(name, "UTF-8"))
                self.file.write(B"\"}}\n")
                struct_flag = True

            # Export custom properties
            if len(nw.item.items()) != 0 and self.export_custom_properties:
                self.export_properties(nw.item)

            # Export the object reference and material references.

            obj = nw.item.data

            if type == NodeType.geometry:
                if obj not in self.container.geometryArray:
                    self.container.geometryArray[obj] = {
                        "structName": bytes("geometry" + str(len(self.container.geometryArray) + 1), "UTF-8"),
                        "nodeTable": [nw.item]}
                else:
                    self.container.geometryArray[obj]["nodeTable"].append(nw.item)

                self.indent_write(B"ObjectRef {ref {$")
                self.file.write(self.container.geometryArray[obj]["structName"])
                self.file.write(B"}}\n")

                for i in range(len(nw.item.material_slots)):
                    self.export_material_ref(nw.item.material_slots[i].material, i)

                shape_keys = OpenGexExporter.get_shape_keys(obj)
                if shape_keys:
                    # FIXME Wrapper or item?
                    self.export_morph_weights(nw.item, shape_keys, scene)

                struct_flag = True

            elif type == NodeType.light:
                if obj not in self.container.lightArray:
                    self.container.lightArray[obj] = \
                        {"structName": bytes("light" + str(len(self.container.lightArray) + 1), "UTF-8"),
                         "nodeTable": [nw.item]}
                else:
                    self.container.lightArray[obj]["nodeTable"].append(nw.item)

                self.indent_write(B"ObjectRef {ref {$")
                self.file.write(self.container.lightArray[obj]["structName"])
                self.file.write(B"}}\n")
                struct_flag = True

            elif type == NodeType.camera:
                if obj not in self.container.cameraArray:
                    self.container.cameraArray[obj] = \
                        {"structName": bytes("camera" + str(len(self.container.cameraArray) + 1), "UTF-8"),
                         "nodeTable": [nw.item]}
                else:
                    self.container.cameraArray[obj]["nodeTable"].append(nw.item)

                self.indent_write(B"ObjectRef {ref {$")
                self.file.write(self.container.cameraArray[obj]["structName"])
                self.file.write(B"}}\n")
                struct_flag = True

            if struct_flag:
                self.file.write(B"\n")

            if pose_bone:
                # If the node is parented to a bone and is not relative, then undo the bone's transform.

                if math.fabs(pose_bone.matrix.determinant()) > kExportEpsilon:
                    self.indent_write(B"Transform\n")
                    self.indent_write(B"{\n")
                    self.inc_indent()

                    self.indent_write(B"float[16]\n")
                    self.indent_write(B"{\n")
                    self.write_matrix(pose_bone.matrix.inverted())
                    self.indent_write(B"}\n")

                    self.dec_indent()
                    self.indent_write(B"}\n\n")

            # Export the transform. If the node is animated, then animation tracks are exported here.

            self.export_node_transformation(nw, scene)

            if nw.bones:
                for bw in nw.bones:
                    self.export_bone(nw, bw, scene)

        # export physics properties
        if self.export_physics and nw.item.game.physics_type != 'NO_COLLISION':
            self.export_physics_properties(nw.item)

        for subnode in nw.children:
            if subnode.parent.item.type != "BONE":
                self.export_node(subnode, scene)

        if nw.nodeRef:
            self.dec_indent()
            self.indent_write(B"}\n")

    def export_properties(self, node):
        prefix = self.get_extension_header(B"Blender", B"Property")

        count = 0
        for (name, value) in node.items():
            if name == "_RNA_UI":
                continue  # for blender only

            count += 1

            if isinstance(value, int):
                type_name = B"int32"
                value_bytes = self.to_int_byte(value)
            elif isinstance(value, float):
                type_name = B"float"
                value_bytes = self.to_float_byte(value)
            elif isinstance(value, str):
                type_name = B"string"
                value_bytes = B"\"" + bytes(value, "UTF-8") + B"\""
            else:
                print("\nWARNING: Unknown custom property type for property \"{}\"".format(name))
                continue

            self.inc_indent()
            self.write(prefix +
                       self.get_primitive_bytes(B"string", [B"\"" + bytes(name, "UTF-8") + B"\""]) +
                       self.get_primitive_bytes(type_name, [value_bytes]))
            self.dec_indent()
            self.write(self.get_indent() + B"}\n")

    SHAPE_TYPE_TO_EXTENSION = {"BOX": B"BoxShape",
                               "SHPERE": B"SphereShape",
                               "CYLINDER": B"CylinderShape",
                               "CONE": B"ConeShape",
                               "CONVEX_HULL": B"ConvexHullShape",
                               "TRIANGLE_MESH": B"TriangleMeshShape",
                               "CAPSULE": B"CapsuleShape"}

    def export_physics_properties(self, o):
        props = o.game
        buff = B"\n" + self.get_extension_header(B"Blender", B"PhysicsMaterial")
        self.inc_indent()

        # physics collision type
        buff += self.get_extension_header(B"Blender", B"PM/type")
        self.inc_indent()
        buff += self.get_primitive_bytes(B"string", [B"\"" + bytes(props.physics_type, "UTF-8") + B"\""])
        self.dec_indent()
        buff += self.get_indent() + B"}\n"

        if props.use_collision_bounds and props.physics_type not in ['NAVMESH', 'OCCLUDER']:
            # export collision shape
            buff += self.get_extension_header(B"Blender", B"PM/shape")
            self.inc_indent()
            shape_type = props.collision_bounds_type

            buff += self.get_extension_header(B"Blender", self.SHAPE_TYPE_TO_EXTENSION[shape_type])
            self.inc_indent()

            if shape_type not in ['CONVEX_HULL', 'TRIANGLE_MESH']:
                # export scale as half-extents
                buff += self.get_primitive_bytes(B"float", map(self.to_float_byte, o.scale))
            else:
                # export geometry as triangle mesh
                buff += self.get_primitive_bytes(B"ref", [B"$" + self.container.geometryArray[o.data]["structName"]])

            # collision shape margin
            buff += self.get_extension_header(B"Blender", B"PM/margin")
            self.inc_indent()
            buff += self.get_primitive_bytes(B"float", [self.to_float_byte(props.collision_margin)])
            self.dec_indent()
            buff += self.get_indent() + B"}\n"  # end PM/margin

            self.dec_indent()
            buff += self.get_indent() + B"}\n"  # end *Shape

            self.dec_indent()
            buff += self.get_indent() + B"}\n"  # end PM/shape

        self.dec_indent()
        self.write(buff + self.get_indent() + B"}\n")

    def export_skin(self, node, armature, export_vertex_array):

        # This function exports all skinning data, which includes the skeleton
        # and per-vertex bone influence data.

        self.indent_write(B"Skin\n", 0, True)
        self.indent_write(B"{\n")
        self.inc_indent()

        # Write the skin bind pose transform.

        self.indent_write(B"Transform\n")
        self.indent_write(B"{\n")
        self.inc_indent()

        self.indent_write(B"float[16]\n")
        self.indent_write(B"{\n")
        self.write_matrix(node.matrix_world)
        self.indent_write(B"}\n")

        self.dec_indent()
        self.indent_write(B"}\n\n")

        # Export the skeleton, which includes an array of bone node references
        # and and array of per-bone bind pose transforms.

        self.indent_write(B"Skeleton\n")
        self.indent_write(B"{\n")
        self.inc_indent()

        # Write the bone node reference array.

        self.indent_write(B"bone_refArray\n")
        self.indent_write(B"{\n")
        self.inc_indent()

        bone_array = armature.data.bones
        bone_count = len(bone_array)

        self.indent_write(B"ref\t\t\t// ")
        self.write_int(bone_count)
        self.indent_write(B"{\n", 0, True)
        self.indent_write(B"", 1)

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

        self.indent_write(B"}\n")

        self.dec_indent()
        self.indent_write(B"}\n\n")

        # Write the bind pose transform array.

        self.indent_write(B"Transform\n")
        self.indent_write(B"{\n")
        self.inc_indent()

        self.indent_write(B"float[16]\t// ")
        self.write_int(bone_count)
        self.indent_write(B"{\n", 0, True)

        for i in range(bone_count):
            self.write_matrixFlat(armature.matrix_world * bone_array[i].matrix_local)
            if i < bone_count - 1:
                self.file.write(B",\n")

        self.indent_write(B"}\n", 0, True)

        self.dec_indent()
        self.indent_write(B"}\n")

        self.dec_indent()
        self.indent_write(B"}\n\n")

        # Export the per-vertex bone influence data.

        group_remap = []

        for group in node.vertex_groups:
            group_name = group.name
            for i in range(bone_count):
                if bone_array[i].name == group_name:
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

        self.indent_write(B"bone_countArray\n")
        self.indent_write(B"{\n")
        self.inc_indent()

        self.indent_write(B"unsigned_int16\t\t// ")
        self.write_int(len(bone_count_array))
        self.indent_write(B"{\n", 0, True)
        self.write_intArray(bone_count_array)
        self.indent_write(B"}\n")

        self.dec_indent()
        self.indent_write(B"}\n\n")

        # Write the bone index array. The number of entries is the sum of the bone counts for all vertices.

        self.indent_write(B"BoneIndexArray\n")
        self.indent_write(B"{\n")
        self.inc_indent()

        self.indent_write(B"unsigned_int16\t\t// ")
        self.write_int(len(bone_index_array))
        self.indent_write(B"{\n", 0, True)
        self.write_intArray(bone_index_array)
        self.indent_write(B"}\n")

        self.dec_indent()
        self.indent_write(B"}\n\n")

        # Write the bone weight array. The number of entries is the sum of the bone counts for all vertices.

        self.indent_write(B"BoneWeightArray\n")
        self.indent_write(B"{\n")
        self.inc_indent()

        self.indent_write(B"float\t\t// ")
        self.write_int(len(bone_weight_array))
        self.indent_write(B"{\n", 0, True)
        self.write_floatArray(bone_weight_array)
        self.indent_write(B"}\n")

        self.dec_indent()
        self.indent_write(B"}\n")

        self.dec_indent()
        self.indent_write(B"}\n")

    @staticmethod
    def to_per_vertex_data(m, num_materials=1, uv_layers=None):
        """
        Generate per vertex data from blender bmesh.
        :param m: triangulated bmesh to generate the data from
        :param num_materials: number of materials used in the mesh
        :param uv_layers: names of uv layers to export or None to export all.
        :return: dict of property to data. Possibly keys are: "position", "normal", "tris" and "texcoord"
        """
        num_materials = max(1, num_materials)

        num_verts = len(m.verts)

        # list of list which stores all the new indices corresponding to an old index
        index_translation = [[i] for i in range(num_verts)]
        positions = [v.co for v in m.verts]
        normals = [None] * num_verts
        color_layer = m.loops.layers.color.active

        if color_layer is not None:
            colors = [None] * num_verts

        if uv_layers is None:
            active_uv_layers = [layer for layer in m.loops.layers.uv.values()]
        else:
            active_uv_layers = [m.loops.layers.uv[name] for name in uv_layers]

        has_uv_layers = (len(active_uv_layers) != 0)
        if has_uv_layers:
            texcoords = {l: [None] * num_verts for l in active_uv_layers}

        mesh_indices = [[]] * num_materials  # list of triples of the faces for all materials

        for face in m.faces:
            face_indices = [0, 0, 0]

            for cur_index, loop in enumerate(face.loops):
                vert = loop.vert

                pos = vert.co
                normal = vert.normal if face.smooth else face.normal

                # check if this vertex has not been initialized yet:
                i = vert.index
                if normals[i] is None:
                    # not in use yet, we can set the data for this
                    # vertex safely
                    normals[i] = normal
                    if color_layer is not None:
                        colors[i] = loop[color_layer]
                    for layer in active_uv_layers:
                        texcoords[layer][i] = loop[layer].uv

                    face_indices[cur_index] = i
                    continue
                # else: check for an existing vertex that matches our data.
                indices = index_translation[vert.index]  # existing indices with same position
                found_existing = False
                for i in indices:
                    # position is always identical.

                    # normals
                    if normals[i] != normal:
                        # this one does not have an identical normal
                        continue

                    # vertex colors
                    if color_layer is not None:
                        if colors[i] != loop[color_layer]:
                            # this one does not have an identical vertex color
                            continue

                    # texture coordinates
                    found_uvs = True  # in case we do not have any active layers.
                    for layer in active_uv_layers:
                        if texcoords[layer][i] != loop[layer].uv:
                            found_uvs = False
                            break

                    if not found_uvs:
                        # this one does not have an identical uv coord in one of its layers
                        continue

                    # we found matching data => reuse!
                    found_existing = True
                    face_indices[cur_index] = i
                    break

                if not found_existing:
                    # no data matched, we need to create some.
                    new_index = len(positions)

                    indices.append(new_index)  # make sure this vertex can be found later
                    face_indices[cur_index] = new_index

                    # append data of current loop
                    positions.append(pos)
                    normals.append(normal)
                    if color_layer is not None:
                        colors.append(loop[color_layer])

                    for layer in active_uv_layers:
                        texcoords[layer].append(loop[layer].uv)

            # add the triple to the list of faces/triangles for the corresponding material index
            mesh_indices[face.material_index].append(face_indices)

        ret_value = {"position": positions, "normal": normals, "tris": mesh_indices}
        if has_uv_layers:
            ret_value["texcoord"] = texcoords
        if color_layer is not None:
            ret_value["color"] = colors
        return ret_value

    def export_geometry(self, object_ref, scene):
        self.progress.begin_task("Exporting geometry for " + object_ref[1]["nodeTable"][0].name + "...")

        # This function exports a single geometry object.

        self.file.write(B"\nGeometryObject $")
        self.file.write(object_ref[1]["structName"])
        self.write_node_table(object_ref)

        self.file.write(B"\n{\n")
        self.inc_indent()

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
                    self.indent_write(B"Morph (index = ", 0, struct_flag)
                    self.write_int(morph_count)

                    if relative and (morph_count != base_index):
                        self.file.write(B", base = ")
                        self.write_int(base_index)

                    self.file.write(B")\n")
                    self.indent_write(B"{\n")
                    self.indent_write(B"Name {string {\"", 1)
                    self.file.write(bytes(block.name, "UTF-8"))
                    self.file.write(B"\"}}\n")
                    self.indent_write(B"}\n")
                    struct_flag = True

                morph_count += 1

            shape_keys.key_blocks[0].value = 1.0
            mesh.update()

        self.indent_write(B"Mesh (primitive = \"triangles\")\n", 0, struct_flag)
        self.indent_write(B"{\n")
        self.inc_indent()

        armature = node.find_armature()
        apply_modifiers = (not armature)

        # Apply all modifiers to create a new mesh with tessfaces.

        # We don't apply modifiers for a skinned mesh because we need the vertex positions
        # before they are deformed by the armature modifier in order to export the proper
        # bind pose. This does mean that modifiers preceding the armature modifier are ignored,
        # but the Blender API does not provide a reasonable way to retrieve the mesh at an
        # arbitrary stage in the modifier stack.

        m = bmesh.new()
        mesh = node.to_mesh(scene, apply_modifiers, "RENDER", True, False)
        m.from_mesh(mesh)

        # Triangulate the mesh
        bmesh.ops.triangulate(m, faces=m.faces, quad_method=0, ngon_method=0)

        m.faces.ensure_lookup_table()
        m.edges.ensure_lookup_table()

        # cleanup loose edges and vertices
        bmesh.ops.delete(m, geom=[v for v in m.verts if len(v.link_faces) == 0], context=1)  # 1 <=> DEL_VERTS

        uv_layers = [layer.name for layer in mesh.uv_textures if layer.active_render]

        export_mesh = self.to_per_vertex_data(m, num_materials=len(mesh.materials), uv_layers=uv_layers)
        vertex_count = len(export_mesh["position"])

        # Write the position array.

        self.indent_write(B"VertexArray (attrib = \"position\")\n")
        self.indent_write(B"{\n")
        self.inc_indent()

        self.indent_write(B"float[3]\t\t// ")
        self.write_int(vertex_count)
        self.indent_write(B"{\n", 0, True)
        self.write_vertex_array3d(export_mesh["position"])
        self.indent_write(B"}\n")

        self.dec_indent()
        self.indent_write(B"}\n\n")

        # Write the normal array.
        if "normal" in export_mesh:
            self.indent_write(B"VertexArray (attrib = \"normal\")\n")
            self.indent_write(B"{\n")
            self.inc_indent()

            self.indent_write(B"float[3]\t\t// ")
            self.write_int(vertex_count)
            self.indent_write(B"{\n", 0, True)
            self.write_vertex_array3d(export_mesh["normal"])
            self.indent_write(B"}\n")

            self.dec_indent()
            self.indent_write(B"}\n")

        # Write the color array if it exists.
        if "color" in export_mesh:
            self.indent_write(B"VertexArray (attrib = \"color\")\n", 0, True)
            self.indent_write(B"{\n")
            self.inc_indent()

            self.indent_write(B"float[3]\t\t// ")
            self.write_int(vertex_count)
            self.indent_write(B"{\n", 0, True)

            self.write_vertex_array3d(export_mesh["color"])

            self.indent_write(B"}\n")

            self.dec_indent()
            self.indent_write(B"}\n")

        # Write the texcoord arrays.
        if "texcoord" in export_mesh:
            count = 0
            for texcoords in export_mesh["texcoord"].values():
                name = B'texcoord'
                if count > 0:
                    name += B'[' + self.to_int_byte(count) + B']'
                self.indent_write(B"VertexArray (attrib = \"" + name + B"\")\n", 0, True)
                self.indent_write(B"{\n")
                self.inc_indent()
                self.indent_write(B"float[2]\t\t// ")
                self.write_int(vertex_count)
                self.indent_write(B"{\n", 0, True)

                self.write_vertex_array2d(texcoords)
                self.indent_write(B"}\n")

                self.dec_indent()
                self.indent_write(B"}\n")

                count += 1
                if count > 2:
                    break

        # If there are multiple morph targets, export them here.
        if shape_keys and False:  # TODO
            shape_keys.key_blocks[0].value = 0.0
            for m in range(1, len(current_morph_value)):
                shape_keys.key_blocks[m].value = 1.0
                mesh.update()

                node.active_shape_key_index = m
                morph_mesh = node.to_mesh(scene, apply_modifiers, "RENDER", True, False)

                # Write the morph target position array.

                self.indent_write(B"VertexArray (attrib = \"position\", morph = ", 0, True)
                self.write_int(m)
                self.file.write(B")\n")
                self.indent_write(B"{\n")
                self.inc_indent()

                self.indent_write(B"float[3]\t\t// ")
                self.write_int(vertex_count)
                self.indent_write(B"{\n", 0, True)
                self.write_morph_position_array3d(export_mesh, morph_mesh.vertices)  # TODO
                self.indent_write(B"}\n")

                self.dec_indent()
                self.indent_write(B"}\n\n")

                # Write the morph target normal array.

                self.indent_write(B"VertexArray (attrib = \"normal\", morph = ")
                self.write_int(m)
                self.file.write(B")\n")
                self.indent_write(B"{\n")
                self.inc_indent()

                self.indent_write(B"float[3]\t\t// ")
                self.write_int(vertex_count)
                self.indent_write(B"{\n", 0, True)
                self.write_morph_normal_array3d(export_mesh, morph_mesh.vertices, morph_mesh.tessfaces)  # TODO
                self.indent_write(B"}\n")

                self.dec_indent()
                self.indent_write(B"}\n")

                bpy.data.meshes.remove(morph_mesh)

        # Write the index arrays.
        for material_index, indices in enumerate(export_mesh["tris"]):
            num_tris = len(indices)
            if num_tris != 0:
                self.indent_write(B"IndexArray (material = ", 0, True)
                self.write_int(material_index)
                self.file.write(B")\n")
                self.indent_write(B"{\n")
                self.inc_indent()

                self.indent_write(B"unsigned_int32[3]\t\t// ")
                self.write_int(num_tris)
                self.indent_write(B"{\n", 0, True)
                self.write_triangle_array(indices)
                self.write(B"\n" + self.get_indent() + B"}\n")

                self.dec_indent()
                self.indent_write(B"}\n")

        # If the mesh is skinned, export the skinning data here.
        if armature and False:  # TODO
            self.export_skin(node, armature, export_mesh)

        # Restore the morph state.

        if shape_keys and False:  # TODO
            node.active_shape_key_index = active_shape_key_index
            node.show_only_shape_key = show_only_shape_key

            for m in range(len(current_morph_value)):
                shape_keys.key_blocks[m].value = current_morph_value[m]

            mesh.update()

        self.dec_indent()
        self.indent_write(B"}\n")

        self.dec_indent()
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
        self.write_node_table(object_ref)

        self.file.write(B"\n{\n")
        self.inc_indent()

        # Export the light's color, and include a separate intensity if necessary.

        self.indent_write(B"Color (attrib = \"light\") {float[3] {")
        self.write_color(obj.color)
        self.file.write(B"}}\n")

        intensity = obj.energy
        if intensity != 1.0:
            self.indent_write(B"Param (attrib = \"intensity\") {float {")
            self.write_float(intensity)
            self.file.write(B"}}\n")

        if is_point:

            # Export a separate attenuation function for each type that's in use.

            falloff = obj.falloff_type

            if falloff == "INVERSE_LINEAR":
                self.indent_write(B"Atten (curve = \"inverse\")\n", 0, True)
                self.indent_write(B"{\n")

                self.indent_write(B"Param (attrib = \"scale\") {float {", 1)
                self.write_float(obj.distance)
                self.file.write(B"}}\n")

                self.indent_write(B"}\n")

            elif falloff == "INVERSE_SQUARE":
                self.indent_write(B"Atten (curve = \"inverse_square\")\n", 0, True)
                self.indent_write(B"{\n")

                self.indent_write(B"Param (attrib = \"scale\") {float {", 1)
                self.write_float(math.sqrt(obj.distance))
                self.file.write(B"}}\n")

                self.indent_write(B"}\n")

            elif falloff == "LINEAR_QUADRATIC_WEIGHTED":
                if obj.linear_attenuation != 0.0:
                    self.indent_write(B"Atten (curve = \"inverse\")\n", 0, True)
                    self.indent_write(B"{\n")

                    self.indent_write(B"Param (attrib = \"scale\") {float {", 1)
                    self.write_float(obj.distance)
                    self.file.write(B"}}\n")

                    self.indent_write(B"Param (attrib = \"constant\") {float {", 1)
                    self.write_float(1.0)
                    self.file.write(B"}}\n")

                    self.indent_write(B"Param (attrib = \"linear\") {float {", 1)
                    self.write_float(obj.linear_attenuation)
                    self.file.write(B"}}\n")

                    self.indent_write(B"}\n\n")

                if obj.quadratic_attenuation != 0.0:
                    self.indent_write(B"Atten (curve = \"inverse_square\")\n")
                    self.indent_write(B"{\n")

                    self.indent_write(B"Param (attrib = \"scale\") {float {", 1)
                    self.write_float(obj.distance)
                    self.file.write(B"}}\n")

                    self.indent_write(B"Param (attrib = \"constant\") {float {", 1)
                    self.write_float(1.0)
                    self.file.write(B"}}\n")

                    self.indent_write(B"Param (attrib = \"quadratic\") {float {", 1)
                    self.write_float(obj.quadratic_attenuation)
                    self.file.write(B"}}\n")

                    self.indent_write(B"}\n")

            if obj.use_sphere:
                self.indent_write(B"Atten (curve = \"linear\")\n", 0, True)
                self.indent_write(B"{\n")

                self.indent_write(B"Param (attrib = \"end\") {float {", 1)
                self.write_float(obj.distance)
                self.file.write(B"}}\n")

                self.indent_write(B"}\n")

            if is_spot:
                # Export additional angular attenuation for spot lights.

                self.indent_write(B"Atten (kind = \"angle\", curve = \"linear\")\n", 0, True)
                self.indent_write(B"{\n")

                end_angle = obj.spot_size * 0.5
                begin_angle = end_angle * (1.0 - obj.spot_blend)

                self.indent_write(B"Param (attrib = \"begin\") {float {", 1)
                self.write_float(begin_angle)
                self.file.write(B"}}\n")

                self.indent_write(B"Param (attrib = \"end\") {float {", 1)
                self.write_float(end_angle)
                self.file.write(B"}}\n")

                self.indent_write(B"}\n")

        self.dec_indent()
        self.file.write(B"}\n")

    def export_camera(self, object_ref):

        # This function exports a single camera object.

        self.file.write(B"\nCameraObject $")
        self.file.write(object_ref[1]["structName"])
        self.write_node_table(object_ref)

        self.file.write(B"\n{\n")
        self.inc_indent()

        obj = object_ref[0]

        self.indent_write(B"Param (attrib = \"fov\") {float {")
        self.write_float(obj.angle_x)
        self.file.write(B"}}\n")

        self.indent_write(B"Param (attrib = \"near\") {float {")
        self.write_float(obj.clip_start)
        self.file.write(B"}}\n")

        self.indent_write(B"Param (attrib = \"far\") {float {")
        self.write_float(obj.clip_end)
        self.file.write(B"}}\n")

        self.dec_indent()
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

        self.indent_write(B"Texture (attrib = \"", 0, True)
        self.file.write(attrib)
        self.file.write(B"\")\n")

        self.indent_write(B"{\n")
        self.inc_indent()

        self.indent_write(B"string {\"")
        self.write_filename(texture_slot.texture.image.filepath.replace("//", ""))
        self.file.write(B"\"}\n")

        # If the texture has a scale and/or offset, then export a coordinate transform.

        uscale = texture_slot.scale[0]
        vscale = texture_slot.scale[1]
        uoffset = texture_slot.offset[0]
        voffset = texture_slot.offset[1]

        if (uscale != 1.0) or (vscale != 1.0) or (uoffset != 0.0) or (voffset != 0.0):
            matrix = [[uscale, 0.0, 0.0, 0.0], [0.0, vscale, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0],
                      [uoffset, voffset, 0.0, 1.0]]

            self.indent_write(B"Transform\n", 0, True)
            self.indent_write(B"{\n")
            self.inc_indent()

            self.indent_write(B"float[16]\n")
            self.indent_write(B"{\n")
            self.write_matrix(matrix)
            self.indent_write(B"}\n")

            self.dec_indent()
            self.indent_write(B"}\n")

        self.dec_indent()
        self.indent_write(B"}\n")

    def export_materials(self):
        # This function exports all of the materials used in the scene.

        for materialRef in self.container.materialArray.items():
            material = materialRef[0]

            self.file.write(B"\nMaterial $")
            self.file.write(materialRef[1]["structName"])
            self.file.write(B"\n{\n")
            self.inc_indent()

            if material.name != "":
                self.indent_write(B"Name {string {\"")
                self.file.write(bytes(material.name, "UTF-8"))
                self.file.write(B"\"}}\n\n")

            intensity = material.diffuse_intensity
            diffuse = [material.diffuse_color[0] * intensity, material.diffuse_color[1] * intensity,
                       material.diffuse_color[2] * intensity]

            self.indent_write(B"Color (attrib = \"diffuse\") {float[3] {")
            self.write_color(diffuse)
            self.file.write(B"}}\n")

            intensity = material.specular_intensity
            specular = [material.specular_color[0] * intensity, material.specular_color[1] * intensity,
                        material.specular_color[2] * intensity]

            if (specular[0] > 0.0) or (specular[1] > 0.0) or (specular[2] > 0.0):
                self.indent_write(B"Color (attrib = \"specular\") {float[3] {")
                self.write_color(specular)
                self.file.write(B"}}\n")

                self.indent_write(B"Param (attrib = \"specular_power\") {float {")
                self.write_float(material.specular_hardness)
                self.file.write(B"}}\n")

            emission = material.emit
            if emission > 0.0:
                self.indent_write(B"Color (attrib = \"emission\") {float[3] {")
                self.write_color([emission, emission, emission])
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

            self.dec_indent()
            self.file.write(B"}\n")

    def export_metrics(self, scene):

        scale = scene.unit_settings.scale_length

        if scene.unit_settings.system == "IMPERIAL":
            scale *= 0.3048

        self.file.write(B"Metric (key = \"distance\") {float {")
        self.write_float(scale)
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
            if nw.nodeRef["nodeType"] == NodeType.geometry:
                armature = nw.item.find_armature()
                if armature:
                    for bone in armature.data.bones:
                        bone_ref = self.container.find_node_wrapper_by_name(bone.name)
                        if bone_ref:
                            # If a node is used as a bone, then we force its type to be a bone.
                            bone_ref.dict["nodeType"] = NodeType.bone

    def execute(self, context):

        start_time = time.time()

        scene = context.scene
        export_all_flag = not self.export_selection
        self.open(self.filepath)
        self.container = ExporterState(export_all_flag, self.sample_animation, scene)

        self.export_metrics(scene)

        original_frame = scene.frame_current
        original_subframe = scene.frame_subframe

        self.progress.begin_task("Preparing objects...")
        for obj in scene.objects:
            if obj.parent is None:
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
