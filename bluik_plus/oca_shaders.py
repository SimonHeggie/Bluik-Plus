# SPDX-License-Identifier: GPL-3.0-or-later
"""Camera-aligned OCA paint blending with explicit backdrop shader sampling.

A material cannot infer the colour of arbitrary geometry behind it. For imported
2D image planes, shared node groups evaluate the actual lower artwork, including
its image animation and object transforms. Then the visible plane uses the
alpha-correct paint blend instead of silently substituting an additive shader.
"""
import bpy

MODES={'normal':'MIX','multiply':'MULTIPLY','screen':'SCREEN','add':'ADD',
       'overlay':'OVERLAY','darken':'DARKEN','lighten':'LIGHTEN',
       'difference':'DIFFERENCE','exclusion':'EXCLUSION','hard_light':'OVERLAY'}


def node(tree,kind,name=None):
    n=tree.nodes.new(kind)
    if name:n.name=n.label=name
    return n


def link(tree,value,socket):
    if isinstance(value,(float,int,tuple,list)):socket.default_value=value
    else:tree.links.new(value,socket)


def math(tree,op,a,b):
    n=node(tree,'ShaderNodeMath');n.operation=op
    link(tree,a,n.inputs[0]);link(tree,b,n.inputs[1]);return n.outputs[0]


def scale(tree,color,factor):
    n=node(tree,'ShaderNodeVectorMath');n.operation='SCALE'
    link(tree,color,n.inputs[0]);link(tree,factor,n.inputs['Scale']);return n.outputs[0]


def add(tree,a,b):
    n=node(tree,'ShaderNodeVectorMath');n.operation='ADD'
    link(tree,a,n.inputs[0]);link(tree,b,n.inputs[1]);return n.outputs[0]


def mix(tree,fac,a,b,mode='MIX',label=None):
    n=node(tree,'ShaderNodeMixRGB',label);n.blend_type=mode;n.use_clamp=False
    link(tree,fac,n.inputs[0]);link(tree,a,n.inputs[1]);link(tree,b,n.inputs[2]);return n.outputs[0]


def group(name):
    g=bpy.data.node_groups.new(name,'ShaderNodeTree')
    for name,kind in [('Color','NodeSocketColor'),('Alpha','NodeSocketFloat')]:
        g.interface.new_socket(name=name,in_out='OUTPUT',socket_type=kind)
    return g,node(g,'NodeGroupOutput')


def instance(tree,g,name):
    n=node(tree,'ShaderNodeGroup',name);n.node_tree=g;return n


def paint(tree,back,front,mode):
    if mode=='normal':return front
    # Hard light swaps the arguments of Overlay.
    a,b=(front,back) if mode=='hard_light' else (back,front)
    return mix(tree,1.,a,b,MODES[mode],'OCA Paint: '+mode)


def sample(obj):
    mat=obj.active_material;original=mat.node_tree
    texture=next(n for n in original.nodes if n.type=='TEX_IMAGE')
    g,out=group('OCA Artwork: '+obj.name)
    tex=node(g,'ShaderNodeTexImage','Artwork Image')
    tex.image=texture.image;tex.extension='CLIP';tex.interpolation=texture.interpolation
    for entry in texture.duik_texanim_images:
        copy=tex.duik_texanim_images.add();copy.image=entry.image;copy.name=entry.name
    opacity=node(g,'ShaderNodeValue','Artwork Opacity')
    opacity.outputs[0].default_value=original.nodes['Opacity'].inputs[1].default_value
    tex.duik_texanim_current_index=texture.duik_texanim_current_index
    # Transfer the two native animation controls to the shared sampler. Both
    # the plane material and every backdrop reference this ONE animated group.
    # Cross-ID drivers targeting embedded node RNA create invalid depsgraph
    # relations in Blender 5.3, so do not use them for TexAnim synchronization.
    from bpy_extras.anim_utils import animdata_get_channelbag_for_assigned_slot
    ad=original.animation_data
    bag=animdata_get_channelbag_for_assigned_slot(ad) if ad else None
    paths={texture.path_from_id('duik_texanim_current_index'):(tex,'duik_texanim_current_index'),
           original.nodes['Opacity'].inputs[1].path_from_id('default_value'):(opacity.outputs[0],'default_value')}
    if bag:
        for curve in bag.fcurves:
            if curve.data_path not in paths:continue
            target,prop=paths[curve.data_path]
            for key in curve.keyframe_points:
                setattr(target,prop,int(key.co[1]) if prop=='duik_texanim_current_index' else key.co[1])
                target.keyframe_insert(data_path=prop,frame=key.co[0])
        from .oca13_import import stepped
        stepped(g)
    texcoord=node(g,'ShaderNodeTexCoord','Artwork Object Coordinates');texcoord.object=obj
    uv=node(g,'ShaderNodeVectorMath');uv.operation='MULTIPLY_ADD'
    w,h=obj.duik_layer.width,obj.duik_layer.height
    uv.inputs[1].default_value=(100/w,100/h,0);uv.inputs[2].default_value=(.5,.5,0)
    g.links.new(texcoord.outputs['Object'],uv.inputs[0]);g.links.new(uv.outputs[0],tex.inputs['Vector'])
    visible=node(g,'ShaderNodeValue','Render Visibility')
    curve=visible.outputs[0].driver_add('default_value');driver=curve.driver
    variable=driver.variables.new();variable.name='hidden';variable.targets[0].id=obj;variable.targets[0].data_path='hide_render'
    driver.expression='1-hidden'
    alpha=math(g,'MULTIPLY',math(g,'MULTIPLY',tex.outputs['Alpha'],opacity.outputs[0]),visible.outputs[0])
    g.links.new(tex.outputs['Color'],out.inputs['Color']);g.links.new(alpha,out.inputs['Alpha'])
    return g


