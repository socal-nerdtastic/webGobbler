#!/usr/bin/python3

# FIXME: Assign an icon to the EXE. (Use http://www.angusj.com/resourcehacker/ ?)
# FIXME: Change the default Tk icon, too.

import sys
import os
import stat
import threading
import queue
import socket
import urllib.request, urllib.parse, urllib.error
import time
import random
import glob
import getopt
import getpass
import logging

# Set default timeout for sockets.
# urllib2 and all other libraries will use this timeout.
# We keep this short so that when we ask collectors to shutdown they are
# stuck no more than 15 seconds waiting for network data.
# This should be okay for most websites.
socket.setdefaulttimeout(15)

from utils.freeze_imports import Image, ImageFile, ImageOps,  ImageEnhance,  ImageFilter,  ImageChops,  ImageDraw
from assets.docs import DISCLAIMER, LICENSE, README, PROGRAMHELP, WEBSITE
from assets.images import PLEASE_WAIT_IMAGE, WEBGOBBLER_LOGO, WEBGOBBLER_LOGO_TRANSPARENCY
from settings import VERSION
import settings
from utils.appconfig import applicationConfig
from collectors import get_collectors, commandToken

# == Classes ===================================================================

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
        self.collectors = get_collectors(config) # List of collector objects which download images from the internet (collector object descendants)

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

class assembler(threading.Thread):
    ''' Generic assembler class. Derived classes will assemble several pictures from
        the pool into a single picture.
        Derived classes must implement .saveImageTo()
    '''
    def __init__(self, pool,config):
        ''' pool (imagePool object): the pool where to get images from.
            config (an applicationConfig object) : the program configuration
            Derived classes may have additional parameters.
        '''
        threading.Thread.__init__(self)
        self.inputCommandQueue = queue.Queue()      # Input commands (commandToken objects)
        self.outImageQueue = queue.Queue()          # Queue where created images are put
        self.pool = pool                            # Image pool
        self.name = 'assembler'
        self.CONFIG = config
        self.pool.start()
        self.closing = False  # Indicates if the threads was asked to close.

    def _logDebug    (self,message): logging.getLogger(self.name).debug    (message)
    def _logInfo     (self,message): logging.getLogger(self.name).info     (message)
    def _logWarning  (self,message): logging.getLogger(self.name).warning  (message)
    def _logError    (self,message): logging.getLogger(self.name).error    (message)
    def _logCritical (self,message): logging.getLogger(self.name).critical (message)
    def _logException(self,message): logging.getLogger(self.name).exception(message)

    def run(self):
        while True:
            try:
                commandToken = self.inputCommandQueue.get_nowait()  # Get orders
                if commandToken.shutdown:
                    self._logInfo("Shutting down")
                    self.closing = True
                    self.pool.shutdown()
                    self.pool.join()
                    return # Exit the tread.
                else:
                    self._logError("Unknown command token")
                    pass  # Unknown command, ignore.
            except queue.Empty:
                #self._log("Nothing in queue")
                time.sleep(0.5)

    def shutdown(self):
        ''' Ask this thread to die. '''
        self.inputCommandQueue.put(commandToken(shutdown=1),True)

    def saveImageTo(self,destinationFilename):
        ''' Save the image to the destination filename and path.
            All assemblers must implement this class.
            This call is blocking.
            This call must succeed (caller does not expect image not to be saved.)
        '''
        self._logError("assembler.saveImageTo() is not implemented.")
        raise NotImplementedError("assembler.saveImageTo()")

class assembler_simple(assembler):
    ''' Outputs a single random image at the desired resolution (with filtering)
    Example:
            a = assembler_simple(pool=imagePool(applicationConfig()))
            a.start()
            a.saveImageTo('singleimage.bmp')
    '''
    def __init__(self,**keywords):
        assembler.__init__(self,**keywords)
        self.name="assembler_simple"

    def saveImageTo(self,destinationFilename):
        ''' Generates an image and save to the destination filename.
            destinationFilename (string): file path and name for destination file.
            Supported file formats: png jpg bmp (and those supported by the PIL module)
            This call is blocking.
        '''
        self._logInfo("Generating image and saving to %s" % destinationFilename )
        image = self.pool.getImageB()
        if image.mode != 'RGB':
            image = image.convert('RGB')
        (imagex, imagey) = image.size
        if (imagex != self.CONFIG["assembler.sizex"] or imagey != self.CONFIG["assembler.sizey"]):
            image.thumbnail((self.CONFIG["assembler.sizex"],self.CONFIG["assembler.sizey"]),Image.LANCZOS)
        if self.CONFIG["assembler.mirror"]:
            image = ImageOps.mirror(image)
        if self.CONFIG["assembler.emboss"]:
            finalimage_embossed = image.filter(ImageFilter.EMBOSS).filter(ImageFilter.SMOOTH)  # Emboss image
            image = ImageOps.equalize( ImageChops.multiply(image, finalimage_embossed) )  # Compose images
            image = Image.blend(image,finalimage_embossed,0.1)
        if self.CONFIG["assembler.invert"]:
            image = ImageOps.invert(image)
        image.save(destinationFilename)
        self._logInfo("Done.")

    #FIXME: Also create an asynchronous, threaded image creation method ?

class assembler_mosaic(assembler):
    ''' Outputs a mosaic of images at the desired resolution (with filtering)

    Example:
            a = assembler_mosaic(pool=imagePool(applicationConfig()),nbX=6,nbY=4)
            a.start()
            a.saveImageTo('mosaic.bmp')
    '''
    def __init__(self,**keywords):
        ''' Additionnal parameters:
            nbX (integer): number of images to stack horizontally.
            nbY (integer): number of images to stack vertically.
        '''
        if 'nbX' in keywords: self.nbX = keywords.pop('nbX')
        else:                 self.nbX = 5
        if 'nbY' in keywords: self.nbY = keywords.pop('nbY')
        else:                 self.nbY = 5
        assembler.__init__(self,**keywords)
        self.name="assembler_mosaic"

    def saveImageTo(self,destinationFilename, resizeMethod=2):
        ''' Generates an image and save to the destination filename.
            destinationFilename (string): file path and name for destination file.
            Supported file formats: png jpg bmp (and those supported by the PIL module)
            This call is blocking.

            sizeMethod (integer): determines how the pictures will be resized/cropped
                                  to fit the thumbnail size.
                                  0 = fit whole picture, keep ratio
                                  1 = fit smaller edge and crop largest, keep ratio
                                  2 = fit, do not keep ratio
        '''
        self._logInfo("Generating image and saving to %s" % destinationFilename )
        finalImage = Image.new('RGB',(self.CONFIG["assembler.sizex"],self.CONFIG["assembler.sizey"]))
        imageSizeX = self.CONFIG["assembler.sizex"] / self.nbX
        imageSizeY = self.CONFIG["assembler.sizex"] / self.nbY
        for y in range(self.nbY):
            for x in range(self.nbX):
                image = self.pool.getImageB()
                if image.mode != 'RGB':
                    image = image.convert('RGB')
                if resizeMethod==1:
                    image = ImageOps.fit(image,size=(imageSizeX,imageSizeY),method=Image.LANCZOS,bleed=0,centering=(0.5,0.5))
                if resizeMethod==2:
                    image = image.resize((imageSizeX,imageSizeY),Image.LANCZOS)
                else:
                    image.thumbnail((imageSizeX,imageSizeY),Image.LANCZOS)
                finalImage.paste(image,(x*imageSizeX,y*imageSizeY))
        if self.CONFIG["assembler.mirror"]:
            finalImage = ImageOps.mirror(finalImage)
        if self.CONFIG["assembler.emboss"]:
            finalimage_embossed = finalImage.filter(ImageFilter.EMBOSS).filter(ImageFilter.SMOOTH)  # Emboss image
            finalImage = ImageOps.equalize( ImageChops.multiply(finalImage, finalimage_embossed) )  # Compose images
        if self.CONFIG["assembler.invert"]:
            finalImage = ImageOps.invert(finalImage)
        finalImage.save(destinationFilename)
        self._logInfo("Done.")

