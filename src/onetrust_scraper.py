# Copyright (C) 2021-2022 Dino Bollinger
# Created as part of a master thesis at ETH Zürich, Information Security Group
# Licensed under BSD 3-Clause License, see included LICENSE file
"""
OneTrust Scraper: Defines the src used for OneTrust's various consent management providers.
Currently only supports English Cookie Consent Data.

The following domains are associated with the OneTrust CMP:
   - https://cdn.cookielaw.org
   - https://optanon.blob.core.windows.net
   - https://cookie-cdn.cookiepro.net
   - https://cookiepro.blob.core.windows.net

The data is generally stored in two variants:
  Variant A: Remotely hosted as a JSON file not directly referenced in the index.html. This json file needs to retrieved using
             a secondary JSON file which contains the ruleset IDs, which in turn point towards the JSON storing the actual cookie
             consent data. Many ruleset IDs may be stored for the same website -- we simply extract data for all of them.
             This variant is easy to parse as it has already been turned into properly formatted JSON.
  Variant B: Directly integrated into a javascript file as an object. Directly referenced in the index.html but much harder to parse
             due to special characters and bad formatting in many cases. This is the more commonly seen variant.
             Note that internally, while similar at first glance, the objects of variant A and variant B do not have the same structure,
             and need to be parsed in a completely different manner.
"""
import requests
import logging
import re
import json
import js2py

from typing import Optional, List, Tuple, Dict, Any
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException

from src.base_scraper import BaseScraper, CrawlState, CookieCategory, uuid_pattern

logger = logging.getLogger("main.BaseScraper.OneTrustScraper")

# Base patterns required for Variant A
cookielaw_base_pattern = re.compile("(https://cdn\\.cookielaw\\.org)")
optanon_base_pattern = re.compile("(https://optanon\\.blob\\.core\\.windows\\.net)")
cookiecdn_base_pattern = re.compile("(https://cookie-cdn\\.cookiepro\\.com)")
cookiepro_base_pattern = re.compile("(https://cookiepro\\.blob\\.core\\.windows\\.net)")

base_patterns = [cookielaw_base_pattern, optanon_base_pattern, cookiecdn_base_pattern, cookiepro_base_pattern]

# Javascript direct links, required for Variant B
v2_cookielaw_pattern = re.compile("https://cdn\\.cookielaw\\.org/consent/" + uuid_pattern.pattern + "[a-zA-Z0-9_-]*\\.js")
v2_optanon_pattern = re.compile("https://optanon\\.blob\\.core\\.windows\\.net/consent/" + uuid_pattern.pattern + "[a-zA-Z0-9_-]*\\.js")
v2_cookiepro_cdn_pattern = re.compile("https://cookie-cdn\\.cookiepro\\.com/consent/" + uuid_pattern.pattern + "[a-zA-Z0-9_-]*\\.js")
v2_cookiepro_blob_pattern = re.compile("https://cookiepro\\.blob\\.core\\.windows\\.net/consent/" + uuid_pattern.pattern + "[a-zA-Z0-9_-]*\\.js")

variantB_patterns = [v2_cookielaw_pattern, v2_optanon_pattern, v2_cookiepro_cdn_pattern, v2_cookiepro_cdn_pattern]


class VariantFailedException(Exception):
    """ Raise when a variant of crawling fails -- should be handled such that the next variant is attempted. """

    def __init__(self, crawlstate: CrawlState, message: str, *args):
        self.crawlstate: CrawlState = crawlstate
        self.message: str = message
        super(VariantFailedException, self).__init__(message, *args)


# Unlike Cookiebot, OneTrust does not have uniform category names.
# To that end, we use simple keyword indicators that map a category name to the 5 fixed categories.
necessary_pattern = re.compile("(necessary|essential|required)", re.IGNORECASE)
analytical_pattern = re.compile("(measurement|analytic|anonym|research|performance)", re.IGNORECASE)
functional_pattern = re.compile("(functional|preference|security|secure)", re.IGNORECASE)
advertise_pattern = re.compile("(^ads.*|.*\s+ads.*|Ad Selection|advertising|advertise|targeting"
                               "|sale of personal data|marketing|tracking|tracker|fingerprint)", re.IGNORECASE)

