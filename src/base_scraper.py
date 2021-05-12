# Copyright (C) 2021 Dino Bollinger, ETH Zürich, Information Security Group
# Licensed under BSD 3-Clause License, see included LICENSE file
"""
This script stores common classes and functions used for both types of crawler.
- Class CrawlState defines the different success/error states that can result from a crawl.
- Class CookieCategory defines uniform cookie consent categories.
- Class BaseScraper defines the base class for all src implementations to inherit from,
  and defines a number of useful utility functions to use, including the schema handling
  and the Selenium webdriver setup.
"""

import os
import re
import logging
import requests
import requests.exceptions as r_excepts
import sqlite3

from enum import IntEnum
from typing import List, Dict, Tuple, Optional
from abc import ABC, abstractmethod

from selenium import webdriver
from selenium.webdriver.common.alert import Alert
import selenium.common.exceptions as selenium_excepts
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver import Firefox

logger = logging.getLogger("main.BaseScraper")

# universal unique identifier pattern
uuid_pattern = re.compile("[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")


class CrawlState(IntEnum):
    SUCCESS = 0                # Everything went fine
    CONN_FAILED = 1            # Connection to server could not be established
    HTTP_ERROR = 2             # Server returned an HTTP Error response
    PARSE_ERROR = 3            # Could not find expected data in retrieved file
    CMP_NOT_FOUND = 4          # Could not find a cookie consent provider
    BOT_DETECTION = 5          # Could not access site due to anti-bot measures (e.g. Captcha)
    MALFORMED_URL = 6          # URL to browse was improperly formatted
    SSL_ERROR = 7              # Server performed invalid TLS handshake or certificate
    LIBRARY_ERROR = 8          # cookie consent provider returned an error response
    REGION_BLOCK = 9           # IP region was prevented access
    MALFORM_RESP = 10          # Response did not have expected format
    NO_COOKIES = 11            # Website didn't have any cookies recorded, despite correct response
    JSON_DECODE_ERROR = 12     # Failed to decode the JSON file for whatever reason
    UNKNOWN = -1               # Unaccounted for Error. If this occurs, need to extend script to handle it.


class CookieCategory(IntEnum):
    UNKNOWN = -1  # Unrecognized category
    ESSENTIAL = 0  # Cookie necessary for the site to function.
    FUNCTIONAL = 1   # Functional and Preferences. Change website options etc.
    ANALYTICAL = 2   # Includes performance and website statistics. Usually anonymized.
    ADVERTISING = 3  # Cookies for Advertising/Tracking/Social Media/Marketing/Personal Data Sale etc.
    UNCLASSIFIED = 4  # Explicitly unclassified cookies.


