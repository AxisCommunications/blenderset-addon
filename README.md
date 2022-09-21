# Blenderset

Blenderset is tool for creating synthetic training data using blender. It can be used
to create random scenes consisting of a real background image, ontop of which random
humans and vehicles models are rendered with random lighting. In addition to the
rendered images, annotations are generated in form of pixelwise
instance-segmentations and bounding boxes.

## Installation

* Create a root directory and make it cwd: `mkdir blenderset; cd blenderset`
* Clone the repo: `git clone https://github.com/AxisCommunications/blenderset-addon.git`
* Create asset and metdata directories: `mkdir blenderset-assets blenderset-metadata`
* Install system-wide dependencies: `sudo apt install libopenexr-dev`
* Create and initialize virtual environment: `. ./init_env.sh`
* Install dependencies: `make sync_env`.
  Addons that crash will simply not show up in the GUI.
* Enable the addons by either
   - `make run-enable_addons` (will fail before dependencies have been installed), or
   - using the blender GUI
      1. Use the menu: Edit/Preferences
      2. Find Add-ons in sidebar of popup
      3. Find the addon in e.g. using the search function
      4. Check the check-box in front of the addon to enable it


## Assets and Metadata

To use blender set custom assets and corresponding metadata are needed.
Depending on what kind of scenes are to be rendered, different types of assets
will be needed. By default, blenderset will look for assets in the
../blenderset-assets and ../blenderset-metadata directories. Some example metadata
for both free and paied asets are availible in example-assets and example-metadata,
which can either be copied to the above dirs or a config file can be placed in
`~/.config/blenderset/config.json` specifying which diretories to use. For example:

```json
{
    "metadata_dir": "/usr/local/src/blenderset/example-metadata",
    "assets_dir": "/usr/local/src/blenderset/example-assets"
}
```


### Real Backgrounds

Each background consist of:

    * A camera image of an empty scene
    * A camera model
    * A region of interest (ROI) defining where to place pedestrians
    * A set of tags used to filter out which backgrounds to use

These are specified in the `images_metadata.json` file. There is a helper script
`poly_roi.py` that can be used to create the ROI coordinates:
`python poly_roi.py --file image.jpg --roi-file roi.json`, which then needs to be
copied into `images_metadata.json`.


### Synthetic Backgrounds

Instead of using a real image as background, the ground plane can be textured with a
 downloaded material. Material can be found at for example
https://polyhaven.com/textures. Select blender as format and unpack the downloaded
zip-file in `example-assets/polyhaven`.


### HDRI Lighting

To light the scene HDRIs are used. They can be found at for example
https://polyhaven.com/hdris. Select format hdr and place the downloaded files in
`example-assets/skys`.


### Vehicles

To add vehicles to the scene, the comercial
[Transportation Addon](https://blendermarket.com/products/transportation) from
blender marked can be used. Install the addon manually and copy
`~/.config/blender/3.2/scripts/addons/Tranportation/data` to
`example-assets/Tranportation_data`.


### Humans

3D models of humans can be created in
[Reallusion Character Creator](https://www.reallusion.com/character-creator/)
or downloaded from [Actorcore](https://actorcore.reallusion.com/). Export them into
blender format and place them in
`example-assets/Character_Creator_v3.41/BlenderCharacters256`. Also, poses are needed
they can be extracted from animations downloaded from for example [Actorcore](https://actorcore.reallusion.com/). Export them as `.fbx` and place them in
`example-assets/Character_Creator_v3.41/Animations/Avatar/<avatar>/`, where
`<avatar>` is the name of the base avatar they are exported for, typically
`CC3_Base_Plus` or `CC_Standard`. Then import them using the `import_animation.py`,
which can be called by `make import_animations`.
This will update the metadata in `animations_metadata.json` and convert the `.fbx`
files into `.blend` files.
