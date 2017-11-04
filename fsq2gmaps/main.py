#!/usr/bin/env python3.6
from config import TOKEN
import foursquare # type: ignore

from kython import *

api = foursquare.Foursquare(access_token=TOKEN)

import csv
from pprint import pprint
import sys

lists = api.users.lists()['lists']['groups'][1]['items']

# TODO use favorites too
lmap = {l['name'].lower(): l for l in lists}

print("LISTS:")
for k in lmap:
    print(k)


class Place(NamedTuple):
    lst: str
    name: str
    address: str
    lat: float
    lon: float

# TODO use layers?
def gen_places(lst) -> Iterable[Place]:
    print(f"Scanning list: {lst['name']}")
    ldet = api.lists(lst['id'])
    # TODO get all of them, might hit the limit
    items = ldet['list']['listItems']['items']
    print(f"{len(items)} items")

    for item in items:
        venue = item['venue']
        yield Place(
            lst=lst['name'],
            name=venue['name'],
            address=venue['location']['address'],
            lat=venue['location']['lat'],
            lon=venue['location']['lng'],
        )


def gen_all_places():
    for lname in ('london-todo', 'london-food', 'london'):
        for p in gen_places(lmap[lname]):
            yield p

INTERESTING = ('london-todo', 'london-food', 'london',)

def get_color(s: str):
    hash(s)

# pip install fastkml, shapely
import fastkml # type: ignore
K = fastkml
from shapely.geometry import Point

# TODO generate each color
# TODO nicer, declarative DSL for building that crap
def build_kml():
    # Create the root KML object
    kml = K.KML()
    ns = '{http://www.opengis.net/kml/2.2}'
    
    # Create a KML Document and add it to the KML root object
    doc = K.Document(ns, 'docid', 'doc name', 'doc description')

    style = K.Style(ns=ns, id="red-normal")
    # TODO ugh, it's aabbggrr
    red = K.styles.IconStyle(ns=ns, color="ff000000")
    red.icon_href = "http://www.gstatic.com/mapspro/images/stock/503-wht-blank_maps.png"
    # TODO ugh, do I really ned url here?
    style.append_style(red)
    doc.append_style(style)

    style_map = K.StyleMap(
        ns=ns,
        id="style-red",
    )
    style_map.normal = K.StyleUrl(ns=ns, url="#red-normal")
    style_map.highlight = K.StyleUrl(ns=ns, url="#red-normal")
    doc.append_style(style_map)


    for lname in INTERESTING:
        # Create a KML Folder and add it to the Document
        folder = K.Folder(ns=ns, id='fid', name=lname)
        for p in gen_places(lmap[lname]):
            pm = K.Placemark(ns=ns, id='id', name=p.name, description=p.address)
            pm.geometry = Point(p.lon, p.lat)
            pm.styleUrl = f"#style-red"
            folder.append(pm)
        doc.append(folder)

    kml.append(doc)
    return kml


kml = build_kml()


with open("res.kml", 'w') as fo:
    import sys
    sys.stdout.write(kml.to_string(prettyprint=True))
    fo.write(kml.to_string(prettyprint=True))

raise RuntimeError
with open("res.csv", 'w') as fo:
    writer = csv.DictWriter(fo, fieldnames=[
        "Name",
        "Address",
        "Latitude",
        "Longitude",
        "Color",
    ])
    writer.writeheader()
    for p in gen_all_places():
        writer.writerow(p)