def prefix(previous,artwork,mode,name):
    g,out=group('OCA Stack: '+name)
    back=instance(g,previous,'Lower Artwork');front=instance(g,artwork,'This Artwork')
    ba,fa=back.outputs['Alpha'],front.outputs['Alpha']
    effective=mix(g,ba,front.outputs['Color'],paint(g,back.outputs['Color'],front.outputs['Color'],mode))
    remaining=math(g,'MULTIPLY',ba,math(g,'SUBTRACT',1.,fa))
    alpha=math(g,'ADD',fa,remaining)
    numerator=add(g,scale(g,effective,fa),scale(g,back.outputs['Color'],remaining))
    color=scale(g,numerator,math(g,'DIVIDE',1.,alpha))
    g.links.new(color,out.inputs['Color']);g.links.new(alpha,out.inputs['Alpha'])
    return g


def configure(importer):
    modes={};chains={}
    def visit(coll,ancestors=()):
        chain=ancestors+(coll,) if coll.get('oca_layer_type')=='grouplayer' else ancestors
        for obj in coll.objects:chains[obj]=chain
        for child in coll.children:visit(child,chain)
    visit(importer.root)
    for obj in importer.created_objects:
        if not obj.get('oca_layer_id'):continue
        mode=obj.get('oca_blending_mode','normal')
        for coll in reversed(chains.get(obj,())):
            if not coll.get('oca_pass_through',False):
                children=[o for o in coll.all_objects if o.get('oca_layer_id')]
                if len(children)==1:mode=coll.get('oca_blending_mode','normal')
                elif coll.get('oca_blending_mode','normal')!='normal':
                    importer.warn(coll.name+': isolated multi-layer blend is not yet reproduced by individual 3D materials')
        modes[obj]=mode
    if not any(mode!='normal' for mode in modes.values()):return
    previous,out=group('OCA Stack: Background')
    color=importer.root_document.get('backgroundColor',[0,0,0,0])
    out.inputs['Color'].default_value=color;out.inputs['Alpha'].default_value=color[3]
    missing=False
    # Imported plane depth fixes the current bottom-to-top order. This does not
    # claim to capture arbitrary 3D depth/order animation.
    for obj in sorted(modes,key=lambda o:o.location.y,reverse=True):
        mode=modes[obj]
        if obj.type!='MESH' or not obj.active_material:
            if not obj.hide_render:missing=True
            continue
        if mode not in MODES:
            importer.warn(obj.name+': unsupported shader blend '+mode+'; normal material retained')
            mode='normal'
        if missing and mode!='normal':
            importer.warn(obj.name+': lower native GP artwork cannot be sampled by a plane shader; blend is partial')
        artwork=sample(obj)
        mat=obj.active_material;nt=mat.node_tree
        texture=next(n for n in nt.nodes if n.type=='TEX_IMAGE')
        old_alpha=nt.nodes['Opacity']
        source=instance(nt,artwork,'OCA Artwork');source.location=(-650,0)
        emission=next(n for n in nt.nodes if n.type=='EMISSION')
        for edge in list(old_alpha.outputs[0].links):nt.links.new(source.outputs['Alpha'],edge.to_socket)
        effective=source.outputs['Color']
        if mode!='normal':
            back=instance(nt,previous,'OCA Backdrop');back.location=(-700,350)
            blended=paint(nt,back.outputs['Color'],effective,mode)
            effective=mix(nt,back.outputs['Alpha'],effective,blended,label='OCA Alpha-Correct Blend')
            mat['oca_effective_blending_mode']=mode;obj['oca_effective_blending_mode']=mode
        nt.links.new(effective,emission.inputs['Color'])
        # The shared group is the editable image/opacity control, not a second
        # unsynchronised copy of the visible material's animation.
        nt.animation_data_clear();nt.nodes.remove(texture);nt.nodes.remove(old_alpha)
        previous=prefix(previous,artwork,mode,obj.name)
    importer.scene.frame_set(importer.scene.frame_current)
