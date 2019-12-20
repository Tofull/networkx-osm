#!/usr/bin/env python3
# -*- coding=utf-8 -*-

"""This example shows you how to download Openstreetmap data and convert those data to a networkx directional graph.
"""

import pathlib
import sys

import matplotlib.pyplot as plt
import networkx as nx

root_folder = pathlib.Path(__file__).parent / '..'
root_folder = root_folder.resolve()

sys.path.append(root_folder.as_posix())

import OSMParser as osmp

# Prepare paths
data_folder = root_folder / 'data'

temp_folder = data_folder / 'temp'
local_osm_file = data_folder / 'saved_local_osm_data.map'
output_shp_folder = data_folder / 'output_shp'

# Download OSM file
osm_map_file_content = osmp.download_osm(left=-73.4244, bottom=45.4302, right=-73.4010, top=45.4466, cache=True, cacheTempDir=temp_folder.as_posix())

# Convert OSM file to networkx graph
graph = osmp.read_osm(osm_map_file_content)

# Display graph on matplotlib figure
nx.draw(graph)
plt.show()

# You could also store the osm response to a file for further processing
with open(local_osm_file.as_posix(), 'w') as f:
    f.write(osm_map_file_content)
