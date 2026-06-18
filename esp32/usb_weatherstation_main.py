from machine import Pin
import dht
import time


STATION_ID = "tangshan"
STATION_NAME = "唐山"
DHT_PIN = 4


def main():
    sensor = dht.DHT11(Pin(DHT_PIN, pull=Pin.PULL_UP))
    print("usb weather station started station={} dht_pin={}".format(STATION_NAME, DHT_PIN))
    while True:
        try:
            sensor.measure()
            temperature = sensor.temperature()
            humidity = sensor.humidity()
            print("{},{},{},{}".format(STATION_ID, STATION_NAME, temperature, humidity))
        except Exception as exc:
            print("error,{},{}".format(type(exc).__name__, exc))
        time.sleep(1)


main()
