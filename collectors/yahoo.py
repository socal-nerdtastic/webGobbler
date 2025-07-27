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

class collector_yahooimagesearch(collector):
    ''' Get images from random queries on Yahoo Image search engine.
        http://search.yahoo.com/images/
        (AllTheWeb.com image search also uses Yahoo database.)
        Used by: imagePool
    '''
    #RE_IMAGEURL = re.compile('&imgcurl=(.+?)&',re.DOTALL|re.IGNORECASE)
    RE_IMAGEURL = re.compile('&imgurl=(.+?)&',re.DOTALL|re.IGNORECASE)
    def __init__(self,**keywords):
        collector.__init__(self,**keywords)
        self.name="collector_yahooimagesearch"
        self.imageurls = {}  # image URLs extracted from html result pages.
        self.waituntil = 0         # Wait until this date.
        self.collectURL = True     # Used to alternate between collecting URL and downloading images

    def _getRandomImage(self):
        if time.time()<self.waituntil:
            return
        if self.collectURL:
            self.collectURL = not self.collectURL
            # First, let's see how many URL remain in our list of urls (self.imageurls)
            if len(self.imageurls)<500:  # If we have less than 500 urls, make another query on Yahoo.
                wordToSearch = ""
                if self.CONFIG['collector.keywords.enabled']:
                    wordToSearch = self.CONFIG['collector.keywords.keywords']
                else:
                    wordToSearch = self._generateRandomWord()
                self._logDebug("Querying '%s'"%wordToSearch)
                self._setCurrentStatus('Querying',wordToSearch)
                # We also get a random result page (between 0-50)
                try:
                    request_url = "http://images.search.yahoo.com/search/images?p=%s&b=%s" % (urllib.parse.quote_plus(wordToSearch), random.randint(0,50)*20+1)
                    request_headers = { 'User-Agent': self.CONFIG["network.http.useragent"] }
                    request = urllib.request.Request(request_url, None, request_headers)  # Build the HTTP request
                    htmlpage = urllib.request.urlopen(request).read(500000)
                except:
                    self._logWarning("Unable to contact images.search.yahoo.com. Waiting 60 seconds.")
                    self._setCurrentStatus('Error','Unable to contact images.search.yahoo.com. Waiting 60 seconds.')
                    self.waituntil = time.time()+60
                    return
                results = collector_yahooimagesearch.RE_IMAGEURL.findall(htmlpage)
                if len(results) > 0:
                    for imageurl in results:
                        # Keep some of those URLs in memory.
                        # (and put the URLs in a dictionnary to remove duplicates)
                        if random.randint(0,1)==1:
                            imageurl = urllib.parse.unquote_plus(imageurl)
                            if not imageurl.startswith("http://"):
                                imageurl = "http://"+imageurl
                            self.imageurls[imageurl] = 0
                else:
                    htmlpage = htmlpage.replace("&nbsp;"," ")
                    if "We did not find results for" in htmlpage:
                        self._logDebug("No results for this word.") # Our search was unsuccessfull.  Nevermind... we'll try another one later.
                        self._setCurrentStatus('Result','No results for this word.')
                    elif "Unfortunately, we are unable to process your request" in htmlpage:
                        self._logWarning("Search engine overloaded ; Waiting 60 seconds.")
                        self._setCurrentStatus('Waiting','Search engine overloaded ; Waiting 60 seconds.')
                        self.waituntil = time.time()+60
                    elif "may contain adult-oriented content" in htmlpage:
                        self._logDebug("Yahoo thinks this may be pr0n. Skipping.")
                        self._setCurrentStatus('Bad result','Yahoo thinks this may be pr0n. Skipping.')
                    else:
                        self._logWarning("Found no image URL in this page. Website changed ?")
                        self._setCurrentStatus('Error','Found no image URL in this page. Website changed ?')
                        if self.CONFIG["debug"]:
                            filename = "debug_yahooimagesearch_%s.html"%hashlib.sha1(htmlpage).hexdigest()
                            self._logDebug("(See corresponding HTML page saved in %s)" % filename)
                            open(filename,"w+b").write(htmlpage) # Write bogus html page to debug
                        self.stopcollecting()
            return

        # Then choose a random image to download.
        if not self.collectURL:
            self.collectURL = not self.collectURL
            if len(self.imageurls)>0:
                imageurl = random.choice(list(self.imageurls.keys()))  # Choose a random image URL.
                del self.imageurls[imageurl]  # Remove it from list
                self._setCurrentStatus('Downloading',imageurl)
                self._logDebug(imageurl)
                i = internetImage(imageurl,self.CONFIG)   # Download the image
                if i.isNotAnImage:
                    self._logDebug("Image discarded because %s." % i.discardReason)
                else:  # We do not make other checks on the image. We always consider the image is OK.
                    i.saveToDisk(self.CONFIG["pool.imagepooldirectory"])
                    self.numberOfImagesToGet -= 1   # One less !
            return
