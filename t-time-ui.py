from zipfile import ZipFile
import importlib,tkinter.filedialog,tkinter
t_time = importlib.import_module("t-time")

_padding=6
_baseTitle="t-time"
_listboxLines=20
_root=None

class GtfsProcessorGui(tkinter.Frame):
    """subclasses tkinter.Frame for main window"""
    def __init__(self,master=None):
        """extends tkinter.Frame.__init__"""
        tkinter.Frame.__init__(self,master)
        self.buttonrow=tkinter.Frame(self)
        self.next=tkinter.Button(self.buttonrow,text="Next",command=self.next)
        self.close=tkinter.Button(self.buttonrow,text="Close",command=self.close)
        self.next.pack(side=tkinter.LEFT)
        self.close.pack(side=tkinter.LEFT)
        self.buttonrow.pack(side=tkinter.BOTTOM,fill=tkinter.Y,expand=True)
        self.pack()
    def next(self):
        """delegates to the internal frame"""
        self.mainframe.next()
    def close(self):
        """close main window"""
        _root.destroy()
class RouteSelecter(tkinter.Frame):
    """subclasses tkinter.Frame for route selection"""
    def __init__(self,gtfs,master=None):
        """extends tkinter.Frame.__init__"""
        tkinter.Frame.__init__(self,master)
        self.gtfs=gtfs
        self.master=master
        _root.wm_title("Select routes - "+_baseTitle)
        gtfs.readAgencyName()
        gtfs.readSettings()
        self.selectedRoutes,self.gtfs.selectedRoutes=self.gtfs.selectedRoutes,()
        gtfs.readRoutes()
        self.gtfs.selectedRoutes=self.selectedRoutes
        self.selectRoutes=MultiSelecter(self)
        routenames=[x.referredTo for x in gtfs.routes.values()]
        routenames.sort()
        self.selectRoutes.populate(gtfs.agencyName,routenames,gtfs.selectedRoutes)
        self.pack()
    def next(self):
        """finish logic based on selected routes, and passes control to StopSelecter"""
        self.gtfs.selectedRoutes=self.selectRoutes.getSelected()
        self.gtfs.readRoutes()
        self.gtfs.readTrips()
        self.gtfs.readStops()
        self.gtfs.readSchedules()
        self.exclude,self.gtfs.excludeStops=self.gtfs.excludeStops,{}
        self.gtfs.buildDataModel()
        self.gtfs.excludeStops=self.exclude
        self.destroy()
        self.master.mainframe=StopSelecter(self.gtfs,self.master)
    def destroy(self):
        """extends tkinter.Frame.destroy"""
        self.selectRoutes.destroy()
        self.pack_forget()
        tkinter.Frame.destroy(self)
class StopSelecter(tkinter.Frame):
        """extends tkinter.Frame.__init__"""
    def __init__(self,gtfs,master=None):
        """extends tkinter.Frame.__init__"""
        tkinter.Frame.__init__(self,master)
        self.gtfs=gtfs
        self.master=master
        _root.wm_title("Select stops - "+_baseTitle)
        self.stopSelecters={}
        for routeName in gtfs.selectedRoutes:
            route=gtfs.routesByName[routeName]
            stops=route.getAllStops()
            displayList=t_time.orderDistinctValues(stops)
            includeList=list(displayList[:])
            for stopid,stopname in stops.items():
                if routeName in gtfs.excludeStops and stopid in gtfs.excludeStops[routeName]:
                    try:includeList.remove(stopname)
                    except ValueError:pass
            self.stopSelecters[routeName]=MultiSelecter(self).populate(route.longname,displayList,includeList)
        self.pack()
    def next(self):
        """finish logic based on selected stops, writes HTML, and exits application"""
        for routeName,selecter in self.stopSelecters.items():
            selected=selecter.getSelected()
            route=self.gtfs.routesByName[routeName]
            excludeids=[]
            for stopid,stopname in route.getAllStops().items():
                if stopname not in selected:
                    excludeids.append(stopid)
            self.gtfs.excludeStops[routeName]=excludeids
            route.reset()
        self.gtfs.buildDataModel()
        self.gtfs.readCss()
        self.gtfs.formatOutputVars()
        self.gtfs.readHtmlTemplate()
        self.gtfs.writeHtml()
        _root.destroy()
    def destroy(self):
        """extends tkinter.Frame.destroy"""
        for routeName,selecter in self.stopSelecters.items():
            selecter.destroy();
        self.pack_forget()
        tkinter.Frame.destroy(self)
class MultiSelecter(tkinter.LabelFrame):
    """create a labeled multiple select listbox with scrollbar"""
    def __init__(self,master=None):
        """extends tkinter.LabelFrame.__init__"""
        tkinter.LabelFrame.__init__(self,master)
        self.selecter=tkinter.Listbox(self,selectmode=tkinter.MULTIPLE,exportselection=0,height=_listboxLines)
        self.yScroll=tkinter.Scrollbar(self,orient=tkinter.VERTICAL)
        self.yScroll.config(command=self.selecter.yview)
        self.selecter.config(yscrollcommand=self.yScroll.set)
        self.selecter.pack(fill=tkinter.X,expand=True)
        self.pack(side=tkinter.LEFT,padx=_padding,pady=_padding)
    def populate(self,label,options,selected):
        """give this thing a label, things to display, and things to select"""
        self.config(text=label)
        for option in options:
            self.selecter.insert(tkinter.END,option)
        if len(options)>_listboxLines:
            self.selecter.pack_forget()
            self.pack_forget()
            self.yScroll.pack(side=tkinter.RIGHT,fill=tkinter.Y)
            self.selecter.pack(fill=tkinter.X,expand=True)
            self.pack(side=tkinter.LEFT,padx=_padding,pady=_padding)
        for item in selected:
            try:
                x=options.index(item)
                self.selecter.selection_set(first=x)
            except ValueError:pass
        return self
    def getSelected(self):
        """return tuple of listbox options selected"""
        return tuple([self.selecter.get(x) for x in self.selecter.curselection()])
    def destroy(self):
        """extends tkinter.LabelFrame.destroy"""
        self.yScroll.pack_forget()
        self.selecter.pack_forget()
        self.pack_forget()
        self.yScroll.destroy()
        self.selecter.destroy()
        tkinter.LabelFrame.destroy(self)

if "__main__"==__name__:
    _root=tkinter.Tk()
    _root.geometry("850x600")
    _root.wm_title(_baseTitle)
    gui=GtfsProcessorGui(master=_root)
    zipname=tkinter.filedialog.askopenfilename(title="Select GTFS zip file",filetypes=(("Zip files","*.zip"),))
    with ZipFile(zipname,'r') as inputZipObject:
        _gtfs=t_time.GtfsProcessor(inputZip=inputZipObject)
        gui.mainframe=RouteSelecter(_gtfs,gui)
        _root.mainloop()


