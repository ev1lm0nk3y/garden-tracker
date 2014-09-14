# Module to access data via NCDC
import datetime
import json
import math

from google.appengine.api import lib_config
from google.appengine.api import memcache
from google.appengine.api import urlfetch
from google.appengine.ext import ndb

#NCDCTOKEN = 'DuEuaUxZrPkhUrVYDJeHWtibOTkSrZfI'  # evilmonkey@gmail.com
NCDCTOKEN = 'ckeqZCHsiCYODGhDxYJzBwfGrqUtzSxd'  # ryan@google.com
NCDC_REQUEST_HEADER = {'token': NCDCTOKEN}

NCDC_DATA_REQUEST = ('http://www.ncdc.noaa.gov/cdo-web/api/v2/data?'
                     'datasetid=NORMAL_ANN&datatypeid=ANN-TMIN-PRBLST-T32FP10'
                     '&stationid=%s')
NCDC_STATE_REQUEST = ('http://www.ncdc.noaa.gov/cdo-web/api/v2/locations?'
                      'locationcategoryid=ST&limit=52')

STATES_DICT = {
    'AL': 'Alabama',
    'AK': 'Alaska',
    'AZ': 'Arizona',
    'AR': 'Arkansas',
    'CA': 'California',
    'CO': 'Colorado',
    'CT': 'Connecticut',
    'DE': 'Delaware',
    'FL': 'Florida',
    'GA': 'Georgia',
    'HI': 'Hawaii',
    'ID': 'Idaho',
    'IL': 'Illinois',
    'IN': 'Indiana',
    'IA': 'Iowa',
    'KS': 'Kansas',
    'KY': 'Kentucky',
    'LA': 'Louisiana',
    'ME': 'Maine',
    'MD': 'Maryland',
    'MA': 'Massachusetts',
    'MI': 'Michigan',
    'MN': 'Minnesota',
    'MS': 'Mississippi',
    'MO': 'Missouri',
    'MT': 'Montana',
    'NE': 'Nebraska',
    'NV': 'Nevada',
    'NH': 'New Hampshire',
    'NJ': 'New Jersey',
    'NM': 'New Mexico',
    'NY': 'New York',
    'NC': 'North Carolina',
    'ND': 'North Dakota',
    'OH': 'Ohio',
    'OK': 'Oklahoma',
    'OR': 'Oregon',
    'PA': 'Pennsylvania',
    'RI': 'Rhode Island',
    'SC': 'South Carolina',
    'SD': 'South Dakota',
    'TN': 'Tennessee',
    'TX': 'Texas',
    'UT': 'Utah',
    'VT': 'Vermont',
    'VA': 'Virginia',
    'WA': 'Washington',
    'WV': 'West Virginia',
    'WI': 'Wisconsin',
    'WY': 'Wyoming',
    'AS': 'American Samoa',
    'DC': 'District of Columbia',
    'FM': 'Federated States of Micronesia',
    'GU': 'Guam',
    'MH': 'Marshall Islands',
    'MP': 'Northern Mariana Islands',
    'PW': 'Palau',
    'PR': 'Puerto Rico',
    'VI': 'Virgin Islands',
}

MEMCACHE = memcache.Client()

class StationProperty(ndb.StructuredProperty):
  id = ndb.StringProperty()
  lat = ndb.FloatProperty()
  lng = ndb.FloatProperty()


class StateStations(ndb.Model):
  stateId = ndb.StringProperty()
  stations = StationProperty(repeated=True)


