from flask import Flask, render_template, request, url_for, redirect
import qrcode
import qrcode.image.pil
import io
import base64
import uuid
import random
import string

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'

# 一時的なルームを管理
rooms = {}
# 予約を管理（予約番号 -> URL）
reservations = {}

def generate_reservation_number():
    """4桁のランダムな数字を生成"""
    return ''.join(random.choices(string.digits, k=4))

@app.route('/')
def index():
    # 一意のルームIDを生成
    room_id = str(uuid.uuid4())
    rooms[room_id] = {"url": None, "connected": False, "reservation_number": None}

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

@app.route('/send')
def send():
    """URLを入力して予約番号を取得するページ"""
    return render_template('send.html')

@app.route('/submit', methods=['POST'])
def submit_url():
    room_id = request.form.get('room_id')
    url = request.form.get('url')
    if room_id in rooms and url:
        rooms[room_id]['url'] = url
        return {'ok': True}, 200
    return {'error': 'invalid room or url'}, 400

@app.route('/create_reservation', methods=['POST'])
def create_reservation():
    """URLを受け取って予約番号を生成"""
    data = request.get_json()
    url = data.get('url')
    
    if not url:
        return {'error': 'URL is required'}, 400
    
    # 一意の予約番号が生成されるまでループ
    while True:
        reservation_number = generate_reservation_number()
        if reservation_number not in reservations:
            break
    
    reservations[reservation_number] = url
    return {'reservation_number': reservation_number, 'ok': True}, 200

@app.route('/apply_reservation', methods=['POST'])
def apply_reservation():
    """予約番号を使ってルームにURLを適用"""
    data = request.get_json()
    room_id = data.get('room_id')
    reservation_number = data.get('reservation_number')
    
    if room_id not in rooms or reservation_number not in reservations:
        return {'error': 'Invalid room or reservation'}, 400
    
    url = reservations[reservation_number]
    rooms[room_id]['url'] = url
    rooms[room_id]['reservation_number'] = reservation_number
    del reservations[reservation_number]
    
    return {'ok': True}, 200

@app.route('/status/<room_id>')
def status(room_id):
    if room_id in rooms and rooms[room_id].get('url'):
        return {'url': rooms[room_id]['url']}
    return {'url': None}

@app.route('/check_reservation/<room_id>')
def check_reservation(room_id):
    """このルームに予約が存在するか確認"""
    if room_id not in rooms:
        return {'has_reservation': False}
    
    # 予約が存在するかどうかを返す
    has_reservation = len(reservations) > 0
    return {'has_reservation': has_reservation}

@app.route('/<reservation_number>')
def redirect_to_url(reservation_number):
    """4桁のコードを指定して直接リダイレクト、存在しない場合はエラー画面"""
    if len(reservation_number) == 4 and reservation_number.isdigit():
        if reservation_number in reservations:
            url = reservations[reservation_number]
            del reservations[reservation_number]
            return redirect(url)
        else:
            return render_template('invalid_code.html', code=reservation_number)
    return "Not Found", 404

if __name__ == '__main__':
    app.run(debug=True)
