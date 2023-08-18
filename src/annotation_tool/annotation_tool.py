#    Copyright 2022 Ruben T Lucassen, UMC Utrecht, The Netherlands 
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.
#
#    ___________________________________________________________________________
#
#    Part of the code is based on an image viewer implemention by foobar167:
#    https://github.com/foobar167/junkyard/blob/master/zoom_advanced3.py
#   
#    MIT License
#   
#    Copyright (c) 2017 foobar167
#   
#    Permission is hereby granted, free of charge, to any person obtaining a copy
#    of this software and associated documentation files (the "Software"), to deal
#    in the Software without restriction, including without limitation the rights
#    to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#    copies of the Software, and to permit persons to whom the Software is
#    furnished to do so, subject to the following conditions:
#   
#    The above copyright notice and this permission notice shall be included in all
#    copies or substantial portions of the Software.
#   
#    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#    OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
#    SOFTWARE.
#
#    ___________________________________________________________________________
#
#    All button icons, except for the icon on the thresholding button, are from 
#    the Material Symbols set: https://fonts.google.com/icons
#
#    Copyright 2016 Google LLC
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

"""
Image annotation tool


Inspection controls (<d>)
_________________________________________________
Left mouse button:                 panning around
Scroll wheel:                  zooming in and out
<r>:                               reset the view
<v>:                       hide/unhide annotation
<LeftArrow>:                 go to previous image
<RightArrow>:                    go to next image
<n>:                       add layer (if enabled)
<s>:                             save annotations



Drawing controls (<d>)
_________________________________________________
Left mouse button:                        drawing
Right mouse button:                       erasing
Scroll wheel:                  zooming in and out
<b>:                           showing brush size
<b> + Scroll wheel:           changing brush size
<SPACE> + Left mouse button:       panning around
<r>:                               reset the view
<v>:                       hide/unhide annotation
<LeftArrow>:                 go to previous image
<RightArrow>:                    go to next image
<n>:                       add layer (if enabled)
<f>:                             change auto fill
<t>:                              threshold image
<i>:                            invert annotation
<z>:                              undo annotation
<c>:             clear annotation or remove layer
<s>:                             save annotations 
"""

import ctypes
import os
import platform
import tkinter
import tkinter as tk
from math import ceil, floor
from pathlib import Path
from tkinter import ttk
from typing import Optional, Union

import numpy as np
import pyglet
import SimpleITK as sitk
import sv_ttk 
from PIL import Image, ImageChops, ImageDraw, ImageTk
from scipy.ndimage import convolve

from ._utils import Buffer, LayerTracker
from ._utils import create_color_matrix, get_hex_color, save_image
from . import fonts
from . import icons


# configure dpi awareness on Windows
if platform.system() == 'Windows':
    try: # >= win 8.1
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except: # win 8.0 or less
        ctypes.windll.user32.SetProcessDPIAware()


FONTS = [
    'DMSans-Regular.ttf',
    'DMSans-Bold.ttf',
]

ICONS = {
    'inspect_button': 'magnifying_glass_icon.png',
    'draw_button': 'brush_icon.png',
    'reset_button': 'compas_icon.png',
    'hide_button': 'visible_icon.png',
    'unhide_button': 'invisible_icon.png',
    'previous_button': 'left_arrow_icon.png',
    'next_button': 'right_arrow_icon.png',
    'fill_on_button': 'circle_filled_icon.png',
    'fill_off_button': 'circle_empty_icon.png',
    'threshold_button': 'threshold_icon.png',
    'invert_button': 'invert_color_icon.png',
    'undo_button': 'undo_icon.png',
    'clear_button': 'delete_icon.png',
    'save_button': 'save_icon.png',
    'settings_button': 'settings_icon.png'
}

# change setting
pyglet.options['win32_gdi_font'] = True


