from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date
import qrcode
import io
import base64
import os
import secrets
import socket

# Inisialisasi Flask
app = Flask(__name__)

# Mendapatkan path absolut untuk database
basedir = os.path.abspath(os.path.dirname(__file__))
instance_dir = os.path.join(basedir, 'instance')

# Pastikan folder instance ada
if not os.path.exists(instance_dir):
    os.makedirs(instance_dir)

app.config['SECRET_KEY'] = 'your-secret-key-here-change-this'
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(instance_dir, "database.db")}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Inisialisasi Database
db = SQLAlchemy(app)

# Inisialisasi Login Manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Fungsi untuk mendapatkan IP lokal
def get_local_ip():
    try:
        # Connect ke Google DNS untuk mendapatkan IP lokal
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except:
        return "127.0.0.1"

# Fungsi untuk generate QR URL yang dinamis
def generate_qr_url(user_id, token, date):
    # Priority: ngrok URL > IP lokal > localhost
    
    # 1. Cek environment variable untuk ngrok
    ngrok_url = os.getenv('NGROK_URL')
    if ngrok_url:
        base_url = ngrok_url.rstrip('/')
        print(f"📱 Menggunakan ngrok URL: {base_url}")
        return f"{base_url}/qr_scan?user_id={user_id}&token={token}&date={date}"
    
    # 2. Cek apakah ada config manual untuk base URL
    manual_url = os.getenv('BASE_URL')
    if manual_url:
        base_url = manual_url.rstrip('/')
        print(f"📱 Menggunakan manual URL: {base_url}")
        return f"{base_url}/qr_scan?user_id={user_id}&token={token}&date={date}"
    
    # 3. Gunakan IP lokal untuk akses dari HP di WiFi yang sama
    local_ip = get_local_ip()
    if local_ip != "127.0.0.1":
        base_url = f"http://{local_ip}:5000"
        print(f"📱 Menggunakan IP lokal: {base_url}")
        print(f"💡 Pastikan HP dan laptop di WiFi yang sama!")
        return f"{base_url}/qr_scan?user_id={user_id}&token={token}&date={date}"
    
    # 4. Fallback ke localhost
    base_url = "http://localhost:5000"
    print(f"💻 Menggunakan localhost: {base_url}")
    print(f"⚠️  Hanya bisa diakses dari komputer yang sama!")
    return f"{base_url}/qr_scan?user_id={user_id}&token={token}&date={date}"

# Model Database
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    attendances = db.relationship('Attendance', backref='user', lazy=True)

class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    time_in = db.Column(db.DateTime, nullable=True)
    time_out = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), default='hadir')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Route untuk halaman utama
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

# Route untuk login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Username atau password salah!')
    
    return render_template('login.html')

# Route untuk logout
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# Route untuk register user baru
@app.route('/register', methods=['GET', 'POST'])
@login_required
def register():
    # Hanya admin yang bisa register user baru
    if not current_user.is_admin:
        flash('Hanya admin yang dapat mendaftarkan user baru!')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        is_admin = 'is_admin' in request.form
        
        # Validasi
        if User.query.filter_by(username=username).first():
            flash('Username sudah digunakan!')
            return render_template('register.html')
        
        if User.query.filter_by(email=email).first():
            flash('Email sudah digunakan!')
            return render_template('register.html')
        
        if len(password) < 6:
            flash('Password minimal 6 karakter!')
            return render_template('register.html')
        
        # Buat user baru
        new_user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
            is_admin=is_admin
        )
        
        try:
            db.session.add(new_user)
            db.session.commit()
            role = "Admin" if is_admin else "User"
            flash(f'User {username} berhasil ditambahkan sebagai {role}!')
            return redirect(url_for('manage_users'))
        except Exception as e:
            flash(f'Error: {str(e)}')
            db.session.rollback()
    
    return render_template('register.html')

# Route untuk manajemen user
@app.route('/manage_users')
@login_required
def manage_users():
    # Hanya admin yang bisa akses
    if not current_user.is_admin:
        flash('Akses ditolak! Hanya admin yang dapat mengelola user.')
        return redirect(url_for('dashboard'))
    
    users = User.query.all()
    total_users = len(users)
    total_admins = len([u for u in users if u.is_admin])
    total_regular_users = total_users - total_admins
    
    return render_template('manage_users.html', 
                         users=users,
                         total_users=total_users,
                         total_admins=total_admins,
                         total_regular_users=total_regular_users)

# Route untuk delete user
@app.route('/delete_user/<int:user_id>')
@login_required
def delete_user(user_id):
    if not current_user.is_admin:
        flash('Akses ditolak!')
        return redirect(url_for('dashboard'))
    
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('Tidak bisa menghapus akun sendiri!')
        return redirect(url_for('manage_users'))
    
    try:
        # Hapus semua data absensi user terlebih dahulu
        Attendance.query.filter_by(user_id=user_id).delete()
        # Hapus user
        db.session.delete(user)
        db.session.commit()
        flash(f'User {user.username} dan semua data absensinya berhasil dihapus!')
    except Exception as e:
        flash(f'Error: {str(e)}')
        db.session.rollback()
    
    return redirect(url_for('manage_users'))

