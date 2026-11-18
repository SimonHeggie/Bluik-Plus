"""Pure transform parsing/version tests; does not import/register Blender."""
import ast,importlib.util,math,tomllib,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('transform_values',ROOT/'oca_transforms.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class Values(unittest.TestCase):
 def test_scalar_and_one_element_rotation(self):
  self.assertEqual(module.rotation(90),(0.,math.pi/2,0.))
  self.assertEqual(module.rotation([-90]),(0.,-math.pi/2,0.))
 def test_three_axis_rotation(self):
  self.assertEqual(module.rotation([10,-20,30]),tuple(math.radians(v) for v in [10,-20,30]))
 def test_signed_scales(self):
  self.assertEqual(module.scale([-2,.5]),(-2.,.5,1.))
  self.assertEqual(module.scale([1,-1],vector=True),(1.,1.,-1.))
  self.assertEqual(module.scale([-1,2,-3]),(-1.,2.,-3.))
 def test_defaults(self):
  self.assertEqual(module.rotation(None),(0.,0.,0.))
  self.assertEqual(module.scale(None),(1.,1.,1.))
 def test_invalid_values(self):
  for value in [True,'90',[1,2],[1,2,3,4],[0,float('nan'),0],float('inf')]:
   with self.subTest(value=value),self.assertRaises(ValueError):module.rotation(value)
  for value in [False,'1',[1],[1,float('inf')],[1,2,3,4]]:
   with self.subTest(value=value),self.assertRaises(ValueError):module.scale(value)
 def test_version_consistency(self):
  tree=ast.parse((ROOT/'__init__.py').read_text())
  info=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='bl_info' for t in n.targets))
  self.assertEqual(info['version'],(0,8,3))
  self.assertEqual(tomllib.loads((ROOT/'blender_manifest.toml').read_text())['version'],'0.8.3')

if __name__=='__main__':unittest.main()
