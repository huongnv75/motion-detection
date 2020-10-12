from aiohttp import web
import socketio
from flask import Flask, render_template
import socketio

sio = socketio.Server(logger=False, async_mode='threading')
app = Flask(__name__)
app.wsgi_app = socketio.WSGIApp(sio, app.wsgi_app)
# https://python-socketio.readthedocs.io/en/latest/server.html
sio = socketio.Server()



@sio.on('connect', namespace='/motion')
def connect(sid, environ):
    print("connect ", sid)


@sio.on('my message', namespace='/motion')
def message(sid, data):
    # await sio.emit('reply', room=sid)
    sio.emit('reply', data, namespace='/motion')
    @sio.on(data, namespace='/motion')
    def message(sid, message):
        sio.emit(data, message, namespace='/motion')
    session =  sio.get_session(sid)


@sio.on('disconnect', namespace='/motion')
def disconnect(sid):
    print('disconnect ', sid)


@sio.event
def connect(sid, environ):
    # username = authenticate_user(environ)
    username = 'ok'
    sio.save_session(sid, {'username': username})


if __name__ == '__main__':
    # web.run_app(app)
    app.run(threaded=True, host='0.0.0.0', port=9090)
