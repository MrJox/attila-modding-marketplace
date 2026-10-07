# RPFM MCP tools (rpfm_server 4.5, 155 tools)

Generated from `tools/list` of a live server. Parameters in **bold** are required. JSON-typed parameters are passed as **JSON strings** (e.g. `paths='[{"File":"a/b"}]'`) unless the schema says array. Almost every tool takes `pack_key` (from `list_open_packs`). The full text of a tool is in the tool list; this page is the map.


## Session, game and schemas

| Tool | Parameters | What it does |
| --- | --- | --- |
| `get_game_selected` | - | Get the currently selected game key |
| `set_game_selected` | **game_name**, **rebuild_dependencies** | Set the current game |
| `is_schema_loaded` | - | Check if a schema is currently loaded |
| `update_schemas` | - | Update schemas from the remote repository |
| `check_schema_updates` | - | Check if there is a schema update available |
| `get_schema` | - | Get the current schema |
| `save_schema` | **schema** | Save the provided schema to disk |
| `get_custom_table_list` | - | Get custom table names (start_pos_, twad_ prefixes) from the schema |
| `import_schema_patch` | **patches** | Import a schema patch from an external source |
| `save_local_schema_patch` | **patches** | Save local schema patches to customize column metadata without modifying the upstream schema |
| `remove_local_schema_patches_for_table` | **value** | Remove local schema patches for a table |
| `remove_local_schema_patches_for_table_and_field` | **key**, **value** | Remove local schema patches for a specific field in a table |
| `update_current_schema_from_asskit` | - | Update the currently loaded schema with data from the game's Assembly Kit |
| `rebuild_dependencies` | **value** | Rebuild dependencies |
| `generate_dependencies_cache` | - | Generate the dependencies cache for the selected game |
| `is_there_a_dependency_database` | **value** | Check if there is a dependency database loaded |
| `assembly_kit_path` | - | Get the Assembly Kit path for the current game |

## Open, create, save and close packs

| Tool | Parameters | What it does |
| --- | --- | --- |
| `new_pack` | - | Create a new empty PackFile |
| `open_packfiles` | **paths** | Open one or more PackFiles |
| `load_all_ca_pack_files` | - | Open all CA (vanilla) PackFiles for the selected game as one merged PackFile |
| `list_open_packs` | - | List all currently open packs with their keys and metadata |
| `open_pack_info` | **pack_key** | Get the info about the pack identified by `pack_key` and the list of files it contains |
| `get_pack_file_name` | **pack_key** | Get the file name of the pack identified by `pack_key` |
| `get_pack_file_path` | **pack_key** | Get the file path of the pack identified by `pack_key` |
| `save_packfile` | **pack_key** | Save the pack identified by `pack_key` |
| `save_pack_as` | **pack_key**, **path** | Save the pack identified by `pack_key` to a new path |
| `clean_and_save_pack_as` | **pack_key**, **path** | Clean the pack identified by `pack_key` from corrupted files and save to a path |
| `close_pack` | **pack_key** | Close the pack identified by `pack_key` without saving |
| `close_all_packs` | - | Close all currently open packs without saving |
| `set_pack_file_type` | **pack_file_type**, **pack_key** | Set the type of the pack identified by `pack_key` |
| `get_pack_settings` | **pack_key** | Get the settings of the pack identified by `pack_key` |
| `set_pack_settings` | **pack_key**, **settings** | Set the settings of the pack identified by `pack_key` |
| `change_compression_format` | **format**, **pack_key** | Change the compression format of the pack identified by `pack_key` |
| `change_data_is_encrypted` | **pack_key**, **value** | Change whether the file data is encrypted for the pack identified by `pack_key` |
| `change_index_is_encrypted` | **pack_key**, **value** | Change whether the pack index (file paths, sizes and timestamps) is encrypted for the pack identified by `pack_key` |
| `change_index_includes_timestamp` | **pack_key**, **value** | Change whether the pack index includes timestamps for the pack identified by `pack_key` |
| `get_dependency_pack_files_list` | **pack_key** | Get the list of PackFiles marked as dependencies of the pack identified by `pack_key` |
| `set_dependency_pack_files_list` | **list**, **pack_key** | Set the list of PackFiles marked as dependencies for the pack identified by `pack_key` |
| `trigger_backup_autosave` | **pack_key** | Trigger a backup autosave for the pack identified by `pack_key` |

