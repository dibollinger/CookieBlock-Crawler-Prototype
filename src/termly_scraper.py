# Copyright (C) 2021-2022 Dino Bollinger
# Created as part of a master thesis at ETH Zürich, Information Security Group
# Licensed under BSD 3-Clause License, see included LICENSE file
"""
Termly Scraper: This file defines the src used for the Termly Consent Management Provider.
"""

import requests
import logging
import re
import os.path
import json
import pickle

from typing import Tuple, Optional, Dict
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException
from src.base_scraper import BaseScraper, CookieCategory, CrawlState, uuid_pattern

logger = logging.getLogger("scrape_cl.BaseScraper.TermlyScraper")

name_to_cat = {"essential": CookieCategory.ESSENTIAL,
               "performance": CookieCategory.FUNCTIONAL,
               "analytics": CookieCategory.ANALYTICAL,
               "advertising": CookieCategory.ADVERTISING,
               "social_networking": CookieCategory.UNKNOWN,
               "unclassified": CookieCategory.UNCLASSIFIED}

known_cookie_attributes = {"name", "category", "tracker_type",
                           "country", "domain", "source", "url",
                           "value", "en_us", "service",
                           "service_policy_link", "expire"}

# url for the termly consent
termly_base = "https://app.termly.io/api/v1/snippets/websites/"

termly_source_href_pattern = re.compile("https://app\\.termly\\.io/embed\\.min\\.js")


