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

# TODO use layers?
def gen_places(lst) -> Iterable[Dict[str, str]]:
    pprint(lst)
    ldet = api.lists(lst['id'])
    pprint(ldet)
    # TODO get all of them, might hit the limit
    items = ldet['list']['listItems']['items']
    pprint(len(items))

    for item in items:
        venue = item['venue']
        yield {
            "Name": venue['name'],
            "Address": venue['location']['address'],
            "Latitude": venue['location']['lat'],
            "Longitude": venue['location']['lng'],
        }


def gen_all_places():
    for lname in ('london-todo', 'london-food', 'london'):
        for p in gen_places(lmap[lname]):
            yield p

with open("res.csv", 'w') as fo:
    writer = csv.DictWriter(fo, fieldnames=[
        "Name",
        "Address",
        "Latitude",
        "Longitude"
    ])
    writer.writeheader()
    for p in gen_all_places():
        writer.writerow(p)