# Route untuk dashboard
@app.route('/dashboard')
@login_required
def dashboard():
    today = date.today()
    attendance_today = Attendance.query.filter_by(
        user_id=current_user.id,
        date=today
    ).first()
    
    # Generate QR Code dengan URL untuk absensi
    token = secrets.token_urlsafe(16)  # Generate secure token
    
    # Simpan token di session untuk verifikasi
    session['qr_token'] = token
    session['qr_user_id'] = current_user.id
    session['qr_date'] = today.isoformat()
    
    # Generate QR URL dengan prioritas
    qr_url = generate_qr_url(current_user.id, token, today)
    
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(qr_url)
    qr.make(fit=True)
    
    qr_img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert ke base64 untuk ditampilkan di HTML
    buffer = io.BytesIO()
    qr_img.save(buffer, format='PNG')
    buffer.seek(0)
    qr_code_base64 = base64.b64encode(buffer.getvalue()).decode()
    
    return render_template('dashboard.html', 
                         attendance=attendance_today, 
                         qr_code=qr_code_base64,
                         qr_url=qr_url,  # Tambah URL untuk testing
                         today=today)

# Route untuk halaman absensi
@app.route('/attendance')
@login_required
def attendance_page():
    attendances = Attendance.query.filter_by(user_id=current_user.id).order_by(Attendance.date.desc()).limit(30).all()
    return render_template('attendance.html', attendances=attendances)

# Route untuk scan QR dari URL
@app.route('/qr_scan')
def qr_scan_url():
    user_id = request.args.get('user_id')
    token = request.args.get('token')
    scan_date = request.args.get('date')
    
    # Validasi parameter
    if not user_id or not token or not scan_date:
        return render_template('qr_result.html', 
                             success=False, 
                             message='QR Code tidak valid atau sudah kadaluarsa!',
                             today=date.today())
    
    # Cek apakah user ada
    user = User.query.get(user_id)
    if not user:
        return render_template('qr_result.html', 
                             success=False, 
                             message='User tidak ditemukan!',
                             today=date.today())
    
    # Parse tanggal
    try:
        scan_date_obj = datetime.strptime(scan_date, '%Y-%m-%d').date()
    except:
        return render_template('qr_result.html', 
                             success=False, 
                             message='Format tanggal tidak valid!',
                             today=date.today())
    
    # Cek apakah QR Code masih valid (hanya untuk hari ini)
    today = date.today()
    if scan_date_obj != today:
        return render_template('qr_result.html', 
                             success=False, 
                             message='QR Code sudah kadaluarsa! Gunakan QR Code hari ini.',
                             today=today)
    
    # Proses absensi
    now = datetime.now()
    attendance = Attendance.query.filter_by(
        user_id=user_id,
        date=today
    ).first()
    
    # Tentukan aksi berdasarkan status absensi
    if not attendance or not attendance.time_in:
        # Check-in
        if not attendance:
            attendance = Attendance(
                user_id=user_id,
                date=today,
                time_in=now,
                status='hadir'
            )
            db.session.add(attendance)
        else:
            attendance.time_in = now
        
        db.session.commit()
        return render_template('qr_result.html', 
                             success=True, 
                             message=f'Check-in berhasil untuk {user.username}!',
                             user=user,
                             time=now.strftime('%H:%M:%S'),
                             action='Check-in',
                             today=today)
    
    elif attendance.time_in and not attendance.time_out:
        # Check-out
        attendance.time_out = now
        db.session.commit()
        
        # Hitung durasi kerja
        duration = now - attendance.time_in
        hours = duration.seconds // 3600
        minutes = (duration.seconds % 3600) // 60
        
        return render_template('qr_result.html', 
                             success=True, 
                             message=f'Check-out berhasil untuk {user.username}!',
                             user=user,
                             time=now.strftime('%H:%M:%S'),
                             action='Check-out',
                             duration=f'{hours} jam {minutes} menit',
                             today=today)
    
    else:
        # Sudah check-in dan check-out
        return render_template('qr_result.html', 
                             success=False, 
                             message=f'{user.username} sudah menyelesaikan absensi hari ini!',
                             today=today)

