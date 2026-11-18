# <pep8 compliant>

import bpy  # pylint: disable=import-error
from bpy_extras.image_utils import load_image  # pylint: disable=import-error


def create_image_material(image, matName="Image", shading="SHADELESS"):
    im = load_image(image, check_existing=True, force_reload=True)
    return create_im_material(im, matName, shading)


def create_im_material(image, matName="Image", shading="SHADELESS"):
    material = bpy.data.materials.new(matName)
    material.use_nodes = True
    node_tree = material.node_tree
    output_node = clean_node_tree(node_tree)

    if hasattr(material, "blend_method"):
        material.blend_method = "BLEND"
    if hasattr(material, "shadow_method"):
        material.shadow_method = "HASHED"

    texture_node = node_tree.nodes.new("ShaderNodeTexImage")
    texture_node.image = image
    if image and hasattr(image, "alpha_mode"):
        image.alpha_mode = "PREMUL"
    texture_node.show_texture = True
    texture_node.extension = "EXTEND"

    create_color_alpha_tree(
        node_tree,
        texture_node.outputs[0],
        texture_node.outputs[1],
        output_node.inputs[0],
        shading,
    )

    return material, texture_node


def create_color_material(color, matName="Color", shading="SHADELESS"):
    material = bpy.data.materials.new(matName)
    material.use_nodes = True
    node_tree = material.node_tree
    output_node = clean_node_tree(node_tree)

    if hasattr(material, "diffuse_color"):
        material.diffuse_color = color
    if hasattr(material, "blend_method"):
        material.blend_method = "BLEND"
    if hasattr(material, "shadow_method"):
        material.shadow_method = "HASHED"

    rgb_node = node_tree.nodes.new("ShaderNodeRGB")
    rgb_node.outputs[0].default_value = color

    alpha_node = node_tree.nodes.new("ShaderNodeValue")
    alpha_node.name = "Alpha"
    alpha_node.outputs[0].default_value = color[3]

    create_color_alpha_tree(
        node_tree,
        rgb_node.outputs[0],
        alpha_node.outputs[0],
        output_node.inputs[0],
        shading,
    )

    return material


def _find_input_socket(node, preferred_names, fallback_index=None):
    """Find a node input socket by name, with optional index fallback."""
    name_map = {sock.name.lower(): sock for sock in node.inputs}
    for nm in preferred_names:
        sock = name_map.get(nm.lower())
        if sock is not None:
            return sock
    if fallback_index is not None and fallback_index < len(node.inputs):
        return node.inputs[fallback_index]
    return None


def _setup_principled_emit(node_tree, principled_node, color_output, strength=1.0):
    """
    Wire color_output into Principled Emission Color and set Emission Strength to `strength`.
    Also wire Base Color for previews/consistency.
    NOTE: links.new(from_socket, to_socket)
    """
    # Base Color
    base_sock = _find_input_socket(
        principled_node,
        preferred_names=["Base Color", "Base colour"],
        fallback_index=0,
    )
    if base_sock is not None:
        node_tree.links.new(color_output, base_sock)

    # Blender 4.5 probe:
    # inputs[27] = Emission Color
    # inputs[28] = Emission Strength
    emission_color_sock = None
    if len(principled_node.inputs) > 27:
        emission_color_sock = principled_node.inputs[27]
    else:
        emission_color_sock = _find_input_socket(
            principled_node,
            preferred_names=["Emission Color", "Emission colour", "Emission"],
            fallback_index=None,
        )

    if emission_color_sock is not None:
        node_tree.links.new(color_output, emission_color_sock)
    else:
        print("[MATERIALS] Warning: Principled Emission Color socket not found.")

    emission_strength_sock = None
    if len(principled_node.inputs) > 28:
        emission_strength_sock = principled_node.inputs[28]
    else:
        emission_strength_sock = _find_input_socket(
            principled_node,
            preferred_names=["Emission Strength"],
            fallback_index=None,
        )

    if emission_strength_sock is not None:
        try:
            emission_strength_sock.default_value = float(strength)
        except Exception:
            val = node_tree.nodes.new("ShaderNodeValue")
            val.outputs[0].default_value = float(strength)
            node_tree.links.new(val.outputs[0], emission_strength_sock)
    else:
        print("[MATERIALS] Warning: Principled Emission Strength socket not found.")


