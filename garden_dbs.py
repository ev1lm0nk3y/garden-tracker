import logging
import time

from google.appengine.ext import ndb


class Users(ndb.Model):
  user = ndb.UserProperty(required=True)
  session_token = ndb.StringProperty(required=True)
  user_profile = ndb.JsonProperty(required=True)


class FuzzyDateRange(object):
    def __init__(self, start_week=None, end_week=None):
      if start_week:
        assert isinstance(start_week, int)
      if end_week:
        assert isinstance(end_week, int)
      else:
        if start_week:
          end_week = start_week + 1
      self.start_week = start_week
      self.end_week = end_week

    def __str__(self):
      return '%s - %s' % (self.start_week, self.end_week)

    def __cmp__(self):
      if self.start_week and self.end_week:
        return True
      return False


class FuzzyDateRangeModel(ndb.Model):
    start_week = ndb.IntegerProperty(required=True)
    end_week = ndb.IntegerProperty()


class FuzzyDateRangeProperty(ndb.StructuredProperty):
  def __init__(self, **kwargs):
    super(FuzzyDateRangeProperty, self).__init__(FuzzyDateRangeModel,
                                                 **kwargs)

  def _validate(self, value):
    assert isinstance(value, FuzzyDateRange)

  def _to_base_type(self, value):
    return FuzzyDateRangeModel(start_week=value.start_week,
                               end_week=value.end_week)

  def _from_base_type(self, value):
    return FuzzyDateRange(value.start_week,
                          value.end_week)


class Plants(ndb.Model):
    plant_id = ndb.StringProperty(required=True, name='Plant Name')
    plant_type = ndb.StringProperty(choices=['flower', 'fruit', 'herb',
                                             'vegetable'],
                                    name='Plant Type')
    start_indoors = FuzzyDateRangeProperty(default=None, name='Start seeds indoors')
    start_outdoors = FuzzyDateRangeProperty(default=None,
                                            name='Start seeds outdoors')
    min_soil_temp = ndb.IntegerProperty(name='Minimum Soil Temperature')
    hardness = ndb.StringProperty(name='Cold Hardiness')
    fertilize = ndb.StringProperty(name='When to Fertalize')
    water = ndb.StringProperty(name='How much to water')
    light = ndb.StringProperty(name='How much light')
    picture = ndb.StringProperty(default=None)
    notes = ndb.TextProperty()

    @classmethod
    def query_plant(cls, plant_name):
        return cls.query(cls.plant_id == plant_name).get()


# For User Gardens
class UserPlants(object):
  def __init__(self, plant, indoor_event_id='', outdoor_event_id='',
               indoor_dates='', outdoor_dates=''):
    assert isinstance(plant, Plants)
    self.plant = plant
    self.indoor_event_id = str(indoor_event_id)
    self.indoor_dates = indoor_dates
    self.outdoor_event_id = str(outdoor_event_id)
    self.outdoor_dates = outdoor_dates


class UserPlantModel(ndb.Model):
  plant = ndb.StructuredProperty(Plants, required=True)
  indoor_event_id = ndb.StringProperty(default=None)
  outdoor_event_id = ndb.StringProperty(default=None)
  indoor_dates = ndb.StringProperty(default=None)
  outdoor_dates = ndb.StringProperty(default=None)


class UserPlantProperty(ndb.StructuredProperty):
  def __init__(self, **kwargs):
    super(UserPlantProperty, self).__init__(UserPlantModel, **kwargs)

  def _validate(self, value):
    assert isinstance(value, UserPlants)

  def _to_base_type(self, value):
    return UserPlantModel(plant=value.plant,
                          indoor_event_id=value.indoor_event_id,
                          outdoor_event_id=value.outdoor_event_id,
                          indoor_dates=value.indoor_dates,
                          outdoor_dates=value.outdoor_dates)

  def _from_base_type(self, value):
    return UserPlants(value.plant,
                      value.indoor_event_id,
                      value.outdoor_event_id,
                      value.indoor_dates,
                      value.outdoor_dates)


class UserGardenModel(ndb.Model):
  user_id = ndb.StringProperty(indexed=True, required=True)
  title = ndb.StringProperty(required=True)
  calendarId = ndb.StringProperty(required=True)
  year = ndb.IntegerProperty()
  plants = UserPlantProperty(repeated=True)
  created = ndb.DateTimeProperty(indexed=True, auto_now_add=True)
  deleted = ndb.BooleanProperty(indexed=True, default=False)
