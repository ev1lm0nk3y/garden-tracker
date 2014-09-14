import datetime
import json
import logging
import urllib
import webapp2

import garden_common
import garden_dbs
import ncdc

from google.appengine.api import users
from oauth2client.appengine import CredentialsModel
from oauth2client.appengine import StorageByKeyName
from google.appengine.api import memcache
from google.appengine.api import oauth
from google.appengine.api import urlfetch
from google.appengine.ext import ndb

from webapp2_extras import sessions

NCDC = ncdc.NCDC()

class BaseGardenHandler(webapp2.RequestHandler):
  def dispatch(self):
    # Get a session stroe for this request
    self.session_store = sessions.get_store(request=self.request)
    try:
      webapp2.RequestHandler.dispatch(self)
    finally:
      # Save all sessions
      self.session_store.save_sessions(self.response)

  @webapp2.cached_property
  def session(self):
    return self.session_store.get_session()


class AdminConsole(BaseGardenHandler):
  @garden_common.DECORATOR.oauth_required
  def AdminHome(self):
    template = garden_common.JINJA_ENV.get_template('templates/admin.html')
    self.response.write(template.render())

  @garden_common.DECORATOR.oauth_required
  def ShowPlants(self):
    template = garden_common.JINJA_ENV.get_template('templates/admin_plants.html')
    all_plants = garden_dbs.Plants.query().order(garden_dbs.Plants.plant_type,
                                                 garden_dbs.Plants.plant_id)
    template_values = {
        'all_plants': all_plants,
    }
    self.response.write(template.render(template_values))

  @garden_common.DECORATOR.oauth_required
  def AddPlants(self):
    raw_file = self.request.POST.multi['plant_json'].file.read()
    garden_common.ProcessPlants(raw_file)
    self.redirect('/admin/plants', True)


class Authenticate(BaseGardenHandler):
  @garden_common.DECORATOR.oauth_required
  def SignIn(self):
    # find the user in the DB
    http = garden_common.DECORATOR.http()
    user_info = users.get_current_user()
    user = garden_dbs.Users.query(
        garden_dbs.Users.user == user_info).get()
    self.session['session_key'] = garden_common.GetNewSessionKey()
    if not user:
      if garden_common.DECORATOR.has_credentials():
        cred = garden_common.DECORATOR.get_credentials()
        if cred.access_token_expired:
          cred.refresh(http)
      user = garden_dbs.Users(
          user=user_info,
          user_profile=garden_common.GetUserProfile(cred.access_token),
          session_token=self.session.get('session_key'))
    else:
      user.session_token = self.session.get('session_key')
    user.put()
    self.redirect('/mygarden')

  def LogOut(self):
    self.session['session_key'] = None
    self.redirect('/')


class Main(BaseGardenHandler):
  @garden_common.DECORATOR.oauth_aware
  def get(self):
    user = users.get_current_user()
    if not user or not self.session.get('session_key'):
      template = garden_common.JINJA_ENV.get_template('templates/home.html')
      tmpl_val = {
          'signin_url': garden_common.DECORATOR.authorize_url(),
      }
      self.response.write(template.render(tmpl_val))
    else:
      user_query = garden_dbs.Users.query(
          garden_dbs.Users.user == user).get()
      if user_query:
        garden_common.MEMCACHE.add(key=user.user_id() + '_client_session',
                                   value=user_query.session_token,
                                   time=86400)
      self.redirect('/mygarden')


