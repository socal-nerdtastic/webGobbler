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

class collector_googleimages(collector):
    ''' Get images from random queries on Google Image search.
        http://images.google.com/
        Used by: imagePool
    '''
    RE_IMAGEURL = re.compile(r'imgurl=(http://.+?)&',re.DOTALL|re.IGNORECASE)
    def __init__(self,**keywords):
        collector.__init__(self,**keywords)
        self.name="collector_googleimages"
        self.imageurls = {}      # image URLs extracted from html result pages.
        self.waituntil = 0       # Wait until this date.
        self.collectURL = False  # Used to alternate between collecting URL and downloading images

    def _getRandomImage(self):
        if time.time()<self.waituntil:
            return
        self.collectURL = not self.collectURL # Alternate between querying the search engine an downloading images.
        if self.collectURL:  # Query the search engine.

            # First, let's see how many URL remain in our list of urls (self.imageurls)
            if len(self.imageurls)<500:  # If we have less than 500 images urls, make another query.
                wordToSearch = ""
                if self.CONFIG['collector.keywords.enabled']:
                    wordToSearch = self.CONFIG['collector.keywords.keywords']
                else:
                    wordToSearch = self._generateRandomWord()
                self._logDebug("Querying '%s'"%wordToSearch)
                self._setCurrentStatus('Querying',wordToSearch)
                # We also get a random result page (between 0-50)
                request_url = "http://images.google.com/images?q=%s&hl=en&start=%d" % (urllib.parse.quote_plus(wordToSearch),random.randint(0,50)*10)
                (htmlpage,results) = self._parsePage(request_url,collector_googleimages.RE_IMAGEURL)
                if not htmlpage:  # Error while getting page.
                    self._logWarning("Unable to contact google.com. Waiting 60 seconds.")
                    self._setCurrentStatus('Error','Unable to contact google.com. Waiting 60 seconds.')
                    self.waituntil = time.time()+60
                elif not results:  # Regex returned no result in page.
                    if "did not match any documents" in htmlpage:
                        self._logDebug("No results for this word.") # Our search was unsuccessfull.  Nevermind... we'll try another one later.
                        self._setCurrentStatus('Result','No results for this word.')
                    else:
                        self._logWarning("Found no image URL in this page. Website changed ?")
                        self._setCurrentStatus('Error','Found no image URL in this page. Website changed ?')
                        if self.CONFIG["debug"]:
                            filename = "debug_googleimages_%s.html"%hashlib.sha1(htmlpage).hexdigest()
                            self._logDebug("(See corresponding HTML page saved in %s)" % filename)
                            open(filename,"w+b").write(htmlpage) # Write bogus html page to debug
                        self.stopcollecting()
                else:   # Let's extract the image URLs.
                    for imageurl in results:
                        if random.randint(0,1)==1:  # We only keep some of these URLs.
                            imageurl = urllib.parse.unquote_plus(imageurl)
                            if not imageurl.startswith("http://"): imageurl = "http://"+imageurl
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
