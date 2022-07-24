#!/bin/python3
# Copyright (C) 2021-2022 Dino Bollinger
# Created as part of a master thesis at ETH Zürich, Information Security Group
# Licensed under BSD 3-Clause License, see included LICENSE file
"""
Cookie-Consent Category Scraper
-----------------------------------
Sequentially scrapes websites that use consent management platforms to obtain category labels for cookies.
Will also output crawl statistics and a list of URLs where the crawling failed.
This can be reused as input for subsequent runs.

Does not retrieve the cookies themselves.

Currently supports:
- Cookiebot
- OneTrust (including OptAnon, CookiePro and CookieLaw domains)
- Termly
-----------------------------------
Usage:
    run_scraper.py (cookiebot|onetrust|termly) (--url <u> | --pkl <fpkl> | --file <fpath>)... [--assume_http] [--loglevel <LEVEL>] [--dbname <DB>]
    run_scraper.py --help

Options:
    -u --url <u>          A single URL string to target. Can specify multiple.
    -p --pkl <fpkl>       One or more file path to pickled list of URLs to parse.
    -f --file <fpath>     One or more paths to files containing one URL per line.
    -a --assume_http      Assume domains are provided without 'HTTP://' prefix, append prefix where necessary.
    --dbname <DB>         Name of the output database. [default: cookiedat.sqlite]

    --loglevel <LEVEL>    Set level for logger [default: INFO]
    -h --help             Display this help screen.
"""

from docopt import docopt
from requests import Session

import os
import pickle
import logging
from typing import Set, Dict
from datetime import datetime

from src.base_scraper import BaseScraper
from src.cookiebot_scraper import CookiebotScraper
from src.onetrust_scraper import OneTrustScraper
from src.termly_scraper import TermlyScraper

logger = logging.getLogger("main")
output_path = f"./scrape_out_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


def add_stderr_to_logger(loglevel: str) -> None:
    """ Enables logging to stderr """
    formatter = logging.Formatter('%(asctime)s :: %(name)s :: %(levelname)s :: %(message)s', datefmt="%Y-%m-%d-%H:%M:%S")
    ch = logging.StreamHandler()
    ch.setLevel(loglevel)
    ch.setFormatter(formatter)
    logger.addHandler(ch)


def setupLogger(logdir: str, loglevel: str) -> None:
    """
    Set up the logger instance, write to a log file.
    :param logdir: Directory for the log file.
    :param loglevel: Log level at which to record.
    """
    loglevel = logging.getLevelName(loglevel)
    logger.setLevel(loglevel)
    formatter = logging.Formatter('%(asctime)s :: %(name)s :: %(levelname)s :: %(message)s', datefmt="%Y-%m-%d-%H:%M:%S")

    os.makedirs(logdir, exist_ok=True)
    logfile = os.path.join(logdir, "scrape_cl.log")

    # log file output
    fh = logging.FileHandler(filename=logfile, mode="w", encoding="utf8")
    fh.setLevel(loglevel)
    fh.setFormatter(formatter)
    logger.addHandler(fh)


def retrieve_urls(cargs: Dict) -> Set[str]:
    """
    Retrieve URLs to be crawled from arguments.
    :param cargs: docopt arguments
    :return: set of unique urls, prefixed with HTTP prefix if needed
    """
    sites: Set[str] = set()

    # retrieve URLs directly from command line
    for u in cargs["--url"]:
        sites.add(u)

    # retrieve data from pickle files
    for p in cargs["--pkl"]:
        if os.path.exists(p):
            with open(p, 'rb') as fd:
                contents = pickle.load(fd, encoding="utf-8")
                for c in contents:
                    sites.add(c)
        else:
            logger.error(f"Provided pickle file path is invalid: \"{p}\"")

    # retrieve urls from plaintext files, one url per line
    for fn in cargs["--file"]:
        if os.path.exists(fn):
            with open(fn, 'r', encoding="utf-8") as fd:
                for line in fd:
                    sites.add(line.strip())
        else:
            logger.error(f"Provided plaintext file path is invalid: \"{fn}\"")

    # check correctness of URL and remove comment lines
    copy = sites.copy()
    while copy:
        url = copy.pop()
        if not url or len(url.strip()) == 0 or url.startswith("#"):
            sites.remove(url)
        elif not url.lower().startswith("http://") and not url.lower().startswith("https://"):
            sites.remove(url)
            if cargs["--assume_http"]:
                sites.add("http://" + url)
                logger.debug(f"Appended HTTP prefix to URL: \"{url}\"")
            else:
                logger.warning(f"Removed URL: \"{url}\" (missing http schema)")

    return sites