class BadImage(Exception):
    ''' This exception is raised when an image seems broken and can't be processed.
        This exception is used in the assembler_superpose class internally.
    '''
    pass

class assembler_superpose(threading.Thread):
    def __init__(self,pool,config,ignorePreviousImage=False):
        ''' Outputs a superposed mesh of images.
            You should call .superpose() method to make the image evolve,
            then call .saveImageTo() or .getImage() to get the resulting picture.
        Example:
            c = applicationConfig()
            a = assembler_superpose(pool=imagePool(config=c),config=c)
            a.start()
            a.superposeB()                // This call is blocking.
            a.saveImageTo("first.bmp")
            a.superposeB()
            a.saveImageTo("second.bmp")

        Note that you can also use the asynchronous methods:
        Example 2:
            c = applicationConfig()
            a = assembler_superpose(pool=imagePool(config=c),config=c)
            a.start()
            a.superpose()     // This call is non-blocking.
            while True:
                image = a.getImage()  // This call is non-blocking either.
                if a == None:
                    print "No image"
                    time.sleep(10)
                else:
                    print "I got an image !"

        Input:
            pool (imagepool object) : a pool of images (not started)
            config (an applicationConfig object) : the program configuration
            ignorePreviousImage (boolean) : If True, will ignore previous image and start a new from scratch.
        '''
        threading.Thread.__init__(self)
        self.CONFIG = config
        self.pool = pool                        # The image pool.
        self.pool.start()                       # Start the image pool right now.
        self.name = 'assembler_superpose'
        self.inputCommandQueue = queue.Queue()  # Input commands (commandToken objects)
        self.superposeCompleted = queue.Queue() # An object in this Queue means ._superpose() has completed its work.
        self.nbImagesToSuperpose = 0            # Number of images to superpose.
        self.currentImage = None                # Image currently beeing generated.
        self.blankImage = False                 # Should the superpose() blank image before starting ?
        self.finalImage = None                  # Final image (self.currentImage after post-processing.)
        self.finalImageCompletionDate = None    # Date/time when last image was generated.
        self.finalImageLock = threading.RLock() # Lock for concurrent access to self.finalImage
        self._loadPreviousImage(ignorePreviousImage) # Get image from previous run.
        self.state = "Waiting"                  # State of the assemble (textual)

    # Loggin methods:
    def _logDebug    (self,message): logging.getLogger(self.name).debug    (message)
    def _logInfo     (self,message): logging.getLogger(self.name).info     (message)
    def _logWarning  (self,message): logging.getLogger(self.name).warning  (message)
    def _logError    (self,message): logging.getLogger(self.name).error    (message)
    def _logCritical (self,message): logging.getLogger(self.name).critical (message)
    def _logException(self,message): logging.getLogger(self.name).exception(message)

    def run(self):
        ''' The main thread dispatch method. '''
        time.sleep(0.5)  # Give time to other threads (usefull to let the GUI start to display)
        while True:
            try:
                commandToken = self.inputCommandQueue.get_nowait()  # Get orders
                if commandToken.shutdown:   # We are aksed to shutdown.
                    self._logInfo("Shutting down")
                    self.state = "Shutting down"
                    self.pool.shutdown()  # Ask the image pool to shutdown.
                    self.pool.join()      # Wait for the thread to die.
                    return                # Exit our tread.
                elif commandToken.superpose:  # We are asked to assemble n images.
                    if self.nbImagesToSuperpose == 0:  # Ignore the command if we are already assembling images (!=0)
                        self._logInfo("Superposing %d images in current image" % commandToken.superpose)
                        self.nbImagesToSuperpose = commandToken.superpose  # Get the number of images to superpose
                        # Blank the image if needed:
                        if self.blankImage:
                            self.currentImage = Image.new('RGB',(self.CONFIG["assembler.sizex"],self.CONFIG["assembler.sizey"]))
                            self.blankImage = False
                else:
                    self._logError("Unknown command token")
                    pass  # Unknown command, ignore.
            except queue.Empty:
                if self.nbImagesToSuperpose > 0:  # Do we have images to assemble ?
                    self._superpose()  # Let's superpose one image. (This method will decrement self.nbImagesToSuperpose if successfull)
                    if self.nbImagesToSuperpose == 0:  # Are we done assembling images ?
                        # Let's save the current image.
                        self._logInfo("Saving session image and post-processing...")
                        self._saveCurrentImage()

                        # Then post-process the image and give it away.
                        finalImage = self._postProcessImage(self.currentImage)
                        self.finalImageLock.acquire()
                        self.finalImage = finalImage
                        self.finalImageCompletionDate = time.time()
                        self.finalImageLock.release()
                        self._logInfo("Done.")
                        self.superposeCompleted.put("completed",True)
                        self.state = "Waiting"
                else:
                    #self._logInfo("Nothing in queue")
                    time.sleep(0.5)

    def _superpose(self):
        ''' Superpose an image.
            This method must only be called by the assembler_superpose thread !
        '''
        (imagex, imagey) = (0,0)
        # Try to get an image from the pool.
        imageToSuperpose = self.pool.getImage()
        if imageToSuperpose == None:  # no image availabe.
            #self._logError("No image from the pool.");
            time.sleep(0.25)
            return  # It's ok, we'll try next time.

        # If the image is too small, get another image.
        (imagex,imagey) = imageToSuperpose.size
        if (imagex < 32) or (imagey < 32):
            return    # Image is too small. We'll take another one.

        self._logInfo("Superposing image %d" % self.nbImagesToSuperpose)
        self.state = "Superposing image %d of %d" % (self.CONFIG["assembler.superpose.nbimages"]-self.nbImagesToSuperpose+1, self.CONFIG["assembler.superpose.nbimages"])

        # Superpose the image in current image.
        try:
            self.currentImage = self._superposeOneImage(self.currentImage,imageToSuperpose)
            self.nbImagesToSuperpose = self.nbImagesToSuperpose - 1
        except BadImage:
            self._logInfo("Broken image ; Ignoring.")
        except Exception as exc:
            self._logError("Could not assemble image because %s" % str(exc))

    def _superposeOneImage(self, currentImage, imageToSuperpose):
        ''' Superposes one image in the current image.
            This method must only be called by the assembler_superpose thread !
            Intput:
                currentImage (PIL Image object) : the current image
                imageToSupepose (PIL Image object) : the image to superpose in current image.
            Output: a PIL Image object.
        '''
        # Darken slightly the current image:
        if self.CONFIG["assembler.superpose.variante"] == 1:
          currentImage = ImageEnhance.Brightness(currentImage).enhance(0.99)  # Old value (in beta 3): 0.985

        # Force the image to RGB mode:
        if imageToSuperpose.mode != 'RGB':
            try:
                imageToSuperpose = imageToSuperpose.convert('RGB')
            except TypeError:  # "TypeError: unsubscriptable object", what's that ?
                raise BadImage
            except IOError:  # IOError: decoder group4 not available ; Yes another PIL exception ?!
                raise BadImage

        # If the image is bigger than current image, scale it down to 1/2 of final picture dimensions
        # (while keeping its ratio)
        (imagex,imagey) = imageToSuperpose.size
        if (imagex > self.CONFIG["assembler.sizex"]) or (imagey > self.CONFIG["assembler.sizey"]):
            try:
                imageToSuperpose.thumbnail((self.CONFIG["assembler.sizex"]/2,self.CONFIG["assembler.sizey"]/2),Image.LANCZOS)
            except TypeError:  #TypeError: unsubscriptable object  ; Spurious exception in PIL.  :-(
                raise BadImage
            (imagex,imagey) = imageToSuperpose.size

        # Scale down/up image if required.
        scaleValue = self.CONFIG["assembler.superpose.scale"]
        if str(scaleValue) != "1.0":
            try:
                imageToSuperpose.thumbnail((int(float(imagex)*scaleValue),int(float(imagey)*scaleValue)),Image.LANCZOS)
            except TypeError:  #TypeError: unsubscriptable object  ; Spurious exception in PIL.  :-(
                raise BadImage
            (imagex,imagey) = imageToSuperpose.size

        # Compensate for poorly-contrasted images on the web
        try:
            imageToSuperpose = ImageOps.autocontrast(imageToSuperpose)
        except TypeError:  # Aaron tells me that this exception occurs with PNG images.
            raise BadImage

        # Some image are too white.
        # For example, the photo of a coin on a white background.
        # These picture degrad the quality of the final image.
        # We try to dectect them by summing the value of the pixels
        # on the borders.
        # If the image is considered "white", we invert it.
        pixelcount = 1  # 1 to prevent divide by zero error.
        valuecount = 0
        try:
            for x in range(0,imagex,20):
                (r,g,b) = imageToSuperpose.getpixel((x,5))
                valuecount += r+g+b
                (r,g,b) = imageToSuperpose.getpixel((x,imagey-5))
                valuecount += r+g+b
                pixelcount += 2
            for y in range(0,imagey,20):
                (r,g,b) = imageToSuperpose.getpixel((5,y))
                valuecount += r+g+b
                (r,g,b) = imageToSuperpose.getpixel((imagex-5,y))
                valuecount += r+g+b
                pixelcount += 2
        except TypeError:  #unsubscriptable object  Arrggghh... not again !
            raise BadImage   # Aggrrreeeuuuu...

        # If the average r+g+b of the border pixels exceed this value,
        # we consider the image is too white, and we invert it.
        if (100*(valuecount/(255*3))/pixelcount)>60:  # Cut at 60%.  (100% is RGB=(255,255,255))
            imageToSuperpose = ImageOps.invert(imageToSuperpose)

        paste_coords = (random.randint(-imagex,self.CONFIG["assembler.sizex"]),random.randint(-imagey,self.CONFIG["assembler.sizey"]) )

        # Darken image borders
        imageToSuperpose = self._darkenImageBorder(imageToSuperpose,borderSize=self.CONFIG["assembler.superpose.bordersmooth"])

        if self.CONFIG["assembler.superpose.randomrotation"]:
            imageToSuperpose = imageToSuperpose.rotate(random.randint(0,359), Image.BICUBIC)
            # Darken the borders of the rotated image:
            imageToSuperpose = self._darkenImageBorder(imageToSuperpose,borderSize=self.CONFIG["assembler.superpose.bordersmooth"])

        mask_image = ImageOps.autocontrast(imageToSuperpose.convert('L'))

        if (self.CONFIG["assembler.superpose.variante"]==1) and (random.randint(0,100)<5):  # Invert the transparency of 5% of the images (Except if we are in variante 1 mode)
            mask_image = ImageOps.invert(mask_image)
        try:
            currentImage.paste(imageToSuperpose,paste_coords,mask_image)
        except IOError:
            # Sometimes, we get a IOError: "image file is truncated (0 bytes not processed)"
            raise BadImage
        if self.CONFIG["assembler.superpose.variante"] == 0:
            currentImage = ImageOps.equalize(currentImage)
        else:
            currentImage = ImageOps.autocontrast(currentImage)

        return currentImage

    def _postProcessImage(self,image):
        ''' Post-process the image before outputing it.
            This method must only be called by the thread !
            Input: a PIL Image object.
            Output: a PIL Image object.
        '''
        finalimage = image.copy()
        if self.CONFIG["assembler.resuperpose"]:
            # We mirror the image (up-down and left-right),
            # then paste is with luminance as mask.
            # This lights up only dark areas while leaving other areas almost untouched.
            # This way, we get rid of most dark areas.
            im_color = ImageOps.mirror(ImageOps.flip(finalimage))  # Flip image vertically and horizontally
            im_mask = ImageOps.invert(finalimage.convert('L'))   # Use the image luminance as mask
            #im_mask = ImageEnhance.Brightness(im_mask).enhance(0.7)  # Darken the mask
            finalimage.paste(im_color,(0,0),im_mask)
            finalimage = ImageOps.equalize(finalimage)

        #  TEST for a new variante. (Less dark areas)
        # (We solarize very dark values.)
        '''
        finalimage = ImageOps.invert(finalimage)
        finalimage = ImageOps.solarize(finalimage, threshold=150)
        finalimage = ImageOps.invert(finalimage)
        finalimage = ImageOps.autocontrast(finalimage)
        '''

        if self.CONFIG["assembler.mirror"]:
            finalimage = ImageOps.mirror(finalimage)
        if self.CONFIG["assembler.emboss"]:
            finalimage_embossed = finalimage.filter(ImageFilter.EMBOSS).filter(ImageFilter.SMOOTH)  # Emboss image
            finalimage = ImageOps.equalize( ImageChops.multiply(finalimage, finalimage_embossed) )  # Compose images
            #finalimage = Image.blend(finalimage,finalimage_embossed,0.5)
        if self.CONFIG["assembler.invert"]:
            finalimage = ImageOps.invert(finalimage)


        (imagex,imagey) = finalimage.size
        # Superpose the webGobbler "logo" in the lower right corner
        (logox,logoy) = WEBGOBBLER_LOGO.size
        #finalimage.paste(WEBGOBBLER_LOGO,(imagex-logox-4,imagey-logoy-2),WEBGOBBLER_LOGO_TRANSPARENCY)
        finalimage.paste(WEBGOBBLER_LOGO,(imagex-logox-4,imagey-logoy-2+6),WEBGOBBLER_LOGO_TRANSPARENCY)  # Adjustment for the new logo
        return finalimage

    def _saveCurrentImage(self):
        ''' Save current image state.  (self.currentImage to file)
            This method must only be called by the thread !
        '''
        if self.currentImage != None:
            savepath = os.path.join(self.CONFIG["persistencedirectory"],"assembler_superpose_current.bmp")
            try:
              self.currentImage.save(savepath)
            except IOError as exc:
              raise IOError("Could not save current image to %s because: %s" % (savepath,exc))

    def _loadPreviousImage(self,ignorePreviousImage=False):
        ''' Try to get persisted image (image from previous run of program)
            (file to self.currentImage)

            Input:
                ignorePreviousImage (boolean) : If True, will ignore previous image and start a new from scratch.
        '''
        try:
            if ignorePreviousImage:
                raise IOError  # Force to create a new image.
            self.currentImage = Image.open(os.path.join(self.CONFIG["persistencedirectory"],"assembler_superpose_current.bmp"))
            # If the image does not have the same size, resize it.
            (imagex,imagey) = self.currentImage.size
            if (imagex!=self.CONFIG["assembler.sizex"]) or (imagey!=self.CONFIG["assembler.sizey"]):
                if self.currentImage.mode != 'RGB':
                    self.currentImage = self.currentImage.convert('RGB')
                self.currentImage = self.currentImage.resize((self.CONFIG["assembler.sizex"],self.CONFIG["assembler.sizey"]),Image.LANCZOS)
                self._logDebug("Starting from previous image resized.")
            else:
                self._logDebug("Starting from previous image.")
        except IOError:
            # Could not read image, create a new one.
            self.currentImage = Image.new('RGB',(self.CONFIG["assembler.sizex"],self.CONFIG["assembler.sizey"]))
            # Before the first images are superposed, we display "Please wait while the first images are downloaded..."
            self.currentImage.paste(PLEASE_WAIT_IMAGE,(30,30))
            self._logDebug("Starting a new image.")
            # Tell the superpose method to blank image when starting to superpose
            # (in order to remove the "Please wait while.." message.)
            self.blankImage = True

        # Prepare image for output so that it's immediately available.
        finalImage = self._postProcessImage(self.currentImage)
        self.finalImageLock.acquire()
        self.finalImage = finalImage
        self.finalImageCompletionDate = time.time()
        self.finalImageLock.release()

    # --------------------------------------------------------------------------
    # Public methods:
    def superpose(self):
        ''' Order the thread to superpose n images. This call is non-blocking.
            After this call, you can call getImage() but you are not guaranteed to get an image.
            (You may get None is the superpose option has not completed.) '''
        self.inputCommandQueue.put(commandToken(superpose=self.CONFIG["assembler.superpose.nbimages"]),True)

    def superposeB(self):
        ''' Order the thread to superpose n images, and wait for completion. This call is blocking.
            After the end of this call, you can call getImage() and you will always get an image..'''
        if not self.isAlive(): return
        # Ask the thread to superpose images.
        self.inputCommandQueue.put(commandToken(superpose=self.CONFIG["assembler.superpose.nbimages"]),True)
        # Then wait for completion:
        while True:  # We loop until .get(block=True) does not raise Queue.Empty exception.
            try:
                self.superposeCompleted.get(block=True,timeout=1)
                return
            except queue.Empty:
                if not self.isAlive(): return  # Do not wait for an answer if thread is dead !
                time.sleep(0.25)

    def getImage(self):
        ''' Returns an image from the assembler (if available).
            This call is non-blocking.
            Returns a PIL Image object, or None if no image is available.

            If you call getImage() after superposeB(), you are guaranteed to have an image.
        '''
        finalImage = None
        self.finalImageLock.acquire()
        if self.finalImage != None:
            finalImage = self.finalImage.copy()
        self.finalImageLock.release()
        return finalImage

    def shutdown(self):
        ''' Order the thread to shutdown and die. '''
        self.inputCommandQueue.put(commandToken(shutdown=1),True)

    def saveImageTo(self,destinationFilename):
        ''' Save last generated image to a file. '''
        if not self.isAlive(): return
        self._logInfo("Saving image to %s" % destinationFilename )
        # Saving image to persistence directory
        self.getImage().save(destinationFilename)  # Save generated image to disk.
        self._logInfo("Done.")

    def _darkenImageBorder(self,image,borderSize=30):
        '''
        Uses a gradient to darken the 4 borders of an image.

        Input:
            image (PIL Image object): the image to process
              WARNING: the image object is not preserved.
              (You can pass yourImage.copy() to prevent this.)
            size (int) : size of the gradient (in pixels)
        Output:
            a PIL Image object: the image with darkened borders.
        '''
        if borderSize <= 0:
            return image

        # Step 1 : create an image and a mask of the right width
        horImage = Image.new('RGB', (image.size[0],borderSize))
        horMask = Image.new('L',horImage.size)
        verImage = Image.new('RGB', (borderSize,image.size[1]))
        verMask = Image.new('L',verImage.size)

        # Step 2 : Draw a gray gradient in the mask:
        drawH = ImageDraw.Draw(horMask)
        drawV = ImageDraw.Draw(verMask)
        for i in range(borderSize):
            drawH.line( (0, i, horMask.size[0], i) ,fill=256-(256*i/borderSize))
            drawV.line( (i,0, i, verMask.size[1]) ,fill=256-(256*i/borderSize))
        del drawH
        del drawV

        # Step 3 : Paste the black image with the gradient mask on the original image:
        image.paste(horImage,(0,0),horMask)  # Paste at image top.
        image.paste(horImage,(0,image.size[1]-borderSize),ImageOps.flip(horMask))  # Paste at image bottom
        image.paste(verImage,(0,0),verMask)  # Paste at image top.
        image.paste(verImage,(image.size[0]-borderSize,0),ImageOps.mirror(verMask))  # Paste at image bottom

        return image