class User(BaseGardenHandler):
  @garden_common.DECORATOR.oauth_required
  def Main(self):
    http = garden_common.DECORATOR.http()
    user_profile = garden_dbs.Users.query(
        garden_dbs.Users.user == users.get_current_user()).get()
    if not user_profile:
      logging.error('No user found, unsetting session_key and redirecting to '
                    'home page')
      self.session['session_key'] = None
      self.redirect('/', body='No User')
    else:
      if self.session.get('session_key') != user_profile.session_token:
        self.redirect('/', body='Session Expired')
      template = garden_common.JINJA_ENV.get_template('templates/user.html')
      gardens = garden_common.MEMCACHE.gets(
          '%s_gardens' % user_profile.user.user_id())
      if not gardens:  # Means there wasn't anything in memcache, so move on.
        gardens = garden_dbs.UserGardenModel.query(
           ndb.AND(
               garden_dbs.UserGardenModel.user_id == user_profile.user.user_id(),
               garden_dbs.UserGardenModel.deleted == False)
        ).fetch()
      if not gardens:
        message = 'You have no gardens currently.'
      else:
        memcache_key = '%s_gardens' % users.get_current_user().user_id()
        memcache.add(key=memcache_key, value=gardens, time=3600)
        message = 'You have %d garden(s).' % len(gardens)
      gprofile = json.loads(user_profile.user_profile)
      all_plants = garden_dbs.Plants.query().order(garden_dbs.Plants.plant_type,
                                                   garden_dbs.Plants.plant_id)
      sorted_gardens = sorted(gardens,
                              key=lambda garden: (garden.year,
                                                  garden.created))
      template_values = {
          'message': message,
          'gardens': sorted_gardens,
          'user': gprofile['name'],
          'photo': gprofile['picture'],
          'email': user_profile.user.email(),
          'all_plants': all_plants,
          'address': gprofile['address'],
          'city': gprofile['city'],
          'state': gprofile['state'],
          'zipcode': gprofile['zipcode'],
          #'admin': oauth.is_current_user_admin(),
      }
      self.response.write(template.render(template_values))

  @garden_common.DECORATOR.oauth_required
  def UpdateProfile(self):
    user = garden_dbs.Users.query(
        garden_dbs.Users.user == users.get_current_user()).get()
    profile = json.loads(user.user_profile)
    if 'state' in profile and profile['state']:
      state_code = NCDC.GetStateCode(profile['state'])
    if ('zipcode' in profile and
        profile['zipcode'] != self.request.get('zipcode')):
      zip_info = json.loads(urlfetch.fetch(
          'http://ziptasticapi.com/%s' % self.request.get('zipcode')).content)
      profile['zipcode'] = self.request.get('zipcode')
      profile['city'] = zip_info['city']
      profile['state'] = zip_info['state']
      state_code = NCDC.GetStateCode(zip_info['state'])
    response_json = json.dumps({
        'city': profile['city'],
        'state': profile['state']})
    if ('address' in profile and
        profile['address'] != self.request.get('address')):
      profile['address'] = self.request.get('address')
    # now just get the lat long data from the address from Google.
    google_maps_url = 'https://maps.googleapis.com/maps/api/geocode/json?%s'
    if profile['address']:
      full_query = google_maps_url % urllib.urlencode({
          'address': '%s,%s' % (profile['address'], profile['zipcode']),
          'sensor': 'false'})
    else:
      full_query = google_maps_url % profile['zipcode']
    gmap_data = json.loads(urlfetch.fetch(full_query).content)
    if ('lat' not in profile or
        profile['lat'] !=
        gmap_data['results'][0]['geometry']['location']['lat'] or
        profile['lng'] != 
        gmap_data['results'][0]['geometry']['location']['lng']):
      profile['lng'] = (
          gmap_data['results'][0]['geometry']['location']['lng'])
      profile['lat'] = (
        gmap_data['results'][0]['geometry']['location']['lat'])
      profile['station'] = NCDC.GetClosestStationId(
          profile['lat'], profile['lng'], NCDC.GetStateStations(state_code))
    user.user_profile = json.dumps(profile)
    user.put()
    self.response.headers['Content-Type'] = 'text/json'
    self.response.write(response_json)

  @garden_common.DECORATOR.oauth_aware
  def CreateGardenForm(self):
    all_plants_ndb = garden_dbs.Plants.query().fetch()
    user = garden_dbs.Users.query(
        garden_dbs.Users.user == users.get_current_user()).get()
    template_values = {
        'profile': json.loads(user.user_profile),
        'all_plants': sorted(all_plants_ndb,
                             key=lambda plant: (plant.plant_type,
                                                plant.plant_id)),
    }
    template = garden_common.JINJA_ENV.get_template(
        'templates/create_garden.html')
    self.response.write(template.render(template_values))

  @garden_common.DECORATOR.oauth_required
  def CreateGardenAction(self):
    http = garden_common.DECORATOR.http()
    plants = self.request.POST.getall('plants')
    cal_info = garden_common.GetOrCreateCalendar(
        garden_common.DECORATOR.http())
    user_garden = garden_dbs.UserGardenModel(
        user_id=users.get_current_user().user_id(),
        calendarId=cal_info['id'],
        title=self.request.POST['garden_title'],
        year=int(self.request.POST['garden_year']))
    user = garden_dbs.Users.query(
        garden_dbs.Users.user == users.get_current_user()).get()
    user_profile = json.loads(user.user_profile)
    last_frost_date = NCDC.GetLastFrostDate(
        user_profile['station'], int(self.request.POST['garden_year']))
    for plant in plants:
      pt, pid = plant.split()
      plantdb_entry = garden_dbs.Plants.query(
          ndb.AND(garden_dbs.Plants.plant_type == pt,
                  garden_dbs.Plants.plant_id == pid)).get()
      indoors_event = {'id': '',
                       'dates': ''}
      outdoors_event = {'id': '',
                        'dates': ''}
      if plantdb_entry.start_indoors.start_week:
        start_datetime = last_frost_date - datetime.timedelta(
            weeks=plantdb_entry.start_indoors.end_week)
        end_datetime = last_frost_date - datetime.timedelta(
            weeks=plantdb_entry.start_indoors.start_week)
        indoors_event['id'] = garden_common.CreateCalendarEntry(
            http_req=http,
            cal_id=cal_info['id'],
            start_date = start_datetime.isoformat(),
            end_date = end_datetime.isoformat(),
            summary = 'Start %s seeds indoors' % pid,
            description = ('This is the time of year to plant your %s seeds '
                           'indoors.') % pid)
        indoors_event['dates'] = '%s to %s' % (start_datetime.isoformat(),
                                               end_datetime.isoformat())
      if plantdb_entry.start_outdoors.start_week:
        start_datetime = last_frost_date + datetime.timedelta(
            weeks=plantdb_entry.start_outdoors.start_week)
        end_datetime = last_frost_date + datetime.timedelta(
            weeks=plantdb_entry.start_outdoors.end_week)
        outdoors_event['id'] = garden_common.CreateCalendarEntry(
            http_req=http,
            cal_id=cal_info['id'],
            start_date = start_datetime.isoformat(),
            end_date = end_datetime.isoformat(),
            summary = 'Start %s outdoors' % pid,
            description = ('Time to plant %s outdoors. Ensure minimum soil '
                           'temperature is at least %s') % (
                                   pid, plantdb_entry.min_soil_temp))
        outdoors_event['dates'] = '%s to %s' % (start_datetime.isoformat(),
                                                end_datetime.isoformat())
      plant_cal_info = garden_dbs.UserPlants(
          plant=plantdb_entry,
          indoor_event_id=indoors_event['id'],
          indoor_dates=indoors_event['dates'],
          outdoor_event_id=outdoors_event['id'],
          outdoor_dates=outdoors_event['dates'])
      user_garden.plants.append(plant_cal_info)
    user_garden.put()
    # delete the cache entry, if it exists, so that we can rebuild the cache
    # entry with this new garden.
    garden_common.MEMCACHE.delete(user.user.user_id() + '_gardens')
    logging.info('User garden created')
    self.response.write('Garden Successfully Created.')

  @garden_common.DECORATOR.oauth_required
  def DeleteGarden(self):
    http = garden_common.DECORATOR.http()
    garden_title = self.request.GET['garden_title']
    # grab the user garden from the NDB.
    user_garden = garden_dbs.UserGardenModel.query(
        ndb.AND(garden_dbs.UserGardenModel.title == garden_title,
                garden_dbs.UserGardenModel.title == garden_title)).get()
    # now remove all entries in the user's calendar.
    if user_garden:
      for plant in user_garden.plants:
        if plant.indoor_event_id:
          logging.info('Removing indoor calendar entry %s', plant.indoor_event_id)
          garden_common.DeleteCalendarEntry(http, plant.indoor_event_id,
                                            user_garden.calendarId)
        if plant.outdoor_event_id:
          logging.info('Removing outdoor calendar entry %s',
                       plant.outdoor_event_id)
          garden_common.DeleteCalendarEntry(http, plant.outdoor_event_id,
                                            user_garden.calendarId)
      logging.info('Removing garden entry from NDB.')
      garden_key = user_garden.key
      garden_key.delete()
    logging.info('Clearing user gardens memcache, forcing memcache to get new '
                 'contents upon reload')
    garden_common.MEMCACHE.delete('%s_gardens' %
                                   users.get_current_user().user_id())
    self.response.write('Garden %s Successfully Deleted.' % garden_title)
