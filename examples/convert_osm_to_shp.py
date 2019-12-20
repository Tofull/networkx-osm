#!/usr/bin/env python3
# -*- coding=utf-8 -*-

"""This example shows you how to convert OSM data into a shapefile file
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
local_osm_file = data_folder / 'saved_local_osm_data.map'
output_shp_folder = data_folder / 'output_shp'

# Load the osm data from a file
graph = osmp.read_osm(local_osm_file.as_posix(), is_xml_string=False)

# Convert the graph into shapefile format
nx.readwrite.nx_shp.write_shp(graph, output_shp_folder.as_posix())
print("OSM data is now available in shp format at : %s" % output_shp_folder.as_posix())
