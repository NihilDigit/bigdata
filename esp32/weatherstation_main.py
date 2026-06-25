from machine import Pin
import dht
import network
import socket
import time
import ujson


SSID = "YOUR_WIFI_SSID"
WIFI_KEY = "YOUR_WIFI_KEY"
STATION_ID = "tangshan"
STATION_NAME = "唐山"
SERVER_HOST = "YOUR_SERVER_HOST"
SERVER_PORT = 8080
SERVER_PATH = "/"
DHT_PIN = 4


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
    return sensor.temperature(), sensor.humidity()


def connect_ws():
    print("websocket resolve host={} port={}".format(SERVER_HOST, SERVER_PORT))
    addr = socket.getaddrinfo(SERVER_HOST, SERVER_PORT)[0][-1]
    print("websocket connect addr={}".format(addr))
    sock = socket.socket()
    sock.settimeout(3)
    sock.connect(addr)
    print("websocket tcp connected")
    key = "dGhlIHNhbXBsZSBub25jZQ=="
    request = (
        "GET {} HTTP/1.1\r\n"
        "Host: {}:{}\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        "Sec-WebSocket-Key: {}\r\n"
        "Sec-WebSocket-Version: 13\r\n"
        "\r\n"
    ).format(SERVER_PATH, SERVER_HOST, SERVER_PORT, key)
    print("websocket send handshake")
    sock.send(request.encode("utf-8"))
    response = b""
    while b"\r\n\r\n" not in response:
        print("websocket wait handshake response bytes={}".format(len(response)))
        chunk = sock.recv(256)
        if not chunk:
            break
        response += chunk
    if b" 101 " not in response.split(b"\r\n", 1)[0]:
        sock.close()
        raise RuntimeError("websocket handshake failed: {}".format(response[:80]))
    print("websocket connected {}:{}".format(SERVER_HOST, SERVER_PORT))
    return sock


def send_ws_text(sock, text, seq):
    payload = text.encode("utf-8")
    length = len(payload)
    if length < 126:
        header = bytes([0x81, 0x80 | length])
    elif length < 65536:
        header = bytes([0x81, 0x80 | 126, (length >> 8) & 0xFF, length & 0xFF])
    else:
        raise ValueError("payload too large")
    mask = bytes([
        seq & 0xFF,
        (seq >> 8) & 0xFF,
        time.ticks_ms() & 0xFF,
        (time.ticks_ms() >> 8) & 0xFF,
    ])
    masked = bytes([payload[i] ^ mask[i % 4] for i in range(length)])
    sock.send(header + mask + masked)


def main():
    connect_wifi(SSID, WIFI_KEY)
    sensor = dht.DHT11(Pin(DHT_PIN, pull=Pin.PULL_UP))
    sample_seq = 0
    sock = None
    next_connect_ms = 0
    print("weather station ws client station={} server={}:{} dht_pin={}".format(STATION_NAME, SERVER_HOST, SERVER_PORT, DHT_PIN))

    while True:
        sample_seq += 1
        try:
            temperature, humidity = read_dht11(sensor)
            record = {
                "station_id": STATION_ID,
                "station_name": STATION_NAME,
                "temperature": temperature,
                "humidity": humidity,
                "sample_seq": sample_seq,
            }
            line = ujson.dumps(record)
            print("serial_json {}".format(line))
            if sock is None and time.ticks_diff(time.ticks_ms(), next_connect_ms) >= 0:
                try:
                    sock = connect_ws()
                except Exception as exc:
                    print("websocket error {}, retry after 3s".format(exc))
                    if sock:
                        sock.close()
                    sock = None
                    next_connect_ms = time.ticks_add(time.ticks_ms(), 3000)
            if sock is not None:
                try:
                    send_ws_text(sock, line, sample_seq)
                    print("send {}".format(line))
                except Exception as exc:
                    print("websocket send error {}, reconnect later".format(exc))
                    sock.close()
                    sock = None
                    next_connect_ms = time.ticks_add(time.ticks_ms(), 3000)
        except Exception as exc:
            print("sensor loop error {}".format(exc))
        time.sleep(1)


main()