class CanvasImage:
    """ 
    Display image and facilitate annotation. 
    
    Attributes:
        parent:  Parent instance.
        container:  Container widget for canvas.
    """
    # define class attributes
    __gain = 1  # panning speed
    __wobble = False  # trades off wobble and stutter when panning
    __zoom_factor = 1.1  # zoom magnitude
    __min_zoom = 0.5  # minimum times zoomed in
    __zoom_limit = 25  # zoom limit (not equivalent to number of times zoomed in)
    __interpolation = Image.NEAREST  # interpolation method 
    __initial_line_width = 45  # px
    __line_width_change = 10  # px
    __min_line_width = 5  # px
    __circle_width = 2  # px
    __N_coords = 10  # number of interpolated coords
    __maximum_buffer = 20  # annotations

    def __init__(self, parent: tkinter.Tk) -> None:
        """ 
        Initialize the canvas with the image for annotation.
        
        Args:
            parent:  Parent instance.
        """      
        # initialize instance attribute
        self.parent = parent

        # initialize container widget
        self.container = tk.Frame(self.parent)
        
        # initialize buffer object and empty dictionary to collect annotations
        self.__buffer = Buffer(self.__maximum_buffer)
        self.__annotations = {}

        # initialize instance attributes to track states
        self.__image_loaded = False
        self.__space = False
        self.__space_disabled = False
        self.__brush = False
        self.__old_x = None
        self.__old_y = None
        self.__line = []
        self.__coords = []
        self.__line_width = self.__initial_line_width
        self.__selected_layer = self.parent.layers[0]
        self.__circle = None
        self.__container = None
        self.__rotated = False
        self.__tool = None

        # initialize the canvas widget
        self.__canvas = tk.Canvas(
            self.container, 
            highlightthickness=0, 
            width=self.parent.canvas_dimensions[0], 
            height=self.parent.canvas_dimensions[1],
        )
        self.__canvas.grid(row=0, column=0, sticky='nswe')
        
        # bind events to methods that affect the canvas
        self.__canvas.bind('<ButtonPress-1>', self.__lb_press)
        self.__canvas.bind('<ButtonPress-3>', self.__rb_press)
        self.__canvas.bind('<Motion>', self.__motion)     
        self.__canvas.bind('<B1-Motion>', self.__lb_motion)
        self.__canvas.bind('<B3-Motion>', self.__rb_motion)
        self.__canvas.bind('<ButtonRelease-1>', lambda event: self.__lift('white'))
        self.__canvas.bind('<ButtonRelease-3>', lambda event: self.__lift('black'))
        self.__canvas.bind('<MouseWheel>', self.__wheel)
        self.__canvas.bind('<Button-5>', self.__wheel)
        self.__canvas.bind('<Button-4>', self.__wheel)
        self.__canvas.bind('<Enter>', lambda event: self.__canvas.focus_set())
        self.__canvas.bind('<Leave>', lambda event: self.__remove_circle())
        self.__canvas.bind('<KeyPress>', self.__keypress)
        self.__canvas.bind('<KeyRelease>', self.__keyrelease)       
        self.__canvas.bind('<Configure>', lambda event: self.__show_image())

        # focus on the canvas
        self.__canvas.focus_set()


    def __lb_press(self, event: tkinter.Event) -> None:
        """
        Record the location of the canvas if the image is zoomed in,
        and when in drawing mode, only if the spacebar is pressed as well.
        """
        # check if an image has been loaded
        if not self.__image_loaded: return

        # if the canvas is in drawing mode and the spacebar is not pressed, 
        # disable the spacebar and record the location for the start of line
        if self.parent.drawing_mode and not self.__space:
            if self.__tool is None and not self.parent.hide_annotation:
                self.__space_disabled = True
                self.__tool = 'brush'
                self.__paint(event, self.parent.foreground_color)
        # if not in drawing mode and/or if the spacebar is pressed, 
        # record the location (when zoomed in)
        else:
            self.__canvas.scan_mark(event.x, event.y)
 

    def __rb_press(self, event: tkinter.Event) -> None:
        """ 
        Disable the spacebar when in drawing mode if it is not pressed.
        """
        # check if an image has been loaded
        if not self.__image_loaded: return

        # if the canvas is in drawing mode and the spacebar is not pressed, 
        # disable the spacebar and record the location for the start of line
        if (self.parent.drawing_mode and self.__tool is None and 
            not self.__space and not self.parent.hide_annotation):
            self.__space_disabled = True
            self.__tool = 'eraser'
            self.__paint(event, self.parent.background_color)


    def __lb_motion(self, event: tkinter.Event) -> None:
        """
        Move the canvas, or when in drawing mode, add to the line in progress 
        (drawing).
        """
        # check if an image has been loaded
        if not self.__image_loaded: return

        # check if both the left and right button are pressed (state == 1280)
        if event.state == 1280:
            self.__rb_motion(event)

        # if in drawing mode and space is pressed, move and update the canvas.
        # if space is not pressed, add to the line in progress (drawing)
        if self.parent.drawing_mode:
            if self.__space and not self.__space_disabled:
                self.__canvas.scan_dragto(event.x, event.y, gain=self.__gain)
                self.__show_image()
            elif (not self.parent.hide_annotation and self.__tool == 'brush'):
                self.__paint(event, self.parent.foreground_color)
        # if not in drawing mode, move and update the canvas
        else:
            self.__canvas.scan_dragto(event.x, event.y, gain=self.__gain)
            self.__show_image()


    def __rb_motion(self, event: tkinter.Event) -> None:
        """
        If in drawing mode, add to the line in progress (erasing).
        """
        # check if an image has been loaded
        if not self.__image_loaded: return
        
        # if drawing is possible, add to the line in progress (erasing)
        if (self.parent.drawing_mode and self.__tool == 'eraser' and 
            self.__space_disabled and not self.parent.hide_annotation):
            self.__paint(event, self.parent.background_color)


    def __motion(self, event: tkinter.Event) -> None:
        """
        Update the circle that indicates the brush size if in drawing mode.
        """
        # check if an image has been loaded
        if not self.__image_loaded: return

        if self.parent.drawing_mode:
            self.__update_circle(event)


    def __wheel(self, event: tkinter.Event) -> None:
        """
        Zoom in and out, or change the brush size when scrolling.
        """
        # check if an image has been loaded
        if not self.__image_loaded: return

        # scrolling is disabled during drawing
        if self.__old_x is None and self.__old_y is None:
            # if the control key is pressed and when in drawing mode, 
            # increase or decrease the brush size
            if self.__brush:
                if self.parent.drawing_mode:
                    if event.num == 5 or event.delta == -120:  # scroll down
                        self.__line_width = max(
                            self.__line_width - self.__line_width_change, 
                            self.__min_line_width,
                        )
                    elif event.num == 4 or event.delta == 120:  # scroll up
                        self.__line_width += self.__line_width_change
                    self.__update_circle(event)
            else:
                # get coordinates of the event on the canvas
                x = self.__canvas.canvasx(event.x)  
                y = self.__canvas.canvasy(event.y)
                
                # check if the scrolling was inside the window
                bbox = self.__canvas.coords(self.__container)
                if not (bbox[0] < x < bbox[2] and bbox[1] < y < bbox[3]): return
                
                # act on Linux (event.num) or Windows (event.delta) wheel event
                if event.num == 5 or event.delta == -120:  # scroll down
                    if self.__imscale == self.__imscale_range[0]: return
                    new_imscale = max(
                        self.__imscale_range[0], 
                        self.__imscale/self.__zoom_factor,
                    )
                elif event.num == 4 or event.delta == 120:  # scroll up
                    if self.__imscale == self.__imscale_range[1]: return
                    new_imscale = min(
                        self.__imscale_range[1], 
                        self.__imscale*self.__zoom_factor,
                    )
                else:
                    return

                # calculate the factor and update the imscale
                factor = new_imscale/self.__imscale
                self.__imscale = new_imscale

                # rescale all objects in the canvas and show the image
                self.__canvas.scale('all', x, y, factor, factor) 
                self.__show_image()
        

    def __keypress(self, event: tkinter.Event) -> None:
        """
        Update state attributes when the spacebar or control key is pressed.
        """
        # check if both <SPACE> and the left mouse button are pressed
        if event.state == 264: return
        # check if an image has been loaded
        if not self.__image_loaded: return

        if event.keysym_num == 98 and self.__brush == False:  # <b>
            self.__brush = True
            self.__space = False  # <b> overrules space 
            if self.parent.drawing_mode:
                self.__create_circle(event)
        elif event.keysym_num == 32 and self.__space == False:  # <SPACE>
            self.__space = True
            self.__remove_circle()


    def __keyrelease(self, event: tkinter.Event) -> None:
        """
        Update state attributes when the spacebar or control key is released.
        """
        # check if an image has been loaded
        if not self.__image_loaded:
            return

        if event.keysym_num == 98 and self.__brush == True:  # <b>
            self.__brush = False
            if self.parent.drawing_mode:
                self.__remove_circle()
        elif event.keysym_num == 32 and self.__space == True:  # <SPACE>
            self.__space = False


    def __show_image(self) -> None:
        """
        Show the image on the canvas.
        """
        # check if an image has been loaded
        if not self.__image_loaded: return

        # get the image area
        box_image = self.__canvas.coords(self.__container) 
        box_image_int = tuple(map(int, box_image))

        # get the visible area of the canvas
        box_canvas = (self.__canvas.canvasx(0), 
                      self.__canvas.canvasy(0),
                      self.__canvas.canvasx(self.__canvas.winfo_width()),
                      self.__canvas.canvasy(self.__canvas.winfo_height()))  

        # Get scroll region box
        box_scroll = [
            min(box_image_int[0], box_canvas[0]), 
            min(box_image_int[1], box_canvas[1]),
            max(box_image_int[2], box_canvas[2]), 
            max(box_image_int[3], box_canvas[3]),
        ]
        
        # Horizontal part of the image is in the visible area
        if box_scroll[0] == box_canvas[0] and box_scroll[2] == box_canvas[2]:
            box_scroll[0] = box_image_int[0]
            box_scroll[2] = box_image_int[2]
        # Vertical part of the image is in the visible area
        if box_scroll[1] == box_canvas[1] and box_scroll[3] == box_canvas[3]:
            box_scroll[1] = box_image_int[1]
            box_scroll[3] = box_image_int[3]

        # set the scroll region
        self.__canvas.configure(scrollregion=tuple(map(int, box_scroll)))

        # get coordinates (x1,y1,x2,y2) of the image region
        x1 = max(box_canvas[0]-box_image[0], 0)  
        y1 = max(box_canvas[1]-box_image[1], 0)
        x2 = min(box_canvas[2], box_image[2])-box_image[0]
        y2 = min(box_canvas[3], box_image[3])-box_image[1]

        # crop the area of the image that will be displayed
        # - the first approach introduces wobble but has less stutter zoomed in
        # - the second approach shows no wobble but has more stutter zoomed in
        if self.__wobble:
            self.__crop_size = (
                int(x1 / self.__imscale), 
                int(y1 / self.__imscale),                  
                int(x2 / self.__imscale), 
                int(y2 / self.__imscale),
            )
        else:
            self.__crop_size = (
                int(x1 / self.__imscale),
                int(y1 / self.__imscale),
                int(x1 / self.__imscale)+int((x2-x1) / self.__imscale),
                int(y1 / self.__imscale)+int((y2-y1) / self.__imscale),
            )
        image = self.__image.crop(self.__crop_size)
                    
        # prepare the image and add it to the canvas
        resized_image = image.resize((int(x2-x1), int(y2-y1)), self.__interpolation)
        imagetk = ImageTk.PhotoImage(resized_image)
        imageid = self.__canvas.create_image(
            max(box_canvas[0], box_image_int[0]),
            max(box_canvas[1], box_image_int[1]),
            anchor='nw', 
            image=imagetk,
        )
        # set image as background and keep a reference 
        # to prevent garbage-collection
        self.__canvas.lower(imageid)  
        self.__canvas.imagetk = imagetk  


    def __create_circle(self, event: tkinter.Event) -> None:
        """
        Create the circle that indicates the brush size.
        """
        # check if an image has been loaded
        if not self.__image_loaded: return

        # create and show circle    
        x = self.__canvas.canvasx(event.x)
        y = self.__canvas.canvasy(event.y)

        self.__circle = self.__canvas.create_oval(
            x+self.__line_width/2, 
            y+self.__line_width/2, 
            x-self.__line_width/2,            
            y-self.__line_width/2, 
            width=self.__circle_width, 
            outline="black",
        )


    def __remove_circle(self) -> None:
        """
        Remove the circle that indicates the brush size to make it invisible.
        """
        # check if an image has been loaded
        if not self.__image_loaded: return

        self.__canvas.delete(self.__circle)
    

    def __update_circle(self, event: tkinter.Event) -> None:
        """
        Remove the old circle and create a new one for showing the brush size.      
        """
        # check if an image has been loaded
        if not self.__image_loaded: return

        if self.__brush and not self.__space:
            self.__remove_circle()
            self.__create_circle(event)


    def __draw_line(self, color: str) -> None:
        """
        Add the drawn line to the annotation image, 
        accounting for the image scale and field of view.

        Args:
            color:  Name of color (either 'black' or 'white').
        """
        # check if an image has been loaded
        if not self.__image_loaded: return

        # get the annotation and corresponding draw variable
        draw, annotation = self.__annotations[self.__selected_layer]

        # add previous annotation to buffer
        self.__buffer.add(annotation.copy(), self.__selected_layer)

        # find the position of the top left corner of the image in the canvas
        box_image = self.__canvas.coords(self.__container)
        top_left = (
            -int(self.__canvas.canvasx(0)-box_image[0]),  
            -int(self.__canvas.canvasy(0)-box_image[1]),
        )
        bottom_right = (
            top_left[0]+(box_image[2]-box_image[0]),  
            top_left[1]+(box_image[3]-box_image[1]),
        )
        # find the relative top left and bottom right position
        relative_top_left = (
            max(0, top_left[0]/self.parent.canvas_dimensions[0]),
            max(0, top_left[1]/self.parent.canvas_dimensions[1]),
        )
        relative_bottom_right = (
            min(1, bottom_right[0]/self.parent.canvas_dimensions[0]),
            min(1, bottom_right[1]/self.parent.canvas_dimensions[1]),
        )
        # calculate relative height and width
        relative_width = relative_bottom_right[0]-relative_top_left[0]
        relative_height = relative_bottom_right[1]-relative_top_left[1]
        # calculate height and width of image in pixels
        pixels_width = self.__crop_size[2]-self.__crop_size[0]
        pixels_height = self.__crop_size[3]-self.__crop_size[1]

        # calculate the line width
        width = int(self.__line_width/self.__imscale)

        converted_coords = []
        for coord in self.__coords:
            # normalize with respect to window
            normalized_coord = (
                coord[0]/self.parent.canvas_dimensions[0],
                coord[1]/self.parent.canvas_dimensions[1],
            )
            # normalize with respect to image in canvas
            relative_coord = (
                (normalized_coord[0]-relative_top_left[0])/relative_width,
                (normalized_coord[1]-relative_top_left[1])/relative_height,
            )
            # convert to pixels
            converted_coords.append(
                (self.__crop_size[0]+relative_coord[0]*pixels_width,
                self.__crop_size[1]+relative_coord[1]*pixels_height),
            )
        self.__coords = converted_coords

        # if a single point was clicked, duplicate the point
        if len(self.__coords) == 1:
            self.__coords = self.__coords*2

        # fill the region if the location of the first and last point 
        # are close enough and auto fill is active
        if self.parent.auto_fill and len(self.__coords) > 1:
            # calculate the distance between the first and last coordinate
            coords = zip(self.__coords[0], self.__coords[-1])
            distance = sum((a-b)**2 for a,b in coords)**0.5
            # check if the first and last drawn point touch 
            # (distance is less than the circle radius)
            if distance < max(1, width):
                # fill the inside of the drawn region
                draw.polygon(self.__coords, fill=color)
                # add additional points between the first and last coordinate
                connecting_coords = []
                N = self.__N_coords
                for i in range(N+1):
                    connecting_coords.append(
                        (self.__coords[0][0]*(i/N) + self.__coords[-1][0]*((N-i)/N),
                        self.__coords[0][1]*(i/N) + self.__coords[-1][1]*((N-i)/N)),
                    )
                self.__coords += connecting_coords

        # draw the line and add circles to the coordinates to address artifacts     
        draw.line(self.__coords, fill=color, width=width, joint='curve')
        for point in self.__coords:
            draw.arc(
                [(point[0]-(width/2), point[1]-(width/2)), 
                (point[0]+(width/2), point[1]+(width/2))], 
                start=0, 
                end=361, 
                fill=color, 
                width=width,
            )

        # reset the coordinates that were stored to plot the line
        self.__coords = []

        # update the annotation
        self.__annotations[self.__selected_layer] = draw, annotation

        # create the image combined with the annotation
        self.__image = ImageChops.composite(
            self.__foreground_color_image, 
            self.__background_color_image, 
            annotation,
        )
        # show the updated annotation on top of the original image        
        self.__show_image()


    def __paint(self, event: tkinter.Event, color: str) -> None:
        """
        Paint a line on the canvas.

        Args:
            color:  Name of color (either 'black' or 'white').
        """
        # check if an image has been loaded
        if not self.__image_loaded: return

        # remove the circle that indicates the brush size
        self.__remove_circle()
        x = self.__canvas.canvasx(event.x)
        y = self.__canvas.canvasy(event.y)

        # if a list with RGB color values is provided, 
        # convert it to hexadecimal notation
        if isinstance(color, list): color = get_hex_color(color)

        # for drawing the first point
        if self.__old_x == None and self.__old_y == None:
            self.__old_x = x
            self.__old_y = y

        # draw the next part of the line segment and add it to a list
        line_segment = self.__canvas.create_line(
            self.__old_x, 
            self.__old_y, 
            x, 
            y,
            width=self.__line_width, 
            fill=color, 
            capstyle=tk.ROUND, 
            smooth=tk.TRUE, 
            splinesteps=36,
        )
        self.__line.append(line_segment)
        
        # also add the new coordinate of the line to a separate list 
        # for drawing on the annotation
        self.__coords.append((event.x, event.y))
        self.__old_x = x
        self.__old_y = y


    def __lift(self, color: str) -> None:
        """
        Lift the brush of the canvas to stop drawing or erasing.
        Add the line to or remove the line from the annotation and 
        delete it from the canvas.

        Args:
            color:  Name of color (either 'black' or 'white').
        """
        # check if an image has been loaded
        if not self.__image_loaded: return

        if ((self.__tool == 'brush' and color == 'white') or
            (self.__tool == 'eraser' and color == 'black')):
            if self.parent.drawing_mode and self.__space_disabled:
                # reset variables
                self.__space_disabled = False    
                self.__old_x = None
                self.__old_y = None

                # redraw the line on the annotation
                self.__draw_line(color)
                self.__tool = None

                # delete the manually drawn line from the canvas
                for l in self.__line:
                    self.__canvas.delete(l)


    def grid(self, **kw) -> None:
        """ 
        Put the CanvasImage widget on the parent widget.
        """
        self.container.grid(**kw)
        # specifying the row and column configuration makes the canvas resizable
        self.container.rowconfigure(0, weight=1)
        self.container.columnconfigure(0, weight=1)


    def pack(self, **kw) -> None:
        """
        Exception: cannot use pack with this widget. 
        """
        message = f'Cannot use place with the widget {self.__class__.__name__}.'
        raise Exception(message)


    def place(self, **kw) -> None:
        """ 
        Exception: cannot use place with this widget 
        """
        message = f'Cannot use place with the widget {self.__class__.__name__}.'
        raise Exception(message)
          

    def load_image(self) -> None:
        """
        Load the image from image_path, optionally load prior annotations
        from the annotation path, and configure the canvas.
        """
        # initialize instance attributes for the image path, the PIL image, 
        # and the image height and width
        index = self.parent.image_index
        self.__image_path = self.parent.image_paths[index]
        self.__original_image = Image.open(self.__image_path) 
        self.__imwidth, self.__imheight = self.__original_image.size
        
        # optionally rotate the image if it is in portrait mode
        if self.__imheight > self.__imwidth and self.parent.rotate_portrait:
            self.__original_image = self.__original_image.transpose(
                Image.Transpose.ROTATE_270,
            )
            self.__imwidth, self.__imheight = self.__imheight, self.__imwidth
            self.__rotated = True
        else:
            self.__rotated = False
        
        # initialize instance attributes for a gray and colored image version 
        self.__original_image_gray = self.__original_image.convert('L')
        self.__original_image_sat = self.__original_image.convert('HSV').split()[1]
        self.__foreground_color_image = self.__original_image.convert(
            'RGB',
            create_color_matrix(
                self.parent.foreground_color, 
                self.parent.foreground_opacity,
            )
        )
        self.__background_color_image = self.__original_image.convert(
            'RGB', 
            create_color_matrix(
                self.parent.background_color, 
                self.parent.background_opacity,
            )
        )
        # load all prior annotations if provided
        self.__annotation_paths = self.parent.annotation_paths[index]
        if self.__annotation_paths is not None:
            # if only a string is provided, add it to a list
            if isinstance(self.__annotation_paths, Path):
                self.__annotation_paths = [self.__annotation_paths]

            # loop over all annotation paths
            prior_annotations = []
            for annotation_path in self.__annotation_paths:
                # load the annotation and store each channel as a PIL image
                annotation = sitk.GetArrayFromImage(
                    sitk.ReadImage(annotation_path),
                )
                # check if there are multiple annotation layers in the image
                annotation_layers = []
                if len(annotation.shape) > 2:
                    for i in range(annotation.shape[0]):
                        annotation_layers.append(
                            Image.fromarray(annotation[i, ...]),
                        )
                else:
                    annotation_layers.append(Image.fromarray(annotation))

                # check if annotations should be rotated to match the image
                for annotation_layer in annotation_layers:                      
                    if self.__rotated:
                        annotation_layer = annotation_layer.transpose(
                            Image.Transpose.ROTATE_270,
                        )
                    prior_annotations.append(annotation_layer)

            # check if all annotation images match the original image in size
            for annotation in prior_annotations:
                if annotation.size != (self.__imwidth, self.__imheight):
                    message = ('A prior annotation does not match'
                               ' the original image in size.')
                    raise ValueError(message)

            message = ('The number of prior annotations and '
                       'annotation layers do not match.')
            # if adding extra annotation layers is disabled, 
            # check if the number of prior_annotations is equal to
            # the number of specified annotation layers
            if not self.parent.add_layers:
                if len(prior_annotations) != len(self.parent.layers):
                    raise ValueError(message)

            # if adding extra annotation layers is enabled, 
            # check if the number of prior_annotations is more or less than
            # the number of specified annotation layers
            else:
                difference = len(prior_annotations)-len(self.parent.layers)
                if difference < 0:
                    raise ValueError(message)
                elif difference > 0:
                    # increase the extra layer counter and get create the name
                    for _ in range(difference):
                        self.parent.layers.add_extra_layer()

            # use the prior annotations instead of creating new annotation images
            for annotation, name in zip(prior_annotations, self.parent.layers):
                self.add_annotation(name, annotation)
            
        # if no prior annotations were provided, create new annotation images
        else:
            for name in self.parent.layers:
                self.add_annotation(name)

        # initialize instance attributes for scaling range 
        canvas_aspect = self.__canvas.winfo_screenwidth()/self.__canvas.winfo_screenheight()
        image_aspect = self.__imwidth/self.__imheight
        if image_aspect > canvas_aspect:        
            self.__imscale_range = [
                self.__canvas.winfo_screenwidth()/self.__imwidth*self.__min_zoom, 
                self.__zoom_limit,
            ]
        else:
            self.__imscale_range = [
                self.__canvas.winfo_screenheight()/self.__imheight*self.__min_zoom, 
                self.__zoom_limit*canvas_aspect,
            ]
        self.__imscale = self.__imscale_range[0]/self.__min_zoom
        
        # create a container for the image
        if self.__container is not None: 
            self.__canvas.delete('image_container')
        self.__container = self.__canvas.create_rectangle(
            (0, 0, self.__imwidth*self.__imscale, self.__imheight*self.__imscale), 
            width=0, tags='image_container')
        
        # set to image loaded state
        self.__image_loaded = True

        # clear the buffer, add the image to the canvas 
        # (depending on whether annotations should be hidden or not)
        # and center the image based on the canvas size
        self.__buffer.clear()
        if self.parent.hide_annotation:
            # replace the annotated image with the original image
            self.__image = self.__original_image.copy()
        else:
            # create the image combined with the annotation
            self.__image = ImageChops.composite(
                self.__foreground_color_image, 
                self.__background_color_image, 
                self.__annotations[self.__selected_layer][1],
            )
        self.reset_view()


    def add_annotation(
        self, 
        layer: str, 
        annotation: Optional[Image.Image] = None,
    ) -> None:
        """
        Add annotation image to dictionary. 
        If None was provided, create an empty one.

        Args:
            layer:  Name of layer.
            annotation:  Image with annotations.
        """
        # create an empty annotation image if None was provided
        if annotation is None:
            annotation = Image.new('L', (self.__imwidth, self.__imheight), 'black')
        # add annotation image to dictionary
        self.__annotations[layer] = (ImageDraw.Draw(annotation), annotation)


    def remove_annotation(self, layer: str) -> None:
        del self.__annotations[layer]


    def is_empty(self, layer: str) -> bool:
        """
        Check if the current annotation is empty (i.e., nothing is drawn).

        Args:
            layer:  Name of layer.
        """
        if np.sum(np.asarray(self.__annotations[layer][1])) == 0:
            return True  
        else:
            return False


    def get_min_zoom(self) -> float:
        return self.__min_zoom


    def get_selected_layer(self) -> str:
        return self.__selected_layer


    def get_tool(self) -> str:
        return self.__tool


    def undo_action(self) -> None:
        """
        Undo the last action (including drawing, erasing, thresholding, and clearing) 
        for the current layer (if previous versions are still in the buffer).
        """
        # check if an image has been loaded
        if not self.__image_loaded: return

        if (self.parent.drawing_mode and not self.parent.hide_annotation
            and self.__tool is None):
            # get the previous annotation from the buffer
            reverted_annotation = self.__buffer.get(self.__selected_layer)

            # check if there was an annotation in the buffer
            if reverted_annotation is not None:
                # create the draw image
                reverted_draw = ImageDraw.Draw(reverted_annotation)
                self.__annotations[self.__selected_layer] = (
                    reverted_draw, 
                    reverted_annotation,
                )
                # create the image combined with the annotation
                self.__image = ImageChops.composite(
                    self.__foreground_color_image, 
                    self.__background_color_image, 
                    reverted_annotation,
                )
                # show the image after the view has been reset   
                self.__show_image()


    def clear_annotation(self) -> None:
        """
        Clear the currently selected annotation if in drawing mode.
        """
        # check if an image has been loaded
        if not self.__image_loaded: return
        # check if the image is not completely empty
        layer = self.parent.canvas.get_selected_layer()
        if self.parent.canvas.is_empty(layer): return

        if (self.parent.drawing_mode and not self.parent.hide_annotation
            and self.__tool is None):
            # add previous annotation to buffer
            self.__buffer.add(
                self.__annotations[self.__selected_layer][1].copy(), 
                self.__selected_layer,
            )
            # create a new annotation
            new_annotation = Image.new('L', (self.__imwidth, self.__imheight), 'black')
            new_draw = ImageDraw.Draw(new_annotation)
            # replace the old annotation with the new annotation
            self.__annotations[self.__selected_layer] = (new_draw, new_annotation)
            
            # create the image combined with the annotation
            self.__image = self.__original_image.copy()
            
            # show the updated annotation on top of the original image     
            self.__show_image()


    def threshold_image(self, filter_size: int = 5) -> None:
        """
        Create annotation by thresholding the image.
        """
        # check if an image has been loaded
        if not self.__image_loaded: return

        if (self.parent.drawing_mode and not self.parent.hide_annotation
            and self.__tool is None):
            # add previous annotation to buffer
            self.__buffer.add(
                self.__annotations[self.__selected_layer][1].copy(), 
                self.__selected_layer,
            )
            # threshold the grayscale version of the image
            threshold = self.parent.threshold
            values = (255, 0) if self.parent.invert_thresholding else (0, 255)
            if self.parent.image_for_thresholding == 'grayscale':
                thresholded_image = self.__original_image_gray.point(
                lambda p: values[0] if p < threshold*255 else values[1]
                )
            elif self.parent.image_for_thresholding == 'saturation':
                thresholded_image = self.__original_image_sat.point(
                    lambda p: values[0] if p < threshold*255 else values[1]
                )
            else:
                raise ValueError('Invalid threshold image.')
            
            # create the annotation by using the thresholded image multiplied 
            # with the previous current annotation or as is
            if self.parent.erase_only_thresholding:
                annotation = ImageChops.multiply(             
                    self.__annotations[self.__selected_layer][1],
                    thresholded_image,   
                )
            else:
                annotation = thresholded_image
            
            # perform a closing operation to remove small holes if necessary
            if self.parent.closing_after_thresholding:
                annotation = np.array(annotation)
                shape = (filter_size, filter_size)
                conv_annotation = convolve(annotation, np.ones(shape)/np.prod(shape))
                conv_annotation = np.where(conv_annotation > self.parent.tolerance*255, 255, 0)
                annotation = (annotation + conv_annotation).astype(np.uint8)
                annotation = Image.fromarray(annotation)

            new_draw = ImageDraw.Draw(annotation)

            # save the new annotation
            self.__annotations[self.__selected_layer] = (new_draw, annotation)

            # create the image combined with the annotation
            self.__image = ImageChops.composite(
                self.__foreground_color_image, 
                self.__background_color_image, 
                annotation,
            )
            # show the annotation on top of the original image     
            self.__show_image()


    def invert_annotation(self) -> None:
        """
        Create annotation by inverting the current annotation.
        """
        # check if an image has been loaded
        if not self.__image_loaded: return

        if (self.parent.drawing_mode and not self.parent.hide_annotation
            and self.__tool is None):
            # add previous annotation to buffer
            self.__buffer.add(
                self.__annotations[self.__selected_layer][1].copy(), 
                self.__selected_layer,
            )
            # invert the annotation
            annotation = self.__annotations[self.__selected_layer][1]
            inverted_annotation = annotation.point(lambda p: 255 if p == 0 else 0)
            new_draw = ImageDraw.Draw(inverted_annotation)

            # save the new annotation
            self.__annotations[self.__selected_layer] = (new_draw, inverted_annotation)

            # create the image combined with the annotation
            self.__image = ImageChops.composite(
                self.__foreground_color_image, 
                self.__background_color_image, 
                inverted_annotation,
            )
            # show the annotation on top of the original image     
            self.__show_image()


    def hide_annotation(self) -> None:
        """
        Hide or unhide the annotation.
        """
        # check if an image has been loaded
        if not self.__image_loaded: return

        if self.parent.hide_annotation:
            # replace the annotated image with the original image
            self.__image = self.__original_image.copy()
            # show the annotation on top of the original image     
            self.__show_image()
        else:
            # create the image combined with the annotation
            self.__image = ImageChops.composite(
                self.__foreground_color_image, 
                self.__background_color_image, 
                self.__annotations[self.__selected_layer][1],
            )
            # show the annotation on top of the original image     
            self.__show_image()


    def update_color(self, level: str) -> None:
        """
        Change the color or opacity of the foreground or background annotation.

        Args:
            level:  Name of level (either 'foreground' or 'background').
        """
        # check if an image has been loaded
        if not self.__image_loaded: return

        # create a new version of the foreground or background color image
        if 'foreground' in level:
            self.__foreground_color_image = self.__original_image.convert(
                'RGB', 
                create_color_matrix(
                    self.parent.foreground_color, 
                    self.parent.foreground_opacity,
                )
            )
        elif 'background' in level:
            self.__background_color_image = self.__original_image.convert(
                'RGB', 
                create_color_matrix(
                    self.parent.background_color, 
                    self.parent.background_opacity,
                )
            )
        else:
            raise ValueError('Invalid argument for level.')
        # create the image combined with the annotation
        self.__image = ImageChops.composite(
            self.__foreground_color_image, 
            self.__background_color_image, 
            self.__annotations[self.__selected_layer][1],
        )
        # show the updated annotation on top of the original image        
        self.__show_image()


    def reset_view(self) -> None:
        """
        Reset the view to show the entire image centered.
        """     
        # check if an image has been loaded
        if not self.__image_loaded: return

        if self.__tool is None:
            # position the canvas to be in the top left corner 
            # the image is now in the top left corner as well, 
            # if it was not translated
            x1, y1, x2, y2 = self.__canvas.coords(self.__container)
            self.__canvas.coords(self.__container, 0, 0, x2-x1, y2-y1)
            # get the coordinate of the top left corner of the image 
            # with respect to the top left corner of the canvas and
            # translate the image in the opposite direction
            x = self.__canvas.coords(self.__container)[0]-self.__canvas.canvasx(0)
            y = self.__canvas.coords(self.__container)[1]-self.__canvas.canvasy(0)
            self.__canvas.move(self.__container, -x, -y)
            # scale the canvas and image such that the image fits inside the window, 
            # depending on whether the height or width is largest
            new_imscale = min(
                self.parent.canvas_dimensions[0]/self.__imwidth, 
                self.parent.canvas_dimensions[1]/self.__imheight,
            ) 
            self.__canvas.scale(
                'all', 
                self.__canvas.canvasx(0), 
                self.__canvas.canvasy(0), 
                new_imscale/self.__imscale, 
                new_imscale/self.__imscale,
            )
            self.__imscale = new_imscale
            # translate the image to be in the center of the window
            x1, y1, x2, y2 = self.__canvas.coords(self.__container)
            x_offset = int((self.__canvas.winfo_width()-(x2-x1))/2)
            y_offset = int((self.__canvas.winfo_height()-(y2-y1))/2)
            self.__canvas.move(self.__container, x_offset, y_offset)

            self.__show_image()


    def switch_layer(self, layer: str) -> None:
        """
        Switch between annotation layers.

        Args:
            layer:  Name of layer.
        """
        # check if an image has been loaded
        if not self.__image_loaded: return

        # get the button name (which is equal to the layer name)
        self.__selected_layer = layer

        # if the annotation is not hidden, switch from layer
        if not self.parent.hide_annotation and self.__tool is None:
            # create the image combined with the annotation
            self.__image = ImageChops.composite(
                self.__foreground_color_image, 
                self.__background_color_image, 
                self.__annotations[self.__selected_layer][1],
            )
            # show the image after the layer has been switched   
            self.__show_image()


    def save_annotations(self, check_buffer: bool = False) -> None:
        """
        Save the annotations as separate channels of a .tiff image 
        or as separate images.

        Args:
            check_buffer: Indicates whether atleast one action must be performed
                on the image before it is saved.
        """
        # check if an image has been loaded
        if not self.__image_loaded: return
        # check if atleast one action was performed on the image
        if check_buffer and len(self.__buffer) == 0: return
        
        # get the annotations for all layers
        layer_annotations = []
        if self.__tool is None:
            for layer in self.parent.layers:
                _, annotation = self.__annotations[layer]
                layer_annotations.append(np.array(annotation)[..., None])

            # get the filename of the original image without extension
            filename = self.__image_path.stem
            # get the output directory
            if self.parent.output_directory is None:
                directory = self.__image_path.parent  
            else:
                directory = self.parent.output_directory

            # determine the latest existing version
            latest_version = 0
            for name in os.listdir(directory):
                if name.startswith(f'{filename}_annotation'):
                    name = name.replace(f'.{self.parent.extension}', '')
                    version = int(name.replace(filename, '').split('-')[1])
                    if version > latest_version:
                        latest_version = version

            # if the .tiff extension was specified, concatenate all channels 
            # and save the annotations as one multi-channel image
            paths = []
            if self.parent.extension.lower() in ['tif', 'tiff']:
                # combine the channels
                annotation_image = np.concatenate(layer_annotations, axis=-1)
                # switch order of dimensions
                annotation_image = annotation_image.transpose((2,0,1))
                # correct for rotation to make the image portrait mode again
                if self.__rotated:
                    annotation_image = np.rot90(annotation_image, 1, (1,2))
                # save the image
                path = save_image(
                    image=annotation_image, 
                    directory=directory, 
                    filename=f'{filename}_annotation',
                    version=latest_version+1,
                    addon=None,
                    extension=self.parent.extension,
                )   
                paths.append(path)
            
            # else save all annotations as separate images with a single channel
            else:
                zipped = zip(layer_annotations, self.parent.layers)
                for annotation_image, layer_name in zipped:
                    # correct for rotation to make the image portrait mode again
                    if self.__rotated:
                        annotation_image = np.rot90(annotation_image, 1, (0,1))
                    # save the image
                    path = save_image(
                        image=annotation_image[..., 0], 
                        directory=directory, 
                        filename=f'{filename}_annotation',
                        version=latest_version+1,
                        addon=layer_name,
                        extension=self.parent.extension,
                    )   
                    paths.append(path)
            
            # replace the annotation paths in the states
            index = self.parent.image_index
            self.parent.annotation_paths[index] = paths