def main():
    argv = None

    ## Some example sites to test the crawler on. Uncomment one line to test the extraction.
    # argv = ["cookiebot", "--url", "https://purplemath.com/", "--loglevel", "DEBUG"]
    # argv = ["cookiebot", "--url", "https://gamefly.com/", "--loglevel", "DEBUG"]
    # argv = ["onetrust", "--url", "https://www.metabomb.net/", "--loglevel", "DEBUG"]
    # argv = ["onetrust", "--url", "https://www.maytag.com/", "--loglevel", "DEBUG"]
    # argv = ["onetrust", "--url", "https://www.aveda.com/", "--loglevel", "DEBUG"]
    # argv = ["onetrust", "--url", "https://www.equipmenttrader.com/", "--loglevel", "DEBUG"]
    # argv = ["onetrust", "--url", "https://www.tiffany.com/", "--loglevel", "DEBUG"]
    # argv = ["termly", "--url", "https://zoella.co.uk/", "--loglevel", "DEBUG"]
    # argv = ["termly", "--url", "https://www.dailystep.com/", "--loglevel", "DEBUG"]

    # Initialize docopt, logger and get the arguments
    cargs = docopt(__doc__, argv=argv)
    setupLogger(logdir=output_path, loglevel=cargs["--loglevel"].upper())
    add_stderr_to_logger(cargs["--loglevel"].upper())
    sites = retrieve_urls(cargs)

    # abort if no sites specified
    if len(sites) == 0:
        logger.error("No URLs to crawl! Aborting...")
        return 1

    scraper: BaseScraper
    if cargs["cookiebot"]:
        logger.info("CookieBot provider selected")
        scraper = CookiebotScraper(output_path, debug_mode=False)
    elif cargs["onetrust"]:
        logger.info("OneTrust provider selected")
        scraper = OneTrustScraper(output_path, debug_mode=False)
    elif cargs["termly"]:
        logger.info("Termly provider selected")
        scraper = TermlyScraper(output_path, debug_mode=False)
    else:
        logger.error("Unsupported Consent Management Provider")
        return 2

    # Perform the crawl
    sess = Session()
    scraper.start_webdriver()
    comp_succ = comp_fail = 0
    total = len(sites)
    try:
        while sites:
            u = sites.pop()
            logger.info(f"Crawling: {u}")
            success_status = scraper.scrape_website(u, sess)
            if success_status:
                logger.info(f"Crawl for site {u} completed successfully.")
                comp_succ += 1
            else:
                logger.warning(f"Crawl for site {u} failed!")
                comp_fail += 1
            logger.info("%i/%i completed." % (comp_succ + comp_fail, total))

    except KeyboardInterrupt:
        logger.info("Execution has been cancelled by Keyboard Interrupt.")
        os.makedirs(output_path, exist_ok=True)
        with open(os.path.join(output_path, "uncrawled_urls.txt"), 'w') as fd:
            for s in sites:
                fd.write(s + "\n")
    finally:
        scraper.stop_webdriver()
        sess.close()

    logger.info("Crawl Completed. Success: %i/%i -- Failed: %i/%i"
                % (comp_succ, total, comp_fail, total))

    # Dump crawl statistics and error information
    scraper.dump_crawl_statistics(os.path.join(output_path, "crawl_statistics.csv"))
    scraper.dump_full_error_info(os.path.join(output_path, "error_info.txt"))
    scraper.dump_failed_urls(os.path.join(output_path, "failed_urls.txt"))

    # Output collected data into a SQLite database
    sql_db = os.path.join(output_path, cargs["--dbname"])
    scraper.setup_database(sql_db, "./schema/schema.sql")
    scraper.store_cookies_in_db()
    scraper.close_database()

    # cookie label output
    # label_path = os.path.join(output_path, "cookie_labels.csv")
    # src.dump_cookie_names_with_labels(label_path)

    logger.info(f"Crawl data has been written to: {output_path}")
    return 0


if __name__ == "__main__":
    exit_code = main()
    exit(exit_code)
