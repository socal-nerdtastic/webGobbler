#!/usr/bin/python3

import os
import stat
import threading
import queue
import urllib.request, urllib.parse, urllib.error
import re
import time
import hashlib
import random
import glob
import logging

from PIL import ImageFile

class commandToken:
    ''' Command tokens used to send commands to threads. '''
    def __init__(self, shutdown=None, stopcollecting=None, collect=None, collectnonstop=None,superpose=None):
        self.shutdown = shutdown                # Collector and pool: Order to shutdown. The thread should stop working and quit (exit the run() method.)
        self.collect = collect                  # Collector: Collect n images and stop. (value = the number of images to collect)
        self.collectnonstop = collectnonstop    # Collector: Collect images continuously
        self.stopcollecting = stopcollecting    # Collector: The treads should stop collecting images, but not shutdown.
        self.superpose = superpose              # Assembler_superpose: Superpose images now.

class internetImage:
    ''' An image from the internet.
        Will download the image from the internet and assign a unique name to the image.
        Maximum image size: 2 Mb.  (Download will abort if file is bigger than 2 Mb.)
        Used by: collectors.
     Example:  i = internetImage("http://www.foo.bar/images/foo.jpg",applicationConfig())
               if i.isNotAnImage:
                   print "Image discarded because "+i.discardReason
               else:
                   i.saveToDisk("c:\\my pictures")  # Save the image to disk.
                   i.getImage()    # Get the PIL Image object.
    '''
    def __init__(self,imageurl,config):
        ''' imageurl (string): url of the image to download.
            config (applicationConfig object) : the program configuration
        '''
        self.imageurl = imageurl  # URL of this image on the internet
        self.imagedata = None     # Raw binary image data (as downloaded from the internet)
        self.filename = None      # Image filename (computed from self.imagedata)
        self.isNotAnImage = True  # True if this URL is not an image.
        self.discardReason = ""   # Reason why
        self.CONFIG=config

        # If the URL of the image matches any of the blacklisted URLs, we discard the image.
        for regexp in self.CONFIG["blacklist.url_re"]:
            if regexp.match(imageurl):  # FIXME : protect against maximum recursion limited exceeded exception ?
                self.discardReason = "URL is blacklisted"
                return  # Discard the image.

        #FIXME: Handle passwords required on some pages (Have to use fancy_url opener or urllib2 ?)
        #       (Those URLs have to be skipped)

        # Build and send the HTTP request:
        request_headers = { 'User-Agent': self.CONFIG["network.http.useragent"] }
        request = urllib.request.Request(imageurl, None, request_headers)  # Build the HTTP request
        try:
            urlfile = urllib.request.urlopen(request)
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                self.discardReason = "not found"  # Display a simplified message for HTTP Error 404.
            else:
                self.discardReason = "HTTP request failed with error %d (%s)" % (exc.code, exc.msg)
            return    # Discard this image.
            # FIXME: display simplified error message for some other HTTP error codes ?
        except urllib.error.URLError as exc:
            self.discardReason = exc.reason
            return    # Discard this image.
        except Exception as exc:
            self.discardReason = exc
            return    # Discard this image.
        #FIXME: catch HTTPError to catch Authentication requests ? (see urllib2 manual)
        # (URLs requesting authentication should be discarded.)

        # If the returned Content-Type is not recognized, ignore the file.
        # ("image/jpeg", "image/gif", etc.)
        MIME_Type = urlfile.info().get_content_type()
        if MIME_Type not in self.CONFIG["collector.acceptedmimetypes"]:
            urlfile.close()
            self.discardReason = "not an image (%s)" % MIME_Type
            return

        # Get the file extension corresponding to this MIME type
        # (eg. "imag/jpeg" --> ".jpg")
        file_extension = self.CONFIG["collector.acceptedmimetypes"][MIME_Type]

        # Check image size announced in HTTP response header.
        # (so that we can abort the download right now if the file is too big.)
        file_size = 0
        try:
            file_size = urlfile.length
        except AttributeError: # Content-Length does not contains an integer
            urlfile.close()
            self.discardReason = "bogus data in Content-Length HTTP headers"
            return  # Discard this image.
        # Note that Content-Length header can be missing. That's not a problem.
        if file_size is None:
            urlfile.close()
            self.discardReason = "no size"
            return  # no size defined !  Discard it.
        elif file_size > self.CONFIG["collector.maximumimagesize"]:
            urlfile.close()
            self.discardReason = "too big"
            return  # Image too big !  Discard it.

        # Then download the image:
        try:
            self.imagedata = urlfile.read(self.CONFIG["collector.maximumimagesize"]) # Max image size: 2 Mb
        except:
            self.discardReason = "error while downloading image"
            urlfile.close()
            pass  # Discard image if there was a problem downloading it.
        urlfile.close()

        # Check image size (can be necessary if Content-Length was not returned in HTTP headers.)
        try:
            if len(self.imagedata) >= self.CONFIG["collector.maximumimagesize"]:  # Too big, probably not an image.
                self.discardReason = "too big"
                return    # Discard the image.
        except TypeError:  # Happens sometimes on len(self.imagedata):  "TypeError: len() of unsized object"
            self.imagedata = "no data"
            return    # Discard the image.

        # Make sure image is not blacklisted.
        datahash = hashlib.sha1(self.imagedata).hexdigest()
        if datahash in self.CONFIG["blacklist.imagesha1"]:
            self.imagedata = "blacklisted"
            return   # Discard the image.

        # Compute filename from file SHA1
        imagesha1 = hashlib.sha1(self.imagedata).hexdigest()
        if imagesha1 in self.CONFIG["blacklist.imagesha1"]:  # discard blacklisted images
            self.discardReason = "blacklisted"
            return
        self.filename = 'WG'+imagesha1+file_extension  # SHA1 in hex + image extension
        self.imagedata += self.CONFIG["pool.sourcemark"].encode() + self.imageurl.encode()   # Add original URL in image file

        self.discardReason = ""
        self.isNotAnImage = False  # The image is ok.

    def getImage(self):
        ''' Returns the image as a PIL Image object.
            Usefull for collectors to read image properties (size, etc.)
            Output: a PIL Image object.   None if the image cannot be understood.
        '''
        if self.isNotAnImage:
            return None
        imageparser = ImageFile.Parser()  # from the PIL module
        image = None
        try:
            imageparser.feed(self.imagedata)
            image = imageparser.close()   # Get the Image object.
            return image
        except IOError:  # PIL cannot understand file content.
            self.isNotAnImage = True
            return None

    def saveToDisk(self, destinationDirectory='imagepool'):
        ''' Save the image to disk.
            Filename will be automatically computed from file content (SHA1).
            This eliminates duplicates in the destination directory.
            Input: destinationDirectory (string): The destination directory.
                   Do not specify a filename (Filename is automatically computed).
        '''
        if self.isNotAnImage:
            raise RuntimeError("This is not an image. Cannot save.")
            # Shame shame, the caller should have discarded this image already !
        # FIXME: Should I implement try/except on the following file write operation ?
        try:
            file = open(os.path.join(destinationDirectory,self.filename),'w+b')
            file.write(self.imagedata)
            file.close()
        except IOError:
            pass  # Ignore this image... nevermind.

