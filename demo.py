import os
import sys
import time

#import coils
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
from util.xml import WriteXml

src = None
motion_config = None
channel = None
pts2 = None
camera_id = '42754'
client = redis.Redis(host='127.0.0.1', port=6379)
if len(sys.argv) == 4:
    progam, src, channel, motion_config = sys.argv

else:
    print('You must to give a camera_id, src, motion_config and channel')

if src:
    rtsp = src
else:
    rtsp = 'rtsp://ubndxinman.ddns.net:560/av0_0'

if channel:
    channel_id = channel
else:
    channel_id = 'hi'

sio = socketio.Client()
sio.connect('http://localhost:9090', namespaces=['/motion'])
width = None
height = None
#width = None if len(sys.argv) <= 1 else int(sys.argv[1])
#height = None if len(sys.argv) <= 2 else int(sys.argv[2])

print("==============================================")
if motion_config and json.loads(motion_config[1:].replace('\\','').replace('"x"',"'x'").replace('"y"',"'y'")) != '[]':
    motion_config = json.loads(motion_config[1:].replace('\\','').replace('"x"',"'x'").replace('"y"',"'y'"))
    print("=========================================================================")
    print("motion_config==========>", motion_config['region_value'])
    print("====================================xxxxxxxxxxxxxx=====================================")
else:
    region = "[[{'x':10,'y':10}, {'x':900, 'y':10}, {'x':900, 'y':500}, {'x':10, 'y':500}]]"
    region_value = ast.literal_eval(region)
pts = []
for i in range(len(region_value)):
    pts.append([])
    for point in region_value[i]:
        pts[i].append((point['x'], point['y']))
# Create video capture object, retrying until successful.
max_sleep = 5.0
cur_sleep = 0.1
print("pts2------------>", pts2)

