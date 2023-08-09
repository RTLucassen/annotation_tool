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

"""
Implementation of helper class and functions
"""

from pathlib import Path
from typing import Any

import numpy as np
import SimpleITK as sitk 


class Buffer:
    """
    Keeps items in memory in case changes must be reverted.
    """

    def __init__(self, maximum_buffer: int) -> None:
        """
        Initialize the buffer.
        
        Args:
            maximum_buffer: number of items that can be stored in the buffer.
        """
        # initialize instance attributes
        self.__buffer = []
        self.__maximum_buffer = maximum_buffer
    
    def __len__(self):
        return len(self.__buffer)

    def add(self, item: Any, category: str) -> None:
        """
        Add a new item to the buffer and assign it to a specific category. 
        Remove the oldest item if the size exceeds the maximum buffer threshold.

        Args:
            item: object to be added to the buffer.
            category: name of category.
        """
        # add item to buffer
        self.__buffer.append((item, category))
        # remove earliest items if the buffer exceeds the maximum size
        while len(self.__buffer) > self.__maximum_buffer:
            self.__buffer = self.__buffer[1:]

    def get(self, selected_category: str) -> None:
        """ 
        Get the last added item from a specific category of the buffer. 
        """
        # return last added item, or None if there are no items in the buffer
        if len(self.__buffer) == 0:
            return None
        else:
            for i in range(1, (len(self.__buffer)+1)):
                if self.__buffer[-i][1] == selected_category:
                    return self.__buffer.pop(-i)[0]
            return None
    
    def clear(self) -> None:
        self.__buffer = []


class LayerTracker:
    """
    Keeps track of layers.
    """

    def __init__(self, defined_layers: list) -> None:
        """
        Initializes the layer tracker.
        """
        self.__defined_layers = list(defined_layers)
        self.__extra_layers = []
        self.__count = 0
        self.__combine_lists()
    
    def __len__(self) -> int:
        return len(self.__defined_layers)+len(self.__extra_layers)
    
    def __getitem__(self, key: int) -> str:
        return self.__all_layers[key]
    
    def __add__(self, items: list) -> list:
        return self.__all_layers+items

    def __combine_lists(self):
        self.__all_layers = self.__defined_layers+self.__extra_layers

    def index(self, layer) -> int:
        return self.__all_layers.index(layer)
    
    @property
    def defined(self) -> list:
        return self.__defined_layers

    @property
    def extra(self) -> list:
        return self.__extra_layers

    def add_extra_layer(self) -> str:
        """
        Adds extra layer with lowest number that is currently not used.
        """
        self.__count += 1
        layer = f'{self.__count}'
        self.__extra_layers.append(layer)
        self.__combine_lists()

        return layer

    def remove_extra_layer(self, layer) -> None:
        self.__extra_layers.remove(layer)
        self.__combine_lists()

    def remove_extra_layers(self) -> None:
        self.__count = 0
        self.__extra_layers = []
        self.__combine_lists()
        

def create_color_matrix(color: list, opacity: float) -> tuple[float]:
    """
    Create color matrix for PIL RGB conversion.
    
    Args:
        color: color values for R, G, and B channel between 0 and 1.
        opacity: opacity value between 0 and 1.
    
    Returns:
        color_matrix: color matrix with RGB conversion information.
    """
    # define color matrix
    color_matrix = (
        1-opacity, 0.0, 0.0, color[0]*255*opacity,          
        0.0, 1-opacity, 0.0, color[1]*255*opacity,
        0.0, 0.0, 1-opacity, color[2]*255*opacity,
    )
    return color_matrix

def save_image(
    image: np.ndarray, 
    directory: Path, 
    filename: str,
    version: int,
    addon: str, 
    extension: str,
) -> None:
    """
    Save numpy array as an image in the specified directory.
    
    Args:
        image: image data.
        directory: path to folder where the image should be saved.
        filename: filename of the image.
        version: integer indicating the new version (latest existing version +1).
        addon: added to filename, not considered in determining the version.
        extension: indicates the image datatype for saving the annotations.
    """
    # construct the full name
    if addon in [None, '']:
        full_name = f'{filename}-{str(version).zfill(3)}.{extension}'
    else:
        full_name = f'{filename}-{str(version).zfill(3)}-{addon}.{extension}'

    # form the path and save the image
    path = directory / full_name
    sitk.WriteImage(sitk.GetImageFromArray(image), path)
    
    return path


def get_hex_color(color: list[float]) -> str:
    """
    Convert list with RGB color values between 0 and 1 
    to the hexadecimal color notation.
    """
    hexadecimal_color = '#'
    for value in color:
        hexadecimal_color += (hex(int(value*255))[2:]).zfill(2)
    
    return hexadecimal_color