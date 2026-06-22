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
CLIENT_MAX_RECORDS = 3


def wifi_status_name(status):
    names = {
        1000: "IDLE",
        1001: "CONNECTING",
        1010: "GOT_IP",
        200: "BEACON_TIMEOUT",
        201: "NO_AP_FOUND",
        202: "AUTH_PENDING_OR_WRONG_PASSWORD",
        203: "ASSOC_FAIL",
        204: "HANDSHAKE_TIMEOUT",
        210: "NO_COMPATIBLE_SECURITY",
        211: "NO_AP_AUTHMODE_THRESHOLD",
        212: "NO_AP_RSSI_THRESHOLD",
    }
    return names.get(status, str(status))


def connect_wifi(ssid, wifi_key):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(False)
    time.sleep(1)
    wlan.active(True)
    time.sleep(2)
    while not wlan.isconnected():
        print("wifi connecting ssid={}".format(ssid))
        try:
            wlan.connect(ssid, wifi_key)
        except Exception as exc:
            print("wifi connect error {}".format(exc))
            time.sleep(5)
            continue
        for retry in range(45):
            if wlan.isconnected():
                break
            status = wlan.status()
            print("wifi retry {} status={} {}".format(retry + 1, status, wifi_status_name(status)))
            time.sleep(1)
        if not wlan.isconnected():
            wlan.disconnect()
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
    sample_seq = 0

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(2)
    print("weather station started station={} port={} dht_pin={}".format(STATION_NAME, PORT, DHT_PIN))

    while True:
        conn, addr = server.accept()
        print("client connected {}".format(addr))
        try:
            for _ in range(CLIENT_MAX_RECORDS):
                sample_seq += 1
                temperature, humidity = read_dht11(sensor)
                line = "{},{},{},{},{}\n".format(STATION_ID, STATION_NAME, temperature, humidity, sample_seq)
                conn.send(line.encode("utf-8"))
                print("send {}".format(line.strip()))
                time.sleep(1)
            print("client record limit reached, rotate connection")
        except Exception as exc:
            print("client disconnected {}".format(exc))
        finally:
            conn.close()


main()
