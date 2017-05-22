from zipfile import ZipFile
import importlib,threading,tkinter,tkinter.messagebox,tkinter.filedialog,tkinter.ttk
t_time = importlib.import_module("t-time")

"""t-time-ui
author: Andrew Bailey
A tk-based GUI for t-time, to easily select routes and stops

class exports:
GtfsProcessorGui
RouteSelecter
StopSelecter
MultiSelecter

variable exports:
_baseTitle
_padding
"""

# title of window
_baseTitle="t-time"
# how much spacing around widgets
_padding=6

class GtfsProcessorGui(tkinter.Tk):
    """subclasses tkinter.Tk for main window"""
    # how wide are buttons
    _buttonWidth=16
    def __init__(self):
        """extends tkinter.Tk.__init__"""
        tkinter.Tk.__init__(self)
        self.buttonrow=tkinter.ttk.Frame(self)
        self.bNext=tkinter.ttk.Button(self.buttonrow,text="Next",command=self.next,width=self._buttonWidth)
        self.bExit=tkinter.ttk.Button(self.buttonrow,text="Exit",command=self.close,width=self._buttonWidth)
        self.bNext.pack(anchor=tkinter.S,side=tkinter.RIGHT,padx=_padding,pady=_padding)
        self.bExit.pack(anchor=tkinter.S,side=tkinter.RIGHT,padx=_padding,pady=_padding)
        self.buttonrow.pack(anchor=tkinter.E,side=tkinter.BOTTOM,fill=tkinter.Y,expand=True)
    def next(self):
        """delegates to the internal frame"""
        self.mainframe.next()
    def close(self):
        """close main window"""
        self.destroy()
class RouteSelecter(tkinter.ttk.Frame):
    """subclasses tkinter.ttk.Frame for route selection"""
    def __init__(self,master):
        """extends tkinter.ttk.Frame.__init__"""
        tkinter.ttk.Frame.__init__(self,master)
        self.master=master
        self.master.wm_title("Select routes - "+_baseTitle)
        self.selectedRoutes,self.master.gtfs.selectedRoutes=self.master.gtfs.selectedRoutes,()
        self.master.gtfs.readRoutes()
        self.master.gtfs.selectedRoutes=self.selectedRoutes
        self.selectRoutes=MultiSelecter(self)
        routenames=[x.referredTo for x in self.master.gtfs.routes.values()]
        routenames.sort()
        self.selectRoutes.populate(self.master.gtfs.agencyName,routenames,self.master.gtfs.selectedRoutes)
        self.selectRoutes.selecter.configure(width=60)
        self.selectRoutes.selecter.pack(fill=tkinter.BOTH,expand=True)
        self.selectRoutes.pack(fill=tkinter.BOTH,expand=True,padx=_padding,pady=_padding)
        self.pack(side=tkinter.TOP)
    def next(self):
        self.pbar=tkinter.ttk.Progressbar(self.master,orient="horizontal",mode="indeterminate")
        self.pbar.pack(anchor=tkinter.E,side=tkinter.BOTTOM,fill=tkinter.X,expand=True,padx=_padding,pady=_padding)
        self.pack(side=tkinter.TOP)
        self.pbar.start()
        threading.Thread(None,self.finishLogic).start()
    def finishLogic(self):
        """finish logic based on selected routes, and passes control to StopSelecter"""
        self.master.gtfs.selectedRoutes=self.selectRoutes.getSelected()
        self.master.gtfs.readRoutes()
        self.master.gtfs.readTrips()
        self.master.gtfs.readStops()
        self.master.gtfs.readSchedules()
        self.exclude,self.master.gtfs.excludeStops=self.master.gtfs.excludeStops,{}
        self.master.gtfs.buildDataModel()
        self.master.gtfs.excludeStops=self.exclude
        self.pbar.stop()
        self.pbar.destroy()
        self.destroy()
        self.master.mainframe=StopSelecter(self.master)
