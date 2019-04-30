Holiday(Hagg/YomTov) Times and Holidays name with HomeAssistant Sensor Custom Component


Guide How to use it
Requirements:

all db now downloading to local json file and once a day the db check for change
no need anymore for geoid and latitude and longitude . the sensor got it from HA config , so you need to besure that you put them in configuration.yaml . also need the TimeZone see link : https://www.home-assistant.io/blog/2015/05/09/utc-time-zone-awareness/ Example :
```
homeassistant:
  latitude: 32.0667
  longitude: 34.7667
  time_zone: Asia/Jerusalem
 ```
please check it before run it.

Now you need to create folder "holiday" in your HomeAssistant config/custom_components folder
Copy python file "sensor.py" to the HA config ./custom_components/holiday/ folder.
Now you need to add those lines in configuration.yaml :
```
sensor:
  - platform: holiday
    havdalah_calc: 42
    time_before_check: 10
    time_after_check: 1
    resources:
      - yom_tov_in
      - yom_tov_out
      - is_yom_tov
      - yom_tov_name
      - holiday_name
``` 
Entity Optional
havdalah_calc = By defaule he get 42 Min , you can set 50Min or 72Min for other methods

time_before_check: By defaule he get 10 Min , you can set minutes so the sensor can check if is holiday yomtov

time_after_check: By defaule he get 10 Min , you can set minutes so the sensor can check if holiday yomtov is ends..

in ui-lovelace.yaml :
```
- id: 
  type: entities
  title: חג / יום טוב
  show_header_toggle: false
  entities:
    - sensor.holiday_holiday_name
    - sensor.holiday_yom_tov_in
    - sensor.holiday_yom_tov_out
    - sensor.holiday_yom_tov_name
    - input_boolean.holiday
```
All sensors icon already set , but you can always customize them..
Good Luck !
