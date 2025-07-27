#!/usr/bin/python3


# When this program is frozen into an EXE with cx_Freeze with the no-console version (Win32GUI.exe)
# stdout, stderr and stdin do not exist.
# Any attempt to write to them (with print for example) would trigger an exception and
# the program.exe would display an exception popup.

# We trap this and create dummy stdin/stdout/stderr so that all print and log statements
# in this programm will work anyway.
# This is needed when bundling webGobbler with cx_Freeze with the console-less stub.

import sys
try:
    sys.stdout.write("\r")
    sys.stdout.flush()
except IOError:
    class dummyStream:
        ''' dummyStream behaves like a stream but does nothing. '''
        def __init__(self): pass
        def write(self,data): pass
        def read(self,data): pass
        def flush(self): pass
        def close(self): pass
    # and now redirect all default streams to this dummyStream:
    sys.stdout = dummyStream()
    sys.stderr = dummyStream()
    sys.stdin = dummyStream()
    sys.__stdout__ = dummyStream()
    sys.__stderr__ = dummyStream()
    sys.__stdin__ = dummyStream()

# For cx_freeze or py2exe, we need to import each image plugin individually:

try:
  from PIL import Image
  from PIL import ImageTk

  # ~ from PIL import ArgImagePlugin
  from PIL import BmpImagePlugin
  from PIL import CurImagePlugin
  from PIL import DcxImagePlugin
  from PIL import EpsImagePlugin
  from PIL import FliImagePlugin
  # ~ from PIL import FpxImagePlugin # requires olefile module
  from PIL import GbrImagePlugin
  from PIL import GifImagePlugin
  from PIL import IcoImagePlugin
  from PIL import ImImagePlugin
  from PIL import ImtImagePlugin
  from PIL import IptcImagePlugin
  from PIL import JpegImagePlugin
  from PIL import McIdasImagePlugin
  # ~ from PIL import MicImagePlugin # requires olefile module
  from PIL import MpegImagePlugin
  from PIL import MspImagePlugin
  from PIL import PalmImagePlugin
  from PIL import PcdImagePlugin
  from PIL import PcxImagePlugin
  from PIL import PdfImagePlugin
  from PIL import PixarImagePlugin
  from PIL import PngImagePlugin
  from PIL import PpmImagePlugin
  from PIL import PsdImagePlugin
  from PIL import SgiImagePlugin
  from PIL import SunImagePlugin
  from PIL import TgaImagePlugin
  from PIL import TiffImagePlugin
  from PIL import WmfImagePlugin
  from PIL import XbmImagePlugin
  from PIL import XpmImagePlugin
  from PIL import XVThumbImagePlugin

  from PIL import ImageFile
  from PIL import ImageOps
  from PIL import ImageEnhance
  from PIL import ImageFilter
  from PIL import ImageChops
  from PIL import ImageDraw
except ImportError as exc:
  raise ImportError("The Pillow module is required to run this program. See https://pypi.org/project/pillow\nCould not import module because: %s" % exc)