def get_unix_lib(lib_name):
    '''Find an Unix / Linux shared library path to use it with ctypes'''

    lib_path=['/lib/','/usr/lib/'] # Standard libs path
    personal_lib_path=os.environ.get("LD_LIBRARY_PATH") # Personal libs path

    if personal_lib_path:
        lib_path += personal_lib_path.split(':')

    if os.path.isfile("/etc/ld.so.conf"): # Other global libs path
        lib_path += open("/etc/ld.so.conf").read().strip().split('\n')

    for path in lib_path:
        if not os.path.isdir(path):
            continue
        for element in os.listdir(path):
            if element[:len(lib_name)] == lib_name: # The letters in the beginning of this lib are the same as our lib_name. I guess this is one of its versions
                return os.path.join(path, element)

    return None # Can't find it

def gnomeWallpaperChanger(config, wallpaperPath='.'):
    ''' Like windowssWallpaperChanger(), This will automatically change the Wallpaper, but under Gnome desktop with Gconf 2.x '''

    log = logging.getLogger('gnomeWallpaperChanger')

    try:
        import ctypes
    except ImportError as exc:
        raise ImportError("The ctypes module is required to run the Gnome wallpaper changer. See http://starship.python.net/crew/theller/ctypes/\nCould not import module because: %s" % exc)

    # Search the libgconf-2.so and load it
    gconf2_path=get_unix_lib("libgconf-2.so")
    if not gconf2_path:
        raise OSError("Is Gconf 2.x installed on your system? Older versions are currently unsupported. If you suspect a bug, please send me an email on frederic.weisbecker@wanadoo.fr")
    gconf=ctypes.CDLL(gconf2_path)
    # Get Gconf Api necessary functions
    g_type_init=gconf.g_type_init
    gconf_client_get_default=gconf.gconf_client_get_default
    gconf_client_set_string=gconf.gconf_client_set_string

    # Wallpaper entry on Gnome configuration
    wallpaper_config="/desktop/gnome/background/picture_filename"

    # Save the image
    wallpaperfilename = os.path.join(os.path.abspath(wallpaperPath),'webgobbler.bmp')
    a = assembler_superpose(pool=imagePool(config=config),config=config)
    a.start()
    a.saveImageTo(wallpaperfilename)

    # Change the "Desktop Wallpaper" value in Gnome configuration
    # Thanks to http://freshmeat.net/projects/wp_tray/ (where I found the way to change the wallpaper under Gnome)
    g_type_init()
    GConfClient=gconf_client_get_default()
    gconf_client_set_string(GConfClient, wallpaper_config, wallpaperfilename, 0)

    # Under gnome, if you change the "Desktop Wallpaper" path with the same path than before (even if the image changed)
    # gnome will not change the wallpaper, considering that nothing changed.
    # So we have to manage the wallpaper with two files: /path/image.ext (real path) and /path/~image.ext (symbolic link to the real path)
    wallpaperlinkname= os.path.join(os.path.abspath(wallpaperPath),'~webgobbler.bmp')
    if os.path.islink(wallpaperlinkname):
        os.remove(wallpaperlinkname)
    os.symlink(wallpaperfilename, wallpaperlinkname)
    link_tour=1

    try:
        while True:
            log.info("Generating a new wallpaper now with %d new images" % config["assembler.superpose.nbimages"])
            a.superposeB()
            a.saveImageTo(wallpaperfilename)
            if link_tour: # It's the wallpaper's link tour
                gconf_client_set_string(GConfClient, wallpaper_config, wallpaperlinkname, 0)
            else: # Normal filename tour
                gconf_client_set_string(GConfClient, wallpaper_config, wallpaperfilename, 0)

            link_tour^=1
            log.info("Done. Next wallpaper in %d seconds." % config["program.every"])
            time.sleep(config["program.every"])
    finally:
        a.shutdown()
        a.join()

