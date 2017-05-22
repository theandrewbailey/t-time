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

import csv,json,time,datetime,email.utils,re,zipfile,io,json,html.parser
from string import Template
from os import stat
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
        return csv.DictReader(io.StringIO(fileobject),dialect=dialect)
    else:
        dialect=csv.Sniffer().sniff(fileobject.read(4090))
        fileobject.seek(0)
        return csv.DictReader(fileobject,dialect=dialect)
def openFileInZip(zipfile,filename):
    """take a zip file, and return an entire file within as a string"""
    with zipfile.open(filename) as file:
        return file.read().decode("utf-8")
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
    #print(ex)
    if isinstance(ex,FileNotFoundError):
        print("File "+ex.filename+" does not exist. This is an invalid feed, because this is a required file." if fileNotFound is None else fileNotFound)
        if shouldExit:
            exit(65)
    elif isinstance(ex,BaseException):
        print("There was a problem opening "+ex.filename+". This is file required to process the feed." if base is None else base)
        if shouldExit:
            exit(66)

class Route:
    """container for trips and schedules, and associated stop points"""
    def __init__(self, csvreader):
        """read columns off a single row of routes.txt"""
        self.id=csvreader["route_id"]
        self.agency=csvreader["agency_id"] if "agency_id" in csvreader else agencyName
        self.shortname=csvreader["route_short_name"]
        self.longname=csvreader["route_long_name"]
        self.referredTo=csvreader[_routeIdColumn]
        self.reset()
    def reset(self):
        """drop current data (undo self.finalize)"""
        self.schedules={}
        self.stops={}
        self.accountedFor={}
    def finalize(self,stops):
        """organize all child trips and stops"""
        for sched in self.schedules.values():
            for destination in sched.values():
                for trip in destination:
                    if trip.direction not in self.stops:
                        self.stops[trip.direction]=[]
                        self.accountedFor[trip.direction]=[]
                    for stop in trip.stops:
                        if stops[stop.stopid] not in self.accountedFor[trip.direction]:
                            # maybe put these in some sort of order?
                            self.stops[trip.direction].append([stops[stop.stopid],stop.stopid])
                            self.accountedFor[trip.direction].append(stops[stop.stopid])
    def getAllStops(self):
        """figure out all stops, regardless of schedule or direction"""
        stops=OrderedDict()
        for direction,stoplist in self.stops.items():
            for stop in stoplist:
                stops[stop[1]]=stop[0]
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
    def __init__(self, csvreader):
        """reads columns off a single row of trips.txt"""
        self.route=csvreader["route_id"]
        self.service=csvreader["service_id"]
        self.trip=csvreader["trip_id"]
        self.direction=csvreader["trip_headsign"]
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
    def __init__(self, csvreader):
        """reads columns off a single row of stop_times.txt"""
        self.time=csvreader["arrival_time"]
        self.sequence=int(csvreader["stop_sequence"])
        self.stopid=csvreader["stop_id"]
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
            "name":stops[self.stopid],
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
    def __init__(self,outputName=None,agencyName=None,inputZip=None,_12hourClock=True):
        """initialize some variables. can specify a zip file that contains the feed, otherwise will read files from cwd. can set a few things here."""
        self.outputName=outputName
        self.agencyName=agencyName # <title> in html output
        self.inputZip=inputZip
        self._12hourClock=_12hourClock # TODO: Automatically determine this based on current locale (python makes this unclear)
        self.selectedRoutes=() # tuple of route IDs
        self.excludeStops={} # dictionary of route IDs to lists of stop IDs
    def readAgencyName(self):
        """read agency.txt from in the GTFS directory. Prefer agency ID for output name, agency name for agency."""
        def process(agencyfile,outputName,agencyName):
            agencytxt=openCsv(agencyfile)
            for agencyrow in agencytxt:
                if outputName is None:
                    outputName=agencyrow["agency_id"]
                if outputName is None:
                    outputName=agencyrow["agency_name"]
                if agencyName is None:
                    agencyName=agencyrow["agency_name"]
                if agencyName is None:
                    agencyName=agencyrow["agency_id"]
            return outputName+".html",agencyName
        try:
            if self.inputZip is None:
                with open("agency.txt",encoding="utf-8") as agencyfile:
                    self.outputName,self.agencyName=process(agencyfile,self.outputName,self.agencyName)
            else:
                self.outputName,self.agencyName=process(openFileInZip(self.inputZip,"agency.txt"),self.outputName,self.agencyName)
        except (FileNotFoundError,BaseException) as ex:
            handleException(ex)
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
    def readRoutes(self):
        """read routes.txt from GTFS directory to select which routes to process."""
        def process(routesfile,selectedRoutes):
            routes={}
            routesByName={}
            routestxt=openCsv(routesfile)
            for routerow in routestxt:
                if selectedRoutes is None or 0==len(selectedRoutes) or routerow[_routeIdColumn] in selectedRoutes:
                    newroute=Route(routerow)
                    routes[newroute.id]=newroute
                    routesByName[newroute.referredTo]=newroute
            return routesByName, routes
        try:
            if self.inputZip is None:
                with open("routes.txt",encoding="utf-8") as routesfile:
                    self.routesByName,self.routes=process(routesfile,self.selectedRoutes)
            else:
                self.routesByName,self.routes=process(openFileInZip(self.inputZip,"routes.txt"),self.selectedRoutes)
        except (FileNotFoundError,BaseException) as ex:
            handleException(ex)
    def readTrips(self):
        """read trips.txt from GTFS directory, and assign trips to schedules ("trip" being a list of stops)."""
        def process(tripsfile,routes):
            trips={}
            tripstxt=openCsv(tripsfile)
            for triprow in tripstxt:
                if triprow["route_id"] in routes:
                    trips[triprow["trip_id"]]=Trip(triprow)
            return trips
        try:
            if self.inputZip is None:
                with open("trips.txt",encoding="utf-8") as tripsfile:
                    self.trips=process(tripsfile,self.routes)
            else:
                self.trips=process(openFileInZip(self.inputZip,"trips.txt"),self.routes)
        except (FileNotFoundError,BaseException) as ex:
            handleException(ex)
    def readStops(self):
        """read stop_times.txt from GTFS directory, and assign stops to trips of selected routes, and name stops."""
        def processStoptimesFile(stoptimesfile,trips):
            stops={}
            stoptimestxt=openCsv(stoptimesfile)
            for stoprow in stoptimestxt:
                if stoprow["trip_id"] in trips and "1"!=stoprow["pickup_type"] and "1"!=stoprow["drop_off_type"]:
                    trip=trips[stoprow["trip_id"]]
                    stop=Stop(stoprow)
                    trip.addStop(stop)
                    stops[stoprow["stop_id"]]=None
            return stops
        def processStopsFile(stopsfile,stops):
            stopstxt=openCsv(stopsfile)
            for stoprow in stopstxt:
                if stoprow["stop_id"] in stops:
                    stopname=stoprow["stop_name"]
                    if stopname.lower().endswith(" station"):
                        stopname=stopname[:-8]
                    stops[stoprow["stop_id"]]=stopname
        stops=None
        try:
            if self.inputZip is None:
                with open("stop_times.txt",encoding="utf-8") as stoptimesfile:
                    self.stops=processStoptimesFile(stoptimesfile,self.trips)
            else:
                self.stops=processStoptimesFile(openFileInZip(self.inputZip,"stop_times.txt"),self.trips)
        except (FileNotFoundError,BaseException) as ex:
            handleException(ex)
        try:
            if self.inputZip is None:
                with open("stops.txt",encoding="utf-8") as stopsfile:
                    processStopsFile(stopsfile,self.stops)
            else:
                processStopsFile(openFileInZip(self.inputZip,"stops.txt"),self.stops)
        except (FileNotFoundError,BaseException) as ex:
            handleException(ex)
    def readSchedules(self):
        """read calendar.txt (daily regularly scheduled service) and calendar_dates.txt (if available) from GTFS directory. return dictionary of regularly scheduled weekday and specific dates the schedule is valid for."""
        def processCalendar(calendar,dates):
            day=datetime.timedelta(days=1)
            caltxt=openCsv(calendar)
            for calrow in caltxt:
                testdate=parseDate(calrow["start_date"])
                enddate=parseDate(calrow["end_date"])
                # sometimes there are schedules that should really be exceptions
                # (since they are only valid for one day),
                # and should not be confused with regular service
                if "1"==calrow["sunday"] and calrow["start_date"]!=calrow["end_date"]:
                    dates[0].append(calrow["service_id"])
                if "1"==calrow["monday"] and calrow["start_date"]!=calrow["end_date"]:
                    dates[1].append(calrow["service_id"])
                if "1"==calrow["tuesday"] and calrow["start_date"]!=calrow["end_date"]:
                    dates[2].append(calrow["service_id"])
                if "1"==calrow["wednesday"] and calrow["start_date"]!=calrow["end_date"]:
                    dates[3].append(calrow["service_id"])
                if "1"==calrow["thursday"] and calrow["start_date"]!=calrow["end_date"]:
                    dates[4].append(calrow["service_id"])
                if "1"==calrow["friday"] and calrow["start_date"]!=calrow["end_date"]:
                    dates[5].append(calrow["service_id"])
                if "1"==calrow["saturday"] and calrow["start_date"]!=calrow["end_date"]:
                    dates[6].append(calrow["service_id"])
                while testdate != enddate:
                    datestr=formatDate(testdate)
                    if datestr not in dates:
                        dates[datestr]=[]
                    dayofweek=testdate.weekday()
                    if (0==dayofweek and "1"==calrow["monday"]) or \
                        (1==dayofweek and "1"==calrow["tuesday"]) or \
                        (2==dayofweek and "1"==calrow["wednesday"]) or \
                        (3==dayofweek and "1"==calrow["thursday"]) or \
                        (4==dayofweek and "1"==calrow["friday"]) or \
                        (5==dayofweek and "1"==calrow["saturday"]) or \
                        (6==dayofweek and "1"==calrow["sunday"]):
                        dates[datestr].append(calrow["service_id"])
                    testdate+=day
        def processDates(calendar,dates):
            caltxt=openCsv(calendar)
            for calrow in caltxt:
                dateexc=parseDate(calrow["date"])
                datestr=formatDate(dateexc)
                if "1"==calrow["exception_type"]:
                    dates[datestr].append(calrow["service_id"])
                elif "2"==calrow["exception_type"]:
                    dates[datestr].remove(calrow["service_id"])
        self.dates={0:[],1:[],2:[],3:[],4:[],5:[],6:[]}
        try:
            if self.inputZip is None:
                with open("calendar.txt",encoding="utf-8") as calendar:
                    processCalendar(calendar,self.dates)
            else:
                processCalendar(openFileInZip(self.inputZip,"calendar.txt"),self.dates)
        except (FileNotFoundError,BaseException) as ex:
            handleException(ex)
        # exceptions to regularly scheduled service
        try:
            if self.inputZip is None:
                with open("calendar_dates.txt",encoding="utf-8") as calendar:
                    processDates(calendar,self.dates)
            else:
                processDates(openFileInZip(self.inputZip,"calendar_dates.txt"),self.dates)
        except (FileNotFoundError,BaseException) as ex:
            handleException(ex,
                "File "+ex.filename+" does not exist. Exceptions to regularly scheduled service will not be considered.",
                "There was a problem opening "+ex.filename+". Exceptions to regularly scheduled service will not be considered.",
                False)
        return self.dates
    def buildDataModel(self):
        """gather trips into route schedules, delete unneccessary schedules, and sort trips within route schedules."""
        self.schedules=[]
        for trip in self.trips.values():
            route=self.routes[trip.route]
            if trip.service not in route.schedules:
                route.schedules[trip.service]={}
            if trip.service not in self.schedules:
                self.schedules.append(trip.service)
            trip.finalize(self.excludeStops,self.routes[trip.route].referredTo)
            if trip.direction not in route.schedules[trip.service]:
                route.schedules[trip.service][trip.direction]=[]
            route.schedules[trip.service][trip.direction].append(trip)
        for dayschedules in self.dates.values():
            for schedule in dayschedules[:]:
                if schedule not in self.schedules:
                    dayschedules.remove(schedule)
        for route in self.routes.values():
            for schedule in route.schedules.values():
                for destination in schedule.values():
                    destination.sort()
            route.finalize(self.stops)
    def formatOutputVars(self):
        """create output variable object for insertion into template."""
        self.outputVars={"title":self.agencyName,"headerTitle":self.agencyName,"generationDate":email.utils.formatdate(localtime=True)}
        routeSelect=""
        tableTemplate="\t<section id='{0}'>\n\t\t<h1>{1}</h1>\n{2}\t</section>\n"
        activeTemplate="\t\t<table><caption>{0}</caption><thead></thead><tbody></tbody></table>\n"
        tables=""
        for routename in self.selectedRoutes if len(self.selectedRoutes)>0 else self.routesByName.keys():
            route=self.routesByName[routename]
            routeSelect+="\t<input type='radio' name='line' value='{1}' id='radio-{1}'/><label for='radio-{1}'>{0}</label>\n".format(route.shortname,route.id)
            routetables=""
            for line in sorted(route.stops.keys()):
                routetables+=activeTemplate.format(line)
            tables+=tableTemplate.format(route.id,route.longname,routetables)
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
                "File "+ex.filename+" does not exist. This is the HTML template to export the data.",
                "There was a problem opening "+ex.filename+". This is the HTML template to export the data.")
        if self.css is not None:
            template=template.replace('<link rel="stylesheet" href="t-time.css" />',self.css,1)
        self.template=Template(template)
    def writeHtml(self):
        """use output variables on template, and write HTML file. return output filename"""
        try:
            with open(self.outputName,"w",encoding="utf-8") as output:
                output.write(self.template.substitute(self.outputVars))
        except BaseException as ex:
            print("There was a problem writing "+ex.filename+". This was to be the output file, but it cannot be created or written, or something.")
            exit(73)
        return self.outputName
    def completeOutput(self):
        self.readCss()
        self.formatOutputVars()
        self.readHtmlTemplate()
        return self.writeHtml()
    def run(self):
        """automatically run things the way they were meant to be run with (hopefully reasonable) defaults."""
        self.readAgencyName()
        oldFile=self.readSettings()
        if oldFile is not None:
            print("Found old file {0} and imported old settings.".format(oldFile))
        self.readRoutes()
        print("Routes read")
        self.readTrips()
        print("Trips read")
        print("Reading stops (please stand by)")
        self.readStops()
        print("Stops read")
        self.readSchedules()
        self.buildDataModel()
        print("Schedules assigned")
        print("Wrote {0} as final output. Have a nice trip!".format(self.completeOutput()))

if "__main__"==__name__:
    if len(argv)>1:
        with zipfile.ZipFile(argv[1]) as inputZipObject:
            GtfsProcessor(inputZip=inputZipObject).run()
    else:
        GtfsProcessor().run()
