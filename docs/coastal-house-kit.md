# Coastal house kit

Drag a scene from `res://assets/models/coastal_houses/` into a Godot 3D scene, or load it as a `PackedScene`. Each filename identifies the assembled house. For example, `craftsman_two_story_veranda.tscn` includes the full upper floor and wide front porch.

| Family | Entries | Roof or height choices |
| --- | --- | --- |
| Cottage | Braced stoop, rain porch | Front gable |
| Craftsman | Gable porch, veranda | One or two stories |
| Island cabin | Lookout deck, mudroom | Metal gable |
| Contemporary | View terrace, screened entry | Single shed, butterfly, offset gable, raised clerestory |

## Placement

Use scale `1`. The origin is at ground level near the center of the house, with Godot +Y up and +Z toward the street. The existing town generator applies `Models.LEGACY_SCALE` to its procedural houses. Omit that multiplier when placing kit scenes.

`Entry` marks the front edge of the porch at deck height. `PorchLight` marks the fixture center. `LevelSite` supplies level-ground steps and any under-deck supports needed by the entry. For sloped terrain, keep the house level and fit the supports and stair run to the lot. The graded examples are in `art/coastal_hillside_kit.blend`.

## Assembly

The scenes reference shared GLB meshes in `parts/`. Each mesh is authored in the same house-local frame. The contemporary scenes expose a separate `Roof` and the two-story Craftsman exposes an `UpperStory`. Surface materials named `Siding`, `RoofFinish`, and `Details` identify paint roles where applicable. The scenes use `house_colors.tres` to display the authored vertex colors. The `ModelParts` loader can also read the meshes for batching.

To regenerate the game assets, run the following from the repository root with Blender on your path.

```sh
blender -b art/hillside_town.blend -P art/export_coastal_houses.py
```

The kit provides house options for [TID-53, visible town growth stages](https://linear.app/tideways/issue/TID-53/choose-visible-growth-stages-for-the-permanent-maps-towns).
