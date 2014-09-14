import httplib2
import jinja2
import json
import logging
import os
import random
import string
import urllib2
import webapp2

import garden_dbs

from apiclient import discovery
from oauth2client import appengine
from oauth2client import client

from google.appengine.api import app_identity
from google.appengine.api import memcache
from google.appengine.api import urlfetch
from google.appengine.ext import ndb


# Jinja Environment, should be the same across the whole app
JINJA_ENV = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'])

CLIENT_SECRETS = os.path.join(os.path.dirname(__file__),
                              'client_secrets.json')
MISSING_CLIENT_SECRETS_MESSAGE = """
<h1>Warning: Please configure OAuth 2.0</h1>
<p>
To make this sample run you will need to populate the client_secrets.json file
found at:
</p>
<p>
<code>%s</code>.
</p>
<p>with information found on the <a
href="https://code.google.com/apis/console">APIs Console</a>.
</p>
""" % CLIENT_SECRETS

HTTP = httplib2.Http(memcache)
CALENDAR_SERVICE = discovery.build('calendar', 'v3', http=HTTP)
DECORATOR = appengine.oauth2decorator_from_clientsecrets(
    CLIENT_SECRETS,
    scope=[
      'https://www.googleapis.com/auth/calendar',
      'https://www.googleapis.com/auth/calendar.readonly',
      'https://www.googleapis.com/auth/userinfo.profile',
    ],
    message=MISSING_CLIENT_SECRETS_MESSAGE)

MEMCACHE = memcache.Client()
SESSION_KEY = ('\xd8\xc5)\xd4\x0c\x1a\x90\xf7\xa8,J\xc3\xc3`s=\x18y`J\xea\xab'
               '\x03\xa3\x85IN\xd98\x9c\xfd\x95\xc3\x86\x87\xdb\xe3\xcd\x11'
               '\xe4V\xab\xda$o\x14\x04q\xa1=\xce\xeeI\x8b5\xb7\xb64\xbe\x18'
               '\x9b\x02Z\x8e')
HASH_KEY = ('\xd6\xb9?\xfd8\xf7c\xaeI3\xaf\xe5\x91\xe3\xa1\x12\xca\x90\xd3\x00'
            '\x02\xc0<\xbd\x943\xa1\x04=\xd6\x9f\xca\xf2\x80\\-\xb3\x96\xd59<'
            '\x08\x03\x16\xd9K\xf1 \x11\x0ehs\xa8U\xb2\xdd\xb7\x1d\xaf\x98q'
            '\x12/\x9c')
EARTH_RADIUS = 6371

def GetNewSessionKey():
  return ''.join(random.choice(string.ascii_uppercase + string.digits)
                               for x in xrange(32))

def GetUserProfile(access_token):
  response = urlfetch.fetch(
      'https://www.googleapis.com/oauth2/v1/userinfo?access_token=%s' % \
          access_token,
      method=urlfetch.GET)
  if response.status_code == 200:
    profile = json.loads(response.content)
    profile.update({
        'address': '',
        'city': '',
        'state': '',
        'zipcode': ''})
    return json.dumps(profile)
  raise Exception('Call Failed. Status: %s, Body: %s' % (response.status_code,
                                                         response.content))

def GetOrCreateCalendar(http_req):
  all_cal_json = CALENDAR_SERVICE.calendarList().list().execute(http=http_req)
  calendar_info = None
  for calendar in all_cal_json['items']:
    if 'Garden Tracker' in calendar['summary']:
      calendar_info = calendar
      break
  if not calendar_info:
    request_body={
        'summary': 'Garden Tracker',
        'description': 'Track the plants in your garden'
    }
    calendar_info = CALENDAR_SERVICE.calendars().insert(
        body=request_body).execute(http=http_req)
  return calendar_info


def CreateCalendarEntry(http_req, cal_id, start_date, end_date, **kwargs):
  request_body = {
      'start': {
          'date': start_date,
      },
      'end': {
          'date': end_date,
      }
  }
  if 'description' in kwargs:
    request_body['description'] = kwargs['description']
  if 'summary' in kwargs:
    request_body['summary'] = kwargs['summary']
  create_event = CALENDAR_SERVICE.events().insert(
      calendarId=cal_id, body=request_body).execute(http=http_req)
  return create_event['id']


def DeleteCalendarEntry(http, event_id, cal_id):
  try:
    CALENDAR_SERVICE.events().delete(calendarId=cal_id,
                                     eventId=event_id).execute(http=http)
  except:
    logging.warn('event or calendar do not exist, printing this for your info')


def ProcessPlants(raw_file):
  """Takes a JSON formated file and makes Plants entries."""
  plants_json = json.loads(raw_file)
  for plant_type, plants in plants_json['plants'].iteritems():
    for plant_info in plants:
      plant = garden_dbs.Plants.query(
          ndb.AND(
              garden_dbs.Plants.plant_type == str(plant_type),
              garden_dbs.Plants.plant_id == str(plant_info['name']))).get()
      if not plant:
        plant = garden_dbs.Plants(
            plant_type=str(plant_type),
            plant_id=str(plant_info['name']))
      plant.min_soil_temp = plant_info['min_temp']
      plant.hardness = str(plant_info['hardness'])
      plant.fertilize = str(plant_info['fertilize'])
      plant.water = str(plant_info['water'])
      plant.start_indoors = garden_dbs.FuzzyDateRange(
          plant_info['start_in_week'],
          plant_info['end_in_week'])
      plant.start_outdoors = garden_dbs.FuzzyDateRange(
          plant_info['start_out_week'],
          plant_info['end_out_week'])
      plant.picture = plant_info['picture']
      plant.notes = plant_info['notes']
      plant.put()
