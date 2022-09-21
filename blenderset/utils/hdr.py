import bpy


def hdr_swap(name, hdr):
    """
    Try to replace the hdr in current world setup. If this fails, create a new world.
    :param name: Name of the resulting world (renamse the current one if swap is successfull)
    :param hdr: Image type
    :return: None
    """
    w = bpy.context.scene.world
    if w:
        w.use_nodes = True
        w.name = name
        nt = w.node_tree
        for n in nt.nodes:
            if "ShaderNodeTexEnvironment" == n.bl_rna.identifier:
                env_node = n
                env_node.image = hdr
                return
    new_hdr_world(name, hdr)


def new_hdr_world(name, hdr):
    """
    creates a new world, links in the hdr with mapping node, and links the world to scene
    :param name: Name of the world datablock
    :param hdr: Image type
    :return: None
    """
    w = bpy.data.worlds.new(name=name)
    w.use_nodes = True
    bpy.context.scene.world = w

    nt = w.node_tree
    env_node = nt.nodes.new(type="ShaderNodeTexEnvironment")
    env_node.image = hdr
    background = get_node_sure(nt, "ShaderNodeBackground")
    tex_coord = get_node_sure(nt, "ShaderNodeTexCoord")
    mapping = get_node_sure(nt, "ShaderNodeMapping")

    nt.links.new(env_node.outputs["Color"], background.inputs["Color"])
    nt.links.new(tex_coord.outputs["Generated"], mapping.inputs["Vector"])
    nt.links.new(mapping.outputs["Vector"], env_node.inputs["Vector"])
    env_node.location.x = -400
    mapping.location.x = -600
    tex_coord.location.x = -800


def get_node_sure(node_tree, ntype=""):
    """
    Gets a node of certain type, but creates a new one if not pre
    """
    node = None
    for n in node_tree.nodes:
        if ntype == n.bl_rna.identifier:
            node = n
            return node
    if not node:
        node = node_tree.nodes.new(type=ntype)

    return node


def load_HDR(file_name, name):
    """Load a HDR into file and link it to scene world."""
    already_linked = False
    for i in bpy.data.images:
        if i.filepath == file_name:
            hdr = i
            already_linked = True
            break

    if not already_linked:
        hdr = bpy.data.images.load(file_name)

    hdr_swap(name, hdr)
    return hdr
