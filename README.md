Travis [![Build Status](https://travis-ci.org/Squareys/Blender-OpenGEX.svg?branch=master)](https://travis-ci.org/Squareys/Blender-OpenGEX)
# Blender-OpenGEX
"Inofficial OpenGEX Exporter" for Blender 2.7x, based on the original exporter code by Eric Lengyel (can be found at http://opengex.org/).

# How to install

Install instructions for all operating systems:
 1. Download the latest release as a .zip from ["releases"](https://github.com/Squareys/Blender-OpenGEX/releases).
 2. Open Blender and under `File > User Preferences... > Addons` select `Install from File...` and locate the zip file.
 Finally click `Install from File..` to close the file browser.
 3. Search for "OpenGEX" and enable the addon.

# Differences from the original

* Support for exporting linked objects and linked groups
* Faster geometry export, but: \*
  * No support for morphing
  * No support for vertex skin weights
* Support for exporting object game physics as Extensions [=> documentation](https://github.com/Squareys/Blender-OpenGEX/wiki/PhysicsMaterial-Extension)
* Support for exporting custom properties as Extensions [=> documentation](https://github.com/Squareys/Blender-OpenGEX/wiki/Property-Extension)
* Support for exporting the worlds ambient color and material ambient factor [=> documentation](https://github.com/Squareys/Blender-OpenGEX/wiki/Ambient-Colors)
* Option for rounding floating point number to n decimal places
* Option to export only the first material slot of each object

Bleeding-edge (on master, but not released):
* Ability to specify prefix for exported texture paths
* Image texture export
* Export OpenGEX in an compressed text format (without whitespaces)

\* Some of the broken features may be implemented in the future if I start needing them.

# Version Semantics

OpenGEX Exporter Addon versions are built up as:

`<OpenGEX specification version>.<1 digit for OpenGEX Exporter Addon version>`

# License

```
Copyright © 2015, 2016 Jonathan Hale
Copyright © 2015 Terathon Software LLC
Copyright © 2015 Nicolas Wehrle

This software is licensed under the Creative Commons
Attribution-ShareAlike 3.0 Unported License:

http://creativecommons.org/licenses/by-sa/3.0/deed.en_US

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR
PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE
FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
DEALINGS IN THE SOFTWARE.
```
