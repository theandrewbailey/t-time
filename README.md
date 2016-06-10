# t-time
GTFS to HTML time table processor

This Python script will take files from a [GTFS](https://developers.google.com/transit/gtfs/reference) feed and output a static SPA that contains a schedule for the routes selected. [(Demo)](https://theandrewbailey.github.io/t-time/PAAC.html)

Every time I used [the T](https://en.wikipedia.org/wiki/Pittsburgh_Light_Rail), I would look at PDFs on my phone. This is me trying to do better.

## Output features

  - full offline functionality (static HTML app)
  - routes displayed at top
     - click/tap route to display time info by destination
  - times are color coded:
     - red means the bus/train should be arriving right now
     - orange is arriving in 5 minutes
     - yellow is arriving in 10 minutes
     - green is arriving in 20 minutes
     - blue is arriving in 30 minutes
  - PM times are in **bold**
  - schedule will automatically update every minute
  - to see full schedule for a day, enter date at bottom and click "Show"
  - if schedule is not available for that specific day, schedule for that day of the week will be shown, and a message will appear on the tables.

## Usage

1. download a feed
   - browse [TransitFeeds](https://transitfeeds.com/)
   - consult your local mass transit organization's developer resources
2. unzip it somewhere
3. run `t-time.py` in somewhere
   - optionally, configure variables in `t-time.py`:
     - `selectRoutes`
       - (tuple/list) only these routes will be included in the output, in that order
      - `excludeStops`
        - (dict keyed by route) these stops will never show in the output
      - `activeStops` (totally bugged and incomplete)
        - (dict keyed by route) only these stops will have times counted down; all stops will show in static schedules
      - `_12hourClock`
        - (True/False) show times between 1-12
      - `outputName`
        - title of HTML output
      - `agency`
        - name of HTML output
4. copy the output HTML file where ever you'd like
    - it is self contained: all JS and CSS is contained within

## Specifics

This was developed against python 3.5 and the [Port Authority of Allegheny County's GTFS feed](http://www.portauthority.org/GeneralTransitFeed/). [PAAC.html](https://theandrewbailey.github.io/t-time/PAAC.html) is it's output.
