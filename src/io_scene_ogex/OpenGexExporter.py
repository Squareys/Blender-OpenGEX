import bpy
import bmesh
import time
from mathutils import Matrix
from bpy_extras.io_utils import ExportHelper
from io_scene_ogex.NodeWrapper import NodeWrapper
from io_scene_ogex.ExporterState import *
from io_scene_ogex.pygex import *

__author__ = 'Eric Lengyel, Jonathan Hale, Nicolas Wehrle'

k_animation_sampled = 0
k_animation_linear = 1
k_animation_bezier = 2

k_export_epsilon = 1.0e-6

struct_identifiers = [B"Node", B"BoneNode", B"GeometryNode", B"LightNode", B"CameraNode"]
axis_name = [B"x", B"y", B"z"]

image_format_items = [
    ('BMP', 'BMP', '', 0),
    ('IRIS', 'Iris', '', 1),
    ('PNG', 'PNG', '', 2),
    ('JPEG', 'JPEG', '', 3),
    ('JPEG2000', 'JPEG 2000', '', 4),
    ('TARGA', 'Targa', '', 5),
    ('TARGA_RAW', 'Targa Raw', '', 6),
    ('CINEON', 'Cineon', '', 7),
    ('DPX', 'DPX', '', 8),
    ('OPEN_EXR_MULTILAYER', 'OpenEXR MultiLayer', '', 9),
    ('OPEN_EXR', 'OpenEXR', '', 10),
    ('HDR', 'Radiance HDR', '', 11),
    ('TIFF', 'TIFF', '', 12)]

oddl_format_items = [
    ('TEXT', 'Text', 'Human readable text.', 0),
    ('COMPRESSED_TEXT', 'Compressed Text',
     'Text without whitespaces, tabs or newlines.\nSmaller and faster to export.', 1)
]


class ProgressLog:
    def __init__(self):
        self.lastTime = 0
        pass

    def begin_task(self, message):
        print(message, end="", flush=True)
        self.lastTime = time.time()

    def end_task(self):
        print(" done! ({:.2f} ms)".format((time.time() - self.lastTime) * 1000))


