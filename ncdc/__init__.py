# Module to access data via NCDC
import datetime
import json
import math

from google.appengine.api import lib_config
from google.appengine.api import memcache
from google.appengine.api import urlfetch
from google.appengine.ext import ndb

NCDCTOKEN = 'DuEuaUxZrPkhUrVYDJeHWtibOTkSrZfI'  # evilmonkey@gmail.com
#NCDCTOKEN = 'ckeqZCHsiCYODGhDxYJzBwfGrqUtzSxd'  # ryan@google.com
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

class Station(object):
  def __init__(self, station_id, lat, lng):
    assert isinstance(station_id, str) or isinstance(station_id, unicode)
    assert isinstance(lat, float)
    assert isinstance(lng, float)
    self.station_id = str(station_id)
    self.lat = lat
    self.lng = lng

  def __str__(self):
    return 'Station ID: %s\nLatitude  : %s\nLongitude : %s' % (self.station_id,
                                                               self.lat,
                                                               self.lng)


class StationModel(ndb.Model):
  station_id = ndb.StringProperty(required=True)
  lat = ndb.FloatProperty(required=True)
  lng = ndb.FloatProperty(required=True)


class StationProperty(ndb.StructuredProperty):
  def __init__(self, **kwargs):
    super(StationProperty, self).__init__(StationModel, **kwargs)

  def _validate(self, value):
    assert isinstance(value, Station)

  def _to_base_type(self, value):
    return StationModel(station_id=value.station_id, lat=value.lat,
                        lng=value.lng)

  def _from_base_type(self, value):
    return Station(value.station_id, value.lat, value.lng)


class StateStations(ndb.Model):
  stateId = ndb.StringProperty()
  stations = StationProperty(repeated=True)


class NCDC(object):
  EARTH_RADIUS = 6371

  def __init__(self):
    # there isn't really anything to do here
    pass

  def GetStateCode(self, state_abbr):
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

  def GetStateStations(self, state_code):
    """Returns a list of all the stations within a state.

    Args:
      state_code: a NCDC FIPS location ID number

    Returns:
      a list of Stations 
    """
    stations = StateStations.query(
        StateStations.stateId == state_code).get()
    if not stations:
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
      all_station_info = []
      for station in all_stations:
        all_station_info.append(Station(
            station_id=str(station['id']),
            lat=station['latitude'],
            lng=station['longitude']))
      ndb_stations.stations = all_station_info
      ndb_stations.put()
      all_stations = ndb_stations.stations
    else:
      all_stations = stations.stations
    return all_stations

  def GetClosestStationId(self, lat, lng, stations):
    """Get the ID of the closest station to the latitude and longitude given.

    Args:
      lat: a float of the latitude
      lng: a float of the longitude
      stations: a list of stations with lat and long data

    Returns:
      a string of the station ID
    """
    closest_station_distance = 999999999  # really big number
    station_id = None
    for station in stations:
      lat_delta = math.radians(lat - station.lat)
      lng_delta = math.radians(lng - station.lng)
      station_lat_rad = math.radians(station.lat)
      lat_rad = math.radians(lat)
      # haversine formula
      a = (math.sin(lat_delta/2) * math.sin(lat_delta/2) +
           math.sin(lng_delta/2) * math.sin(lng_delta/2) *
           math.cos(station_lat_rad) * math.cos(lat_rad))
      c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
      distance = self.EARTH_RADIUS * c
      if distance < closest_station_distance:
        station_id = station.station_id
        closest_station_distance = distance
    return station_id

  def GetLastFrostDate(self, station, year):
    """Gets the 10% probability of frost after a given date from NCDC.

    Args:
      station: string of the station id number to get the data from
      year: integer of the year to calculate last spring frost for.

    Returns:
      datetime.date()
    """
    # the number we are looking for is the number of days from the beginning of
    # the year. Any negative numbers should return the spring equinox for that
    # year, i.e. %(year)d-03-20
    spring = datetime.date(year, 3, 20)
    last_frost = MEMCACHE.get(station)
    if not last_frost:
      try:
        last_frost_request = urlfetch.fetch(
            NCDC_DATA_REQUEST % station,
            headers=NCDC_REQUEST_HEADER,
            deadline=60)
        if last_frost_request.status_code == 200:
          last_frost = json.loads(last_frost_request.content)
          MEMCACHE.add(key=station, value=last_frost)
      except urlfetch.DownloadError as err:
        logging.error(err)
        logging.error('Request Status Code: %s',
                      last_frost_request.status_code)
        logging.error('Request contents (if any): %s',
                      last_frost_request.content)
        return spring
    if last_frost['results'][0]['value'] > 0:
      spring = (datetime.date(year, 1, 1) +
                datetime.timedelta(days=last_frost['results'][0]['value']))
    return spring