def kdeWallpaperChanger(config, wallpaperPath="."):
    '''Like windowsWallpaperChanger (), This will automatically change the Wallpaper, but under Kde 3.x Desktop (and perhaps older versions)'''

    log=logging.getLogger('kdeWallpaperChanger')

    try:
        import pcop
    except ImportError as exc:
        raise ImportError("The python-dcop module is required to run The Kde wallpaper. Python-dcop is included into kdebindings (a part of kde). Your distribution probably have this package.\nCould not import module because: %s" % exc)

    # Does setWallpaper() 's kdesktop method exists?
    wallpaper_methods=pcop.method_list("kdesktop","KBackgroundIface")
    try:
        wallpaper_methods.index('void setWallpaper(QString wallpaper,int mode)')
    except ValueError:
        raise ValueError("Webgobbler needs to use kde resources with dcop service to manage kde wallpaper. I'm unable to access kdesktop 's setWallpaper() method. Perhaps kde is not started or you are running a too old kde version.")

    wallpaperfilename = os.path.join(os.path.abspath(wallpaperPath),'webgobbler.bmp')
    a = assembler_superpose(pool=imagePool(config=config),config=config)
    a.start()
    a.saveImageTo(wallpaperfilename)

    # Set wallpaper
    # Thanks to http://linuxfr.org/tips/213.html where I found the way to change wallpaper under Kde,
    # http://lea-linux.org/cached/index/Dev-dcop.html and thanks to many other urls....
    pcop.dcop_call("kdesktop", "KBackgroundIface", "setWallpaper", (wallpaperfilename,1))
    # Create a link to the wallpaper to alternate two names for the wallpaper for the same reason explained in changeGnomeWallpaper
    wallpaperlinkname= os.path.join(os.path.abspath(wallpaperPath),'~webgobbler.bmp')
    os.symlink(wallpaperfilename, wallpaperlinkname)
    link_tour=1

    try:
        while True:
            log.info("Generating a new wallpaper now with %d new images" % config["assembler.superpose.nbimages"])
            a.superposeB()
            a.saveImageTo(wallpaperfilename)
            if link_tour: # Tell kdesktop to use the picture's link path
                pcop.dcop_call("kdesktop", "KBackgroundIface", "setWallpaper", (wallpaperlinkname,1))
            else: # Tell kdesktop to use the normal picture's path
                pcop.dcop_call("kdesktop", "KBackgroundIface", "setWallpaper", (wallpaperfilename,1))

            link_tour^=1
            log.info("Done. Next wallpaper in %d seconds." % config["program.every"])
            time.sleep(config["program.every"])
    finally:
        a.shutdown()
        a.join()

