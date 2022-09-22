import json
from itertools import chain
from pathlib import Path
import uuid
import bpy
import sys
from blenderset.assets import AssetGenerator

assets = AssetGenerator(None)
root = assets.root / "Character_Creator_v3.41" / "Animations" / "Avatar"
metadata_dir = assets.metadata_dir
if (metadata_dir / "animations_metadata.json").exists():
    pose_animations = json.load(open(metadata_dir / "animations_metadata.json"))
else:
    pose_animations = {}

for avatar in root.glob("*"):
    for fn in chain(avatar.glob("*.fbx"), avatar.glob("*.Fbx")):
        bpy.ops.wm.open_mainfile(filepath="blank.blend")
        bpy.ops.cc3.importer(filepath=str(fn), param="IMPORT_QUALITY")
        anim_names = list(bpy.data.actions.keys())
        for name in anim_names:
            key = "_".join([avatar.name, fn.name.split(".")[0], name])
            ofn = key + ".blend"
            for ch in "/|\\":
                ofn = ofn.replace(ch, "_")
            ofn = root.parent / "Blender" / ofn
            ofn.parent.mkdir(parents=True, exist_ok=True)

            if key not in pose_animations:
                print("Importing", key)
                anim = bpy.data.actions[name]
                anim.name = str(uuid.uuid1())
                bpy.data.libraries.write(str(ofn), {anim})

                start, stop = anim.frame_range
                entry = {
                    "name": anim.name,
                    "file": ofn.name,
                    "avatar": avatar.name,
                    "tags": [],
                    "length": stop - start,
                }
                if name.endswith("_M"):
                    entry["gender"] = "male"
                elif name.endswith("_F"):
                    entry["gender"] = "female"
                if "Seat" not in name and "Floor" not in name and "Leaning" not in name:
                    entry["tags"].append("Standing")
                if "Leaning" in name:
                    entry["tags"].append("Leaning")
                pose_animations[key] = entry

                with open(metadata_dir / "animations_metadata.json", "w") as fd:
                    json.dump(pose_animations, fd, indent=4)