class ControlButtons:
    """
    Set of buttons to switch between inspection and drawing mode, reset the view,
    hide / unhide the annotation, and go to the next or previous image.
    
    Attributes:
        parent:  Parent instance
        container:  Widget that groups all control buttons.    
    """

    def __init__(self, parent: tkinter.Tk) -> None:
        """
        Initialize the control buttons.

        Args:
            parent:  Parent instance.
        """
        # initialize instance attribute for parent
        self.parent = parent
        
        # initialize a container frame to pack the buttons
        self.container = ttk.Frame(self.parent) 

        # initialize attribute to keep track of whether an image is being 
        # changed at the moment
        self.__changing_image = False

        # calculate vertical padding
        padding = self.parent.get_header_padding()
        pady = (floor(padding/2), ceil(padding/2))
        
        # initialize the control buttons
        self.__inspect_button = ttk.Button(
            self.container, 
            image=self.parent.icons['inspect_button'],
            command=self.switch_mode,
        )         
        self.__inspect_button.image = self.parent.icons['inspect_button'] 
        self.__inspect_button.grid(row=0, column=0, padx=5, pady=pady, sticky='ns')

        self.__draw_button = ttk.Button(
            self.container, 
            image=self.parent.icons['draw_button'],
            command=self.switch_mode,
        )
        self.__draw_button.image = self.parent.icons['draw_button'] 
        self.__draw_button.grid(row=0, column=1, padx=5, pady=pady, sticky='ns')

        self.__reset_button = ttk.Button(
            self.container, 
            image=self.parent.icons['reset_button'],
            command=self.parent.canvas.reset_view,
        )
        self.__reset_button.image = self.parent.icons['reset_button'] 
        self.__reset_button.grid(row=0, column=2, padx=5, pady=pady, sticky='ns')

        self.__hide_button = ttk.Button(
            self.container, 
            image=self.parent.icons['hide_button'],
            command=self.change_visibility,
        )
        self.__hide_button.image = self.parent.icons['hide_button'] 
        self.__hide_button.grid(row=0, column=3, padx=5, pady=pady, sticky='ns')

        # only add previous and next buttons if more than one image path was specified
        if len(self.parent.image_paths) > 1:
            self.__previous_button = ttk.Button(
                self.container, 
                image=self.parent.icons['previous_button'],
                command=self.load_previous_image,
            )
            self.__previous_button.image = self.parent.icons['previous_button'] 
            self.__previous_button.grid(row=0, column=4, padx=5, pady=pady, sticky='ns')

            self.__next_button = ttk.Button(
                self.container, 
                image=self.parent.icons['next_button'],
                command=self.load_next_image,
            )
            self.__next_button.image = self.parent.icons['next_button']
            self.__next_button.grid(row=0, column=5, padx=5, pady=pady, sticky='ns')

            # disable the previous or next button depending on the index
            if self.parent.image_index == 0:
                self.__previous_button.state(['disabled'])
            if self.parent.image_index == len(self.parent.image_paths)-1:
                self.__next_button.state(['disabled'])

        # disable the button for the mode that is active by default 
        if self.parent.drawing_mode:
            self.__draw_button.state(['disabled'])
        else:
            self.__inspect_button.state(['disabled'])


    def grid(self, **kw) -> None:
        """ 
        Put the ControlButtons on the parent widget.
        """
        self.container.grid(**kw)


    def pack(self, **kw) -> None:
        """
        Exception: cannot use pack with this widget.
        """
        message = f'Cannot use pack with the widget {self.__class__.__name__}.'
        raise Exception(message)


    def place(self, **kw) -> None:
        """
        Exception: cannot use place with this widget.
        """
        message = f'Cannot use pack with the widget {self.__class__.__name__}.'
        raise Exception(message)
    

    def switch_mode(self) -> None:
        """
        Switch between the inspection and drawing mode if the button of 
        the inactive mode or the corresponding key (<d>) is pressed.
        """
        # switch the mode
        self.parent.drawing_mode = not self.parent.drawing_mode
        # change the appearance of the mode buttons 
        if self.__inspect_button.instate(['disabled']):
            self.__inspect_button.state(['!disabled'])
            self.__draw_button.state(['disabled'])
            self.parent.annotation_buttons.change_button_state(['!disabled'])
        else:
            self.__inspect_button.state(['disabled'])
            self.__draw_button.state(['!disabled'])
            self.parent.annotation_buttons.change_button_state(['disabled'])


    def change_visibility(self) -> None:
        """
        Hide or unhide the annotation.
        """
        if self.parent.canvas.get_tool() is None:
            # switch the hide configuration for the annotation
            self.parent.hide_annotation = not self.parent.hide_annotation
            # change the symbol of the hide annotation button 
            if self.parent.hide_annotation:
                self.__hide_button.configure(image=self.parent.icons['unhide_button'])
                self.__hide_button.image = self.parent.icons['unhide_button']
            else:
                self.__hide_button.configure(image=self.parent.icons['hide_button'])
                self.__hide_button.image = self.parent.icons['hide_button']
        
            # hide or unhide annotation
            self.parent.canvas.hide_annotation()


    def load_previous_image(self) -> None:
        """
        Load the previous image.
        """
        # check if more than one image path was specified
        if len(self.parent.image_paths) <= 1: return
        # check if the image is not being changed at the moment
        if self.__changing_image: return

        # check if the current image is not the first in the sequence
        if self.parent.image_index > 0:
            # change the state to indicate that the image is being changed 
            self.__changing_image = True
            # autosave image if enabled
            if self.parent.autosave:
                self.parent.canvas.save_annotations(check_buffer=True)
            
            self.parent.image_index -= 1
            # disable the previous button in case the index is on the first image
            if self.parent.image_index == 0:
                self.__previous_button.state(['disabled'])
            # enable the next button in case it was disabled
            if self.__next_button.instate(['disabled']):
                self.__next_button.state(['!disabled'])
            
            # remove all extra buttons and layers
            self.parent.layer_buttons.remove_extra_buttons()
            self.parent.layer_buttons.reset_canvas()
            self.parent.layers.remove_extra_layers()
            self.parent.canvas.load_image()
            self.parent.layer_buttons.initialize_extra_buttons()
            # change the state to indicate that the image has been changed 
            self.__changing_image = False


    def load_next_image(self) -> None:
        """
        Load the next image.
        """
        # check if more than one image path was specified
        if len(self.parent.image_paths) <= 1: return
        # check if the image is not being changed at the moment
        if self.__changing_image: return
        
        # check if the current image is not the last in the sequence
        if self.parent.image_index < len(self.parent.image_paths)-1:
            # change the state to indicate that the image is being changed 
            self.__changing_image = True
            # autosave image if enabled
            if self.parent.autosave:
                self.parent.canvas.save_annotations(check_buffer=True)

            self.parent.image_index += 1
            # disable the next button in case the index is on the first image
            if self.parent.image_index == len(self.parent.image_paths)-1:
                self.__next_button.state(['disabled'])
            # enable the previous button in case it was disabled
            if self.__previous_button.instate(['disabled']):
                self.__previous_button.state(['!disabled'])

            # remove all extra buttons and layers
            self.parent.layer_buttons.remove_extra_buttons()
            self.parent.layer_buttons.reset_canvas()
            self.parent.layers.remove_extra_layers()
            self.parent.canvas.load_image()
            self.parent.layer_buttons.initialize_extra_buttons()
            # change the state to indicate that the image has been changed 
            self.__changing_image = False


