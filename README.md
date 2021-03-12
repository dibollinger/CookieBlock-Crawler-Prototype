# CookieBlock Consent Label Webcrawler -- Prototype

Prototype variant of the CookieBlock consent label webcrawler.

Using a list of input domains, crawls websites that use specific Consent Management Platforms to 
retrieve the declared purpose of cookies and other tracking technologies. This includes the given
description of each entry as well. The cookies themselves are not gathered by this crawl.

This was the original implementation before OpenWPM was used. Licensed under BSD 3-clause.

Tested with Python 3.8

## Usage
    run_scraper.py (cookiebot|onetrust|termly) (--url <u> | --pkl <fpkl> | --file <fpath>)... [--assume_http] [--loglevel <LEVEL>] [--dbname <DB>]
    run_scraper.py --help

### Options:
    -u --url <u>          URL string to crawl.
    -p --pkl <fpkl>       File path to pickled list of URLs to parse.
    -f --file <fpath>     Path to file containing one URL per line.
    -a --assume_http      Assume input is in form of domains, to be accessed via HTTP protocol.
    --dbname <DB>         Name of the output database, if differs from default. [default: cookiedat.sqlite]

    --loglevel <LEVEL>    Set level for logger [default: INFO]
    -h --help             Display this help screen.

### Outputs:

For each crawl, the script produces a folder called `scrape_out_<timestamp>` which contains 
the collected CMP data and statistics on each type of error with detailed description.

The consent data is stored in a SQLite database called `cookiedat.sqlite` which contains the
following table:

    TABLE consent_data
        id INTEGER PRIMARY KEY,         -- unique identifier
        name TEXT NOT NULL,             -- name as specified in the CMP
        domain TEXT NOT NULL,           -- domain as specified in the CMP
        path TEXT DEFAULT "/",          -- path in the CMP (rarely listed)

        cat_id INTEGER NOT NULL,        -- Identifies the category
        cat_name VARCHAR(256) NOT NULL, -- Name of the category. May vary for the same ID.
        purpose TEXT,                   -- Declared purpose of the cookie.
        type VARCHAR(256)               -- Cookiebot technology type


## Repository Contents

    ./database         -- Contains the database schema.
    ./documentation    -- Documentation on Cookiebot, OneTrust and the crawler failure cases.
    ./domain_sources   -- A list of example domains to crawl, sourced from BuiltWith.
    ./src              -- Source files for the crawler.
    ./run_scraper.py   -- Command line script to run the crawler, with usage described above.

## Description

This tool allows the user to scrape websites for cookie consent purposes if 
the target website makes use of one of the supported Consent Management Platforms.
Currently supported by the script are Cookiebot, OneTrust and Termly CMPs. 

Due to the GDPR, websites that offer their services to countries in the EU 
are required to request consent from visitors when the website attempts to 
store cookies on the visitor's browser. This is commonly accomplished by
websites using plugins offered by Consent Management Platforms (CMPs).

These plugins usually offer consent toggles for the visitor, and sometimes 
display detailed information of the purpose of each cookie present on the website. 
This crawler specifically targets CMP implementations that display such information,
for the purpose of gathering a dataset of cookie labels and purposes.

Each cookie is assigned to one of the following purpose classes:

* __Strictly Necessary Cookies__: Cookies that are required for the website to function 
    properly. These require no consent from the visitor and usually cannot be rejected, 
    but are still declared inside privacy policies and consent management popups.
* __Functional Cookies__: Cookies that provide additional services or improve the user 
    experience, but are not strictly necessarily for the website to function. This 
    includes cookies such as website style settings, user preferences, etc. 
* __Performance/Analytical Cookies__: These are cookies that gather anonymized data 
    from the user in order to report statistics of the website usage or website 
    performance to the host. This data should be used to improve the site and the 
    browsing experience for the visitors, but are not to be used for advertising 
    or data sale purposes.
* __Advertising/Tracking__: This category encompasses all cookies that are used 
    for advertising and tracking purposes. Often this also involves the collection
    of sensitive personal data, which may be sold to other interested parties. 
    This is generally the category of cookies where the loss of privacy is the largest
    concern. Depending on what data is being gathered, these cookies can identify a 
    visitor's habits, interests, interests both leisurly and political, as well as 
    name and identity, geographical location and social standing.
* __Uncategorized__: Some CMPs leave cookies uncategorized. This category catches
    all such declarations.
* __Unknown__: Some categories cannot be easily be assigned to any of the above categories. 
    This includes category labels such as "Information Storage and Access" or "Content Delivery" 
    as these labels state little about how the cookie is intended to be used. In addition,
    some CMP use language-specific declarations. This crawler only supports English language
    categories.

If a cookie has multiple purposes assigned, the tool will generally assign the less 
privacy-preserving class.

# Credits and License

Copyright (c) 2021, Dino Bollinger

This project is released under the BSD 3-clause license, see the included LICENSE file.

---

The scripts in this repository were created as part of a master thesis on GDPR Compliance, 
and is part of a series of repositories for the __CookieBlock__ browser extension:

https://github.com/dibollinger/CookieBlock

__Thesis Supervision and Assistance:__
* Karel Kubicek
* Dr. Carlos Cotrini
* Prof. Dr. David Basin
* The Institute of Information Security at ETH Zürich
