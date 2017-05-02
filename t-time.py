#! /usr/bin/env python
# -*- coding: utf-8 -*-

# t-time
# author: Andrew Bailey
# I wanted a SPA to tell me when the next T ride would come.

import csv,json,time,datetime,email.utils
from collections import OrderedDict
from string import Template
from os import stat
from sys import exit

# routes will be referred to by this column from routes.txt
routeIdColumn="route_short_name"
# select these routes
selectRoutes=("BLLB","BLSV","RED")
# stops that will never appear per route (stops will have IDs in their <th>)
excludeStops={"RED":("X14472","X14000","X13850","X14075","X13900","X14540","X14467","X14490","X14495","X14468","X14550","X13905","X14080","X13855","X14005","X14474","X14405"),
              "BLLB":("X14467","X14468"),
              "BLSV":("X14467","X14468")}
# stops that will have their times counted down (or all of them)
activeStops={}
# use AM/PM or 24 hour time representation? because Python can't reliably tell this :(
_12hourClock=True
# output file name (will have .html attached later)
outputName=None
# <title> contents
agency=None

schedules=[]

def parsedate(datestr):
    """take the GTFS date format and return a date object"""
    tstr=time.strptime(datestr,"%Y%m%d")
    return datetime.date(tstr.tm_year,tstr.tm_mon,tstr.tm_mday)

def formatdate(date):
    """take a date object and return a JS acceptable string"""
    return date.strftime("%Y-%m-%d")

def opencsv(fileobject):
    """take a file object, determine format, and return a CSV DictReader"""
    dialect=csv.Sniffer().sniff(fileobject.read(4095))
    fileobject.seek(0)
    return csv.DictReader(fileobject,dialect=dialect)

def formatTime(timestr):
    parts=timestr.split(':')
    return str(int(parts[0]))+":"+parts[1]

def handleException(ex,fileNotFound=None,base=None,shouldExit=True):
    """generic file exception handler"""
    if fileNotFound is None:
        fileNotFound="File "+ex.filename+" does not exist. This is an invalid feed, because this is a required file."
    if base is None:
        base="There was a problem opening "+ex.filename+". This is file required to process the feed."
    if isinstance(ex,FileNotFoundError):
        print(fileNotFound)
        if shouldExit:
            exit(65)
    elif isinstance(ex,BaseException):
        print(base)
        if shouldExit:
            exit(66)

class Route:
    def __init__(self, csvreader):
        self.schedules={}
        self.id=csvreader["route_id"]
        self.agency=csvreader["agency_id"] if "agency_id" in csvreader else agency
        self.shortname=csvreader["route_short_name"]
        self.longname=csvreader["route_long_name"]
        self.referredTo=csvreader[routeIdColumn]
        self.stops={}
        self.accountedFor={}
    def finalize(self):
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
    def __repr__(self):
        return self.__str__()
    def __str__(self):
        return str(
            {#"id":self.id,
             "stops":self.stops,
             #"stopids":self.stopids,
             "schedules":self.schedules})

class Trip:
    """a glorified list of stops"""
    def __init__(self, csvreader):
        self.route=csvreader["route_id"]
        self.service=csvreader["service_id"]
        self.trip=csvreader["trip_id"]
        self.direction=csvreader["trip_headsign"]
        self.time=None
        self.stops=[]
    def addStop(self, stop):
        self.stops.append(stop)
    def finalize(self):
        """exclude stops and determine time for trip as a whole, for sorting purposes"""
        routename=routes[self.route].referredTo
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
        for orderstop in routes[self.route].accountedFor[self.direction]:
            found=False
            for stop in self.stops:
                if orderstop==stops[stop.stopid]:
                    orderedstops.append(formatTime(stop.time))
                    found=True
                    break
            if not found:
                orderedstops.append('\x00')
        return str(orderedstops)

class Stop:
    def __init__(self, csvreader):
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
        global stops
        return str({
            "name":stops[self.stopid],
            "time":self.time})

