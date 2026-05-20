from flask import Flask, render_template, request, url_for
import qrcode
import qrcode.image.pil
import io
import base64
import uuid

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'

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
    img = qr.make_image(image_factory=qrcode.image.pil.PilImage, fill_color="black", back_color="white")

    # 画像をBase64に変換
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode('utf-8')

    return render_template('index.html', qr_code=img_str, room_id=room_id)

@app.route('/scan/<room_id>')
def scan(room_id):
    return render_template('scan.html', room_id=room_id)

@app.route('/submit', methods=['POST'])
def submit_url():
    room_id = request.form.get('room_id')
    url = request.form.get('url')
    if room_id in rooms and url:
        rooms[room_id]['url'] = url
        return {'ok': True}, 200
    return {'error': 'invalid room or url'}, 400

@app.route('/status/<room_id>')
def status(room_id):
    if room_id in rooms and rooms[room_id].get('url'):
        return {'url': rooms[room_id]['url']}
    return {'url': None}

if __name__ == '__main__':
    app.run(debug=True)