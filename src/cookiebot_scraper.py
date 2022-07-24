# Copyright (C) 2021-2022 Dino Bollinger
# Created as part of a master thesis at ETH Zürich, Information Security Group
# Licensed under BSD 3-Clause License, see included LICENSE file
"""
Cookiebot Scraper: This file defines the src used for the Cookiebot Consent Management Provider.
"""
import requests
from bs4 import BeautifulSoup
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException

import logging
import re
import os.path
from typing import Tuple
from ast import literal_eval

from src.base_scraper import BaseScraper, CookieCategory, CrawlState, uuid_pattern

logger = logging.getLogger("main.BaseScraper.CookiebotScraper")

cookiebot_catnames = ["Necessary", "Preference", "Statistics", "Advertising", "Unclassified"]

name_to_cat = {"Necessary": CookieCategory.ESSENTIAL,
               "Preference": CookieCategory.FUNCTIONAL,
               "Statistics": CookieCategory.ANALYTICAL,
               "Advertising": CookieCategory.ADVERTISING,
               "Unclassified": CookieCategory.UNCLASSIFIED}


# url pattern for the cookiebot consent cdn
cookiebot_base_pattern = re.compile("https://consent\\.cookiebot\\.com/")
variant_2_pattern = re.compile("https://consent\\.cookiebot\\.com/([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})/cc\\.js")
variant_3_pattern = re.compile("[&?]cbid=([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})")


# patterns to parse the final cc.js file, which is where the actual category data is stored
category_patterns = {CookieCategory.ESSENTIAL: re.compile("CookieConsentDialog\\.cookieTableNecessary = (.*);"),
                     CookieCategory.FUNCTIONAL: re.compile("CookieConsentDialog\\.cookieTablePreference = (.*);"),
                     CookieCategory.ANALYTICAL: re.compile("CookieConsentDialog\\.cookieTableStatistics = (.*);"),
                     CookieCategory.ADVERTISING: re.compile("CookieConsentDialog\\.cookieTableAdvertising = (.*);"),
                     CookieCategory.UNCLASSIFIED: re.compile("CookieConsentDialog\\.cookieTableUnclassified = (.*);")}


