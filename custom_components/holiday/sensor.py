"""
Platform to get Holiday Times And Holiday information for Home Assistant.

Document will come soon...
"""
import logging
import urllib
import json
import codecs
import pathlib
import datetime
import time
import voluptuous as vol
from homeassistant.components.sensor import PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    CONF_LATITUDE, CONF_LONGITUDE, CONF_RESOURCES)
from homeassistant.helpers.entity import Entity
from homeassistant.core import callback
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.components.sensor import ENTITY_ID_FORMAT

_LOGGER = logging.getLogger(__name__)

SENSOR_PREFIX = 'Holiday '
HAVDALAH_MINUTES = 'havdalah_calc'
TIME_BEFORE_CHECK = 'time_before_check'
TIME_AFTER_CHECK = 'time_after_check'

SENSOR_TYPES = {
    'yom_tov_in': ['yom_tov_in', 'mdi:candle'],
    'yom_tov_out': ['yom_tov_out', 'mdi:exit-to-app'],
    'is_yom_tov': ['is_yom_tov', 'mdi:candle'],
    'yom_tov_name': ['yom_tov_name', 'mdi:book-open-variant'],
    'holiday_name': ['holiday_name', 'mdi:book-open-variant'],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_LATITUDE): cv.latitude,
    vol.Optional(CONF_LONGITUDE): cv.longitude,
    vol.Optional(HAVDALAH_MINUTES, default=42): int,
    vol.Optional(TIME_BEFORE_CHECK, default=10): int,
    vol.Optional(TIME_AFTER_CHECK, default=10): int,
    vol.Required(CONF_RESOURCES, default=[]):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
})


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up the holiday config sensors."""
    havdalah = config.get(HAVDALAH_MINUTES)
    latitude = config.get(CONF_LATITUDE, hass.config.latitude)
    longitude = config.get(CONF_LONGITUDE, hass.config.longitude)
    time_before = config.get(TIME_BEFORE_CHECK)
    time_after = config.get(TIME_AFTER_CHECK)

    if None in (latitude, longitude):
        _LOGGER.error("Latitude or longitude not set in Home Assistant config")
        return

    entities = []

    for resource in config[CONF_RESOURCES]:
        sensor_type = resource.lower()
        if sensor_type not in SENSOR_TYPES:
            SENSOR_TYPES[sensor_type] = [
                sensor_type.title(), '', 'mdi:flash']
        entities.append(Holiday(hass, sensor_type, hass.config.time_zone, latitude, longitude,
                                havdalah, time_before, time_after))
    async_add_entities(entities, False)


class Holiday(Entity):
    """Create Holiday sensor."""
    holiday_db = []
    yomtov_db = []
    holiday_in = None
    holiday_out = None
    file_time_stamp = None
    sunday = None
    saturday = None
    config_path = None

    def __init__(self, hass, sensor_type, timezone, latitude, longitude,
                 havdalah, time_before, time_after):
        """Initialize the sensor."""
        self.type = sensor_type
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT,
            '_'.join([SENSOR_PREFIX, SENSOR_TYPES[self.type][0]]), hass=hass)
        self._latitude = latitude
        self._longitude = longitude
        self._timezone = timezone
        self._havdalah = havdalah
        self._time_before = time_before
        self._time_after = time_after
        self.config_path = hass.config.path() + "/custom_components/holiday/"
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return SENSOR_PREFIX + SENSOR_TYPES[self.type][0]

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return SENSOR_TYPES[self.type][1]

    @property
    def should_poll(self):
        """Return true if the device should be polled for state updates"""
        return True

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    async def async_update(self):
        """Update our sensor state."""
        await self.update_db()
        type_to_func = {
            'yom_tov_in': self.get_time_in,
            'yom_tov_out': self.get_time_out,
            'is_yom_tov': self.is_yom_tov,
            'yom_tov_name': self.get_yom_tov_name,
            'holiday_name': self.get_holiday_name
        }
        self._state = await type_to_func[self.type]()

        await self.async_update_ha_state()

    async def create_db_file(self):
        """Create the json db."""
        import astral
        self.yomtov_db = []
        self.holiday_db = []
        self.set_days()
        self.file_time_stamp = datetime.date.today()
        convert = [{"date": str(self.file_time_stamp), "sunday": str(self.sunday), "saturday": str(self.saturday)}]
        with codecs.open(self.config_path + 'date_update.json', 'w', encoding='utf-8') as outfile:
            json.dump(convert, outfile, skipkeys=False, ensure_ascii=False, indent=4,
                      separators=None, default=None, sort_keys=True)
        try:
            with urllib.request.urlopen(
                    "https://www.hebcal.com/hebcal/?v=1&cfg=fc&start="
                    + str(self.sunday) + "&end=" + str(self.saturday)
                    + "&maj=on&min=on&nx=on&mf=on&ss=on&mod=on&s=on&c=on"
                    + "&o=on&i=on&geo=pos&latitude=" + str(self._latitude)
                    + "&longitude=" + str(self._longitude)
                    + "&tzid=" + str(self._timezone)
                    + "&m=" + str(self._havdalah) + "&lg=h"
            ) as holiday_url:
                holiday_data = json.loads(holiday_url.read().decode())
            havdalah_count = 0
            candles_count = 0
            for extract_data in holiday_data:
                if "candles" in extract_data.values():
                    day = datetime.datetime.strptime(extract_data['start'], '%Y-%m-%dT%H:%M:%S').isoweekday()
                    if day is not 5 and day is not 6:
                        candles_count += 1
                        self.yomtov_db.append(extract_data)
                    elif day is 6 and candles_count is 0:
                        candles_time = str(datetime.datetime.strptime(extract_data['start'], '%Y-%m-%dT%H:%M:%S')
                                           - datetime.timedelta(minutes=60)).replace(" ", "T")
                        self.yomtov_db.append({'className': 'candles', 'hebrew': 'הדלקת נרות', 'start': candles_time,
                                               'allDay': False, 'title': 'הדלקת נרות'})
                        candles_count += 1
                elif 'holiday yomtov' in extract_data.values():
                    self.yomtov_db.append(extract_data)
                elif "havdalah" in extract_data.values():
                    if datetime.datetime.strptime(extract_data['start'], '%Y-%m-%dT%H:%M:%S').isoweekday() is not 6:
                        havdalah_count += 1
                        self.yomtov_db.append(extract_data)
                elif "parashat" not in extract_data.values():
                    sunset = astral.Location(('', '', float(self._latitude), float(self._longitude), 'Asia/Jerusalem'))
                    start = datetime.datetime.strptime(str(extract_data['start'][:10]), '%Y-%m-%d').date() \
                            - datetime.timedelta(days=1)
                    end = datetime.datetime.strptime(str(extract_data['start'][:10]), '%Y-%m-%d').date()
                    extract_data['start'] = str(start) + "T" + str(sunset.sun(start).get('sunset'))[11:19]
                    extract_data['end'] = str(end) + "T" + str(sunset.sun(end).get('sunset'))[11:19]
                    self.holiday_db.append(extract_data)
            if self.yomtov_db:
                for extract_data in self.yomtov_db:
                    if "havdalah" in extract_data.values() and candles_count is 0:
                        candles_time = str(datetime.datetime.strptime(extract_data['start'], '%Y-%m-%dT%H:%M:%S')
                                           - datetime.timedelta(days=1) - datetime.timedelta(minutes=65)).replace(" ", "T")
                        self.yomtov_db.append({'className': 'candles', 'hebrew': 'הדלקת נרות', 'start': candles_time,
                                               'allDay': False, 'title': 'הדלקת נרות'})
                    elif "candles" in extract_data.values() and havdalah_count is 0:
                        havdalah_time = str(datetime.datetime.strptime(extract_data['start'], '%Y-%m-%dT%H:%M:%S')
                                            + datetime.timedelta(days=1) + datetime.timedelta(minutes=65)).replace(" ", "T")
                        self.yomtov_db.append({'hebrew': 'הבדלה - 42 דקות', 'start': havdalah_time, 'className': 'havdalah',
                                               'allDay': False, 'title': 'הבדלה - 42 דקות'})
            else:
                self.yomtov_db.append({"status:": "db empty"})
            with codecs.open(self.config_path + 'yomtov_data.json', 'w', encoding='utf-8') as outfile:
                json.dump(self.yomtov_db, outfile, skipkeys=False, ensure_ascii=False, indent=4,
                          separators=None, default=None, sort_keys=True)
            with codecs.open(self.config_path + 'holiday_data.json', 'w', encoding='utf-8') as outfile:
                json.dump(self.holiday_db, outfile, skipkeys=False, ensure_ascii=False, indent=4,
                          separators=None, default=None, sort_keys=True)
        finally:
            self.yomtov_db = self.yomtov_db
            self.holiday_db = self.holiday_db

    async def update_db(self):
        """Update the db."""
        if not pathlib.Path(self.config_path + 'yomtov_data.json').is_file() or \
                not pathlib.Path(self.config_path + 'holiday_data.json').is_file() or \
                not pathlib.Path(self.config_path + 'date_update.json').is_file():
            await self.create_db_file()
        elif not self.yomtov_db or not self.holiday_db or self.file_time_stamp is None:
            with open(self.config_path + 'yomtov_data.json', encoding='utf-8') as data_file:
                self.yomtov_db = json.loads(data_file.read())
            with open(self.config_path + 'holiday_data.json', encoding='utf-8') as data_file:
                self.holiday_db = json.loads(data_file.read())
            with open(self.config_path + 'date_update.json', encoding='utf-8') as data_file:
                data = json.loads(data_file.read())
                self.file_time_stamp = datetime.datetime.strptime(data[0]['date'], '%Y-%m-%d').date()
                if self.file_time_stamp != datetime.date.today():
                    await self.create_db_file()
        elif self.file_time_stamp != datetime.date.today():
            await self.create_db_file()
        await self.get_full_time_in()
        await self.get_full_time_out()

    @callback
    def set_days(self):
        """Set the friday and saturday."""
        weekday = self.set_sunday(datetime.date.today().isoweekday())
        self.sunday = datetime.date.today() + datetime.timedelta(days=weekday)
        self.saturday = datetime.date.today() + datetime.timedelta(
            days=weekday + 6)

    @classmethod
    def set_sunday(cls, day):
        """Set friday day."""
        switcher = {
            7: 0,  # sunday
            1: -1,  # monday
            2: -2,  # tuesday
            3: -3,  # wednesday
            4: -4,  # thursday
            5: -5,  # friday
            6: -6,  # saturday
        }
        return switcher.get(day)

    # get holiday entrace
    async def get_time_in(self):
        """Get holiday entrace."""
        result = ''
        for extract_data in self.yomtov_db:
            if "candles" in extract_data.values():
                result = extract_data['start'][11:16]
        if self.is_time_format(result):
            return result
        return 'None'

    # get holiday time exit
    async def get_time_out(self):
        """Get holiday time exit."""
        result = ''
        for extract_data in self.yomtov_db:
            if "havdalah" in extract_data.values():
                result = extract_data['start'][11:16]
        if self.is_time_format(result):
            return result
        return 'None'

    async def get_full_time_in(self):
        """Get full time entrace holiday for check if is holiday now."""
        for extract_data in self.yomtov_db:
            if "candles" in extract_data.values():
                is_in = extract_data['start']
        try:
            self.holiday_in = datetime.datetime.strptime(
                is_in, '%Y-%m-%dT%H:%M:%S')
            self.holiday_in = self.holiday_in - datetime.timedelta(
                minutes=int(self._time_before))
        except:
            self.holiday_in = self.holiday_in

    # get full time exit holiday for check if is holiday now
    async def get_full_time_out(self):
        """Get full time exit holiday for check if is holiday now."""
        for extract_data in self.yomtov_db:
            if "havdalah" in extract_data.values():
                is_out = extract_data['start']
        try:
            self.holiday_out = datetime.datetime.strptime(
                is_out, '%Y-%m-%dT%H:%M:%S')
            self.holiday_out = self.holiday_out + datetime.timedelta(
                minutes=int(self._time_after))
        except:
            try:
                self.holiday_out = datetime.datetime.strptime(
                    self.holiday_in, '%Y-%m-%dT%H:%M:%S') + datetime.timedelta(days=1) \
                                   + datetime.timedelta(minutes=65)
            except:
                self.holiday_out = self.holiday_out
        if self.holiday_out is None:
            self.holiday_out = self.holiday_out

    # check if is holiday now / return true or false
    async def is_yom_tov(self):
        """Check if is holiday now / return true or false."""
        if self.holiday_in is not None and self.holiday_out is not None:
            if (self.holiday_in.replace(tzinfo=None) <
                    datetime.datetime.today() < self.holiday_out.replace(tzinfo=None)):
                return 'True'
            return 'False'
        return 'False'

    async def get_yom_tov_name(self):
        """Get yomtov name."""
        for extract_data in self.yomtov_db:
            if 'holiday yomtov' in extract_data.values():
                date = datetime.datetime.strptime(extract_data['start'], '%Y-%m-%d').date()
                return self.heb_day_convert(date.isoweekday()) + " " + extract_data['hebrew']
        return "לא נמצא יום טוב"

    async def get_holiday_name(self):
        """Get holiday name."""
        result = self.heb_day_str()
        for extract_data in self.holiday_db:
            start = datetime.datetime.strptime(str(extract_data['start']), '%Y-%m-%dT%H:%M:%S')
            end = datetime.datetime.strptime(str(extract_data['end']), '%Y-%m-%dT%H:%M:%S')
            if start < datetime.datetime.today() < end:
                result = result + " " + extract_data['hebrew']
        return result

    @classmethod
    def heb_day_str(cls):
        """Set hebrew day."""
        switcher = {
            7: "יום ראשון, ",
            1: "יום שני, ",
            2: "יום שלישי, ",
            3: "יום רביעי, ",
            4: "יום חמישי, ",
            5: "יום שישי, ",
            6: "יום שבת, ",
        }
        return switcher.get(datetime.datetime.today().isoweekday())

    @callback
    def heb_day_convert(self, day):
        """Set hebrew day."""
        switcher = {
            7: "יום ראשון, ",
            1: "יום שני, ",
            2: "יום שלישי, ",
            3: "יום רביעי, ",
            4: "יום חמישי, ",
            5: "יום שישי, ",
            6: "יום שבת, ",
        }
        return switcher.get(day)

    # check if the time is correct
    @classmethod
    def is_time_format(cls, input_time):
        """Check if the time is correct."""
        try:
            time.strptime(input_time, '%H:%M')
            return True
        except ValueError:
            return False
