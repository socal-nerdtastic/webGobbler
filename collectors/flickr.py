#!/usr/bin/python3

import urllib.request, urllib.parse, urllib.error
import re
import time
import hashlib
import random

try:
    from collectors.meta import collector, internetImage
except ImportError:
    from meta import collector, internetImage

class collector_flickr(collector):
    ''' Get images from flickr.com.
        http://flickr.com
        Used by: imagePool
    '''
    name="collector_flickr"
    source="Flickr"

    # Regexp to get all images (eg. "http://static.flickr.com/36/94902996_d58bec5e04_t.jpg") from http://flickr.com/photos/?start=x
    #                                http://farm9.staticflickr.com/8540/8631778383_0724517a90_t.jpg
    RE_FLICKR_IMAGEURL = re.compile(r'src="(http://farm\d+.staticflickr.com.+?_t\.jpg)" width',re.DOTALL|re.IGNORECASE)
    RE_GOOGLEIMAGES_IMAGEURL = re.compile(r'imgurl=(http://.+?)&',re.DOTALL|re.IGNORECASE)
    #RE_IMAGEURL = re.compile('<img src="(http://www.randomimage.us/files/.+?)"',re.DOTALL|re.IGNORECASE)
    def __init__(self,**keywords):
        collector.__init__(self,**keywords)
        self.imageurls = {}  # URLs of images (eg."http://static.flickr.com/36/94902996_d58bec5e04_o.jpg")
        self.waituntil = 0         # Wait until this date.
        self.collectURL = False     # Used to alternate between collecting URL and downloading images

    def _getRandomImage(self):
        if time.time()<self.waituntil:
            return
        self.collectURL = not self.collectURL
        if self.collectURL:   # Collect image URLs
            # First, let's see how many URL remain in our list of urls (self.imageurls)
            if len(self.imageurls)<100:  # If we have less than 500 urls, let's get more images URLs.
                request_url = ''
                (htmlpage,results) = (None,None)
                if self.CONFIG['collector.keywords.enabled']: # Search by keyword
                    wordToSearch = self.CONFIG['collector.keywords.keywords']
                    self._logDebug("Querying '%s'" % wordToSearch)
                    self._setCurrentStatus('Querying',wordToSearch)
                    # This looks ridiculous: flickr has more than 10 BILLION photos but won't let you search beyond page 67.
                    # So I use Google Image Search with site:flickr.com
                    request_url = "http://images.google.com/images?q=site%%3Aflickr.com+%s&hl=en&start=%d" % (urllib.parse.quote_plus(wordToSearch),random.randint(0,50)*10)
                    (htmlpage,results) = self._parsePage(request_url,collector_flickr.RE_GOOGLEIMAGES_IMAGEURL)
                else:  # Random images:
                    pageNumber = random.randint(1,999999999)
                    self._logDebug("Getting 'Most recent photos' page %d" % pageNumber)
                    self._setCurrentStatus('Querying',"Getting 'Most recent photos' page %d" % pageNumber)
                    request_url = "http://flickr.com/photos/?start=%d" % pageNumber
                    (htmlpage,results) = self._parsePage(request_url,collector_flickr.RE_FLICKR_IMAGEURL)

                if not htmlpage:  # Error while getting page.
                    self._logWarning("Unable to contact website. Waiting 60 seconds.")
                    self._setCurrentStatus('Error','Unable to contact website. Waiting 60 seconds.')
                    self.waituntil = time.time()+60
                elif not results:
                    if "Your search didn't match any photos." in htmlpage:
                        # No results, let's try again (we probably used a page number too high)
                        self.collectURL = True
                    else:
                        self._logWarning("Found no image URL in this page. Website changed ?")
                        self._setCurrentStatus('Error','Found no image URL in this page. Website changed ?')
                        if self.CONFIG["debug"]:
                            filename = "debug_flickr_%s.html"%hashlib.sha1(htmlpage).hexdigest()
                            self._logDebug("(See corresponding HTML page saved in %s)" % filename)
                            open(filename,"w+b").write(htmlpage) # Write bogus html page to debug
                        self.stopcollecting()
                else:
                    for imageurl in results:
                        # Keep some of those URLs in memory (and put the URLs in a dictionnary to remove duplicates)
                        if random.randint(0,3)==1:
                            if not imageurl.startswith("http://"):
                                imageurl = "http://"+imageurl
                            imageurl = imageurl.replace("_t.jpg","_b.jpg").replace("_m.jpg","_b.jpg")
                            # _t is for "Thumbnail", "_m" is for "medium size", "_o" is for "original size".
                            self.imageurls[imageurl] = 0  # Put in the dictionnary to remove duplicates
        else:  # Download images:
            if len(self.imageurls)>0:
                imageurl = random.choice(list(self.imageurls.keys()))  # Choose a random image URL.
                del self.imageurls[imageurl]  # Remove it from list
                self._logDebug(imageurl)
                self._setCurrentStatus('Downloading',imageurl)
                i = internetImage(imageurl,self.CONFIG)   # Download the image
                if i.isNotAnImage:
                    self._logDebug("Image discarded because %s." % i.discardReason)
                else:  # We do not make other checks on the image. We always consider the image is OK.
                    i.saveToDisk(self.CONFIG["pool.imagepooldirectory"])
                    self.numberOfImagesToGet -= 1   # One less !