@sio.on('connect', namespace='/motion')
def on_connect():
    global channel_id, camera_id
    print('channel_id---->', channel_id)
    sio.emit('my message', channel_id, namespace='/motion')
    while True:
        cap = cv2.VideoCapture(rtsp)
        if cap.isOpened():
            break
        global  cur_sleep
        print("cur_sleep---->", cur_sleep)
        print("max_sleep----->", max_sleep)
	    # print('not opened, sleeping {}s'.format(cur_sleep))
        time.sleep(cur_sleep)
        if cur_sleep < max_sleep:
            cur_sleep *= 2
            cur_sleep = min(cur_sleep, max_sleep)
            continue
        cur_sleep = 0.1

    # Create client to the Redis store.
    #store = redis.Redis()

    # Set video dimensions, if given.
    if width: cap.set(3, width)
    if height: cap.set(4, height)

    # Monitor the framerate at 1s, 5s, 10s intervals.
    #fps = coils.RateTicker((1, 5, 10))

    md = SingleMotionDetector(pts)

    total = 0
    fail_count = 0
    frame_count = 0
    recording_event = {
        'event_uuid': '',
        'status': 0,
        'camera_id': camera_id,
        'channel_id': channel_id,
        'event_type': 'motion_detect',
        'event_detail': {},
        'event_description': '',
        'thumbnail_url': '',
        'start_time': '',
        'end_time': ''
    }
    start_time = ''
    end_time = 0
    time_count = 0
    time_frame_current = 0
    time_frame_xml = ''
    count_1s = 0
    time_start_frame = ''
    while True:
        status, frame = cap.read()
        if frame is None:
            fail_count = fail_count + 1
            time.sleep(0.5)
            if fail_count > 2:
                cap.release()
                cap = cv2.VideoCapture(rtsp)
                fail_count = 0
            continue
        frame_count += 1
        # status = cv2.imwrite('images/' + str(1) + '.jpg', frame)
        # print(status)
        # if frame_count % 5 == 0:
        # frame = imutils.resize(frame, width=600)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (7, 7), 0)
            # grab the current timestamp and draw it on the frame
            #timestamp = datetime.now()

        if total > 0:
                # detect motion in the image
            motion = md.detect(gray)
                # cehck to see if motion was found in the frame
            if motion is not None:
                print("Co motion")
                    # unpack the tuple and draw the box surrounding the
                    # "motion area" on the output frame
                (thresh, rect) = motion
                time_frame_current = datetime.now()
                for r in rect:
                    cv2.rectangle(frame, (r['x'], r['y']), (r['x'] + r['w'], r['y'] + r['h']),
                                (0, 0, 255), 2)

                if start_time == '':
                    data = ET.Element('data')
                    print("Start time")
                    start_time = datetime.now()
                    date_time = start_time.strftime("%m-%d-%Y_%H:%M:%S")

                    event_uuid = channel_id + "_" + date_time
                    recording_event['event_uuid'] = event_uuid
                    recording_event['start_time'] = str(start_time)
                    recording_event['status'] = 0
                    recording_event['thumbnail_url'] = '/images/' + event_uuid
                    client.publish('recording_event_topic', json.dumps(recording_event))
                    t = WriteImage(event_uuid, frame)
                    t.write_image()

                    event_uuid_1 = ET.SubElement(data, 'event_uuid')
                    event_uuid_1.text = event_uuid
                    camera_id_1 = ET.SubElement(data, 'camera_id')
                    camera_id_1.text = camera_id
                    channel_id_1 = ET.SubElement(data, 'channel_id')
                    channel_id_1.text = channel_id
                    status_1 = ET.SubElement(data, 'status')
                    status_1.text = "1"

                    # xml = WriteXml(1)
                    # xml.create_object(1, 2, 3, 4)
                    end_time = 0
                    time_count = 0
                    time_start_frame = datetime.now()
                    time_frame_xml = datetime.now()
                    # motion_1 = ET.SubElement(motion_list, 'motion')
                    # motion_1.text = time_frame_xml
            if start_time != '':
                if count_1s < 1:
                    t_1s = datetime.now() - time_start_frame
                    count_1s = decimal.Decimal(t_1s.seconds)
                    if time_frame_xml == '':
                        time_frame_xml = datetime.now()
                        motion_list = ET.SubElement(data, 'motion_list')
                        motion_list.text = str(time_frame_xml)
                else:
                    time_start_frame = datetime.now()
                    time_frame_xml = ''
                    count_1s = 0
            if start_time != '':
                if motion is not None:
                    end_time = 0
                else:
                    if end_time < 5:
                        t = datetime.now() - time_frame_current
                        t_count = datetime.now() - start_time
                        end_time = decimal.Decimal(t.seconds)
                        time_count = decimal.Decimal(t_count.seconds)
                    else:
                        recording_event['end_time'] = str(datetime.now())
                        recording_event['status'] = 1
                        client.publish('recording_event_topic', json.dumps(recording_event))
                        recording_event['end_time'] = ''
                        end_time = 0
                        start_time = ''
                        time_count = 0
                        print('XML write')
                        b_xml = ET.tostring(data)
                        with open("xml/" + event_uuid + ".xml", "wb") as f:
                            f.write(b_xml)
            if end_time < 5 and time_count > 20:
                print("End time 300s")
                recording_event['end_time'] = str(datetime.now())
                recording_event['status'] = 1
                client.publish('recording_event_topic', json.dumps(recording_event))
                end_time = 0
                time_count = 0
                start_time = ''

                b_xml = ET.tostring(data)
                with open("xml/" + event_uuid + ".xml", "wb") as f:
                    f.write(b_xml)

                start_time = datetime.now()
                date_time = start_time.strftime("%m-%d-%Y_%H:%M:%S")
                event_uuid = channel_id + "_" + date_time
                t = WriteImage(event_uuid, frame)
                t.write_image()
                recording_event['event_uuid'] = event_uuid
                recording_event['start_time'] = str(start_time)
                recording_event['status'] = 0
                recording_event['thumbnail_url'] = '/images/' + event_uuid
                recording_event['end_time'] = ''
                client.publish('recording_event_topic', json.dumps(recording_event))


            # update the background model and increment the total number
            # of frames read thus far
        md.update(gray)
        cv2.putText(frame, time.asctime(time.localtime(time.time())), (10, frame.shape[0] - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 255), 1)
        total += 1
        for item in pts:
            pts2 = np.array(item, np.int32)
            #pts2 = pts2.reshape((-1, 1, 2))
            frame = cv2.polylines(frame, [pts2], True, (0,0,255),3)
        hello, frame = cv2.imencode('.jpg', frame)

        value = np.array(frame).tobytes()
        image = base64.b64encode(value).decode()
        # print(channel_id)
        sio.emit("hi", image, namespace='/motion')
        # sio.emit(channel_id, image, namespace='/motion')