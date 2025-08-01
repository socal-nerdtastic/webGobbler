webGobbler
==========

What is it ?
============

webGobbler is a generative art program. It creates pictures by assembling random images from the web. Think of it as attempt to capture the chaos of the human activity, which the internet is a partial and subjective snapshot of.

You can use it to create a cool CD case, get an everchanging wallpaper, make an original poster for you wall, get material for your art project... or just relax.

webGobbler runs as a GUI application or in command-line mode. It can work as a simple image generator, a webpage generator, a wallpaper changer, a screensaver...

You can check the results in the [gallery](http://sebsauvage.net/galerie/?dir=webGobbler).

Requirements
============

* Python3 (developed with Python3.13)
* Pillow ([Python Imaging Library](https://pypi.org/project/pillow/))


Usage
=====

* Run in GUI mode: `python webgobbler.py`
* Display command-line options with: `python webgobbler.py --help`
* Other example are available in command-line help screens.


Note
====

This code is 13 years old, rather ugly and really *REALLY* deserves refactoring. Please be indulgent. Also note that due to website changes, only the Yahoo crawler works (DeviantArt, AskJeeves, Flickr and Google crawler do not work anymore).


Licence
=======

------------------------------------------------------------------------------

This program is distributed under the OSI-certified zlib/libpng license.
http://www.opensource.org/licenses/zlib-license.php

This software is provided 'as-is', without any express or implied warranty.
In no event will the authors be held liable for any damages arising from
the use of this software.

Permission is granted to anyone to use this software for any purpose,
including commercial applications, and to alter it and redistribute it freely,
subject to the following restrictions:

    1. The origin of this software must not be misrepresented; you must not
       claim that you wrote the original software. If you use this software
       in a product, an acknowledgment in the product documentation would be
       appreciated but is not required.

    2. Altered source versions must be plainly marked as such, and must not
       be misrepresented as being the original software.

    3. This notice may not be removed or altered from any source distribution.

------------------------------------------------------------------------------