def windowsWallpaperChanger(config, wallpaperPath='.'):
    ''' This will automatically change the Windows wallpaper.
        wallpaperPath (string): Directory where to put webgobbler.bmp which will be used as wallpaper (Default: current directory)
        config (an applicationConfig object) : the program configuration

        Example:
            windowsWallpaperChanger(applicationConfig())
    '''
    log = logging.getLogger('windowsWallpaperChanger')

    # FIXME: Option to restore old wallpaper on exit ?
    try:
        import ctypes
    except ImportError as exc:
        raise ImportError("The ctypes module is required to run the Windows wallpaper changer. See http://starship.python.net/crew/theller/ctypes/\nCould not import module because: %s" % exc)
    SM_CXSCREEN = 0
    SM_CYSCREEN = 1

    # Get Windows screen resolution and use it (we ignore resolution specified in command-line)
    screen_resolution = ( ctypes.windll.user32.GetSystemMetrics(SM_CXSCREEN), ctypes.windll.user32.GetSystemMetrics(SM_CYSCREEN) )
    log.info("Using screen resolution %dx%d"%(screen_resolution[0],screen_resolution[1]))
    (config["assembler.sizex"],config["assembler.sizey"]) = screen_resolution

    SPI_SETDESKWALLPAPER = 20 # According to http://support.microsoft.com/default.aspx?scid=97142
    wallpaperfilename = os.path.join(os.path.abspath(wallpaperPath),'webgobbler.bmp')
    a = assembler_superpose(pool=imagePool(config=config),config=config)
    a.start()
    # Display immediately an image:
    a.saveImageTo(wallpaperfilename)
    ctypes.windll.user32.SystemParametersInfoA(SPI_SETDESKWALLPAPER, 0, wallpaperfilename , 0)
    try:
        while True:
            log.info("Generating a new wallpaper now with %d new images" % config["assembler.superpose.nbimages"])
            a.superposeB() # Evolve current image
            a.saveImageTo(wallpaperfilename)
            # Force Windows to use our wallpaper:
            ctypes.windll.user32.SystemParametersInfoA(SPI_SETDESKWALLPAPER, 0, wallpaperfilename , 0)
            log.info("Done. Next wallpaper in %d seconds." % config["program.every"])
            time.sleep(config["program.every"])
    finally:
        a.shutdown()
        a.join()   # Make sure assemble is shutdown before shutting down the image pool.

def image_saver(config, imageName='webgobbler.bmp',generateSingleImage=False):
    ''' Continuously generate new images (using the assembler_superpose) and save them
        into a file.
        config (an applicationConfig object) : the program configuration
        imageName (string): name of image to save (eg."toto.jpeg","dudu.png"...)
        generateSingleImage (bool): If True, will generate a single image.
    '''
    log = logging.getLogger('image_saver')
    a = assembler_superpose(pool=imagePool(config=config),config=config)
    a.start()
    try:
        while True:
            log.info("Generating a new image to %s" % imageName)
            a.superposeB()  # Evolve current image
            a.saveImageTo(imageName)
            if generateSingleImage: break;
            log.info("Will generate a new image in %d seconds." % config["program.every"])
            time.sleep(config["program.every"])
    finally:
        a.shutdown()
        a.join()