class LayerButtons:
    """
    Set of buttons to switch between annotation layers and optionally add 
    more annotation layers in scrollable area.
    
    Attributes:
        parent:  Parent instance.
        container:  Widget that groups all layer buttons. 
    """
    # default values for layout
    __minimum_to_screen_width_ratio = 0.2
    # default scroll speed
    __step = 1

    def __init__(self, parent: tkinter.Tk) -> None:
        """
        Initialize the layer buttons.
        
        Args:
            parent:  Parent instance.
        """
        # initialize instance attribute for parent
        self.parent = parent

        # initialize a container frame and canvas widget
        self.container = ttk.Frame(self.parent) 
        self.__canvas = tk.Canvas(self.container)
        self.__canvas.grid(row=0, column=0)
        
        # initialize a frame and use it as window for the canvas
        self.__scrollable_frame = ttk.Frame(self.__canvas)
        self.__canvas.create_window(
            (0, 0), 
            window=self.__scrollable_frame, 
            anchor="nw",
        )
        # calculate vertical padding
        padding = self.parent.get_header_padding()
        pady = (floor(padding/2), 0)

        # initialize the layer buttons
        self.__buttons = []
        names = self.parent.layers + (['+'] if self.parent.add_layers else [])
        for i, name in enumerate(names):
            button = ttk.Button(
                self.__scrollable_frame, 
                text=name, 
                style='text.TButton',
            )          
            button.grid(row=0, column=i, padx=5, pady=pady, sticky='ns')
            button.bind('<Button-1>', self.switch_layer_wrapper)
            self.__buttons.append(button)

        # initialize a width attribute and set the canvas width
        self.__width = max(
            min(self.__scrollable_frame.winfo_width(), 
                self.parent.get_available_width()),
            self.get_minimum_width(),             
        )
        self.__canvas.configure(width=self.__width)

        # disable the first button
        self.__buttons[0].state(['disabled'])

        # initialize and position the scrollbar
        self.__scrollbar = ttk.Scrollbar(
            self.container, 
            orient="horizontal", 
            command=self.__canvas.xview,
        )
        self.__scrollbar.grid(row=1, column=0, sticky="ew")
        self.__show_scrollbar = False

        # add an event binding to the scrollable frame
        self.__scrollable_frame.bind(
            "<Configure>",
            lambda event: 
                self.__canvas.configure(scrollregion=self.__canvas.bbox("all")),
        )
        # configure the canvas
        self.__canvas.configure(xscrollcommand=self.__scrollbar.set)
        self.__canvas.bind('<Enter>', self.__bound_to_mousewheel)
        self.__canvas.bind('<Leave>', self.__unbound_to_mousewheel)

        if self.__scrollable_frame.winfo_width() > self.__width:
            self.__show_scrollbar = True
        else:
            self.__show_scrollbar = False
            self.__scrollbar.grid_remove()


    def grid(self, **kw) -> None:
        """ 
        Put the LayerButtons on the parent widget.
        """
        self.container.grid(**kw)


    def pack(self, **kw) -> None:
        """
        Exception: cannot use pack with this widget.
        """
        message = f'Cannot use pack with the widget {self.__class__.__name__}.'
        raise Exception(message)


    def place(self, **kw) -> None:
        """
        Exception: cannot use place with this widget.
        """
        message = f'Cannot use pack with the widget {self.__class__.__name__}.'
        raise Exception(message)


    def __bound_to_mousewheel(self, event: tkinter.Event) -> None:
        """
        When the cursor enters the canvas, bind the mousewheel events.
        """ 
        self.__canvas.bind_all("<MouseWheel>", self.__wheel)
        self.__canvas.bind_all("<Button-4>", self.__wheel)
        self.__canvas.bind_all("<Button-5>", self.__wheel)


    def __unbound_to_mousewheel(self, event: tkinter.Event) -> None:
        """
        When the cursor leaves the canvas, unbind the mousewheel events.
        """
        self.__canvas.unbind_all("<MouseWheel>")
        self.__canvas.unbind_all("<Button-4>")
        self.__canvas.unbind_all("<Button-5>")


    def __wheel(self, event) -> None:
        """
        When the cursor is inside the canvas, scroll to move the buttons left or right.
        """
        if event.num == 5 or event.delta == -120:  # scroll down
            self.__canvas.xview_scroll(self.__step, "units")
        elif event.num == 4 or event.delta == 120:  # scroll up
            self.__canvas.xview_scroll(-self.__step, "units")
        

    def switch_layer_wrapper(
        self, 
        event: Optional[tkinter.Event], 
        clicked_button: Optional[str] = None,
    ) -> None:
        """
        Call the switch layer method of the canvas, disable the clicked button,
        and enable all other buttons.
        """
        # determine which button was clicked (either by the user or virtually)
        if event is not None:
            clicked_button = event.widget.cget('text')
        elif clicked_button is None:
            return
        
        # check if the '+' button was clicked
        if clicked_button == '+':
            # add extra layer, create extra button, and annotation image
            layer = self.parent.layers.add_extra_layer()
            clicked_button = layer
            self.__add_extra_button(layer)
            self.parent.canvas.add_annotation(layer)

        # call the switch_layer method of the canvas
        self.parent.canvas.switch_layer(clicked_button)

        # disable the clicked button and enable all other buttons
        for button in self.__buttons:
            if button.cget('text') == clicked_button:
                button.state(['disabled'])
            else:
                button.state(['!disabled'])


    def __add_extra_button(self, layer: str) -> None:
        """
        Add button for extra layer.
       
        Args:
            layer:  Name of extra layer.
        """
        # change the name of the "+" button
        self.__buttons[-1].configure(text=layer)

        # calculate vertical padding
        padding = self.parent.get_header_padding()
        pady = (floor(padding/2), 0)

        # create extra button
        button = ttk.Button(
            self.__scrollable_frame, 
            text='+', 
            style='text.TButton',
        )
        button.grid(row=0, column=len(self.__buttons), padx=5, pady=pady, sticky='ns')
        button.bind('<Button-1>', self.switch_layer_wrapper)
        self.__buttons.append(button)
        
        # move scrollbar to the far right
        self.__canvas.update()
        self.__canvas.xview_moveto(self.__canvas.winfo_width())


    def __remove_extra_button(self, layer: str, select_prior: bool) -> None:
        """
        Remove the button for the extra layer.
        
        Args:
            layer:  Name of extra layer.
            select_prior:  Indicates whether the prior button should be disabled
                and the prior layer should be selected.
        """
        # get the index of the button that should be removed
        index = self.parent.layers.index(layer)
        
        # remove the button
        self.parent.canvas.remove_annotation(layer)
        self.__buttons[index].destroy()
        del self.__buttons[index]

        # select prior button and call the switch_layer method of the canvas
        if select_prior:
            self.__buttons[index-1].configure(state=['disabled'])
            self.parent.canvas.switch_layer(
                self.parent.layers[index-1],
            )
        # change the column positions of the next buttons 
        for i in range(index, len(self.parent.layers)):
            self.__buttons[i].grid(row=0, column=i) 


    def remove_extra_buttons(self) -> None:
        """
        Remove all buttons for extra layers.
        """
        # check if the currently selected layer is an extra layer
        # if so, select the last predefined layer, else keep the selected layer
        if self.parent.canvas.get_selected_layer() in self.parent.layers.extra:
            select_prior = True
        else:
            select_prior = False

        for layer in reversed(self.parent.layers.extra):
            self.__remove_extra_button(layer, select_prior=select_prior)
            self.parent.layers.remove_extra_layer(layer)


    def initialize_extra_buttons(self) -> None:
        """
        Add a button for each extra layer.
        """
        # add a button for each extra layer
        for layer in self.parent.layers.extra:
            self.__add_extra_button(layer)


    def clear_annotation_else_remove_button(self) -> None:
        """
        Clear the annotation. If the annotation was already empty 
        and the layer was extra (added using the '+' button),
        remove the layer and button.
        """
        if self.parent.drawing_mode:
            layer = self.parent.canvas.get_selected_layer()
            # check if the layer is an extra layer
            if layer in self.parent.layers.extra:
                # check if the annotation is empty
                if self.parent.canvas.is_empty(layer):
                    self.__remove_extra_button(layer, select_prior=True)
                    self.parent.layers.remove_extra_layer(layer)
            # clear the annotation if the layer was not removed
            if layer in self.parent.layers:
                self.parent.canvas.clear_annotation()


    def configure(self) -> None:
        """ 
        Configure the canvas height of widget.
        """
        ypad = floor(self.parent.get_header_padding()/2)
        self.__canvas.configure(height=self.__buttons[0].winfo_height()+ypad)


    def get_minimum_width(self) -> int:
        return int(self.parent.canvas_dimensions[0]
                   * self.__minimum_to_screen_width_ratio)


    def get_scrollbar_status(self) -> int:
        return self.__show_scrollbar


    def reset_canvas(self) -> None:
        self.__canvas.xview_moveto(0)


    def resize_canvas(self) -> None:
        """
        Resize the canvas with buttons depending on the available width.
        """           
        # if the width of the buttons is smaller than what is available, 
        # resize the scrollable region
        available_width = self.parent.get_available_width()
        if available_width < self.__scrollable_frame.winfo_width():
            self.__width = available_width
            self.__canvas.configure(width=self.__width)
            # make scrollbar visible in case it is still invisible
            if self.__show_scrollbar == False:
                self.__show_scrollbar = True
                self.__scrollbar.grid()
        # set the width of the canvas equal to the width 
        # of the buttons if it is not
        elif self.__width != self.__scrollable_frame.winfo_width():
            self.__canvas.configure(width=self.__scrollable_frame.winfo_width())
            # make scrollbar invisible in case it is still visible
            if self.__show_scrollbar == True:
                self.__show_scrollbar = False
                self.__scrollbar.grid_remove()


