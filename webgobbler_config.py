#!/usr/bin/python
# -*- coding: iso-8859-1 -*-
'''
webGobbler configuration GUI 1.2.8


Note: this configuration GUI is still kept outside the main webgobbler code
      so that webGobbler core is not polluted with Tkinter/GUI stuff.

'''

try:
    import Pmw
except ImportError:
    raise ImportError("The Pmw (Python Megawidgets) module is required for the webGobbler configuration GUI. See http://pmw.sourceforge.net/")

import os, os.path
import hashlib

import tkinter
import tkinter.font
import tkinter.filedialog
import tkinter.simpledialog

import io, base64
from utils.freeze_imports import Image, ImageTk
import webgobbler   # We import the webGobbler module.
from assets.icons import get_icons
from assets.docs import ABOUTMESSAGE

def main():
    root = tkinter.Tk()             # Initialize Tkinter
    root.withdraw()                 # Hide the main root window
    Pmw.initialise(root)            # Initialize Pmw
    wgconfig = wg_confGUI(root)     # Build the GUI.
    root.wait_window(wgconfig.top)  # Wait for configuration window to close.

# FIXME: allow to choose where to save to/load from ? (combo with .ini file/registry ?)

class wg_confGUI(tkinter.Toplevel):  # FIXME: Should I derive from Frame so that I can be included ?
    '''
    Example:
        root = Tkinter.Tk()             # Initialize Tkinter
        root.withdraw()                 # Hide the main root window
        Pmw.initialise(root)            # Initialize Pmw
        wgconfig = wg_confGUI(root)     # Build the GUI.
        root.wait_window(wgconfig.top)  # Wait for configuration window to close.

    Example 2:
        import webgobbler_config
        wgconfig = webgobbler_config.wg_confGUI(None)
        wgconfig.focus_set()
        self._parent.wait_window(wgconfig.top)  # Wait for window to close.
    '''
    def __init__(self,parent):
        tkinter.Toplevel.__init__(self, parent)
        self.top = self
        # the following dictionnary will keep a refenrece to all the widgets/variables
        # we need to read/write information from/to.
        self._widgets = {}  # References to tkinter widgets and tkinter variables
        self._widgets_group = {}  # We group some widgets to enable/disable them by group.
        self.config = None  #  The webGobbler configuration (an wg.applicationConfig object)
        self.configSource = None  # Configuration source ('registry','inifile' or 'default')
        self.configChanged = False   # Tells if the user has changed the configuration

        self._setICONS()
        self._initializeGUI()
        self.loadConfig()   # Automatically load current webGobbler configuration into the GUI.
        if not self.configSource in ('registry','inifile'):
            Pmw.MessageDialog(self.top,title = 'Configuration loaded',message_text="Configuration could not be read from registry or .ini file.\nConfiguration was loaded with default values.",iconpos='w',icon_bitmap='warning')

    def _setICONS(self):
        ''' Here are all the icons used by the GUI '''
        # Yeah... I know it's bad to have base64 data in code. Sue me.
        self._ICONS = get_icons(master=self.top)

    def quit(self, event=None):
        pass

    def loadConfig(self,appConfig=None):
        ''' Read webGobbler configuration from registry or .INI file.
            If the registry is not available, the .ini file will be read.
            If the .ini file is not available, the default configuration will be used.
        '''
        if appConfig != None:
            raise NotImplementedError
        self.config = webgobbler.applicationConfig()  # Get a new applicationConfig object.
        self.configSource = None
        # First, we try to read configuration from registry.
        try:
            self.config.loadFromRegistryCurrentUser()
            self.configSource = "registry"
        except ImportError:
            pass
        except WindowsError:
            pass

        if self.configSource == None:
            # We are probably not under Windows, or the registry could not be read.
            # We try to read the .ini file in user's home directory:
            try:
                self.config.loadFromFileInUserHomedir()
                self.configSource = "inifile"
            except:
                self.configSource = 'default'

        # Then we push the configuration to the GUI so that the user can change it.
        self.configToGUI(self.config)

    def saveConfig(self):
        ''' Save configuration from the GUI to registry or .ini file.'''
        # Get all data from the GUI back into the applicationConfig object:
        self.GUItoConfig(self.config)

        # We first try to save config from where we got it.
        configSaved = False
        if self.configSource == 'registry':
            try:
                self.config.saveToRegistryCurrentUser()
                configSaved = True
            except ImportError:
                pass
            except WindowsError:
                pass
        elif self.configSource == 'inifile':
            try:
                self.config.saveToFileInUserHomedir()
                configSaved = True
            except IOError:
                pass

        # If configuration was not properly saved, try to save by another mean:
        if not configSaved:
            self.configSource == 'default'
            try:  # Try registry first.
                self.config.saveToRegistryCurrentUser()
                configSaved = True
                self.configSource = "registry"
            except ImportError:
                pass
            except WindowsError:
                pass
        if not configSaved:  # If save into registry failed, try to .ini file.
            self.configSource = 'default'
            try:
                self.config.saveToFileInUserHomedir()
                configSaved = True
                self.configSource = "inifile"
            except ImportError:
                pass
            except WindowsError:
                pass

        if not configSaved:
            self.configSource = 'default'
        else:
            self.configChanged = True

    def defaultValues(self):
        ''' Set configuration back to the default values.
            Note that this does not alter configuration saved in registry
            or .ini file until you press the 'Save' button.
        '''
        # Get the default values for webGobbler configuration:
        self.config = webgobbler.applicationConfig()
        self.configSource = None
        # Then we push the configuration to the GUI so that the user can change it.
        self.configToGUI(self.config)

    def _initializeGUI(self):
        ''' This method creates all the GUI widgets. '''
        # GUI programming sucks.



        boldFont = tkinter.font.Font(weight='bold',size=-11)  # A simple bold font.
        smallFont = tkinter.font.Font(size=-9)  # A smaller font (for blacklists)

        defaultPadding = 5   # Padding around some widgets.

        # FIXME: All expand and sticky have to be set for proper GUI resizing.

        # FIXME: correct tab order.

        # FIXME: Put Icons on every option.

        # ----------------------------------------------------------------------
        # Main frame:
        # row 0 - Note book (tabs)
        # row 1 - Help area
        # row 2 - Buttons (Save/Default/Cancel)

        # row 0 - Note book (tabs)
        nbook = Pmw.NoteBook(self.top)
        self._widgets['main_notebook'] = nbook
        nbook.grid(column=0,row=0,sticky='NSWE')
        for name in ("Image generation","Storage","Network","Blacklists","About"):
            nbook.add(name)

        # row 1 - Help area
        #helpFrame = Tkinter.Frame(self.top)
        #helpFrame.grid(column=0,row=1,sticky='NSWE')

        # row 2 - Buttons (Save/Default/Cancel)
        buttonsframe = tkinter.Frame(self.top,borderwidth=5 )
        buttonsframe.grid(column=0,row=2,sticky='NSWE')


        # ----------------------------------------------------------------------
        # Help area:
