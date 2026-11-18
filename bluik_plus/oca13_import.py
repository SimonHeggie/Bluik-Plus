# SPDX-License-Identifier: GPL-3.0-or-later
"""OCA 1.3 import plus explicit Bluik rotation/scale extensions; legacy stays separate.

Development integration, intentionally not imported by HandOff's runtime.
Uses Bluik's scene/plane/material creation and Blender's native GP SVG importer.
"""
from __future__ import annotations
import copy,json,math,shutil,subprocess,tempfile,hashlib,struct
from pathlib import Path
from xml.etree import ElementTree as ET
import bpy
import numpy as np
from bpy_extras.anim_utils import animdata_get_channelbag_for_assigned_slot
from . import layers,dublf

PROTOTYPE_FIELDS={'pivot','pivotPosition','rotation','scale','shear','animation'}

def display_name(layer):
    # OCA has one global name namespace; Blender has separate namespaces for
    # Collections and Objects. Restore authored names without changing OCA IDs.
    return layer.get('meta',{}).get('handoff',{}).get('originalName') or layer['name']


def walk(items):
    for n in items:
        yield n
        yield from walk(n.get('childLayers',[]))


def _transform_fields(document):
    for layer in walk(document.get('layers',[])):
        yield PROTOTYPE_FIELDS.intersection(layer)
        for frame in layer.get('frames',[]):yield PROTOTYPE_FIELDS.intersection(frame)


def is_standard(document):
    return document.get('ocaVersion')=='1.3.0' and not any(_transform_fields(document))


def is_importable(document):
    # Rotation/scale are explicit Bluik extensions. Keep the repaired 1.3 ID,
    # shader, SVG and visibility pipeline rather than falling into legacy code.
    return document.get('ocaVersion')=='1.3.0' and all(not (keys-{'rotation','scale'}) for keys in _transform_fields(document))


def document_path(path):
    path=Path(path).resolve()
    if path.is_dir():
        files=list(path.glob('*.oca'))
        if len(files)!=1:raise ValueError(f'{path}: expected one root OCA document')
        path=files[0]
    if not path.is_file():raise FileNotFoundError(path)
    return path


def stepped(idblock):
    ad=idblock.animation_data
    if not ad:return
    bag=animdata_get_channelbag_for_assigned_slot(ad)
    if bag:
        for curve in bag.fcurves:
            for k in curve.keyframe_points:k.interpolation='CONSTANT'


def copy_drawing(source,target,material_offset):
    target.add_strokes([len(s.points) for s in source.strokes])
    fields={'FLOAT':('value',1,np.float32),'INT':('value',1,np.int32),'INT8':('value',1,np.int32),
            'BOOLEAN':('value',1,bool),'FLOAT_VECTOR':('vector',3,np.float32),'FLOAT_COLOR':('color',4,np.float32)}
    for attr in source.attributes:
        if attr.data_type not in fields:raise ValueError('Unsupported GP attribute '+attr.name+': '+attr.data_type)
        field,count,dtype=fields[attr.data_type]
        dst=target.attributes.get(attr.name)
        if dst is None:dst=target.attributes.new(attr.name,attr.data_type,attr.domain)
        values=np.empty(len(attr.data)*count,dtype=dtype);attr.data.foreach_get(field,values)
        if attr.name=='material_index':values+=material_offset
        dst.data.foreach_set(field,values)