class TermlyScraper(BaseScraper):
    """
    Scraper for the Termly Consent Management Provider
    """

    # global
    total_debug_outs: int = 0


    class exists_script_tag_with_termly_embed():
        """
        Internal utility class to check if there exists a script tag for the termly embed banner.
        :return The uuid string for retrieving the termly cookie policy.
        """

        def __call__(self, driver):
            elems = driver.find_elements_by_tag_name("script")
            for e in elems:
                try:
                    termly_found = False
                    embed_src = e.get_attribute("src")
                    if embed_src and termly_source_href_pattern.match(embed_src):
                        termly_found = True
                    else:
                        data_name = e.get_attribute("data-name")
                        if data_name == "termly-embed-banner":
                            termly_found = True

                    if termly_found:
                        uuid = e.get_attribute("id")
                        if uuid and uuid_pattern.match(uuid):
                            return uuid
                        else:
                            uuid = e.get_attribute("data-website-uuid")
                            if uuid and uuid_pattern.match(uuid):
                                return uuid
                            else:
                                logger.warning("Found termly embed banner script tag without an id attribute.")
                except StaleElementReferenceException:
                    logger.warning("Stale element exception while looking through script tags. Continuing with next one...")
                    continue

            return None


    def retrieve_termly_json(self, url, sess) -> Tuple[Optional[Dict], CrawlState, str]:
        """
        Attempt to use Selenium to retrieve the termly "cookies" json file.
        :param sess: Session for request to termly cdn URL
        :param url: URL we want to direct the Selenium Webdriver to.
        :return: json dict, CrawlState, error report
        """

        cookies_json = dict()
        uuid1: Optional[str] = None

        state, report = self.driver_get(url)
        if state != CrawlState.SUCCESS:
            return cookies_json, state, report
        try:
            try:
                # Variant 1: try to retrieve "data-cbid" attribute
                wait = WebDriverWait(self.webdriver, 3)
                uuid1 = wait.until(self.exists_script_tag_with_termly_embed())
            except TimeoutException:
                logger.info("Timeout while looking for termly uuid.")

            if not uuid1:
                return cookies_json, CrawlState.CMP_NOT_FOUND, "Could not find Termly UUID to access cookie policies."
            logger.info(f"Retrieved uuid1: {uuid1}")

            resp, state, err = self.static_get_request(termly_base + uuid1, session=sess)
            if state != CrawlState.SUCCESS:
                return cookies_json, state, "Failed to retrieve Termly policy JSON: " + err

            try:
                policy_dict = json.loads(resp.text)
            except json.JSONDecodeError as ex:
                return cookies_json, CrawlState.JSON_DECODE_ERROR, f"Failed to decode Termly policy JSON. Details: {ex}"

            uuid2: Optional[str] = None
            if "documents" in policy_dict:
                for doc in policy_dict["documents"]:
                    if "name" in doc and doc["name"] == "Cookie Policy":
                        if uuid_pattern.match(doc["uuid"]):
                            uuid2 = doc["uuid"]
                            break
                        else:
                            logger.error("Found a UUID entry inside policy JSON that wasn't a UUID!")

            if uuid2 is None:
                return cookies_json, CrawlState.PARSE_ERROR, "Failed to retrieve second UUID string from policy JSON."

            logger.info(f"Retrieved uuid2: {uuid2}")

            cookies_path = termly_base + uuid1 + "/documents/" + uuid2 + "/cookies"
            resp2, state, err = self.static_get_request(cookies_path, session=sess)
            if state != CrawlState.SUCCESS:
                return cookies_json, state, f"Failed to retrieve Termly cookies JSON from {cookies_path}: " + err

            try:
                cookies_json = json.loads(resp2.text)
            except json.JSONDecodeError as ex:
                return cookies_json, CrawlState.JSON_DECODE_ERROR, f"Failed to decode Termly cookies JSON. Details: {ex}"

            return cookies_json, CrawlState.SUCCESS, "Successfully retrieved Termly cookies JSON"

        except Exception as ex:
            report = f"Unexpected error while trying to retrieve Termly Cookies JSON: : {type(ex)} {ex}"
            return cookies_json, CrawlState.UNKNOWN, report



    def debug_dump_dict(self, outname, cookies_dict):
        if self.debug_mode:
            self.total_debug_outs += 1
            with open(os.path.join(self.logpath, outname + str(self.total_debug_outs)), 'wb') as fd:
                pickle.dump(cookies_dict, fd, pickle.HIGHEST_PROTOCOL)



    def parse_termly_cookie_json(self, url:str, cookie_dict) -> Tuple[CrawlState, str]:
        """
        Parse the cookies json dictionary and retrieve cookie data + labels.
        :param url: URL of the website that was targeted during the crawl
        :param cookie_dict: dict from transformed JSON
        :return: crawl state, report
        """
        debug_out = "termly_malf_resp.pkl"
        cookie_count = 0
        weird_stuff_occurred = False
        if "cookies" in cookie_dict:
            try:
                for catname, entry in cookie_dict["cookies"].items():
                    if catname not in name_to_cat:
                        weird_stuff_occurred = True
                        logger.error(f"UNKNOWN CATEGORY: {catname}")
                        continue
                    cat_id = name_to_cat[catname]
                    for cookie in entry:
                        if self.debug_mode:
                            print(catname)
                            print(cookie)

                        for k in cookie.keys():
                            if k not in known_cookie_attributes:
                                weird_stuff_occurred = True
                                logger.warning(f"UNKNOWN COOKIE ATTRIBUTE: {k}")

                        cookie_count += 1
                        if "name" not in cookie:
                            weird_stuff_occurred = True
                            logger.warning(f"Cookie #{cookie_count} has no name!!!")
                            name = None
                        else:
                            name = cookie["name"]
                        if "category" in cookie and cookie["category"] != catname:
                            weird_stuff_occurred = True
                            logger.warning(f"Category in cookie mismatches category array!! array: {catname}, cookie: {cookie['category']}")

                        tracker_type = cookie["tracker_type"] if "tracker_type" in cookie else None
                        domain = cookie["domain"] if "domain" in cookie else None
                        purpose = cookie["en_us"] if "en_us" in cookie else None
                        # expiry = cookie["expire"] if "expire" in cookie else None
                        # country = cookie["country"] if "country" in cookie else None
                        # source = cookie["source"] if "source" in cookie else None
                        # url = cookie["url"] if "url" in cookie else None
                        # value = cookie["value"] if "value" in cookie else None
                        # service = cookie["service"] if "service" in cookie else None
                        # service_policy_link = cookie["service_policy_link"] if "service_policy_link" in cookie else None
                        self.collect_cookie_dat(url, name, domain, "/", catname, cat_id, purpose, tracker_type)
            except Exception as ex:
                self.debug_dump_dict(debug_out, cookie_dict)
                report = f"Unexpected error while extracting Cookies from Termly Dict: : {type(ex)} {ex}"
                return CrawlState.PARSE_ERROR, report
        else:
            self.debug_dump_dict(debug_out, cookie_dict)
            return CrawlState.MALFORM_RESP, "No 'cookies' attribute in cookies JSON!"

        if weird_stuff_occurred:
            self.debug_dump_dict(debug_out, cookie_dict)

        if cookie_count == 0:
            return CrawlState.NO_COOKIES, "No cookies found in Termly JSON!!"
        else:
            return CrawlState.SUCCESS, f"Number of Cookies extracted: {cookie_count}"

    def scrape_website(self, url: str, sess: requests.Session) -> bool:
        """
        Retrieve Termly cookie label data from URL.
        :param sess: persistent session for the termly host
        :param url: URL to crawl for category data
        """
        # Retrieve cookies.json
        cookies_dict, state, report = self.retrieve_termly_json(url, sess)
        if state != CrawlState.SUCCESS:
            self.update_crawl_stats(url, state, report)
            return False
        logger.info("Found cookie json dict")

        state, report = self.parse_termly_cookie_json(url, cookies_dict)
        self.update_crawl_stats(url, state, report)
        return state == CrawlState.SUCCESS
