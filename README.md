# Bluik – OCA Importer for Blender (Duik 2D)

Bluik is a Blender importer for **Open Cel Animation (.oca)** documents, targeting a Krita → Blender → game/VFX pipeline using **Duik 2D** conventions.

This fork significantly improves reliability and correctness of OCA imports compared to upstream 0.7.5, with a focus on blend modes, clone layers, and animated frame handling.

---

## Key Features

- Robust **blend mode support** via a deterministic `BLEND-MODE` shader node group
- Correct handling of **image clone layers**
  - Shared mesh datablocks
  - Independent per-object materials (object-linked slots)
  - Independent opacity animation
  - Correct depth (Y) placement
- **Animated cropped / trimmed frame compensation**
  - Per-frame transform keying to preserve visual alignment
- Deterministic post-import audit and diagnostics
- Duik-compatible scene setup (camera, depth, layering)

---

## Supported Blend Modes

OCA/Krita blend modes are mapped to a stable compatibility subset:

| OCA Blend Mode | Blender Output |
|---------------|----------------|
| normal        | normal         |
| add / screen | add            |
| multiply     | multiply       |
| dodge / glow | luminosity (approximate) |

Unsupported or incompatible modes are **warned** and safely fall back to `normal`.

---

## Versioning

This release represents a **major functional improvement** over 0.7.5.

See `CHANGELOG.md` for full details.

---

## Notes for Developers

- The node group datablock name is **`BLEND-MODE`**
  - Do not search by UI label (“Blend Mode”)
- Material Output sockets accept only **one incoming link**
- Clone layers are resolved *after* originals are created
- Object-linked material slots are required for per-clone animation

---

## License

GPL-3.0  
Original work by RxLaboratory contributors.  
This fork contains significant functional changes and fixes.