class collector(threading.Thread):
    ''' Generic collector class. Implements methods common to all collectors.
        (This class implements all the thread logic and message handling.)
        Must be derived.
        Derived classes must implement:
           self.name in the constructor  (String, name of the collector (eg."self.name=collector_deviantart"))
           method self._getRandomImage(self)  (downloads a random image.)
            _getRandomImage() will be called continuously. _getRandomImage() should terminate fast
            (ideally get only one picture)
        Used by: imagePool
    '''
    name="collector"
    def __init__(self,config,dictionnaryFile=None):
        ''' Download random images
              config (an applicationConfig object) : the program configuration
              dictionnaryFile (string): A filename+path to an optionnal word dictionnary.
        '''
        threading.Thread.__init__(self)
        self.inputCommandQueue = queue.Queue()   # Input commands (commandToken objects)
        self.numberOfImagesToGet = 0     # By default, do not start to collect images.
        self.continuousCollect = False
        self.dictionnaryFile = dictionnaryFile  # Optional word dictionnary
        self.CONFIG=config
        self.statusLock = threading.RLock()  # A lock to access collector status.
        self.status = ('Stopped','')    # Status of this collector

    def _logDebug    (self,message): logging.getLogger(self.name).debug    (message)
    def _logInfo     (self,message): logging.getLogger(self.name).info     (message)
    def _logWarning  (self,message): logging.getLogger(self.name).warning  (message)
    def _logError    (self,message): logging.getLogger(self.name).error    (message)
    def _logCritical (self,message): logging.getLogger(self.name).critical (message)
    def _logException(self,message): logging.getLogger(self.name).exception(message)

    # Thread activity methods:
    def collectAndStop(self,n):
        ''' Ask this collector to collect n images and stop. '''
        self.inputCommandQueue.put(commandToken(collect=n),True)

    def collectNonStop(self):
        ''' Ask this collector to collect images and never stop. '''
        self.inputCommandQueue.put(commandToken(collectnonstop=1),True)

    def stopcollecting(self):
        ''' Ask the thread to stop collecting images ASAP (this may not be right now). '''
        self.inputCommandQueue.put(commandToken(stopcollecting=1),True)

    # Thread life methods:
    def shutdown(self):
        ''' Ask this thread to die. '''
        self.inputCommandQueue.put(commandToken(shutdown=1),True)

    def run(self):
        ''' Main thread loop. '''
        while True:
            try:
                commandToken = self.inputCommandQueue.get_nowait()  # Get orders
                # Handle commands put in the command queue:
                if commandToken.shutdown:
                    self._logDebug("Shutting down.")
                    self._setCurrentStatus('Shutting down','')
                    return # Exit the tread.
                elif commandToken.collect:  # Order to collect n images
                    if self.numberOfImagesToGet==0:
                        self._logDebug("Starting to collect %d images..."%commandToken.collect)
                    self.numberOfImagesToGet = commandToken.collect
                    self.continuousCollect = False
                elif commandToken.collectnonstop:  # Order to collect continuously
                    if not self.continuousCollect:
                        self._logDebug("Starting to collect images non-stop...")
                    self.continuousCollect = True
                    self.numberOfImagesToGet = 0
                elif commandToken.stopcollecting:  # Stop collecting images
                    if (self.numberOfImagesToGet>1) or self.continuousCollect:
                        self._logDebug("Stopped")
                        self._setCurrentStatus('Stopped','')
                    self.numberOfImagesToGet = 0
                    self.continuousCollect = False
                else:
                    self._logError("Unknown command token")
                    pass  # Unknown command, ignore.
            except queue.Empty: # Else (if no command is available), do some stuff.
                try:
                    if self.continuousCollect: # collect continuously
                        self.numberOfImagesToGet = 1
                        self._getRandomImage()  # This call must decrement self.numberOfImagesToGet
                        time.sleep(0.25)
                    elif self.numberOfImagesToGet > 0:
                        self._getRandomImage()  # This call must decrement self.numberOfImagesToGet
                        time.sleep(0.25)
                    else:
                        time.sleep(0.25)
                except Exception as exc:
                    self._logException(exc)  # Log any unexpected exception

    def _setCurrentStatus(self,status,information):
        ''' Sets the current status so that it can be read by others. '''
        #
        self.statusLock.acquire()
        self.status = (status,information)
        self.statusLock.release()

    def getCurrentStatus(self):
        ''' Returns the current status of the collector.
            Output: a tuple (status, information)
            status (string): 'Querying','Downloading','Stopped','Waiting','Error'
                             or other string specific to a collector.
                             (Note that collector may use different status.)
            information (string): 'abc','http://...','60 seconds' (information complementary to status.)
        '''
        self.statusLock.acquire()
        status,information = self.status
        self.statusLock.release()
        return (status,information)

    def _getRandomImage(self):
        ''' Each derived class must implement this method.
            The method:
              - may perform several requests on the internet (but ideally only one)
              - should download at least one image (but has the right to fail)
              - should return as soon as possible (short execution time, ideally 1 second
                but can be much more )
              - must decrement self.numberOfImagesToGet by 1 if successfully downloaded an image
                (and considers the image is to be kept.)
            This method will be automatically called again 0.25 seconds after completion,
            continuously (except when the pool decides there are enough images.)
        '''
        self._logError("collector._getRandomImage() is not implemented.")
        raise NotImplementedError("collector._getRandomImage()")

    def _generateRandomWord(self):
        ''' Generates a random word.
            This method can be used by all derived classes.
            Usefull to get random result from search engines when you do not have
            a dictionnary at hand.
            The generated word can be a number (containing only digits),
            a word (containing only letters) or both mixed.
            Output: string (a random word)

            Example: word = self._generateRandomWord()
        '''
        # FIXME: To implement
        #if self.dictionnaryFile:
        #     ...get word from dictionnary...
        #else:
        #     ...the old standalone method below...
        word = '1'
        if random.randint(0,100)<30: # Sometimes use only digits
            if random.randint(0,100)<30:
                word = str(random.randint(1,999))
            else:
                word = str(random.randint(1,999999))
        else:  # Generate a word containing letters
            word = ''
            charset = 'abcdefghijklmnopqrstuvwxyz' # Search for random word containing letter only.
            if random.randint(0,100)<60: # Sometimes include digits with letters
                charset = 'abcdefghijklmnopqrstuvwxyz'*2 + '0123456789'  # *2 to have more letters than digits
            for i in range(random.randint(2,5)): # Only generate short words (2 to 5 characters)
              word += random.choice(charset)
        return word

    def _parsePage(self,url,regex=None):
      ''' Download a specified HTML page and optionnally runs a regular expression on it.
          Input: url (string) : The URL of the page to download.
                 regex : Compiled regular expression (obtained with re.compile)
                         If regex is None, the page will be returned as is.
          Output: A tuple (htmlpage,results)
                  htmlpage is the raw HTML response page. (None in case of error)
                  results is an array containing the regular expression results (as returned by re.findall()) or None
          Examples:
              # Just return the page:
              (htmlpage,results) = parsePage('http://google.com')  # Just return the page.
              # Get cats image URLs:
              (htmlpage,results) = parsePage('http://images.google.com/images?q=cats&hl=en',re.compile('imgurl=(http://.+?)&',re.DOTALL|re.IGNORECASE))
              if (!htmlpage): print "Error getting page"
              if (!results): print "No results."
      '''
      htmlpage = ''
      results = []
      try:
          request_headers = { 'User-Agent': self.CONFIG["network.http.useragent"] }
          request = urllib.request.Request(url, None, request_headers)  # Build the HTTP request
          htmlpage = urllib.request.urlopen(request).read(2000000)  # Read at most 2 Mb.
          htmlpage = htmlpage.decode('latin-1')
          # FIXME: catch specific HTTP errors ?
          # FIXME: return HTTP errors ?
      except Exception as exc:
          self._logError('parsePage("'+url+'"): '+repr(exc))
          return (None,None)
      if regex:
          results = regex.findall(htmlpage)
      return (htmlpage, results)

