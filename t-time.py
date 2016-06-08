#! /usr/bin/env python
# -*- coding: utf-8 -*-

# t-time
# author: Andrew Bailey
# I wanted a SPA to tell me when the next T ride would come.

import csv,json,time,datetime
from collections import OrderedDict
from string import Template
from os import stat
from sys import exit

# select these routes, column "route_id" in routes.txt
selectRoutes=("BLLB-161","BLSV-161","SPCL-161","RED-161")
# stops that will never appear per route (stops will have IDs in their <th>)
excludeStops={"SPCL-161":("X14472","X14000","X13850","X14075","X13900","X14540","X14467","X14490","X14495","X14468","X14550","X13905","X14080","X13855","X14005","X14474","X14405"),
              "BLLB-161":("X14467","X14468"),
              "BLSV-161":("X14467","X14468")}
# stops that will have their times counted down (or all of them)
activeStops={}
# use AM/PM or 24 hour time representation? because Python can't reliably tell this :(
_12hourClock=True
# output file name (will have .html attached later)
outputName=None
# <title> contents
agency=None

day=datetime.timedelta(days=1)
dates={0:[],1:[],2:[],3:[],4:[],5:[],6:[]}
schedules={}
trips={}
stops={}
routes={}
schedules=[]
template=""

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

class Route:
    def __init__(self, csvreader):
        self.schedules={}
        self.id=csvreader["route_id"]
        self.agency=routerow["agency_id"] if "agency_id" in routerow else agency
        self.shortname=routerow["route_short_name"]
        self.longname=csvreader["route_long_name"]
        self.stops={}
        #self.stopids={}
    def finalize(self):
        accountedFor={}
        for sched in self.schedules.values():
            for trip in sched:
                if trip.direction not in self.stops:
                    self.stops[trip.direction]=[]
                    accountedFor[trip.direction]=[]
                #if trip.direction not in self.stopids:
                #    self.stopids[trip.direction]={}
                for stop in trip.stops:
                    if stops[stop.stopid] not in accountedFor[trip.direction]:
                        self.stops[trip.direction].append([stops[stop.stopid],stop.stopid])
                        accountedFor[trip.direction].append(stops[stop.stopid])
                    #if stops[stop.stopid] not in self.stopids[trip.direction]:
                    #    self.stopids[trip.direction][stops[stop.stopid]]=stop.stopid
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
        for stopobj in self.stops[:]:
            if self.route in excludeStops and stopobj.stopid in excludeStops[self.route]:
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
        return str(
            {#"route":self.route,
             #"service":self.service,
             #"trip":self.trip,
             "direction":self.direction,
             "stops":self.stops})
             #"time":self.time})

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
            #"stopid":self.stopid,
            "name":stops[self.stopid],
            "time":self.time})

# get agency name(s)
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
except FileNotFoundError as ex:
    print("File "+ex.filename+" does not exist. This is an invalid feed, because this is a required file.")
    exit(65)
except BaseException as ex:
    print("There was a problem opening "+ex.filename+". This is file required to process the feed.")
    exit(66)
# select which routes to process
try:
    with open("routes.txt",encoding="utf-8") as routesfile:
        routestxt=opencsv(routesfile)
        for routerow in routestxt:
            if selectRoutes is None or len(selectRoutes) is 0 or routerow["route_id"] in selectRoutes:
                routes[routerow["route_id"]]=Route(routerow)
except FileNotFoundError as ex:
    print("File "+ex.filename+" does not exist. This is an invalid feed, because this is a required file.")
    exit(65)
except BaseException as ex:
    print("There was a problem opening "+ex.filename+". This is file required to process the feed.")
    exit(66)
print("Routes read")

# assign trips to schedules ("trip" being a list of stops)
try:
    with open("trips.txt",encoding="utf-8") as tripsfile:
        tripstxt=opencsv(tripsfile)
        for triprow in tripstxt:
            if triprow["route_id"] in routes:
                trips[triprow["trip_id"]]=Trip(triprow)
except FileNotFoundError as ex:
    print("File "+ex.filename+" does not exist. This is an invalid feed, because this is a required file.")
    exit(65)
except BaseException as ex:
    print("There was a problem opening "+ex.filename+". This is file required to process the feed.")
    exit(66)
print("Trips read")

# assign stops to trips of selected routes
print("Reading stops (please stand by)")
try:
    with open("stop_times.txt",encoding="utf-8") as stoptimesfile:
        stoptimestxt=opencsv(stoptimesfile)
        for stoprow in stoptimestxt:
            if stoprow["trip_id"] in trips and "1"!=stoprow["pickup_type"] and "1"!=stoprow["drop_off_type"]:
                trip=trips[stoprow["trip_id"]]
                stop=Stop(stoprow)
                trip.addStop(stop)
                stops[stoprow["stop_id"]]=None
except FileNotFoundError as ex:
    print("File "+ex.filename+" does not exist. This is an invalid feed, because this is a required file.")
    exit(65)
except BaseException as ex:
    print("There was a problem opening "+ex.filename+". This is file required to process the feed.")
    exit(66)
print("Stops read")

