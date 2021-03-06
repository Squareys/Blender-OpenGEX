import os
from collections import OrderedDict
import itertools
from io_scene_ogex.pyddl import DdlPrimitiveDataType as DataType
from io_scene_ogex.pyddl import *

"""
DdlStructure subclasses for structures of OpenGEX for easier use.
"""


class Name(DdlStructure):
    def __init__(self, name):
        super().__init__(B"Name", children=[
            DdlPrimitive(data_type=DataType.string, data=[name])
        ])


class Color(DdlStructure):
    def __init__(self, attrib, value):
        super().__init__(B"Color", props={B"attrib": attrib}, children=[
            DdlPrimitive(data_type=DataType.float, data=[value], vector_size=3)
        ])


class Param(DdlStructure):
    def __init__(self, attrib, value):
        super().__init__(B"Param", props={B"attrib": attrib}, children=[
            DdlPrimitive(data_type=DataType.float, data=[value])
        ])


class Track(DdlStructure):
    def __init__(self, children=[], target=None):
        props = dict() if target is None else {B"target": target}
        super().__init__(B"Track", props=props, children=[])
        self.children.extend(children)


class Time(DdlStructure):
    def __init__(self, curve=B"linear", children=[]):
        props = dict() if curve == B"linear" else {B"curve": curve}

        super().__init__(B"Time", props=props, children=children)


class Key(DdlStructure):
    def __init__(self, kind=None, data=[], vector_size=0):
        props = dict() if kind is None else {B"kind": kind}

        primitive = DdlPrimitive(data_type=DataType.float, data=data, vector_size=vector_size)
        if vector_size == 16:
            # special case for matrices which should be displayed one per line
            DdlTextWriter.set_max_elements_per_line(primitive, 1)

        super().__init__(B"Key", props=props, children=[primitive])


class Value(DdlStructure):
    def __init__(self, curve=B"linear", children=[]):
        props = dict() if curve == B"linear" else {B"curve": curve}

        super().__init__(B"Value", props=props, children=children)


class Metric(DdlStructure):
    def __init__(self, key, data_type, value):
        super().__init__(B"Metric", props={B"key": key}, children=[
            DdlPrimitive(data_type, data=[value])
        ])


class Translation(DdlStructure):
    def __init__(self, value, kind=None, name=None, vector_size=0):
        props = dict if kind is None else {B"kind": kind}
        super().__init__(B"Translation", name=name, props=props, children=[
            DdlPrimitive(DataType.float, data=[value], vector_size=vector_size)
        ])
        self.name_is_global = False


class Rotation(DdlStructure):
    def __init__(self, value, kind=None, name=None, vector_size=0):
        props = dict if kind is None else {B"kind": kind}
        super().__init__(B"Rotation", name=name, props=props, children=[
            DdlPrimitive(DataType.float, data=[value], vector_size=vector_size)
        ])
        self.name_is_global = False


class Scale(DdlStructure):
    def __init__(self, value, kind=None, name=None, vector_size=0):
        props = dict if kind is None else {B"kind": kind}
        super().__init__(B"Scale", name=name, props=props, children=[
            DdlPrimitive(DataType.float, data=[value], vector_size=vector_size)
        ])
        self.name_is_global = False


class Transform(DdlStructure):
    def __init__(self, matrix=None, matrices=None):
        if matrices is None:
            matrices = [] if matrix is None else [matrix]
        super().__init__(B"Transform", children=[
            DdlTextWriter.set_max_elements_per_line(
                DdlPrimitive(DataType.float, data=[tuple(itertools.chain(*zip(*matrix))) for matrix in matrices],
                             vector_size=16),
                elements=4
            )
        ])


class Extension(DdlStructure):
    def __init__(self, type, applic=B"Blender", children=[]):
        super().__init__(B"Extension",
                         props=OrderedDict([(B"applic", applic), (B"type", type)]), children=children)


class ObjectRef(DdlStructure):
    def __init__(self, ref_object):
        if not isinstance(ref_object, DdlStructure):
            raise TypeError("Cannot create a ObjectRef for a non DdlStructure object.")

        super().__init__(B"ObjectRef", children=[
            DdlPrimitive(DataType.ref, data=[ref_object])
        ])


