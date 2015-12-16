# Blender-OpenGEX
"Inofficial OpenGEX Exporter" for Blender 2.7x, based on the original exporter code by Eric Lengyel (can be found at http://opengex.org/).

# How to install

Install instructions for all operating systems:
 1. Download the latest release as a .zip from "releases".
 2. Open Blender and under `File > User Preferences... > Addons` select `Install from File...` and locate the zip file.
 Finally click `Install from File..` to close the file browser.
 3. Search for "OpenGEX" and enable the addon.

# Differences from the original

* Support for exporting linked objects and linked groups
* Faster geometry export, but:
  * No support for morphing
  * No support for vertex skin weights
* Support for exporting custom properties as Extensions

Properties can be exported as:
```
	Extension (applic = "Blender", type = "Property")
	{
		string {"a_string"}
		string {"Hello World"}
	}
	Extension (applic = "Blender", type = "Property")
	{
		string {"a_int"}
		int32 {42}
	}
	Extension (applic = "Blender", type = "Property")
	{
		string {"a_float"}
		float {3.14}
	}
```

Some of the broken features may be implemented if I start needing them.

# License

```
Copyright 2015, Terathon Software LLC
Copyright 2015, Jonathan Hale
Copyright 2015, Nicolas Wehrle

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