class AnnotationButtons:
    """
    Set of buttons for annotation actions.
    
    Attributes:
        parent:  Parent instance.
        container:  Widget that groups all annotation buttons.
    """

    def __init__(self, parent: tkinter.Tk) -> None:
        """
        Initialize the annotation buttons.
        
        Args:
            parent:  Parent instance.
        """
        # initialize instance attribute for parent
        self.parent = parent

        # initialize a frame to pack the buttons
        self.container = ttk.Frame(self.parent) 

        # calculate vertical padding
        padding = self.parent.get_header_padding()
        pady = (floor(padding/2), ceil(padding/2))

        # initialize the annotation buttons
        self.__fill_button = ttk.Button(
            self.container, 
            image=self.parent.icons['fill_off_button'],
            command=self.change_auto_fill,
        )
        self.__fill_button.image = self.parent.icons['fill_off_button']
        self.__fill_button.grid(row=0, column=0, padx=5, pady=pady, sticky='ns')
        # change the symbol if auto fill is active
        if self.parent.auto_fill:
            self.__fill_button.configure(image=self.parent.icons['fill_on_button'])
            self.__fill_button.image = self.parent.icons['fill_on_button']

        self.__threshold_button = ttk.Button(
            self.container, 
            image=self.parent.icons['threshold_button'],
            command=self.parent.canvas.threshold_image,
        )
        self.__threshold_button.image = self.parent.icons['threshold_button']
        self.__threshold_button.grid(row=0, column=1, padx=5, pady=pady, sticky='ns')

        self.__invert_button = ttk.Button(
            self.container, 
            image=self.parent.icons['invert_button'],
            command=self.parent.canvas.invert_annotation,
        )
        self.__invert_button.image = self.parent.icons['invert_button']
        self.__invert_button.grid(row=0, column=2, padx=5, pady=pady, sticky='ns')

        self.__undo_button = ttk.Button(
            self.container, 
            image=self.parent.icons['undo_button'],
            command=self.parent.canvas.undo_action,
        )
        self.__undo_button.image = self.parent.icons['undo_button']
        self.__undo_button.grid(row=0, column=3, padx=5, pady=pady, sticky='ns')

        self.__clear_button = ttk.Button(
            self.container, 
            image=self.parent.icons['clear_button'],
            command=self.parent.layer_buttons.clear_annotation_else_remove_button   
        )
        self.__clear_button.image = self.parent.icons['clear_button']
        self.__clear_button.grid(row=0, column=4, padx=5, pady=pady, sticky='ns')

        self.__save_button = ttk.Button(
            self.container, 
            image=self.parent.icons['save_button'],
            command=self.parent.canvas.save_annotations,
        )
        self.__save_button.image = self.parent.icons['save_button']
        self.__save_button.grid(row=0, column=5, padx=5, pady=pady, sticky='ns')

        self.__settings_button = ttk.Button(
            self.container, 
            image=self.parent.icons['settings_button'],
            command=self.open_settings_window,
        )
        self.__settings_button.image = self.parent.icons['settings_button']
        self.__settings_button.grid(row=0, column=6, padx=5, pady=pady, sticky='ns')

        # depending on whether the initial mode is drawing or inspection
        if not self.parent.drawing_mode:
            self.change_button_state(['disabled'])


    def grid(self, **kw) -> None:
        """ 
        Put the AnnotationButtons on the parent widget.
        """
        self.container.grid(**kw)


    def pack(self, **kw) -> None:
        """ 
        Exception: cannot use pack with this widget.
        """
        message = f'Cannot use pack with the widget {self.__class__.__name__}.'
        raise Exception(message)


    def place(self, **kw) -> None:
        """ 
        Exception: cannot use place with this widget.
        """
        message = f'Cannot use pack with the widget {self.__class__.__name__}.'
        raise Exception(message)


    def change_auto_fill(self) -> None:
        """
        Change the auto fill setting.
        """
        if self.parent.drawing_mode:
            # switch the auto fill configuration
            self.parent.auto_fill = not self.parent.auto_fill
            # change the symbol of the auto fill button 
            if self.parent.auto_fill:
                self.__fill_button.configure(image=self.parent.icons['fill_on_button'])
                self.__fill_button.image = self.parent.icons['fill_on_button']
            else:
                self.__fill_button.configure(image=self.parent.icons['fill_off_button'])
                self.__fill_button.image = self.parent.icons['fill_off_button']


    def change_button_state(self, state: list) -> None:
        """
        Change the state of the buttons (except for the save and settings buttons).

        Args:
            state:  Tkinter statespec, i.e. ['disabled'] or ['!disabled'].
        """
        # define list of buttons (except for the save and settings buttons)
        buttons = [
            self.__fill_button, 
            self.__threshold_button, 
            self.__invert_button, 
            self.__undo_button, 
            self.__clear_button,
        ]
        for button in buttons:
            button.state(state)


    def open_settings_window(self) -> None:
        """
        Open an additional window to let the user modify settings.
        """
        # check if the settings window is not active
        if not self.parent.active_settings_window:
            self.parent.active_settings_window = True
            self.settings_window = SettingsWindow(self.parent)
        else:
            self.settings_window.close_window()


