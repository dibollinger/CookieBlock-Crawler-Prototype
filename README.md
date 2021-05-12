# Prototype: Cookie Consent Label Crawler

This is a variant of the cookie consent label webcrawler that was used for CookieBlock. It is fully functional and contains the main components of the final crawler, which includes the targeting of the Cookiebot, OneTrust and Termly CMP data. However, it is implemented using only Selenium, works sequentially and not in parallel, and does not collect the cookie data itself -- only the cookie consent data.

Using a list of input domains, the crawler crawls websites that use specific Consent Management Platforms to 
retrieve the declared purpose of cookies and other tracking technologies. This includes the given description 
of each entry as well. As mentioned, the cookies themselves are not gathered by this crawl.

This was the original implementation before OpenWPM was used. There is also a number of changes between this variant and the final release that may make it less effective at extracting data. The main purpose of this repository is to release the novel components of the crawler independently under a non-GPL license. 

See also: https://github.com/dibollinger/CookieBlock-Consent-Crawler

Licensed under BSD 3-clause. Tested with Python 3.8 and Python 3.9.

## Usage
    run_scraper.py (cookiebot|onetrust|termly) (--url <u> | --pkl <fpkl> | --file <fpath>)... [--assume_http] [--loglevel <LEVEL>] [--dbname <DB>]
    run_scraper.py --help

### Options:
    cookiebot:            Try to extract Cookiebot CMP data.
    onetrust:             Try to extract OneTrust CMP data. 
    cookiebot:            Try to extract Termly CMP data.
    -u --url <u>          URL string to target during the crawl. Can specify multiple.
    -p --pkl <fpkl>       File path to pickled list of URLs to parse. Can specify multiple.
    -f --file <fpath>     Path to file containing one URL per line. Can specify multiple.
    -a --assume_http      Attach http protocol to domain if not present already.
    --dbname <DB>         Name of the output database, if differs from default. [default: cookiedat.sqlite]

    --loglevel <LEVEL>    Set the level for the logger [default: INFO]
    -h --help             Display this help screen.

### Outputs:

For each crawl, the script produces a folder called `scrape_out_<timestamp>` which contains 
the collected CMP data and statistics on each type of error with detailed description.

The consent data is stored in a SQLite database called `cookiedat.sqlite` which contains the
following table:

    TABLE consent_data
        id INTEGER PRIMARY KEY,         -- unique record identifier
        name TEXT NOT NULL,             -- name of the cookie as specified in the CMP
        domain TEXT NOT NULL,           -- origin domain of the cookie as specified in the CMP
        path TEXT DEFAULT "/",          -- path of the cookie in the CMP (rarely listed)

        cat_id INTEGER NOT NULL,        -- Discrete internal cookie category identity. (0 == Necessary; 1 == Functional; 2 == Analytics; 3 == Advertising; 4 == Uncategorized; -1 == Unknown)
        cat_name VARCHAR(256) NOT NULL, -- Given name of the category. May differ for different CMPs.
        purpose TEXT,                   -- Given purpose for the cookie or tracking technology. May be empty.
        type VARCHAR(256)               -- Specific for Cookiebot, the type of tracking technology used. (0 == HTTP cookies; 1 == Javascript Cookies; 4 == Tracking Pixels)

This repository is a predecessor of the OpenWPM-based crawler implementation found at:

## Repository Contents
The repository contains the following subfolders and scripts:

    ./database         -- Contains the SQL database schema.
    ./documentation    -- Documentation on how data can be extracted from the Cookiebot and OneTrust CMPs. Also contains analysis of a test run of the crawler.
    ./domain_sources   -- A list of example domains to crawl, sourced from BuiltWith. High likelihood to contain one of the three CMPs.
    ./src              -- Source code files for the crawler, written in Python.
    ./run_scraper.py   -- Command line script to run the crawler, with usage described above.

## Description

Due to the GDPR, websites that offer their services to countries in the EU 
are required to request consent from visitors when the website attempts to 
store cookies on the visitor's browser. This is commonly accomplished by
websites using plugins offered by Consent Management Platforms (CMPs).

These plugins usually offer consent toggles for the visitor, and sometimes 
display detailed information of the purpose of each cookie present on the website. 
This crawler specifically targets CMP implementations that display such information,
for the purpose of gathering a dataset of cookie labels and purposes.

Using a list of input domains, the label crawler scrapes domains in expectation
that they use specific Consent Management Platform plugin to display cookie banners
to users. Currently supported CMPs are __Cookiebot__, __OneTrust__ and __Termly__.
If the CMP is found, specific string identifiers are extracted from the website
to then retrieve the externally hosted cookie label information.

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
    concern.
* __Uncategorized__: Some CMPs leave cookies uncategorized and without a specific
    description. This category catches all such declarations.
* __Unknown__: Some categories cannot be easily be assigned to any of the above categories. 
    This includes category labels such as "Information Storage and Access" or "Content Delivery" 
    as these labels state little about how the cookie is intended to be used. In addition,
    some CMP use language-specific declarations. This crawler only supports English 
    language categories.

If a cookie has multiple purposes assigned, the tool will generally assign the less 
privacy-preserving class.

# License

The code in this repository is licensed under BSD 3-clause. 

## Installation

----

The scripts in this repository were created as part of the master thesis *"Analyzing Cookies Compliance with the GDPR*, 
and is part of a series of repositories for the __CookieBlock__ browser extension.

__Related Repositories:__
* CookieBlock: https://github.com/dibollinger/CookieBlock
* Final Crawler: https://github.com/dibollinger/CookieBlock-Consent-Crawler
* Cookie Classifier: https://github.com/dibollinger/CookieBlock-Consent-Classifier
* Violation Detection & More: https://github.com/dibollinger/CookieBlock-Other-Scripts 
* Collected Data: https://drive.google.com/drive/folders/1P2ikGlnb3Kbb-FhxrGYUPvGpvHeHy5ao

__Thesis Supervision and Assistance:__
* Karel Kubicek
* Dr. Carlos Cotrini
* Prof. Dr. David Basin
* Information Security Group at ETH Zürich


See also the following repositories for other components that were developed as part of the thesis:

* __CookieBlock Extension:__ https://github.com/dibollinger/CookieBlock
* __OpenWPM-based Consent Crawler:__ https://github.com/dibollinger/CookieBlock-Consent-Crawler
* __Cookie Classifier:__ https://github.com/dibollinger/CookieBlock-Consent-Classifier
* __Violation Detection:__ https://github.com/dibollinger/CookieBlock-Other-Scripts
* __Collected Data:__ https://drive.google.com/drive/folders/1P2ikGlnb3Kbb-FhxrGYUPvGpvHeHy5ao

## License

__Copyright (c) 2021 Dino Bollinger, Department of Computer Science at ETH Zürich, Information Security Group__

__With help from Karel Kubicek, Dr. Carlos Cotrini and Prof. Dr. David Basin.__

This project is released under the BSD 3-clause license, see the included LICENSE file.
