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

class collector_deviantart(collector):
    ''' This collector gets random images from http://deviantART.com, an excellent
        collaborative art website. Anyone can post its creations, and visitors
        can comment. Site contains photography, drawings, paintings,
        computer-generated images, etc.
        Used by: imagePool.
    '''
    # Regular expression used to extract the image URL from a random deviant Art page.
    RE_IMAGEURL = re.compile(r'<meta name="og:image" content="(.+?\.(jpg|png|gif))">',re.DOTALL|re.IGNORECASE)

    # Regular expression to extract the maximum deviantionID from homepage
    RE_ALLDEVIATIONID = re.compile(r'href="http://www.deviantart.com/morelikethis/(\d+)"',re.DOTALL|re.IGNORECASE)

    def __init__(self,**keywords):
        collector.__init__(self,**keywords)   # Call the mother class constructor.
        self.name="collector_deviantart"
        self.max_deviationid = -1  # We do not know yet what if the maximum deviationID
        self.deviationIDs = []     # List of deviantionIDs (DeviantArt picture identifier). Used only for keyword search.
        self.imageurltoget = ""    # URL of image to get.
        self.waituntil = 0         # Wait until this date.

    def _getRandomImage(self):
        if time.time()<self.waituntil:
            return
        if self.max_deviationid < 0: # If we do not know the maximum deviationid:
            # Get the maximum deviationID from the Homepage:
            self._logDebug("Getting maximum deviationID from homepage.")
            self._setCurrentStatus('Querying','Maximum deviationID from homepage')
            request_url = "http://browse.deviantart.com/?order=5"
            (htmlpage,results) = self._parsePage(request_url,collector_deviantart.RE_ALLDEVIATIONID)
            if not htmlpage:  # Error while getting page.
                self._logWarning("Unable to contact deviantArt.com. Waiting 60 seconds.")
                self._setCurrentStatus('Error','Unable to contact deviantArt.com. Waiting 60 seconds.')
                self.waituntil = time.time()+60
            elif not results:  # Regex returned no result in page.
                # If no deviationID was found in homepage, display an error message and stop collecting.
                self._logWarning("Could not find any deviationID from homepage. Website changed ?")
                self._setCurrentStatus('Error','Could not find any deviationID from homepage. Website changed ?')
                if self.CONFIG["debug"]:
                    filename = "debug_deviantart_%s.html"%hashlib.sha1(htmlpage).hexdigest()
                    self._logDebug("(See corresponding HTML page saved in %s)" % filename)
                    open(filename,"w+b").write(htmlpage) # Write bogus html page to debug
                self.stopcollecting()
                return
            # Get the maximum deviationID:
            for result in results:
                try:
                    self.max_deviationid = max(self.max_deviationid,int(result))
                except ValueError:  # could not convert to int
                    pass  # ignore value
            if self.max_deviationid > 0:
                self._logDebug("Max deviationid = %d"%self.max_deviationid)
            return

        if len(self.imageurltoget)==0: # If we do not have the URL of an image, get a random DeviantArt page.
            deviationid = 0
            if self.CONFIG['collector.keywords.enabled']:
                # If we do not have enough deviations corresponding to the search word,
                # let's run a search on deviantArt search engine:
                if len(self.deviationIDs)<40:
                    # If keyword search is enabled, we use the search engine of DeviantArt
                    # to get a list of deviationID (images).
                    wordToSearch = self.CONFIG['collector.keywords.keywords']
                    self._logDebug("Querying %s" % wordToSearch)
                    self._setCurrentStatus('Querying',wordToSearch)
                    # Get the search result page:
                    request_url = "http://browse.deviantart.com/?order=5&q=%s&offset=%d" % (urllib.parse.quote_plus(wordToSearch),random.randint(0,300)*24)
                    (htmlpage,results) = self._parsePage(request_url,collector_deviantart.RE_ALLDEVIATIONID)
                    if not htmlpage:
                        self._logInfo("Unable to contact DeviantART.com. Waiting 60 seconds.") # Nevermind temporary failures
                        self._setCurrentStatus('Error','Unable to contact DeviantART.com. Waiting 60 seconds.')
                        self.waituntil = time.time()+60
                        return
                    if not results:
                        self._logWarning("Could not find any deviationID from homepage. Website changed ?")
                        self._setCurrentStatus('Error','Could not find any deviationID from homepage. Website changed ?')
                        if self.CONFIG["debug"]:
                            filename = "debug_deviantart_%s.html"%hashlib.sha1(htmlpage).hexdigest()
                            self._logDebug("(See corresponding HTML page saved in %s)" % filename)
                            open(filename,"w+b").write(htmlpage) # Write bogus html page to debug
                        self.stopcollecting()
                        return
                    else:
                        # Search for devationIDs in the result page.
                        for result in results:
                            try:
                                deviationid = int(result)
                                if random.randint(0,2)<2:  # We keep some of these images.
                                    self.deviationIDs.append(deviationid)
                            except ValueError:  # could not convert to int
                                pass  # ignore value

                # Pick a random deviationID corresponding to the search word:
                deviationid = random.choice(self.deviationIDs)
                self.deviationIDs.remove(deviationid)
            else:  # Get a random deviation page:
                deviationid = random.randint(1,self.max_deviationid)   # choose a random deviation
            self._logDebug("Getting deviation page %d" % deviationid)
            self._setCurrentStatus('Querying','Deviation page %s' % deviationid)
            request_url = "http://www.deviantart.com/deviation/%d/" % deviationid
            (htmlpage,results) = self._parsePage(request_url,collector_deviantart.RE_IMAGEURL)
            if not htmlpage:
                self._logInfo("Unable to contact DeviantART.com. Waiting 60 seconds.") # Nevermind temporary failures
                self._setCurrentStatus('Error','Unable to contact DeviantART.com. Waiting 60 seconds.')
                self.waituntil = time.time()+60
                return
            if not results:
                if len(htmlpage.strip())==0:
                    self._logInfo("Empty page - skipped.")
                    self._setCurrentStatus('Skipped','Empty page. Skipped.')
                    self.waituntil = time.time()+1
                elif '<iframe class="flashtime"' in htmlpage:
                    self._logInfo("Flash animation - skipped.")
                    self._setCurrentStatus('Skipped','Flash animation. Skipped.')
                    self.waituntil = time.time()+1
                elif "<b>Fatal error</b>:" in htmlpage:  # Temporary deviantart problem.
                    self._logInfo("Temporary error on site. Waiting 60 seconds.")
                    self._setCurrentStatus('Error','Temporary error on site. Waiting 60 seconds.')
                    self.waituntil = time.time()+60
                elif 'Mature Content Filter' in htmlpage:
                    self._logInfo("Mature content - skipped.")
                    self._setCurrentStatus('Skipping','Mature content - skipped.')
                    self.waituntil = time.time()+1
                else:
                    self._logWarning("Found no image URL in this page. Website changed ?")
                    self._setCurrentStatus('Error','Found no image URL in this page. Website changed ?')
                    if self.CONFIG["debug"]:
                        filename = "debug_deviantart_%s.html"%hashlib.sha1(htmlpage).hexdigest()
                        self._logDebug("(See corresponding HTML page saved in %s)" % filename)
                        open(filename,"w+b").write(htmlpage) # Write bogus html page to debug
                        self.stopcollecting()
            else: # Page contains a link to an image
                self.imageurltoget = results[0][0]
        else: # Download an image.
            self._logDebug(self.imageurltoget)
            self._setCurrentStatus('Downloading',self.imageurltoget)
            i = internetImage(self.imageurltoget,self.CONFIG)  # Download the image
            if i.isNotAnImage:
                self._logDebug("Image discarded because %s." % i.discardReason)
            else:  # We do not make other checks on the image. We always consider the image is OK.
                i.saveToDisk(self.CONFIG["pool.imagepooldirectory"])
                self.numberOfImagesToGet -= 1   # One less !
            self.imageurltoget = ""
            return