## Files inside a pack

| Tool | Parameters | What it does |
| --- | --- | --- |
| `packed_file_exists` | **pack_key**, **value** | Check if a file exists in the pack identified by `pack_key` |
| `folder_exists` | **pack_key**, **value** | Check if a folder exists in the pack identified by `pack_key` |
| `get_packed_files_info` | **pack_key**, **values** | Get the info of one or more files in the pack identified by `pack_key` |
| `get_rfile_info` | **pack_key**, **value** | Get the info of a single file in the pack identified by `pack_key` |
| `new_packed_file` | **new_file**, **pack_key**, **path** | Create a new file inside the pack identified by `pack_key` |
| `add_packed_files` | **destination_paths**, ignore_paths, **pack_key**, **source_paths** | Add files from disk to the pack identified by `pack_key` |
| `add_packed_files_from_pack_file` | **container_paths**, **pack_key**, **source_pack_path** | Add files from another PackFile to the pack identified by `pack_key` |
| `extract_packed_files` | **destination_path**, **export_as_tsv**, **pack_key**, **source_paths** | Extract files from the pack identified by `pack_key` to disk |
| `delete_packed_files` | **pack_key**, **paths** | Delete files from the pack identified by `pack_key` |
| `rename_packed_files` | **pack_key**, **renames** | Rename files in the pack identified by `pack_key` |
| `duplicate_packed_files` | **pack_key**, **paths** | Duplicate files in-place within the same pack |
| `copy_packed_files` | **paths_by_pack** | Copy files to the internal clipboard |
| `cut_packed_files` | **paths_by_pack** | Cut files to the internal clipboard |
| `paste_packed_files` | **destination_path**, **pack_key** | Paste files from the internal clipboard into the pack identified by `pack_key` |
| `get_packed_file_raw_data` | **pack_key**, **value** | Get the raw binary data of a file in the pack identified by `pack_key` |
| `import_dependencies_to_open_pack_file` | **pack_key**, **paths** | Import files from dependencies into the pack identified by `pack_key` |
| `get_packed_files_names_starting_with_path_from_all_sources` | **path** | Get all file names under a path prefix across all data sources (PackFile, GameFiles, ParentFiles) |
| `get_rfiles_from_all_sources` | **lowercase**, **paths** | Get files from all known sources (PackFile, GameFiles, ParentFiles) |
| `clean_cache` | **pack_key**, **paths** | Clean the decode cache for the provided paths in the pack identified by `pack_key` |
| `open_packed_file_in_external_program` | **container_path**, **pack_key**, **source** | Open a file in the system's default program from the pack identified by `pack_key` |
| `save_packed_file_from_external_view` | **external_path**, **internal_path**, **pack_key** | Save a file from an external program back to the pack identified by `pack_key` |
| `open_containing_folder` | **pack_key** | Open the folder containing the pack identified by `pack_key` in the file manager |

## Decode, edit and TSV

