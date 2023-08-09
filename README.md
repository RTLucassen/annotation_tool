# Annotation Tool
A simple graphical user interface (GUI) for bitmap image annotation in Python using 
[Tkinter](https://docs.python.org/3/library/tkinter.html).

## Installing the Annotation Tool
The annotation tool can be installed from GitHub:
```console
$ pip install git+https://github.com/RTLucassen/annotation_tool
```

## Example
A minimal example of how the annotation tool can be used.
```
from annotation_tool import AnnotationTool

# define the image paths and layer names / classes
paths = ['image1.png', 'image2.png']
layer_names = ['foreground', 'background']

# start annotating
AnnotationTool(image_paths=paths, layer_names=layer_names)     
```

## Buttons and Keyboard Shortcuts
The table below lists the buttons of the annotation tool with the corresponding symbol, keyboard shortcut, and explanation of the action.
|&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Button&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|Symbol|Keyboard Shortcut|Explanation of Action|
|:---:|:---:|:---:|---|
|**Inspection mode**|<img src="src/annotation_tool/icons/magnifying_glass_icon.png" height="30%" width="30%">|`<d>`|Switch to Inspection mode (the annotation cannot be modified).|
|**Drawing mode**|<img src="src/annotation_tool/icons/brush_icon.png" height="30%" width="30%">|`<d>`|Switch to Drawing mode.|
|**Reset view**|<img src="src/annotation_tool/icons/compas_icon.png" height="30%" width="30%">|`<r>`|Reset the zoom and position to display the image centered and completely in frame.|
|**Hide annotation**|<img src="src/annotation_tool/icons/visible_icon.png" height="30%" width="30%">|`<v>`|Hide/unhide the annotation (the annotation cannot be modified while hidden).|
|**Next image**|<img src="src/annotation_tool/icons/right_arrow_icon.png" height="30%" width="30%">|`<RightArrow>`|Continue to the next image (if available).|
|**Previous image**|<img src="src/annotation_tool/icons/left_arrow_icon.png" height="30%" width="30%">|`<LeftArrow>`|Go back to the previous image (if available).|
|**Add layer**|<img src="src/annotation_tool/icons/plus_icon.png" height="30%" width="30%">|`<n>`|Add a new annotation layer (if this is enabled).|
|**Fill encircled**|<img src="src/annotation_tool/icons/circle_empty_icon.png" height="30%" width="30%">|`<f>`|Enable/disable automatically filling the encircled region if the end of the drawn line connects to the start.|
|**Threshold image**|<img src="src/annotation_tool/icons/threshold_icon.png" height="30%" width="30%">|`<t>`|Annotate all pixels of the image (in grayscale) that subceed the threshold value.|
|**Invert annotation**|<img src="src/annotation_tool/icons/invert_color_icon.png" height="30%" width="30%">|`<i>`|Invert the annotation (foreground becomes background and background becomes foreground).|
|**Undo action**|<img src="src/annotation_tool/icons/undo_icon.png" height="30%" width="30%">|`<z>`|Undo the last action. By default, the last 20 actions can be reverted.|
|**Clear annotation**|<img src="src/annotation_tool/icons/delete_icon.png" height="30%" width="30%">|`<c>`|Clear the annotation. For layers added using the '+' button, if no annotation is present, remove the layer.|
|**Save annotation**|<img src="src/annotation_tool/icons/save_icon.png" height="30%" width="30%">|`<s>`|Save the annotation as one multi-channel image or one image per layer depending on the configuration.|
|**Open settings**|<img src="src/annotation_tool/icons/settings_icon.png" height="30%" width="30%">| |Open the settings window to adjust the threshold value, as well as the foreground and background color and opacity.|

## Actions and Controls
The table below lists the actions with the corresponding controls that the user can perform, depending on the mode that is active.
|&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Action&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;| Inspection mode (<img src="src/annotation_tool/icons/magnifying_glass_icon.png" height="4%" width="4%">) controls|Drawing mode (<img src="src/annotation_tool/icons/brush_icon.png" height="4%" width="4%">) controls|
|:---:|:---:|:---:|
|**Pan around image**| `Left mouse click and move` | `<SPACE>`+`Left mouse click and move` |
|**Zoom in/out of image**| `Scroll up/down` | `Scroll up/down` |
|**Draw annotation**|  | `Left mouse click and move` |
|**Erase annotation**|  | `Right mouse click and move` |
|**Show brush/eraser size**|  | `<b>` |
|**Adjust brush/eraser size**|  | `<b>`+`Scroll up/down` |

## Notes
- Adjusting the brush/eraser size using `<b>`+`Scroll up/down` or moving the cursor while 
`<b>` is pressed occasionally results in thin, black, horizontal or vertical lines coming 
off of the circular size indicator. This is only a visual bug that does not affect
the behaviour of the annotation tool. The lines automatically disappear after panning the 
image or drawing/erasing near the lines.
- At the moment, the tool becomes slower after annotating for a while.
This is most noticable when panning the image. For now, restarting the tool resolves the problem.
- On Linux, *tkinter* is often by default not installed with Python. To install 
*tkinter* with Python on Debian-derived distributions like Ubuntu, use `apt-get install python3-tk`.
Moreover, because *tkinter* is incompatable with the external fonts on Linux, one of the system fonts is used.
- The tool has only been tested on Windows and Linux machines.
- The tool was designed for and has only been tested on screens in landscape orientation.
