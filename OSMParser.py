"""
Convert a Open Street Maps `.map` format file into a networkx directional graph.

This parser is based on the osm to networkx tool from aflaxman : https://gist.github.com/aflaxman/287370/


Added :
- python3.6 compatibility
- networkx v2 compatibility
- cache to avoid downloading the same osm tiles again and again
- distance computation to estimate length of each ways (useful to compute the shortest path)

Copyright (C) 2017 Loïc Messal (github : Tofull)

"""

import copy
import urllib.request
import xml.sax
from math import radians, cos, sin, asin, sqrt
from pathlib import Path

import networkx


def haversine_distance(lon1, lat1, lon2, lat2, unit_m=True):
    """
    Calculate the great circle distance between two points
    on the earth (specified in decimal degrees)
    default unit : km
    """
    # convert decimal degrees to radians
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])

    # haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
    c = 2 * asin(sqrt(a))
    r = 6371  # Radius of the Earth in kilometers. Use 3956 for miles
    if unit_m:
        r *= 1000
    return c * r


def download_osm(left=-73.4244, bottom=45.4302, right=-73.4010, top=45.4466, proxy=False, proxyHost="10.0.4.2", proxyPort="3128", cache=False, cacheTempDir="/tmp/tmpOSM/", verbose=True):
    """ Return a filehandle to the downloaded data from osm api."""
    if cache:
        # cached tile filename
        cachedTileFilename = "osm_map_{:.8f}_{:.8f}_{:.8f}_{:.8f}.map".format(left, bottom, right, top)

        if verbose:
            print("Cached tile filename :", cachedTileFilename)

        cacheTempDir = Path(cacheTempDir)
        cacheTempDir.mkdir(parents=True, exist_ok=True)  # Create cache path if not exists

        osmFile = Path(cacheTempDir / cachedTileFilename).resolve()  # Replace the relative cache folder path to absolute path

        if osmFile.is_file():
            # download from the cache folder
            if verbose:
                print("Tile loaded from the cache folder.")

            with open(osmFile, mode='r') as f:
                content = f.read()
            return content

    if proxy:
        # configure the urllib request with the proxy
        proxy_handler = urllib.request.ProxyHandler({'https': 'https://' + proxyHost + ":" + proxyPort, 'http': 'http://' + proxyHost + ":" + proxyPort})
        opener = urllib.request.build_opener(proxy_handler)
        urllib.request.install_opener(opener)

    request = "http://api.openstreetmap.org/api/0.6/map?bbox=%f,%f,%f,%f" % (left, bottom, right, top)

    if verbose:
        print("Download the tile from osm web api ... in progress")
        print("Request :", request)

    fp = urllib.request.urlopen(request)
    content = fp.read().decode('utf-8')

    if verbose:
        print("OSM Tile downloaded")

    if cache:
        if verbose:
            print("Write osm tile in the cache")

        with open(osmFile, 'w') as f:
            f.write(content)

        if osmFile.is_file():
            if verbose:
                print("OSM tile written in the cache")

    return content


def read_osm(osm_xml_data, is_xml_string=True, only_roads=True):
    """Read graph in OSM format from file specified by name or by stream object.
    Parameters
    ----------
    filename_or_stream : filename or stream object

    Returns
    -------
    G : Graph

    Examples
    --------
    >>> G=nx.read_osm(nx.download_osm(-122.33,47.60,-122.31,47.61))
    >>> import matplotlib.pyplot as plt
    >>> plt.plot([G.node[n]['lat']for n in G], [G.node[n]['lon'] for n in G], 'o', color='k')
    >>> plt.show()
    """
    osm = OSM(osm_xml_data, is_xml_string=is_xml_string)
    G = networkx.DiGraph()

    ## Add ways
    for w in osm.ways.values():
        if only_roads and 'highway' not in w.tags:
            continue

        if ('oneway' in w.tags):
            if (w.tags['oneway'] == 'yes'):
                # ONLY ONE DIRECTION
                networkx.add_path(G, w.nds, id=w.id)
            else:
                # BOTH DIRECTION
                networkx.add_path(G, w.nds, id=w.id)
                networkx.add_path(G, w.nds[::-1], id=w.id)
        else:
            # BOTH DIRECTION
            networkx.add_path(G, w.nds, id=w.id)
            networkx.add_path(G, w.nds[::-1], id=w.id)

    # Complete the used nodes' information
    coordinates_map = {}
    for n_id in G.nodes():
        n = osm.nodes[n_id]
        G.nodes[n_id]['lat'] = n.lat
        G.nodes[n_id]['lon'] = n.lon
        G.nodes[n_id]['id'] = n.id
        coordinates_map[n_id] = (n.lon, n.lat)

    # Estimate the length of each way
    for u, v, d in G.edges(data=True):
        distance = haversine_distance(G.nodes[u]['lon'], G.nodes[u]['lat'], G.nodes[v]['lon'], G.nodes[v]['lat'], unit_m=True)  # Give a realistic distance estimation (neither EPSG nor projection nor reference system are specified)

        G.add_weighted_edges_from([(u, v, distance)], weight='havlen')

    G = networkx.relabel_nodes(G, coordinates_map)
    return G