def windowsScreensaver(startmode,config):
    ''' Start as Windows Screensaver
        startmode (string): Start option
             s = start screensaver
             c = display GUI to configure screensaver
             p = preview screensaver (FIXME: get Window handle)
             a = set Window screensaver password (95/98/ME)
        config (an applicationConfig object) : the program configuration
        Example: python webgobbler.py --localonly -s --every 20

        This class does not depend on Mark Hammond's win32 modules, nor Tkinter, nor pyScr.
        It only requires bare ctypes module and (of course) PIL (Python Imaging Library)
    '''
    # I chose to tap directly in the Win32 API (which explains why the code below is
    # ugly and low-level) in order not to depend on Mark Hammond's Win32 modules,
    # nor Tkinter modules, nor pyScr.
    # Here, we entierly depend on ctypes only.
    # Less dependencies, more joy.
    # This will give smaller binaries.

    log = logging.getLogger('windowsScreensaver')

    try:
        import wgwin32screensaver
    except ImportError as exc:
        raise ImportError("wgwin32screensaver module is required to run the Windows screensaver.\nCould not import module because: %s" % exc)

    # Check parameters passed.
    if not (startmode in ('s','c','p','a')):
        raise RuntimeError("Parameter startmode=%s not supported by windowsScreensaver." % str(startmode))

    if startmode=='s':
        # Get current screen resolution:
        screen_resolution = wgwin32screensaver.getScreenResolution()
        # screen_resolution is a tuple (x,y) where x and y are integers.

        # Ignore resolution specified in command-line and use screen resolution.
        log.info("Using screen resolution %dx%d"%(screen_resolution[0],screen_resolution[1]))
        (config["assembler.sizex"],config["assembler.sizey"]) = screen_resolution

        a = assembler_superpose(pool=imagePool(config=config),config=config)
        a.start()         # Start the assembler (non-blocking)

        # Ask the wgwin32screensaver module to create the screensaver Window
        # and handle the low-level stuff (Windows message handling, etc.)
        # messageLoop() will use the assembler we created.
        try:
            wgwin32screensaver.messageLoop(assembler_sup=a,config=config);  # this call is a blocking call.
        finally:
            # At this point, the screensaver has stopped and the screensaver window
            # has disappeared, but some threads are still alive (collectors, pool, etc.)
            # We ask all threads to shutdown, but this may take a while...
            a.shutdown()  # When we shutdown the assembler, the assembler will take care of shutting all threads it manages.
            a.join()
        return

    if startmode=='p':
        return  # Ignore.  FIXME: Implement the preview mode.

    # else, display error:
    raise NotImplementedError("/%s option not implemented yet" % startmode)

def x11Screensaver(config):
    ''' Start as XWindow Screensaver (XFree86) in a Linux/Unix os type.
    You have to start your XWindow server before starting this mode.
    You will only need ctypes module to run this mode.
    As gnomeWallpaperChanger and kdeWallpaperChanger are inspired from windowsWallpaperChanger
    function, x11Screensaver function is directly inspired from windowsScreensaver's
        function written by Sebsauvage.
    '''

    log = logging.getLogger('XwindowScreensaver')

    try:
        import wgx11screensaver
    except ImportError as exc:
        raise ImportError("wgx11screensaver module is required to run the XWindow screensaver.\nCould not import module because: %s" % exc)

    # Define our unix_lib finder on wgx11screensaver module
    wgx11screensaver.get_unix_lib=get_unix_lib
    # Get current screen resolution:
    screen_resolution = wgx11screensaver.getScreenResolution()
    # screen_resolution is a tuple (x,y) where x and y are integers.

    # Ignore resolution specified in command-line and use screen resolution.
    log.info("Using screen resolution %dx%d"%(screen_resolution[0],screen_resolution[1]))
    (config["assembler.sizex"],config["assembler.sizey"]) = screen_resolution

    a = assembler_superpose(pool=imagePool(config=config),config=config)
    a.start()         # Start the assembler (non-blocking)

    # Launch the Xwindow Screensaver
    try:
        wgx11screensaver.Loop(assembler_sup=a,config=config)  # this call is a blocking call.
    finally:
        # At this point, the screensaver has stopped and the screensaver window
        # has disappeard, but some threads are still alive.
        # We ask all threads to shutdown, but this may take a while...
        a.shutdown()
        a.join()
        return

def htmlPageGenerator(htmlFilename,config):
    ''' Generates a HTML page and a JPEG image.
        The HTML page contains refresh META tags so that the page is
        automatically reloaded in the browser.

        Input: htmlFilename (string): name of the HTML file (with or without path)
               config (an applicationConfig object) : the program configuration
        The name of the JPEG file will always be webgobbler.jpg
        (progressive JPEG file).
    '''
    log = logging.getLogger('htmlPageGenerator')
    a = assembler_superpose(pool=imagePool(config=config),config=config)
    a.start()
    # Get the path of the htmlFile and write the image in the same directory:
    (path,htmlfilename) = os.path.split(htmlFilename)
    if path == None: path = "."
    path = os.path.abspath(path)  # Convert to absolute path.

    try:
        while True:
            log.info("Generating an image and HTML page in %s..." % path)
            a.superposeB()  # Evolve current image
            i = a.getImage()
            if len(path.strip())>0:
                imagepath = os.path.join(path,'webgobbler.jpg')
            else:
                imagepath = 'webgobbler.jpg'
            i.save(imagepath,option={'progression':True,'quality':70,'optimize':True})
            file = open(htmlFilename,'w+b')  # Overwrite any existing html page with this name.
            file.write('''<html>
  <head>
    <meta http-equiv="refresh" content="%d; url=%s">
    <title>Image created with WebGobbler - http://sebsauvage.net/python/webgobbler/</title>
    <!-- This page was automatically generated by webGobbler on %s-->
  </head>
  <body bgcolor="#000000" style="margin: 0px;">
    <img src="webgobbler.jpg" width="%d" height="%d" alt="webGobbler generated image">
  </body>
</html>
''' % (config["program.every"],htmlfilename,time.asctime(time.localtime()),i.size[0],i.size[1]))
            file.close()
            log.info("Will generate a new image and HTML page in %d seconds." % config["program.every"])
            time.sleep(config["program.every"])
    finally:
        a.shutdown()
        a.join()



# ### Program help ###############################################################

def usage(programname):
    '''Displays program help and command-line options.'''
    if programname.endswith('.py'):
        programname = 'python '+programname
    # FIXME: code the following parameters for the windows screensaver.
    '''
    /p  : Preview Windows screensaver
    /a  : Set Windows screensaver password (95/98/ME only)
    '''
    t = PROGRAMHELP%((programname,)*8)
    sys.stdout.write(t)

