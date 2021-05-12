# Cookie Consent Label Webcrawler - Prototype

* [Introduction](#introduction)
* [Description](#description)
* [Installation](#installation)
    * [Requirements](#requirements)
    * [Usage](#usage)
    * [Options](#options)
* [Outputs](#outputs)
* [Repository Contents](#repository-contents)
* [Credits](#credits)
* [License](#license)
    

## Introduction

CookieBlock is a browser extension developed by researchers at ETH Zürich, 
which automatically enforces GDPR cookie consent preferences of the user without 
having to rely on the website to respect the user's privacy. The extension is 
available for all major browsers. For more information and a link to add-on stores, 
see the following repository: 

https://github.com/dibollinger/CookieBlock

To classify cookies, CookieBlock uses a gradient-boosted tree classifier. To 
train this classifier, it is necessary to retrieve a ground truth of category labels 
for the training samples. This is the task of the tool in this repository. It is a 
prototype implementation of a crawler that attempts to retrieve cookie labels by scraping 
data from Consent Management Platforms (CMPs).

This repository is a predecessor of the OpenWPM-based crawler implementation found at:

https://github.com/dibollinger/CookieBlock-Consent-Crawler

It is released here separately under the BSD 3-clause license such that the relevant
crawling logic can potentially be reused without having to bother with the GPL license.

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
    concern. Depending on what data is being gathered, these cookies can identify a 
    visitor's habits, interests, interests both leisurly and political, as well as 
    name and identity, geographical location and social standing.
* __Uncategorized__: Some CMPs leave cookies uncategorized. This category catches
    all such declarations.
* __Unknown__: Some categories cannot be easily be assigned to any of the above categories. 
    This includes category labels such as "Information Storage and Access" or "Content Delivery" 
    as these labels state little about how the cookie is intended to be used. In addition,
    some CMP use language-specific declarations. This crawler only supports English 
    language categories.

If a cookie has multiple purposes assigned, the tool will generally assign the less 
privacy-preserving class.

In addition to the code, this repository also includes an informal analysis of how
the CookieBot and OneTrust CMPs store the relevant cookie consent data, and what 
information can be retrieved.

The code in this repository is licensed under BSD 3-clause. 

## Installation

No special setup is needed, simply install the required Python libraries (either as virtual environment or globally)
and execute the script `run_scraper.py` with the required arguments.

### Requirements

* Tested with __Python 3.8__ and __3.9__
* Required third-party libraries:
   * requests (tested w/ version: 2.25.1) 
   * beautifulsoup4 (4.9.3)
   * docopt (0.6.2)
   * selenium (3.141)
   * Js2Py (0.70)

### Usage
    run_scraper.py (cookiebot|onetrust|termly) (--url <u> | --pkl <fpkl> | --file <fpath>)... [--assume_http] [--loglevel <LEVEL>] [--dbname <DB>]
    run_scraper.py --help

The first required argument determines which CMP to look for. This must be one of the following:
* cookiebot : Test for the Cookiebot CMP on the provided domains.
* onetrust : Test for OneTrust, OptAnon and CookiePro CMP on the given domains. These all implement the same backend.
* termly : Test for the Termly CMP on the given domains.

The second required argument determines the urls to crawl. These must be given in HTTP protocol format.

#### Options
    -u --url <u>          A single URL string to target. Can specify multiple.
    -p --pkl <fpkl>       File path to pickled list of URLs.
    -f --file <fpath>     Path to file containing one URL per line.
    -a --assume_http      Assume domains are provided without 'HTTP://' prefix, append prefix where necessary.
    --dbname <DB>         Name of the output database. Default is: "cookiedat.sqlite"

    --loglevel <LEVEL>    Set level for logger [default: INFO]
    -h --help             Display this help screen.

## Outputs:

For each crawl, the script produces a folder called `scrape_out_<timestamp>` which contains 
the collected CMP data and statistics on each type of error with detailed descriptions of each error.

The consent data is stored in a SQLite database (called `cookiedat.sqlite` by default) which 
contains the following table:

    TABLE consent_data
        id INTEGER PRIMARY KEY,         -- unique identifier
        site_url TEXT NOT NULL,         -- site that was targetted in the crawl
        name TEXT NOT NULL,             -- name as specified in the CMP
        domain TEXT NOT NULL,           -- domain as specified in the CMP
        path TEXT DEFAULT "/",          -- path in the CMP (rarely listed)

        cat_id INTEGER NOT NULL,        -- Identifies the category
        cat_name VARCHAR(256) NOT NULL, -- Name of the category. May vary for the same ID.
        purpose TEXT,                   -- Declared purpose of the cookie.
        type VARCHAR(256)               -- Cookiebot technology type


## Repository Contents
    ./documentation    -- Documentation on Cookiebot, OneTrust and the crawler failure cases.
    ./domain_sources   -- A list of example domains to crawl, sourced from BuiltWith.
    ./schema           -- Contains the database schema.
    ./src              -- Source files for the crawler.
    ./run_scraper.py   -- Command line script to run the crawler, with usage described above.

## Credits
This repository was created as part of the master thesis __"Analyzing Cookies Compliance with the GDPR"__, 
which can be found here:

https://www.research-collection.ethz.ch/handle/20.500.11850/477333

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
