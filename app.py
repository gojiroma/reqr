from flask import Flask, render_template, request, redirect, url_for
from flask_socketio import SocketIO, emit
import qrcode
import io
import base64
import uuid

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'
socketio = SocketIO(app, cors_allowed_origins="*")

# 一時的なルームを管理
rooms = {}

@app.route('/')
def index():
    # 一意のルームIDを生成
    room_id = str(uuid.uuid4())
    rooms[room_id] = {"url": None, "connected": False}

    # QRコードを生成（ルームIDを含むURL）
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(url_for('scan', room_id=room_id, _external=True))
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    # 画像をBase64に変換
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode('utf-8')

    return render_template('index.html', qr_code=img_str, room_id=room_id)

@app.route('/scan/<room_id>')
def scan(room_id):
    return render_template('scan.html', room_id=room_id)

@socketio.on('connect')
def handle_connect():
    emit('status', {'message': '接続されました'})

@socketio.on('join')
def handle_join(data):
    room_id = data['room_id']
    if room_id in rooms:
        rooms[room_id]['connected'] = True
        join_room(room_id)
        emit('status', {'message': f'ルーム {room_id} に参加しました'}, room=room_id)

@socketio.on('submit_url')
def handle_submit_url(data):
    room_id = data['room_id']
    url = data['url']
    if room_id in rooms:
        rooms[room_id]['url'] = url
        emit('redirect', {'url': url}, room=room_id)

if __name__ == '__main__':
    socketio.run(app, debug=True)