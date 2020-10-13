import os, stat
import sys
import time

# import coils
import cv2
import numpy as np
import redis
from datetime import datetime
import imutils
from util.motion_detection import SingleMotionDetector
import socketio
import sys
import base64
import ast
import json
import decimal
from util.images import WriteImage
import xml.etree.ElementTree as ET


# cap quyen cho thu muc
def change_permissions_recursive(path, mode):
    for root, dirs, files in os.walk(path, topdown=False):
        os.chmod(root, mode)
        for dir in [os.path.join(root, d) for d in dirs]:
            os.chmod(dir, mode)
        for file in [os.path.join(root, f) for f in files]:
            os.chmod(file, mode)


# tra ve duong dan den file
def make_path(prefix, suffix, filename):
    now = datetime.utcnow()
    # day = int(datetime.timestamp(datetime.strptime(now.strftime("%d/%m/%Y"), "%d/%m/%Y")))
    day = int((datetime.strptime(now.strftime("%d/%m/%Y"), "%d/%m/%Y") - datetime(1970, 1, 1)).total_seconds())
    minute = now.strftime("%M")[:-1] + "0"
    date_string = now.strftime("%d/%m/%Y " + "%H:" + minute + ":00")
    date = datetime.strptime(date_string, "%d/%m/%Y %H:%M:%S")
    block = int((date - datetime(1970, 1, 1)).total_seconds())
    return prefix + "/" + str(day) + "/" + str(block) + "/" + suffix + "/" + filename


# tao ra mot file rong voi duong dan cho truoc
def create_file(filename):
    if not os.path.exists(os.path.dirname(filename)):
        try:
            os.makedirs(os.path.dirname(filename))
        except OSError as exc:  # Guard against race condition
            if exc.errno != errno.EEXIST:
                raise


client = redis.Redis(host="localhost", port=6379)

src = None
motion_config = None
camera = None
channel = None
pts2 = None
if len(sys.argv) == 5:
    progam, src, camera, channel, motion_config = sys.argv

else:
    print('You must to give a src, camera, channel and motion_config')

if src:
    rtsp = src
else:
    rtsp = 'rtsp://127.0.0.1:8554/110000000008xyz966223c1d1d75-1fd4-4442-9e3a-c978d902bee3'

if camera:
    camera_id = camera
else:
    camera_id = '49511'

if channel:
    channel_id = channel
else:
    channel_id = '49511'

sio = socketio.Client()

sio.connect('http://localhost:9090', namespaces=['/motion'])
width = None
height = None
# width = None if len(sys.argv) <= 1 else int(sys.argv[1])
# height = None if len(sys.argv) <= 2 else int(sys.argv[2])

print("==============================================")
if motion_config and json.loads(
        motion_config[1:].replace('\\', '').replace('"x"', "'x'").replace('"y"', "'y'")) != '[]':
    motion_config = json.loads(motion_config[1:].replace('\\', '').replace('"x"', "'x'").replace('"y"', "'y'"))
    print("=========================================================================")
    print("motion_config==========>", motion_config)
    print("====================================xxxxxxxxxxxxxx=====================================")
    region_value = ast.literal_eval(motion_config['region_value'])
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
try:
    if motion_config['enable_motion'] == "1":
        @sio.on('connect', namespace='/motion')
        def on_connect():
            global channel_id, camera_id
            print('channel_id---->', channel_id)
            sio.emit('my message', channel_id, namespace='/motion')
            while True:
                cap = cv2.VideoCapture(rtsp)
                if cap.isOpened():
                    break
                global cur_sleep
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
            # store = redis.Redis()

            # Set video dimensions, if given.
            # if width: cap.set(3, width)
            # if height: cap.set(4, height)

            # Monitor the framerate at 1s, 5s, 10s intervals.
            # fps = coils.RateTicker((1, 5, 10))

            md = SingleMotionDetector(pts, motion_config['threshold_value'], motion_config['region_type'])

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
                height, width = frame.shape[:2]

                frame = imutils.resize(frame, width=int(width*int(motion_config['detect_resolution'])/100))

                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                gray = cv2.GaussianBlur(gray, (7, 7), 0)
                # grab the current timestamp and draw it on the frame
                # timestamp = datetime.now()

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
                            start_time = datetime.now()
                            date_time = start_time.strftime("%m%d%Y%H%M%S")

                            event_uuid = channel_id + "_" + date_time
                            prefix = "/u02/store/" + channel_id
                            suffix = "motions/" + event_uuid
                            image_file = make_path(prefix, suffix, "thumbnail")
                            create_file(image_file)
                            recording_event['event_uuid'] = event_uuid
                            recording_event['start_time'] = str(int(datetime.now().timestamp() * 1000))
                            recording_event['status'] = 0
                            recording_event['thumbnail_url'] = image_file
                            client.publish('recording_event_topic', json.dumps(recording_event))
                            print("Start time " + recording_event['start_time'])
                            t = WriteImage(image_file, frame)
                            t.write_image()
                            change_permissions_recursive("/u02/store/", stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)

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
                                recording_event['end_time'] = str(int(datetime.now().timestamp() * 1000))
                                recording_event['status'] = 1
                                client.publish('recording_event_topic', json.dumps(recording_event))
                                print("End Time " + recording_event['end_time'])
                                recording_event['end_time'] = ''
                                end_time = 0
                                start_time = ''
                                time_count = 0
                                print('XML write')
                                b_xml = ET.tostring(data)
                                # with open("./xml/" + event_uuid + ".xml", "wb") as f:
                                #    f.write(b_xml)
                    if end_time < 5 and time_count > 300:
                        print("End time 300s")
                        recording_event['end_time'] = str(int(datetime.now().timestamp() * 1000))
                        recording_event['status'] = 1
                        client.publish('recording_event_topic', json.dumps(recording_event))
                        end_time = 0
                        time_count = 0
                        start_time = ''

                        b_xml = ET.tostring(data)
                        # with open("./xml/" + event_uuid + ".xml", "wb") as f:
                        #    f.write(b_xml)

                        start_time = datetime.now()
                        date_time = start_time.strftime("%m%d%Y%H%M%S")
                        event_uuid = channel_id + "_" + date_time

                        prefix = "/u02/store/" + channel_id
                        suffix = "motions/" + event_uuid
                        image_file = make_path(prefix, suffix, "thumbnail")
                        create_file(image_file)
                        t = WriteImage(image_file, frame)
                        t.write_image()
                        change_permissions_recursive("/u02/store/", stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)
                        recording_event['event_uuid'] = event_uuid
                        recording_event['start_time'] = int(datetime.now().timestamp() * 1000)
                        recording_event['status'] = 0
                        recording_event['thumbnail_url'] = image_file
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
                    # pts2 = pts2.reshape((-1, 1, 2))
                    frame = cv2.polylines(frame, [pts2], True, (0, 0, 255), 3)
                hello, frame = cv2.imencode('.jpg', frame)

                value = np.array(frame).tobytes()
                image = base64.b64encode(value).decode()
                # print(channel_id)
                # sio.emit("hi", image, namespace='/motion')
                sio.emit(channel_id, image, namespace='/motion')


        @sio.on('disconnect')
        def disconnect(sid):
            print('disconnect ', sid)
except:
    print("Caught exception socket.error") 