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

def get_collectors(config):
    if config["collector.localonly"]:
        return [collector_local(config=config)]
    else:
        return [
            collector_googleimages(config=config),
            collector_yahooimagesearch(config=config),
            collector_flickr(config=config),
            collector_deviantart(config=config)
            ]