class StopSelecter(tkinter.ttk.Frame):
    """subclasses tkinter.Frame for stop selection"""
    def __init__(self,master):
        """extends tkinter.ttk.Frame.__init__"""
        tkinter.ttk.Frame.__init__(self,master)
        self.master=master
        self.master.wm_title("Select stops - "+_baseTitle)
        self.stopSelecters={}
        self.rows=[tkinter.ttk.Frame(self)]
        for routeName in self.master.gtfs.selectedRoutes:
            route=self.master.gtfs.routesByName[routeName]
            stops=route.getAllStops()
            displayList=t_time.orderDistinctValues(stops)
            includeList=list(displayList[:])
            for stopid,stopname in stops.items():
                if routeName in self.master.gtfs.excludeStops and stopid in self.master.gtfs.excludeStops[routeName]:
                    try:includeList.remove(stopname)
                    except ValueError:pass
            if 4<len(self.rows[-1].winfo_children()):
                self.rows[-1].pack(side=tkinter.TOP,anchor=tkinter.N,padx=_padding)
                self.rows.append(tkinter.ttk.Frame(self))
            self.stopSelecters[routeName]=MultiSelecter(self.rows[-1]).populate("{0} ({1})".format(route.shortname,route.longname),displayList,includeList)
        self.rows[-1].pack(side=tkinter.LEFT,anchor=tkinter.S,padx=_padding,pady=_padding)
        self.pack(side=tkinter.TOP)
    def next(self):
        """finish logic based on selected stops, writes HTML, and exits application"""
        for routeName,selecter in self.stopSelecters.items():
            selected=selecter.getSelected()
            route=self.master.gtfs.routesByName[routeName]
            excludeids=[]
            for stopid,stopname in route.getAllStops().items():
                if stopname not in selected:
                    excludeids.append(stopid)
            self.master.gtfs.excludeStops[routeName]=excludeids
            route.reset()
        self.master.gtfs.buildDataModel()
        tkinter.messagebox.showinfo(_baseTitle,"Wrote {0} as final output. Have a nice trip!".format(self.master.gtfs.completeOutput()),parent=self.master)
        _root.destroy()
class MultiSelecter(tkinter.ttk.LabelFrame):
    """create a labeled multiple select listbox with scrollbar"""
    # how many lines should a listbox show
    _lines=18
    # how wide should a listbox be
    _width=35
    def __init__(self,master=None):
        """extends tkinter.ttk.LabelFrame.__init__"""
        tkinter.ttk.LabelFrame.__init__(self,master)
        self.selecter=tkinter.Listbox(self,selectmode=tkinter.MULTIPLE,exportselection=0,height=self._lines,width=self._width,activestyle=tkinter.NONE)
        self.yScroll=tkinter.ttk.Scrollbar(self,orient=tkinter.VERTICAL)
        self.yScroll.config(command=self.selecter.yview)
        self.selecter.config(yscrollcommand=self.yScroll.set)
        self.selecter.pack(fill=tkinter.X,expand=True)
        self.pack(padx=_padding,pady=_padding,side=tkinter.LEFT)
    def populate(self,label,options,selected):
        """give this thing a label, things to display, and things to select"""
        self.config(text=label)
        for option in options:
            self.selecter.insert(tkinter.END,option)
        if len(options)>self._lines:
            self.selecter.pack_forget()
            self.pack_forget()
            self.yScroll.pack(side=tkinter.RIGHT,fill=tkinter.Y)
            self.selecter.pack(fill=tkinter.X,expand=True)
            self.pack(padx=_padding,pady=_padding,side=tkinter.LEFT)
        for item in selected:
            try:
                x=options.index(item)
                self.selecter.selection_set(first=x)
            except ValueError:pass
        return self
    def getSelected(self):
        """return tuple of listbox options selected"""
        return tuple([self.selecter.get(x) for x in self.selecter.curselection()])

if "__main__"==__name__:
    _root=GtfsProcessorGui()
    _root.wm_title(_baseTitle)
    zipname=tkinter.filedialog.askopenfilename(parent=_root,title="Select GTFS zip file",filetypes=(("Zip files","*.zip"),))
    while ""==zipname:
        if not tkinter.messagebox.askyesno("Select GTFS zip file","A GTFS zip file is required. Continue?",parent=_root):
            _root.close()
            exit()
        zipname=tkinter.filedialog.askopenfilename(parent=_root,title="Select GTFS zip file",filetypes=(("Zip files","*.zip"),))
    with ZipFile(zipname,'r') as inputZipObject:
        _root.gtfs=t_time.GtfsProcessor(inputZip=inputZipObject)
        _root.gtfs.readAgencyName()
        _root.gtfs.outputName=tkinter.filedialog.asksaveasfilename(parent=_root,title="Select output file",initialfile=_root.gtfs.outputName,filetypes=(("HTML files","*.html"),))
        while ""==_root.gtfs.outputName:
            _root.gtfs.outputName=None
            _root.gtfs.readAgencyName()
            if not tkinter.messagebox.askyesno("Select output file","An output file will be written, and settings can be read if it already exists. Continue?",parent=_root):
                _root.close()
                exit()
            _root.gtfs.outputName=tkinter.filedialog.asksaveasfilename(parent=_root,title="Select output file",initialfile=_root.gtfs.outputName,filetypes=(("HTML files","*.html"),))
        _root.gtfs.readSettings()
        _root.mainframe=RouteSelecter(_root)
        _root.mainloop()


