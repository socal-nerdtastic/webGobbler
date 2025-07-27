#!/usr/bin/python3

import sys

CTYPES_AVAILABLE = True
try:
    import ctypes
except ImportError:
    CTYPES_AVAILABLE = False

# If ctypes is available and we are under Windows,
# let's put a mutex so that the InnoSetup uninstaller knows
# when webGobbler is still running.
# (This mutex is not re-used in any other part of webGobbler).
WEBGOBBLER_MUTEX = None
if CTYPES_AVAILABLE and sys.platform=="win32":
    try:
        WEBGOBBLER_MUTEX = ctypes.windll.kernel32.CreateMutexA(None, False, "sebsauvage_net_webGobbler_running")
    except:
        pass  # If any error occured, nevermind the mutex: it's not critical for webGobbler.
              # (It's only an installer issue.)

# FIXME: Code some unit-testing !
# FIXME: Pychecker the code often !
# FIXME: Profile the code with the profile module, then optimize.

# === Globals ==================================================================

# Default list of blacklisted images (based on their content)
# These images will be discarded, whatever the name of the file or the
# website address.
# (You can do a sha1sum on the image you want to blacklist and put the SHA1 here)
# (This list may be overwritten by saved configuration (.INI file or registry.))
BLACKLIST_IMAGESHA1 = { '142da07c8cfd0aa9bebb0b2f5939ad636bd474e5' : 0,  # deviantArt.com "Poetry" logo
                        'd6ee67a52d8fbef935225de1363847d30a86b5de' : 0,  # FortuneCity hosting/domaine names logo
                        '6a92790b1c2a301c6e7ddef645dca1f53ea97ac2' : 0,  # Flickr "photo not available" GIF
                      }


# Default list of blacklisted URLs
# If an image comes from one of those URL, it will be discarded.
# You can use * in URLs.   An implicit * will be added at end (?a AdBlock)
# Examples: BLACKLIST_URL = [ 'http://*.doubleclick.net/', 'http://ads.*.*/', 'http://*.*.*/adserver/','*/banners/' ]
# (This list may be overwritten by saved configuration (.INI file or registry.))
BLACKLIST_URL = [ 'http://www.flickr.com/images/photo_unavailable.gif',
                  'http://*.deviantart.net/*/shared/poetry.jpg']


# Accepted MIME type.
# Only these types will be considered images and downloaded.
# key=MIME type (Content-Type),  value=file extension (which will be used to save
# the file in the imagepool directory)
ACCEPTED_MIME_TYPES = { 'image/jpeg': '.jpg',
                        'image/gif' : '.gif',
                        'image/png' : '.png',
                        'image/bmp' : '.bmp',   # Microsoft Windows space-hog file format
                        'image/pcx' : '.pcx',   # old ZSoft/Microsoft PCX format (used in Paintbrush)
                        'image/tiff': '.tiff'
                      }

# ---------------------------------------------------------------------------------------

DEFAULTCONFIG = {
		"network.http.proxy.enabled" : False,           # (boolean) If true, will use a proxy (--proxy)
		"network.http.proxy.address" : "",              # (string)  Address of proxy (example)
		"network.http.proxy.port"    : 3128,            # (integer) Port of proxy (example)
		"network.http.proxy.auth.enabled" : False,      # (boolean) Proxy requires authentication (--proxyauth)
		"network.http.proxy.auth.login"   : "",         # (string)  Login for proxy.
		"network.http.proxy.auth.password": "",         # (string)  Password for proxy.
		"network.http.useragent"     : "webGobbler/1.2.8",# (string) User-agent passed in HTTP requests.
		"collector.maximumimagesize" : 4000000,         # (integer) Maximum image file size in bytes. If a picture is bigger than this, it will not be downloaded.
		"collector.acceptedmimetypes": ACCEPTED_MIME_TYPES, # (dictionnary)  List of image types which will be downloaded.
		"collector.localonly"        : False,           # (boolean) If true, will collect images from local disk instead of internet (--localonly)
		"collector.localonly.startdir" : "/",           # (string) When using local disk only, the directory to scan for images (default="/"=Whole disk.)
		"collector.keywords.enabled" : False,           # (boolean) Use keywords for image search. If False, random generated words will be used.
		"collector.keywords.keywords": "cats",          # (string) Keyword(s) for keyword search. Can be a single word or several words separated with a space (eg."cats dogs")
		"pool.imagepooldirectory"    : "imagepool",     # (string)  Directory where to store image pool (--pooldirectory)
		"pool.nbimages"              : 50,              # (integer) Minimum number of images to maintain in pool (--poolnbimages)
		"pool.sourcemark"            : "--- Picture taken from ", # (string) String used to store image source in image files.
											   # If you change this string, you will have to delete all images from your pool.
		"pool.keepimages"            : False,           # (boolean) Do not delete images from the pool after use (--keepimage)
		"assembler.sizex"            : 1024,            # (integer) Width of image to generate (--resolution). Ignored for wallpaper changer and screensaver.
		"assembler.sizey"            :  768,            # (integer) Height of image to generate (--resolution). Ignored for wallpaper changer and screensaver.
		"assembler.mirror"           : False,           # (boolean) Horizontal mirror of image (to render text unreadable) (--mirror)
		"assembler.invert"           : False,           # (boolean) Invert (negative) final picture before saving (--invert)
		"assembler.emboss"           : False,           # (boolean) Emboss the final picture before saving (--emboss)
		"assembler.resuperpose"      : False,           # (boolean) Rotates and re-superposes the final image on itself.
		"assembler.superpose.nbimages": 20,             # (integer) Number of images to superpose on each new image (--nbimages)
		"assembler.superpose.randomrotation": True,     # (boolean) Rotate images randomly (--norotation to disable)
		"assembler.superpose.variante": 0,              # (integer) Variantes of the superpose assembler (this give different results) (--variante).
														# 0=Equalize (default, recommended), 1=Darkening+autoConstrast.
		"assembler.superpose.bordersmooth": 30,         # (integer) Size of border smooth (0 to disable border smooth.)
		"assembler.superpose.scale": float(1.0),        # (float) Scale images before superposing them (--scale)
		"persistencedirectory"       : ".",             # (string) Directory where classes save their data between program runs
		"program.every"              : 60,              # (integer) Generate a new image every n seconds (--every)
		"debug"                      : False,           # (boolean) debug mode (True will display various activity on screen and log into the file webGobbler.log) (--debug)
		"blacklist.imagesha1"        : BLACKLIST_IMAGESHA1, # (dictionnary: key=hex SHA1 (string), value=0) List of images to blacklist (based on their content)
		"blacklist.url"              : BLACKLIST_URL,   # (list of strings) List of blacklisted URLs.
		"blacklist.url_re"           : []               # (list of regular expression objets) Same as blacklist.url, but compiled as regular expressions.
														# (blacklist.url_re is automatically compiled from blacklist.url)
		}

# FIXME: Add explanations on each parameter ? (in another dictionnary with the same keys ? CONFIG_HELP ?))

# The following parameters will not be exported to INI or registry, nor imported.
# (Mostly because they are code dependant.)
NONEXPORTABLE_PARAMETERS = {
	"collector.acceptedmimetypes":0,
	"collector.maximumimagesize":0,
	"blacklist.url_re": 0,
	"pool.sourcemark":0,
	"network.http.useragent":0
	}

CONFIG_FILENAME =".webGobblerConf"  # Name of configuration file.
CONFIG_SECTIONNAME = "webGobbler"  # Name of section in .INI files.
CONFIG_REGPATH = "Software\\sebsauvage.net\\webGobbler"  # Registry key containing configuration

