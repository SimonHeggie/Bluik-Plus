Bluik-Plus 0.8.3 improves OCA transform import, clone placement and animation compatibility in Blender 5.3.

## Changes in 0.8.3

- **Rotation and keyed transforms:** Apply the existing rotation convention consistently to layers and individual animation frames, using stepped keyframes. Single angles rotate about the imported 2D axis; three values represent XYZ Euler rotation in degrees. Image planes keep their 90-degree X-axis basis.
- **Signed scaling and flipped artwork:** Support negative scale values for images and Grease Pencil instances, including horizontal and vertical flips. Two-value scaling follows each artwork type's local image axes; three-value scaling addresses XYZ directly.
- **Clone placement:** Correct clone sizing and positioning when source geometry has non-uniform scale or rotation. Cropped frames, negative dimensions and animated clone sizes are handled without changing the shared source mesh or its transform keys.
- **Independent clone animation:** Instances continue to share their artwork data while retaining separate location, rotation, scale and animation keys.
- **Blender 5.3 animation fixes:** Update legacy image-opacity animation to use Blender's action-slot API instead of removed direct F-curve access. Correct parsing of Blender ID-property arrays in imported rotation data.
- **OCA 1.3 importer compatibility:** Apply supported rotation and scale extensions without bypassing the newer layer-ID, visibility, SVG and paint-blend import path.

## Compatibility notes

The rotation and scale properties are importer extensions, not standard OCA 1.3 fields. Pivot animation, transformed collection instances and animated draw-order changes are not included. Some complex compositing effects remain approximate.

## Install

Download **[bluik-plus_v0.8.3.zip](https://github.com/SimonHeggie/Bluik-Plus/releases/download/v0.8.3/bluik-plus_v0.8.3.zip)** and install it through **Blender > Edit > Preferences > Get Extensions > Install from Disk**. Restart Blender if an older version is already loaded.

If you are using the legacy add-on installer rather than Blender's extension installer, use the separately attached legacy ZIP instead.
