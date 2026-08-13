from flask import Flask, render_template, request, url_for, redirect
import qrcode
import qrcode.image.pil
import io
import base64
import os
import uuid

import db

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your_secret_key_here')

@app.route('/')
def index():
    # 一意のルームIDを生成
    room_id = str(uuid.uuid4())
    db.create_room(room_id)

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
    if room_id and url and db.set_room_url(room_id, url):
        return {'ok': True}, 200
    return {'error': 'invalid room or url'}, 400

@app.route('/create_reservation', methods=['POST'])
def create_reservation():
    """URLを受け取って予約番号を生成"""
    data = request.get_json()
    url = data.get('url')
    
    if not url:
        return {'error': 'URL is required'}, 400

    reservation_number = db.create_reservation(url)
    if not reservation_number:
        return {'error': 'could not allocate a code'}, 503

    return {'reservation_number': reservation_number, 'ok': True}, 200

@app.route('/apply_reservation', methods=['POST'])
def apply_reservation():
    """予約番号を使ってルームにURLを適用"""
    data = request.get_json()
    room_id = data.get('room_id')
    reservation_number = data.get('reservation_number')
    
    if not room_id or not reservation_number:
        return {'error': 'Invalid room or reservation'}, 400

    if not db.apply_reservation(room_id, reservation_number):
        return {'error': 'Invalid room or reservation'}, 400

    return {'ok': True}, 200

@app.route('/status/<room_id>')
def status(room_id):
    room = db.get_room(room_id)
    if room and room.get('url'):
        return {'url': room['url']}
    return {'url': None}

@app.route('/check_reservation/<room_id>')
def check_reservation(room_id):
    """このルームに対応する予約が存在するか確認（改良版）
    
    入力者が待機中にコード生成を待つシーンで、
    ポーリング中でも予約があるかチェックして即座にステータスを返す
    """
    room = db.get_room(room_id)
    if room is None:
        return {'has_reservation': False, 'url': None}

    # ルームにURLがあればそれを返す（最優先）
    if room.get('url'):
        return {'has_reservation': True, 'url': room['url'], 'ready': True}

    # 予約が存在するかどうかを返す
    return {'has_reservation': db.has_pending_reservation(), 'url': None, 'ready': False}

@app.route('/<reservation_number>')
def redirect_to_url(reservation_number):
    """4桁のコードを指定して直接リダイレクト、存在しない場合はエラー画面"""
    if len(reservation_number) == 4 and reservation_number.isdigit():
        url = db.take_reservation(reservation_number)
        if url:
            return redirect(url)
        else:
            return render_template('invalid_code.html', code=reservation_number)
    return "Not Found", 404

if __name__ == '__main__':
    app.run(debug=True)