class OpenGexExporter(bpy.types.Operator, ExportHelper):
    """Export to OpenGEX format"""
    bl_idname = "export_scene.ogex"
    bl_label = "Export OpenGEX"
    filename_ext = ".ogex"

    export_selection = bpy.props.BoolProperty(name="Export Selection Only",
                                              description="Export only selected objects", default=False)
    sample_animation = bpy.props.BoolProperty(name="Force Sampled Animation",
                                              description="Always export animation as per-frame samples",
                                              default=False)

    # Advanced settings
    export_only_first_material = bpy.props.BoolProperty(name="Export First Material Only",
                                                        description="Only export the first material of any object. May"
                                                                    "be useful for some game engines for example.",
                                                        default=False)
    rounding = bpy.props.IntProperty(name="Float Rounding Decimal Places",
                                     description="Amount of decimal places to round floating point values to.",
                                     default=6)
    oddl_format = bpy.props.EnumProperty(name="OpenDDL Format", items=oddl_format_items, default='TEXT',
                                         description="Format for the exported OpenGEX (based on OpenDDL) file.")

    # Extension settings
    export_custom_properties = bpy.props.BoolProperty(name="Export Custom Properties",
                                                      description="Export object custom properties to an OGEX"
                                                                  "Extension structure",
                                                      default=False)
    export_physics = bpy.props.BoolProperty(name="Export Game Physics",
                                            description="Export game physics to an OGEX 'PhysicsMaterial' and"
                                                        "'PhysicsConstraint' Extension structures.",
                                            default=False)
    export_ambient = bpy.props.BoolProperty(name="Export Ambient Color",
                                            description="Export world ambient color and material ambient factors as a"
                                                        "not officially specified Param.",
                                            default=False)
    export_audio = bpy.props.BoolProperty(name="Export Audio Sources",
                                          description="Export Speaker objects to an OGEX Extension structure.",
                                          default=False)
    audio_path_prefix = bpy.props.StringProperty(name="Audio Path Prefix", default='',
                                                 description="Prefix relative to the exported scene file\n"
                                                             "to set audio paths to.\n\nExample: audio/")

    # image texture export properties
    export_image_textures = bpy.props.BoolProperty(name="Export Image Textures",
                                                   description="Whether to export images for exported textures.")
    image_path_prefix = bpy.props.StringProperty(name="Image Path Prefix", default='',
                                                 description="Prefix relative to the exported scene file\n"
                                                             "to export image textures to.\n\nExample: textures/")
    image_format = bpy.props.EnumProperty(name="Image Format", items=image_format_items, default='PNG',
                                          description="Format for exported image textures.")

    def __init__(self):
        super().__init__()
        self.progress = ProgressLog()
        self.container = None
        self.document = None
        self.unresolved_refs = []

    @staticmethod
    def get_shape_keys(mesh):

        shape_keys = mesh.shape_keys
        if shape_keys and (len(shape_keys.key_blocks) > 1):
            return shape_keys

        return None

    def find_node(self, name):
        # TODO this does not seem very efficient...
        for nodeRef in self.node_array.items():
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
                return k_animation_sampled

        if bezier_count == 0:
            return k_animation_linear
        elif linear_count == 0:
            return k_animation_bezier

        return k_animation_sampled

    @staticmethod
    def animation_keys_differ(fcurve):

        key_count = len(fcurve.keyframe_points)
        if key_count > 0:
            key1 = fcurve.keyframe_points[0].co[1]

            for i in range(1, key_count):
                key2 = fcurve.keyframe_points[i].co[1]
                if math.fabs(key2 - key1) > k_export_epsilon:
                    return True

        return False

    @staticmethod
    def animation_tangents_nonzero(fcurve):

        key_count = len(fcurve.keyframe_points)
        if key_count > 0:
            key = fcurve.keyframe_points[0].co[1]
            left = fcurve.keyframe_points[0].handle_left[1]
            right = fcurve.keyframe_points[0].handle_right[1]
            if (math.fabs(key - left) > k_export_epsilon) or (math.fabs(right - key) > k_export_epsilon):
                return True

            for i in range(1, key_count):
                key = fcurve.keyframe_points[i].co[1]
                left = fcurve.keyframe_points[i].handle_left[1]
                right = fcurve.keyframe_points[i].handle_right[1]
                if (math.fabs(key - left) > k_export_epsilon) or (math.fabs(right - key) > k_export_epsilon):
                    return True

        return False

    @staticmethod
    def animation_present(fcurve, kind):

        if kind != k_animation_bezier:
            return OpenGexExporter.animation_keys_differ(fcurve)

        return (OpenGexExporter.animation_keys_differ(fcurve)) or (OpenGexExporter.animation_tangents_nonzero(fcurve))

    @staticmethod
    def matrices_differ(m1, m2):
        """
        Compare matrices using the export epsilon.
        :param m1: Matrix A
        :param m2: Matrix B
        :return: True if at least one component of A differs significantly form the analog component in B
        """
        for i in range(4):
            for j in range(4):
                if math.fabs(m1[i][j] - m2[i][j]) > k_export_epsilon:
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

    def export_key_times(self, function_curve):
        """
        Export points of a time curve. Each value on the curve will be offset to the begin frame.
        :param function_curve: the curve
        :return: a Key DdlStructure
        """
        return Key(data=[(p.co[0] - self.container.beginFrame) * self.container.frameTime
                         for p in function_curve.keyframe_points])

    def export_key_time_control_points(self, function_curve):
        """
        Export handles (/control points) of a time bezier curve. Each handle on the curve will be offset to the begin frame.
        :param function_curve: the curve
        :return: two Key DdlStructures in a list
        """
        return [
            Key(kind=B"-control",
                data=[(point.handle_left[0] - self.container.beginFrame) * self.container.frameTime
                      for point in function_curve.keyframe_points]),
            Key(kind=B"+control",
                data=[(point.handle_right[0] - self.container.beginFrame) * self.container.frameTime
                      for point in function_curve.keyframe_points])
        ]

    @staticmethod
    def export_key_values(function_curve):
        """
        Export points of a value curve.
        :param function_curve: the curve
        :return: a Key DdlStructure
        """
        return Key(data=[p.co[1] for p in function_curve.keyframe_points])

    @staticmethod
    def export_key_value_control_points(function_curve):
        """
        Export handles (/control points) of a value bezier curve.
        :param function_curve: the curve
        :return: two Key DdlStructures in a list
        """
        return [
            Key(kind=B"-control", data=[p.handle_left[1] for p in function_curve.keyframe_points]),
            Key(kind=B"+control", data=[p.handle_right[1] for p in function_curve.keyframe_points])
        ]

    def export_animation_track(self, function_curve, kind, target):
        """
        Export a function curve as a Track DDL structure.
        :param function_curve: the curve
        :param kind: Animation type (linear or bezier)
        :param target: the structure that is being animated
        :return: the Track DdlStructure
        """
        # This function exports a single animation track. The curve types for the
        # Time and Value structures are given by the kind parameter.
        track_struct = Track(target=target)

        if kind != k_animation_bezier:
            track_struct.children.extend([
                Time(children=self.export_key_times(function_curve)),
                Value(children=self.export_key_values(function_curve))
            ])
        else:
            track_struct.children.extend([
                Time(curve=B"bezier",
                     children=[self.export_key_times(function_curve)] + self.export_key_time_control_points(function_curve)),
                Value(curve=B"bezier",
                      children=[self.export_key_values(function_curve)] + self.export_key_value_control_points(function_curve))
            ])

        return track_struct

    def export_node_sampled_animation(self, nw, node, scene):
        """
        Export animation as full 4x4 matrices for each frame.
        :param nw: Node wrapper
        :param node: the node to export the animated transforms for
        :param scene: the current scene
        :return: the created Animation DdlStructure
        """
        # Save frame settings to later restore
        previous_frame = scene.frame_current
        previous_subframe = scene.frame_subframe

        # if transform for frames is the same, there is no need for animation.
        has_animation = False
        first_frame_transform = node.matrix_local.copy()
        for i in range(self.container.beginFrame, self.container.endFrame):
            # matrix_local adapts to the current frame.
            scene.frame_set(i)
            cur_frame_transform = node.matrix_local

            if OpenGexExporter.matrices_differ(first_frame_transform, cur_frame_transform):
                has_animation = True
                break

        # if there is an animation, assemble the Animation DdlStructure
        animation_struct = None
        if has_animation:
            # helper to get local transformation matrix at a certain frame index
            def get_matrix_local_at_frame(i):
                scene.frame_set(i)
                blender_matrix = self.handle_offset(node.matrix_local, nw.offset)
                return itertools.chain(*zip(*blender_matrix))  # create list of all elements

            begin_frame = self.container.beginFrame
            end_frame = self.container.endFrame
            frame_time = self.container.frameTime

            animation_struct = DdlStructure(B"Animation", children=[
                Track(target=B"%transform", children=[
                    Time(children=[
                        Key(data=[((i - begin_frame) * frame_time) for i in range(begin_frame, end_frame + 1)])
                    ]),
                    Value(children=[
                        Key(data=[get_matrix_local_at_frame(i) for i in range(begin_frame, end_frame + 1)],
                            vector_size=16)
                    ])
                ])
            ])

        # restore "current frame" settings
        scene.frame_set(previous_frame, previous_subframe)

        return animation_struct

    def export_bone_sampled_animation(self, pose_bone, scene):
        """
        :param pose_bone: bone to export the animation of
        :param scene: scene of the bone
        :return: an optional Animation DdlStructure
        """

        # This function exports bone animation as full 4x4 matrices for each frame.

        current_frame = scene.frame_current
        current_subframe = scene.frame_subframe

        has_animation = False
        m1 = pose_bone.matrix.copy()

        # search for a frame which has a different bone matrix than in an other frame
        for i in range(self.container.beginFrame, self.container.endFrame):
            scene.frame_set(i)
            m2 = pose_bone.matrix
            if OpenGexExporter.matrices_differ(m1, m2):
                has_animation = True
                break

        animation_structure = None

        if has_animation:
            parent = pose_bone.parent

            # -----
            # Helpers for the generator of the Value structure data
            def get_matrix_at_frame(frame_index):
                scene.frame_set(frame_index)
                return pose_bone.matrix

            def get_matrix_at_frame_with_parent(frame_index):
                scene.frame_set(frame_index)
                if math.fabs(parent.matrix.determinant()) > k_export_epsilon:
                    return parent.matrix.inverted() * pose_bone.matrix
                else:
                    return pose_bone.matrix
            # -----

            get_value_for_frame = get_matrix_at_frame_with_parent if parent is not None else get_matrix_at_frame

            animation_structure = DdlStructure(B"Animation", children=[
                Track(target=B"%transform", children=[
                    Time(children=[
                        Key(data=[(i - self.container.beginFrame) * self.container.frameTime
                                  for i in range(self.container.beginFrame, self.container.endFrame + 1)])
                    ]),
                    Value(children=[
                        Key(data=[get_value_for_frame(i)
                                  for i in range(self.container.beginFrame, self.container.endFrame + 1)],
                            vector_size=16)
                    ])
                ])
            ])

        scene.frame_set(current_frame, current_subframe)

        return animation_structure

    def export_morph_weight_sampled_animation_track(self, block, target, scene):
        # TODO doc
        """
        :param block:
        :param target:
        :param scene:
        :return: a Track DdlStructure
        """
        current_frame = scene.frame_current
        current_subframe = scene.frame_subframe

        # helper function for generater of Value Key data
        def get_frame_value(frame_index):
            scene.frame_set(frame_index)
            return block.value

        track_struct = Track(target=target, children=[
            Time(children=[
                Key(data=[(i - self.container.beginFrame) * self.container.frameTime
                          for i in range(self.container.beginFrame, self.container.endFrame + 1)])
            ]),
            Value(children=[
                Key(data=[get_frame_value(i) for i in range(self.container.beginFrame, self.container.endFrame + 1)])
            ])
        ])

        scene.frame_set(current_frame, current_subframe)

        return track_struct

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

        structs = []

        if (not sampled_animation) and node.animation_data:
            action = node.animation_data.action
            if action:
                for fcurve in action.fcurves:
                    kind = OpenGexExporter.classify_animation_curve(fcurve)
                    if kind != k_animation_sampled:
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
            if self.export_physics and (node.parent is not None) \
                    and node.parent.game.physics_type != 'NO_COLLISION':
                # a child of a scale as half extent object
                parent_props = node.parent.game
                if parent_props.use_collision_bounds and parent_props.collision_bounds_type not in \
                        ['CONVEX_HULL', 'TRIANGLE_MESH']:
                    inverted_scale = Matrix()
                    scale = node.parent.scale
                    inverted_scale[0][0] = scale[0]
                    inverted_scale[1][1] = scale[1]
                    inverted_scale[2][2] = scale[2]
                    transformation = inverted_scale * transformation
            if self.export_physics and node.game.physics_type != 'NO_COLLISION':
                # a child of a scale as half extent object
                if node.game.use_collision_bounds and node.game.collision_bounds_type not in \
                        ['CONVEX_HULL', 'TRIANGLE_MESH']:
                    # simply remove scale
                    transformation = Matrix.Translation(transformation.translation) \
                                     * transformation.to_quaternion().to_matrix().to_4x4()

            transform_struct = Transform(matrix=self.handle_offset(transformation, nw.offset))
            structs.append(transform_struct)
            if sampled_animation:
                transform_struct.name = B"transform"
                transform_struct.name_is_global = False

                animation_struct = self.export_node_sampled_animation(nw, node, scene)

                if animation_struct is not None:
                    structs.append(animation_struct)

        else:
            animation_struct = DdlStructure(B"Animation", props=OrderedDict([
                (B"begin", (action.frame_range[0] - self.container.beginFrame) * self.container.frameTime),
                (B"end", (action.frame_range[1] - self.container.beginFrame) * self.container.frameTime)
            ]))

            delta_translation = node.delta_location
            if delta_position_animated:

                # When the delta location is animated, write the x, y, and z components separately
                # so they can be targeted by different tracks having different sets of keys.

                for i in range(3):
                    pos = delta_translation[i]
                    if delta_pos_animated[i] or (math.fabs(pos) > k_export_epsilon):
                        structs.append(Translation(name=B"d" + axis_name[i] + B"pos", kind=axis_name[i], value=pos))
                    if delta_pos_animated[i]:
                        animation_struct.children.append(
                            self.export_animation_track(delta_pos_anim_curve[i], delta_pos_anim_kind[i], structs[-1])
                        )

            elif ((math.fabs(delta_translation[0]) > k_export_epsilon) or (
                        math.fabs(delta_translation[1]) > k_export_epsilon) or (
                        math.fabs(delta_translation[2]) > k_export_epsilon)):
                structs.append(Translation(value=delta_translation, vector_size=3))

            translation = node.location
            if position_animated:
                # When the location is animated, write the x, y, and z components separately
                # so they can be targeted by different tracks having different sets of keys.
                for i in range(3):
                    pos = translation[i]
                    if (pos_animated[i]) or (math.fabs(pos) > k_export_epsilon):
                        structs.append(Translation(name=axis_name[i] + B"pos", kind=axis_name[i], value=pos))
                    if pos_animated[i]:
                        animation_struct.children.append(
                            self.export_animation_track(pos_anim_curve[i], pos_anim_kind[i], structs[-1])
                        )

            elif ((math.fabs(translation[0]) > k_export_epsilon) or (math.fabs(translation[1]) > k_export_epsilon) or (
                        math.fabs(translation[2]) > k_export_epsilon)):
                structs.append(Translation(value=translation, vector_size=3))

            if delta_rotation_animated:

                # When the delta rotation is animated, write three separate Euler angle rotations
                # so they can be targeted by different tracks having different sets of keys.

                for i in range(3):
                    axis = ord(mode[2 - i]) - 0x58
                    angle = node.delta_rotation_euler[axis]
                    if (delta_rot_animated[axis]) or (math.fabs(angle) > k_export_epsilon):
                        structs.append(Rotation(name=B"d" + axis_name[axis] + B"rot", kind=axis_name[axis], value=angle))
                    if delta_rot_animated[i]:
                        animation_struct.children.append(
                            self.export_animation_track(delta_rot_anim_curve[i], delta_rot_anim_kind[i], structs[-1])
                        )

            else:

                # When the delta rotation is not animated, write it in the representation given by
                # the node's current rotation mode. (There is no axis-angle delta rotation.)

                if mode == "QUATERNION":
                    quaternion = node.delta_rotation_quaternion
                    if ((math.fabs(quaternion[0] - 1.0) > k_export_epsilon) or (
                                math.fabs(quaternion[1]) > k_export_epsilon) or (
                                math.fabs(quaternion[2]) > k_export_epsilon) or (
                                math.fabs(quaternion[3]) > k_export_epsilon)):
                        structs.append(Translation(value=quaternion, kind=B"quaternion", vector_size=4))

                else:
                    for i in range(3):
                        axis = ord(mode[2 - i]) - 0x58
                        angle = node.delta_rotation_euler[axis]
                        if math.fabs(angle) > k_export_epsilon:
                            structs.append(Rotation(kind=axis_name[axis], value=angle))

            if rotation_animated:

                # When the rotation is animated, write three separate Euler angle rotations
                # so they can be targeted by different tracks having different sets of keys.

                for i in range(3):
                    axis = ord(mode[2 - i]) - 0x58
                    angle = node.rotation_euler[axis]
                    if rot_animated[axis] or (math.fabs(angle) > k_export_epsilon):
                        structs.append(Rotation(name=axis_name[axis] + B"rot", kind=axis_name[axis], value=angle))
                    if rot_animated[i]:
                        animation_struct.children.append(
                            self.export_animation_track(rot_anim_curve[i], rot_anim_kind[i], structs[-1])
                        )

            else:

                # When the rotation is not animated, write it in the representation given by
                # the node's current rotation mode.

                if mode == "QUATERNION":
                    quaternion = node.rotation_quaternion
                    if ((math.fabs(quaternion[0] - 1.0) > k_export_epsilon) or (
                                math.fabs(quaternion[1]) > k_export_epsilon) or (
                                math.fabs(quaternion[2]) > k_export_epsilon) or (
                                math.fabs(quaternion[3]) > k_export_epsilon)):
                        structs.append(Translation(value=quaternion, kind=B"quaternion", vector_size=4))

                elif mode == "AXIS_ANGLE":
                    if math.fabs(node.rotation_axis_angle[0]) > k_export_epsilon:
                        structs.append(Translation(value=node.rotation_axis_angle, kind=B"axis", vector_size=4))

                else:
                    for i in range(3):
                        axis = ord(mode[2 - i]) - 0x58
                        angle = node.rotation_euler[axis]
                        if math.fabs(angle) > k_export_epsilon:
                            structs.append(Rotation(kind=axis_name[axis], value=angle))

            delta_scale = node.delta_scale
            if delta_scale_animated:

                # When the delta scale is animated, write the x, y, and z components separately
                # so they can be targeted by different tracks having different sets of keys.

                for i in range(3):
                    scl = delta_scale[i]
                    if delta_scl_animated[i] or (math.fabs(scl) > k_export_epsilon):
                        structs.append(Scale(name=B"d" + axis_name[i] + B"scl", kind=axis_name[i], value=scl))
                    if delta_scl_animated[i]:
                        animation_struct.children.append(
                            self.export_animation_track(delta_scale_anim_curve[i], delta_scale_anim_kind[i], structs[-1])
                        )

            elif ((math.fabs(delta_scale[0] - 1.0) > k_export_epsilon) or (
                        math.fabs(delta_scale[1] - 1.0) > k_export_epsilon) or (
                        math.fabs(delta_scale[2] - 1.0) > k_export_epsilon)):
                structs.append(Scale(value=delta_scale, vector_size=3))

            scale = node.scale
            if scale_animated:
                # When the scale is animated, write the x, y, and z components separately
                # so they can be targeted by different tracks having different sets of keys.
                for i in range(3):
                    scl = scale[i]
                    if scl_animated[i] or (math.fabs(scl) > k_export_epsilon):
                        structs.append(Scale(name=axis_name[i] + B"scl", kind=axis_name[i], value=scl))
                    if scl_animated[i]:
                        animation_struct.children.append(
                            self.export_animation_track(scale_anim_curve[i], scale_anim_kind[i], structs[-1])
                        )

            elif ((math.fabs(scale[0] - 1.0) > k_export_epsilon) or (math.fabs(scale[1] - 1.0) > k_export_epsilon) or (
                        math.fabs(scale[2] - 1.0) > k_export_epsilon)):
                structs.append(Scale(value=scl, vector_size=3))

            structs.append(animation_struct)

        return structs

    @staticmethod
    def handle_offset(matrix, offset):
        if not offset:
            return matrix

        m = matrix.copy()
        m.translation -= offset
        return m

    def export_bone_transform(self, nw, bw, scene):
        # TODO doc!
        """
        :return: a Transform DdlStructure
        """

        curve_array = self.export_bone_animation(nw.item, bw.item.name)
        animation = ((len(curve_array) != 0) or self.container.sampleAnimationFlag)

        transform = bw.item.matrix_local.copy()
        parent_bone_wrapper = bw.parent
        if parent_bone_wrapper and (math.fabs(parent_bone_wrapper.item.matrix_local.determinant()) > k_export_epsilon):
            transform = parent_bone_wrapper.item.matrix_local.inverted() * transform

        pose_bone = nw.item.pose.bones.get(bw.item.name)
        if pose_bone:
            transform = pose_bone.matrix.copy()
            parent_pose_bone = pose_bone.parent
            if parent_pose_bone and (math.fabs(parent_pose_bone.matrix.determinant()) > k_export_epsilon):
                transform = parent_pose_bone.matrix.inverted() * transform

        transform_struct = Transform(matrix=transform)

        if animation:
            transform_struct.name = B"transform"
            transform_struct.name_is_global = False

            if pose_bone:
                animation_struct = self.export_bone_sampled_animation(pose_bone, scene)

                if animation_struct is not None:
                    transform_struct.children.append(animation_struct)

        return transform_struct

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

        structs = []
        for (k, block) in enumerate(shape_keys.key_blocks):
            morph_weight_struct = DdlStructure(B"MorphWeight", props={B"index": k}, children=[
                DdlPrimitive(data_type=DataType.float, data=[block.value if (block.name != reference_name) else 1.0])
            ])

            if animated:
                morph_weight_struct.name = B"mw"
                morph_weight_struct.name_is_global = False

            structs.append(morph_weight_struct)

        if animated:
            animation_struct = DdlStructure(B"Animation", props=OrderedDict[
                (B"begin", (action.frame_range[0] - self.container.beginFrame) * self.container.frameTime),
                (B"end", (action.frame_range[1] - self.container.beginFrame) * self.container.frameTime)], children=[])

            for a in range(len(curve_array)):
                k = index_array[a]
                target = bytes("%mw" + str(k), "UTF-8")

                fcurve = curve_array[a]
                kind = OpenGexExporter.classify_animation_curve(fcurve)
                if (kind != k_animation_sampled) and (not self.container.sampleAnimationFlag):
                    animation_struct.children.append(self.export_animation_track(fcurve, kind, target))
                else:
                    animation_struct.children.append(
                        self.export_morph_weight_sampled_animation_track(shape_keys.key_blocks[k], target, scene))

            self.dec_indent()
            self.indent_write(B"}\n")

    def export_bone(self, nw, bw, scene):  # armature, bone, scene):
        bone_struct = None
        structs = []

        if nw.nodeRef:
            bone_struct = DdlStructure(struct_identifiers[nw.nodeRef["nodeType"]], name=nw.nodeRef["structName"],
                                       children=[Name(name=bw.item.name)])
            structs.append(bone_struct)
            nw.nodeRef["struct"] = bone_struct

            bone_struct.children.append(self.export_bone_transform(nw, bw, scene))

            for child in bw.children:
                bone_struct.children.extend(self.export_bone(nw, child, scene))
        else:
            for child in bw.children:
                structs.extend(self.export_bone(nw, child, scene))

        # Export any ordinary nodes that are parented to this bone.
        bone_subnode_array = self.container.boneParent_array.get(bw.item.name)
        if bone_subnode_array:
            pose_bone = None
            if not bw.item.use_relative_parent:
                pose_bone = nw.item.pose.bones.get(bw.item.name)

            for subnode_wrapper in bone_subnode_array:
                node = self.export_node(subnode_wrapper, scene, pose_bone)
                if bone_struct is None:
                    structs.append(node)
                else:
                    bone_struct.children.append(node)

        return structs

    def export_node(self, nw, scene, pose_bone=None):

        # This function exports a single node in the scene and includes its name,
        # object reference, material references (for geometries), and transform.
        # Subnodes are then exported recursively.

        if nw.nodeRef:

            # Export the object reference and material references.
            obj = nw.item.data
            node_type = nw.nodeRef["nodeType"]

            if node_type == NodeType.geometry:
                mesh = nw.item

                geometry = self.export_geometry(scene, node=mesh, mesh=mesh.data)
                materials = self.export_materials(mesh, mesh.material_slots)
                struct = GeometryNode(mesh=nw.item,
                                      name=nw.nodeRef["structName"],
                                      materials=materials,
                                      geometry=geometry,
                                      use_custom_properties=self.export_custom_properties)

                # TODO Shape Keys?
                shape_keys = OpenGexExporter.get_shape_keys(mesh.data)
                if shape_keys:
                    # FIXME Wrapper or item?
                    self.export_morph_weights(mesh, shape_keys, scene)
            else:
                struct = Node(struct_identifiers[node_type],
                              obj=nw.item,
                              name=nw.nodeRef["structName"],
                              children=[],
                              use_custom_properties=self.export_custom_properties)

            nw.nodeRef["struct"] = struct

            if node_type == NodeType.light:
                struct.children.append(ObjectRef(ref_object=self.export_light(nw.item, obj)))
            elif node_type == NodeType.camera:
                struct.children.append(ObjectRef(ref_object=self.export_camera(nw.item, obj)))

            if pose_bone:
                # If the node is parented to a bone and is not relative, then undo the bone's transform.
                if math.fabs(pose_bone.matrix.determinant()) > k_export_epsilon:
                    struct.children.append(Transform(pose_bone.matrix.inverted()))

            # Export the transform. If the node is animated, then animation tracks are exported here.
            struct.children.extend(self.export_node_transformation(nw, scene))

            if nw.bones:
                for bw in nw.bones:
                    self.export_bone(nw, bw, scene)  # TODO

        # export physics properties
        if self.export_physics:
            if nw.item.game.physics_type != 'NO_COLLISION' and (nw.item.parent is None or not nw.item.parent.game.use_collision_compound):
                struct.children.append(self.export_physics_properties(scene, nw.item))

                for constraint in nw.item.constraints:
                    if constraint.type == 'RIGID_BODY_JOINT' and constraint.target is not None:
                        struct.children.append(self.export_physics_constraint(constraint))

        if self.export_audio and nw.item.type == 'SPEAKER':
            struct.children.append(self.export_audio_properties(nw.item.data))

        for subnode in nw.children:
            if subnode.parent.item.type != "BONE":
                substructure = self.export_node(subnode, scene)
                struct.children.append(substructure)
                substructure = None

        return struct

    @staticmethod
    def almost_equal(a, b, rtol=1.0000000000000001e-05, atol=1e-08):
        """
        Compares whether two floats are almost equal
        :param a: first float
        :param b: second float
        :param rtol: relative tolearance
        :param atol: absolute tolerance
        :return: True if the floats are almost equal
        """
        return math.fabs(a - b) <= (atol + rtol * math.fabs(b))

    SHAPE_TYPE_TO_EXTENSION = {"BOX": B"BoxShape",
                               "SPHERE": B"SphereShape",
                               "CYLINDER": B"CylinderShape",
                               "CONE": B"ConeShape",
                               "CONVEX_HULL": B"ConvexHullShape",
                               "TRIANGLE_MESH": B"TriangleMeshShape",
                               "CAPSULE": B"CapsuleShape"}

    def export_physics_properties(self, scene, o):
        props = o.game
        struct = Extension(B"PhysicsMaterial", children=[
            Extension(B"PM/type", children=[
                # physics collision type
                DdlPrimitive(DataType.string, data=[props.physics_type])
            ])
        ])

        def create_float_property(name, value, default):
            if not self.almost_equal(value, default):
                struct.children.append(Extension(B"PM/" + name, children=[
                    DdlPrimitive(DataType.float, data=[value])
                ]))

        # export mass
        create_float_property(b"mass", props.mass, default=1.0)
        create_float_property(b"radius", props.radius, default=1.0)
        create_float_property(b"form_factor", props.form_factor, default=0.4)

        create_float_property(b"linear_vel_min", props.velocity_min, default=0.0)
        create_float_property(b"linear_vel_max", props.velocity_max, default=0.0)
        create_float_property(b"angular_vel_min", props.angular_velocity_min, default=0.0)
        create_float_property(b"angular_vel_max", props.angular_velocity_max, default=0.0)

        create_float_property(b"damping", props.damping, default=0.04)
        create_float_property(b"rot_damping", props.rotation_damping, default=0.1)

        # get physics material of object
        if o.type == 'MESH':
            if len(o.material_slots) != 0:
                # blender game engine only uses the first, therefore only that will be exported.
                slot = o.material_slots[0]
                if slot.material.game_settings.physics:
                    pmat = slot.material.physics

                    create_float_property(b"friction", pmat.friction, default=0.5)
                    create_float_property(b"elasticity", pmat.elasticity, default=0.0)

                    # force field
                    if props.use_material_physics_fh:
                        create_float_property(b"force", pmat.fh_force, default=0.0)
                        create_float_property(b"force_distance", pmat.fh_distance, default=0.0)
                        create_float_property(b"force_damping", pmat.fh_damping, default=0.0)

                        if pmat.use_fh_normal:
                            struct.children.append(Extension(B"PM/force_use_normal", children=[
                                DdlPrimitive(DataType.bool, data=[True])
                            ]))

        if props.lock_location_x or props.lock_location_y or props.lock_location_z:
            lock_vector = [props.lock_location_x, props.lock_location_y, props.lock_location_z]
            struct.children.append(Extension(B"PM/linear_factor", children=[
                DdlPrimitive(DataType.float, data=[1.0 if b else 0.0 for b in lock_vector])
            ]))

        if props.physics_type == 'RIGID_BODY' and (props.lock_rotation_x or props.lock_rotation_y or props.lock_rotation_z):
            lock_vector = [props.lock_rotation_x, props.lock_rotation_y, props.lock_rotation_z]
            struct.children.append(Extension(B"PM/angular_factor", children=[
                DdlPrimitive(DataType.float, data=[1.0 if b else 0.0 for b in lock_vector])
            ]))

        if props.use_anisotropic_friction:
            struct.children.append(Extension(B"PM/anisotropic_friction", children=[
                DdlPrimitive(DataType.float,
                             data=props.friction_coefficients)
            ]))

        # calculate collision group and mask
        collision_mask = 0
        collision_group = 0

        for i in range(16):
            if props.collision_group[i]:
                collision_group |= 1 << i
            if props.collision_mask[i]:
                collision_mask |= 1 << i

        if collision_group != 0x01:
            struct.children.append(Extension(B"PM/collision_group", children=[
                DdlPrimitive(DataType.unsigned_int16, data=[collision_group])
            ]))

        if collision_mask != 0xFF:
            struct.children.append(Extension(B"PM/collision_mask", children=[
                DdlPrimitive(DataType.unsigned_int16, data=[collision_mask])
            ]))

        if props.use_collision_bounds and props.physics_type not in {'NAVMESH', 'OCCLUDER'}:
            shape_struct = self.export_collision_bounds(o, scene)

            struct.children.append(Extension(B"PM/shape", children=[
                shape_struct
            ]))

        return struct

    def export_collision_bounds(self, o, scene, force_no_compound=False, parent_scaling=[1.0, 1.0, 1.0]):
        if o.game.use_collision_compound and not force_no_compound:
            compound_struct = Extension(B"CompoundShape", children=[])

            compound_struct.children.append(Extension(B"CompoundChild", children=[
                self.export_collision_bounds(o, scene, True)
            ]))

            # Blender does not seem to provide component-wise multiplication. '*' is dot product.
            parent_scaling = [x*y for (x, y) in zip(o.scale, parent_scaling)]

            for child in o.children:
                transform = Matrix.Scale(parent_scaling[0], 4, [1, 0, 0]) * \
                            Matrix.Scale(parent_scaling[1], 4, [0, 1, 0]) * \
                            Matrix.Scale(parent_scaling[2], 4, [0, 0, 1]) * \
                            child.matrix_local
                if self.matrices_differ(transform, Matrix()):
                    compound_struct.children.append(Extension(B"CompoundChild", children=[
                        DdlTextWriter.set_max_elements_per_line(
                            DdlPrimitive(DataType.float,
                                         data=[tuple(itertools.chain(*zip(*transform)))],
                                         vector_size=16),
                            elements=4),
                        self.export_collision_bounds(child, scene, parent_scaling=child.scale)
                    ]))
                else:
                    compound_struct.children.append(Extension(B"CompoundChild", children=[
                        self.export_collision_bounds(child, scene, parent_scaling=child.scale)
                    ]))

            return compound_struct

        else:
            # export collision shape
            shape_type = o.game.collision_bounds_type
            shape_struct = Extension(self.SHAPE_TYPE_TO_EXTENSION[shape_type], children=[])

            if shape_type not in {'CONVEX_HULL', 'TRIANGLE_MESH'}:
                if shape_type == 'SPHERE':
                    # export radius of bounding sphere. Same as "radius" property.
                    # TODO: Deprecated.
                    shape_struct.add_primitive(DataType.float, data=[o.game.radius])
                else:
                    # export scale as half-extents
                    shape_struct.add_primitive(DataType.float, data=[o.scale], vector_size=3)
            else:
                # export geometry as triangle mesh
                shape_struct.add_primitive(DataType.ref, [self.export_geometry(scene, node=o, mesh=o.data)])

            # collision shape margin
            shape_struct.children.append(Extension(B"PM/margin", children=[
                DdlPrimitive(DataType.float, data=[o.game.collision_margin])
            ]))

            return shape_struct

    def export_physics_constraint(self, constraint):
        struct = Extension(B"PhysicsConstraint", children=[
            Extension(B"PC/pivot_type", children=[
                DdlPrimitive(DataType.string, data=[constraint.pivot_type])
            ])
        ])

        if constraint.target is not None:
            # FIXME: Name is not unique! Because of linked objects there can be more that one object with the same name
            target_struct = Extension(B"PC/target", children=[
                DdlPrimitive(DataType.ref, data=[constraint.target.name])
            ])
            struct.children.append(target_struct)
            self.unresolved_refs.append(target_struct.children[0])

        if constraint.use_linked_collision:
            struct.children.append(Extension(B"PC/use_linked_collision", children=[
                DdlPrimitive(DataType.bool, data=[constraint.use_linked_collision])
            ]))

        if constraint.pivot_x != 0.0 or constraint.pivot_y != 0.0 or constraint.pivot_z != 0.0:
            struct.children.append(Extension(B"PC/pivot", children=[
                DdlPrimitive(DataType.float,
                             data=[constraint.pivot_x,
                                   constraint.pivot_y,
                                   constraint.pivot_z])
            ]))

        if constraint.axis_x != 0.0 or constraint.axis_y != 0.0 or constraint.axis_z != 0.0:
            struct.children.append(Extension(B"PC/axis", children=[
                DdlPrimitive(DataType.float,
                             data=[constraint.axis_x,
                                   constraint.axis_y,
                                   constraint.axis_z])
            ]))

        if constraint.pivot_type in {'HINGE', 'CONE_TWIST', 'GENERIC_6_DOF'} \
                and constraint.use_angular_limit_x:

            struct.children.append(Extension(B"PC/limit_angle_x", children=[
                DdlPrimitive(DataType.float,
                             data=[constraint.limit_angle_min_x,
                                   constraint.limit_angle_max_x])
            ]))

            if constraint.pivot_type in {'CONE_TWIST', 'GENERIC_6_DOF'}:

                if constraint.use_angular_limit_y:
                    struct.children.append(Extension(B"PC/limit_angle_y", children=[
                        DdlPrimitive(DataType.float,
                                     data=[constraint.limit_angle_min_y,
                                           constraint.limit_angle_max_y])
                    ]))
                if constraint.use_angular_limit_z:
                    struct.children.append(Extension(B"PC/limit_angle_z", children=[
                        DdlPrimitive(DataType.float,
                                     data=[constraint.limit_angle_min_z,
                                           constraint.limit_angle_max_z])
                    ]))

        if constraint.pivot_type == 'GENERIC_6_DOF':
            if constraint.use_limit_x:
                struct.children.append(Extension(B"PC/limit_x", children=[
                    DdlPrimitive(DataType.float,
                                 data=[constraint.limit_min_x,
                                       constraint.limit_max_x])
                ]))
            if constraint.use_limit_y:
                struct.children.append(Extension(B"PC/limit_y", children=[
                    DdlPrimitive(DataType.float,
                                 data=[constraint.limit_min_y,
                                       constraint.limit_max_y])
                ]))
            if constraint.use_limit_z:
                struct.children.append(Extension(B"PC/limit_z", children=[
                    DdlPrimitive(DataType.float,
                                 data=[constraint.limit_min_z,
                                       constraint.limit_max_z])
                ]))

        return struct

    def export_audio_properties(self, speaker):
        struct = Extension(B"AudioSource", children=[])

        if speaker.sound is not None:
            import bpy
            (_, path) = os.path.split(bpy.path.abspath(speaker.sound.filepath))
            # prepend path prefix
            path = os.path.relpath(self.audio_path_prefix + path).replace("\\", "/")
            struct.children.append(DdlPrimitive(DataType.string, data=[path]))

        if speaker.volume != 1.0:
            struct.children.append(Extension(B"AS/gain", children=[
                DdlPrimitive(DataType.float, data=[speaker.volume])
            ]))

        if speaker.pitch != 1.0:
            struct.children.append(Extension(B"AS/pitch", children=[
                DdlPrimitive(DataType.float, data=[speaker.pitch])
            ]))

        if speaker.volume_min != 0.0:
            struct.children.append(Extension(B"AS/gain_min", children=[
                DdlPrimitive(DataType.float, data=[speaker.volume_min])
            ]))

        if speaker.volume_max != 1.0:
            struct.children.append(Extension(B"AS/gain_max", children=[
                DdlPrimitive(DataType.float, data=[speaker.volume_max])
            ]))

        if speaker.attenuation != 1.0:
            struct.children.append(Extension(B"AS/rolloff", children=[
                DdlPrimitive(DataType.float, data=[speaker.attenuation])
            ]))

        if speaker.distance_max < 10000000.0:
            struct.children.append(Extension(B"AS/dist_max", children=[
                DdlPrimitive(DataType.float, data=[speaker.distance_max])
            ]))

        if speaker.distance_reference != 1.0:
            struct.children.append(Extension(B"AS/dist_ref", children=[
                DdlPrimitive(DataType.float, data=[speaker.distance_reference])
            ]))

        use_cone = False
        cone_struct = Extension(B"AS/cone", children=[])
        if speaker.cone_angle_outer != 360.0 or speaker.cone_angle_inner != 360.0:
            cone_struct.children.append(DdlPrimitive(
                DataType.float, vector_size=2, data=[(speaker.cone_angle_outer, speaker.cone_angle_inner)]
            ))
            use_cone = True

        if speaker.cone_volume_outer != 1.0:
            cone_struct.children.append(Extension(B"AS/gain_outer", children=[
                DdlPrimitive(DataType.float, data=[speaker.cone_volume_outer])
            ]))
            use_cone = True

        if use_cone:
            struct.children.append(cone_struct)

        return struct

    def export_skin(self, node, armature, export_vertex_array):

        # This function exports all skinning data, which includes the skeleton
        # and per-vertex bone influence data.

        skin_struct = DdlStructure(B"Skin\n", children=[
            Transform(node.matrix_world)
        ])

        skeleton_struct = DdlStructure(B"Skeleton", children=[
            DdlStructure(B"BoneRefArray", children=[
                DdlPrimitive(data_type=DataType.ref, data=[self.find_node(bone.name)[1]["struct"]
                                                           for bone in armature.data.bones])
            ]),
            Transform(matrices=[armature.matrix_world * bone.matrix_local for bone in armature.data.bones])
        ])
        skin_struct.children.append(skeleton_struct)

        # Export the per-vertex bone influence data.

        group_remap = []

        for group in node.vertex_groups:
            group_name = group.name
            for (i, bone) in enumerate(armature.data.bones):
                if bone.name == group_name:
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

        skin_struct.children.append(DdlStructure(B"BoneCountArray", children=[
            DdlPrimitive(data_type=DataType.unsigned_int16, data=bone_count_array)
        ]))
        skin_struct.children.append(DdlStructure(B"BoneIndexArray", children=[
            DdlPrimitive(data_type=DataType.unsigned_int16, data=bone_index_array)
        ]))
        skin_struct.children.append(DdlStructure(B"BoneWeightArray", children=[
            DdlPrimitive(data_type=DataType.float, data=bone_weight_array)
        ]))

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

    def export_geometry(self, scene, node, mesh):
        if mesh in self.container.geometry_array:
            entry = self.container.geometry_array[mesh]
            if node not in entry["nodeTable"]:
                entry["nodeTable"].append(node)
            return entry["struct"]

        self.progress.begin_task("Exporting geometry for " + node.name + "...")

        struct = GeometryObject(name=B"geometry" + bytes(str(len(self.container.geometry_array) + 1), "UTF-8"))
        self.container.geometry_array[mesh] = {
            "struct": struct,
            "nodeTable": [node]}

        # This function exports a single geometry object.]

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
                    props = OrderedDict([(B"index", morph_count)])
                    if relative and (morph_count != base_index):
                        props[B"base"] = base_index

                    struct.add_structure(B"Morph", props=props, children=[
                        Name(block.name)
                    ])

                morph_count += 1

            shape_keys.key_blocks[0].value = 1.0
            mesh.update()

        # Mesh substructure

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

        uv_layers = [mesh.uv_textures.active_index] if mesh.uv_textures.active_index != -1 else None

        export_mesh = self.to_per_vertex_data(m, num_materials=len(mesh.materials), uv_layers=uv_layers)
        vertex_count = len(export_mesh["position"])

        mesh_struct = Mesh(mesh=m, children=[
            # position array
            VertexArray(B"position", vertex_count=vertex_count, data=export_mesh["position"])
        ])
        struct.children.append(mesh_struct)

        # Write the normal array.
        if "normal" in export_mesh:
            mesh_struct.children.append(VertexArray(B"normal", vertex_count=vertex_count, data=export_mesh["normal"]))

        # Write the color array if it exists.
        if "color" in export_mesh:
            mesh_struct.children.append(VertexArray(B"color", vertex_count=vertex_count, data=export_mesh["color"]))

        # Write the texcoord arrays.
        if "texcoord" in export_mesh:
            count = 0
            for texcoords in export_mesh["texcoord"].values():
                name = B'texcoord'
                if count > 0:
                    name += B'[' + self.to_int_byte(count) + B']'

                mesh_struct.children.append(
                    VertexArray(attrib=name, vertex_count=vertex_count, data=texcoords, vector_size=2))

                count += 1
                if count > 2:
                    break

        # If there are multiple morph targets, export them here.
        if shape_keys and False:  # TODO currently no shape key support
            shape_keys.key_blocks[0].value = 0.0
            for i in range(1, len(current_morph_value)):
                shape_keys.key_blocks[i].value = 1.0
                mesh.update()

                node.active_shape_key_index = i
                morph_mesh = node.to_mesh(scene, apply_modifiers, "RENDER", True, False)

                # morph target position array
                mesh_struct.children.append(
                    VertexArray(attrib=B"position", morph=i, data=[morph_mesh.vertices[i].co for i in export_mesh],
                                vertex_count=vertex_count))  # TODO currently no shape key support

                # morph target normal array
                mesh_struct.children.append(
                    VertexArray(attrib=B"normal",
                                morph=i,
                                data=[vert.normal if face.use_smooth else face.normal for (face, vert) in
                                      [(morph_mesh.tessfaces[v.faceIndex], morph_mesh.vertices[v.vertexIndex])
                                       for v in export_mesh]],
                                vertex_count=vertex_count))  # TODO currently no shape key support

                bpy.data.meshes.remove(morph_mesh)

        # Write the index arrays.
        for material_index, indices in enumerate(export_mesh["tris"]):
            num_tris = len(indices)
            if num_tris != 0:
                props = dict()
                if material_index != 0:
                    props[B"material"] = material_index
                mesh_struct.add_structure(B"IndexArray", props=props, children=[
                    DdlTextWriter.set_max_elements_per_line(
                        DdlTextWriter.set_comment(
                            DdlPrimitive(DataType.unsigned_int32, vector_size=3, data=indices), comment=str(num_tris)),
                        elements=16)
                ])

        # If the mesh is skinned, export the skinning data here.
        if armature and False:  # TODO
            self.export_skin(node, armature, export_mesh)

        # Restore the morph state.

        if shape_keys and False:  # TODO
            node.active_shape_key_index = active_shape_key_index
            node.show_only_shape_key = show_only_shape_key

            for i in range(len(current_morph_value)):
                shape_keys.key_blocks[i].value = current_morph_value[i]

            mesh.update()

        self.progress.end_task()

        return struct

    def export_light(self, node, light):
        """
        Export a light as a DdlStructure into self.container.light_array to later add to the DdlDocument.
        :param node: node for which this light is being exported, which will be added to the list of referring nodes
        :param light: light data to export
        :return: the created DdlStructure
        """
        if light not in self.container.light_array:
            struct = LightObject(name=B"light" + bytes(str(len(self.container.light_array) + 1), "UTF-8"), light=light)
            self.container.light_array[light] = {"struct": struct, "nodeTable": [node]}
            return struct
        else:
            entry = self.container.light_array[light]
            if node not in entry["nodeTable"]:
                entry["nodeTable"].append(node)
            return entry["struct"]

    def export_texture(self, texture_slot, layer):
        if texture_slot.texture.type != 'IMAGE':
            return None  # only image textures supported.

        if texture_slot.texture.image is None:
            return None  # cannot export no image.

        img = texture_slot.texture.image
        if img not in self.container.texture_array:
            # get filename from blender path
            import bpy
            (_, path) = os.path.split(bpy.path.abspath(img.filepath))
            # prepend path prefix
            path = os.path.relpath(self.image_path_prefix + path).replace("\\", "/")

            if self.export_image_textures:
                context = bpy.context
                scene = context.scene

                # The written file should have the same name as the blender image
                (prefix, _) = os.path.split(path)
                if len(prefix) > 1:
                    prefix += "/"
                path = bpy.path.ensure_ext(prefix + bpy.path.clean_name(img.name),
                                           scene.render.file_extension, case_sensitive=True)

                # Convert ogex relative path of image to .blend relative path or absolute path
                (ogex_filepath, _) = os.path.split(self.filepath)
                image_path = ogex_filepath + os.sep + path

                img.save_render(image_path, scene=scene)

            struct = Texture(texture_slot, layer, path)
            self.container.texture_array[img] = {"struct": struct, "nodeTable": [img]}

            return struct
        else:
            return self.container.texture_array[img]["struct"]

    def export_material(self, node, material):
        """
        Create a DdlStructure from material data
        :param node: The referring node which will be added to the corresponding nodeTable
        :param material: the material data
        :return: the created DdlStructure
        """
        if material not in self.container.material_array:
            diffuse_texture = None
            specular_texture = None
            emission_texture = None
            transparency_texture = None
            normal_texture = None

            textures = []

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
                textures.append(self.export_texture(diffuse_texture, B"diffuse"))
            if specular_texture:
                textures.append(self.export_texture(specular_texture, B"specular"))
            if emission_texture:
                textures.append(self.export_texture(emission_texture, B"emission"))
            if transparency_texture:
                textures.append(self.export_texture(transparency_texture, B"transparency"))
            if normal_texture:
                textures.append(self.export_texture(normal_texture, B"normal"))

            name = B"material" + bytes(str(len(self.container.material_array) + 1), "UTF-8")
            struct = Material(material, name, self.export_ambient, list(filter(None, textures)))
            self.container.material_array[material] = {"struct": struct, "nodeTable": [node]}

            return struct
        else:
            return self.container.material_array[material]["struct"]

    def export_materials(self, node, material_slots):
        if self.export_only_first_material and len(material_slots) > 0:
            return [self.export_material(node, material_slots[0].material)]
        else:
            return [self.export_material(node, slot.material) for slot in material_slots]

    def export_camera(self, node, camera):
        if camera not in self.container.camera_array:
            struct = CameraObject(B"camera" + bytes(str(len(self.container.camera_array) + 1), "UTF-8"), camera)
            self.container.camera_array[camera] = {"struct": struct, "nodeTable": [node]}
            return struct
        else:
            entry = self.container.camera_array[camera]
            if node not in entry["nodeTable"]:
                entry["nodeTable"].append(node)
            return entry["struct"]

    def export_objects(self):
        self.document.structures.extend([
            DdlTextWriter.set_comment(item["struct"], B", ".join([bytes(n.name, "UTF-8") for n in item["nodeTable"]]))
            for item in itertools.chain(self.container.geometry_array.values(),
                                        self.container.light_array.values(),
                                        self.container.camera_array.values(),
                                        self.container.material_array.values())
            ])

    @staticmethod
    def export_metrics(scene):
        """
        Get a list of Metric DdlStructures.
        :param scene: scene to get the metrics from
        :return: [io_scene_ogex.pygex.Metric]
        """

        scale = scene.unit_settings.scale_length
        if scene.unit_settings.system == "IMPERIAL":
            scale *= 0.3048

        return [
            Metric(B"distance", data_type=DataType.float, value=scale),
            Metric(B"angle", data_type=DataType.float, value=1.0),
            Metric(B"time", data_type=DataType.float, value=1.0),
            Metric(B"up", data_type=DataType.string, value="z"),
        ]

    def get_children_for_node(self, node):

        if node in self.nodeChildren:
            return self.nodeChildren[node]
        else:
            return node.children

    def process_skinned_meshes(self):

        for nw in self.container.nodes.values():
            if nw.nodeRef["nodeType"] == NodeType.geometry:
                armature = nw.item.find_armature()
                if armature:
                    for bone in armature.data.bones:
                        bone_ref = self.container.find_node_wrapper_by_name(bone.name)
                        if bone_ref:
                            # If a node is used as a bone, then we force its type to be a bone.
                            bone_ref.dict["nodeType"] = NodeType.bone

    def resolve_unresolved_refs(self):
        for ref in self.unresolved_refs:
            # FIXME: Name is not unique! Because of linked objects there can be more that one object with the same name
            ref.data = [self.container.find_node_wrapper_by_name(name).nodeRef["struct"] for name in ref.data]

        self.unresolved_refs = []

    def execute(self, context):

        start_time = time.time()

        previous_file_format = context.scene.render.image_settings.file_format
        context.scene.render.image_settings.file_format = self.image_format
        # OpenGEX uses only '/', may not contain \
        # Remove blender // prefix
        path_prefix = self.image_path_prefix.replace("//", "").replace("\\", "/")
        if len(path_prefix) > 1 and not path_prefix.endswith('/'):
            self.image_path_prefix = path_prefix + "/"
        else:
            self.image_path_prefix = path_prefix

        self.document = DdlDocument()
        scene = context.scene

        export_all_flag = not self.export_selection
        self.container = ExporterState(export_all_flag, self.sample_animation, scene)

        self.document.structures.extend(self.export_metrics(scene))

        # export the worlds ambient color, if enabled
        if self.export_ambient:
            self.document.structures.append(Extension(type=B"AmbientColor", children=[
                DdlPrimitive(DataType.float, data=[scene.world.ambient_color], vector_size=3)
            ]))

        original_frame = scene.frame_current
        original_subframe = scene.frame_subframe

        self.progress.begin_task("Preparing objects...")
        for obj in scene.objects:
            if obj.parent is None:
                NodeWrapper(obj, self.container)

        # self.process_skinned_meshes()

        self.progress.end_task()

        for obj in self.container.nodes:
            if not obj.parent:
                self.document.structures.append(self.export_node(obj, scene))

        # progress update is handled within ExportObjects()
        self.export_objects()

        restore_frame = False
        if restore_frame:
            scene.frame_set(original_frame, original_subframe)

        self.resolve_unresolved_refs()

        self.progress.begin_task("Writing file...")
        if self.oddl_format == 'TEXT':
            DdlTextWriter(self.document, rounding=self.rounding).write(self.filepath)
        if self.oddl_format == 'COMPRESSED_TEXT':
            DdlCompressedTextWriter(self.document, rounding=self.rounding).write(self.filepath)
        self.progress.end_task()

        # cleanup
        del self.document
        del self.container

        context.scene.render.image_settings.file_format = previous_file_format

        print('-- Successfully exported to "{}". ({:.2f} sec)'.format(self.filepath, time.time() - start_time))

        return {'FINISHED'}

    def draw(self, context):
        layout = self.layout

        col = layout.column()
        col.label("General")
        col.prop(self, "export_selection")
        col.prop(self, "sample_animation")
        col.prop(self, "export_image_textures")

        if self.export_image_textures:
            col.prop(self, "image_format")
        col.separator()

        col.label("Extensions")
        col.prop(self, "export_custom_properties")
        col.prop(self, "export_physics")
        col.prop(self, "export_ambient")
        col.prop(self, "export_audio")
        if self.export_audio:
            col.prop(self, "audio_path_prefix")
        col.separator()

        col.label("Advanced")
        col.prop(self, "rounding")
        col.prop(self, "export_only_first_material")
        col.prop(self, "image_path_prefix")
        col.prop(self, "oddl_format")