def get_input_nodes(node, links):
    input_links = {lnk for lnk in links if lnk.to_node == node}
    sorted_nodes = []
    done_nodes = set()
    for socket in node.inputs:
        done_links = set()
        for link in input_links:
            nd = link.from_node
            if nd in done_nodes:
                done_links.add(link)
            elif link.to_socket == socket:
                sorted_nodes.append(nd)
                done_links.add(link)
                done_nodes.add(nd)
        input_links -= done_links
    return sorted_nodes


def clean_node_tree(node_tree):
    nodes = node_tree.nodes
    for node in list(nodes):
        if node.type != "OUTPUT_MATERIAL":
            nodes.remove(node)
    return node_tree.nodes[0]


def get_shadeless_node(dest_node_tree):
    try:
        node_tree = bpy.data.node_groups["IAP_SHADELESS"]
    except KeyError:
        node_tree = bpy.data.node_groups.new("IAP_SHADELESS", "ShaderNodeTree")
        output_node = node_tree.nodes.new("NodeGroupOutput")
        input_node = node_tree.nodes.new("NodeGroupInput")

        if bpy.app.version < (4, 0, 0):
            node_tree.outputs.new("NodeSocketShader", "Shader")
            node_tree.inputs.new("NodeSocketColor", "Color")
        else:
            node_tree.interface.new_socket(
                name="Shader",
                in_out="OUTPUT",
                socket_type="NodeSocketShader",
            )
            node_tree.interface.new_socket(
                name="Color",
                in_out="INPUT",
                socket_type="NodeSocketColor",
            )

        diffuse_shader = node_tree.nodes.new("ShaderNodeBsdfDiffuse")
        node_tree.links.new(input_node.outputs[0], diffuse_shader.inputs[0])

        emission_shader = node_tree.nodes.new("ShaderNodeEmission")
        node_tree.links.new(input_node.outputs[0], emission_shader.inputs[0])

        light_path = node_tree.nodes.new("ShaderNodeLightPath")
        is_glossy_ray = light_path.outputs["Is Glossy Ray"]
        is_shadow_ray = light_path.outputs["Is Shadow Ray"]
        ray_depth = light_path.outputs["Ray Depth"]
        transmission_depth = light_path.outputs["Transmission Depth"]

        unrefracted_depth = node_tree.nodes.new("ShaderNodeMath")
        unrefracted_depth.operation = "SUBTRACT"
        unrefracted_depth.label = "Bounce Count"
        node_tree.links.new(ray_depth, unrefracted_depth.inputs[0])
        node_tree.links.new(transmission_depth, unrefracted_depth.inputs[1])

        refracted = node_tree.nodes.new("ShaderNodeMath")
        refracted.operation = "SUBTRACT"
        refracted.label = "Camera or Refracted"
        refracted.inputs[0].default_value = 1.0
        node_tree.links.new(unrefracted_depth.outputs[0], refracted.inputs[1])

        reflection_limit = node_tree.nodes.new("ShaderNodeMath")
        reflection_limit.operation = "SUBTRACT"
        reflection_limit.label = "Limit Reflections"
        reflection_limit.inputs[0].default_value = 2.0
        node_tree.links.new(ray_depth, reflection_limit.inputs[1])

        camera_reflected = node_tree.nodes.new("ShaderNodeMath")
        camera_reflected.operation = "MULTIPLY"
        camera_reflected.label = "Camera Ray to Glossy"
        node_tree.links.new(reflection_limit.outputs[0], camera_reflected.inputs[0])
        node_tree.links.new(is_glossy_ray, camera_reflected.inputs[1])

        shadow_or_reflect = node_tree.nodes.new("ShaderNodeMath")
        shadow_or_reflect.operation = "MAXIMUM"
        shadow_or_reflect.label = "Shadow or Reflection?"
        node_tree.links.new(camera_reflected.outputs[0], shadow_or_reflect.inputs[0])
        node_tree.links.new(is_shadow_ray, shadow_or_reflect.inputs[1])

        shadow_or_reflect_or_refract = node_tree.nodes.new("ShaderNodeMath")
        shadow_or_reflect_or_refract.operation = "MAXIMUM"
        shadow_or_reflect_or_refract.label = "Shadow, Reflect or Refract?"
        node_tree.links.new(
            shadow_or_reflect.outputs[0], shadow_or_reflect_or_refract.inputs[0]
        )
        node_tree.links.new(refracted.outputs[0], shadow_or_reflect_or_refract.inputs[1])

        mix_shader = node_tree.nodes.new("ShaderNodeMixShader")
        node_tree.links.new(shadow_or_reflect_or_refract.outputs[0], mix_shader.inputs[0])
        node_tree.links.new(diffuse_shader.outputs[0], mix_shader.inputs[1])
        node_tree.links.new(emission_shader.outputs[0], mix_shader.inputs[2])

        node_tree.links.new(mix_shader.outputs[0], output_node.inputs[0])

        auto_align_nodes(node_tree)

    group_node = dest_node_tree.nodes.new("ShaderNodeGroup")
    group_node.node_tree = node_tree
    return group_node


