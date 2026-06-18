from machine import Pin
import dht
import time


sensor = dht.DHT11(Pin(4, pull=Pin.PULL_UP))

for index in range(5):
    try:
        sensor.measure()
        temperature = sensor.temperature()
        humidity = sensor.humidity()
        print("sample={},temperature={},humidity={}".format(index + 1, temperature, humidity))
    except Exception as exc:
        print("sample={},error={}".format(index + 1, exc))
    time.sleep(2)