# Route untuk scan QR (simulasi) - yang lama tetap ada
@app.route('/scan_qr', methods=['POST'])
@login_required
def scan_qr():
    action = request.json.get('action')  # 'checkin' atau 'checkout'
    today = date.today()
    now = datetime.now()
    
    attendance = Attendance.query.filter_by(
        user_id=current_user.id,
        date=today
    ).first()
    
    if action == 'checkin':
        if not attendance:
            # Buat record absensi baru
            attendance = Attendance(
                user_id=current_user.id,
                date=today,
                time_in=now,
                status='hadir'
            )
            db.session.add(attendance)
            db.session.commit()
            return jsonify({'success': True, 'message': 'Check-in berhasil!'})
        elif not attendance.time_in:
            attendance.time_in = now
            db.session.commit()
            return jsonify({'success': True, 'message': 'Check-in berhasil!'})
        else:
            return jsonify({'success': False, 'message': 'Anda sudah check-in hari ini!'})
    
    elif action == 'checkout':
        if attendance and attendance.time_in and not attendance.time_out:
            attendance.time_out = now
            db.session.commit()
            return jsonify({'success': True, 'message': 'Check-out berhasil!'})
        elif not attendance or not attendance.time_in:
            return jsonify({'success': False, 'message': 'Anda harus check-in terlebih dahulu!'})
        else:
            return jsonify({'success': False, 'message': 'Anda sudah check-out hari ini!'})
    
    return jsonify({'success': False, 'message': 'Aksi tidak valid!'})

# Route untuk laporan absensi (Admin only)
@app.route('/attendance_report')
@login_required
def attendance_report():
    if not current_user.is_admin:
        flash('Akses ditolak! Hanya admin yang dapat melihat laporan.')
        return redirect(url_for('dashboard'))
    
    # Get filter parameters
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    user_filter = request.args.get('user_id')
    
    # Base query
    query = db.session.query(Attendance, User).join(User, Attendance.user_id == User.id)
    
    # Apply filters
    if start_date:
        try:
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
            query = query.filter(Attendance.date >= start_date_obj)
        except:
            flash('Format tanggal mulai tidak valid!')
    
    if end_date:
        try:
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
            query = query.filter(Attendance.date <= end_date_obj)
        except:
            flash('Format tanggal akhir tidak valid!')
    
    if user_filter:
        query = query.filter(Attendance.user_id == user_filter)
    
    # Get results
    attendances = query.order_by(Attendance.date.desc()).limit(100).all()
    users = User.query.filter_by(is_admin=False).all()  # For filter dropdown
    
    return render_template('attendance_report.html', 
                         attendances=attendances,
                         users=users,
                         start_date=start_date,
                         end_date=end_date,
                         user_filter=user_filter)

# Route untuk konfigurasi URL (Admin only)
@app.route('/config', methods=['GET', 'POST'])
@login_required
def config():
    if not current_user.is_admin:
        flash('Akses ditolak!')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        base_url = request.form.get('base_url', '').strip()
        if base_url:
            os.environ['BASE_URL'] = base_url
            flash(f'Base URL berhasil diset ke: {base_url}')
        else:
            if 'BASE_URL' in os.environ:
                del os.environ['BASE_URL']
            flash('Base URL berhasil di-reset ke otomatis')
    
    current_url = os.getenv('BASE_URL', 'Otomatis')
    local_ip = get_local_ip()
    
    return render_template('config.html', 
                         current_url=current_url,
                         local_ip=local_ip)

# Fungsi untuk membuat user admin default
def create_admin_user():
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        admin = User(
            username='admin',
            email='admin@example.com',
            password_hash=generate_password_hash('admin123'),
            is_admin=True
        )
        db.session.add(admin)
        
        # Tambah user demo
        demo_user = User(
            username='user1',
            email='user1@example.com',
            password_hash=generate_password_hash('password123'),
            is_admin=False
        )
        db.session.add(demo_user)
        db.session.commit()
        print(" Database dan user default berhasil dibuat!")
        print(" Admin: admin / admin123")
        print(" User: user1 / password123")

# Inisialisasi database
def init_database():
    try:
        with app.app_context():
            db.create_all()
            create_admin_user()
            print(f" Database: {os.path.join(instance_dir, 'database.db')}")
    except Exception as e:
        print(f"Error database: {e}")

def print_startup_info():
    print("\n" + "="*60)
    print(" SISTEM ABSENSI QR CODE")
    print("="*60)
    
    local_ip = get_local_ip()
    
    print(f" Localhost: http://127.0.0.1:5000")
    if local_ip != "127.0.0.1":
        print(f" IP Lokal: http://{local_ip}:5000")
        print(f"    Untuk akses dari HP (WiFi sama)")
    
    print(f"\n CARA TESTING QR CODE DI HP:")
    print(f"1. Pastikan HP & laptop di WiFi yang sama")
    print(f"2. Buka di HP: http://{local_ip}:5000") 
    print(f"3. Login → Dashboard → Scan QR Code")
    print(f"4. Atau gunakan ngrok untuk akses global")
    
    print(f"\n ENVIRONMENT VARIABLES (optional):")
    print(f"   NGROK_URL=https://your-ngrok-url.ngrok.app")
    print(f"   BASE_URL=http://your-custom-url.com")
    
    print("\n" + "="*60 + "\n")

if __name__ == '__main__':
    init_database()
    print_startup_info()
    
    # Jalankan dengan host 0.0.0.0 agar bisa diakses dari HP
    app.run(debug=True, host='0.0.0.0', port=5000)