def setUrllibProxy(log, CONFIG):
    ''' Sets the URLLib proxy for the application.

        Input:
            config (an applicationConfig object)  : the program configuration
            log (a logger object) to spit information out.
        Output
            an applicationConfig object : the modified configuration
            (in case we had to ask for the password.)
    '''
    # FIXME: Write handler in case proxy asks for authentication
    #        and --proxyauth was not provided ?
    # FIXME: Test proxy login/password here ?
    # FIXME: Handle HTTP error if proxy login/password is wrong ?
    if CONFIG["network.http.proxy.enabled"]:
        if log != None:
            log.info('  Using proxy %s:%d' % (CONFIG["network.http.proxy.address"],CONFIG["network.http.proxy.port"]))
        if CONFIG["network.http.proxy.auth.enabled"]:  # For proxy with Basic authentication
            #if p_action =='--saveconffile':
            #    log.warning("*** WARNING: The proxy password will be saved in a file in your home directory.")
            #if p_action =='--saveconfreg':
            #    log.warning("*** WARNING: The proxy password will be saved in the Windows registry.")
            if len(CONFIG["network.http.proxy.auth.password"])==0:
                CONFIG["network.http.proxy.auth.password"] = getpass.getpass("  Please enter password for %s at %s:%d:" % (CONFIG["network.http.proxy.auth.login"],CONFIG["network.http.proxy.address"],CONFIG["network.http.proxy.port"]))
            if log != None:
                log.info("  Using authentication on proxy.")
            # Code shamelessly copy-pasted from:
            # http://groups.google.com/groups?selm=mailman.983901970.11969.python-list%40python.org
            proxy_info = { 'host' : CONFIG["network.http.proxy.address"],
                           'port' : CONFIG["network.http.proxy.port"],
                           'user' : CONFIG["network.http.proxy.auth.login"],
                           'pass' : CONFIG["network.http.proxy.auth.password"]
                         }
            # build a new opener that uses a proxy requiring authorization
            proxy_support = urllib.request.ProxyHandler({"http" :
                            "http://%(user)s:%(pass)s@%(host)s:%(port)d" % proxy_info})
            opener = urllib.request.build_opener(proxy_support)
            urllib.request.install_opener(opener)  # install it as the default opener
        else:  # Use proxy with no password
            proxy_info = { 'host' : CONFIG["network.http.proxy.address"],
                           'port' : CONFIG["network.http.proxy.port"]
                         }
            # build a new opener that uses a proxy
            proxy_support = urllib.request.ProxyHandler({"http" :
                            "http://%(host)s:%(port)d" % proxy_info})
            opener = urllib.request.build_opener(proxy_support)
            urllib.request.install_opener(opener)  # install it as the default opener
    else:
        # Disable proxy
        # (We have to disable any existing installed ProxyHandler):
        opener = urllib.request.build_opener()  # Get the default handler.
        urllib.request.install_opener(opener)  # install it as the default opener
    return CONFIG


# == Main ======================================================================

