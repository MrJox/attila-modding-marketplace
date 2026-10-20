---
name: attila-ui-layouts
description: Read, edit and render Total War UI layout files (the extension-less files under ui/ in the packs, .cml, .fc, .twui.images) through the wce-ui MCP server (tools ui_files, ui_open, ui_tree, ui_entry, ui_xml, ui_set_xml, ui_set_entry, ui_add, ui_delete, ui_reparent, ui_render, ui_save). Layouts convert to XML on open and back to the exact binary on save; pictures come from the game packs. Use when the task is to change a UI panel, move or resize components, change a text, add or remove a component, see what a layout looks like, or ship a UI change in a mod pack.
---

# UI layouts with the wce-ui MCP server

The tool names start with `ui_` (server `wce-ui`). If the server shows a single `ui_setup_help` tool, the executable is missing: it is built from the Warscape Community Editor (`cargo build --release -p wce_ui_cli`) and located through the plugin option `wce_ui_path`, `WCE_UI`, the plugin's `bin` folder or PATH.

## Workflow

1. `ui_files` with a `filter` finds the layout (`settlement` -> `ui/campaign ui/settlement_panel`). Mod packs sit over vanilla, so a layout the mod already changed opens as changed.
2. `ui_open` it (any later call may also pass `source` instead of `id`), then `ui_tree` for the components: `[number] name (class) @x,y WxH  screen x,y`. Offsets are relative to the parent; `screen` is absolute in the layout's own pixels (the root is the screen size, for example 1280x1024). A component with a dock point is put at that point of its parent plus its dock offset, whatever its stored offset says (`ui_tree` then adds `(stored x,y)`): to move a docked component use `ui_set_entry` x/y (it changes the dock offset) rather than editing the first two integers.
3. `ui_render` returns a PNG (pictures from the packs; text in a small upper-case font; hidden-by-default panels are drawn too). Use `outlines`, `select` + `frame` and `scale` to look at one component. Render before and after an edit.
4. Edit: `ui_set_entry` (x, y, w, h, name, text, color), `ui_set_property` (by the game's name from the `properties` list of `ui_entry` / `ui_state`: 'Visible', 'Dock point' = 'Bottom centre', 'Horizontal alignment' = 'Centre', 'Interactive', 'Text colour' = '#RRGGBB'; use `scope` state or `state` name for state properties; prefer it, it knows what the flags and numbers mean), `ui_set_field` (any primitive by field number, for what has no property), `ui_add`, `ui_duplicate`, `ui_delete`, `ui_move` (paint order), `ui_reparent` (keeps the place on screen), or `ui_set_xml` to replace a component's XML (or the whole file). A bad edit is refused and changes nothing.
5. `ui_validate`, then `ui_save` with `pack` (a mod `.pack`; `path` is the in-pack path, default where it came from) or `out` (a file; `format` xml for the XML). Never save into the game's own packs.

Component numbers change after add, delete, duplicate, move and reparent (those return the new number): re-run `ui_tree`, or address components by name path (`root/panel/button`).

## The XML in short

One element per primitive, in file order (`<i>5</i>`, `<s>text</s>`, `<unicode>`, `<flt>`, `<yes />`/`<no />`, `<byte>`, `<uuid>`), inside structure tags. The file has no field names: position is the meaning, so keep the order and count of primitives of an element. `count` attributes are fixed automatically. `<!-- ... -->` comments are labels for people; they are ignored. A `uientry` has: id, name, class (`title2`), x, y, 12 flags, tooltip text and id, docking values, images (id, path, size), states (id, name, size, text, font, colour, shaders, image uses with their rectangle inside the component), properties, funcs, children, additional data. Duplicating with `ui_duplicate` gives new ids; copying XML by hand duplicates ids, which ties image uses to the wrong images.

## Screens, related layouts and animations

* `ui_render` with `screen` ("1920x1080") sizes the root to that screen as the game does and re-docks every docked component: use it to check a change at other resolutions. `ui_tree` takes `screen` too.
* States belong to single components; there is no layout-wide state. Use `ui_states` with `entry` to list one component's states and `entry_state` ("button=hover") to draw it in one. (`state` draws every component that has a state of that name; it is only a shortcut.)
* `ui_related` lists layouts used together with this one (a layout named after a component of this one is a child; one with a component named after this layout is a parent). The format does not store this link, so it is found by name and can be wrong (common names are flagged). `ui_render` with `related` draws them faded as visual reference.
* `ui_animations` lists a component's animations (frames: time, easing, what moves, targets, triggers); `ui_render` with `animation`, `animation_entry` and `time` (ms) draws the layout part way through one, including the animations and state changes its frames trigger. Edit frames with `ui_xml` / `ui_set_xml` (`<anim>` elements). Rotation, picture cross-fade and shader values are not drawn.

## Limits to know

Not drawn: hover/click behaviour, scripts, list and table layouts, rotation, shader values, what the game creates at runtime. Text uses the game's own bitmap fonts. Components hidden at load (seventh flag) and `*template` names are left out unless `show_hidden` / `show_templates`; `skin` takes a skin folder under ui/skins (`ui_skins`). Only the versions in Attila (2, 52 and 77 to 97) were checked byte for byte against real files; other games' versions use the same converter but are untested here. Offsets and sizes are integers in the file; the game clips nothing for you, so check a moved component against its parent in a render.