class SettingsWindow(tk.Toplevel):
    """
    Window that pops up when the settings button is pressed, 
    containing settings that can be adjusted by the user.
    
    Attributes:
        parent:  Parent instance
        window:  Top level window. 
    """
    # default values for layout
    __height_window_to_screen_ratio = 0.58
    __width_to_height_ratio = 0.52

    def __init__(self, parent: tkinter.Tk) -> None:
        """
        Initialize the settings slides.
        
        Args:
            parent:  Parent instance.
        """
        super().__init__()

        # initialize instance attribute for parent
        self.parent = parent

        # initialize fonts
        header_font = ('-family', self.parent.font, '-size', 14, '-weight', 'bold')
        font = ('-family', self.parent.font, '-size', 12)

        # get the main window position and size
        main_window_x = self.parent.winfo_x()
        main_window_y = self.parent.winfo_y()
        main_window_width = self.parent.canvas_dimensions[0]

        # get the screen width and height
        screen_height = self.winfo_screenheight()
        # calculate the width and height of the window, 
        # and the offset with respect to the outside of the screen
        window_height = int(screen_height*self.__height_window_to_screen_ratio)
        window_width = int(window_height*self.__width_to_height_ratio)
        left_window_offset = main_window_x+main_window_width-window_width
        top_window_offset = main_window_y+self.parent.title_bar_height+self.parent.get_header_height()

        # specify the window geometry and prevent resizing the window
        self.title('Settings')
        self.geometry((f'{window_width}x{window_height}+'
            f'{left_window_offset}+{top_window_offset}')
        )
        self.resizable(False, False)
        self.overrideredirect(True)

        # configure the grid
        for i in range(3): self.columnconfigure(i, weight=1)
        for j in range(16): self.rowconfigure(j, weight=1)
 
        # initialize and position the settings label
        self.__settings_label = ttk.Label(self, text='Thresholding', 
                                          font=header_font)
        self.__settings_label.grid(row=0, column=0, columnspan=3,
                                   padx=20, pady=(10, 0), sticky='sw')

        self.__radio_buttons = ttk.Frame(self)
        self.__radio_buttons_var = tk.StringVar(value=self.parent.image_for_thresholding)
        self.__radio_button_gray = ttk.Radiobutton(self.__radio_buttons, 
                                                   text='Grayscale',
                                                   value='grayscale',
                                                   variable=self.__radio_buttons_var,
                                                   command=self.update_threshold_image, 
                                                   style='text.TRadiobutton')
        self.__radio_button_gray.grid(row=0, column=0, sticky='w', padx=(0, 20))
        self.__radio_button_sat = ttk.Radiobutton(self.__radio_buttons,
                                                  text='Saturation',
                                                  value='saturation',
                                                  variable=self.__radio_buttons_var,
                                                  command=self.update_threshold_image, 
                                                  style='text.TRadiobutton')
        self.__radio_button_sat.grid(row=0, column=1, sticky='e')
        self.__radio_buttons.grid(row=1, column=0, columnspan=3, padx=20,
                                  pady=(0, 5), sticky='ew')

        # initialize and position the threshold label and slider
        self.__threshold_label = ttk.Label(self, font=font, 
                                           text=f'Threshold: {self.parent.threshold:0.2f}')
        self.__threshold_label.grid(row=2, column=0, columnspan=3, 
                                    padx=20, pady=0, sticky='w')
        self.__threshold = tk.DoubleVar(value=self.parent.threshold)
        self.__threshold_slider = ttk.Scale(self, from_=0.0, to=1.0, 
            variable=self.__threshold, command=lambda event: self.update_threshold())
        self.__threshold_slider.grid(row=3, column=0, columnspan=3, 
                                     padx=20, pady=0, sticky='ew')

        # initialize and position checkboxes for thresholding settings
        self.__invert_var = tk.BooleanVar(value=self.parent.invert_thresholding)
        self.__invert_checkbox = ttk.Checkbutton(self, text='Invert', 
                                                  variable=self.__invert_var,
                                                  onvalue=True, offvalue=False,
                                                  command=self.update_checkboxes,
                                                  style='Switch.TCheckbutton')     
        self.__invert_checkbox.grid(row=4, column=0, columnspan=3, 
                                    padx=20, pady=0, sticky='w')
        
        self.__erase_only_var = tk.BooleanVar(value=self.parent.erase_only_thresholding)
        self.__erase_only_checkbox = ttk.Checkbutton(self, text='Erase only',
                                                     variable=self.__erase_only_var,
                                                     onvalue=True, offvalue=False,
                                                     command=self.update_checkboxes,
                                                     style='Switch.TCheckbutton')
        self.__erase_only_checkbox.grid(row=5, column=0, columnspan=3, 
                                        padx=20, pady=0, sticky='w')
        
        self.__closing_var = tk.BooleanVar(value=self.parent.closing_after_thresholding)
        self.__closing_checkbox = ttk.Checkbutton(self, text='Fill holes', 
                                                  variable=self.__closing_var,
                                                  onvalue=True, offvalue=False,
                                                  command=self.update_checkboxes,
                                                  style='Switch.TCheckbutton')     
        self.__closing_checkbox.grid(row=6, column=0, columnspan=3, 
                                     padx=20, pady=0, sticky='w')

        # initialize and position the tolerance label and slider
        self.__tolerance_label = ttk.Label(self, font=font,
                                           text=f'Tolerance: {self.parent.tolerance:0.2f}')
        self.__tolerance_label.grid(row=7, column=0, columnspan=3, 
                                    padx=20, pady=0, sticky='w')
        self.__tolerance = tk.DoubleVar(value=self.parent.tolerance)
        self.__tolerance_slider = ttk.Scale(self, from_=0.0, to=1.0, 
            variable=self.__tolerance, command=lambda event: self.update_tolerance())
        self.__tolerance_slider.grid(row=8, column=0, columnspan=3, 
                                     padx=20, pady=0, sticky='ew')

        # add sliders for changing the opacity and color of the foreground
        # initialize and position the first separator
        self.__separator_1 = ttk.Separator(self, orient='horizontal')
        self.__separator_1.grid(row=9, column=0, columnspan=3, 
                                padx=0, pady=5, sticky='ew')
        
        # initialize and position the foreground label
        self.__fg_label = ttk.Label(self, text='Foreground', font=header_font)
        self.__fg_label.grid(row=10, column=0, columnspan=3, 
                             padx=20, pady=(10, 0), sticky='sw')
        
        # initialize and position the foreground opacity label and slider
        self.__fg_opacity_label = ttk.Label(self, text='Opacity', font=font)
        self.__fg_opacity_label.grid(row=11, column=0, columnspan=3, 
                                     padx=20, pady=0, sticky='w')
        self.__fg_opacity = tk.DoubleVar(value=self.parent.foreground_opacity)
        self.__fg_opacity_slider = ttk.Scale(self, from_=0.0, to=1.0, 
                                             variable=self.__fg_opacity)
        self.__fg_opacity_slider.grid(row=12, column=0, columnspan=3,  
                                      padx=20, pady=0, sticky='ew')
        self.__fg_opacity_slider.bind('<ButtonRelease>', 
            lambda event: self.update_color('foreground'))

        # initialize and position the foreground color label and picker
        self.__fg_color_label = ttk.Label(self, text='Color', font=font)
        self.__fg_color_label.grid(row=13, column=0, columnspan=3, 
                                   padx=20, pady=0, sticky='w')
        self.__fg_color_picker = ColorPicker(self, 'foreground')
        self.__fg_color_picker.grid(row=14, column=0, columnspan=3, 
                                    padx=20, pady=(0, 5), sticky='ew')

        # add slides for changing the opacity and color of the background
        # initialize and position the second separator
        self.__seperator_2 = ttk.Separator(self, orient='horizontal')
        self.__seperator_2.grid(row=15, column=0, columnspan=3, 
                                padx=0, pady=5, sticky='ew')

        # initialize and position the background label
        self.__bg_label = ttk.Label(self, text='Background', font=header_font)
        self.__bg_label.grid(row=16, column=0, columnspan=3, 
                             padx=20, pady=(10, 0), sticky='sw')
        
        # initialize and position the background opacity label and slider
        self.__bg_opacity_label = ttk.Label(self, text='Opacity', font=font)
        self.__bg_opacity_label.grid(row=17, column=0, columnspan=3, 
                                     padx=20, pady=0, sticky='w')
        self.__bg_opacity = tk.DoubleVar(value=self.parent.background_opacity)
        self.__bg_opacity_slider = ttk.Scale(self, from_=0.0, to=1.0, 
                                             variable=self.__bg_opacity)
        self.__bg_opacity_slider.grid(row=18, column=0, columnspan=3, 
                                      padx=20, pady=0, sticky='ew')
        self.__bg_opacity_slider.bind('<ButtonRelease>', 
                                      lambda event: self.update_color('background'))

        # initialize and position the background color label and picker
        self.__bg_color_label = ttk.Label(self, text='Color', font=font)
        self.__bg_color_label.grid(row=19, column=0, columnspan=3, 
                                   padx=20, pady=0, sticky='w')
        self.__bg_color_picker = ColorPicker(self, 'background')
        self.__bg_color_picker.grid(row=20, column=0, columnspan=3, 
                                    padx=20, pady=(0, 10), sticky='ew')

        # window is closed when mouse leaves settings window
        self.bind('<Leave>', self.__close)


    def __close(self, event) -> None:
        """ 
        Close the window.
        """
        widget = [item for item in str(event.widget).split('.!') if item != '']
        if len(widget) == 1 and 'settingswindow' in widget[0]:
            self.parent.active_settings_window = False
            self.destroy()


    def close_window(self) -> None:
        """ 
        Close the window.
        """
        self.parent.active_settings_window = False
        self.destroy()


    def update_threshold(self) -> None:
        """ 
        Update the state attribute with the current threshold slider value.
        """
        self.parent.threshold = self.__threshold.get()
        self.__threshold_label.configure(text=f'Threshold: {self.parent.threshold:0.2f}')


    def update_threshold_image(self) -> None:
        """ 
        Update the state attribute with the image to use for thresholding.
        """
        self.parent.image_for_thresholding = self.__radio_buttons_var.get()


    def update_color(self, level: str) -> None:
        """
        Update the opacity of the annotation with the current slider value.

        Args:
            level: 'foreground' or 'background' level.
        """
        if level == 'foreground':
            self.parent.foreground_opacity = self.__fg_opacity.get()
        elif level == 'background':
            self.parent.background_opacity = self.__bg_opacity.get()
        else:
            raise ValueError('Invalid argument for level.')
        # apply the opacity change
        self.parent.canvas.update_color(level)


    def update_checkboxes(self) -> None:
        """ 
        Update the state attributes with the checkbox values.
        """
        self.parent.invert_thresholding = self.__invert_var.get()
        self.parent.erase_only_thresholding = self.__erase_only_var.get()
        self.parent.closing_after_thresholding = self.__closing_var.get()


    def update_tolerance(self) -> None:
        """ 
        Update the state attribute with the current tolerance slider value.
        """
        self.parent.tolerance = self.__tolerance.get()
        self.__tolerance_label.configure(text=f'Tolerance: {self.parent.tolerance:0.2f}')


