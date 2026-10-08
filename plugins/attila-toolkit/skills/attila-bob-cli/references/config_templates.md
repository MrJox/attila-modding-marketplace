# BOB configuration templates

All files go to `<kit>\binaries\BOB\<name>_configuration.xml`; run with `/configuration:<name>`. `bob_run.py` writes the common shape for you; these are the verified variants. `&lt;raw>` and `&lt;raw&gt;` are equivalent.

## Building (verified)

```xml
<bob_configuration>
    <processors><processor>Building</processor></processors>
    <directories/>
    <global_rules/>
    <retail>0</retail>
    <silent>1</silent>
    <scan_perforce>0</scan_perforce>
    <merge_for_checkin_mode>3</merge_for_checkin_mode>
    <keep_output>1</keep_output>
    <load_asset_graph>0</load_asset_graph>
    <selected_providers/>
    <selected_consumers>
        <entry>&lt;raw>/art/battle/land/models/architecture/eastern/House.CS2</entry>
    </selected_consumers>
</bob_configuration>
```

`bob_run.py run --processor Building --consumer raw:/art/battle/land/models/architecture/eastern/House.CS2`

## Pack (verified)

```xml
<bob_configuration>
    <processors><processor>Pack</processor></processors>
    <directories><directory>&lt;working>/</directory></directories>
    <global_rules/>
    <retail>1</retail>
    <silent>1</silent>
    <scan_perforce>0</scan_perforce>
    <merge_for_checkin_mode>3</merge_for_checkin_mode>
    <keep_output>1</keep_output>
    <load_asset_graph>0</load_asset_graph>
    <selected_providers>
        <entry>&lt;retail>/data/house.pack</entry>
    </selected_providers>
    <selected_consumers/>
</bob_configuration>
```

Needs a `[Pack]` rules.bob covering the files (`PackFile = <retail>/data/house.pack`). `bob_run.py run --processor Pack --directory raw:... --retail --provider "<retail>/data/house.pack" --temp-rules "<kit>\working_data\RigidModels\Buildings\house=pack_rules.txt"`. (`--directory "<working>/"` is `working:/`.)

CA's tile example, `assembly_kit_battle_tilemap\binaries\BOB\custom_tile_processing_configuration.xml`: same, with `<scan_perforce>1</scan_perforce>` and provider `<retail>/data/osgiliath_test.pack`; its working folder `working_data\terrain\battles\osgiliath_test\rules.bob` is:

```
[Pack]
	BasePath = /
	PackFile = <retail>/data/osgiliath_test.pack
	PackType = mod
```

## Cs2: skeleton, unit part, animation clip, vegetation model (verified)

```xml
<bob_configuration>
    <processors><processor>Cs2</processor></processors>
    <directories><directory>&lt;raw>/animations/skeletons/</directory></directories>
    <global_rules/>
    <retail>0</retail>
    <silent>1</silent>
    <scan_perforce>0</scan_perforce>
    <merge_for_checkin_mode>3</merge_for_checkin_mode>
    <keep_output>1</keep_output>
    <load_asset_graph>0</load_asset_graph>
    <selected_providers/>
    <selected_consumers>
        <entry>&lt;raw>/animations/skeletons/rome_man_game.cs2</entry>
    </selected_consumers>
</bob_configuration>
```

All files of one run must share the export folder named in `<directories>`.

## Texture (verified)

Same as Cs2 with `<processor>Texture</processor>`, one `<directory>` per raw folder and the `.tga` files as consumers; each folder needs a `[+Texture] TargetPath = ...` rules.bob (CRLF).

## Database export, localisation (Terry, from `binaries_terry\BOB\export_changes_from_database_editor_configuration.xml`)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<bob_configuration>
<processors><processor>Database Export</processor><processor>Localisation</processor></processors>
<directories/>
<global_rules/>
<retail>0</retail>
<silent>1</silent>
<connect_db>0</connect_db>
<merge_for_checkin_mode>2</merge_for_checkin_mode>
<selected_files>
<entry>&lt;working&gt;/db/campaigns_tables/campaigns</entry>
<entry>&lt;raw&gt;/EmpireDesignData/campaigns.xml</entry>
</selected_files>
</bob_configuration>
```

Pairs of `<working>/db/<table>_tables/<table>` and `<raw>/EmpireDesignData/<table>.xml`. Unverified from the CLI.

## Terrain, Tile, Vegetation, Battle, Campaign (unverified)

Start from the Cs2 shape with `<processor>Terrain</processor>` and a map folder as directory/consumer, e.g.:

```
python bob_run.py run --kit <battle kit> --processor Terrain --directory raw:/terrain/battles/<map>/ \
       --consumer raw:/terrain/battles/<map>/ --dry-run
```

then run it on a **scratch kit** and read `bob.log` for "`Terrain / Tilemap`", "`Terrain / Heights & Normals`", "`Terrain / Terry file`" actions. Record what worked in `SKILL.md`.