uncat_pattern = re.compile("(uncategori[zs]e|unknown)", re.IGNORECASE)


# The ordering here is important and has been purposefully chosen.
def category_lookup_en(cat_name):
    if advertise_pattern.search(cat_name): return CookieCategory.ADVERTISING
    elif necessary_pattern.search(cat_name): return CookieCategory.ESSENTIAL
    elif analytical_pattern.search(cat_name): return CookieCategory.ANALYTICAL
    elif functional_pattern.search(cat_name): return CookieCategory.FUNCTIONAL
    elif uncat_pattern.search(cat_name): return CookieCategory.UNCLASSIFIED
    else:
        logger.warning(f"Unrecognized category name: {cat_name}")
        return CookieCategory.UNKNOWN


class OneTrustScraper(BaseScraper):

    def variantA_try_retrieve_uuid(self, url: str) -> Tuple[str, str, CrawlState, str]:
        """
        Extract "data-domain-script" attribute from script tag inside 'index.html'.
        This will allow us to access the cookielaw ruleset json.
        :return: source domain, data domain id, or None if not found (+ state and report)
        """
        state, report = self.driver_get(url)
        if state != CrawlState.SUCCESS:
            return "", "", state, report

        try:
            self.webdriver.implicitly_wait(5)
            elems = self.webdriver.find_elements_by_tag_name("script")
            for e in elems:
                try:
                    # Find a script tag with the  data-domain-script attribute
                    dd_id = str(e.get_attribute("data-domain-script"))
                    if (dd_id is not None) and uuid_pattern.match(str(dd_id)):
                        source_stub = e.get_attribute("src")
                        if source_stub is None:
                            logger.warning(f"Found a script tag with the data-domain attribute, but no URL? Script ID: {dd_id}")
                            continue
                        else:
                            for pat in base_patterns:
                                m = pat.match(source_stub)
                                if m:
                                    return m.group(1), dd_id, CrawlState.SUCCESS, "Found data-domain-script id"
                                else:
                                    logger.debug(f"no match for pattern {pat.pattern} on {source_stub}")
                            else:
                                logger.warning(f"Found a data-domain-script tag with unknown source URL: {source_stub}. Script ID: {dd_id}")

                except StaleElementReferenceException as ex:
                    logger.warning(f"Stale Element Exception -- skipping to next script tag.")
                    logger.debug(f"Exception Details: {type(ex)} {ex}")
                    continue

                except Exception as ex:
                    return "", "", CrawlState.UNKNOWN, f"Unexpected error while retrieving dd-id: : {type(ex)} {ex}"

        except TimeoutException:
            logger.error("Timeout on trying to retrieve data domain id value.")


        # If we arrived here, no script held the desired attribute
        return "", "", CrawlState.PARSE_ERROR, f"Could not find data-domain script id on website: {url}"


    def variantA_try_retrieve_ruleset_id(self, domain_url:str, dd_id:str, sess: requests.Session) -> Tuple[List[str], CrawlState, str]:
        """
        Using the data-domain id, parse a list of rulesets from a json file stored on cookielaw.org,
        and extract IDs that will help retrieving the json files storing the actual cookie category data.
        :param domain_url: Domain on which to access the ruleset json
        :param dd_id: Data domain ID (UUID) that is used to retrieve the ruleset json
        :param sess: requests session that is persistently connected to cookielaw
        :return: (cookie json ids, crawl state, report). List of ids may be empty if none found.
        """
        target_url = f"{domain_url}/consent/{dd_id}/{dd_id}.json"
        ruleset_json, state, report = self.static_get_request(target_url, session=sess)

        if state != CrawlState.SUCCESS:
            return [], state, report

        ids = []
        rs_dict = json.loads(ruleset_json.text)

        try:
            rulesets = rs_dict["RuleSet"]
            if rulesets is None:
                return [], CrawlState.PARSE_ERROR, f"No valid 'RuleSet' element found on {target_url}"
            else:
                for r in rulesets:
                    languageset = r["LanguageSwitcherPlaceholder"]
                    if languageset is None:
                        continue
                    if "en" in languageset.values():
                        ids.append(r["Id"])

            if len(ids) == 0:
                return [], CrawlState.PARSE_ERROR, f"No valid language ruleset found on {target_url}"

            return ids, CrawlState.SUCCESS, f"Found {len(ids)} ruleset ids"
        except (AttributeError, KeyError) as kex:
            return [], CrawlState.PARSE_ERROR, f"Key Error on {target_url} -- Details: {kex}"


    def variantA_get_and_parse_json(self, website_url, domain_url:str, dd_id:str, ruleset_ids: List[str],
                                    sess: requests.Session) -> Tuple[int, CrawlState, str]:
        """
        Retrieve and parse the json files from the domain URL storing the cookie categories.
        Currently supports only english language json.
        The raw cookie data will be stored internally and can later be persisted to disk.
        :param website_url: URL of the website that was targetted.
        :param domain_url: Domain on which to access the consent data json
        :param dd_id: Data domain ID, previously extracted before retrieving the ruleset ids.
        :param ruleset_ids: List of ids extracted from the ruleset json.
        :param sess: persistent connection, helps with repeated accesses
        :return: number of cookies extracted, crawl state, report
        """
        cookie_count = 0
        for i in ruleset_ids:
            curr_ruleset_url = f"{domain_url}/consent/{dd_id}/{i}/en.json"
            cc_json, state, report = self.static_get_request(curr_ruleset_url, session=sess, verify_ssl=True)

            if state != CrawlState.SUCCESS:
                logger.error(f"Failed to retrieve ruleset at: {curr_ruleset_url}")
                logger.error(f"Details: {state} -- {report}")
                continue

            # parse json for data
            try:
                json_data = json.loads(cc_json.text)
                json_body = json_data["DomainData"]

                if "en" in json_body["Language"]["Culture"]:
                    cat_lookup = category_lookup_en
                else:
                    logger.warning(f"Unrecognized language in ruleset: {json_body['Language']['Culture']}")
                    continue

                group_list = json_data["DomainData"]["Groups"]
                for g_contents in group_list:
                    cat_name = g_contents["GroupName"]
                    cat_id = cat_lookup(cat_name)

                    firstp_cookies = g_contents["FirstPartyCookies"]
                    for c in firstp_cookies:
                        cdesc = c["description"] if "description" in c else None
                        self.collect_cookie_dat(site_url=website_url, name=c["Name"], domain=c["Host"], path="/",
                                                purpose=cdesc, cat_id=cat_id, cat_name=cat_name, type=None)
                        cookie_count += 1

                    thirdp_cookies = g_contents["Hosts"]
                    for host_dat in thirdp_cookies:
                        for c in host_dat["Cookies"]:
                            cdesc = c["description"] if "description" in c else None
                            self.collect_cookie_dat(site_url=website_url, name=c["Name"], domain=c["Host"], path="/",
                                                    purpose=cdesc, cat_id=cat_id, cat_name=cat_name, type=None)
                            cookie_count += 1

            except (AttributeError, KeyError) as ex:
                logger.error(f"Could not retrieve an expected attribute from json for ruleset : {curr_ruleset_url}.")
                logger.error(f"Details: {type(ex)} -- {ex}")
            except json.JSONDecodeError as ex:
                logger.error(f"Failed to decode json file for ruleset : {curr_ruleset_url}")
                logger.error(f"Details: {type(ex)} -- {ex}")

        if cookie_count == 0:
            logger.error(f"Could not extract any cookies for ddid: {dd_id} and rulesets {ruleset_ids}")
            return cookie_count, CrawlState.PARSE_ERROR, f"Failed to extract cookies from rulesets: {ruleset_ids}"

        return cookie_count, CrawlState.SUCCESS, f"Cookies Extracted: {cookie_count}"



    def variantB_retrieve_script_path(self, url:str) -> Tuple[str, CrawlState, str]:
        """
        Directly retrieve the link to the javascript containing the onetrust consent categories.
        Looks for domains of the form https://<domain>/consent/<UUID>.js
        :param url: Domain to retrieve the script from. Will be navigated to using Selenium.
        :return: url to js or empty if not found; crawl state; report
        """
        state, report = self.driver_get(url)
        if state != CrawlState.SUCCESS:
            return "", state, report

        try:
            self.webdriver.implicitly_wait(5)
            elems = self.webdriver.find_elements_by_tag_name("script")
            for e in elems:
                try:
                    source = e.get_attribute("src")
                    if source:
                        # any of them match --> extract URL. otherwise, continue to next script tag
                        for pattern in variantB_patterns:
                            matchobj = pattern.match(source)
                            if matchobj:
                                return matchobj.group(0), CrawlState.SUCCESS, "Found OneTrust consent javascript link"

                except StaleElementReferenceException as ex:
                    logger.warning(f"Stale element exception: {str(e)} -- skipping to next script tag.")
                    logger.debug(f"Exception Details: {type(ex)}  -- {ex}")
                    continue
                except Exception as ex:
                    return "", CrawlState.UNKNOWN, f"Unexpected error while retrieving javascript link: : {type(ex)} {ex}"

        except TimeoutException:
            logger.error("Variant B: Timeout on trying to retrieve onetrust javascript link.")
            return "", CrawlState.CONN_FAILED, f"Variant B: Timed out trying to find OneTrust javascript tags."

        # If we arrived here, no script held the desired attribute
        return "", CrawlState.PARSE_ERROR, f"Variant B: Could not find OneTrust javascript url in any tag."


    def variantB_parse_script_for_object(self, script_url: str) -> Tuple[Optional[Dict], CrawlState, str]:
        """
        Extract the consent data from an inline json object. This assumes that inside the object,
        the array "Groups" is found. Inside this array we can find all the cookie data we need
        -- however, the object needs to be sanitized first, and stray characters need to be removed.

        The process isn't perfect, but it should work with a sufficient number of instances.
        """
        cookielaw_script = requests.get(script_url).text.strip()

        # purge newlines
        cookielaw_script = re.sub('\n', ' ', cookielaw_script)

        # Find the start of the group array
        matchobj = re.search(",\\s*Groups:\\s*\\[", cookielaw_script)
        try:
            if matchobj:
                startpoint = matchobj.start(0)

                # Get the end of the group array
                i = matchobj.end(0)
                open_brackets = 1
                while i < len(cookielaw_script) and open_brackets > 0:
                    if cookielaw_script[i] == "[": open_brackets += 1
                    elif cookielaw_script[i] == "]": open_brackets -= 1
                    i += 1
                group_string = cookielaw_script[startpoint+1:i]

                # put the object into a javascript function, and evaluate it
                # This returns a dict of the cookie consent data we need.
                js_object_string = "function $() {return {" + group_string + "}};"
                data_dict = js2py.eval_js(js_object_string)()

                return data_dict, CrawlState.SUCCESS, "Successfully extracted objects from javascript"
            else:
                return None, CrawlState.PARSE_ERROR, "Failed to find desired javascript object in Onetrust consent script."
        except Exception as ex:
            return None, CrawlState.UNKNOWN, f"Unexpected error while parsing OneTrust javascript: : {type(ex)} {ex}"


    def variantB_extract_cookies_from_dict(self, website_url:str, consent_data: Dict[str, Any]) -> Tuple[int, CrawlState, str]:
        """
        Using the cookie data dictionary from the previous step, extract the data contained within and store it.
        :param website_url: URL of the target website.
        :param consent_data: Cookie data dictionary extracted from previous step.
        :return: number of cookies extracted, crawl state, report
        """
        cookie_count = 0
        try:

            # only support english at this time
            cat_lookup = category_lookup_en

            g_data = consent_data["Groups"]
            for g_contents in g_data:
                if g_contents["Parent"] is None:
                    cat_name = g_contents["GroupLanguagePropertiesSets"][0]["GroupName"]["Text"]
                else:
                    cat_name = g_contents["Parent"]["GroupLanguagePropertiesSets"][0]["GroupName"]["Text"]
                cat_id = cat_lookup(cat_name)

                for cookie_dat in g_contents["Cookies"]:
                    cname = cookie_dat["Name"] # not null
                    chost = cookie_dat["Host"] # not null
                    cdesc = cookie_dat["description"] if "description" in cookie_dat else None
                    self.collect_cookie_dat(site_url=website_url, name=cname, domain=chost, path="/",
                                            purpose=cdesc, cat_id=cat_id, cat_name=cat_name, type=None)
                    cookie_count += 1

        except (AttributeError, KeyError) as ex:
            logger.error(f"Could not retrieve an expected attribute from consent data dict.")
            return 0, CrawlState.PARSE_ERROR, f"{type(ex)} - {ex}"

        if cookie_count == 0:
            return 0, CrawlState.MALFORM_RESP, "Consent Platform Script contained zero cookies!"
        else:
            return cookie_count, CrawlState.SUCCESS, f"Successfully retrieved {cookie_count} cookies."


    def scrape_website(self, url: str, sess: requests.Session) -> bool:
        """
        Extract cookie category data from the OneTrust Cookie Consent Provider.
        The category data is found in json, either separate or as an inline document inside javascript.
        The crawling process attempts to obtain this data and read the data from it.
        :param url: URL to crawl for category data
        :param sess: Session for frequent requests to the same site.
        """
        # First GET Request to see if site is reachable at all
        r, status, report = self.static_get_request(url, None, verify_ssl=True)

        if status != CrawlState.SUCCESS:
            self.update_crawl_stats(url, status, report)
            return False
        logger.debug(f"Connection to {url} successful.")

        try:
            # Variant A, Part 1: Retrieve data domain id
            domain_url, dd_id, state, report = self.variantA_try_retrieve_uuid(url)
            if state != CrawlState.SUCCESS:
                raise VariantFailedException(state, report)
            logger.debug(f"Onetrust data domain url = {domain_url}/{dd_id}")

            # Variant A, Part 2: Using the data domain ID, retrieve ruleset ID list
            rs_ids, state, report = self.variantA_try_retrieve_ruleset_id(domain_url, dd_id, sess)
            if state != CrawlState.SUCCESS:
                raise VariantFailedException(state, report)
            logger.info(f"Found {len(rs_ids)} ruleset ids")
            logger.debug(f"{rs_ids}")

            # Variant A, Part 3: For each ruleset id, retrieve cookie json
            cookie_count, state, report = self.variantA_get_and_parse_json(url, domain_url, dd_id, rs_ids, sess)
            if state != CrawlState.SUCCESS:
                raise VariantFailedException(state, report)
            else:
                self.update_crawl_stats(url, state, report)
                logger.info(f"VARIANT A SUCCESS -- retrieved {cookie_count} cookies")
                return True

        except VariantFailedException as v1:
            logger.warning(f"Variant A failed. Reason: {v1.crawlstate} -- {v1.message}")

        try:
            logger.info(f"Attempting Variant B")

            # Variant B, Part 1: Obtain the javascript URL
            script_url, state, report = self.variantB_retrieve_script_path(url)
            if state != CrawlState.SUCCESS:
                raise VariantFailedException(state, report)
            logger.debug(f"Onetrust javascript url = {script_url}")

            # Variant B, Part 2: Access the script and retrieve raw data from it
            data_dict, state, report = self.variantB_parse_script_for_object(script_url)
            if state != CrawlState.SUCCESS:
                raise VariantFailedException(state, report)
            logger.debug(f"Successfully retrieved OneTrust Consent javascript object data.")

            # Variant B, Part 3: Extract the cookie values from raw data
            cookie_count, state, report = self.variantB_extract_cookies_from_dict(url, data_dict)
            if state != CrawlState.SUCCESS:
                raise VariantFailedException(state, report)
            else:
                self.update_crawl_stats(url, state, report)
                logger.info(f"VARIANT B SUCCESS -- retrieved {cookie_count} cookies")
                return True

        except VariantFailedException as v2:
            self.update_crawl_stats(url, v2.crawlstate, v2.message)
            return False