class NCDC(object):
  EARTH_RADIUS = 6371

  def _getStateCode(state_abbr):
    """Will return the State's NCDC FIPS code.

    If the code doesn't currently exist, this will populate memcache with codes.

    Args:
      state_abbr: a 2-letter state abbreviation

    Returns:
      a string like 'FIPS:01'
    """
    state_code = MEMCACHE.get(state_abbr)
    if not state_code:
      self._RetrieveAndStoreStateCodesInMemcache()
      state_code = MEMCACHE.get(state_abbr)
    return state_code

  def _RetrieveAndStoreStateCodesInMemcache(self):
    """Makes a call to NCDC to get a list of all state codes."""
    ncdc_states = json.loads(urlfetch.fetch(
        NCDC_STATE_REQUEST,
        headers=NCDC_REQUEST_HEADER).content)
    for si in ncdc_states['results']:
      for abbr, name in STATES_DICT.iteritems():
        if name == si['name']:
          MEMCACHE.add(key=abbr, value=si['id'])
          break

  def _getStateStations(state_code):
    """Returns a list of all the stations within a state.

    Args:
      state_code: a NCDC FIPS location ID number

    Returns:
      a list of stations in that state
    """
    stations = StateStations.query(
        StateStations.stateId == state_code).get()
    if not stations.stations:
      all_stations = []
      offset = 1
      stations = json.loads(urlfetch.fetch(
          ('http://www.ncdc.noaa.gov/cdo-web/api/v2/stations?locationid=%s&'
           'datasetid=NORMAL_ANN&datatypeid=ANN-TMIN-PRBLST-T32FP10&limit=%s'
           '&offset=%s') % (state_code, 1000, 1),
          headers=NCDC_REQUEST_HEADER,
          deadline=60).content)
      while 'results' in stations:
        all_stations += stations['results']
        resultset = stations['metadata']['resultset']
        if not ((resultset['offset'] + resultset['limit']) > resultset['count']):
          offset += 1000
          stations = json.loads(urlfetch.fetch(
              ('http://www.ncdc.noaa.gov/cdo-web/api/v2/stations?locationid=%s&'
               'datasetid=NORMAL_ANN&datatypeid=ANN-TMIN-PRBLST-T32FP10&limit=%s'
               '&offset=%s') % (state_code, 1000, offset),
              headers=NCDC_REQUEST_HEADER,
              deadline=60).content)
        else:
          break
      ndb_stations = StateStations(stateId=state_code)
      for station in all_stations:
        station_info = StationProperty(
            id=station['id'],
            lat=station['latitude'],
            lng=station['longitude'])
        ndb_stations.stations.append(station_info)
      ndb_stations.put()
    else:
      all_stations = stations.stations
    return all_stations

  def _getClosestStationId(lat, lng, stations):
    """Get the ID of the closest station to the latitude and longitude given.

    Args:
      lat: a float of the latitude
      lng: a float of the longitude
      stations: a list of stations with lat and long data

    Returns:
      a string of the station ID
    """
    for station in stations:
      if 'latitude' not in station:
        continue
      lat_delta = math.radians(lat - station['latitude'])
      lng_delta = math.radians(lng - station['longitude'])
      station_lat_rad = math.radians(station['latitude'])
      lat_rad = math.radians(lat)
      # haversine formula
      a = (math.sin(lat_delta/2) * math.sin(lat_delta/2) +
           math.sin(lng_delta/2) * math.sin(lng_delta/2) *
           math.cos(station_lat_rad) * math.cos(zip_lat_rad))
      c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
      distance = EARTH_RADIUS * c
      if distance < closest_station_distance:
        station_id = station['id']
        closest_station_distance = distance
    logging.info('Closest Station %s is %s from zipcode', station_id,
                 closest_station_distance)
    return station_id

  def _getLastFrostDate(station, year):
    """Gets the 10% probability of frost after a given date from NCDC.

    Args:
      station: string of the station id number to get the data from
      year: integer of the year to calculate last spring frost for.

    Returns:
      datetime.date()
    """
    last_frost = json.loads(urlfetch.fetch(
        NCDC_DATA_REQUEST % station,
        headers=NCDC_REQUEST_HEADER,
        deadline=60).content)
    # the number we are looking for is the number of days from the beginning of
    # the year. Any negative numbers should return the spring equinox for that
    # year, i.e. %(year)d-03-20
    spring = datetime.date(year, 3, 20)
    if last_frost['results']['value'] > 0:
      spring = (datetime.date(year, 1, 1) +
                datetime.timedelta(days=last_frost['results']['value']))
    return spring


ncdc = lib_config.register('ncdc', 
                           {'FindClosestStation': NCDC._getClosestStationId,
                            'GetStations': NCDC._getStateStations,
                            'GetStateCode': NCDC._getStateCode,
                            'GetLastFrostDate': NCDC._getLastFrostDate})

