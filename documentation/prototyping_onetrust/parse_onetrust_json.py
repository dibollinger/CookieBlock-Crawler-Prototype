# Copyright (C) 2021-2022 Dino Bollinger, ETH Zürich, Information Security Group
# Licensed under BSD 3-Clause License, see included LICENSE file
"""
Parse the OneTrust javascript/json document, variant 1 or variant 2.

Usage:
    parse_onetrust_json.py (--v1 | --v2) <file>

Options:
    --v1        Parse variant 1 json formatting.
    --v2        Parse variant 2 json formatting.
    -h --help   Show this printout.
"""

import re
import sys
from ast import literal_eval
from enum import Enum
from docopt import docopt
from typing import Dict, Set, Any
import json


class CookieCategories(Enum):
    NECESSARY = 0
    PERFORMANCE = 1
    FUNCTIONAL = 2
    TARGETING = 3
    SOCIAL_MEDIA = 4
    ANALYTICAL = 5
    ADVERTISEMENT = 6
    PERSONAL_DATA_SALE = 7
    UNCATEGORIZED = -1
    UNRECOGNIZED = -2

def category_lookup_en(cat_name):
    if cat_name == "Strictly Necessary Cookies": return CookieCategories.NECESSARY
    elif cat_name == "Performance Cookies": return CookieCategories.PERFORMANCE
    elif cat_name == "Functional Cookies": return CookieCategories.FUNCTIONAL
    elif cat_name == "Targeting Cookies": return CookieCategories.TARGETING
    elif cat_name == "Social Media Cookies": return CookieCategories.SOCIAL_MEDIA
    elif cat_name == "Uncategorised cookies": return CookieCategories.UNCATEGORIZED
    elif cat_name == "Anonymised analytical cookies": return CookieCategories.ANALYTICAL
    elif cat_name == "Personalized Advertisements": return CookieCategories.ADVERTISEMENT
    elif cat_name == "Sale of Personal Data": return CookieCategories.PERSONAL_DATA_SALE
    else: return CookieCategories.UNRECOGNIZED


cc_map: Dict[CookieCategories, Set[str]] = dict()
for c in CookieCategories:
    cc_map[c] = set()

cookie_lookup : Dict[str, Dict] = dict()


def parse_cookie_dict(cat_id: CookieCategories, cookie_dat: Dict[str, Any]):
    c_name = cookie_dat["Name"]
    if c_name not in cc_map:
        cc_map[cat_id].add(c_name)
        cookie_lookup[c_name] = cookie_dat
    else:
        for k, c in cookie_dat.items():
            if not cookie_lookup[cookie_dat["Name"]][k] == c:
                print("Duplicate Cookie entry found with mismatched contents!")
                break
        else:
            print("Matching Duplicate Cookie Entry found.")


def parse_variant1(json_data: Dict[str, Any]):
    json_body = json_data["DomainData"]

    if "en" in json_body["Language"]["Culture"]:
        cat_lookup = category_lookup_en
    else:
        raise ValueError("Illegal Language")

    group_list = json_data["DomainData"]["Groups"]
    for g_contents in group_list:
        cat_name = g_contents["GroupName"]
        cat_id = cat_lookup(cat_name)
        firstp_cookies = g_contents["FirstPartyCookies"]
        for cookie_dat in firstp_cookies:
            parse_cookie_dict(cat_id, cookie_dat)

        thirdp_cookies = g_contents["Hosts"]
        for host_dat in thirdp_cookies:
            for cookie_dat in host_dat["Cookies"]:
                parse_cookie_dict(cat_id, cookie_dat)


def parse_variant2(json_data: Dict[str, Any]):

    if "en" in json_data["Language"]["Culture"]:
        cat_lookup = category_lookup_en
    else:
        raise ValueError("Illegal Language")

    g_data = json_data["Groups"]
    for g_contents in g_data:
        if g_contents["Parent"] == "null":
            #print(g_contents["GroupLanguagePropertiesSets"])
            cat_name = g_contents["GroupLanguagePropertiesSets"][0]["GroupName"]["Text"]
        else:
            cat_name = g_contents["Parent"]["GroupLanguagePropertiesSets"][0]["GroupName"]["Text"]
        cat_id = cat_lookup(cat_name)
        for cookie_dat in g_contents["Cookies"]:
            parse_cookie_dict(cat_id, cookie_dat)


def main():

    args = docopt(__doc__)

    with open(args["<file>"], 'r') as fd:
        json_data = json.load(fd)


    if args["--v1"]:
        parse_variant1(json_data)
    elif args["--v2"]:
        parse_variant2(json_data)


    for cat in CookieCategories:

        print("==============================\n"
             f"Category: {cat}\n"
              "==============================")
        cookie_names = cc_map[cat]

        if len(cookie_names) == 0:
            print("Empty")

        for c_name in sorted(cookie_names):
            cookie_dat = cookie_lookup[c_name]
            print(f"cookie name:   {cookie_dat['Name']}")
            print(f"source:        {cookie_dat['Host']}")
            print(f"session?:      {cookie_dat['IsSession']}")
            print(f"expiry:        {cookie_dat['Length']}")
            if ('description' in cookie_dat):
                print(f"description:   {cookie_dat['description']}")
            print(f"--------------")


if __name__ == "__main__":
    main()