class Node(object):
    def __init__(self, id, lon, lat):
        self.id = id
        self.lon = lon
        self.lat = lat
        self.tags = {}

    def __str__(self):
        return "Node (id : %s) lon : %s, lat : %s "%(self.id, self.lon, self.lat)


class Way(object):
    def __init__(self, id, osm):
        self.osm = osm
        self.id = id
        self.nds = []
        self.tags = {}

    def split(self, dividers):
        # slice the node-array using this nifty recursive function
        def slice_array(ar, dividers):
            for i in range(1,len(ar)-1):
                if dividers[ar[i]]>1:
                    left = ar[:i+1]
                    right = ar[i:]

                    rightsliced = slice_array(right, dividers)

                    return [left]+rightsliced
            return [ar]

        slices = slice_array(self.nds, dividers)

        # create a way object for each node-array slice
        ret = []
        i = 0
        for slice in slices:
            littleway = copy.copy(self)
            littleway.id += "-%d" % i
            littleway.nds = slice
            ret.append(littleway)
            i += 1

        return ret


class OSM(object):
    def __init__(self, osm_xml_data, is_xml_string=True):
        """ File can be either a filename or stream/file object.

        set `is_xml_string=False` if osm_xml_data is a filename or a file stream.
        """
        nodes = {}
        ways = {}

        superself = self

        class OSMHandler(xml.sax.ContentHandler):
            @classmethod
            def setDocumentLocator(self, loc):
                pass

            @classmethod
            def startDocument(self):
                pass

            @classmethod
            def endDocument(self):
                pass

            @classmethod
            def startElement(self, name, attrs):
                if name == 'node':
                    self.currElem = Node(attrs['id'], float(attrs['lon']), float(attrs['lat']))
                elif name == 'way':
                    self.currElem = Way(attrs['id'], superself)
                elif name == 'tag':
                    self.currElem.tags[attrs['k']] = attrs['v']
                elif name == 'nd':
                    self.currElem.nds.append(attrs['ref'])

            @classmethod
            def endElement(self, name):
                if name == 'node':
                    nodes[self.currElem.id] = self.currElem
                elif name == 'way':
                    ways[self.currElem.id] = self.currElem

            @classmethod
            def characters(self, chars):
                pass

        if is_xml_string:
            xml.sax.parseString(osm_xml_data, OSMHandler)
        else:
            with open(osm_xml_data, mode='r') as f:
                xml.sax.parse(f, OSMHandler)

        self.nodes = nodes
        self.ways = ways

        # count times each node is used
        node_histogram = dict.fromkeys(self.nodes.keys(), 0)
        for way in self.ways.values():
            if len(way.nds) < 2:  # if a way has only one node, delete it out of the osm collection
                del self.ways[way.id]
            else:
                for node in way.nds:
                    node_histogram[node] += 1

        # use that histogram to split all ways, replacing the member set of ways
        new_ways = {}
        for id, way in self.ways.items():
            split_ways = way.split(node_histogram)
            for split_way in split_ways:
                new_ways[split_way.id] = split_way
        self.ways = new_ways
