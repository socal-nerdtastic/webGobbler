#!/usr/bin/python3

# import collectors
try:
    from collectors.google import collector_googleimages
    from collectors.yahoo import collector_yahooimagesearch
    from collectors.flickr import collector_flickr
    from collectors.deviantart import collector_deviantart
except ImportError:
    from google import collector_googleimages
    from yahoo import collector_yahooimagesearch
    from flickr import collector_flickr
    from deviantart import collector_deviantart

try:
    from collectors.local import collector_local
    from collectors.meta import commandToken
except ImportError:
    from local import collector_local
    from meta import commandToken

# The known collectors:
ALL_COLLECTORS = [
    collector_googleimages,
    collector_yahooimagesearch,
    collector_flickr,
    collector_deviantart,
    collector_local
]

def get_collectors(config):
    if config["collector.localonly"]:
        return [collector_local(config=config)]
    else:
        return [coll(config=config) for coll in ALL_COLLECTORS if coll is not collector_local]

