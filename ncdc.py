import datetime
import json
import logging
import math
import re
import webapp2
import garden_common
import garden_handlers

from google.appengine.api import urlfetch

#NCDCTOKEN = 'DuEuaUxZrPkhUrVYDJeHWtibOTkSrZfI'  # evilmonkey@gmail.com
NCDCTOKEN = 'ckeqZCHsiCYODGhDxYJzBwfGrqUtzSxd'  # ryan@google.com
NCDC_DATASETS = 'http://www.ncdc.noaa.gov/cdo-web/api/v2/datasets?limit=1000'
NCDC_DATA = (
    'http://www.ncdc.noaa.gov/cdo-web/api/v2/data?datasetid=NORMAL_ANN'
    '&datatypeid=ANN-TMIN-PRBLST-T32FP10&stationid=%s')
NCDC_LOCATIONS = (
    'http://www.ncdc.noaa.gov/cdo-web/api/v2/locations?locationcategoryids=CITY&'
    'datasetid=NORMAL_ANN&sortfield=name&limit=1000')
NCDC_FIPS_LOCATION = (
    'http://www.ncdc.noaa.gov/cdo-web/api/v2/locations/FIPS:06')
NCDC_REQUEST_HEADER = {'token': NCDCTOKEN}

STATES_INFO = json.loads(urlfetch.fetch(
    ('http://www.ncdc.noaa.gov/cdo-web/api/v2/locations?'
     'locationcategoryid=ST&limit=52'),
    headers = NCDC_REQUEST_HEADER).content)

CITIES = (
    'http://www.ncdc.noaa.gov/cdo-web/api/v2/data?datasetid=NORMAL_ANN&datatypeid='
    'ANN-TMIN-PRBLST-T32FP10&locationid=ST:%s&limit=10&sortorder=asc')

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


class NCDC(webapp2.RequestHandler):
  def get(self):
    self.response.content_type = 'text/json'
    zipcode = ''
    if self.request.get('zipcode'):
      zipcode = self.request.get('zipcode')
      # get city and state from zipcode
      zipcode_info = json.loads(urlfetch.fetch(
          'http://ziptasticapi.com/%s' % zipcode).content)
      for state in STATES_INFO['results']:
        if STATES_DICT[zipcode_info['state']] in state['name']:
          state_id = state['id']
          break
      stations = garden_common.MEMCACHE.gets(state_id)
      if not stations:
        logging.info('State station info not found in memcache, fetching.')
        stations = GetStations(state_id)
        garden_common.MEMCACHE.add(key=state_id,
                                   value=stations,
                                   time=86400)
      closest_station = FindClosestStationId(stations, zipcode)
      logging.info('Fetching data: %s',
                   NCDC_DATA % closest_station)
      ncdc_request = json.loads(urlfetch.fetch(
          NCDC_DATA % closest_station,
          headers=NCDC_REQUEST_HEADER).content)
      self.response.write(ncdc_request)
      # calculate day of the value returned
      if ncdc_request['results'][0]['value'] < 0:
        self.response.write('No viable data, use first day of spring as frost '
                            'data')
      else:
        last_frost_date = (datetime.date(2014, 1, 1) + datetime.timedelta(
            days=int(ncdc_request['results'][0]['value']))).isoformat()
        self.response.write('Last Frost Day: %s' % last_frost_date)

    else:
      self.response.content_type = 'text/html'
      response = """<html><body><form action="/ncdc">
      Enter Zip Code: <input type=text name=zipcode>
      <input type=submit name=submit value="Get Frost Point">
      </form></body></html>"""
      self.response.write(response)


def FindClosestStationId(stations, zipcode):
  # get the lat lon for the zipcode
  zip_info = json.loads(urlfetch.fetch(
      'http://maps.googleapis.com/maps/api/geocode/json?address=%s&sensor=false' % \
      zipcode,
      deadline=60).content)
  if zip_info['status'] != 'OK':
    logging.info('Could not get Google GeoLocation info from zipcode %s',
                 zipcode)
    return None
  # The result list should have only 1 item, and we are really only interested
  # in the location information from the geometry key.
  zip_location = zip_info['results'][0]['geometry']['location']
  closest_station_distance = 9999999999  # really big number
  station_id = None
  EARTH_RADIUS = 6371
  for station in stations:
    if 'latitude' not in station:
      continue
    lat_delta = math.radians(zip_location['lat'] - station['latitude'])
    lng_delta = math.radians(zip_location['lng'] - station['longitude'])
    station_lat_rad = math.radians(station['latitude'])
    zip_lat_rad = math.radians(zip_location['lat'])
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

def GetStations(state_id):
  logging.info('Getting all stations for state id %s', state_id)
  all_stations = []
  stations = json.loads(urlfetch.fetch(
      ('http://www.ncdc.noaa.gov/cdo-web/api/v2/stations?locationid=%s&'
       'datasetid=NORMAL_ANN&datatypeid=ANN-TMIN-PRBLST-T32FP10&limit=%s'
       '&offset=%s') % (state_id, 1000, 1),
      headers=NCDC_REQUEST_HEADER,
      deadline=60).content)
  offset = 1
  while 'results' in stations:
    all_stations += stations['results']
    offset += 1000
    stations = json.loads(urlfetch.fetch(
      ('http://www.ncdc.noaa.gov/cdo-web/api/v2/stations?locationid=%s&'
       'datasetid=NORMAL_ANN&datatypeid=ANN-TMIN-PRBLST-T32FP10&limit=%s'
       '&offset=%s') % (state_id, 1000, offset),
      headers=NCDC_REQUEST_HEADER,
      deadline=60).content)
  return all_stations

app = webapp2.WSGIApplication(
    [('/ncdc', NCDC)],
    debug=True)
