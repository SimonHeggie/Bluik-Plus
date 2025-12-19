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
- **Animated cropped / trimmed frame compensation**
  - Per-frame transform keying to preserve visual alignment
- Deterministic post-import audit and diagnostics for useful bug reports
- Duik-compatible scene setup maintained with .OCA version 1.20

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
Therefore, first release to follow this is named; 0.8.0

---

## License

GPL-3.0  
Original work by RxLaboratory contributors.  
This fork contains significant functional changes and fixes.
