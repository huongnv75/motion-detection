# USAGE
# python webstreaming.py --ip 0.0.0.0 --port 8000

# import the necessary packages
from util.motion_detection import SingleMotionDetector
from imutils.video import VideoStream
from flask import Response
from flask import Flask
from flask import render_template
import threading
import argparse
import imutils
import time
import cv2
import redis
import xml.etree.ElementTree as ET
from kafka import KafkaProducer
import json
from datetime import datetime, timedelta
import decimal
# initialize the output frame and a lock used to ensure thread-safe
# exchanges of the output frames (useful for multiple browsers/tabs
# are viewing tthe stream)

env = 'camera'
topic = 'numtest'
outputFrame = None
lock = threading.Lock()

client = redis.Redis(host='localhost', port=6379, db=0)

# initialize a flask object
app = Flask(__name__)
udp = 'udp://177.0.0.1:5005'

send_data = {
	"link_udp": udp,
    "rect_list": [],
    "time": ''
}

producer = KafkaProducer(
    bootstrap_servers='localhost:9092',
    value_serializer=lambda v: json.dumps(v).encode('utf-8'))

# initialize the video stream and allow the camera sensor to
# warmup
#vs = VideoStream(usePiCamera=1).start()
vs = VideoStream(src=udp).start()
time.sleep(2.0)

start_time = ''
end_time = 0
@app.route("/")
def index():
	# return the rendered template
	return render_template("index.html")


def detect_motion(frameCount):
	# grab global references to the video stream, output frame, and
	# lock variables
	global vs, outputFrame, lock, start_time, end_time

	# initialize the motion detector and the total number of frames
	# read thus far
	md = SingleMotionDetector(accumWeight=0.1)
	total = 0
	file = 0

	# loop over frames from the video stream
	while True:
		# read the next frame from the video stream, resize it,
		# convert the frame to grayscale, and blur it
		frame = vs.read()
		frame = imutils.resize(frame, width=400)
		gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
		gray = cv2.GaussianBlur(gray, (7, 7), 0)

		# grab the current timestamp and draw it on the frame
		timestamp = datetime.now()
		cv2.putText(frame, timestamp.strftime(
			"%A %d %B %Y %I:%M:%S%p"), (10, frame.shape[0] - 10),
			cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 255), 1)

		# if the total number of frames has reached a sufficient
		# number to construct a reasonable background model, then
		# continue to process the frame
		rect_list = []


		if total > frameCount:
			# detect motion in the image
			motion = md.detect(gray)
			# cehck to see if motion was found in the frame
			if motion is not None:
				# unpack the tuple and draw the box surrounding the
				# "motion area" on the output frame
				(thresh, (minX, minY, maxX, maxY)) = motion
				cv2.rectangle(frame, (minX, minY), (maxX, maxY),
					(0, 0, 255), 2)

				item = {
					"point1": {
						"x": minX,
						"y": minY
					},
					"point2": {
						"x": maxX,
						"y": maxY
					}
				}
				rect_list.append(item)
				send_data['rect_list'] = rect_list
				client.publish(env, str(send_data))
				producer.send(topic, value=send_data)
				if start_time == '':
					start_time = datetime.now()
					client.publish(env, 'Start_time:' + str(start_time))
					data = ET.Element('data')
					items = ET.SubElement(data, 'items')
					file = file + 1
					item = ET.SubElement(items, 'item')
					item.set('name', 'item')
					point1 = ET.SubElement(item, "point")
					point2 = ET.SubElement(item, "point")

					# point 1
					point1.set('name', 'point1')
					x1 = ET.SubElement(point1, 'x')
					y1 = ET.SubElement(point1, 'y')
					x1.text = str(minX)
					y1.text = str(minY)

					# point 2
					point2.set('name', 'point2')
					x2 = ET.SubElement(point2, 'x')
					y2 = ET.SubElement(point2, 'y')
					x2.text = str(maxX)
					y2.text = str(maxY)

					mydata = ET.tostring(data).decode('utf-8')
					# now = datetime.now()
					# dt_string = now.strftime("%d/%m/%Y%H:%M:%S.xml")

					myfile = open('xml/' + str(file) + '.xml', "w")
					myfile.write(mydata)
					cv2.imwrite('images/' + str(file) + '.jpg', frame)

			if start_time != '':
				if motion is None:
					if end_time < 5:
						t = datetime.now() - start_time
						end_time = decimal.Decimal(t.seconds)
					else:
						client.publish(env, 'End time:' + str(datetime.now()))
						end_time = 0
						start_time = ''
				else:
					end_time = 0


		# update the background model and increment the total number
		# of frames read thus far
		md.update(gray)
		total += 1

		# acquire the lock, set the output frame, and release the
		# lock
		with lock:
			outputFrame = frame.copy()
		
def generate():
	# grab global references to the output frame and lock variables
	global outputFrame, lock

	# loop over frames from the output stream
	while True:
		# wait until the lock is acquired
		with lock:
			# check if the output frame is available, otherwise skip
			# the iteration of the loop
			if outputFrame is None:
				continue

			# encode the frame in JPEG format
			(flag, encodedImage) = cv2.imencode(".jpg", outputFrame)

			# ensure the frame was successfully encoded
			if not flag:
				continue


		# yield the output frame in the byte format
		yield(b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' +
			bytearray(encodedImage) + b'\r\n')

@app.route("/video_feed")
def video_feed():
	# return the response generated along with the specific media
	# type (mime type)
	return Response(generate(),
		mimetype = "multipart/x-mixed-replace; boundary=frame")

# check to see if this is the main thread of execution
if __name__ == '__main__':
	# construct the argument parser and parse command line arguments
	ap = argparse.ArgumentParser()
	ap.add_argument("-i", "--ip", type=str, required=True,
		help="ip address of the device")
	ap.add_argument("-o", "--port", type=int, required=True,
		help="ephemeral port number of the server (1024 to 65535)")
	ap.add_argument("-f", "--frame-count", type=int, default=32,
		help="# of frames used to construct the background model")
	args = vars(ap.parse_args())

	# start a thread that will perform motion detection
	t = threading.Thread(target=detect_motion, args=(
		args["frame_count"],))
	t.daemon = True
	t.start()

	# start the flask app
	app.run(host=args["ip"], port=args["port"], debug=True,
		threaded=True, use_reloader=False)

# release the video stream pointer
vs.stop()