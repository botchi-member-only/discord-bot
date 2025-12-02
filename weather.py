import openmeteo_requests
import requests_cache
import pandas as pd
from retry_requests import retry
import re
# Open-Meteo APIの設定
cache_session = requests_cache.CachedSession('.cache', expire_after=3600)
retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
openmeteo = openmeteo_requests.Client(session=retry_session)
#緯度
citycodes_latitude = {
    "札幌": '43.0667',
    "仙台": '38.2667',
    "新潟": '37.8864',
    "さいたま": '35.9081',
    "東京": '35.6895',
    "横浜": '35.4659',
    "金沢": '36.6',
    "静岡": '34.9833',
    "名古屋": '35.1815',
    "三重": '34.7333',
    "大阪": '34.6937',
    "広島": '34.4',
    "高知": '33.5048',
    "福岡": '33.6',
    "那覇": '26.2167',
    "シアトル": '47.6062',
	"ブカレスト": '44.4267',
    "シーランド公国": '51.89528',#ここからネタ枠
    "ロンドン": '51.5085',#ここからネタ枠
    "西表島": '24.3333',#ここからネタ枠
    "志布志市志布志町志布志": '31.476'#ここからネタ枠
}
#経度
citycodes_longitude = {
    "札幌": '141.35',
    "仙台": '140.8667',
    "新潟": '139.0059',
    "さいたま": '139.6566',
    "東京": '139.6917',
    "横浜": '139.6223',
    "金沢": '136.6167',
    "静岡": '138.3833',
    "名古屋": '136.9064',
    "三重": '136.5167',
    "大阪": '135.5022',
    "広島": '132.45',
    "高知": '133.4447',
    "福岡": '130.4167',
    "那覇": '127.6833',
    "シアトル": '-122.3321',
	"ブカレスト": '26.1025',
    "シーランド公国": '1.48056',#ここからネタ枠
    "ロンドン": '-0.1257',#ここからネタ枠
    "西表島": '24.3333',#ここからネタ枠
    "志布志市志布志町志布志": '131.1011'#ここからネタ枠
}
def on_message(reg_res):
    if reg_res.group(1) in citycodes_latitude.keys():
      citycode_latitude = citycodes_latitude[reg_res.group(1)]
      citycode_longitude = citycodes_longitude[reg_res.group(1)]
      url = "https://api.open-meteo.com/v1/forecast"
      params = {
      "latitude": citycode_latitude,  # 東京の緯度
      "longitude": citycode_longitude,  # 東京の経度
      "daily": ["temperature_2m_min", "temperature_2m_max"],
	  "hourly": "precipitation_probability",
	  "current": ["precipitation", "temperature_2m", "relative_humidity_2m", "wind_speed_10m", "wind_direction_10m", "cloud_cover"],
      "forecast_days": 1,
      "wind_speed_unit": "ms",
      "timezone": "Asia/Tokyo"
      }
      responses = openmeteo.weather_api(url, params=params)
      response = responses[0]
      # 最新の天気データを取得
      current = response.Current()
      current_precipitation = current.Variables(0).Value()
      current_temperature_2m = current.Variables(1).Value()
      current_relative_humidity_2m = current.Variables(2).Value()
      current_wind_speed_10m = current.Variables(3).Value()
      current_wind_direction_10m = current.Variables(4).Value()
      current_cloud_cover  = current.Variables(5).Value()
      # 風向きを変換
      wind_directions = ["北", "北北東", "北東", "東北東", "東", "東南東", "南東", "南南東",
                    "南", "南南西", "南西", "西南西", "西", "西北西", "北西", "北北西"]
      wind_dir_text = wind_directions[int((current_wind_direction_10m + 11.25) / 22.5) % 16]
      #時間ごと
      hourly = response.Hourly()
      hourly_precipitation_probability = hourly.Variables(0).ValuesAsNumpy()[0]
      #日ごと
      daily = response.Daily()
      daily_temperature_2m_min = daily.Variables(0).ValuesAsNumpy()[0]
      daily_temperature_2m_max = daily.Variables(1).ValuesAsNumpy()[0]
      # Discordに天気情報を送信
      weather_message = (
        f"📍 **{reg_res.group(1)}の天気情報**\n"
        f"🌡 気温: {current_temperature_2m:.1f}°C\n"
        f"🌞 最高気温: {daily_temperature_2m_max:.1f}°C\n"
        f"❄️ 最低気温: {daily_temperature_2m_min:.1f}°C\n"
        f"💧 湿度: {current_relative_humidity_2m:.1f}%\n"
        f"☔ 降水量: {current_precipitation:.1f} mm\n"
        f"🌧️ 降水確率: {hourly_precipitation_probability:.1f}%\n"
        f"💨 風速: {current_wind_speed_10m:.1f} m/s\n"
        f"🧭 風向: {wind_dir_text} ({current_wind_direction_10m:.1f}°)\n"
        f"⛅ 雲量: {current_cloud_cover:.1f}%\n"
        f"-# 緯度: {citycode_latitude}° 経度: {citycode_longitude}°"
      )
      return weather_message
    else:
      return 'そこの天気はわからないです．．．'
