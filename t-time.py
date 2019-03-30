#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""t-time
author: Andrew Bailey
I wanted a SPA to tell me when the next T ride would come.

class exports:
Route
Trip
Stop
SettingsFetcher
GtfsProcessor

function exports:
parseDate
formatDate
openCsv
openFileInZip
formatTime
removeSpaces
handleException
orderDistinctValues

variable exports:
_removeSpacesRegex
_routeIdColumn
"""

import csv,json,time,datetime,email.utils,re,zipfile,io,json,html.parser,codecs
from multiprocessing import Pool
from string import Template
from os import stat,cpu_count
from collections import OrderedDict
from sys import exit,argv

# routes will be referred to by this column from routes.txt
_routeIdColumn="route_short_name"
# see removeSpaces function
_removeSpacesRegex=re.compile(r"([\'\"\]\}][,\:]) ([\'\"\[\{])",re.MULTILINE)

def parseDate(datestr):
    """take the GTFS date format and return a date object"""
    tstr=time.strptime(datestr,"%Y%m%d")
    return datetime.date(tstr.tm_year,tstr.tm_mon,tstr.tm_mday)
def formatDate(date):
    """take a date object and return a JS acceptable string"""
    return date.strftime("%Y-%m-%d")
def openCsv(fileobject):
    """take a file object, determine format, and return a CSV DictReader"""
    if type(fileobject) is str:
        dialect=csv.Sniffer().sniff(fileobject[:4090])
        return csv.reader(io.StringIO(fileobject),dialect=dialect)
    else:
        dialect=csv.Sniffer().sniff(fileobject.read(4090))
        fileobject.seek(0)
        return csv.reader(fileobject,dialect=dialect)
def getFile(name,inputZip,shouldExitOnError=True):
    try:
        if inputZip is None:
            with open(name,encoding="utf-8") as fileObject:
                return fileObject.read()
        else:
            with inputZip.open(name) as file:
                fileBytes=file.read()
                if fileBytes.startswith(codecs.BOM_UTF8):
                    return fileBytes.decode("utf-8-sig")
                return fileBytes.decode("utf-8")
    except (FileNotFoundError,BaseException) as ex:
        handleException(ex,shouldExit=shouldExitOnError)
def formatTime(timestr):
    """remove leading zeros on hours"""
    parts=timestr.split(':')
    return str(int(parts[0]))+":"+parts[1]
def orderDistinctValues(dic):
    """return values of a dictionary (in iteration order), without duplicates"""
    output=[]
    for key,value in dic.items():
        if value not in output:
            output.append(value)
    return tuple(output)
def removeSpaces(victim):
    """remove spaces between brackets and commas, for smaller filesize"""
    return _removeSpacesRegex.sub(r"\1\2",victim)
def handleException(ex,fileNotFound=None,base=None,shouldExit=True):
    """generic file exception handler"""
    if isinstance(ex,FileNotFoundError):
        print("File {0} does not exist. This is an invalid feed, because this is a required file.".format(ex.filename) if fileNotFound is None else fileNotFound)
        if shouldExit:
            exit(65)
    elif isinstance(ex,BaseException):
        print("There was a problem opening {0}. This is file required to process the feed.".format(ex.filename) if base is None else base)
        if shouldExit:
            exit(66)
    return None
class Route:
    """container for trips and schedules, and associated stop points"""
    def __init__(self, routeId, routeAgency, routeShortname, routeLongname, routeReferredTo):
        self.id=routeId
        self.agency=routeAgency
        self.shortname=routeShortname
        self.longname=routeLongname
        self.referredTo=routeReferredTo
        self.reset()
    def reset(self):
        """drop current data (undo self.finalize)"""
        self.schedules={}
        self.stops={}
    def finalize(self,excludeStops):
        """organize all child trips and stops"""
        stops=self.getAllStops()
        for sched in self.schedules.values():
            for destination in sched.values():
                for trip in destination:
                    trip.finalize(excludeStops,self.referredTo)
        for sched in self.schedules.values():
            for destination in sched.values():
                for trip in destination:
                    for stop in trip.stops:
                        if stop.name is not None:
                            if trip.direction not in self.stops:
                                self.stops[trip.direction]=[]
                            if stop.name not in self.stops[trip.direction]:
                                self.stops[trip.direction].append(stop.name)
    def getAllTrips(self):
        """get all trips, regardless of schedule or direction"""
        trips={}
        for schedule in self.schedules:
            for direction in self.schedules[schedule]:
                for trip in self.schedules[schedule][direction]:
                    trips[trip.trip]=trip
        return trips
    def getAllStops(self):
        """figure out all stops, regardless of schedule or direction"""
        stops=OrderedDict()
        for trip in self.getAllTrips().values():
            for stop in trip.stops:
                stops[stop.stopid]=stop
        return stops
    def __lt__(self,other):
        return self.referredTo.__lt__(other.referredTo)
    def __gt__(self,other):
        return self.referredTo.__gt__(other.referredTo)
    def __eq__(self,other):
        return self.referredTo==other.referredTo
    def __ne__(self,other):
        return not self==other
    def __ge__(self,other):
        return not self<other
    def __le__(self,other):
        return not self>other
    def __repr__(self):
        return self.__str__()
    def __str__(self):
        return removeSpaces(str(
            {#"id":self.id,
             "stops":self.stops,
             #"stopids":self.stopids,
             "schedules":self.schedules}))
class Trip:
    """a glorified list of stops"""
    def __init__(self, routeId, serviceId, tripId, tripDirection):
        self.route=routeId
        self.service=serviceId
        self.trip=tripId
        self.direction=tripDirection
        self.time=None
        self.stops=[]
    def addStop(self, stop):
        self.stops.append(stop)
    def finalize(self,excludeStops,routename):
        """exclude stops and determine time for trip as a whole, for sorting purposes"""
        for stopobj in self.stops[:]:
            if routename in excludeStops and stopobj.stopid in excludeStops[routename]:
                self.stops.remove(stopobj)
        self.stops.sort()
        if self.stops[0]:
            self.time=self.stops[0].time
    def __lt__(self,other):
        if self.service!=other.service:
            return self.service.__lt__(other.service)
        if self.route!=other.route:
            return self.route.__lt__(other.route)
        if self.direction!=other.direction:
            return self.direction.__lt__(other.direction)
        return self.time.__lt__(other.time)
    def __gt__(self,other):
        if self.service!=other.service:
            return self.service.__gt__(other.service)
        if self.route!=other.route:
            return self.route.__gt__(other.route)
        if self.direction!=other.direction:
            return self.direction.__gt__(other.direction)
        return self.time.__gt__(other.time)
    def __eq__(self,other):
        return self.service==other.service and self.route==other.route and self.route==other.route and self.time==other.time
    def __ne__(self,other):
        return not self==other
    def __ge__(self,other):
        return not self<other
    def __le__(self,other):
        return not self>other
    def __repr__(self):
        return self.__str__()
    def __str__(self):
        orderedstops=[]
        for stop in self.stops:
            orderedstops.append(formatTime(stop.time))
        return str(orderedstops)
class Stop:
    """represents when a vehicle may pickup or dropoff passengers. a single specific instance will never exist in multiple schedules, routes, or trips."""
    def __init__(self, arrivalTime, sequence, stopId, name=None):
        self.time=arrivalTime
        self.sequence=int(sequence)
        self.stopid=stopId
        self.name=name
    def __lt__(self,other):
        return self.sequence<other.sequence
    def __gt__(self,other):
        return self.sequence>other.sequence
    def __eq__(self,other):
        return self.stopid==other.stopid and self.time==other.time and self.sequence==other.sequence
    def __ne__(self,other):
        return not self==other
    def __ge__(self,other):
        return not self<other
    def __le__(self,other):
        return not self>other
    def __repr__(self):
        return self.__str__()
    def __str__(self):
        return str({
            "name":self.name,
            "time":self.time})
class SettingsFetcher(html.parser.HTMLParser):
    """subclasses html.parser.HTMLParser to look for settings in old output file"""
    def __init__(self):
        """extends html.parser.HTMLParser.__init__"""
        html.parser.HTMLParser.__init__(self)
        self.tag=None
        self.foundTag=False
        self.settings=None
        self.agencyName=None
    def handle_starttag(self,tag,attrs):
        """overides html.parser.HTMLParser.handle_starttag"""
        self.tag=tag
        if "script"==tag and len(attrs)==1 and "type"==attrs[0][0] and "application/x-t-time-settings"==attrs[0][1]:
            self.foundTag=True
        elif "title"==tag:
            self.foundTag=True
    def handle_data(self,data):
        """overides html.parser.HTMLParser.handle_data"""
        if self.foundTag:
            if "script"==self.tag:
                self.settings=data
            elif "title"==self.tag:
                self.agencyName=data
    def handle_endtag(self,tag):
        """overides html.parser.HTMLParser.handle_endtag"""
        self.foundTag=False
class GtfsProcessor:
    """container to hold methods and variables necessary to process GTFS feeds"""
    def __init__(self,outputName=None,agencyName=None,_12hourClock=True):
        """initialize some variables. can specify a zip file that contains the feed, otherwise will read files from cwd. can set a few things here."""
        self.outputName=outputName
        self.agencyName=agencyName # <title> in html output
        self._12hourClock=_12hourClock # TODO: Automatically determine this based on current locale (python makes this unclear)
        self.selectedRoutes=() # tuple of route IDs
        self.excludeStops={} # dictionary of route IDs to lists of stop IDs
        self.schedules=[]
        self.routes={}
    def readAgencyName(self,inputZip):
        """read agency.txt from in the GTFS directory. Prefer agency ID for output name, agency name for agency."""
        agencytxt=openCsv(getFile("agency.txt",inputZip))
        headers=next(agencytxt)
        for agencyrow in agencytxt:
            if self.outputName is None:
                self.outputName=agencyrow[headers.index("agency_id")]
            if self.outputName is None:
                self.outputName=agencyrow[headers.index("agency_name")]
            if self.agencyName is None:
                self.agencyName=agencyrow[headers.index("agency_name")]
            if self.agencyName is None:
                self.agencyName=agencyrow[headers.index("agency_id")]
        self.outputName+=".html"
    def readSettings(self,lastOutput=None):
        """try to read output of the last run of this feed, and load some settings if possible.

        arguments:
        lastOutput -- optional, if last output filename is different than agencyName
        """
        if lastOutput is None:
            lastOutput=self.outputName
        try:
            with open(lastOutput,'r') as old:
                fetcher=SettingsFetcher()
                fetcher.feed(old.read())
                settings=json.loads(fetcher.settings)
                self._12hourClock=settings["_12hourClock"]
                self.selectedRoutes=settings["selectedRoutes"]
                self.excludeStops=settings["excludeStops"]
        except:return None
        return lastOutput
    def readRoutes(self,inputZip):
        """read routes.txt from GTFS directory to select which routes to process."""
        routestxt=openCsv(getFile("routes.txt",inputZip))
        headers=next(routestxt)
        routeIdColumn=headers.index("route_id")
        routeAgencyColumn=headers.index("agency_id")
        routeShortnameColumn=headers.index("route_short_name")
        routeLongnameColumn=headers.index("route_long_name")
        routeReferredToColumn=headers.index(_routeIdColumn)
        for routerow in routestxt:
            if self.selectedRoutes is None or 0==len(self.selectedRoutes) or routerow[routeReferredToColumn] in self.selectedRoutes:
                newroute=Route(routerow[routeIdColumn],routerow[routeAgencyColumn],routerow[routeShortnameColumn],routerow[routeLongnameColumn],routerow[routeReferredToColumn])
                self.routes[newroute.id]=newroute
    def readTrips(self,inputZip):
        """read trips.txt from GTFS directory, and assign trips to schedules ("trip" being a list of stops)."""
        trips={}
        tripstxt=openCsv(getFile("trips.txt",inputZip))
        headers=next(tripstxt)
        tripRouteColumn=headers.index("route_id")
        tripServiceColumn=headers.index("service_id")
        tripIdColumn=headers.index("trip_id")
        tripDirectionColumn=headers.index("trip_headsign")
        for triprow in tripstxt:
            if triprow[tripRouteColumn] in self.routes:
                trips[triprow[tripIdColumn]]=Trip(triprow[tripRouteColumn],triprow[tripServiceColumn],triprow[tripIdColumn],triprow[tripDirectionColumn])
        for trip in trips.values():
            route=self.routes[trip.route]
            if trip.service not in route.schedules:
                route.schedules[trip.service]={}
            if trip.service not in self.schedules:
                self.schedules.append(trip.service)
            if trip.direction not in route.schedules[trip.service]:
                route.schedules[trip.service][trip.direction]=[]
            route.schedules[trip.service][trip.direction].append(trip)
    def _processStopsFiles(stoptimesfile,route):
        trips=route.getAllTrips()
        stoptimestxt=openCsv(stoptimesfile)
        headers=next(stoptimestxt)
        stopTimeColumn=headers.index("arrival_time")
        stopSequenceColumn=headers.index("stop_sequence")
        stopIdColumn=headers.index("stop_id")
        tripIdColumn=headers.index("trip_id")
        pickupColumn=headers.index("pickup_type")
        dropoffColumn=headers.index("drop_off_type")
        for stoprow in stoptimestxt:
            if stoprow[tripIdColumn] in trips and "1"!=stoprow[pickupColumn] and "1"!=stoprow[dropoffColumn]:
                trip=trips[stoprow[tripIdColumn]]
                stop=Stop(stoprow[stopTimeColumn],stoprow[stopSequenceColumn],stoprow[stopIdColumn])
                trip.addStop(stop)
        return route
    def _updateRoutes(self,routes):
        for route in routes:
            self.routes[route.id]=route
    def readStops(self,inputZip):
        """read stop_times.txt from GTFS directory, and assign stops to trips of selected routes, and name stops."""
        try:
            stoptimes=getFile("stop_times.txt",inputZip)
            poolcount=min(len(self.routes),cpu_count())
            with Pool(poolcount) as pool:
                asyncresult=pool.starmap_async(GtfsProcessor._processStopsFiles,[(stoptimes,route) for route in self.routes.values()],callback=self._updateRoutes)
                stops={}
                stopstxt=openCsv(getFile("stops.txt",inputZip))
                headers=next(stopstxt)
                stopNameColumn=headers.index("stop_name")
                stopIdColumn=headers.index("stop_id")
                for stoprow in stopstxt:
                    stopname=stoprow[stopNameColumn]
                    if stopname.lower().endswith(" station"):
                        stopname=stopname[:-8]
                    stops[stoprow[stopIdColumn]]=stopname
                asyncresult.wait()
                for route in self.routes.values():
                    for sched in route.schedules.values():
                        for destination in sched.values():
                            for trip in destination:
                                for stop in trip.stops:
                                    stop.name=stops[stop.stopid]
        except (FileNotFoundError,BaseException) as ex:
            handleException(ex)
    def readSchedules(self,inputZip):
        """read calendar.txt (daily regularly scheduled service) and calendar_dates.txt (if available) from GTFS directory. return dictionary of regularly scheduled weekday and specific dates the schedule is valid for."""
        self.dates={0:[],1:[],2:[],3:[],4:[],5:[],6:[]}
        day=datetime.timedelta(days=1)
        caltxt=openCsv(getFile("calendar.txt",inputZip))
        headers=next(caltxt)
        startDateColumn=headers.index("start_date")
        endDateColumn=headers.index("end_date")
        serviceIdColumn=headers.index("service_id")
        mondayColumn=headers.index("monday")
        tuesdayColumn=headers.index("tuesday")
        wednesdayColumn=headers.index("wednesday")
        thursdayColumn=headers.index("thursday")
        fridayColumn=headers.index("friday")
        saturdayColumn=headers.index("saturday")
        sundayColumn=headers.index("sunday")
        for calrow in caltxt:
            testdate=parseDate(calrow[startDateColumn])
            enddate=parseDate(calrow[endDateColumn])
            # sometimes there are schedules that should really be exceptions
            # (since they are only valid for one day),
            # and should not be confused with regular service
            if "1"==calrow[sundayColumn] and calrow[startDateColumn]!=calrow[endDateColumn]:
                self.dates[0].append(calrow[serviceIdColumn])
            if "1"==calrow[mondayColumn] and calrow[startDateColumn]!=calrow[endDateColumn]:
                self.dates[1].append(calrow[serviceIdColumn])
            if "1"==calrow[tuesdayColumn] and calrow[startDateColumn]!=calrow[endDateColumn]:
                self.dates[2].append(calrow[serviceIdColumn])
            if "1"==calrow[wednesdayColumn] and calrow[startDateColumn]!=calrow[endDateColumn]:
                self.dates[3].append(calrow[serviceIdColumn])
            if "1"==calrow[thursdayColumn] and calrow[startDateColumn]!=calrow[endDateColumn]:
                self.dates[4].append(calrow[serviceIdColumn])
            if "1"==calrow[fridayColumn] and calrow[startDateColumn]!=calrow[endDateColumn]:
                self.dates[5].append(calrow[serviceIdColumn])
            if "1"==calrow[saturdayColumn] and calrow[startDateColumn]!=calrow[endDateColumn]:
                self.dates[6].append(calrow[serviceIdColumn])
            while testdate != enddate:
                datestr=formatDate(testdate)
                if datestr not in self.dates:
                    self.dates[datestr]=[]
                dayofweek=testdate.weekday()
                if (0==dayofweek and "1"==calrow[mondayColumn]) or \
                    (1==dayofweek and "1"==calrow[tuesdayColumn]) or \
                    (2==dayofweek and "1"==calrow[wednesdayColumn]) or \
                    (3==dayofweek and "1"==calrow[thursdayColumn]) or \
                    (4==dayofweek and "1"==calrow[fridayColumn]) or \
                    (5==dayofweek and "1"==calrow[saturdayColumn]) or \
                    (6==dayofweek and "1"==calrow[sundayColumn]):
                    self.dates[datestr].append(calrow[serviceIdColumn])
                testdate+=day

        # exceptions to regularly scheduled service
        caltxt=openCsv(getFile("calendar_dates.txt",inputZip,shouldExitOnError=False))
        headers=next(caltxt)
        dateColumn=headers.index("date")
        exceptionColumn=headers.index("exception_type")
        serviceIdColumn=headers.index("service_id")
        if caltxt is None:
            return
        for calrow in caltxt:
            dateexc=parseDate(calrow[dateColumn])
            datestr=formatDate(dateexc)
            if "1"==calrow[exceptionColumn]:
                if datestr not in self.dates:
                    self.dates[datestr]=[]
                self.dates[datestr].append(calrow[serviceIdColumn])
            elif "2"==calrow[exceptionColumn] and datestr in self.dates and calrow[serviceIdColumn] in self.dates[datestr]:
                self.dates[datestr].remove(calrow[serviceIdColumn])
    def buildDataModel(self):
        """gather trips into route schedules, delete unneccessary schedules, and sort trips within route schedules."""
        for dayschedules in self.dates.values():
            for schedule in dayschedules[:]:
                if schedule not in self.schedules:
                    dayschedules.remove(schedule)
        for route in self.routes.values():
            route.finalize(self.excludeStops)
            for schedule in route.schedules.values():
                for destination in schedule.values():
                    destination.sort()
    def formatOutputVars(self):
        """create output variable object for insertion into template."""
        self.outputVars={"title":self.agencyName,"headerTitle":self.agencyName,"generationDate":email.utils.formatdate(localtime=True)}
        routeSelect=""
        tables=""
        tableTemplate="\t<input type='radio' name='line' value='{0}' id='radio-{0}'/>\n\t<section id='{0}'>\n\t\t<h1>{1}</h1>\n\t</section>\n"
        for route in (route for route in self.routes.values() if len(self.selectedRoutes) is 0 or route.referredTo in self.selectedRoutes):
            routeSelect+="\t<label for='radio-{1}'>{0}</label>\n".format(route.shortname,route.id)
            tables+=tableTemplate.format(route.id,route.longname)
        self.outputVars["ttimesettings"]=removeSpaces(json.dumps({"selectedRoutes":self.selectedRoutes,"excludeStops":self.excludeStops,"_12hourClock":self._12hourClock}))
        self.outputVars["html"]=routeSelect+tables
        self.outputVars["javascript"]="const dates={0};\nconst routes={1};\nconst _12hourClock={2};\n".format(removeSpaces(self.dates.__str__()),removeSpaces(self.routes.__str__().replace("'\\x00'","null")),str(self._12hourClock).lower())
    def readCss(self,cssFilename="t-time.css"):
        """read entire CSS file.

        arguments:
        cssFilename -- optional, if CSS is different than t-time.css
        """
        self.css="<style>"
        try:
            with open(cssFilename,"r",encoding="utf-8") as cssfile:
                for line in cssfile:
                    self.css+=line
            self.css+="</style>"
        except BaseException as ex:
            self.css=None
    def readHtmlTemplate(self,templateFilename="t-time.html"):
        """read entire HTML template and optionally insert CSS

        arguments:
        templateFilename -- optional, if template is different than t-time.html
        """
        template=""
        try:
            with open(templateFilename,"r",encoding="utf-8") as templatefile:
                for line in templatefile:
                    template+=line
        except (FileNotFoundError,BaseException) as ex:
            handleException(ex,
                "File {0} does not exist. This is the HTML template to export the data.".format(ex.filename),
                "There was a problem opening {0}. This is the HTML template to export the data.".format(ex.filename))
        if self.css is not None:
            template=template.replace('<link rel="stylesheet" href="t-time.css" />',self.css,1)
        self.template=Template(template)
    def writeHtml(self):
        """use output variables on template, and write HTML file. return output filename"""
        try:
            with open(self.outputName,"w",encoding="utf-8") as output:
                output.write(self.template.substitute(self.outputVars))
        except BaseException as ex:
            print("There was a problem writing {0}. This was to be the output file, but it cannot be created or written, or something.".format(ex.filename))
            exit(73)
        return self.outputName
    def completeOutput(self):
        self.readCss()
        self.formatOutputVars()
        self.readHtmlTemplate()
        return self.writeHtml()
    def run(self,inputZip):
        """automatically run things the way they were meant to be run with (hopefully reasonable) defaults."""
        self.readAgencyName(inputZip)
        oldFile=self.readSettings()
        if oldFile is not None:
            print("Found old file {0} and imported old settings.".format(oldFile))
        self.readRoutes(inputZip)
        print("Routes read")
        self.readTrips(inputZip)
        print("Trips read")
        print("Reading stops (please stand by)")
        self.readStops(inputZip)
        print("Stops read")
        self.readSchedules(inputZip)
        self.buildDataModel()
        print("Schedules assigned")
        print("Wrote {0} as final output. Have a nice trip!".format(self.completeOutput()))

if "__main__"==__name__:
    if len(argv)>1:
        with zipfile.ZipFile(argv[1]) as inputZipObject:
            GtfsProcessor().run(inputZipObject)
    else:
        GtfsProcessor().run()