class collector_local(collector):
    ''' This collector does not use the internet and only searches local harddisks
        to find images.
        Used by: imagePool.
    '''

    def __init__(self,**keywords):
        '''
         Parameters:
            config (applicationConfig object) : the program configuration
        '''
        collector.__init__(self,**keywords)   # Call the mother class constructor.
        self.directoryToScan = self.CONFIG["collector.localonly.startdir"]
        self.name="collector_local"
        self.remainingDirectories = [self.directoryToScan]  # Directories to scan
        self.filepaths = {}  # Paths to images

    def _getRandomImage(self):
        if len(self.filepaths) < 2000:  # Stop scanning directories if we have more than 2000 images filenames
            for i in range(5): # Read 5 directories
                if len(self.remainingDirectories)>0:
                    directory = random.choice(self.remainingDirectories) # Get a directory to scan
                    self.remainingDirectories.remove(directory)
                    self._logDebug("Reading directory %s" % directory)
                    self._setCurrentStatus('Reading directory',directory)
                    # Scan the directory:
                    files = []
                    try:
                        files = os.listdir(directory)
                    except:
                        pass   # I probably do not have access rights to this directory. Skip it silentely.
                    for filename in files:
                        filepath = os.path.join(directory,filename)
                        # FIXME: I should try/except isdir() and isfile() in case the directory/file
                        # was removed (or I do not have access rights)
                        if os.path.isdir(filepath):
                            # Avoid /mnt /proc and /dev
                            pathsToAvoid = ('/mnt/','/proc/','/dev/') # Paths to avoid under *nixes systems.
                            if not (filepath.startswith('/mnt/') or filepath.startswith('/proc/') or filepath.startswith('/dev/')):
                               self.remainingDirectories += [filepath] # This is a new directory to scan
                        elif os.path.isfile(filepath):
                            (name,extension) = os.path.splitext(filename)
                            if extension.lower() in ('.jpg','.jpeg','.jpe','.png','.gif','.bmp','.tif','.tiff','.pcx','.ppm','tga'):
                                self.filepaths[filepath] = 0  # Keep file path
            # If there are no more directories to scan, restart all over:
            if len(self.remainingDirectories) == 0:
                self.remainingDirectories = [self.directoryToScan]


        # Now choose a random image from scanned directories and copy it to the pool directory
        if len(self.filepaths) > 0:
            filepath = random.choice(list(self.filepaths.keys())) # Choose a random file path
            del self.filepaths[filepath]  # Remove it from the list
            self._logDebug("Getting %s" % filepath)
            self._setCurrentStatus('Copying file',filepath)
            try:   #... and copy the image to the pool directory
                file = open(filepath,'rb')
                imagedata = file.read(2000000) # Max 2 Mb for local images
                file.close()
            except:
                imagedata = ''  # Discard image if there was a problem reading the file.

            if (len(imagedata)>0) and (len(imagedata) < 2000000):
                # Compute filename from file SHA1
                imagesha1 = hashlib.sha1(imagedata).hexdigest()
                if imagesha1 not in self.CONFIG["blacklist.imagesha1"]:
                    extension = filepath[filepath.rfind("."):].lower()  # Get file extension
                    outputfilename = 'WG'+imagesha1+extension   # SHA1 in hex + original image extension
                    imagedata += self.CONFIG["pool.sourcemark"] + filepath   # Add original URL in image file
                    # and save the image to disk.
                    # FIXME: try/except file creation:
                    file = open(os.path.join(self.CONFIG["pool.imagepooldirectory"],outputfilename),"w+b")
                    file.write(imagedata)
                    file.close()
                    time.sleep(0.25) #Be gentle with other threads

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

