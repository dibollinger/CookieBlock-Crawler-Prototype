# Copyright (C) 2021-2022 Dino Bollinger, ETH Zürich, Information Security Group
# Licensed under BSD 3-Clause License, see included LICENSE file
""" Try to retrieve the cc.js file for Cookiebot.
Usage: retrieve_cookiebot_js.py <url> """

import re
import requests
from bs4 import BeautifulSoup
from docopt import docopt
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException

class exists_script_tag_with_cbid:
    """Class to check if there exists a script tag with the data-cbid attribute.

    :param attribute: used to find the element
    :return WebElement: first matching script tag, or False otherwise
    """
    idhash_pattern = "[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"

    def __call__(self, driver):
      elems = driver.find_elements_by_tag_name("script")
      for e in elems:
          cbid = e.get_attribute("data-cbid")
          if cbid and re.match(self.idhash_pattern, str(cbid)):
              return e
      return False


if __name__ == "__main__":
    args = docopt(__doc__)

    url = args["<url>"]
    r = requests.get(url)

    with open("index.html", 'w') as fd:
        fd.write(r.text)

    html = r.text
    bs = BeautifulSoup(html, features='html5lib')

    cbid = None

    # first attempt:
    tags = bs.findAll("script")
    for t in tags:
        if t.has_attr("data-cbid"):
           cbid = t["data-cbid"]
           break

    # second attempt:
    if cbid is None:
        print("second attempt")
        tag = bs.find(id="Cookiebot")
        if tag is not None:
            cbid = tag["data-cbid"]

    # third attempt (required for some sites like gamefly)
    if cbid is None:
        print("third attempt")
        driver = webdriver.Firefox()
        driver.get(url)
        element = None

        try:
            wait = WebDriverWait(driver, 10)
            element = wait.until(exists_script_tag_with_cbid())
            cbid = element.get_attribute("data-cbid")
        except TimeoutException:
            print("Timeout reached.")
        finally:
            driver.close()

        if cbid is None:
            print("Failed to retrieve cbid on third try. Aborting...")
            exit(1)

    print(cbid)
    print("cbid found")
    cc_r = requests.get(f"https://consent.cookiebot.com/{cbid}/cc.js", headers={"Referer": url})
    with open("cc.js", 'w') as fd:
        fd.write(cc_r.text)
