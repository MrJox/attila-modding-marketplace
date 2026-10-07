---
name: attila-file-formats
description: Binary file format specifications for Total War Attila assets - .rigid_model_v2 (RMV2 v6 meshes), .cs2.parsed (v11/v13 building technical files), .cs2 (3ds Max intermediate scene), .anim (v5 animations) and .bone_inv_trans_mats (skeleton inverse bind matrices). Use when reading, writing, converting or debugging models, buildings, skeletons or animations, e.g. writing an importer/exporter, fixing a corrupt model, or checking what a field in a building file means.
---

# Attila file formats

Reverse-engineered specs written against Attila's engine and the Assembly Kit tools. Each file is self-contained: layout diagram, field tables with types and byte offsets, enums, and notes on the C++ types in the engine header (`attila-engine-header` skill). All data is little-endian.

| Spec | File type | Where it lives in packs | Read it for |
| --- | --- | --- | --- |
| [rigid_model_v2_spec.md](references/rigid_model_v2_spec.md) | `.rigid_model_v2`, RMV2 version 6 | `variantmeshes/...`, `terrain/...`, building and prop meshes | LOD groups, mesh headers, materials/shader params, vertex formats (half floats, packed normals, bone weights), attachment points |
| [cs2_parsed_spec.md](references/cs2_parsed_spec.md) | `.cs2.parsed`, versions 11 and 13 | next to building models (`*_tech.cs2.parsed`) | building pieces, destruction levels, collision hulls, pathfinding/no-go zones, siege-engine mounts, docking points, VFX anchors |
| [cs2_spec.md](references/cs2_spec.md) | `.cs2` (3ds Max exporter output) | authoring side, not shipped | the intermediate scene/mesh/animation format the Assembly Kit converts to RMV2 and `.cs2.parsed` |
| [anim_spec.md](references/anim_spec.md) | `.anim`, version 5 | `animations/...` | bone hierarchy, track mapping, 16-bit compressed quaternions, float translations |
| [bone_inv_trans_mats_spec.md](references/bone_inv_trans_mats_spec.md) | `.bone_inv_trans_mats` | `animations/skeletons/<skeleton>.bone_inv_trans_mats` | inverse bind pose matrices used for GPU skinning |

## How to use

- Pull a file out of a pack first (`attila-rpfm`: `extract_packed_files` with `export_as_tsv:false`, or `rpfm_cli pack extract -f "<path>;<short dir>"`).
- Check the version field before applying a spec: RMV2 v6 and CS2 parsed v11/v13 are the Attila ones; other Total War games use other versions (their layouts differ).
- RPFM can already decode and export some of these: `export_rigid_to_gltf` (RMV2 to glTF) and the animation tools. For structure questions, read the spec; for conversion, try RPFM first.
- Validate a parser by round-tripping real vanilla files and comparing byte-for-byte; the specs describe padding and alignment where the engine requires it.
- Engine-side structures (`EMPIREUTILITY::BUILDING_PIECE_DESCR`, `WARSCAPE::WS_SCENE_NODE_RIGID_V2`, `UTILITYLIB::ANIMATION`) can be inspected with `python header.py struct <NAME> --bases`.