class MaterialRef(DdlStructure):
    def __init__(self, ref_material, index):
        super().__init__(B"MaterialRef", props={B"index": index}, children=[
            DdlPrimitive(DataType.ref, data=[ref_material])
        ])


class Mesh(DdlStructure):
    def __init__(self, mesh=None, primitive=B"triangles", children=[]):
        super().__init__(B"Mesh", props={B"primitive": primitive}, children=children)

        # a reference to a blender mesh to keep it in memory for referring VertexArrays
        self.mesh = mesh


class Texture(DdlStructure):
    def __init__(self, texture_slot, attrib, path):
        super().__init__(B"Texture", props={B"attrib": attrib}, children=[
            DdlPrimitive(DataType.string, data=[path])
        ])
        # If the texture has a scale and/or offset, then export a coordinate transform.

        uscale = texture_slot.scale[0]
        vscale = texture_slot.scale[1]
        uoffset = texture_slot.offset[0]
        voffset = texture_slot.offset[1]

        if (uscale != 1.0) or (vscale != 1.0) or (uoffset != 0.0) or (voffset != 0.0):
            matrix = [[uscale, 0.0, 0.0, 0.0],
                      [0.0, vscale, 0.0, 0.0],
                      [0.0, 0.0, 1.0, 0.0],
                      [uoffset, voffset, 0.0, 1.0]]

            self.children.append(Transform(matrix))


class Material(DdlStructure):
    def __init__(self, material, name, export_ambient=False, textures=[]):
        if material is None:
            raise ValueError("material cannot be None")

        super().__init__(B"Material", name=name, children=[])

        if material.name != "":
            self.children.append(Name(material.name))

        intensity = material.diffuse_intensity
        diffuse = [material.diffuse_color[0] * intensity, material.diffuse_color[1] * intensity,
                   material.diffuse_color[2] * intensity]

        self.children.append(Color("diffuse", diffuse))

        intensity = material.specular_intensity
        specular = [material.specular_color[0] * intensity, material.specular_color[1] * intensity,
                    material.specular_color[2] * intensity]

        if (specular[0] > 0.0) or (specular[1] > 0.0) or (specular[2] > 0.0):
            self.children.append(Color("specular", specular))
            self.children.append(Param("specular_power", material.specular_hardness))

        emission = material.emit
        if emission > 0.0:
            self.children.append(Color("emission", [emission, emission, emission]))

        # export ambient factor if enabled.
        if export_ambient and material.ambient != 1.0:
            self.children.append(Param("ambient_factor", material.ambient))

        # export shadeless flag
        if material.use_shadeless:
            self.children.append(Extension(type=B"Shadeless", children=[
                DdlPrimitive(DataType.bool, data=[True])
            ]))

        # export shadow receive flag
        if material.use_shadows:
            self.children.append(Extension(type=B"Shadow/receive", children=[
                DdlPrimitive(DataType.bool, data=[True])
            ]))

        # export shadow cast flag
        if material.use_cast_shadows:
            self.children.append(Extension(type=B"Shadow/cast", children=[
                DdlPrimitive(DataType.bool, data=[True])
            ]))
        self.children.extend(textures)


