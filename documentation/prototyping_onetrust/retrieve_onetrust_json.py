# Copyright (C) 2021-2022 Dino Bollinger, ETH Zürich, Information Security Group
# Licensed under BSD 3-Clause License, see included LICENSE file
"""
Retrieve the OneTrust cookie data storage file.

Usage: retrieve_onetrust_js.py <url> """

import re
import requests
import json
from bs4 import BeautifulSoup
from docopt import docopt
from selenium import webdriver
from selenium.common.exceptions import TimeoutException

ddid_pattern = "[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"


def variant_one(url: str) -> int:
    """
    Variant 1
    :param url: URL to retrieve ddid from
    """
    # First attempt, simple get request for the index (could fail because of page not loading fully)
    # Faster than using selenium
    dd_id = None
    try:
        r = requests.get(url, timeout=(5, 10))

        with open(f"index.html", 'w') as fd:
            print(f"Writing index.html from {url} to disk...")
            fd.write(r.text)

        html = r.text
        bs = BeautifulSoup(html, features='html5lib')

        tags = bs.findAll("script")
        for t in tags:
            if t.has_attr("data-domain-script"):
                if re.match(ddid_pattern, t["data-domain-script"]):
                    dd_id = t["data-domain-script"]
                    print(dd_id)
                    break
    except requests.Timeout:
        print("Timeout")

    # Second attempt: Use Selenium. Slower, but sure to find the id.
    if dd_id is None:
        print("second attempt")
        driver = webdriver.Firefox()
        driver.get(url)
        try:
            driver.implicitly_wait(5)
            elems = driver.find_elements_by_tag_name("script")
            for e in elems:
                try:
                    dd_id = e.get_attribute("data-domain-script")
                    if (dd_id is not None) and re.match(ddid_pattern, str(dd_id)):
                        print(dd_id)
                        break
                except Exception as ex:
                    print(ex)
                    # Following error may occur: Message: The element reference of <script id="scr653042142_774854207" src="https://accdn.lpsnmedia.net/api/account/48719195/configuration/setting/accountproperties/?cb=lpCb84374x27975" type="text/javascript"> is stale; either the element is no longer attached to the DOM, it is not in the current frame context, or the document has been refreshed
                    return 1

        except TimeoutException:
            print("Timeout reached.")
        finally:
            driver.close()

        if dd_id is None:
            print("Failed to retrieve dd_id after second try. Aborting...")
            return 1

    print("dd_id found")
    cookielaw_ruleset_json = requests.get(f"https://cdn.cookielaw.org/consent/{dd_id}/{dd_id}.json")

    with open("cookielaw_ruleset.json", 'w') as fd:
        fd.write(cookielaw_ruleset_json.text)

    ids = []
    rs_dict = json.loads(cookielaw_ruleset_json.text)
    for r in rs_dict["RuleSet"]:
        if "en" in r["LanguageSwitcherPlaceholder"].values():
            ids.append(r["Id"])

    if len(ids) == 0:
        print("no ids found, aborting")
        return 1

    print(f"Found {len(ids)} ids")
    for i in ids:
        print(i)
        cc_json = requests.get(f"https://cdn.cookielaw.org/consent/{dd_id}/{i}/en.json")
        with open(f"{i}_en.json", 'w') as fd:
            fd.write(cc_json.text)

    return 0


def variant_two(url):
    """
    Second variant of the OneTrust CMP storage
    """
    js_link = None

    try:
        r = requests.get(url, timeout=(5, 10))

        with open(f"index.html", 'w') as fd:
            print(f"Writing index.html from {url} to disk...")
            fd.write(r.text)

        html = r.text
        bs = BeautifulSoup(html, features='html5lib')

        cbid = None

        tags = bs.findAll("script")
        for t in tags:
            if t.has_attr("src"):
                source = t["src"]
                matchobj = re.match(f"https://cdn\\.cookielaw\\.org/consent/{ddid_pattern}\\.js", t["src"])
                if matchobj:
                    js_link = matchobj.group(0)
                    print(js_link)
                    break
    except requests.Timeout as ex:
        print("Timeout")

    # Second attempt: Use Selenium. Slower, but sure to find the id.
    if js_link is None:
        print("second attempt")
        driver = webdriver.Firefox()
        driver.get(url)
        element = None
        try:
            driver.implicitly_wait(5)
            elems = driver.find_elements_by_tag_name("script")
            for e in elems:
                try:
                    source = e.get_attribute("src")
                    if source:
                        matchobj = re.match(f"https://cdn\\.cookielaw\\.org/consent/{ddid_pattern}\\.js", source)
                        if matchobj:
                            js_link = matchobj.group(0)
                            print(js_link)
                            break
                except Exception as ex:
                    print(ex)
                    driver.close()
                    return 1

        except TimeoutException:
            print("Timeout reached.")
        finally:
            driver.close()

        if js_link is None:
            print("Failed to retrieve javascript link after second try. Aborting...")
            return 1

    print("javascript link found")
    cookielaw_script = requests.get(js_link).text.strip()
    # purge random dumbass newlines
    cookielaw_script = re.sub('\n', ' ', cookielaw_script)

    with open("variant2_cl_script.js", 'w') as fd:
        fd.write(cookielaw_script)

    # Attempt to extract inline json from javascript document
    matchobj = re.search("=({cctId.*?})\\);", cookielaw_script)
    if matchobj:
        # Try to transform the javascript object in a way such that it can be parsed as JSON.
        json_data = matchobj.group(1)
        json_data = re.sub(r"!", r'', json_data)
        json_data = re.sub(r"(\w+):(?!//)", r'"\1":', json_data)
        json_data = re.sub(r":(\w+)", r':"\1"', json_data)
        json.loads(json_data)
        with open(f"variant2_en.json", 'w', encoding='utf-8') as fd:
            fd.write(json_data)
        return 0
    else:
        print("Failed to find inline json in cookielaw javascript file")
        return 1


def main():
    """ Test script to retrieve consent label data for OneTrust """
    argv = None
    # argv = ["https://www.maytag.com"]
    # argv = ["https://www.metabomb.net/"]
    # argv = ["https://www.aveda.com/"]
    # argv = ["https://www.equipmenttrader.com/"]
    args = docopt(__doc__, argv=argv)

    url = args["<url>"]
    exit_code = variant_one(url)
    if exit_code != 0:
        exit_code = variant_two(url)

    if exit_code:
        print("failure")
        return exit_code
    else:
        print("success")
        return 0


if __name__ == "__main__":
    exit_code = main()
    exit(exit_code)
