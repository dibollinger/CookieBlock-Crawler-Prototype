# Copyright (C) 2021-2022 Dino Bollinger, ETH Zürich, Information Security Group
# Licensed under BSD 3-Clause License, see included LICENSE file
"""Parse the cookiebot cc.js file.

Usage: parse_cb_js.py <file>"""

import re
import sys
from ast import literal_eval
from enum import Enum
from docopt import docopt

## Some observations:
# The Javascript file contains some data that isn't shown on the actual webpage, namely in the last 3 entries of each array.
# Furthermore, it appears as if not all entries in the Cookiebot table are actually true Cookies.
# The following types are listed:
# > HTTP: ID 1, most likely actual Cookies.
# > HTML: ID 2, no idea what this type is supposed to be.
# > Pixel: ID 5, Tracking pixels embedded on the website
# Additional information includes a regular expression (possibly to identify variations of the same cookie)
# and a final URL as the last entry, possibly the true destination where the data is sent to?

class CookieCategories(Enum):
    NECESSARY = 0
    PREFERENCE = 1
    STATISTICS = 2
    ADVERTISING = 3
    UNCLASSIFIED = 4


category_patterns = {CookieCategories.NECESSARY : "CookieConsentDialog\.cookieTableNecessary = (.*);",
                     CookieCategories.PREFERENCE : "CookieConsentDialog\.cookieTablePreference = (.*);",
                     CookieCategories.STATISTICS : "CookieConsentDialog\.cookieTableStatistics = (.*);",
                     CookieCategories.ADVERTISING : "CookieConsentDialog\.cookieTableAdvertising = (.*);",
                     CookieCategories.UNCLASSIFIED: "CookieConsentDialog\.cookieTableUnclassified = (.*);"}



if __name__ == "__main__":

    args = docopt(__doc__)


    with open(args["<file>"], 'r') as fd:
        cb_js = fd.read()


    for cat in CookieCategories:
        matchobj = re.search(category_patterns[cat], cb_js)

        print("==============================\n"
             f"Category: {cat}\n"
             f"==============================")
        if not matchobj:
            print("Did not find match", file=sys.stderr)
            exit(1)

        cookies = literal_eval(matchobj.group(1))
        for c in cookies:
            print(f"cookie name:   {c[0]}")
            print(f"source:        {c[1]}")
            print(f"purpose:       {c[2]}")
            print(f"expires after: {c[3]}")
            print(f"type name:     {c[4]}")
            print(f"type id:       {c[5]}")
            print(f"regex match:   {c[6]}")
            print(f"Hyperlink URL: {c[7]}")
            print(f"--------------")