class CookiebotScraper(BaseScraper):
    """
    Scraper for the Cookiebot Consent Management Provider
    Cookiebot stores its category data inside a number of nested Javascript arrays.
    """

    class exists_script_tag_with_cbid():
        """
        Internal utility class to check if there exists a script tag with the 'data-cbid' attribute.
        :return WebElement: first matching script tag, or None otherwise
        """
        def __call__(self, driver):
            elems = driver.find_elements_by_tag_name("script")
            for e in elems:
                try:
                    cbid = e.get_attribute("data-cbid")
                    if cbid and uuid_pattern.match(str(cbid)):
                        return e
                except StaleElementReferenceException:
                    logger.warning("Stale element exception while looking through script tags. Continuing with next one...")
                    continue

            return None


    def try_requests_approach(self, res: requests.Response) -> Tuple[str, CrawlState, str]:
        """
        Attempt the simple approach of parsing the requests response for the 'cbid' value.
        Fast if it works, but may not work because javascript and the page doesn't fully load.
        DEPRECATED: Better to always use Selenium
        :param res: Response to parse for the 'cbid' value.
        :return: PageState, cookie bot id, error report
            SUCCESS: cbid was found.
            PARSE_ERROR: failed to find cbid
            UNKNOWN: Unexpected Error
        """
        cbid: str = ""
        html: str = res.text
        bs = BeautifulSoup(html, features='html5lib')

        try:
            tags = bs.findAll("script")
            for t in tags:
                if t.has_attr("data-cbid"):
                    cbid = t["data-cbid"]
                    state = CrawlState.SUCCESS
                    report = "OK"
                    break
            else:
                variant_2 = variant_2_pattern.search(html)
                variant_3 = variant_3_pattern.search(html)
                if variant_2 or variant_3:
                    cbid = variant_2.group(1) if variant_2 else variant_3.group(1)
                    state = CrawlState.SUCCESS
                    report = "OK"
                else:
                    state = CrawlState.PARSE_ERROR
                    report = "Failed to find cbid in index.html during simple GET request approach"

        except Exception as ex:
            state = CrawlState.UNKNOWN
            report = f"Unexpected Error in \"try_requests_approach\": {type(ex)} {ex}"

        return cbid, state, report



    def try_selenium_approach(self, url) -> Tuple[str, CrawlState, str]:
        """
        Attempt to use Selenium to retrieve the 'cbid' value.
        Slower than requests library, but more reliable, as it can load the entire page with javascript enabled.
        :param url: URL to extract cbid value from.
        :return: PageState, cookie bot id, error report
            SUCCESS: cbid was found.
            PARSE_ERROR: failed to find cbid
            UNKNOWN: Unexpected Error
        """

        state, report = self.driver_get(url)
        if state != CrawlState.SUCCESS:
            return "", state, report
        try:
            try:
                # Variant 1: try to retrieve "data-cbid" attribute
                wait = WebDriverWait(self.webdriver, 3)
                element = wait.until(self.exists_script_tag_with_cbid())
                cbid = element.get_attribute("data-cbid")
                logger.info("Found cookie bot ID using first variant.")
                return cbid, CrawlState.SUCCESS, "OK"
            except TimeoutException:
                logger.info("Timeout while looking for cbid.")
            except StaleElementReferenceException as ex:
                logger.debug(f"Stale element exception encountered on \"{url}\".")
                logger.debug(f"Exception Details: {type(ex)} {ex}")

            logger.info("Attempting Variants 2 and 3")

            # Variant 2 & 3: CBID may actually be integrated into the URL itself, rather than being an attribute
            page_source = self.driver_get_current_pagesource()
            variant_2 = variant_2_pattern.search(page_source)
            variant_3 = variant_3_pattern.search(page_source)

            if variant_2 or variant_3:
                cbid = variant_2.group(1) if variant_2 else variant_3.group(1)
                return cbid, CrawlState.SUCCESS, "OK"
            else:
                return "", CrawlState.PARSE_ERROR, "All attempts to find cookiebot cbid failed."

        except Exception as ex:
            report = f"Unexpected error: : {type(ex)} {ex}"
            return "", CrawlState.UNKNOWN, report


    def try_retrieve_cbid(self, res: requests.Response, url: str) -> Tuple[str, CrawlState, str]:
        """
        Wrapper for retrieving the cookiebot UUID value.
        Currently only uses the Selenium approach.
        :param res: GET response to parse, from python requests library.
        :param url: URL to browse with the help of Selenium. URL and response should match.
        :return: Tuple(State, cookie bot id, error report)
        """
        #cbid, state, report = self.try_requests_approach(res)
        #if state == CrawlState.PARSE_ERROR:
            #logger.debug(f"Requests approach failed: {state} -- {report}")
        cbid, state, report = self.try_selenium_approach(url)
        return cbid, state, report


    def try_find_correct_referrer(self, cbid:str, fallback:str) -> str:
        """
        The referer required to access the Cookiebot data may differ from the site the request is made from.
        In this case, the referer is listed as an argument inside the cc.js URL itself. This extracts said URL.
        :param cbid: cookiebot ID previously discovered
        :param fallback: referer string to use if the referer URL cannot be found. Typically set to be the current URL.
        :return: Referer string, or defined fallback if referer cannot be found.
        """
        page_source = self.driver_get_current_pagesource()
        ref_pattern = re.compile(f"https://consent\\.cookiebot\\.com/{cbid}/cc\\.js.*(\\?|&amp;)referer=(.*?)&.*")
        m = ref_pattern.search(page_source)
        if m:
            new_referer = m.group(2)
            logger.debug(f"Found referrer: {new_referer}")
            return new_referer
        else:
            logger.debug(f"Could not find specific referrer, falling back to: {fallback}")
            return fallback


    def scrape_website(self, url: str, session: requests.Session) -> bool:
        """
        Cookiebot stores its category data in a javascript file called cc.js
        The crawling process attempts to obtain this file and read the data from it.
        :param url: URL to crawl for category data
        :param session: requests session to send requests to the cookiebot cdn
        """
        # First GET Request to see if site is reachable
        r, state, report = self.static_get_request(url, None, verify_ssl=True)

        if state != CrawlState.SUCCESS:
            self.update_crawl_stats(url, state, report)
            return False
        logger.debug("Connection successful.")

        # Retrieve CBID required to access cc.js
        cbid, state, report = self.try_retrieve_cbid(r, url)
        if state != CrawlState.SUCCESS:
            self.update_crawl_stats(url, state, report)
            return False
        logger.debug(f"Cookiebot UUID = {cbid}")

        referer = self.try_find_correct_referrer(cbid, url)

        # retrieve cc.js from cookiebot domain using persistent session
        cc_url = f"https://consent.cookiebot.com/{cbid}/cc.js?referer={referer}"
        cc_resp, state, report = self.static_get_request(cc_url, session=session, headers={"Referer": url})
        if state != CrawlState.SUCCESS:
            self.update_crawl_stats(url, CrawlState.LIBRARY_ERROR, report)
            return False

        # Some structural checks on cc.js
        js_contents = cc_resp.text
        if "CookieConsent.setOutOfRegion" in js_contents:
            self.update_crawl_stats(url, CrawlState.REGION_BLOCK, f"Received an out-of-region response from \"{cc_url}\": {js_contents}")
            return False
        elif re.search("cookiedomainwarning='Error: .* is not a valid domain.", js_contents):
            self.update_crawl_stats(url, CrawlState.LIBRARY_ERROR, f"Cookiebot doesn't recognize referer \"{referer}\" with cbid \"{cbid}\" as a valid domain.")
            return False
        elif len(js_contents.strip()) == 0:
            self.update_crawl_stats(url, CrawlState.LIBRARY_ERROR, f"Empty response when trying to retrieve \"{cc_url}\".")
            return False
        logger.debug(f"Successfully accessed \"https://consent.cookiebot.com/{cbid}/cc.js\"")

        # Finally, if we arrived here we likely found our cookie category data.
        cookie_count = 0
        try:
            for catname in cookiebot_catnames:
                cat_id = name_to_cat[catname]

                matchobj = category_patterns[cat_id].search(js_contents)
                if not matchobj:
                    logger.warning(f"Could not find array for category {catname}")
                    continue

                cookies = literal_eval(matchobj.group(1))
                cookie_count += len(cookies)
                for c in cookies:
                    self.collect_cookie_dat(site_url=url, name=c[0], domain=c[1], path="/",
                                            purpose=c[2], cat_name=catname, cat_id=cat_id, type=c[5])

        # In case any unexpected issues occur, handle them here and output a debug js
        except Exception as ex:
            if self.debug_mode:
                with open(os.path.join(self.logpath, f"debug_{cbid}_cc.js"), 'w') as fd:
                    fd.write(js_contents)

            self.update_crawl_stats(url, CrawlState.MALFORM_RESP, f"Failed to extract cookie data from {cc_url}: {type(ex)} {ex}")
            return False

        # if no cookies were found, record the fact
        if cookie_count == 0:
            if self.debug_mode:
                with open(os.path.join(self.logpath, f"debug_{cbid}_cc.js"), 'w') as fd:
                    fd.write(js_contents)
            self.update_crawl_stats(url, CrawlState.NO_COOKIES, f"No cookies found in {cc_url} ")
            return False

        # if we arrive here, report success
        logger.info(f"Extracted {cookie_count} cookie entries.")
        self.update_crawl_stats(url, CrawlState.SUCCESS, f"OK")
        return True