def auto_align_nodes(node_tree):
    x_gap = 200
    y_gap = 180
    nodes = node_tree.nodes
    links = node_tree.links

    output_node = None
    for node in nodes:
        if node.type in {"OUTPUT_MATERIAL", "GROUP_OUTPUT"}:
            output_node = node
            break
    if output_node is None:
        return

    def align(to_node):
        from_nodes = get_input_nodes(to_node, links)
        for i, nd in enumerate(from_nodes):
            nd.location.x = min(nd.location.x, to_node.location.x - x_gap)
            nd.location.y = to_node.location.y
            nd.location.y -= i * y_gap
            nd.location.y += (len(from_nodes) - 1) * y_gap / max(1, len(from_nodes))
            align(nd)

    align(output_node)


def create_color_alpha_tree(node_tree, color_input, alpha_input, shader_output, shading="SHADELESS"):
    """
    shading modes:
      - 'PRINCIPLED'
      - 'PRINCIPLEDEMIT'  (Principled with emission driven by image color, strength=1)
      - 'SHADELESS'
      - 'EMISSION'
    """
    if shading in {"PRINCIPLED", "PRINCIPLEDEMIT"}:
        shader_node = node_tree.nodes.new("ShaderNodeBsdfPrincipled")
        node_tree.links.new(color_input, shader_node.inputs[0])

        if shading == "PRINCIPLEDEMIT":
            _setup_principled_emit(node_tree, shader_node, color_input, strength=1.0)

    elif shading == "SHADELESS":
        shader_node = get_shadeless_node(node_tree)
        node_tree.links.new(color_input, shader_node.inputs[0])

    else:
        shader_node = node_tree.nodes.new("ShaderNodeEmission")
        node_tree.links.new(color_input, shader_node.inputs[0])
        if len(shader_node.inputs) > 1:
            shader_node.inputs[1].default_value = 1.0

    # Alpha handling
    alpha_node = node_tree.nodes.new("ShaderNodeMath")
    alpha_node.operation = "MULTIPLY"
    alpha_node.inputs[1].default_value = 1.0
    alpha_node.label = "Opacity"
    alpha_node.name = "Opacity"
    node_tree.links.new(alpha_input, alpha_node.inputs[0])

    if shading in {"PRINCIPLED", "PRINCIPLEDEMIT"}:
        alpha_sock = _find_input_socket(shader_node, preferred_names=["Alpha"], fallback_index=18)
        if alpha_sock is not None:
            node_tree.links.new(alpha_node.outputs[0], alpha_sock)
        else:
            print("[MATERIALS] Warning: Principled Alpha socket not found.")
        final_shader = shader_node
    else:
        bsdf_transparent = node_tree.nodes.new("ShaderNodeBsdfTransparent")
        mix_shader = node_tree.nodes.new("ShaderNodeMixShader")
        node_tree.links.new(alpha_node.outputs[0], mix_shader.inputs[0])
        node_tree.links.new(bsdf_transparent.outputs[0], mix_shader.inputs[1])
        node_tree.links.new(shader_node.outputs[0], mix_shader.inputs[2])
        final_shader = mix_shader

    node_tree.links.new(final_shader.outputs[0], shader_output)
    auto_align_nodes(node_tree)


def get_blank_image():
    try:
        im = bpy.data.images["OCA_blank"]
    except KeyError:
        im = bpy.data.images.new("OCA_blank", 256, 256, alpha=True)
        im.generated_color = (0.0, 0.0, 0.0, 0.0)
    return im
