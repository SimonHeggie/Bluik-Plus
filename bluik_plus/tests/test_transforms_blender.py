"""Self-contained Blender 5.3 rotation/clone integration; no HandOff dependency."""
import bpy,os,sys,json,math
from pathlib import Path
import numpy as np
if os.environ.get('BLUIK_SOURCE'):sys.path.insert(0,str(Path(os.environ['BLUIK_SOURCE']).parent))
else:sys.path.insert(0,'/home/simon/.config/blender/5.3/scripts/addons')
import bluik_plus
if os.environ.get('BLUIK_SOURCE'):assert Path(bluik_plus.__file__).parent.samefile(os.environ['BLUIK_SOURCE'])
assert bluik_plus.bl_info['version']==(0,8,3)
from bluik_plus.oca_transforms import rotation
from bluik_plus.oca13_import import is_standard,is_importable
out=Path(os.environ['HANDOFF_TEST_OUTPUT']);out.mkdir(parents=True,exist_ok=True)
bluik_plus.register();scene=bpy.context.scene

def clear():
 for obj in list(bpy.data.objects):bpy.data.objects.remove(obj,do_unlink=True)
 for coll in list(bpy.data.collections):bpy.data.collections.remove(coll)

def image(path,size,quarters=False):
 w,h=size;rgba=np.empty((h,w,4),np.float32)
 rgba[:]=np.array([220,40,30,255])/255;rgba[:,w//2:]=np.array([30,180,40,255])/255
 if quarters:
  rgba[h//2:,:w//2]=np.array([20,40,220,255])/255;rgba[h//2:,w//2:]=np.array([230,210,20,255])/255
 im=bpy.data.images.new(path.stem,width=w,height=h,alpha=True)
 im.pixels.foreach_set(np.flip(rgba,axis=0).ravel());im.filepath_raw=str(path);im.file_format='PNG';im.save();bpy.data.images.remove(im)

def pixels(path):
 im=bpy.data.images.load(str(path),check_existing=False);w,h=im.size
 values=np.empty(w*h*4,np.float32);im.pixels.foreach_get(values);bpy.data.images.remove(im)
 return np.flip(values.reshape(h,w,4),axis=0)

def cel(name,frame,w,h,pos):
 return dict(name=name,id=name+str(frame),fileName=name+'.png',frameNumber=frame,duration=1,width=w,height=h,position=pos,opacity=1.)

def layer(name,frames,w=160,h=120,pos=None):
 return dict(name=name,id=name,type='paintlayer',animated=len(frames)>1,fileType='png',width=w,height=h,position=pos or [80,60],opacity=1.,visible=True,reference=False,blendingMode='normal',inheritAlpha=False,label=0,meta={},frames=frames)

def document(name,layers,version='1.3.0',end=3):
 return dict(name=name,ocaVersion=version,width=160,height=120,frameRate=24,startTime=0,endTime=end,colorDepth='U8',backgroundColor=[0,0,0,0],layers=layers)

def import_doc(folder,doc):
 path=folder/(doc['name']+'.oca');path.write_text(json.dumps(doc))
 assert getattr(bpy.ops.import_oca,'import')('EXEC_DEFAULT',filepath=str(path),directory=str(folder),shader='EMISSION',render_settings='REALTIME',color_management='DEFAULT')=={'FINISHED'}
 return path

def verify_modern(doc):
 source=doc['layers'][0];frames=source['frames'];clones=doc['layers'][1:]
 objects={o.get('oca_layer_id'):o for o in scene.objects if o.get('oca_layer_id')};checks=[]
 for frame in range(3):
  scene.frame_set(frame);fr=frames[frame];obj=objects['Source'];angles=rotation(fr.get('rotation',source['rotation']))
  np.testing.assert_allclose(obj.rotation_euler,[math.pi/2+angles[0],angles[1],angles[2]],atol=2e-6)
  factors=fr.get('scale',source['scale']);np.testing.assert_allclose(obj.scale[:2],[fr['width']/160*factors[0],fr['height']/120*factors[1]],atol=2e-6)
  for clone in clones:
   instance=objects[clone['id']];assert instance.data==obj.data
   assert instance.animation_data.action!=obj.animation_data.action
   angles=rotation(clone.get('rotation'));np.testing.assert_allclose(instance.rotation_euler,[math.pi/2+angles[0],angles[1],angles[2]],atol=2e-6)
   factors=clone.get('scale',[1,1]);np.testing.assert_allclose(instance.scale[:2],[fr['width']/160*factors[0],fr['height']/120*factors[1]],atol=2e-6)
  checks.append(dict(frame=frame,source_rotation=list(obj.rotation_euler),clone_scale=list(objects['MirrorX'].scale)))
 return checks

if os.environ.get('BLUIK_REOPEN_DOCUMENT'):
 doc=json.loads(Path(os.environ['BLUIK_REOPEN_DOCUMENT']).read_text());checks=verify_modern(doc)
 (out/'result.json').write_text(json.dumps(checks,indent=2));bluik_plus.unregister();print('BLUIK_083_REOPEN_PASS',flush=True);sys.exit(0)

clear();folder=out/'modern';folder.mkdir(exist_ok=True)
frames=[cel('F0',0,24,12,[40,40]),cel('F1',1,32,16,[44,46]),cel('F2',2,20,20,[48,48])]
for fr in frames:image(folder/fr['fileName'],(fr['width'],fr['height']))
source=layer('Source',frames);source.update(rotation=[10,20,30],scale=[1.5,.5])
frames[1].update(rotation=-25,scale=[.8,1.25]);frames[2].update(rotation=[-10,25,5],scale=[-1,1])
clones=[]
for name,rot,factors in [('MirrorX',90,[-1,1]),('MirrorY',[15,-20,35],[1,-1]),('Independent',None,None)]:
 clone=layer(name,[]);clone.update(type='clonelayer',source=dict(id='Source',timeOffset=0),position=[110,70])
 if rot is not None:clone['rotation']=rot
 if factors is not None:clone['scale']=factors
 clones.append(clone)
doc=document('Modern',[source,*clones]);assert not is_standard(doc) and is_importable(doc);import_doc(folder,doc)
checks=verify_modern(doc);scene.render.resolution_percentage=100;scene.eevee.taa_render_samples=8
scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGBA';scene.render.filepath=str(out/'modern-render.png')
bpy.ops.render.render(write_still=True);bpy.ops.wm.save_as_mainfile(filepath=str(out/'modern.blend'))

clear();folder=out/'legacy';folder.mkdir(exist_ok=True);image(folder/'Source.png',(40,20))
source=layer('LegacySource',[cel('Source',0,40,20,[40,30]),cel('Source',1,60,30,[44,34])],80,80,[40,30]);source.update(rotation=[10,20,30]);source['frames'][1]['rotation']=-35
legacy=[]
for name,w,h,pos in [('LegacyMirrorX',-40,20,[120,30]),('LegacyMirrorY',40,-20,[120,90])]:
 clone=layer(name,[cel('Source',0,20,10,pos),cel('Source',1,30,15,[pos[0]+4,pos[1]+4])],w,h,pos);clone.update(type='clonelayer',rotation=25);legacy.append(clone)
import_doc(folder,document('Legacy',[source,*legacy],'1.1.0',end=1))
original=bpy.data.objects['LegacySource'];x=bpy.data.objects['LegacyMirrorX'];y=bpy.data.objects['LegacyMirrorY'];assert x.data==y.data==original.data
for frame in range(2):
 scene.frame_set(frame);fw,fh=(20,10) if frame==0 else (30,15)
 np.testing.assert_allclose(x.scale[:2],[-fw/80,fh/80],atol=2e-6);np.testing.assert_allclose(y.scale[:2],[fw/80,-fh/80],atol=2e-6)
 angles=rotation(source['frames'][frame].get('rotation',source['rotation']))
 np.testing.assert_allclose(original.rotation_euler,[math.pi/2+angles[0],angles[1],angles[2]],atol=2e-6)
 np.testing.assert_allclose(x.rotation_euler,[math.pi/2,math.radians(25),0],atol=2e-6)
 pos=legacy[0]['frames'][frame]['position'];np.testing.assert_allclose([x.location.x,x.location.z],[(pos[0]-80)/100,(60-pos[1])/100],atol=2e-6)
assert x.active_material!=original.active_material

clear();folder=out/'flip-render';folder.mkdir(exist_ok=True);image(folder/'Quarters.png',(24,20),quarters=True)
source=layer('QuarterSource',[cel('Quarters',0,24,20,[40,30])]);flips=[]
for name,pos,factors in [('FlipHorizontal',[130,60],[-1,1]),('FlipVertical',[180,60],[1,-1])]:
 clone=layer(name,[]);clone.update(type='clonelayer',source=dict(id='QuarterSource',timeOffset=0),position=pos,scale=factors);flips.append(clone)
import_doc(folder,document('Flips',[source,*flips],end=1));scene.eevee.taa_render_samples=32
scene.view_settings.view_transform='Standard';scene.view_settings.look='None';scene.render.filepath=str(out/'flips.png')
bpy.ops.render.render(write_still=True);rgba=pixels(out/'flips.png')
source_pixels=rgba[20:40,28:52];horizontal=rgba[20:40,78:102];vertical=rgba[20:40,128:152]
assert min(source_pixels[...,3].max(),horizontal[...,3].max(),vertical[...,3].max())>.99
# Avoid antialiased outer edges AND the four-colour seam: compare solid
# quadrant cores, where horizontal/vertical correspondence is unambiguous.
cores=[(slice(3,7),slice(3,8)),(slice(3,7),slice(16,21)),
       (slice(13,17),slice(3,8)),(slice(13,17),slice(16,21))]
err_x=max(float(abs(horizontal[y,x]-source_pixels[:,::-1][y,x]).max()) for y,x in cores)
err_y=max(float(abs(vertical[y,x]-source_pixels[::-1][y,x]).max()) for y,x in cores)
assert max(err_x,err_y)<=2/255+1e-6,(err_x,err_y)
from bluik_plus import layers
mat=layers.create_layer_shader('Static opacity',[dict(name='Static',fileName=str(folder/'Quarters.png'),opacity=.35)],animated=False,shader='EMISSION')
assert abs(mat.node_tree.nodes['Opacity'].inputs[1].default_value-.35)<1e-6
(out/'result.json').write_text(json.dumps(dict(modern=checks,legacy_signed_clone_bounds=True,instance_transforms_independent=True,horizontal_pixel_error=err_x,vertical_pixel_error=err_y),indent=2))
bluik_plus.unregister();assert not any(fn.__module__.startswith('bluik_plus') for fn in bpy.app.handlers.frame_change_post)
print('BLUIK_083_TRANSFORMS_PASS',flush=True)