#        helpArea = Pmw.Group(helpFrame, tag_text='Help',tag_font=boldFont)
#        helpArea.pack(expand=1,fill='both')
#        message = 'This area will contain the help text which describes the control which is in focus.'
#        helpText = Tkinter.Text(helpArea.interior(), bg='#d4d0c8', height=4, relief='flat', wrap='word', takefocus=0, exportselection=0)
#        helpText.pack(expand=1,fill='both')
#        helpText.insert('0.0',message)  # Insert text in area.
#        helpText.config(state='disabled')  # Make area read-only.

        # ----------------------------------------------------------------------
        # Buttons (Save/Default/Cancel):
        # FIXME: Use Pmw.ButtonBox() instead ?
        tkinter.Button(buttonsframe,text="Save configuration",command=self.saveClick).grid(column=0,row=0)
        tkinter.Button(buttonsframe,text="Load configuration",command=self.loadClick).grid(column=1,row=0)
        tkinter.Button(buttonsframe,text="Get default values",command=self.defaultClick).grid(column=2,row=0)
        tkinter.Button(buttonsframe,text="Close",command=self.exitClick).grid(column=3,row=0)

        # ======================================================================
        # Note book tab "Image generation"
        # Cells:
        #     00000      "If you're unsure of the options to change, you can leave the default values."
        #     11111      Image resolution
        #     22222      Frequency
        #     33333      Keyword image search
        #     44 55      44=Output options,  55=Variante
        #     44 66      66=Debug

        # Cell 0 - "If you're unsure of the options to change, you can leave the default values."
        tkinter.Label(nbook.page(0),text="If you're unsure of the options to change, you can leave the default values.",
                font=boldFont).grid(column=0,row=0,columnspan=2)

        # Cell 1 - Image resolution
        resolutionFrame = Pmw.Group(nbook.page(0), tag_text='Image resolution')
        resolutionFrame.grid(column=0,row=1,columnspan=2,sticky='NSEW',padx=defaultPadding,pady=defaultPadding,ipadx=defaultPadding,ipady=defaultPadding)

        # Cell 2 - Frequency
        timeFrame = Pmw.Group(nbook.page(0), tag_text='Frequency')
        timeFrame.grid(column=0,row=2,columnspan=2,sticky='NSEW',padx=defaultPadding,pady=defaultPadding,ipadx=defaultPadding,ipady=defaultPadding)

        # Cell 3 - Keyword image search
        keywordFrame = Pmw.Group(nbook.page(0), tag_text='Keyword image search')
        keywordFrame.grid(column=0,row=3,columnspan=2,sticky='NSEW',padx=defaultPadding,pady=defaultPadding,ipadx=defaultPadding,ipady=defaultPadding)

        # Cell 4 - Output options
        optionsGroup = Pmw.Group(nbook.page(0), tag_text='Output options')
        optionsGroup.grid(column=0,row=4,rowspan=2,sticky='NSEW',padx=defaultPadding,pady=defaultPadding,ipadx=defaultPadding,ipady=defaultPadding)

        # Cell 5 - Variante
        varianteGroup = Pmw.Group(nbook.page(0), tag_text='Variante')
        varianteGroup.grid(column=1,row=4,sticky='NSEW',padx=defaultPadding,pady=defaultPadding,ipadx=defaultPadding,ipady=defaultPadding)

        # Cell 6 - Debug
        debugGroup = Pmw.Group(nbook.page(0), tag_text='Debug')
        debugGroup.grid(column=1,row=5,sticky='NSEW',padx=defaultPadding,pady=defaultPadding,ipadx=defaultPadding,ipady=defaultPadding)

        # ----------------------------------------------------------------------
        # Cell 1 content: Image resolution:
        #    II  FFFFFFF    FFF = frame containing the cursors
        #    II  LLLLLLL    LLL = "Note: Resolution will be ignored by the Windows screensaver..."
        #                   III = icon
        #
        tkinter.Label(resolutionFrame.interior(),image=self._ICONS['imagesize'],width=80).grid(column=0,row=0,rowspan=2,sticky='w')
        tempFrame = tkinter.Frame(resolutionFrame.interior())
        tempFrame.grid(column=1,row=0)
        tkinter.Label(resolutionFrame.interior(),text="Note: Resolution will be ignored by the Windows screensaver.\n(It will automatically detect screen resolution.)",justify='left').grid(column=1,row=1)

        # The frame FFFFFFF containing the cursors:
        self._widgets['assembler.sizex'] = Pmw.Counter(tempFrame,datatype={'counter':'numeric'},entryfield_value='1024',entry_width=6)
        self._widgets['assembler.sizex'].grid(column=0,row=0)
        tkinter.Label(tempFrame,text=" by ").grid(column=1,row=0)
        self._widgets['assembler.sizey'] = Pmw.Counter(tempFrame,datatype={'counter':'numeric'},entryfield_value='768',entry_width=6)
        self._widgets['assembler.sizey'].grid(column=2,row=0)
        tkinter.Label(tempFrame,text="Width").grid(column=0,row=1)
        tkinter.Label(tempFrame,text="Height").grid(column=2,row=1)

        # ----------------------------------------------------------------------
        # Cell 2 content : Frequency
        tkinter.Label(timeFrame.interior(),text="Evolve current image every").grid(column=1,row=0,sticky='e')
        # FIXME: How do I right justify this ?  (label_justify does not exist !)
        self._widgets['program.every'] = Pmw.Counter(timeFrame.interior(),datatype={'counter':'numeric'},entryfield_value='60',entry_width=4)
        self._widgets['program.every'].grid(column=2,row=0)
        tkinter.Label(timeFrame.interior(),text="seconds").grid(column=3,row=0,sticky='w')

        tkinter.Label(timeFrame.interior(),text="by adding").grid(column=1,row=1,sticky='e')
        self._widgets['assembler.superpose.nbimages'] = Pmw.Counter(timeFrame.interior(),datatype={'counter':'numeric'},entryfield_value='10',entry_width=4)
        self._widgets['assembler.superpose.nbimages'].grid(column=2,row=1)
        tkinter.Label(timeFrame.interior(),text="random images from the internet").grid(column=3,row=1,sticky='w')

        tkinter.Label(timeFrame.interior(),image=self._ICONS['frequency'],width=80).grid(column=0,row=0,rowspan=3,sticky='w')

        # ----------------------------------------------------------------------
        # Cell 3 content : Keyword image search
        v = tkinter.IntVar(); self._widgets['collector.keywords.enabled'] = v
        tkinter.Radiobutton(keywordFrame.interior(),variable=v,value=0,command=self._enablerDisabler,text="Use totally random images (default)").grid(column=0,row=0,sticky='W')
        tkinter.Radiobutton(keywordFrame.interior(),variable=v,value=1,command=self._enablerDisabler,text="Search images using the following keywords:").grid(column=0,row=1,sticky='W')
        v.set(0)

        s = tkinter.StringVar(); self._widgets['collector.keywords.keywords'] = s
        widget = tkinter.Entry(keywordFrame.interior(),width=40,textvariable=s)
        widget.grid(column=1,row=1,sticky='EW')
        self._widgets_group['collector.keywords.keywords'] = [widget]  # Store reference to this widget so that we can enable/disable it later.

        # FIXME: empty image pool if keyword search enabled (but not if keyword search disabled)

        # ----------------------------------------------------------------------
        # Cell 4 content: Output options
        v = tkinter.IntVar(); self._widgets['assembler.superpose.randomrotation']=v
        self._widgets['RotationCheckbutton'] = tkinter.Checkbutton(optionsGroup.interior(),variable=v,image=self._ICONS['rotation'],command=self._imageChanger)
        self._widgets['RotationCheckbutton'].grid(column=0,row=0,sticky='W')
        tkinter.Label(optionsGroup.interior(),text="Random rotation").grid(column=1,row=0,sticky='W')

        v = tkinter.IntVar(); self._widgets['assembler.mirror']=v
        self._widgets['MirrorCheckbutton'] = tkinter.Checkbutton(optionsGroup.interior(),variable=v,image=self._ICONS['mirror'],command=self._imageChanger)
        self._widgets['MirrorCheckbutton'].grid(column=0,row=1,sticky='W')
        tkinter.Label(optionsGroup.interior(),text="Mirror (left-right)").grid(column=1,row=1,sticky='W')

        v = tkinter.IntVar(); self._widgets['assembler.invert']=v
        self._widgets['InvertCheckbutton'] = tkinter.Checkbutton(optionsGroup.interior(),variable=v,image=self._ICONS['invert'],command=self._imageChanger)
        self._widgets['InvertCheckbutton'].grid(column=0,row=2,sticky='W')
        tkinter.Label(optionsGroup.interior(),text="Invert (negative)").grid(column=1,row=2,sticky='W')

        v = tkinter.IntVar(); self._widgets['assembler.emboss']=v
        self._widgets['EmbossCheckbutton'] = tkinter.Checkbutton(optionsGroup.interior(),variable=v,image=self._ICONS['emboss'],command=self._imageChanger)
        self._widgets['EmbossCheckbutton'].grid(column=0,row=3,sticky='W')
        tkinter.Label(optionsGroup.interior(),text="Emboss").grid(column=1,row=3,sticky='W')

        v = tkinter.IntVar(); self._widgets['assembler.resuperpose']=v
        self._widgets['ResuperposeCheckbutton'] = tkinter.Checkbutton(optionsGroup.interior(),variable=v,image=self._ICONS['resuperpose'],command=self._imageChanger)
        self._widgets['ResuperposeCheckbutton'].grid(column=0,row=4,sticky='W')
        tkinter.Label(optionsGroup.interior(),text="Re-superpose").grid(column=1,row=4,sticky='W')

        self._widgets['assembler.superpose.bordersmooth'] = Pmw.Counter(optionsGroup.interior(),datatype={'counter':'numeric'},entry_width=4,entryfield_value=30)
        self._widgets['assembler.superpose.bordersmooth'].grid(column=0,row=5,sticky='W')
        tkinter.Label(optionsGroup.interior(),text="pixels border smooth\n(0=no smooth)",anchor='w').grid(column=1,row=5,sticky='NW')

        tkinter.Label(optionsGroup.interior(),text="scale before superposing\n(1=no scale)",anchor='w').grid(column=1,row=6,sticky='NW')
        s = tkinter.StringVar(); self._widgets['assembler.superpose.scale'] = s
        tkinter.Entry(optionsGroup.interior(),width=6,textvariable=s).grid(column=0,row=6,sticky='EW')

        # ----------------------------------------------------------------------
        # Cell 5 content: Variante
        v = tkinter.IntVar(); self._widgets['assembler.superpose.variante'] = v
        tkinter.Radiobutton(varianteGroup.interior(),variable=v,value=0,command=self._enablerDisabler,image=self._ICONS['variante0']).grid(column=0,row=0,sticky='W')
        tkinter.Radiobutton(varianteGroup.interior(),variable=v,value=1,command=self._enablerDisabler,image=self._ICONS['variante1']).grid(column=0,row=1,sticky='W')
        v.set(0)
        tkinter.Label(varianteGroup.interior(),text="0 (Superpose+Equalize)   [Recommended]").grid(column=1,row=0,sticky='w')
        tkinter.Label(varianteGroup.interior(),text="1 (Darken+Superpose+Autocontrast)").grid(column=1,row=1,sticky='w')

        # ----------------------------------------------------------------------
        # Cell 6 content: Debug
        tempFrame= tkinter.Frame(debugGroup.interior())
        tempFrame.grid(column=0,row=0,sticky='W')
        v = tkinter.IntVar(); self._widgets['debug']=v
        tkinter.Checkbutton(tempFrame,image=self._ICONS['debug'],variable=v).grid(column=0,row=0,sticky='W')
        tkinter.Label(tempFrame,text="Debug mode").grid(column=1,row=0,sticky='W')
        tkinter.Label(debugGroup.interior(),text="(Debug mode will create webGobbler.log in the installation directory.)").grid(column=0,row=1,columnspan=2,sticky='w')

        # ======================================================================
        # Note book tab "Storage"
        # row 0 - Downloaded images
        # row 1 - Working directory
        downloadedImagesGroup = Pmw.Group(nbook.page(1), tag_text='Downloaded images')
        downloadedImagesGroup.grid(column=0,row=0,sticky='NSEW',padx=defaultPadding,pady=defaultPadding,ipadx=defaultPadding,ipady=defaultPadding)
        workingDirGroup = Pmw.Group(nbook.page(1), tag_text='Working directory')
        workingDirGroup.grid(column=0,row=1,sticky='NSEW',padx=defaultPadding,pady=defaultPadding,ipadx=defaultPadding,ipady=defaultPadding)

        # ----------------------------------------------------------------------
        # row 0 content: Downloaded images
        tkinter.Label(downloadedImagesGroup.interior(),image=self._ICONS['storage'],width=80).grid(column=0,row=0,rowspan=2,sticky='w')

        tkinter.Label(downloadedImagesGroup.interior(),text="Store downloaded images in :").grid(column=1,row=0,columnspan=2,sticky='W')
        s = tkinter.StringVar(); self._widgets['pool.imagepooldirectory'] = s
        tkinter.Entry(downloadedImagesGroup.interior(),width=50,textvariable=s).grid(column=1,row=1,sticky='W')
        tkinter.Button(downloadedImagesGroup.interior(),text="Browse...",command=self.chooseImagepoolDirClick).grid(column=2,row=1,sticky='W')
        tkinter.Label(downloadedImagesGroup.interior(),text="(Directory will be created if it does not exist.)\n").grid(column=1,row=2,columnspan=2,sticky='W')
        tempFrame = tkinter.Frame(downloadedImagesGroup.interior())
        tempFrame.grid(column=1,row=3,columnspan=2,sticky='W')
        tkinter.Label(tempFrame,text="Keep").grid(column=0,row=0)

        self._widgets['pool.nbimages'] = Pmw.Counter(tempFrame,datatype={'counter':'numeric'},entry_width=4,entryfield_value=50)
        self._widgets['pool.nbimages'].grid(column=1,row=0)
        tkinter.Label(tempFrame,text="images in this directory.  (Recommended: 50)").grid(column=2,row=0)

        # ----------------------------------------------------------------------
        # row 1 content: Working directory
        tkinter.Label(workingDirGroup.interior(),image=self._ICONS['workingdir'],width=80).grid(column=0,row=0,rowspan=2,sticky='nw')

        tkinter.Label(workingDirGroup.interior(),text="Store working files in :").grid(column=1,row=0,columnspan=2,sticky='W')
        s = tkinter.StringVar() ; self._widgets['persistencedirectory'] = s
        tkinter.Entry(workingDirGroup.interior(),width=50,textvariable=s).grid(column=1,row=1,sticky='W')
        tkinter.Button(workingDirGroup.interior(),text="Browse...",command=self.chooseWorkingDirClick).grid(column=2,row=1,sticky='W')

        # ======================================================================
        # Note book tab "Network":
        # in the connectionGroup:
        #       ii  00000
        #       ii  11111
        #       ii  22222
        # row 0 - radiobutton "Do not connect to internet"
        # row 1 - radiobutton "Use the internet"
        # row 2 - group "Internet connexion parameters"
        # iii - image.

        connectionGroup = Pmw.Group(nbook.page(2), tag_text='Connection')
        connectionGroup.grid(column=0,row=0,sticky='NSEW',padx=defaultPadding,pady=defaultPadding)

        self._widgets['ConnectionImage'] = tkinter.Label(connectionGroup.interior(),image=self._ICONS['connected'])
        self._widgets['ConnectionImage'].grid(column=0,row=0,rowspan=5,sticky='n')

        # ----------------------------------------------------------------------
        # row 0 content: radiobutton "Do not connect to internet"
        v = tkinter.IntVar() ; self._widgets['collector.localonly'] = v
        tkinter.Radiobutton(connectionGroup.interior(),variable=v,value=1,command=self._enablerDisabler,text="Do not connect to internet: use images found on local disk").grid(column=1,row=0,columnspan=2,sticky='W')
        # Choose directory

        s = tkinter.StringVar() ; self._widgets['collector.localonly.startdir'] = s
        localStartDirEntry = tkinter.Entry(connectionGroup.interior(),width=30,textvariable=s)
        localStartDirEntry.grid(column=2,row=1,sticky='EW')
        chooseLocalStartDirButton = tkinter.Button(connectionGroup.interior(),text="Choose diretory...",command=self.chooseLocalStartDirectory)
        chooseLocalStartDirButton.grid(column=3,row=1,sticky='W')

        # ----------------------------------------------------------------------
        # row 1 content: radiobutton "Use the internet"
        tkinter.Radiobutton(connectionGroup.interior(),variable=v,value=0,command=self._enablerDisabler,text="Use the internet :").grid(column=1,row=2,columnspan=3,sticky='W')
        v.set(0)
        # ----------------------------------------------------------------------
        # row 2 content: group "Internet connexion parameters"
        #     SSSS GGGG     SSSS = a space (Canvas)
        #                   GGGG = the "Internet connexion parameter" group.

        tkinter.Canvas(connectionGroup.interior(),width=20,height=10).grid(column=1,row=4)  # Just a spacer
        connectionParamGroup = Pmw.Group(connectionGroup.interior(), tag_text='Internet connection parameters')
        connectionParamGroup.grid(column=2,row=4,columnspan=3,sticky='W',padx=defaultPadding,pady=defaultPadding)

        # "Internet connexion parameter" group content:
        v = tkinter.IntVar(); self._widgets['network.http.proxy.enabled'] = v
        rbDirectConnection = tkinter.Radiobutton(connectionParamGroup.interior(),variable=v,value=0,text="Direction connection",command=self._enablerDisabler)
        rbDirectConnection.grid(column=0,row=0,sticky='W')
        rbUseProxy = tkinter.Radiobutton(connectionParamGroup.interior(),variable=v,value=1,text="Use HTTP Proxy :",command=self._enablerDisabler)
        rbUseProxy.grid(column=0,row=1,sticky='NW')
        v.set(0)
        proxyParamsFrame = tkinter.Frame(connectionParamGroup.interior())
        proxyParamsFrame.grid(column=1,row=1)
        self._widgets['proxyParamsFrame'] = proxyParamsFrame

        # Proxy parameters:
        tkinter.Label(proxyParamsFrame,text="Proxy address").grid(column=0,row=0,sticky='W')
        tkinter.Label(proxyParamsFrame,text="Port").grid(column=1,row=0,sticky='W')

        s = tkinter.StringVar(); self._widgets['network.http.proxy.address'] = s
        proxyAddressEntry = tkinter.Entry(proxyParamsFrame,width=30,textvariable=s)
        proxyAddressEntry.grid(column=0,row=1,sticky='EW')

        s = tkinter.StringVar(); self._widgets['network.http.proxy.port'] = s
        proxyPortEntry = tkinter.Entry(proxyParamsFrame,width=6,textvariable=s)
        proxyPortEntry.grid(column=1,row=1,sticky='EW')

        v = tkinter.IntVar(); self._widgets['network.http.proxy.auth.enabled'] = v
        proxyUseAuthCheckbox = tkinter.Checkbutton(proxyParamsFrame,text="Proxy requires authentication",variable=v,command=self._enablerDisabler)
        proxyUseAuthCheckbox.grid(column=0,row=2,columnspan=2,sticky='W')

        proxyAuthFrame = tkinter.Frame(proxyParamsFrame,width=50)
        self._widgets['proxyAuthFrame'] = proxyAuthFrame
        #proxyAuthFrame.grid_propagate(0)
        proxyAuthFrame.grid(column=0,row=3,columnspan=2,stick='E')

        # Proxy authentication frame:
        tkinter.Canvas(proxyAuthFrame,width=20,height=10).grid(column=0,row=0,rowspan=3)  # Just a spacer
        tkinter.Label(proxyAuthFrame,text="Login :").grid(column=1,row=1,sticky='W')
        s = tkinter.StringVar(); self._widgets['network.http.proxy.auth.login'] = s
        loginEntry = tkinter.Entry(proxyAuthFrame,width=15,textvariable=s)
        loginEntry.grid(column=2,row=1,sticky='EW')
        tkinter.Label(proxyAuthFrame,text="Password :").grid(column=1,row=2,sticky='W')
        s = tkinter.StringVar(); self._widgets['network.http.proxy.auth.password'] = s
        passwordEntry = tkinter.Entry(proxyAuthFrame,width=15,textvariable=s,show='*')
        passwordEntry.grid(column=2,row=2,sticky='EW')
        tkinter.Label(proxyAuthFrame,text="(WARNING: Password is stored in registry)").grid(column=2,row=3)

        # List of widgets to disable according to selected options:
        self._widgets_group['network.http.proxy.auth.enabled'] = ( loginEntry,passwordEntry )
        self._widgets_group['network.http.proxy.enabled']      = ( loginEntry,passwordEntry,proxyUseAuthCheckbox,proxyAddressEntry,proxyPortEntry)
        self._widgets_group['collector.localonly']             = ( loginEntry,passwordEntry,proxyUseAuthCheckbox,proxyAddressEntry,proxyPortEntry,rbDirectConnection,rbUseProxy)
        self._widgets_group['NOT collector.localonly']         = ( localStartDirEntry, chooseLocalStartDirButton)

        # ======================================================================
        # Note book tab "Blacklists"
        # column 0 - "Blacklisted images"
        # column 1 - "Blacklisted URLs"
        blacklistedImagesGroup = Pmw.Group(nbook.page(3), tag_text='Blacklisted images')
        blacklistedImagesGroup.grid(column=0,row=0,sticky='NS')
        blacklistedURLsGroup = Pmw.Group(nbook.page(3), tag_text='Blacklisted URLs')
        blacklistedURLsGroup.grid(column=1,row=0,sticky='NS')

        # Blacklisted images:
        self._widgets['blacklist.imagesha1'] = Pmw.ScrolledText(blacklistedImagesGroup.interior(),text_width=42,text_height=30,text_wrap='none',vscrollmode='static',text_font=smallFont)
        self._widgets['blacklist.imagesha1'].grid(column=0,row=0)
        tkinter.Button(blacklistedImagesGroup.interior(),text="Add image...",command=self.addImageBlacklist).grid(column=0,row=1)

        # Blacklisted URLs
        self._widgets['blacklist.url'] = Pmw.ScrolledText(blacklistedURLsGroup.interior(),text_width=42,text_height=30,text_wrap='none',vscrollmode='static',text_font=smallFont)
        self._widgets['blacklist.url'].grid(column=0,row=0)


        # ======================================================================
        # Note book tab "About"
        aboutNbook = Pmw.NoteBook(nbook.page(4))
        self._widgets['about_notebook'] = aboutNbook
        aboutNbook.grid(column=0,row=0)
        for name in ("About","License","Disclaimer"):
            aboutNbook.add(name)

        # "About" tab content:
        aboutMessage = ABOUTMESSAGE % webgobbler.VERSION
        aboutText = Pmw.ScrolledText(aboutNbook.page(0),text_width=70,text_height=30,text_bg='#d4d0c8', text_relief='flat', text_takefocus=0, text_exportselection=0 )
        aboutText.grid(column=0,row=0)
        aboutText.insert('0.0',aboutMessage)
        aboutText.image_create('0.0', image=self._ICONS['sebsauvage.net'])
        aboutText.configure(text_state='disabled')  # Text in read-only


        # "License" tab content:
        licenseText = Pmw.ScrolledText(aboutNbook.page(1),text_width=70,text_height=30,text_bg='#d4d0c8', text_relief='flat', text_takefocus=0, text_exportselection=0 )
        licenseText.grid(column=0,row=0)
        licenseText.insert('0.0',webgobbler.LICENSE)
        licenseText.configure(text_state='disabled')  # Text in read-only

        # "Disclaimer" tab content:
        disclaimerText = Pmw.ScrolledText(aboutNbook.page(2),text_width=70,text_height=30,vscrollmode='static',text_bg='#d4d0c8', text_relief='flat', text_takefocus=0, text_exportselection=0 )
        disclaimerText.grid(column=0,row=0)
        disclaimerText.insert('0.0',webgobbler.DISCLAIMER)
        disclaimerText.configure(text_state='disabled')  # Text in read-only

        aboutNbook.setnaturalsize()

        nbook.setnaturalsize()  # Auto-size the notebook to fit all its pages size.

        # FIXME: force types in widgets (numeric, etc.)

    def configToGUI(self,c):
        ''' Reads an applicationConfig object of webGobbler and pushes all the value to the GUI. '''
        # For the "Image generation" tab:
        self._widgets['assembler.sizex'].setentry( c['assembler.sizex'] )
        self._widgets['assembler.sizey'].setentry( c['assembler.sizey'] )
        self._widgets['program.every'].setentry( c['program.every'] )
        self._widgets['assembler.superpose.nbimages'].setentry( c['assembler.superpose.nbimages'] )
        if c['assembler.superpose.randomrotation']: self._widgets['assembler.superpose.randomrotation'].set(1)
        else:                                       self._widgets['assembler.superpose.randomrotation'].set(0)
        if c['assembler.mirror']: self._widgets['assembler.mirror'].set(1)
        else:                     self._widgets['assembler.mirror'].set(0)
        if c['assembler.invert']: self._widgets['assembler.invert'].set(1)
        else:                     self._widgets['assembler.invert'].set(0)
        if c['assembler.emboss']: self._widgets['assembler.emboss'].set(1)
        else:                     self._widgets['assembler.emboss'].set(0)
        if c['assembler.resuperpose']: self._widgets['assembler.resuperpose'].set(1)
        else:                          self._widgets['assembler.resuperpose'].set(0)

        self._widgets['assembler.superpose.bordersmooth'].setentry( c['assembler.superpose.bordersmooth'] )
        self._widgets['assembler.superpose.scale'].set( c['assembler.superpose.scale'] )

        self._widgets['assembler.superpose.variante'].set(c['assembler.superpose.variante'])
        if c['debug']: self._widgets['debug'].set(1)
        else:          self._widgets['debug'].set(0)

        self._widgets['collector.keywords.enabled'].set( c['collector.keywords.enabled'] )
        self._widgets['collector.keywords.keywords'].set( c['collector.keywords.keywords'] )

        # For the "Storage" tab:
        self._widgets['pool.imagepooldirectory'].set( c['pool.imagepooldirectory'] )
        self._widgets['persistencedirectory'].set( c['persistencedirectory'] )
        self._widgets['pool.nbimages'].setentry(c['pool.nbimages'])  # Why the hell the Pmw.Counter().setentry() method is not documented ?


        # For the "Network" tab:
        if c['collector.localonly']: self._widgets['collector.localonly'].set(1)
        else:                        self._widgets['collector.localonly'].set(0)

        self._widgets['collector.localonly.startdir'].set( c['collector.localonly.startdir'] )

        if c['network.http.proxy.enabled']: self._widgets['network.http.proxy.enabled'].set(1)
        else:                        self._widgets['network.http.proxy.enabled'].set(0)
        self._widgets['network.http.proxy.address'].set(c['network.http.proxy.address'])
        self._widgets['network.http.proxy.port'].set(c['network.http.proxy.port'])
        if c['network.http.proxy.auth.enabled']: self._widgets['network.http.proxy.auth.enabled'].set(1)
        else:                                     self._widgets['network.http.proxy.auth.enabled'].set(0)
        self._widgets['network.http.proxy.auth.login'].set(c['network.http.proxy.auth.login'])
        self._widgets['network.http.proxy.auth.password'].set(c['network.http.proxy.auth.password'])

        # For the "Blacklists" tab
        self._widgets['blacklist.imagesha1'].delete('1.0', 'end')
        self._widgets['blacklist.imagesha1'].insert('0.0','\n'.join(list(c['blacklist.imagesha1'].keys())))

        self._widgets['blacklist.url'].delete('1.0', 'end')
        self._widgets['blacklist.url'].insert('0.0','\n'.join(c['blacklist.url']))

        self._enablerDisabler()  # Enabled/disable widgets according to values.
        self._imageChanger()     # Display proper icons


    def GUItoConfig(self,c):
        ''' Commit all GUI parameters to the config object (c must be an webgobbler.applicationConfig object)
            c is modified in-place.
        '''
        # From the "Image generation" tab:
        c['assembler.sizex'] = int(self._widgets['assembler.sizex'].get())
        c['assembler.sizey'] = int(self._widgets['assembler.sizey'].get())
        c['program.every'] = int(self._widgets['program.every'].get())
        c['assembler.superpose.nbimages'] = int(self._widgets['assembler.superpose.nbimages'].get())
        if self._widgets['assembler.superpose.randomrotation'].get()==0: c['assembler.superpose.randomrotation']=False
        else:                                                            c['assembler.superpose.randomrotation']=True
        if self._widgets['assembler.mirror'].get()==0: c['assembler.mirror']=False
        else:                                          c['assembler.mirror']=True
        if self._widgets['assembler.invert'].get()==0: c['assembler.invert']=False
        else:                                          c['assembler.invert']=True
        if self._widgets['assembler.emboss'].get()==0: c['assembler.emboss']=False
        else:                                          c['assembler.emboss']=True
        c['assembler.superpose.variante'] = int(self._widgets['assembler.superpose.variante'].get())
        if self._widgets['assembler.resuperpose'].get()==0: c['assembler.resuperpose']=False
        else:                                               c['assembler.resuperpose']=True

        c['assembler.superpose.bordersmooth'] = int(self._widgets['assembler.superpose.bordersmooth'].get())
        c['assembler.superpose.scale'] = float(self._widgets['assembler.superpose.scale'].get())

        if self._widgets['collector.keywords.enabled'].get()==0: c['collector.keywords.enabled']=False
        else:                                                    c['collector.keywords.enabled']=True
        c['collector.keywords.keywords'] = str(self._widgets['collector.keywords.keywords'].get())

        if self._widgets['debug'].get()==0: c['debug']=False
        else:                               c['debug']=True

        # From the "Storage" tab:
        c['pool.imagepooldirectory'] = str(self._widgets['pool.imagepooldirectory'].get())
        c['persistencedirectory'] = str(self._widgets['persistencedirectory'].get())
        c['pool.nbimages'] = int(self._widgets['pool.nbimages'].get() )

        # For the "Network" tab:
        if self._widgets['collector.localonly'].get()==0: c['collector.localonly']=False
        else:                                             c['collector.localonly']=True
        c['collector.localonly.startdir'] = self._widgets['collector.localonly.startdir'].get()

        if self._widgets['network.http.proxy.enabled'].get()==0: c['network.http.proxy.enabled']=False
        else:                                                    c['network.http.proxy.enabled']=True
        c['network.http.proxy.address'] = str(self._widgets['network.http.proxy.address'].get())
        c['network.http.proxy.port'] = int(self._widgets['network.http.proxy.port'].get())
        if self._widgets['network.http.proxy.auth.enabled'].get()==0: c['network.http.proxy.auth.enabled']=False
        else:                                                         c['network.http.proxy.auth.enabled']=True
        c['network.http.proxy.auth.login'] = str(self._widgets['network.http.proxy.auth.login'].get())
        c['network.http.proxy.auth.password'] = str(self._widgets['network.http.proxy.auth.password'].get())

        # For the "Blacklists" tab
        c['blacklist.imagesha1'] = dict([ (i.strip(),0) for i in self._widgets['blacklist.imagesha1'].getvalue().strip().split('\n') if len(i.strip())!=0])
        c['blacklist.url'] = [i.strip() for i in self._widgets['blacklist.url'].getvalue().strip().split('\n') if len(i.strip())!=0]


    # ##########################################################################
    # GUI elements events handlers:

    def _enablerDisabler(self):
        ''' This handler will enable/disable widgets according to the value of
            some of these widgets.
        '''
        # First enable all widgets, then de-activate them according to selected options.
        for group in list(self._widgets_group.values()):
            for widget in group:
                widget.configure(state='normal')

        # Enable/disable according to "Use HTTP proxy:" radiobutton.
        if self._widgets['collector.localonly'].get()!=0:
            for widget in self._widgets_group['collector.localonly']:
                widget.configure(state='disabled')
        else:
            for widget in self._widgets_group['NOT collector.localonly']:
                widget.configure(state='disabled')

        # Enable/disable according to "Use HTTP proxy:" radiobutton.
        if self._widgets['network.http.proxy.enabled'].get()==0:
            for widget in self._widgets_group['network.http.proxy.enabled']:
                widget.configure(state='disabled')

        # Enable/disable according to "Proxy requires authentication:" checkbox
        if self._widgets['network.http.proxy.auth.enabled'].get()==0:
            for widget in self._widgets_group['network.http.proxy.auth.enabled']:
                widget.configure(state='disabled')

        if self._widgets['collector.localonly'].get()==0:
            if self._widgets['network.http.proxy.enabled'].get()==0:
                self._widgets['ConnectionImage'].configure(image=self._ICONS['connected'])
            else:
                if self._widgets['network.http.proxy.auth.enabled'].get()==0:
                    self._widgets['ConnectionImage'].configure(image=self._ICONS['proxy'])
                else:
                    self._widgets['ConnectionImage'].configure(image=self._ICONS['proxyauth'])
        else:
            self._widgets['ConnectionImage'].configure(image=self._ICONS['localonly'])


        # Enable/disable keyword search text area:
        if self._widgets['collector.keywords.enabled'].get()==0:
            self._widgets_group['collector.keywords.keywords'][0].configure(state='disabled')
        else:
            self._widgets_group['collector.keywords.keywords'][0].configure(state='normal')



    def _imageChanger(self):
        ''' This event handler changes the image according to checked options. '''
        if self._widgets['assembler.superpose.randomrotation'].get()==0:
            self._widgets['RotationCheckbutton'].configure(image=self._ICONS['norotation'])
        else:
            self._widgets['RotationCheckbutton'].configure(image=self._ICONS['rotation'])

        if self._widgets['assembler.mirror'].get()==0:
            self._widgets['MirrorCheckbutton'].configure(image=self._ICONS['normal'])
        else:
            self._widgets['MirrorCheckbutton'].configure(image=self._ICONS['mirror'])

        if self._widgets['assembler.invert'].get()==0:
            self._widgets['InvertCheckbutton'].configure(image=self._ICONS['normal'])
        else:
            self._widgets['InvertCheckbutton'].configure(image=self._ICONS['invert'])

        if self._widgets['assembler.emboss'].get()==0:
            self._widgets['EmbossCheckbutton'].configure(image=self._ICONS['normal'])
        else:
            self._widgets['EmbossCheckbutton'].configure(image=self._ICONS['emboss'])

        if self._widgets['assembler.resuperpose'].get()==0:
            self._widgets['ResuperposeCheckbutton'].configure(image=self._ICONS['normal'])
        else:
            self._widgets['ResuperposeCheckbutton'].configure(image=self._ICONS['resuperpose'])


    def saveClick(self):
        self.saveConfig()
        if self.configSource in ('registry','inifile'):
            sourceName = "registry"
            if self.configSource == 'inifile':
                sourceName = self.config.configFilename()
            # Pre-defined Tk bitmaps: ('error', 'gray25', 'gray50', 'hourglass','info', 'questhead', 'question', 'warning')
            Pmw.MessageDialog(self.top,title = 'Configuration saved',message_text="Configuration saved to %s." % sourceName,iconpos='w',icon_bitmap='info')
        else:
            Pmw.MessageDialog(self.top,title = 'Error while saving configuration',message_text="Could not save configuration to registry or .ini file !",iconpos='w',icon_bitmap='error')

    def loadClick(self):
        self.loadConfig()
        if self.configSource in ('registry','inifile'):
            sourceName = "registry"
            if self.configSource == 'inifile':
                sourceName = self.config.configFilename()
            Pmw.MessageDialog(self.top,title = 'Configuration loaded',message_text="Configuration loaded from from %s." % sourceName,iconpos='w',icon_bitmap='info')
        else:
            Pmw.MessageDialog(self.top,title = 'Configuration loaded',message_text="Configuration could not be read from registry or .ini file.\nConfiguration was loaded with default values.",iconpos='w',icon_bitmap='warning')

    def defaultClick(self):
        self.defaultValues()

    def exitClick(self):
        self.top.destroy()

    def chooseImagepoolDirClick(self):
        initialDir = self._widgets['pool.imagepooldirectory'].get()
        newDir = tkinter.filedialog.askdirectory(parent=self,initialdir=initialDir,title='Select a directory where to store downloaded images...').strip()
        if len(newDir) > 0:
            self._widgets['pool.imagepooldirectory'].set( newDir )

    def chooseWorkingDirClick(self):
        initialDir = self._widgets['persistencedirectory'].get()
        newDir = tkinter.filedialog.askdirectory(parent=self,initialdir=initialDir,title='Select a directory where to store working files...').strip()
        if len(newDir) > 0:
            self._widgets['persistencedirectory'].set( newDir )

    def addImageBlacklist(self):
        file = tkinter.filedialog.askopenfile(parent=self,mode='rb',title='Select a file to add to the blacklist...')
        if file == None:
            return
        data = file.read(10000000)  # Read at most 10 Mb
        file.close()
        self._widgets['blacklist.imagesha1'].insert('end',"\n"+hashlib.sha1(data).hexdigest())

    def chooseLocalStartDirectory(self):
        initialDir = self._widgets['collector.localonly.startdir'].get()
        newDir = tkinter.filedialog.askdirectory(parent=self,initialdir=initialDir,title='Select a directory where to get images from...').strip()
        if len(newDir) > 0:
            self._widgets['collector.localonly.startdir'].set( newDir )

    def showAbout(self):
        ''' Displays the about dialog. '''
        self._widgets['main_notebook'].selectpage(4)
        self._widgets['about_notebook'].selectpage(0)

if __name__ == "__main__":
    main()

