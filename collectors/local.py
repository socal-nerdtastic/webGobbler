#!/usr/bin/python3

import os
import time
import hashlib
import random

try:
    from collectors.meta import collector
except ImportError:
    from meta import collector

class collector_local(collector):
    ''' This collector does not use the internet and only searches local harddisks
        to find images.
        Used by: imagePool.
    '''
    name="collector_local"
    source='Local disk'

    def __init__(self,**keywords):
        '''
         Parameters:
            config (applicationConfig object) : the program configuration
        '''
        collector.__init__(self,**keywords)   # Call the mother class constructor.
        self.directoryToScan = self.CONFIG["collector.localonly.startdir"]
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