class LightObject(DdlStructure):
    def __init__(self, name, light):
        is_point = False
        is_spot = False

        super().__init__(B"LightObject", name=name, props=OrderedDict(), children=[])

        if light.type == "SUN":
            self.properties[B"type"] = B"infinite"
        elif light.type == "POINT":
            self.properties[B"type"] = B"point"
            is_point = True
        else:
            self.properties[B"type"] = B"spot"
            is_point = True
            is_spot = True

        if not light.use_shadow:
            self.properties[B"shadow"] = False

        # export the light's color, and include a separate intensity if necessary.
        self.children.append(Color(B"light", light.color))
        if light.energy != 1.0:
            self.children.append(Param(B"intensity", light.energy))

        if is_point:
            # export a separate attenuation function for each type that's in use.
            falloff = light.falloff_type

            if falloff == "INVERSE_LINEAR":
                self.add_structure(B"Atten", props={B"curve": B"inverse"}, children=[
                    Param(B"scale", light.distance)
                ])

            elif falloff == "INVERSE_SQUARE":
                self.add_structure(B"Atten", props={B"curve": B"inverse_square"}, children=[
                    Param(B"scale", light.distance)
                ])

            elif falloff == "LINEAR_QUADRATIC_WEIGHTED":
                if light.linear_attenuation != 0.0:
                    self.add_structure(B"Atten", props={B"curve": B"inverse"}, children=[
                        Param(B"scale", light.distance),
                        Param(B"constant", 1.0),
                        Param(B"linear", light.linear_attenuation)
                    ])

                if light.quadratic_attenuation != 0.0:
                    self.add_structure(B"Atten", props={B"curve": B"inverse_square"}, children=[
                        Param(B"scale", light.distance),
                        Param(B"constant", 1.0),
                        Param(B"quadratic", light.quadratic_attenuation)
                    ])

            if light.use_sphere:
                self.add_structure(B"Atten", props={B"curve": B"linear"}, children=[
                    Param(B"end", light.distance)
                ])

            if is_spot:
                # Export additional angular attenuation for spot lights.
                end_angle = light.spot_size * 0.5
                begin_angle = end_angle * (1.0 - light.spot_blend)

                self.add_structure(B"Atten", props=OrderedDict([(B"kind", B"angle"), (B"curve", B"linear")]), children=[
                    Param(B"begin", begin_angle),
                    Param(B"end", end_angle)
                ])


class CameraObject(DdlStructure):
    def __init__(self, name, camera):
        super().__init__(B"CameraObject", name=name, children=[
            Param(B"fov", camera.angle_x),
            Param(B"near", camera.clip_start),
            Param(B"far", camera.clip_end)
        ])


class Node(DdlStructure):
    def __init__(self, identifier, obj, name, props=dict(), children=[], use_custom_properties=False):
        super().__init__(identifier, name=name, props=props, children=[])

        if obj.name != "":
            self.children.append(Name(obj.name))

        # Export custom properties
        if len(obj.items()) != 0 and use_custom_properties:
            self.children.extend(self.export_properties(obj))

        self.children.extend(children)

    @staticmethod
    def export_properties(node):
        properties = []

        for (name, value) in node.items():
            if name == "_RNA_UI":
                continue  # for blender only

            if isinstance(value, int):
                type_name = DataType.int32
            elif isinstance(value, float):
                type_name = DataType.float
            elif isinstance(value, str):
                type_name = DataType.string
            else:
                print("\nWARNING: Unknown custom property type for property \"{}\"".format(name))
                continue

            properties.append(Extension(type=B"Property", children=[
                # key
                DdlPrimitive(data_type=DataType.string, data=[B"\"" + bytes(name, "UTF-8") + B"\""]),
                # value
                DdlPrimitive(data_type=type_name, data=[value])
            ]))

        return properties


class VertexArray(DdlStructure):
    def __init__(self, attrib, data, vertex_count, vector_size=3, morph=None):
        props = OrderedDict([(B"attrib", attrib)])
        if morph is not None:
            props[B"morph"] = morph

        super().__init__(B"VertexArray", props=props, children=[
            DdlTextWriter.set_max_elements_per_line(
                DdlTextWriter.set_comment(DdlPrimitive(DataType.float, data=data, vector_size=vector_size),
                                          comment=str(vertex_count)),
                elements=8)
        ])


class GeometryObject(DdlStructure):
    def __init__(self, name):
        super().__init__(B"GeometryObject", name=name, children=[])


class GeometryNode(Node):
    def __init__(self, mesh, name, geometry, materials, use_custom_properties=False):
        props = {B"visible": False} if mesh.hide_render else dict()
        super().__init__(B"GeometryNode", mesh, name, props=props, children=[],
                         use_custom_properties=use_custom_properties)

        self.children.append(ObjectRef(geometry))

        for (i, material) in enumerate(materials):
            self.children.append(MaterialRef(material, index=i))