def readAgencyName(outputName=None,agency=None):
    """read agency.txt from in the GTFS directory. Prefer agency ID for output name, agency name for agency."""
    try:
        with open("agency.txt",encoding="utf-8") as agencyfile:
            agencytxt=opencsv(agencyfile)
            for agencyrow in agencytxt:
                if outputName is None:
                    outputName=agencyrow["agency_id"]
                if outputName is None:
                    outputName=agencyrow["agency_name"]
                if agency is None:
                    agency=agencyrow["agency_name"]
                if agency is None:
                    agency=agencyrow["agency_id"]
    except (FileNotFoundError,BaseException) as ex:
        handleException(ex)
    return outputName, agency

def readRoutes(selectRoutes):
    """read routes.txt from GTFS directory to select which routes to process.

    arguments:
    selectRoutes -- optional, list of route IDs to return, otherwise return all
    """
    routes={}
    routesByName={}
    try:
        with open("routes.txt",encoding="utf-8") as routesfile:
            routestxt=opencsv(routesfile)
            for routerow in routestxt:
                if selectRoutes is None or len(selectRoutes) is 0 or routerow[routeIdColumn] in selectRoutes:
                    newroute=Route(routerow)
                    routes[newroute.id]=newroute
                    routesByName[newroute.referredTo]=newroute
    except (FileNotFoundError,BaseException) as ex:
        handleException(ex)
    return routesByName, routes

def readTrips(routes):
    """read trips.txt from GTFS directory, and assign trips to schedules ("trip" being a list of stops)

    arguments:
    routes -- required, list of routes to retrieve trips for
    """
    trips={}
    try:
        with open("trips.txt",encoding="utf-8") as tripsfile:
            tripstxt=opencsv(tripsfile)
            for triprow in tripstxt:
                if triprow["route_id"] in routes:
                    trips[triprow["trip_id"]]=Trip(triprow)
    except (FileNotFoundError,BaseException) as ex:
        handleException(ex)
    return trips

def readStops(trips):
    """read stop_times.txt from GTFS directory, and assign stops to trips of selected routes and name stops

    arguments:
    trips -- required, list of trips to get stops for
    """
    stops={}
    try:
        with open("stop_times.txt",encoding="utf-8") as stoptimesfile:
            stoptimestxt=opencsv(stoptimesfile)
            for stoprow in stoptimestxt:
                if stoprow["trip_id"] in trips and "1"!=stoprow["pickup_type"] and "1"!=stoprow["drop_off_type"]:
                    trip=trips[stoprow["trip_id"]]
                    stop=Stop(stoprow)
                    trip.addStop(stop)
                    stops[stoprow["stop_id"]]=None
    except (FileNotFoundError,BaseException) as ex:
        handleException(ex)
    try:
        with open("stops.txt",encoding="utf-8") as stopsfile:
            stopstxt=opencsv(stopsfile)
            for stoprow in stopstxt:
                if stoprow["stop_id"] in stops:
                    stopname=stoprow["stop_name"]
                    if stopname.lower().endswith(" station"):
                        stopname=stopname[:-8]
                    stops[stoprow["stop_id"]]=stopname
    except (FileNotFoundError,BaseException) as ex:
        handleException(ex)
    return stops

def readSchedules():
    """read calendar.txt (daily regularly scheduled service) and calendar_dates.txt (if available) from GTFS directory."""
    day=datetime.timedelta(days=1)
    dates={0:[],1:[],2:[],3:[],4:[],5:[],6:[]}
    try:
        with open("calendar.txt",encoding="utf-8") as calendar:
            caltxt=opencsv(calendar)
            for calrow in caltxt:
                testdate=parsedate(calrow["start_date"])
                enddate=parsedate(calrow["end_date"])
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
                    datestr=formatdate(testdate)
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
    except (FileNotFoundError,BaseException) as ex:
        handleException(ex)
    # exceptions to regularly scheduled service
    try:
        with open("calendar_dates.txt",encoding="utf-8") as calendar:
            caltxt=opencsv(calendar)
            for calrow in caltxt:
                dateexc=parsedate(calrow["date"])
                datestr=formatdate(dateexc)
                if "1"==calrow["exception_type"]:
                    dates[datestr].append(calrow["service_id"])
                elif "2"==calrow["exception_type"]:
                    dates[datestr].remove(calrow["service_id"])
    except (FileNotFoundError,BaseException) as ex:
        handleException(ex,
            "File "+ex.filename+" does not exist. Exceptions to regularly scheduled service will not be considered.",
            "There was a problem opening "+ex.filename+". Exceptions to regularly scheduled service will not be considered.",
            False)
    # gather trips into route schedules
    for trip in trips.values():
        route=routes[trip.route]
        if trip.service not in route.schedules:
            route.schedules[trip.service]={}
        if trip.service not in schedules:
            schedules.append(trip.service)
        trip.finalize()
        if trip.direction not in route.schedules[trip.service]:
            route.schedules[trip.service][trip.direction]=[]
        route.schedules[trip.service][trip.direction].append(trip)
    # delete unneccessary schedules
    for dayschedules in dates.values():
        for schedule in dayschedules[:]:
            if schedule not in schedules:
                dayschedules.remove(schedule)
    # sort trips within route schedules
    for route in routes.values():
        for schedule in route.schedules.values():
            for destination in schedule.values():
                destination.sort()
        route.finalize()
    return dates

