#!/usr/bin/env python3
import argparse
import functools
import sys
import logging
from datetime import datetime
from pathlib import Path
from pprint import pprint
from tempfile import TemporaryDirectory
from typing import Dict, Iterable, List, NamedTuple, Optional, Any

from kython.klogging import LazyLogger, setup_logzero

import fastkml as K # type: ignore
import webcolors # type: ignore
from shapely.geometry import Point # type: ignore


logger = LazyLogger('fsq2gmaps')

LONDON = [51.538, -0.14]


@functools.lru_cache(1)
def get_4sq_api():
    from config import TOKEN
    import foursquare # type: ignore
    api = foursquare.Foursquare(access_token=TOKEN)
    return api


def get_4sq_lists(): # TODO eh, should get local?
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


# TODO move to config?
INTERESTING = {
    'my saved places': 'red',
    'my liked places': 'pink',
    'london-food': None,
    'london': 'blue',
    'london-todo': 'red',
}


class Place(NamedTuple):
    lst: str
    jvenue: Any
    color: Optional[str]=None

    @property
    def name(self) -> str:
        return self.jvenue['name']

    @property
    def address(self) -> str:
        return ' '.join(self.jvenue['location'].get('formattedAddress', []))

    @property
    def lat(self):
        return self.jvenue['location']['lat']

    @property
    def lng(self):
        return self.jvenue['location']['lng']

    @property
    def description(self) -> str:
        return f"{self.name}\n{self.address}\nList: {self.lst}"


# TODO use layers?
def gen_places() -> Iterable[Place]:
    api = get_4sq_api()
    lists = get_4sq_lists()

    for lname, lst in lists.items():
        if lname not in INTERESTING:
            logger.info('skipping list %s', lname)
            continue
        # TODO warn about unused??
        color = INTERESTING[lname]

        print(f"Scanning list: {lst['name']}")
        ldet = api.lists(lst['id']) # pylint: disable=no-member
        # TODO get all of them, might hit the limit
        items = ldet['list']['listItems']['items']
        print(f"{len(items)} items")

        for item in items:
            venue = item['venue']
            yield Place(
                lst=lst['name'],
                jvenue=venue,
                color=color,
            )


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
def _get_kml(items):
    kml = KmlMaker()
    from kython import group_by_key
    for lname, places in group_by_key(items, key=lambda p: p.lst).items():
        color = places[0].color
        style_url = None if color is None else kml.make_icon_style(color=color)
        marks = []
        for p in places:
            pm = K.Placemark(
                id=p.name,
                name=p.name,
                description=p.description,
                styleUrl=style_url,
            )
            pm.geometry = Point(p.lng, p.lat)
            marks.append(pm)
        kml.add_folder(
            name=lname,
            items=marks,
        )

    ss = kml.to_string(prettyprint=True)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ss


def get_kml():
    return _get_kml(gen_places())


def get_test_places():
    return [
        Place(
            lst='whatever',
            jvenue={
                'location': {
                    'formattedAddress': ['London', 'UK', 'Shoreditch'],
                    'lat': 11.123,
                    'lng': 0.4,
                },
                'name': 'Some place',
            },
        )
    ]




def _get_map(places):
    def style_list(lname, color):
        if color is None:
            return lname
        else:
            return f'<span style="color:{color}">{lname}</span>'

    callback = """
function (row) {
    const [lat, lon, color, tooltip, popup] = row;
    // const marker = L.marker(
    //     new L.LatLng(lat, lon),
    //     {
    //         color: color,
    //     },
    // );
    const marker = L.circleMarker(
        new L.LatLng(lat, lon),
        {radius: 7,
         color: color,
         fill: true,
         fill_color: color,
       }
    );
    marker.bindPopup(popup);
    marker.bindTooltip(tooltip, {permanent: true});
    //  TODO get url from 4sq?
    return marker;
};
"""
    params = []
    for p in places:
        tooltip = p.name + ' ' + style_list(p.lst, p.color)
        popup = '<br>'.join(p.description.splitlines())
        params.append([p.lat, p.lng, p.color, tooltip, popup])

    import folium # type: ignore
    from folium import plugins as fplugins
    fmap = folium.Map(location=LONDON) # TODO perhaps extract in my.geo or something?
    cluster = fplugins.FastMarkerCluster(
        params,
        callback=callback,
    ).add_to(fmap)
    fplugins.Fullscreen().add_to(fmap)


    legend_parts = []
    for lname, color in INTERESTING.items():
        legend_parts.append(style_list(lname, color))

    # https://medium.com/@bobhaffner/creating-a-legend-for-a-folium-map-c1e0ffc34373
    legend_html = f"""
     <div style=”position: fixed;
     bottom: 50px; left: 50px; width: 100px; height: 90px;
     border:2px solid grey; z-index:9999; font-size:14px;
     “>&nbsp; Legend: {' '.join(legend_parts)}
     </div>
     """

    fmap.get_root().html.add_child(folium.Element(legend_html))
    return fmap


def test_get_map():
    with TemporaryDirectory() as td:
        mm = Path(td) / 'map.html'
        places = get_test_places()
        _get_map(places).save(str(mm))


def test_get_kml():
    places = get_test_places()
    _get_kml(places)

def get_map():
    places = list(gen_places())
    # places = []
    return _get_map(places)


def main():
    setup_logzero(logger, level=logging.INFO)
    pa = argparse.ArgumentParser()
    pa.add_argument('--kml', type=Path)
    pa.add_argument('--map', type=Path)
    args = pa.parse_args()

    if args.kml is not None:
        args.kml.write_text(get_kml())
        logger.info('file to upload: %s', args.kml)
    elif args.map is not None:
        fmap = get_map()
        fmap.save(str(args.map))
        logger.info('saved map: %s', args.map)
    else:
        raise RuntimeError(args)


if __name__ == '__main__':
    main()