class ColorPicker:
    """
    Widget for selecting a color.
    
    Attributes:
        parent:  Parent instance.
    """

    def __init__(self, parent: tkinter.Tk, level: str) -> None:
        """
        Initialize color picker.
        
        Args:
            parent:  Parent object
            level:  'foreground' or 'background' level.
        """
        # initialize instance attributes
        self.parent = parent
        self.__level = level
        if self.__level == 'foreground':
            color = self.parent.parent.foreground_color
        elif self.__level == 'background':
            color = self.parent.parent.background_color
        else:
            raise ValueError('Invalid level.')

        # define font
        self.__font = ('-family', self.parent.parent.font, '-size', 11)

        # initialize a frame to pack the buttons
        self.__frame = ttk.Frame(self.parent) 

        # configure the grid
        self.__frame.columnconfigure(0, weight=4)
        self.__frame.columnconfigure(1, weight=1)
        self.__frame.columnconfigure(2, weight=3)
        self.__frame.rowconfigure(0, weight=1)
        self.__frame.rowconfigure(1, weight=1) 
        self.__frame.rowconfigure(2, weight=1)

        # initialize label that indicates the current color
        self.__color_label = ttk.Label(
            self.__frame, 
            background=get_hex_color(color),
        ) 
        self.__color_label.grid(row=0, column=0, rowspan=3, sticky='nswe')

        # initialize labels that indicate RGB values
        self.__R_label = ttk.Label(self.__frame, text='R', font=self.__font) 
        self.__R_label.grid(row=0, column=1)

        self.__G_label = ttk.Label(self.__frame, text='G', font=self.__font) 
        self.__G_label.grid(row=1, column=1)

        self.__B_label = ttk.Label(self.__frame, text='B', font=self.__font) 
        self.__B_label.grid(row=2, column=1)

        # initialize scales to change the RGB values
        self.__R_value = tk.DoubleVar(value=color[0])
        self.__R_slider = ttk.Scale(self.__frame, from_=0, to=1, variable=self.__R_value)
        self.__R_slider.grid(row=0, column=2, sticky='ew')
        self.__R_slider.bind('<ButtonRelease>', lambda event: self.update_color())

        self.__G_value = tk.DoubleVar(value=color[1])
        self.__G_slider = ttk.Scale(self.__frame, from_=0, to=1, variable=self.__G_value)
        self.__G_slider.grid(row=1, column=2, sticky='ew')
        self.__G_slider.bind('<ButtonRelease>', lambda event: self.update_color())

        self.__B_value = tk.DoubleVar(value=color[2])
        self.__B_slider = ttk.Scale(self.__frame, from_=0, to=1, variable=self.__B_value)
        self.__B_slider.grid(row=2, column=2, sticky='ew')
        self.__B_slider.bind('<ButtonRelease>', lambda event: self.update_color())


    def grid(self, **kw) -> None:
        """ 
        Put the CanvasImage widget on the parent widget.
        """
        self.__frame.grid(**kw)


    def pack(self, **kw) -> None:
        """ 
        Exception: cannot use pack with this widget.
        """
        message = f'Cannot use pack with the widget {self.__class__.__name__}.'
        raise Exception(message)


    def place(self, **kw) -> None:
        """ 
        Exception: cannot use place with this widget.
        """
        message = f'Cannot use pack with the widget {self.__class__.__name__}.'
        raise Exception(message)


    def update_color(self) -> None:
        """
        Change the color after one of the sliders has been adjusted
        """
        # get the RGB values from the slides and change the color value 
        color = [
            self.__R_value.get(), 
            self.__G_value.get(), 
            self.__B_value.get(),
        ]
        if self.__level == 'foreground':
            self.parent.parent.foreground_color = color
        else:
            self.parent.parent.background_color = color

        # change the color of the color indicator label
        self.__color_label.configure(
            background=get_hex_color(color),
        )
        # change the annotation color
        self.parent.parent.canvas.update_color(self.__level)