def formatOutputVars(agency,selectRoutes,routes,routesByName,dates,_12hourClock):
    """return output variable object for insertion into template."""
    outputVars={"title":agency,"headerTitle":agency,"generationDate":email.utils.formatdate(localtime=True)}
    routeSelect=""
    tableTemplate="\t<section id='{0}'>\n\t\t<h1>{1}</h1>\n{2}\t</section>\n"
    activeTemplate="\t\t<table><caption>{0}</caption><thead></thead><tbody></tbody></table>\n"
    tables=""
    for routename in selectRoutes if len(selectRoutes)>0 else routesByName.keys():
        route=routesByName[routename]
        routeSelect+="\t<input type='radio' name='line' value='{1}' id='radio-{1}'/><label for='radio-{1}'>{0}</label>\n".format(route.shortname,route.id)
        routetables=""
        for line in sorted(route.stops.keys()):
            routetables+=activeTemplate.format(line)
        tables+=tableTemplate.format(route.id,route.longname,routetables)
    outputVars["html"]=routeSelect+tables
    outputVars["javascript"]="const dates={0};\nconst routes={1};\nconst _12hourClock={2};\n".format(dates.__str__(),routes.__str__().replace("'\\x00'","null"),str(_12hourClock).lower())
    return outputVars

def readCss(cssFilename="t-time.css"):
    """read entire CSS file, or return None."""
    css="<style>"
    try:
        with open(cssFilename,"r",encoding="utf-8") as cssfile:
            for line in cssfile:
                css+=line
        css+="</style>"
    except BaseException as ex:
        css=None
    return css

def readHtmlTemplate(templateFilename="t-time.html",css=None):
    """read entire HTML template, insert CSS (optionally), and return it in a Template object."""
    template=""
    try:
        with open(templateFilename,"r",encoding="utf-8") as templatefile:
            for line in templatefile:
                template+=line
    except (FileNotFoundError,BaseException) as ex:
        handleException(ex,
            "File "+ex.filename+" does not exist. This is the HTML template to export the data.",
            "There was a problem opening "+ex.filename+". This is the HTML template to export the data.")
    if css != None:
        template=template.replace('<link rel="stylesheet" href="t-time.css" />',css,1)
    return Template(template)

def writeHtml(template,outputVars,outputName):
    """use output variables on template, and write HTML file."""
    outputName=outputName+".html"
    try:
        with open(outputName,"w",encoding="utf-8") as output:
            output.write(template.substitute(outputVars))
    except BaseException as ex:
        print("There was a problem writing "+ex.filename+". This was to be the output file, but it cannot be created or written, or something.")
        exit(73)

if __name__=="__main__":
    outputName,agency=readAgencyName(outputName,agency)
    routesByName,routes=readRoutes(selectRoutes)
    print("Routes read")
    trips=readTrips(routes)
    print("Trips read")
    print("Reading stops (please stand by)")
    stops=readStops(trips)
    print("Stops read")
    dates=readSchedules()
    print("Schedules assigned")
    outputVars=formatOutputVars(agency,selectRoutes,routes,routesByName,dates,_12hourClock)
    template=readHtmlTemplate(css=readCss())
    writeHtml(template,outputVars,outputName)
    print("Wrote {0} as final output. Have a nice trip!".format(outputName))
