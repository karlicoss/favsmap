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
from shapely.geometry import Point # type


class KmlMaker:
    NS = '{http://www.opengis.net/kml/2.2}'

    def __init__(self) -> None:
        self.kml = K.KML()
        self.doc = K.Document(
            ns=KmlMaker.NS,
            id='docid',
            name='doc name',
            description='doc description'
        )
        self.kml.append(self.doc)


    def make_Style(self, **kwargs):
        return K.Style(
            # ns=KmlMaker.NS,
            **kwargs
        )

    def make_IconStyle(self, **kwargs):
        return K.IconStyle(
            # ns=KmlMaker.NS,
            **kwargs
        )

    # TODO is ns really necessary?
    def make_StyleMap(self, **kwargs):
        return K.StyleMap(
            # ns=KmlMaker.NS,
            **kwargs
        )

    def _get_color(self, color: str):
        # ugh, it's aabbggrr for some reason..
        import webcolors # type: ignore
        (rr, gg, bb) = webcolors.name_to_rgb(color)
        return "ff{:02x}{:02x}{:02x}".format(bb, gg, rr)

    def make_icon_style(self, name: str, color: str='red') -> str:
        style_id = f"style-{name}"
        style = self.make_Style(
            id=style_id,
            styles=[
                self.make_IconStyle(
                    icon_href="http://www.gstatic.com/mapspro/images/stock/503-wht-blank_maps.png",
                    # TODO ugh, it's aabbggrr
                    color=self._get_color(color),
                ),
            ],
        )
        self.doc.append_style(style)

        style_map = self.make_StyleMap(
            id=style_id,
            normal=K.StyleUrl(url=f"#{style_id}"),
            highlight=K.StyleUrl(url=f"#{style_id}"),
        )
        self.doc.append_style(style_map)
        return f'#{style_id}'

    def add_folder(self, name: str, items: List):
        folder = K.Folder(
            id=name, # TODO 
            name=name
        )
        for i in items:
            folder.append(i)
        self.doc.append(folder)

    def to_string(self, **kwargs) -> str:
        if 'prettyprint' not in kwargs:
            kwargs['prettyprint'] = True
        return self.kml.to_string(**kwargs)

# TODO generate each color
# TODO nicer, declarative DSL for building that crap
def build_kml() -> KmlMaker:
    # Create the root KML object
    kml = KmlMaker()
    style_url = kml.make_icon_style(name='blue', color='blue')

    for lname in INTERESTING:
        # Create a KML Folder and add it to the Document
        marks = []
        for p in gen_places(lmap[lname]):
            pm = K.Placemark(
                id=p.name,
                name=p.name,
                description=p.address,
                styleUrl=style_url,
            )
            pm.geometry = Point(p.lon, p.lat)
            marks.append(pm)
        kml.add_folder(
            name=lname,
            items=marks,
        )

    return kml


kml = build_kml()


with open("res.kml", 'w') as fo:
    import sys
    sys.stdout.write(kml.to_string(prettyprint=True))
    fo.write(kml.to_string(prettyprint=True))