class Importer:
    def __init__(self,context,operator,path):
        self.context=context;self.operator=operator;self.path=document_path(path)
        self.scene=context.scene;self.warnings=[];self.pending=[];self.depth=0;self.loaded={};self.documents=[]
        self.root_document=self.load(self.path)
        self.width=self.root_document['width'];self.height=self.root_document['height']
        self.start=self.root_document.get('startTime',0);self.end=self.root_document['endTime']
        self.created_objects=[];self.created_collections=[];self.source_files=[]
        self.svg_previews=None;self.svg_preview_paths=set()

    def warn(self,message):
        if message not in self.warnings:self.warnings.append(message);print('[BLUIK OCA 1.3]',message,flush=True)

    def load(self,path,chain=()):
        path=document_path(path)
        if path in chain:raise ValueError('Nested OCA cycle: '+str(path))
        if path in self.loaded:return self.loaded[path]
        data=json.loads(path.read_text(encoding='utf-8'))
        if not is_importable(data):raise ValueError('Nested document uses unsupported OCA transform extensions: '+str(path))
        for key in ('width','height'):
            if not isinstance(data.get(key),int) or data[key]<=0:raise ValueError(f'{path}: invalid {key}')
        byid={};names=set()
        for layer in walk(data['layers']):
            identity=layer.get('id');name=layer.get('name')
            if not identity or identity in byid:raise ValueError(f'{path}: missing/duplicate layer ID: {identity}')
            if not name or name in names:raise ValueError(f'{path}: missing/duplicate name: {name}')
            names.add(name);byid[identity]=layer
        def acyclic(identity,chain):
            if identity in chain:raise ValueError('Cyclic OCA source.id: '+identity)
            node=byid[identity];edges=[n['id'] for n in node.get('childLayers',[])]
            if node['type']=='clonelayer':edges.append(node.get('source',{}).get('id'))
            for target in edges:
                if target not in byid:raise ValueError(node['name']+': missing OCA source.id')
                acyclic(target,chain|{identity})
        for identity in byid:acyclic(identity,set())
        # Do not cache until recursion has been checked.
        for layer in byid.values():
            kind=layer['type']
            from .oca_transforms import rotation,scale
            for item in [layer,*layer.get('frames',[])]:
                if 'rotation' in item:rotation(item['rotation'])
                if 'scale' in item:scale(item['scale'])
            if kind=='grouplayer' and (rotation(layer.get('rotation'))!=(0.,0.,0.) or scale(layer.get('scale'))!=(1.,1.,1.)):
                raise ValueError(layer['name']+': group rotation/scale extensions are not implemented')
            if kind=='clonelayer' and layer.get('source',{}).get('id') not in byid:raise ValueError(layer['name']+': missing clone source.id')
            if kind=='ocalayer':self.load(self.nested_path(layer,path),(*chain,path))
            elif kind not in ('paintlayer','vectorlayer','grouplayer','clonelayer'):raise ValueError('Unsupported OCA layer type: '+kind)
            for frame in layer.get('frames',[]):
                if frame.get('name')=='_blank':continue
                asset=path.parent/frame['fileName']
                if not asset.is_file():raise FileNotFoundError(f'{layer["name"]}: {asset}')
        self.loaded[path]=data
        return data

    def nested_path(self,layer,path):
        source=layer['source'];relative=source.get('relFileName','');absolute=source.get('absFileName','')
        candidate=path.parent/relative if relative else Path('/__missing_oca_reference__')
        if not candidate.exists():candidate=Path(absolute) if absolute else candidate
        return document_path(candidate)

    def collection(self,name,parent,layer=None):
        # Bluik's legacy helper strips dotted names; preserve the authored name here.
        name=display_name(layer) if layer else name
        result=layers.create_group(self.context,name,parent);result.name=name
        self.created_collections.append(result)
        if layer:self.metadata(result,layer)
        return result

    def metadata(self,obj,layer):
        obj['oca_layer_id']=layer['id'];obj['oca_layer_type']=layer['type'];obj['oca_label']=int(layer.get('label',-1))
        obj['oca_opacity']=float(layer.get('opacity',1));obj['oca_blending_mode']=layer.get('blendingMode','normal')
        obj['oca_inherit_alpha']=bool(layer.get('inheritAlpha',False));obj['oca_reference']=bool(layer.get('reference',False))
        obj['oca_pass_through']=bool(layer.get('passThrough',False))
        obj['oca_original_metadata']=json.dumps(layer.get('meta',{}),ensure_ascii=False)
        # Retain numeric labels even when a receiving application's palette differs.
        if isinstance(obj,bpy.types.Collection):
            tag={1:'COLOR_01',2:'COLOR_02',3:'COLOR_03',4:'COLOR_04',5:'COLOR_05',6:'COLOR_06',7:'COLOR_07',8:'COLOR_08'}.get(layer.get('label'),'NONE')
            obj.color_tag=tag
        if layer.get('inheritAlpha'):self.warn(layer['name']+': Inherit Alpha is retained as metadata; 3D plane clipping is not implemented')


    def run(self):
        self.root=layers.create_scene(self.context,self.root_document['name'],self.width,self.height,[0,0,0,0],'2D','EMISSION')
        self.created_collections.append(self.root)
        self.root['oca_document_path']=str(self.path);self.root['oca_metadata_path']=str(self.path.with_name(self.path.stem+'_meta.json'))
        self.scene.camera=self.root.duik_scene.camera
        self.scene.camera.data.ortho_scale=max(self.width,self.height)/100
        self.scene.render.resolution_x=self.width;self.scene.render.resolution_y=self.height
        self.scene.render.resolution_percentage=100;self.scene.render.pixel_aspect_x=self.scene.render.pixel_aspect_y=1
        self.scene.render.film_transparent=True
        fps=float(self.root_document.get('frameRate',24))
        if getattr(self.operator,'update_fps',True):
            self.scene.render.fps=max(1,round(fps));self.scene.render.fps_base=self.scene.render.fps/fps
        if getattr(self.operator,'update_timeline',True):
            self.scene.frame_start=max(0,self.start);self.scene.frame_end=max(0,self.end-1)
        if self.start<0:self.warn('Negative OCA frame numbers are retained; Blender timeline-range RNA clamps its start to zero')
        self.root['oca_start_time']=self.start;self.root['oca_end_time']=self.end
        self.build_document(self.path,self.root,(0,0),0,True,1,(self.start,self.end))
        remaining=list(self.pending)
        while remaining:
            next_pass=[]
            for item in remaining:
                layer,parent,origin,offset,shown,opacity,clip,state=item
                source=state['built'].get(layer['source']['id'])
                if source is None:next_pass.append(item);continue
                self.build_clone(item,source)
            if len(next_pass)==len(remaining):raise ValueError('Unresolved/cyclic OCA clone source IDs: '+', '.join(x[0]['name'] for x in next_pass))
            remaining=next_pass
        color=self.root_document.get('backgroundColor',[0,0,0,0])
        if color[3]>0:
            bg=layers.create_layer(self.context,'OCA Background',self.width,self.height,self.root)
            bg.location.y=.1;bg.data.materials.append(dublf.materials.create_color_material(color,'OCA Background','EMISSION'))
        if not is_standard(self.root_document):
            self.warn('Rotation/scale imported as Bluik extensions; these are not official OCA 1.3 transform fields')
        self.scene.frame_set(self.start)
        from .oca_shaders import configure
        configure(self)
        self.root['oca_import_warnings']=json.dumps(self.warnings)
        self.operator._oca13_result=dict(root=self.root.name,objects=[o.name for o in self.created_objects],warnings=self.warnings)
        self.operator._blend_queue=[]
        return self.root

    def build_document(self,path,parent,origin,offset,shown,opacity,clip):
        data=self.load(path);state=dict(path=path,data=data,built={},layers={n['id']:n for n in walk(data['layers'])})
        self.documents.append(state)
        for layer in data['layers']:self.build(layer,parent,origin,offset,shown,opacity,clip,state)
        return state

    def size(self,layer,state):
        return int(layer.get('width',state['data']['width'])),int(layer.get('height',state['data']['height']))

    def top_left(self,layer,origin,state):
        w,h=self.size(layer,state);x,y=layer.get('position',[w/2,h/2])
        return origin[0]+x-w/2,origin[1]+y-h/2

    def build(self,layer,parent,origin,offset,shown,opacity,clip,state):
        shown=shown and layer.get('visible',True) and not layer.get('reference',False)
        own_alpha=float(layer.get('opacity',1));opacity*=own_alpha
        kind=layer['type'];top=self.top_left(layer,origin,state)
        if kind=='clonelayer':self.pending.append((layer,parent,origin,offset,shown,opacity,clip,state));return
        if kind=='grouplayer':
            group=self.collection(layer['name'],parent,layer);state['built'][layer['id']]=group
            group.hide_render=not shown;group.hide_viewport=not shown;group['oca_global_origin']=list(top)
            if own_alpha!=1:self.warn(layer['name']+': group opacity is applied per child; isolated overlapping group opacity is not exact in 3D')
            for child in layer.get('childLayers',[]):self.build(child,group,top,offset,shown,opacity,clip,state)
            return
        if kind=='ocalayer':
            source=layer['source'];path=self.nested_path(layer,state['path']);child=self.load(path)
            group=self.collection(layer['name'],parent,layer);state['built'][layer['id']]=group
            group['oca_document_path']=str(path);group['oca_time_offset']=int(source.get('timeOffset',0))
            if child.get('frameRate')!=state['data'].get('frameRate') or child.get('colorDepth')!=state['data'].get('colorDepth'):
                self.warn(layer['name']+': nested FPS/depth differ; parent timeline settings prevail')
            time=offset+int(source.get('timeOffset',0));start=max(clip[0],child['startTime']+time);end=min(clip[1],child['endTime']+time)
            w,h=child['width'],child['height'];cx,cy=layer.get('position',[w/2,h/2]);position=(origin[0]+cx-w/2,origin[1]+cy-h/2)
            if source.get('id'):
                child_state=dict(path=path,data=child,built={},layers={n['id']:n for n in walk(child['layers'])})
                target=child_state['layers'].get(source['id'])
                if target is None:raise ValueError(layer['name']+': missing nested source.id')
                self.build(target,group,position,time,shown,opacity,(start,end),child_state)
            else:self.build_document(path,group,position,time,shown,opacity,(start,end))
            return
        self.artwork(layer,parent,top,offset,shown,opacity,clip,state)

    def events(self,frames,offset,clip):
        events={clip[0]:None,clip[1]:None}
        # Starts take precedence over preceding exposure ends at the same frame.
        for cel in frames:events[int(cel['frameNumber'])+int(cel.get('duration',1))+offset]=None
        for cel in frames:events[int(cel['frameNumber'])+offset]=None if cel.get('name')=='_blank' else cel
        active=None;result={}
        for frame,cel in sorted(events.items()):
            if frame<=clip[0]:active=cel
            if frame==clip[0]:result[frame]=cel
            elif clip[0]<frame<clip[1]:result[frame]=cel
        result.setdefault(clip[0],active);result[clip[1]]=None
        return sorted(result.items())

    def artwork(self,layer,parent,top,offset,shown,opacity,clip,state,shared=None,time_shift=0):
        frames=copy.deepcopy(layer.get('frames',[]));vector=layer['type']=='vectorlayer'
        unsupported=[]
        if vector:
            for cel in frames:
                if not cel.get('fileName'):continue
                path=state['path'].parent/cel['fileName'];tags={e.tag.split('}')[-1] for e in ET.parse(path).iter()}
                if tags & {'linearGradient','radialGradient','filter','mask','use','pattern','text','image'}:unsupported.append(cel)
            if unsupported:
                rendered=False
                for cel in frames:
                    if not cel.get('fileName'):continue
                    alternate=cel.get('meta',{}).get('handoff',{}).get('raster')
                    if alternate:cel.update(alternate)
                    else:
                        cel['fileName']=str(self.svg_preview(state['path'].parent/cel['fileName'],cel,layer))
                        rendered=True
                vector=False
                self.warn(layer['name']+(': SVG preview rendered with Inkscape and packed into Blender; original SVG retained' if rendered else ': native GP cannot reproduce SVG features; using rendered companion and preserving SVG source references'))
        w,h=self.size(layer,state)
        if vector:
            obj=self.gp(layer,frames,state,offset,opacity,clip,shared=shared,time_shift=time_shift)
        else:
            obj=layers.create_layer(self.context,display_name(layer),w,h,parent)
            if shared is not None and isinstance(shared.data,bpy.types.Mesh):obj.data=shared.data
            material,texture=self.material(layer,frames,state,offset,opacity,clip)
            if shared is not None:
                obj.material_slots[0].link='OBJECT';obj.material_slots[0].material=material
            else:obj.data.materials.append(material)
        if obj.name not in parent.objects:layers.set_as_layer(obj,parent)
        self.metadata(obj,layer);self.created_objects.append(obj);state['built'][layer['id']]=obj
        self.depth-=.01;depth=self.depth
        obj['oca_source_file']=str(state['path']);obj['oca_frames']=json.dumps(layer.get('frames',[]),ensure_ascii=False)
        obj['oca_native_vector']=bool(vector)
        for frame,cel in self.events(frames,offset,clip):
            nonblank=cel is not None
            fw,fh=(float(cel.get('width',w)),float(cel.get('height',h))) if nonblank else (w,h)
            cx,cy=cel.get('position',[w/2,h/2]) if nonblank else (w/2,h/2)
            x,y=top[0]+cx,top[1]+cy
            if vector:x-=fw/2;y-=fh/2
            obj.location=((x-self.width/2)/100,depth,(self.height/2-y)/100)
            obj.scale=(1,1,1) if vector else (fw/w if w else 1,fh/h if h else 1,1)
            from .oca_transforms import apply as apply_transform
            factors=apply_transform(obj,layer,cel,vector=vector)
            collapsed=factors[0]==0 or factors[2 if vector else 1]==0
            obj.hide_render=obj.hide_viewport=not (shown and nonblank and not collapsed)
            for prop in ('location','rotation_euler','scale','hide_render','hide_viewport'):obj.keyframe_insert(data_path=prop,frame=frame)
        stepped(obj)
        return obj

    def svg_preview(self,path,cel,layer):
        executable=shutil.which('inkscape')
        if not executable:
            raise ValueError(layer['name']+': SVG needs a compatible renderer. Install Inkscape or export Rasterise Vector Layers from HandOff')
        if self.svg_previews is None:self.svg_previews=tempfile.TemporaryDirectory(prefix='bluik-oca-svg-')
        width,height=int(cel['width']),int(cel['height'])
        key=hashlib.sha256(path.read_bytes()+f':{width}x{height}'.encode()).hexdigest()
        output=Path(self.svg_previews.name)/(key+'.png')
        if not output.exists():
            result=subprocess.run([executable,str(path),'--export-area-page','--export-type=png',
                '--export-filename='+str(output),'--export-width='+str(width),'--export-height='+str(height)],
                stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=60)
            if result.returncode or not output.is_file():raise ValueError(layer['name']+': SVG renderer failed: '+result.stderr[-1500:])
            with output.open('rb') as stream:header=stream.read(24)
            if header[:8]!=b'\x89PNG\r\n\x1a\n' or struct.unpack('>II',header[16:24])!=(width,height):
                raise ValueError(layer['name']+': SVG renderer produced incorrect image dimensions')
        self.svg_preview_paths.add(str(output))
        return output

    def image(self,path):
        image=bpy.data.images.load(str(path),check_existing=True)
        if str(path) in self.svg_preview_paths and not image.packed_file:
            image.alpha_mode='STRAIGHT';image.pack()
        return image

    def material(self,layer,frames,state,offset,opacity,clip):
        first=next((f for f in frames if f.get('fileName')),None)
        image=self.image(state['path'].parent/first['fileName']) if first else dublf.materials.get_blank_image()
        material,texture=dublf.materials.create_im_material(image,display_name(layer),'EMISSION')
        texture.extension='CLIP';texture.interpolation='Closest'
        opacity_socket=material.node_tree.nodes['Opacity'].inputs[1]
        # Populate Bluik's existing TexAnim instead of adding a parallel handler.
        for frame,cel in self.events(frames,offset,clip):
            im=self.image(state['path'].parent/cel['fileName']) if cel else dublf.materials.get_blank_image()
            im.alpha_mode='PREMUL' if im.filepath.lower().endswith('.exr') else 'STRAIGHT'
            entry=texture.duik_texanim_images.add();entry.image=im;entry.name=im.name
            texture.duik_texanim_current_index=len(texture.duik_texanim_images)-1
            texture.keyframe_insert(data_path='duik_texanim_current_index',frame=frame)
            opacity_socket.default_value=opacity*float(cel.get('opacity',1)) if cel else 0
            opacity_socket.keyframe_insert(data_path='default_value',frame=frame)
        stepped(material.node_tree)
        return material,texture

    def gp(self,layer,frames,state,offset,opacity,clip,shared=None,time_shift=0):
        data=shared.data if shared is not None else bpy.data.grease_pencils.new(display_name(layer))
        obj=bpy.data.objects.new(display_name(layer),data)
        self.scene.collection.objects.link(obj);obj.use_grease_pencil_lights=False
        target_layers={}
        if time_shift:
            shift=obj.modifiers.new('OCA source time offset','GREASE_PENCIL_TIME')
            shift.mode='FIX';shift.offset=0;shift.use_keep_loop=False
            obj['oca_time_offset']=time_shift
        alpha=obj.modifiers.new('OCA instance opacity','GREASE_PENCIL_OPACITY');alpha.color_mode='BOTH'
        for frame,cel in self.events(frames,offset,clip):
            for target in target_layers.values():
                if next((f for f in target.frames if f.frame_number==frame),None) is None:target.frames.new(frame)
            if time_shift:
                # Select the source drawing explicitly at each OCA exposure.
                # This is independent of Blender's scene-range retiming rules.
                shift.offset=frame-time_shift;shift.keyframe_insert(data_path='offset',frame=frame)
            alpha.color_factor=opacity*float(cel.get('opacity',1)) if cel else 0
            alpha.keyframe_insert(data_path='color_factor',frame=frame)
            if cel is None or shared is not None:continue
            bpy.ops.object.select_all(action='DESELECT')
            path=state['path'].parent/cel['fileName']
            before=set(bpy.data.objects)
            bpy.ops.wm.grease_pencil_import_svg(filepath=str(path),scale=.01/(.0254/96),use_scene_unit=False,recenter_bounds=False)
            imported=[o for o in bpy.data.objects if o not in before]
            # Native px is 0.0254 / 96 metres; destination is 0.01 units/px.
            # Set the operator scale directly to their ratio (37.79527559).
            for source_obj in imported:
                if source_obj.type!='GREASEPENCIL':continue
                material_offset=len(data.materials)
                for mat in source_obj.data.materials:data.materials.append(mat)
                for index,source_layer in enumerate(source_obj.data.layers):
                    key=(index,source_layer.name)
                    if key not in target_layers:
                        target=data.layers.new(source_layer.name,set_active=True);target.use_lights=False;target_layers[key]=target
                        for earlier,_ in self.events(frames,offset,clip):
                            if earlier<frame:target.frames.new(earlier)
                    target=target_layers[key]
                    dst=next((f for f in target.frames if f.frame_number==frame),None)
                    if dst is None:dst=target.frames.new(frame)
                    source_frame=next((f for f in source_layer.frames if len(f.drawing.strokes)),None)
                    if source_frame:copy_drawing(source_frame.drawing,dst.drawing,material_offset)
                    target.opacity=float(source_layer.opacity)
                old_data=source_obj.data;bpy.data.objects.remove(source_obj,do_unlink=True)
                if old_data.users==0:bpy.data.grease_pencils.remove(old_data)
            if not any(len(f.drawing.strokes) for l in data.layers for f in l.frames):raise ValueError(layer['name']+': native SVG importer produced no drawing')
        stepped(data)
        return obj

    def build_clone(self,item,source):
        layer,parent,origin,offset,shown,opacity,clip,state=item
        source_layer=state['layers'][layer['source']['id']];time=int(layer['source'].get('timeOffset',0))
        while source_layer['type']=='clonelayer':
            time+=int(source_layer['source'].get('timeOffset',0))
            source_layer=state['layers'][source_layer['source']['id']]
        if isinstance(source,bpy.types.Collection):
            if time:raise ValueError(layer['name']+': time-offset collection clones need an independent animation instance')
            from .oca_transforms import rotation,scale
            if rotation(layer.get('rotation'))!=(0.,0.,0.) or scale(layer.get('scale'))!=(1.,1.,1.):
                raise ValueError(layer['name']+': transformed Collection clones are not implemented')
            obj=bpy.data.objects.new(layer['name'],None);parent.objects.link(obj)
            obj.instance_type='COLLECTION';obj.instance_collection=source
            w,h=self.size(source_layer,state);cx,cy=layer.get('position',[w/2,h/2])
            source_origin=source.get('oca_global_origin',[0,0]);obj.location=((origin[0]+cx-w/2-source_origin[0])/100,0,-(origin[1]+cy-h/2-source_origin[1])/100)
            obj.hide_render=obj.hide_viewport=not shown;self.metadata(obj,layer);state['built'][layer['id']]=obj;self.created_objects.append(obj)
            return
        target=copy.deepcopy(source_layer);target.update({k:v for k,v in layer.items() if k not in ('type','frames','animated','fileType','width','height','source')})
        target['id']=layer['id'];target['name']=layer['name']
        # Instances share data, not the source object's layer transforms.
        for key in ('rotation','scale'):
            target[key]=layer.get(key)
            for frame in target['frames']:
                frame.pop(key,None)
        top=self.top_left(target,origin,state)
        obj=self.artwork(target,parent,top,offset+time,shown,opacity,clip,state,shared=source,time_shift=time)
        obj['oca_layer_type']='clonelayer';obj['oca_source_id']=layer['source']['id']


def try_import(operator,context):
    path=document_path(operator.filepath)
    document=json.loads(path.read_text(encoding='utf-8'))
    if not is_importable(document):return False
    importer=Importer(context,operator,path)
    try:importer.run()
    except Exception:
        import traceback;traceback.print_exc();raise
    return True
