import cv2
import numpy as np
import redis
from datetime import datetime
import imutils
import socketio
import sys
import base64
import ast
import json
import decimal
import xml.etree.ElementTree as ET

from util.motion_detection import SingleMotionDetector
from util.images import WriteImage

r = redis.Redis(host = '127.0.0.1', port = 6379)
sio = socketio.Client()
sio.connect('http://localhost:9090', namespaces=['/motion'])
src = 'rtsp://ubndxinman.ddns.net:560/av0_0'
channel_id = 'hi'

@sio.on('connect', namespace='/motion')
def on_connect():
    sio.emit('my message', channel_id, namespace='/motion')
    p = r.pubsub()
    p.subscribe('cameras')
    while True:
        message = p.get_message()
        if message and not message['data'] == 1:
            message = message['data'].decode('utf-8')
            if message == 'run_script':
                print('script running in the targeted machine')
            else:
                print("AAA")