| Tool | Parameters | What it does |
| --- | --- | --- |
| `decode_packed_file` | **pack_key**, **path**, **source** | Decode a file from the pack identified by `pack_key` |
| `save_packed_file_from_view` | **data**, **pack_key**, **path** | Save an edited decoded file back to the pack identified by `pack_key` |
| `save_packed_files_to_pack_file_and_clean` | **files**, **optimize**, **pack_key** | Save files to the pack identified by `pack_key` and optionally optimize afterward |
| `export_tsv` | **pack_key**, **table_path**, **tsv_path** | Export a table from the pack identified by `pack_key` to a TSV file |
| `import_tsv` | **pack_key**, **table_path**, **tsv_path** | Import a TSV file to a table in the pack identified by `pack_key` |
| `update_table` | **pack_key**, **value** | Update a table to the latest schema version in the pack identified by `pack_key` |
| `merge_files` | **delete_source**, delta_merge, **merged_path**, **pack_key**, **paths** | Merge multiple compatible tables into one in the pack identified by `pack_key` |
| `get_tables_by_table_name` | **pack_key**, **value** | Get table paths by table name from the pack identified by `pack_key` |
| `fields_processed` | **definition** | Get the processed fields from a definition, with bitwise expansion, enum conversions, and colour-group merging applied |
| `definitions_by_table_name` | **value** | Get all definitions for a table name |
| `definition_by_table_name_and_version` | **name**, **version** | Get a specific definition by table name and version |
| `delete_definition` | **name**, **version** | Delete a definition by table name and version |
| `get_missing_definitions` | **pack_key** | Export missing table definitions for the pack identified by `pack_key` to a file (for debugging) |

## Vanilla / dependency data and references

| Tool | Parameters | What it does |
| --- | --- | --- |
| `get_tables_from_dependencies` | **value** | Get table data from dependencies by table name |
| `get_table_list_from_dependency_pack_file` | - | Get the table names of all DB files in dependency PackFiles |
| `get_table_definition_from_dependency_pack_file` | **value** | Get the definition of a table from the dependency database |
| `get_table_version_from_dependency_pack_file` | **value** | Get the version of a table from the dependency database |
| `dependencies_column_values` | **column_name**, **table_name** | Get the distinct values of the column `column_name` of the DB table `table_name` (like `factions_tables`), from the open packs, their parent packs and vanilla |
| `get_reference_data_from_definition` | **definition**, **force**, **pack_key**, **table_name** | Get valid reference values for columns in a table definition for the pack identified by `pack_key` |
| `referencing_columns_for_definition` | **definition**, **table_name** | Get columns from other tables that reference the given table's definition |
| `search_references` | **pack_key**, **reference_map**, **value** | Find all references to a value in the pack identified by `pack_key` |
| `go_to_definition` | **column_name**, **pack_key**, **table_name**, **values** | Go to the definition of a reference in the pack identified by `pack_key` |
| `go_to_loc` | **pack_key**, **value** | Go to a loc key's location in the pack identified by `pack_key` |
| `get_source_data_from_loc_key` | **pack_key**, **value** | Get the source data of a loc key in the pack identified by `pack_key` |
| `cascade_edition` | **changes**, **definition**, **pack_key**, **table_name** | Trigger a cascade edition on all referenced data in the pack identified by `pack_key` |
| `generate_missing_loc_data` | **pack_key** | Generate all missing loc entries for the pack identified by `pack_key` |
| `add_keys_to_key_deletes` | **key_table_name**, **keys**, **pack_key**, **table_file_name** | Add keys to the key_deletes table in the pack identified by `pack_key` |

## Search, diagnostics and tests

| Tool | Parameters | What it does |
| --- | --- | --- |
| `global_search` | **pack_key**, **search** | Run a global search across the pack identified by `pack_key` |
| `global_search_replace_all` | **pack_key**, **search** | Replace all matches in a global search for the pack identified by `pack_key` |
| `global_search_replace_matches` | **matches**, **pack_key**, **search** | Replace specific matches in a global search for the pack identified by `pack_key` |
| `diagnostics_check` | **check_ak_only_refs**, **ignored** | Run a full diagnostics check over all open packs |
| `diagnostics_update` | **check_ak_only_refs**, **diagnostics**, **paths** | Update diagnostics incrementally for changed files across all open packs |
| `add_line_to_pack_ignored_diagnostics` | **pack_key**, **value** | Add a line to the ignored diagnostics list for the pack identified by `pack_key` |
| `lua_run_tests` | campaign, **test_source** | Run Lua tests against the scripts of all open packs, outside of the game |

## Ship and game integration

