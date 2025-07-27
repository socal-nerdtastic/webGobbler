#!/usr/bin/python3

import urllib.request, urllib.parse, urllib.error
import re
import time
import hashlib
import random
import json

try:
    from collectors.meta import collector, internetImage
except ImportError:
    from meta import collector, internetImage

subreddits = [
    "r/pics/",
    "r/funny/",
    "r/memes/",
    "r/art/",
    "r/aww/",
]

class collector_reddit(collector):
    ''' Get the top 100 images from each of the given subreddits
        https://www.reddit.com
        Used by: imagePool
        TODO: get more than 100 from each subreddit
    '''
    name="collector_reddit"
    source = "Reddit"

    def __init__(self, **keywords):
        collector.__init__(self,**keywords)
        self.imageurls = []      # image URLs extracted from html result pages.
        self.waituntil = 0       # Wait until this date.
        self.collectURL = None  # Used to alternate between collecting URL and downloading images

    def _getRandomImage(self):
        if time.time()<self.waituntil:
            return

        # First, let's see how many URL remain in our list of urls (self.imageurls)
        if len(self.imageurls)<10:  # If we have less than 50 images urls, make another query.
            self.collectURL = 0
            self.imageurls.clear()

        if self.collectURL is None:
            self.download_image()
        else:
            self.gather_links()

    def gather_links(self):
        subreddit = subreddits[self.collectURL]
        self.collectURL += 1
        if len(subreddits) <= self.collectURL:
            self.collectURL = None

        self._logDebug("Querying reddit")
        self._setCurrentStatus('Querying', subreddit)

        url = "https://www.reddit.com/"+subreddit+".json?limit=100"
        data, _ = self._parsePage(url)
        n = json.loads(data)
        children = n['data']['children']
        self.imageurls += [child['data']['url'] for child in children]
        random.shuffle(self.imageurls)

    def download_image(self):
        imageurl = self.imageurls.pop()  # Choose a random image URL.
        self._logDebug(imageurl)
        self._setCurrentStatus('Downloading',imageurl)
        i = internetImage(imageurl,self.CONFIG)   # Download the image
        if i.isNotAnImage:
            self._logDebug("Image discarded because %s." % i.discardReason)
        else:  # We do not make other checks on the image. We always consider the image is OK.
            i.saveToDisk(self.CONFIG["pool.imagepooldirectory"])

"""
from collectors import reddit
config={"network.http.useragent":"webGobbler/3.0.0"}
n = reddit.collector_reddit(config=config)
n._getRandomImage()
"""
