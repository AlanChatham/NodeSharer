"""
MIT License

Copyright (c) 2021 Node Sharer Devs

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

bl_info = {
    "name": "Node Sharer",
    "author": "NodeSharer Devs, Alan Chatham",
    "version": (0, 3, 0),
    "blender": (2, 90, 0),
    "location": "Node Editor Toolbar",
    "description": "Share node setups as text strings.",
    "warning": "Blender can crash when pasting node groups. Save your work before pasting.",
    "category": "Node",
    "tracker_url": "https://github.com/wildiness/NodeSharer#supporthelp-and-bug-reports",
}
# (In your __init__.py)
# When bpy is already in local, we know this is not the initial import...
if "bpy" in locals():
    # ...so we need to reload our submodule(s) using importlib
    import importlib
    if "nodesharer" in locals():
        importlib.reload(nodesharer)
        print("hot reload")
else:
    print("bpy was not in locals")

import importlib

def register():
    from . import nodesharer
    importlib.reload(nodesharer)
    nodesharer.register()


def unregister():
    from . import nodesharer
    nodesharer.unregister()