class BaseScraper(ABC):

    def __init__(self, log_path, debug_mode = False):
        """
        Base class for all cookie consent scrapers.
        """
        # Selenium webdriver used to access website data
        self.webdriver: Optional[WebDriver] = None

        # stores final state and potential error report of each website crawl
        self._crawl_log: Dict[str, Tuple[CrawlState, str]] = dict()

        # websites for which crawling failed
        self._failed_urls: List[str] = list()

        # stores number of occurrences of each final page state
        self._status_counts: Dict[CrawlState, int]

        # path where outputs and log files are stored
        self.logpath: str = log_path

        # true -> dump json where parsing failed
        self.debug_mode: bool = debug_mode

        # initialize crawlstate array
        self._status_counts = dict()
        for e in CrawlState:
            self._status_counts[e] = 0

        # cookie data and labels
        self.database_cookie_data: List[Tuple] = list()
        self.cookie_labels: Dict = dict()

        # sqlite schema connection to persist the cookie data
        self.db: Optional[sqlite3.Connection] = None


    def update_crawl_stats(self, url: str, state: CrawlState, report: str) -> None:
        """
        Update final crawl stats and log reports.
        :param url: URL for which we want to record the final status
        :param state: Success/Error state
        :param report: Details on the state
        """
        self._status_counts[state] += 1
        if report is not None:
            self._crawl_log[url] = (state, report)

        if state != CrawlState.SUCCESS:
            self._failed_urls.append(url)
            ## in debug mode, if crawl failed, dump index.html of the site for analysis
            # if self._debug_mode:
            #     with open(os.path.join(self._logpath,
            #                           url.replace("/", "_").replace(":", "") + ".html"), 'w') as fd:
            #        source = self.driver_get_current_pagesource()
            #        fd.write(source)

        logger.debug(f"Crawl Result for \"{url}\" = {state}")
        logger.debug(f"Details: {report}")


    def dump_failed_urls(self, outpath: Optional[str]) -> None:
        """
        Write URLs for which the library crawling failed into the given file path.
        :param outpath: Path to which the URLs will be written
        """
        if len(self._failed_urls) == 0:
            logger.debug("No failed URLs to dump.")
            return

        if not outpath:
            outpath = self.logpath

        dirs, fn = os.path.split(outpath)
        os.makedirs(dirs, exist_ok=True)
        with open(outpath, 'w') as fd:
            for u in self._failed_urls:
                fd.write(u + "\n")
        logger.info(f"Dumped failed crawl URLs to: \"{outpath}\"")


    def dump_crawl_statistics(self, outpath: Optional[str]) -> None:
        """
        Dump the crawl statistics in CSV format.
        :param outpath: Path to which the statistics will be written.
        """
        dirs, fn = os.path.split(outpath)
        os.makedirs(dirs, exist_ok=True)

        if not outpath:
            outpath = self.logpath

        with open(outpath, 'w') as fd:
            fd.write(f"Successful requests:          {self._status_counts[CrawlState.SUCCESS]}\n")
            fd.write(f"Failed to connect:            {self._status_counts[CrawlState.CONN_FAILED]}\n")
            fd.write(f"HTTP errors:                  {self._status_counts[CrawlState.HTTP_ERROR]}\n")
            fd.write(f"Website parse failures:       {self._status_counts[CrawlState.PARSE_ERROR]}\n")
            fd.write(f"Consent Library not found:    {self._status_counts[CrawlState.CMP_NOT_FOUND]}\n")
            fd.write(f"Malformed URL:                {self._status_counts[CrawlState.MALFORMED_URL]}\n")
            fd.write(f"SSL Errors:                   {self._status_counts[CrawlState.SSL_ERROR]}\n")
            fd.write(f"Region Block Response:        {self._status_counts[CrawlState.REGION_BLOCK]}\n")
            fd.write(f"Malformed Response:           {self._status_counts[CrawlState.MALFORM_RESP]}\n")
            fd.write(f"Library Returned Error:       {self._status_counts[CrawlState.LIBRARY_ERROR]}\n")
            fd.write(f"Unknown Errors:               {self._status_counts[CrawlState.UNKNOWN]}\n")

        logger.info(f"Dumped crawl statistics to: \"{outpath}\"")


    def dump_full_error_info(self, outpath:Optional[str]) -> None:
        """
        Write error log information for each crawled site into the provided filepath.
        :param outpath: Path to write error information to.
        """
        dirs, fn = os.path.split(outpath)
        os.makedirs(dirs, exist_ok=True)

        if not outpath:
            outpath = self.logpath

        with open(outpath, 'w') as fd:
            for e in CrawlState:
                if e == CrawlState.SUCCESS:
                    continue
                fd.write(f"Error Type {e}\n")
                errors = [f"Website: \"{url}\"  ----  Details: \"{report}\"" for url, (s, report) in self._crawl_log.items() if s == e]
                if len(errors) > 0:
                    fd.write("\n".join(errors))
                    fd.write("\n")

        logger.info(f"Dumped full error info to: \"{outpath}\"")


    def print_error_info(self) -> None:
        """ Write error information to log. """
        for e in CrawlState:
            if e == CrawlState.SUCCESS:
                continue
            errors = [f"Website: \"{url}\" -- Details: \"{report}\"" for url, (s, report) in self._crawl_log.items() if s == e]
            if len(errors) > 0:
                logger.debug(f"Errors of type: {e}")
                logger.debug("\n".join(errors))


    def _init_firefox_webdriver(self) -> Firefox:
        """
        Set up Firefox webdriver with a number of settings.
        """
        profile = webdriver.FirefoxProfile()
        options = webdriver.FirefoxOptions()

        profile.set_preference("privacy.donottrackheader.enabled", False)
        profile.set_preference("privacy.resistFingerprinting", False)
        profile.set_preference("privacy.trackingprotection.pbmode.enabled", False)
        profile.set_preference("privacy.trackingprotection.enabled", False)
        # profile.set_preference("permissions.default.image", 2)  # disable loading images
        options.add_argument("--headless")

        firefox = webdriver.Firefox(firefox_profile=profile, options=options)
        firefox.set_page_load_timeout(30)
        firefox.set_script_timeout(20)

        logger.debug(f"Firefox webdriver initialized in headless mode.")
        return firefox


    def start_webdriver(self, wtype: str = "Firefox") -> None:
        """
        Set up the Selenium Webdriver. Only Firefox currently supported.
        """
        if self.webdriver:
            raise RuntimeError("Webdriver already running!")

        if wtype == "Firefox":
            self.webdriver = self._init_firefox_webdriver()
        else:
            raise ValueError("Unsupported Webdriver Type")

        logger.info(f"Webdriver initialized.")


    def stop_webdriver(self) -> None:
        """
        Close the Selenium Webdriver, exit all open windows.
        """
        if not self.webdriver:
            raise RuntimeError("Webdriver isn't running!")
        self.webdriver.quit()
        self.webdriver = None
        logger.info(f"Webdriver stopped")


    def driver_get(self, url: str) -> Tuple[CrawlState, Optional[str]]:
        """
        Direct the Selenium Webdriver to retrieve the provided URL.
        Checks for a number of error conditions. This only serves to catch and identify
        errors early in the pipeline, strictly speaking it is not necessary to do so.
        :param url: send GET request to this URL
        :return: PageState + Report
            SUCCESS: No errors occurred when browsing to page.
            MALFORMED_URL: provided URL was not formatted correctly
            CONN_FAILED: No connection to server / no DNS entry
            SSL_ERROR: Received an SSL Certificate Error
            UNKNOWN: WebDriver Exception that is unaccounted for.
        """
        if not self.webdriver:
            raise RuntimeError("Webdriver isn't running!")
        try:
            self.webdriver.get(url)
            try:
                alert: Alert = self.webdriver.switch_to.alert()
                alert.dismiss()
            except selenium_excepts.NoAlertPresentException:
                pass
            self.webdriver.switch_to.default_content()
            return CrawlState.SUCCESS, None
        except selenium_excepts.TimeoutException as ex:
            logger.warning("Timeout reached, but site may have loaded required data anyways, continuing.")
            return CrawlState.SUCCESS, str(type(ex)) + str(ex)
        except selenium_excepts.InvalidArgumentException as ex:
            return CrawlState.MALFORMED_URL, str(ex)
        except selenium_excepts.InsecureCertificateException as ex:
            return CrawlState.SSL_ERROR, str(ex)
        except selenium_excepts.WebDriverException as ex:
            if "Reached error page:" in str(ex):
                return CrawlState.CONN_FAILED, str(ex)
            return CrawlState.UNKNOWN, str(type(ex)) + str(ex)


    def driver_get_current_pagesource(self):
        """
        Retrieve html source of current page.
        :return: html as string
        """
        if not self.webdriver:
            raise RuntimeError("Webdriver isn't running!")

        return self.webdriver.page_source


    @staticmethod
    def static_get_request(url: str, session:requests.Session = None, verify_ssl: bool = True,
                           timeout: Tuple[int, int] = (6, 30), **kwargs) -> Tuple[Optional[requests.Response], CrawlState, str]:
        """
        Use the requests library to send a simple GET request to the given URL,
        and try to identify potential errors. Can also use a Session to send request.
        Error detection helps identify issues early on, but is strictly speaking not necessary.
        :param url: URL to send a request to.
        :param session: If provided, will send request using the session object. [Default: None]
        :param verify_ssl: If true, will check SSL certificate. [Default: True]
        :param timeout: Connect and Read timeout, respectively [Default: (6,30)]
        :param kwargs: Any additional keyword arguments to pass to the GET request.
        :return: Potential Response, State, Error Report
            Possible States:
            - SUCCESS: No errors occurred.
            - HTTP_ERROR: An HTTP Error occurred (status code >= 400)
            - SSL_ERROR: SSL Handshake failed, or invalid SSL Certificate encountered.
            - MALFORMED_URL: Invalid URL passed to request.
            - CONN_FAILED: Failed to connect to the server, or doesn't exist.
            - UNKNOWN: Unaccounted-for error.
        """
        try:
            if session:
                r = session.get(url, timeout=timeout, verify=verify_ssl, **kwargs)
            else:
                r = requests.get(url, timeout=timeout, verify=verify_ssl, **kwargs)

            # Status codes:
            if r.status_code == 525:
                return r, CrawlState.SSL_ERROR, "Error Code: 525 -- SSL Handshake with Cloudflare failed."
            elif r.status_code >= 400:
                return r, CrawlState.HTTP_ERROR, f"Error Status Code: {r.status_code}"
            else:
                return r, CrawlState.SUCCESS, str(r.status_code)
        except r_excepts.HTTPError as ex:
            return None, CrawlState.HTTP_ERROR, f"HTTP Error Exception for URL \"{url}\". Details: {ex}"
        except r_excepts.SSLError as ex:
            return None, CrawlState.SSL_ERROR, f"SSL Certificate issue encountered when connecting to {url}. -- Details: {ex}"
        except (r_excepts.URLRequired, r_excepts.MissingSchema) as ex:
            return None, CrawlState.MALFORMED_URL, f"Possibly malformed URL: \"{url}\" -- Details: \"{ex}\""
        except (r_excepts.ConnectionError, r_excepts.ProxyError, r_excepts.TooManyRedirects, r_excepts.Timeout) as ex:
            return None, CrawlState.CONN_FAILED, f"Connection to \"{url}\" failed. -- Details: {ex}"
        except Exception as ex:
            return None, CrawlState.UNKNOWN, f"Unknown Error: {type(ex)} {ex}"


    def dump_cookie_names_with_labels(self, outpath: Optional[str]) -> None:
        """
        Dump the collected category labels in CSV format.
        DEPRECATED IN FAVOR OF SQLITE
        :param outpath: Path to which the data will be written.
        """
        dirs, fn = os.path.split(outpath)
        os.makedirs(dirs, exist_ok=True)

        if not outpath:
            outpath = self.logpath

        with open(outpath, 'w') as fd:
            for name, labels in self.cookie_labels.items():
                fd.write(f"{name}  {'  '.join(labels)}\n")

    def collect_cookie_dat(self, site_url: str, name: str, domain: str, path: str,
                           cat_name: str, cat_id: int, purpose=None, type=None):
        """
        Collect the provided data on the cookie inside the class-internal datastructures.
        This data will be output at the end of the crawl.
        """
        cookie_ident = (name, domain, path)
        if cookie_ident in self.cookie_labels:
            existing_categories = self.cookie_labels[cookie_ident]
            if cat_name not in existing_categories:
                self.cookie_labels[cookie_ident].append(cat_name)
        else:
            self.cookie_labels[cookie_ident] = [cat_name]

        self.database_cookie_data.append((site_url, name, domain, path, cat_id, cat_name, purpose, type))


    @abstractmethod
    def scrape_website(self, url: str, sess: requests.Session) -> bool:
        """
        Contains the main loop for the cookie category crawling process.
        :param sess: Session for retrieving data from CMP CDN.
        :param url: URL to scrape
        """
        raise NotImplementedError()


    def setup_database(self, sql_db: str, schema: str) -> None:
        """
        Establish a connection to the provided SQLite schema path
        :param sql_db: path to sqlite schema (folder must exist). Database file will be created if not present.
        """
        self.db = sqlite3.connect(sql_db)
        c = self.db.cursor()
        with open(schema, 'r') as f:
            c.execute(f.read())
        c.close()


    def store_cookies_in_db(self) -> None:
        """
        Persist the currently collected cookie data in the sqlite schema as a single batch commit.
        Empties the raw_cookie_data array.
        """
        command = "INSERT INTO consent_data (site_url, name, domain, path, cat_id, cat_name, purpose, type) " \
                  "VALUES (?,?,?,?,?,?,?,?);"
        self.db.executemany(command, self.database_cookie_data)
        self.db.commit()
        self.database_cookie_data = []


    def close_database(self) -> None:
        """
        Close the schema connection and commit any pending transactions.
        """
        self.db.commit()
        self.db.close()