class collector_googleimages(collector):
    ''' Get images from random queries on Google Image search.
        http://images.google.com/
        Used by: imagePool
    '''
    RE_IMAGEURL = re.compile('imgurl=(http://.+?)&',re.DOTALL|re.IGNORECASE)
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


class collector_flickr(collector):
    ''' Get images from flickr.com.
        http://flickr.com
        Used by: imagePool
    '''

    # Regexp to get all images (eg. "http://static.flickr.com/36/94902996_d58bec5e04_t.jpg") from http://flickr.com/photos/?start=x
    #                                http://farm9.staticflickr.com/8540/8631778383_0724517a90_t.jpg
    RE_FLICKR_IMAGEURL = re.compile(r'src="(http://farm\d+.staticflickr.com.+?_t\.jpg)" width',re.DOTALL|re.IGNORECASE)
    RE_GOOGLEIMAGES_IMAGEURL = re.compile(r'imgurl=(http://.+?)&',re.DOTALL|re.IGNORECASE)
    #RE_IMAGEURL = re.compile('<img src="(http://www.randomimage.us/files/.+?)"',re.DOTALL|re.IGNORECASE)
    def __init__(self,**keywords):
        collector.__init__(self,**keywords)
        self.name="collector_flickr"
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

class imagePool(threading.Thread):
    ''' This object is in charge of maintaining a pool of images downloaded from the internet.
        If the pool is going low, it will ask the collectors do to download some more random images.
        Used by: assemblers and other programs.
    '''
    def __init__(self,config):
        ''' config (applicationConfig object) : the program configuration '''
        threading.Thread.__init__(self)
        self.inputCommandQueue = queue.Queue()       # Input commands (commandToken objects)
        self.outputImages = queue.Queue()            # Output images taken from the pool (PIL.Image objects)
        self.collectors = []                         # List of collector objects which download images from the internet (collector object descendants)
        self.delayBetweenChecks = 5                  # Seconds between image pool directory content check
        self.availableFiles = []                     # List of currently available images in the directory
        self.lastCheckTime = 0                       # Datetime of last directory check.
        self.CONFIG = config
        self._log = logging.getLogger('imagepool')
        # If directory does not exist, create it.
        if not os.path.isdir(self.CONFIG["pool.imagepooldirectory"]):
            os.makedirs(self.CONFIG["pool.imagepooldirectory"])
        if not os.path.isdir(self.CONFIG["pool.imagepooldirectory"]):
            self._log.error("Could not create directory "+ os.path.abspath(self.CONFIG["pool.imagepooldirectory"]))
            raise IOError("Could not create directory "+ os.path.abspath(self.CONFIG["pool.imagepooldirectory"]))
        self._log.debug("Using images in %s" % os.path.abspath(self.CONFIG["pool.imagepooldirectory"]))
        # Instanciate all collectors
        if self.CONFIG["collector.localonly"]:
            self.collectors.append( collector_local(config=self.CONFIG) )
        else:
            self.collectors.append( collector_googleimages    (config=self.CONFIG) )
            self.collectors.append( collector_yahooimagesearch(config=self.CONFIG) )  # £££ FIXM%E: on test pour le moment un seul collecteur.
            self.collectors.append( collector_flickr          (config=self.CONFIG) )
            self.collectors.append( collector_deviantart      (config=self.CONFIG) )

    def run(self):
        # Start all collectors
        for collector in self.collectors:
            collector.start()           # Start all collector threads.
        time.sleep(0.5)   # Give them time to start.
        while True:
            try:
                commandToken = self.inputCommandQueue.get_nowait()  # Get orders
                if commandToken.shutdown:
                    self._log.debug("Shutting down")
                    for collector in self.collectors:  # Ask all collectors to stop
                        collector.shutdown()
                    for collector in self.collectors:  # and wait for them to stop.
                        collector.join()
                    return # Exit the tread.
                else:
                    self._log.error("Unknown command token")
                    pass  # Unknown command, ignore.
            except queue.Empty:
                # Ensure there are always enough images in the directory.
                # and start/stop the collector is there are not enough/enough pictures in the directory.
                elapsed = time.time()-self.lastCheckTime  # Count time since last check.
                if (elapsed > self.delayBetweenChecks) or (elapsed<0):
                    # Check the directory
                    self.availableFiles = self._getFileList()
                    if len(self.availableFiles) < self.CONFIG["pool.nbimages"]:  # We do not have enough images
                        for collector in self.collectors:
                            collector.collectNonStop()
                    else:  # we have enough images: stop collecting.
                        for collector in self.collectors:
                            collector.stopcollecting()
                    self.lastCheckTime = time.time()
                    time.sleep(0.25)
                # Then ensure there is always one image in the output queue
                # available to assemblers.
                if (self.outputImages.qsize()<1) and (len(self.availableFiles)>0):
                    # Get a random filename from the list of available images.
                    filename = random.choice(self.availableFiles) # Choose a random file in the list
                    #(we do not need to remove the file from the self.availableFiles list, because the file will be
                    # deleted and will diseappear from the list at the next refresh of self.availableFiles)
                    imagedata = None
                    try: # Read image file.
                        file = open(filename,'rb')
                        imagedata = file.read(self.CONFIG["collector.maximumimagesize"])
                        file.close()
                    except IOError:
                        pass
                    if imagedata != None:
                        if not self.CONFIG["pool.keepimages"]:
                            try:
                                os.remove(filename)  # Delete the file we've just successfully read.
                            except OSError:
                                pass
                        imageparser = ImageFile.Parser()
                        image = None
                        try:  # Try to decode file content.
                            imageparser.feed(imagedata)
                            image = imageparser.close()   # Get the Image object.
                        except: # PIL cannot understand file content.
                            pass # self._log.info("Bad image. Dropping file.")  # Oops !  Bad image. Ignore it.
                        imageurl = "<url unknown>"
                        try: # Extract image URL from file (written at end)
                            partial_data = imagedata[-1024:]  # Get the 1024 last bytes of file
                            commentoffset = partial_data.rfind(self.CONFIG["pool.sourcemark"])
                            if commentoffset < 0:
                                imageurl = '<url unknown>'
                            else:
                                imageurl = partial_data[commentoffset+len(self.CONFIG["pool.sourcemark"]):]
                        except:
                            imageurl = "<url unknown>"
                        # Now, log in HTML format.
                        localfilename = os.path.split(filename)[1]
                        self._logImageUrl('<code>%s:&nbsp;<a href="%s">%s</a></code><br>' % (localfilename,imageurl,imageurl))
                        self.outputImages.put(image,True)  # Put the image in the output queue
                time.sleep(0.25)

    def _getFileList(self):
        ''' Returns the list of image files present in the imagepool directory.
        '''
        filelist = []
        for extension in ('jpg','jpeg','jpe','png','gif','bmp','tif','tiff','pcx','ppm','tga'):
            filelist += glob.glob(os.path.join(self.CONFIG["pool.imagepooldirectory"],"*."+extension))
        #FIXME: Maybe I could do a better job here by using a single listdir() and use fnmatch()
        return filelist

    def shutdown(self):
        ''' Ask this thread to die. '''
        self.inputCommandQueue.put(commandToken(shutdown=1),True)

    def getImage(self):
        ''' Returns an image from the pool.
            This is a non-blocking method.
            Will return None if no image is available at this time.
            If no image is available, caller should call this method again
            a few time later (It will probably have images available.)
        '''
        image = None
        try:
            image = self.outputImages.get_nowait()
        except queue.Empty:
            pass
        return image

    def getImageB(self):
        ''' Returns an image from the pool.
            This is blocking and will block until an image is available.
            (The duration may be several seconds.)
        '''
        image = None
        while (image==None):
            try:
                image = self.outputImages.get_nowait()
            except queue.Empty:
                pass
            time.sleep(0.25)
        return image

    def getPoolSize(self):
        ''' Returns the number of images in the pool. '''
        return len(self.availableFiles)

    def _logImageUrl(self, text):
        ''' Record the URL of the last given image.
            text will be added to the log file (last_used_images.html in the image pool directory).
            If the log file exceeds 1 Mb, it will be truncated to 800 kb.
            The most recent lines always appear at the end of file.
            The users will be able to see the last used images URLs at the bottom of this file.
            Note that ideally, 'text' should contain only HTML, and a single line of text (no CR/LF)
        '''
        # FIXME: try/except all IO operations here ?
        filename = os.path.join(self.CONFIG["pool.imagepooldirectory"],"last_used_images.html")
        file = open(filename,"a+")
        file.write(text+"\n")
        file.close()
        if os.stat(filename)[stat.ST_SIZE] > 1000000: # If file is bigger than 1 Mb, truncate to 800 kb
            self._log.info("Truncating log file to 800 kb.")
            file = open(filename,"rb")
            data = file.read()
            file.close()
            data = data[-800000:] # Keep the last 800 kilobytes
            data = "\n".join(data.split("\n")[2:])  # Remove the first lines (which is probably cut)
            file = open(filename,"w+b")
            file.write(data)
            file.close()