| Tool | Parameters | What it does |
| --- | --- | --- |
| `optimize_pack_file` | **options**, **pack_key** | Optimize the pack identified by `pack_key` by removing unchanged/duplicate data |
| `get_optimizer_options` | - | Get the default optimizer options |
| `live_export` | **pack_key** | Live export the pack identified by `pack_key` to the game folder for testing |
| `build_starpos_get_campaign_ids` | **pack_key** | Get campaign IDs for starpos building in the pack identified by `pack_key` |
| `build_starpos_check_victory_conditions` | **pack_key** | Check if victory conditions file exists for starpos building in the pack identified by `pack_key` |
| `build_starpos` | **campaign_id**, **pack_key**, **process_hlp_spd** | Build starpos (pre-processing step) for the pack identified by `pack_key` |
| `build_starpos_post` | **campaign_id**, **pack_key**, **process_hlp_spd** | Build starpos (post-processing step) for the pack identified by `pack_key` |
| `build_starpos_cleanup` | **campaign_id**, **pack_key**, **process_hlp_spd** | Clean up starpos temporary files for the pack identified by `pack_key` |
| `pack_map` | **pack_key**, **tile_maps**, **tiles** | Pack map tiles into the pack identified by `pack_key` |
| `initialize_my_mod_folder` | **game**, gitignore, **name**, **sublime**, **vscode** | Initialize a MyMod folder for mod development |

## Models, animation and misc (rare for Attila)

| Tool | Parameters | What it does |
| --- | --- | --- |
| `export_rigid_to_gltf` | **output_path**, **rigid_model** | Export a RigidModel to glTF format |
| `add_packed_files_from_animpack` | **anim_pack_key**, **animpack_path**, **container_paths**, **pack_key**, **source** | Copy files from an AnimPack owned by `anim_pack_key` into the destination pack `pack_key` (the two may differ) |
| `add_packed_files_from_pack_file_to_animpack` | **animpack_path**, **container_paths**, **pack_key**, **source_pack_key** | Copy files from the pack identified by `source_pack_key` into an AnimPack owned by `pack_key` (the two may differ) |
| `delete_from_animpack` | **animpack_path**, **container_paths**, **pack_key** | Delete files from an AnimPack in the pack identified by `pack_key` |
| `update_anim_ids` | **offset**, **pack_key**, **starting_id** | Update animation IDs with an offset in the pack identified by `pack_key` |
| `get_anim_paths_by_skeleton_name` | **value** | Get animation paths by skeleton name |
| `set_video_format` | **format**, **pack_key**, **path** | Change the format of a ca_vp8 video file in the pack identified by `pack_key` |
| `add_note` | **note**, **pack_key** | Add a note to the pack identified by `pack_key` |
| `delete_note` | **id**, **pack_key**, **path** | Delete a note by path and ID in the pack identified by `pack_key` |
| `notes_for_path` | **pack_key**, **value** | Get all notes under a path in the pack identified by `pack_key` |
| `dependencies_art_set_ids` | - | Get art set IDs from dependencies' campaign_character_arts_tables |
| `local_art_set_ids` | **pack_key** | Get local art set IDs from campaign_character_arts_tables in the pack identified by `pack_key` |
| `patch_siege_ai` | **pack_key** | Patch the SiegeAI of a Siege Map in the pack identified by `pack_key` for Warhammer games |

## RPFM global settings and updates (change only when asked)

