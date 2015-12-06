# Blender-OpenGEX
"Inofficial" OpenGEX Import/Export for Blender 2.7x, based on the original exporter code by Eric Lengyel (can be found at http://opengex.org/).

# How to install

Install instructions for all operating systems:
 1. Download the latest release as a .zip from "releases".
 2. Open Blender and under `File > User Preferences... > Addons` select `Install from File...` and locate the zip file.
 Finally click `Install from File..` to close the file browser.
 3. Search for "OpenGEX" and enable the addon.

# Differences from the original

* Support for exporting linked objects and linked groups
* Faster geometry export
  * currently does not quite export smooth surfaces correctly in some cases
  * No support for morphing
  * Armature export untested
* Support for exporting custom properties as Extensions

# License
This software is licensed under the Creative Commons
Attribution-ShareAlike 3.0 Unported License:

http://creativecommons.org/licenses/by-sa/3.0/deed.en_US