def main():
    '''Parses the command-line options and rects accordingly (launches the GUI, etc.). '''

    CONFIG = applicationConfig()

    # Set up the default log:
    logging.getLogger().setLevel(logging.INFO)  # By default, only display informative messages and fatal errors.
    # Attach a handler to this log:
    handler_stdout = logging.StreamHandler()
    handler_stdout.setFormatter(logging.Formatter('%(message)s'))
    #handler_stdout.setFormatter(logging.Formatter('%(name)s: %(message)s'))  # Change format of messages.

    logging.getLogger().addHandler(handler_stdout)

    log = logging.getLogger('main')    # The log for the main()


    # Default value for command-line parameters:
    p_action = None            # Action to perform (screensaver, wallpaper changer...)
    p_action_parameter = None  # Optional parameters for action

    # Parse command-line options:
    # In case we are called directly by Windows as a screensaver, the command-line may contain /s /c /p or /a
    # We first parse the command-line ourselves.
    if len(sys.argv) > 1:
        line_option = sys.argv[1].lower() # Get the first command-line option.
        if len(line_option)>1 and line_option[0] in ('/','-') and line_option[1] in ('s','c','p','a'):
            p_action = "--windowsscreensaver"
            p_action_parameter = line_option[1]
            del sys.argv[1]  # Then remove this option (because getopt does not like slashes)
            if p_action_parameter=='c':
                import webgobbler_config
                webgobbler_config.main()  # Call the configuration GUI
                return # Then exit.

    # Then we let the command-line be parsed by getopt:
    # FIXME: Use the new optparse module ?
    try:
        opts, args = getopt.getopt(sys.argv[1:],'',['tofile=','resolution=','debug','variante=','emboss',
                                                    'keepimages','nbimages=','every=','pooldirectory=',
                                                    'invert','mirror','poolnbimages=','localonly','help',
                                                    'proxy=','proxyauth=','singleimage=','tohtml=',
                                                    'bordersmooth=', 'tognomewallpaper','tokdewallpaper',
                                                    'towindowswallpaper','norotation','resuperpose','guiconfig',
                                                    'saveconfreg','loadconfreg','saveconffile','loadconffile',
                                                    'xscreensaver','scale=','keywords='])
    except getopt.GetoptError as ex:
        print(("Error in command-line: %s" % ex))
        #usage(sys.argv[0])  # print help information and exit:
        logging.shutdown()
        return

    for opt, arg in opts:
        if opt == '--resolution':  # Example: --resolution 1024x768
            (x,y) = arg.split('x')  # FIXME: try/except split+assignment
            CONFIG["assembler.sizex"] = int(x)      # FIXME: try/except conversion to int
            CONFIG["assembler.sizey"] = int(y)
        elif opt == '--help':
            usage(sys.argv[0])  # print help information and exit:
            return  # Exit program.
        elif opt == '--every':
            CONFIG["program.every"] = int(arg) # FIXME: try/except conversion to int
        elif opt == '--keepimages':
            CONFIG["pool.keepimages"] = True
        elif opt == '--pooldirectory':
            CONFIG["pool.imagepooldirectory"] = str(arg)
        elif opt == '--poolnbimages':
            CONFIG["pool.nbimages"] = int(arg)        # FIXME: try/except conversion to int
        elif opt == '--nbimages':
            CONFIG["assembler.superpose.nbimages"] = int(arg)   # FIXME: try/except conversion to int
        elif opt == '--keywords':
            CONFIG["collector.keywords.enabled"] = True
            CONFIG["collector.keywords.keywords"] = str(arg)
        elif opt == '--bordersmooth':
            CONFIG["assembler.superpose.bordersmooth"] = int(arg)   # FIXME: try/except conversion to int
        elif opt == '--invert':
            CONFIG["assembler.invert"] = True
        elif opt == '--mirror':
            CONFIG["assembler.mirror"] = True
        elif opt == '--emboss':
            CONFIG["assembler.emboss"] = True
        elif opt == '--resuperpose':
            CONFIG["assembler.resuperpose"] = True
        elif opt == '--localonly':
            CONFIG["collector.localonly"] = True
        elif opt == '--debug':
            CONFIG["debug"] = True
        elif opt == "--variante":
            CONFIG["assembler.superpose.variante"] = int(arg)   # FIXME: try/except conversion to int
        elif opt == "--scale":
            CONFIG["assembler.superpose.scale"] = float(arg)    # FIXME: try/except conversion to float
        elif opt == '--norotation':
            CONFIG["assembler.superpose.randomrotation"] = False
        elif opt == '--proxy':
            proxyaddress, proxyport = str(arg).split(":")
            CONFIG["network.http.proxy.address"] = proxyaddress
            CONFIG["network.http.proxy.port"] = int(proxyport)   # FIXME: try/except conversion to int
            CONFIG["network.http.proxy.enabled"] = True
            # FIXME: Test proxy connexion here ?
            # FIXME: handle authentication errors.
        elif opt == '--proxyauth':
            CONFIG["network.http.proxy.auth.enabled"] = True
            if arg.find(":") > 0:
              proxylogin, proxypasswd = arg.split(":")
            else:
              proxylogin = arg
              proxypasswd = ""
            CONFIG["network.http.proxy.auth.login"] = proxylogin
            CONFIG["network.http.proxy.auth.password"] = proxypasswd
        elif opt in ('--tofile'):  # Save to file
            p_action = opt
            p_action_parameter = arg
        elif opt in ('--towindowswallpaper'):  # Set wallpaper under Windows
            p_action = opt
        elif opt in ('--tognomewallpaper'):  # Set wallpaper under Gnome
            p_action = opt
        elif opt in ('--tokdewallpaper'):  # Set wallpaper under Kde
            p_action = opt
        elif opt in ('--xscreensaver'): # Set image on a xwindow Screensaver (Linux or Unix with XFree86)
            p_action = opt
        elif opt in ('--singleimage'):  # Generate a single image and exit.
            p_action = opt
            p_action_parameter = arg
        elif opt in ('--tohtml'):  # Generate a HTML page and JPEG image continuously
            p_action = opt
            p_action_parameter = arg
        elif opt == '--guiconfig':   # Display configuration screen
            p_action = opt
        elif opt == '--saveconffile':  # Save configuration to file
            p_action = opt
        elif opt == '--loadconffile':  # Load configuration from file.
            log.info("Loading options from user's home dir...")
            CONFIG.loadFromFileInUserHomedir()
        elif opt == '--saveconfreg':   # Save configuration to registry
            p_action = opt
        elif opt == '--loadconfreg':   # Load configuration from registry
            log.info("Loading options from Windows registry...")
            CONFIG.loadFromRegistryCurrentUser()

    # If the Windows screensaver was called, ignore options set above,
    # and read from registry:
    if p_action == "--windowsscreensaver":
        log.info("Reading configuration from registry")
        CONFIG.loadFromRegistryCurrentUser()

    # If the action is to call the configuration GUI, call the GUI and exit
    # (do not start image generation)
    # Note: configuration specified in command-line (such as --mirror)
    #       will be ignored when using --guiconfig
    if p_action == "--guiconfig":
        import webgobbler_config
        webgobbler_config.main()  # Call the GUI configuration
        return  # Then exit.

    # When running in GUI application mode, get the config from registry or .ini by default.
    if p_action==None:
        CONFIG = getConfig()


    if CONFIG["debug"]:  # If we are running in debug mode:
        # Change the display of the main log (to screen)
        handler_stdout.setFormatter(logging.Formatter('%(name)s: %(message)s'))  # Change format of messages.
        logging.getLogger().setLevel(logging.DEBUG)  # And switch to DEBUG view (=view all messages)
        # And also log everything to a file:
        handler = logging.FileHandler('webGobbler.log') # Log to a file.
        handler.setFormatter(logging.Formatter('[%(thread)d] %(name)s: %(message)s'))
        logging.getLogger().addHandler(handler)

    # Display parameters:
    log.info('Parameters:')

    # Configure proxy (if provided in command-line):
    CONFIG = setUrllibProxy(log, CONFIG)

    log.info('  Resolution: %dx%d' % (CONFIG["assembler.sizex"],CONFIG["assembler.sizey"]))
    log.info('  Generate new image every %d seconds' % CONFIG["program.every"])
    if CONFIG["assembler.invert"]: log.info('  Images will be inverted (negative)')
    if CONFIG["assembler.mirror"]: log.info('  Images will be mirror (left-right)')
    if CONFIG["assembler.emboss"]: log.info('  Images will be embossed')
    if CONFIG["assembler.resuperpose"]: log.info('  Images will be re-superposed')
    if not CONFIG["assembler.superpose.randomrotation"]: log.info('  Rotation is disabled.')
    log.info('  Use %d images at each image generation' % CONFIG["assembler.superpose.nbimages"])
    log.info('  Image pool storage directory: %s' % CONFIG["pool.imagepooldirectory"])
    log.info('  Will try to maintain %d images in this directory.' % CONFIG["pool.nbimages"])
    if CONFIG["pool.keepimages"]:
        log.info('  Will keep images after use.')
    if CONFIG["collector.localonly"]:
        log.info('  Will collect image from local system instead of internet')
    if CONFIG["collector.keywords.enabled"]:
        log.info("  Will search the internet for the words '%s'" % CONFIG["collector.keywords.keywords"])


    if CONFIG["debug"]:
        log.info('  Running in debug mode.')

    # Otherwise, execute the desired action:
    if p_action == '--tofile':
        log.info('Starting image generator...')
        image_saver(imageName=p_action_parameter,config=CONFIG)
    if p_action == '--singleimage':
        log.info('Generating a single image...')
        image_saver(imageName=p_action_parameter,generateSingleImage=True,config=CONFIG)
    elif p_action == "--tohtml":
        log.info("Starting HTML page generator...")
        htmlPageGenerator(p_action_parameter,config=CONFIG)
    elif p_action == '--towindowswallpaper':
        log.info('Starting wallpaper changer...')
        windowsWallpaperChanger(config=CONFIG)
    elif p_action == '--tognomewallpaper':
        log.info('Starting wallpaper changer...')
        gnomeWallpaperChanger(config=CONFIG)
    elif p_action == '--tokdewallpaper':
        log.info('Starting wallpaper changer...')
        kdeWallpaperChanger(config=CONFIG)
    elif p_action == "--windowsscreensaver":
        log.info("Starting Windows screensaver...")
        windowsScreensaver(p_action_parameter,config=CONFIG)
    elif p_action == "--xscreensaver":
        log.info("Starting X11 Window Screensaver...")
        x11Screensaver(config=CONFIG)
    elif p_action == "--saveconfreg":
        CONFIG.saveToRegistryCurrentUser()
        log.info("Configuration saved to Windows registry.")
    elif p_action == "--saveconffile":
        CONFIG.saveToFileInUserHomedir()
        log.info("Configuration saved in user's home directory.")
    else: # If no action is provided, display command-line parameters.
        webgobbler_application(CONFIG)
        #log.error('No running mode provided ; Displaying help:')
        #usage(sys.argv[0])  # print help information and exit:
        logging.shutdown()
        return

    logging.shutdown()


def getConfig():
    '''Returns automatically webGobbler configuration from what's available: registry or .ini file.

       If none can be found, default config is returned.

       Output: an applicationConfig object.
    '''
    config = applicationConfig()  # Get a new applicationConfig object.
    configSource = None
    # First, we try to read configuration from registry.
    try:
        config.loadFromRegistryCurrentUser()
        configSource = "registry"
    except ImportError:
        pass
    except WindowsError:
        pass

    if configSource == None:
        # We are probably not under Windows, or the registry could not be read.
        # We try to read the .ini file in user's home directory:
        try:
            config.loadFromFileInUserHomedir()
            configSource = "inifile"
        except:
            configSource = 'default'
    return config

def webgobbler_application(config):
    '''Runs webGobbler as a GUI application.

       config (applicationConfig object) : the configuration
    '''
    # Import all GUI stuff:

    import tkinter  # FIXME: try/catch import ?

    try:
        import Pmw
    except ImportError as exc:
        raise ImportError("The Pmw (Python Megawidgets) module is required for the webGobbler application. See http://pmw.sourceforge.net/\nCould not import module because: %s" % exc)
    try:
        import webgobbler_app
    except ImportError as exc:
        raise ImportError("The webgobbler_app module is required to run the webGobbler application.\nCould not import module because: %s" % exc)
    root = tkinter.Tk()              # Initialize Tkinter
    Pmw.initialise(root)             # Initialize Pmw
    root.title(VERSION)         # Set window title.

    # Display the application window:
    wgapp = webgobbler_app.wg_application(root,config)  # Build the GUI, and pass the program configuration.
    root.mainloop()                  # Display it and let is operate...

if __name__ == "__main__":
    sys.stdout.write(f"{VERSION} -- {WEBSITE}\n")
    main()