| Tool | Parameters | What it does |
| --- | --- | --- |
| `settings_get_all` | - | Get all settings at once (bool, i32, f32, string, raw_data, and vec_string maps) |
| `settings_get_bool` | **value** | Get a boolean setting value by key |
| `settings_get_f32` | **value** | Get an f32 setting value by key |
| `settings_get_i32` | **value** | Get an i32 setting value by key |
| `settings_get_path_buf` | **value** | Get a PathBuf setting value by key |
| `settings_get_string` | **value** | Get a string setting value by key |
| `settings_get_vec_raw` | **value** | Get a raw bytes setting value by key |
| `settings_get_vec_string` | **value** | Get a Vec<String> setting value by key |
| `settings_set_bool` | **key**, **value** | Set a boolean setting value |
| `settings_set_f32` | **key**, **value** | Set an f32 setting value |
| `settings_set_i32` | **key**, **value** | Set an i32 setting value |
| `settings_set_path_buf` | **key**, **value** | Set a PathBuf setting value |
| `settings_set_string` | **key**, **value** | Set a string setting value |
| `settings_set_vec_raw` | **key**, **value** | Set a raw bytes setting value |
| `settings_set_vec_string` | **key**, **value** | Set a Vec<String> setting value |
| `settings_clear_path` | **path** | Clear a config path |
| `clear_settings` | - | Clear all settings and reset to defaults |
| `backup_settings` | - | Backup the current settings to memory |
| `restore_backup_settings` | - | Restore settings from the backup |
| `config_path` | - | Get the config path |
| `schemas_path` | - | Get the schemas path |
| `dependencies_cache_path` | - | Get the dependencies cache path |
| `backup_autosave_path` | - | Get the backup autosave path |
| `table_profiles_path` | - | Get the table profiles path |
| `translations_local_path` | - | Get the translations local path |
| `old_ak_data_path` | - | Get the old Assembly Kit data path |
| `check_updates` | - | Check if there is an RPFM update available |
| `update_main_program` | - | Update the program to the latest version |
| `check_lua_autogen_updates` | - | Check for Lua autogen updates |
| `update_lua_autogen` | - | Update the Lua autogen repository |
| `check_translations_updates` | - | Check for translation updates |
| `update_translations` | - | Update the translations repository |
| `generate_vanilla_translation_source` | **src_lang** | Generate the vanilla texts of a source language from the game's locale packs |
| `get_pack_translation` | **language**, **pack_key**, src_lang | Get pack translation data for a language from the pack identified by `pack_key` |
| `check_empire_and_napoleon_ak_updates` | - | Check for Empire/Napoleon Assembly Kit updates |
| `update_empire_and_napoleon_ak` | - | Update the Empire/Napoleon Assembly Kit files |

## Escape hatch

| Tool | Parameters | What it does |
| --- | --- | --- |
| `call_command` | **command** | Call any IPC command directly |

## Resources (read with `resources/read`, no tool call needed)

| URI | Content |
| --- | --- |
| `rpfm://games` | valid game keys |
| `rpfm://enums/PFHFileType`, `CompressionFormat`, `DataSource`, `ContainerPath`, `NewFile`, `SupportedFormats` | enum values with JSON examples |
| `rpfm://examples/global_search` | complete `GlobalSearch` object to copy and edit |
| `rpfm://examples/optimizer_options` | complete `OptimizerOptions` object with field descriptions |
| `rpfm://reference/initialization` | start-up sequence |
| `rpfm://reference/path_conventions` | in-pack path conventions |

## Response shapes seen in practice

Responses are `{"<VariantName>": payload}` JSON in one text content block:

| Call | Response |
| --- | --- |
| `new_pack` | `{"String":"new_pack.pack"}` (the pack key) |
| `open_packfiles` | `{"StringContainerInfo":[<key>,{file_name,file_path,pfh_version,pfh_file_type,compress,timestamp}]}` |
| `list_open_packs` | `{"VecStringContainerInfo":[[<key>,{...}],...]}` |
| `decode_packed_file` (DB) | `{"DBRFileInfo":[{"table":{"table_name","definition","table_data":[[cell,...],...]}}, {path,file_type,...}]}`; cells are `{"I32":1}`, `{"StringU8":"x"}`, `{"Boolean":true}` ... |
| `decode_packed_file` (Lua/XML) | `{"TextRFileInfo":[{"encoding","format","contents"},{...}]}` |
| `export_tsv`, `save_packed_file_from_view`, `new_packed_file` | `"Success"` |
| `extract_packed_files` | `{"StringVecPathBuf":["files_extracted_success",[<paths>]]}` |
| `import_tsv` | decoded file on success, `{"Error":"..."}` text on a bad TSV |
| `dependencies_column_values` | `{"HashSetString":[...]}` |
| `diagnostics_check` | `{"Diagnostics":{"results":[...]}}` |
| `set_game_selected` | `{"CompressionFormatDependenciesInfo":["None",<info or null>]}` |
