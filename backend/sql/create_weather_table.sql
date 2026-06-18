DROP TABLE IF EXISTS weather_table;

CREATE EXTERNAL TABLE weather_table (
  collect_time STRING COMMENT '采集时间',
  station_id STRING COMMENT '站点 ID',
  station_name STRING COMMENT '站点名称',
  temperature DOUBLE COMMENT '温度，摄氏度',
  humidity DOUBLE COMMENT '相对湿度，百分比',
  pressure DOUBLE COMMENT '地面气压，hPa',
  wind_speed DOUBLE COMMENT '10 米风速，m/s',
  wind_direction DOUBLE COMMENT '10 米风向，角度',
  weather_code INT COMMENT 'Open-Meteo 天气代码'
)
ROW FORMAT DELIMITED
FIELDS TERMINATED BY ','
LOCATION '/weathertextdb';

SELECT station_name, COUNT(*) AS records
FROM weather_table
GROUP BY station_name
ORDER BY station_name;

SELECT *
FROM weather_table
ORDER BY collect_time, station_id
LIMIT 5;