class MainWindow(tk.Tk):
    """
    Main window class
    
    Attributes:
        image_paths:  Path(s) to image(s).
        annotation_paths:  Path(s) to annotations(s).
        output_directory:  Directory for saving the annotations.
        extension:  Datatype for saving the annotation.
        rotate_portrait:  Indicates whether images in portrait mode are rotated 
            90 degrees for annotation.
        add_layers: Indicates whether extra layers for annotation can be added 
            by the user while annotating.
        autosave: Indicates whether annotations are automatically saved before 
            going to the previous or next image.
        image_index:  Index value for images.
        layers:  Layer tracker object names for all annotation layers.
        drawing_mode:  Indicates whether the draw mode is activated.
        hide_annotation:  Indicates whether hiding annotations is activated.
        auto_fill:  Indicates whether auto fill for annotation is activated.
        threshold:  Value for threshold.
        erase_only_thresholding:  Indicates whether thresholding can only erase.
        closing_after_thresholding:  Indicates whether closing after thresholding 
            is performed.
        foreground_opacity:  Value for foreground opacity.
        background_opacity:  Value for background opacity.
        foreground_color:  RGB values for foreground color.
        background_color:  RGB values for background color.
        canvas_dimensions:  Height and width of canvas.
    """
    # default values for settings
    __initial_drawing_mode = True
    __initial_hide_annotation = False
    __initial_auto_fill = False
    __initial_threshold = 0.85
    __initial_image_for_thresholding = 'grayscale'
    __initial_invert_thresholding = True
    __initial_erase_only_thresholding = False
    __initial_closing_after_thresholding = False
    __initial_tolerance = 0.85
    __initial_foreground_opacity = 0.5
    __initial_background_opacity = 0.0
    __initial_foreground_color = [0.0, 1.0, 1.0]
    __initial_background_color = [1.0, 1.0, 1.0]

    # default values for layout
    __window_to_screen_ratio = 0.75
    __icon_to_screen_ratio = 0.04
    __padding_to_screen_height_ratio = 0.04
    __padx = 10

    def __init__(
        self, 
        image_paths: Union[str, tuple, list], 
        annotation_paths: Union[str, tuple, list], 
        output_directory: Union[str, Path],
        extension: str, 
        layers: list[str], 
        rotate_portrait: bool,
        add_layers: bool,
        autosave: bool,
        theme: str,
    ) -> None:
        """
        Initialize all widgets that are part of the main window.
        
        Args:
            image_paths:  Path(s) to image(s).
            annotation_paths:  Path(s) to annotations(s).
            output_directory:  Directory for saving the annotations.
            extension:  Datatype for saving the annotation.
            layers:  Names for all annotation layers.
            rotate_portrait:  Indicates whether images in portrait mode are 
                rotated 90 degrees for annotation.
            add_layers:  Indicates whether extra layers for annotation can be 
                added by the user while annotating.
            autosave:  Indicates whether annotations are automatically saved 
                before going to the previous or next image.
            theme:  Indicates whether the light or dark theme is used.
        """
        super().__init__()
        
        # initialize font
        if platform.system() in ('Windows', 'Darwin'):
            self.font = 'DM Sans'
            for font in FONTS:
                pyglet.font.add_file(
                    (Path(fonts.__file__).parent / font).as_posix(),
                )
        else:
            self.font = 'Helvetica'

        # initialize dictionary with icons
        self.icons = {}
        icon_size = int(self.winfo_screenheight()*self.__icon_to_screen_ratio)
        for button_name, filename in ICONS.items():
            path = Path(icons.__file__).parent / filename
            icon = ImageTk.PhotoImage(
                Image.open(path).resize(
                    tuple([icon_size]*2), # height == width
                    Image.ANTIALIAS,
                ),
            )
            self.icons[button_name] = icon

        # configure theme and style of window
        sv_ttk.set_theme(theme)
        style = ttk.Style()
        style.configure('text.TButton', font=(self.font, 14, 'bold'))
        style.configure('Switch.TCheckbutton', font=(self.font, 12))
        style.configure('text.TRadiobutton', font=(self.font, 12))

        # calculate the width and height of the window
        window_width = int(self.winfo_screenwidth()*self.__window_to_screen_ratio)
        window_height = int(self.winfo_screenheight()*self.__window_to_screen_ratio)
        left_window_offset = int((self.winfo_screenwidth()-window_width)/2)
        top_window_offset = int((self.winfo_screenheight()-window_height)/2)

        # specify the window geometry and prevent resizing the window
        self.title('Annotation tool')
        self.wm_iconphoto(False, self.icons['draw_button'])
        self.geometry(
            f'{window_width}x{window_height}+{left_window_offset}+{top_window_offset}'
        )
        # get the height of the main window title bar
        self.update_idletasks()
        if platform.system() == 'Windows':
            offset_y = int(self.geometry().rsplit('+', 1)[-1])
            self.title_bar_height = self.winfo_rooty() - offset_y
        else:
            self.title_bar_height = 0

        # initialize instance attributes for paths
        self.image_paths = image_paths
        self.annotation_paths = annotation_paths
        self.output_directory = Path(
            '' if output_directory is None else output_directory
        )
        self.extension = extension

        # initialize instance attributes for permanent settings
        self.rotate_portrait = rotate_portrait
        self.add_layers = add_layers
        self.autosave = autosave
        
        # initialize instance attributes for specific states
        self.image_index = 0
        self.layers = LayerTracker(layers)
        self.drawing_mode = self.__initial_drawing_mode
        self.hide_annotation = self.__initial_hide_annotation
        self.auto_fill = self.__initial_auto_fill
        self.threshold = self.__initial_threshold
        self.tolerance = self.__initial_tolerance
        self.foreground_opacity = self.__initial_foreground_opacity
        self.background_opacity = self.__initial_background_opacity
        self.foreground_color = self.__initial_foreground_color
        self.background_color = self.__initial_background_color
        self.canvas_dimensions = (window_width, window_height)
        self.image_for_thresholding = self.__initial_image_for_thresholding
        self.invert_thresholding = self.__initial_invert_thresholding
        self.erase_only_thresholding = self.__initial_erase_only_thresholding
        self.closing_after_thresholding = self.__initial_closing_after_thresholding
        self.active_settings_window = False

        # configure the grid layout of the window 
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)
        self.columnconfigure(2, weight=1)
        self.rowconfigure(1, weight=1)
        self.__occupied_width = 0

        # initialize the canvas widget
        self.canvas = CanvasImage(self)

        # initialize the widget with buttons for control and navigation
        self.control_buttons = ControlButtons(self)
        self.control_buttons.grid(row=0, column=0, padx=self.__padx, sticky='nsw')

        # initialize the widget with buttons to switch between layers
        self.layer_buttons = LayerButtons(self)
        self.layer_buttons.grid(row=0, column=1, padx=self.__padx, sticky='ns')

        # initialize the widget with buttons for annotating the image
        self.annotation_buttons = AnnotationButtons(self)
        self.annotation_buttons.grid(row=0, column=2, padx=self.__padx, sticky='nse')

        # aggregate the width for the control and annotation button frames
        for frame in [self.control_buttons.container, self.annotation_buttons.container]:
            frame.update()
            self.__occupied_width += (frame.winfo_width() + 3*self.__padx)

        # configure the layer buttons widget
        self.layer_buttons.configure()

        # add canvas to window
        self.canvas.grid(row=1, column=0, columnspan=3, sticky='nsew')
        self.canvas.load_image()
        self.layer_buttons.initialize_extra_buttons()

        # set the minimum height and width
        self.minsize(
            int(max(self.__occupied_width+self.layer_buttons.get_minimum_width(), 
                self.winfo_screenwidth()*self.canvas.get_min_zoom())), 
            int((self.winfo_screenheight()*self.canvas.get_min_zoom()) 
                + self.get_header_height())
        )
        # bind keypress and resizing events to methods
        self.bind('<KeyPress>', self.__keypress)
        self.bind('<Configure>', self.__resize_action)
        

    def __keypress(self, event: tkinter.Event) -> None:                                   
        """
        Perform an action that corresponds to a particular key press:
            <d>: Switch between inspection and drawing mode.
            <r>: Reset the view (zoom and location) to the default.
            <f>: Change the auto fill configuration.
            <z>: Undo annotation.
            <t>: Create annotation by thresholding the image.
            <v>: Change the visibility of the annotation.
            <c>: Clear the canvas with annotation.
            <s>: Save annotations as image(s).
        """
        if event.keysym_num == 100:  # <d>
            self.control_buttons.switch_mode()
        elif event.keysym_num == 114:  # <r>
            self.canvas.reset_view() 
        elif event.keysym_num == 118:  # <v>
            self.control_buttons.change_visibility()
        elif event.keysym_num == 65361:  # <LeftArrow>
            self.control_buttons.load_previous_image()
        elif event.keysym_num == 65363:  # <RightArrow>
            self.control_buttons.load_next_image()
        elif event.keysym_num == 110:  # <n>
            if self.add_layers:
                self.layer_buttons.switch_layer_wrapper(None, '+')
        elif event.keysym_num == 102:  # <f>
            self.annotation_buttons.change_auto_fill()
        elif event.keysym_num == 116:  # <t>
            self.canvas.threshold_image()
        elif event.keysym_num == 105:  # <i>
            self.canvas.invert_annotation()        
        elif event.keysym_num == 122:  # <z>
            self.canvas.undo_action()
        elif event.keysym_num == 99:  # <c>
            self.layer_buttons.clear_annotation_else_remove_button()
        elif event.keysym_num == 115:  # <s>
            self.canvas.save_annotations()
         

    def __resize_action(self, event: tkinter.Event) -> None:
        """
        Resize the canvas with image and the layer buttons in response to a 
        change in the window size.
        """     
        # first close the settings window if it is open
        if self.active_settings_window:
            self.annotation_buttons.settings_window.close_window()

        # if only the position of the window on screen changes, return early
        if event.width == self.winfo_width():
            if event.height == self.winfo_height():
                return
        # update the canvas dimensions
        self.canvas_dimensions = (
            self.winfo_width(), 
            self.winfo_height()-self.get_header_height()
        )
        # resize the layer buttons container
        self.layer_buttons.resize_canvas()


    def get_header_height(self) -> int:
        """ 
        Return the height of the header.
        """
        return self.control_buttons.container.winfo_height()


    def get_header_padding(self) -> int:
        """ 
        Return the height of the header.
        """
        return int(self.__padding_to_screen_height_ratio*self.winfo_screenheight())


    def get_available_width(self) -> float:
        """
        Return the available width for the layer buttons.
        """
        return self.winfo_width()-self.__occupied_width


class AnnotationTool:
    """
    Annotation tool setup class
    """

    def __init__(
        self, 
        input_paths: Union[str, Path, tuple, list], 
        layers: list[str], 
        output_directory: str = None,
        extension: str = 'tiff', 
        rotate_portrait: bool = True,
        add_layers: bool = True,
        autosave: bool = False,
        theme: str = 'light',
    ) -> None:
        """
        Initialize the main window for the annotation tool.
        
        Args:
            input_paths:  Path(s) to image(s) and optionally annotation(s).
            layers:  Names for all annotation layers.
            output_directory:  Directory for saving the annotations.
            extension:  Datatype for saving the annotation.
            rotate_portrait:  Indicates whether images in portrait mode are 
                rotated 90 degrees for annotation.
            add_layers:  Indicates whether extra layers for annotation can be 
                added by the user while annotating.
            autosave:  Indicates whether annotations are automatically saved 
                before going to the previous or next image.
            theme: Indicates whether the light or dark theme is used.
        """
        # format and check layer names
        if isinstance(layers, str):
            layers = [layers]
        elif isinstance(layers, (list, tuple)):
            layers = list(layers)
        else:
            raise ValueError('Invalid layer name(s).')
        if not len(layers):
            raise ValueError('No layer name(s) were provided.')
        # check if no layer is named "+"
        if '+' in layers:
            raise ValueError('Invalid layer name "+".')
        # check if no layer is named ""
        if '' in layers:
            raise ValueError('Invalid layer name "".')
        # check if all layer names are unique
        if len(set(layers)) != len(layers):
            raise ValueError('Atleast one layer name is not unique.')

        # format and check the image and annotation paths
        # e.g. 'image.png'
        if isinstance(input_paths, (str, Path)): 
            image_paths = [Path(input_paths)]
            annotation_paths = [None]
        elif isinstance(input_paths, (tuple, list)):
            image_paths = []
            annotation_paths = []
            # e.g. ['image.png', 'image2.png']
            for item in input_paths:
                if isinstance(item, (str, Path)): 
                    image_paths.append(Path(item))
                    annotation_paths.append(None)
                # e.g. [('image.png', None)], 
                # or   [('image2.png', 'image2_annotation-001.png')],
                # or   [('image3.png', 
                #        'image3_annotation-001-first.png', 
                #        'image3_annotation-001-second.png')]
                elif isinstance(item, (tuple, list)): 
                    # e.g. [('image.png', None)]
                    if (len(item) == 1) or (len(item) == 2 and item[1] is None):
                        if isinstance(item[0], (str, Path)): 
                            image_paths.append(Path(item[0]))
                            annotation_paths.append(None)
                        else:
                            raise TypeError('Invalid input argument datatype.')
                    # e.g. [('image2.png', 'image2_annotation-001.png')]
                    elif len(item) == 2 and item[1] is not None:
                        if isinstance(item[0], (str, Path)) and isinstance(item[1], (str, Path)):
                            image_paths.append(Path(item[0]))
                            annotation_paths.append(Path(item[1]))
                        else:
                            raise TypeError('Invalid input argument datatype.')
                    # e.g. [('image3.png', 'image3_annotation-001-first.png', 
                    #        'image3_annotation-001-second.png')]
                    else:
                        # check first whether any of the elements are not paths
                        for element in item:
                            if not isinstance(element, (str, Path)):
                                raise TypeError('Invalid input argument datatype.')
                        # if all are paths, add them to the storage
                        image_paths.append(Path(item[0]))
                        annotation_paths.append([Path(path) for path in item[1:]])
                else:
                    raise TypeError('Invalid input argument datatype.')
        else:
            raise TypeError('Invalid input argument datatype.')    

        # format and check the extension type
        extension = extension.lower()
        while len(extension) > 0 and extension[0] == '.':
            extension = extension[1:]
        
        if len(extension) == 0:
            raise ValueError('Invalid argument for annotation file extension.')

        # initialize the window
        self.__window = MainWindow(image_paths, annotation_paths, output_directory, 
                                   extension, layers, rotate_portrait, add_layers, 
                                   autosave, theme)
        # bind closing event to method
        self.__window.protocol("WM_DELETE_WINDOW", self.__on_close)
        # start the mainloop
        self.__window.after(10, self.__window.canvas.reset_view)
        self.__window.mainloop()


    def __on_close(self) -> None:
        """
        If autosave is active, save the annotations before closing.
        Destroy the window afterwards.
        """
        if self.__window.autosave: 
            self.__window.canvas.save_annotations(check_buffer=True)
        self.__window.destroy()