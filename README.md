# Bluik-Plus

**OCA artwork and animation import for Blender.** Bluik-Plus brings layered 2D documents into Blender as editable scene elements, with tools for cutout animation and Duik-style workflows. It is a fork of Bluik, originally developed by Nicolas Dufresne and contributors.

## Features

- **OCA import:** Import layered stills and animated documents, including supported OCA 1.3 layers, SVG artwork, image sequences, references, nested sources and opacity data.
- **Artwork reuse:** Keep supported image and Grease Pencil clones linked to their source data while allowing each instance to have its own placement and animation.
- **Layer organization:** Create Blender scene objects and collections with imported artwork order, names, visibility and placement.
- **Transform import:** Read supported position, cropped-frame placement, scale and rotation data. Preserve stepped frame animation, signed scaling, image flips and per-instance transforms.
- **Paint and blend modes:** Translate supported OCA blend modes into Blender materials and shader configurations, with documented approximations for unsupported combinations.
- **Cutout tools:** Retain the existing 2D rigging, layer, selection and animation controls included with Bluik.

Rotation and scale values outside the standard OCA fields are supported as Bluik import extensions. Some vector effects, nested group compositing and 3D intersections may render differently from their source editors.

## Installation

Download the current **Blender extension ZIP** from [Releases](https://github.com/SimonHeggie/Bluik-Plus/releases) and install it through **Edit > Preferences > Get Extensions > Install from Disk**. Do not extract it first. A legacy add-on ZIP is provided separately where needed.

The extension manifest requires **Blender 4.5 or newer**. Transform handling and animation have been tested in Blender 5.3 beta, but that does not certify every Blender version or receiving document.

## Documentation

See [Bluik documentation](https://bluik.rxlab.guide/) for the underlying toolset. Version changes are recorded in [GitHub Releases](https://github.com/SimonHeggie/Bluik-Plus/releases).

## Licence and attribution

GPL-3.0-or-later. Original project by Nicolas Dufresne and contributors. Bluik-Plus modifications by Simon Heggie. See [LICENSE](LICENSE).