# name stops
try:
    with open("stops.txt",encoding="utf-8") as stopsfile:
        stopstxt=opencsv(stopsfile)
        for stoprow in stopstxt:
            if stoprow["stop_id"] in stops:
                stopname=stoprow["stop_name"]
                if stopname.lower().endswith(" station"):
                    stopname=stopname[:-8]
                stops[stoprow["stop_id"]]=stopname
except FileNotFoundError as ex:
    print("File "+ex.filename+" does not exist. This is an invalid feed, because this is a required file.")
    exit(65)
except BaseException as ex:
    print("There was a problem opening "+ex.filename+". This is file required to process the feed.")
    exit(66)
print("Stops identified")

# daily regularly scheduled service
try:
    with open("calendar.txt",encoding="utf-8") as calendar:
        caltxt=opencsv(calendar)
        for calrow in caltxt:
            testdate=parsedate(calrow["start_date"])
            enddate=parsedate(calrow["end_date"])
            if "1"==calrow["sunday"]:
                dates[0].append(calrow["service_id"])
            if "1"==calrow["monday"]:
                dates[1].append(calrow["service_id"])
            if "1"==calrow["tuesday"]:
                dates[2].append(calrow["service_id"])
            if "1"==calrow["wednesday"]:
                dates[3].append(calrow["service_id"])
            if "1"==calrow["thursday"]:
                dates[4].append(calrow["service_id"])
            if "1"==calrow["friday"]:
                dates[5].append(calrow["service_id"])
            if "1"==calrow["saturday"]:
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
except FileNotFoundError as ex:
    print("File "+ex.filename+" does not exist. This is an invalid feed, because this is a required file.")
    exit(65)
except BaseException as ex:
    print("There was a problem opening "+ex.filename+". This is file required to process the feed.")
    exit(66)
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
except FileNotFoundError as ex:
    print("File "+ex.filename+" does not exist. Exceptions to regularly scheduled service will not be considered.")
except BaseException as ex:
    print("There was a problem opening "+ex.filename+". Exceptions to regularly scheduled service will not be considered.")
# gather trips into route schedules
for trip in trips.values():
    route=routes[trip.route]
    if trip.service not in route.schedules:
        route.schedules[trip.service]=[]
    if trip.service not in schedules:
        schedules.append(trip.service)
    trip.finalize()
    route.schedules[trip.service].append(trip)
# delete unneccessary schedules
for dayschedules in dates.values():
    for schedule in dayschedules[:]:
        if schedule not in schedules:
            dayschedules.remove(schedule)
# sort trips within route schedules
for route in routes.values():
    for schedule in route.schedules.values():
        schedule.sort()
    route.finalize()
print("Schedules assigned")

outputVars={"title":agency,"headerTitle":agency,"_12hourClock":str(_12hourClock).lower(),"generationDate":datetime.datetime.now().isoformat()}
routeSelect=""
tableTemplate="\t<div id='{0}' class='hide'>\n\t\t<h2>{1}</h2>\n{2}\t</div>\n"
activeTemplate="\t\t<table class='active'><caption>{0}</caption><thead></thead><tbody></tbody></table>\n"
tables=""
css="<style>"
if selectRoutes is None or len(selectRoutes) is 0:
	for routeid in routes.keys():
		route=routes[routeid]
		routeSelect+="\t\t<li><a href='#' data-route='{1}'>{0}</a></li>\n".format(route.shortname,route.id)
		routetables=""
		for line in route.stops:
			routetables+=activeTemplate.format(line)
		tables+=tableTemplate.format(route.id,route.longname,routetables)
else:
	for routeid in selectRoutes:
		route=routes[routeid]
		routeSelect+="\t\t<li><a href='#' data-route='{1}'>{0}</a></li>\n".format(route.shortname,route.id)
		routetables=""
		for line in route.stops:
			routetables+=activeTemplate.format(line)
		tables+=tableTemplate.format(route.id,route.longname,routetables)
outputVars["routeSelect"]=routeSelect
outputVars["javascript"]="var routes={1};\nvar dates={0};\n".format(dates.__str__(),routes.__str__())
outputVars["routeDisplay"]=tables

# read CSS to combine into HTML
try:
    with open("t-time.css","r",encoding="utf-8") as cssfile:
        for line in cssfile:
            css+=line
except BaseException as ex:pass # Don't worry about it; I trust you know what you are doing
css+="</style>"
# read template
try:
    with open("t-time.html","r",encoding="utf-8") as templatefile:
        for line in templatefile:
            template+=line
except FileNotFoundError as ex:
    print("File "+ex.filename+" does not exist. This is the HTML template to export the data.")
    exit(65)
except BaseException as ex:
    print("There was a problem opening "+ex.filename+". This is the HTML template to export the data.")
    exit(66)
template=template.replace('<link rel="stylesheet" href="t-time.css" />',css,1)
templateObj=Template(template)
# write HTML
outputName=outputName+".html"
try:
    with open(outputName,"w",encoding="utf-8") as output:
        output.write(templateObj.substitute(outputVars))
except BaseException as ex:
    print("There was a problem writing "+ex.filename+". This was to be the output file, but it cannot be created or written, or something.")
    exit(73)
input("Wrote {0} as final output. Have fun!".format(outputName))
