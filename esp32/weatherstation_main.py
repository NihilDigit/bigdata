from machine import Pin
import dht
import network
import socket
import time


SSID = "YOUR_WIFI_SSID"
WIFI_KEY = "YOUR_WIFI_KEY"
STATION_ID = "tangshan"
STATION_NAME = "唐山"
HOST = "0.0.0.0"
PORT = 8080
DHT_PIN = 4


def connect_wifi(ssid, wifi_key):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    while not wlan.isconnected():
        print("wifi connecting ssid={}".format(ssid))
        try:
            wlan.disconnect()
            time.sleep(0.3)
            wlan.connect(ssid, wifi_key)
        except Exception as exc:
            print("wifi connect error {}".format(exc))
            time.sleep(5)
            continue
        for retry in range(10):
            if wlan.isconnected():
                break
            print("wifi retry {}".format(retry + 1))
            time.sleep(1)
        if not wlan.isconnected():
            print("wifi not connected, retry after 5s")
            time.sleep(5)
    ipaddr = wlan.ifconfig()[0]
    print("wifi connected ip={}".format(ipaddr))
    return ipaddr


def read_dht11(sensor):
    sensor.measure()
    temperature = sensor.temperature()
    humidity = sensor.humidity()
    return temperature, humidity


def main():
    connect_wifi(SSID, WIFI_KEY)
    sensor = dht.DHT11(Pin(DHT_PIN, pull=Pin.PULL_UP))

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(2)
    print("weather station started station={} port={} dht_pin={}".format(STATION_NAME, PORT, DHT_PIN))

    while True:
        conn, addr = server.accept()
        print("client connected {}".format(addr))
        try:
            while True:
                temperature, humidity = read_dht11(sensor)
                line = "{},{},{},{}\n".format(STATION_ID, STATION_NAME, temperature, humidity)
                conn.send(line.encode("utf-8"))
                print("send {}".format(line.strip()))
                time.sleep(1)
        except Exception as exc:
            print("client disconnected {}".format(exc))
            conn.close()


main()
