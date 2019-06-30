#!/usr/bin/env python3
import argparse
import functools
import sys
from datetime import datetime
from pathlib import Path
from pprint import pprint
from typing import Dict, Iterable, List, NamedTuple, Optional

import fastkml as K
import webcolors
from shapely.geometry import Point


@functools.lru_cache(1)
def get_4sq_api():
    from config import TOKEN
    import foursquare # type: ignore
    api = foursquare.Foursquare(access_token=TOKEN)
    return api


def get_4sq_data(): # TODO eh, should get local?
    api = get_4sq_api()
    lists = api.users.lists() # pylint: disable=no-member

    def_lists = lists['lists']['groups'][0]['items']
    user_lists = lists['lists']['groups'][1]['items']

    all_lists = def_lists + user_lists
    lmap = {l['name'].lower(): l for l in all_lists}

    print("LISTS:")
    for k in lmap:
        print(k)
    # TODO use favorites too
    return lmap


class Place(NamedTuple):
    lst: str
    name: str
    address: str
    lat: float
    lon: float

# TODO use layers?
def gen_places(lst) -> Iterable[Place]:
    api = get_4sq_api()
    print(f"Scanning list: {lst['name']}")
    ldet = api.lists(lst['id']) # pylint: disable=no-member
    # TODO get all of them, might hit the limit
    items = ldet['list']['listItems']['items']
    print(f"{len(items)} items")

    for item in items:
        venue = item['venue']
        yield Place(
            lst=lst['name'],
            name=venue['name'],
            address=venue['location'].get('address', 'NO ADDRESS!'),
            lat=venue['location']['lat'],
            lon=venue['location']['lng'],
        )


# TODO move to config?
INTERESTING = {
    'my saved places': 'red',
    'my liked places': 'pink',
    # 'london-food': None,
    'london': 'blue',
    'london-todo': 'red',
}


# TODO er... whre is it coming from?
class KmlMaker:
    NS = '{http://www.opengis.net/kml/2.2}'

    def __init__(self) -> None:
        self.kml = K.KML()
        self.doc = K.Document(
            ns=KmlMaker.NS,
            id='docid',
            name=f'foursquare-{datetime.now().strftime("%Y%m%d")}',
            description='Foursquare lists',
        )
        self.color2style: Dict[str, str] = {}
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
        (rr, gg, bb) = webcolors.name_to_rgb(color)
        return "ff{:02x}{:02x}{:02x}".format(bb, gg, rr)

    def _add_style(self, color: str):
        style_id = f"style-{color}"
        style_url = f"#{style_id}"
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
            normal=K.StyleUrl(url=style_url),
            highlight=K.StyleUrl(url=style_url),
        )
        self.doc.append_style(style_map)

        self.color2style[color] = style_url

    def make_icon_style(self, color: str) -> Optional[str]:
        if color not in self.color2style:
            self._add_style(color)
        return self.color2style.get(color)

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
    lmap = get_4sq_data()
    kml = KmlMaker()
    for lname, color in INTERESTING.items():
        style_url = None if color is None else kml.make_icon_style(color=color)
        marks = []
        for p in gen_places(lmap[lname]):
            pm = K.Placemark(
                id=p.name,
                name=p.name,
                description=f"List: {lname}\n{p.address}",
                styleUrl=style_url,
            )
            pm.geometry = Point(p.lon, p.lat)
            marks.append(pm)
        kml.add_folder(
            name=lname,
            items=marks,
        )

    return kml


def get_kml() -> str:
    kml = build_kml()
    ss = kml.to_string(prettyprint=True)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ss


def main():
    pa = argparse.ArgumentParser()
    pa.add_argument('--kml', type=Path)
    pa.add_argument('--map', type=Path)
    args = pa.parse_args()

    if args.kml is not None:
        args.kml.write_text(get_kml())
        print(f"File to upload:\n{args.kml}")
    elif args.map is not None:
        pass
    else:
        raise RuntimeError(args)


if __name__ == '__main__':
    main()
