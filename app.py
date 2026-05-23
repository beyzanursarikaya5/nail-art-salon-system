from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename 
from functools import wraps
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

# .env dosyasını yükle
load_dotenv()

# --- GÜVENLİK VE AYARLAR ---
SECRET_KEY = os.getenv('SECRET_KEY', 'senin_cok_gizli_anahtarin_burada_olmali_bu_cok_onemli')
# Klasör yollarını proje yapına göre ayarla
UPLOAD_FOLDER = os.path.join('diff', 'static', 'uploads') 
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app = Flask(__name__,
            template_folder='diff/templates',
            static_folder='diff/static')
app.secret_key = SECRET_KEY
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# MySQL Konfigürasyonu
app.config['MYSQL_HOST'] = os.getenv('MYSQL_HOST', 'localhost')
app.config['MYSQL_USER'] = os.getenv('MYSQL_USER', 'root')
app.config['MYSQL_PASSWORD'] = os.getenv('MYSQL_PASSWORD') # ŞİFRENİZ
app.config['MYSQL_DB'] = os.getenv('MYSQL_DB', 'pixienails_db')
app.config['MYSQL_CURSORCLASS'] = 'DictCursor' # Verileri sözlük olarak çeker (KeyError'u önler)
mysql = MySQL(app)

# --- YARDIMCI FONKSİYONLAR ---
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def is_over_18(dob_str):
    today = datetime.today()
    try:
        birth_date = datetime.strptime(dob_str, '%Y-%m-%d')
    except ValueError:
        return False 
    age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
    return age >= 18

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session or not session['logged_in']:
            flash('Bu sayfaya erişim için giriş yapmalısınız.', 'error')
            return redirect(url_for('auth_page', next=request.path))
        return f(*args, **kwargs)
    return decorated_function

# --- 1. TEMEL ROTALAR ---

@app.before_request
def check_profil_setup():
    if session.get('logged_in'):
        # Döngüye girmemesi gereken sayfalar
        allowed_endpoints = ['profile_setup_page', 'save_profile_setup', 'logout', 'static', 'admin_dashboard', 'admin_add_design', 'admin_delete_design']
        if request.endpoint in allowed_endpoints:
            return 
        
        # Profil tamamlanmış mı kontrol et
        cur = mysql.connection.cursor()
        cur.execute("SELECT profile_completed FROM users WHERE user_id = %s", [session['user_id']])
        user_status = cur.fetchone()
        cur.close()

        if user_status and not user_status.get('profile_completed'):
            flash('Lütfen randevu almadan önce profil bilgilerinizi tamamlayın.', 'warning')
            return redirect(url_for('profile_setup_page'))

@app.route('/')
@app.route('/index')
def index():
    cursor = mysql.connection.cursor()

    # 1. Tasarımları Çek
    cursor.execute("SELECT design_id, design_image, design_price FROM designs ORDER BY design_id DESC LIMIT 6")
    designs = cursor.fetchall()

    # 2. Yorumları Çek
    cursor.execute("""
        SELECT r.content, r.rating, u.full_name, u.profile_image
        FROM reviews r 
        JOIN users u ON r.user_id = u.user_id 
        ORDER BY r.created_at DESC 
        LIMIT 3
    """)
    reviews_data = cursor.fetchall()
    cursor.close()

    # 3. Yorumları Düzenle (DictCursor sayesinde row['key'] kullanıyoruz)
    reviews = []
    if reviews_data:
        for row in reviews_data:
            reviews.append({
                'content': row['content'],
                'rating': row['rating'],
                'full_name': row['full_name'],
                'profile_image': row['profile_image'] if row['profile_image'] else 'default_profile.png'
            })

    return render_template('index.html', designs=designs, reviews=reviews)

@app.route('/auth')
def auth_page():
    if session.get('logged_in'):
        # Yönetici ise dashboard'a, değilse profile
        if session.get('is_admin'):
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('profile_page'))
    
    error = request.args.get('error', '')
    next_url = request.args.get('next', '')
    return render_template('auth.html', error=error, next=next_url)

@app.route('/tasarimlar')
def tasarimlar_page():
    cur = mysql.connection.cursor()
    cur.execute("SELECT design_id, design_image, design_price, design_name FROM designs ORDER BY design_id DESC")
    all_designs = cur.fetchall()
    cur.close()
    return render_template('tasarimlar.html', all_designs=all_designs)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# --- 2. KULLANICI İŞLEMLERİ (GİRİŞ/KAYIT) ---

@app.route('/login', methods=['POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password_raw = request.form.get('password')
        next_url = request.args.get('next') 

        cur = mysql.connection.cursor()
        cur.execute("SELECT user_id, username, password_hash, full_name, is_admin, profile_image FROM users WHERE username = %s", (email,))
        user = cur.fetchone()
        cur.close()

        if user and check_password_hash(user['password_hash'], password_raw):
            session['logged_in'] = True
            session['user_id'] = user['user_id']
            session['full_name'] = user['full_name']
            
            # Admin bilgisini session'a kaydet (1 ise True)
            session['is_admin'] = True if user.get('is_admin') == 1 else False
            session['profile_image'] = user.get('profile_image')

            flash('Giriş başarılı!', 'success')

            # YÖNLENDİRME MANTIĞI
            if session['is_admin']:
                return redirect(url_for('admin_dashboard'))
            elif next_url:
                return redirect(next_url)
            else:
                return redirect(url_for('profile_page'))
        else:
            return redirect(url_for('auth_page', error='E-posta veya şifre hatalı.', next=next_url))
            
    return redirect(url_for('auth_page'))

@app.route('/register', methods=['POST'])
def register():
    if request.method == 'POST':
        full_name = request.form.get('full_name')
        email = request.form.get('email')
        password_raw = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if password_raw != confirm_password:
            return redirect(url_for('auth_page', error='Şifreler uyuşmuyor.'))

        password_hashed = generate_password_hash(password_raw)
        
        try:
            cur = mysql.connection.cursor()
            cur.execute("SELECT user_id FROM users WHERE username = %s", [email])
            if cur.fetchone():
                cur.close()
                return redirect(url_for('auth_page', error='Bu e-posta zaten kayıtlı.'))

            # Yeni kayıtlar varsayılan olarak is_admin = 0 (Müşteri) olur
            sql = """INSERT INTO users (username, password_hash, full_name, profile_completed, is_admin) 
                     VALUES (%s, %s, %s, FALSE, 0)"""
                        
            cur.execute(sql, (email, password_hashed, full_name))
            mysql.connection.commit()
            new_user_id = cur.lastrowid
            cur.close()
            
            session['logged_in'] = True
            session['user_id'] = new_user_id
            session['full_name'] = full_name 
            session['is_admin'] = False # Yeni kayıt yönetici değildir
            
            return redirect(url_for('profile_setup_page'))
        
        except Exception as e:
            print(f"SQL HATA: {e}")
            return redirect(url_for('auth_page', error='Kayıt başarısız oldu.'))
            
    return redirect(url_for('auth_page'))

# --- 3. PROFİL İŞLEMLERİ ---

@app.route('/profile_setup')
def profile_setup_page():
    if not session.get('logged_in'):
        return redirect(url_for('auth_page'))
    return render_template('profile_setup.html')

@app.route('/save_profile_setup', methods=['POST'])
def save_profile_setup():
    if not session.get('logged_in'):
        return redirect(url_for('auth_page'))

    if request.method == 'POST':
        user_id = session.get('user_id')
        phone = request.form.get('phone')
        birth_date_str = request.form.get('birth_date')
        continue_action = request.form.get('continue_to_appointment')

        if not is_over_18(birth_date_str):
            flash('18 yaş altı hizmet veremiyoruz.', 'error')
            return redirect(url_for('profile_setup_page')) 

        try:
            cur = mysql.connection.cursor()
            sql = """UPDATE users SET phone = %s, birth_date = %s, profile_completed = TRUE WHERE user_id = %s"""
            cur.execute(sql, (phone, birth_date_str, user_id))
            mysql.connection.commit()
            cur.close()
            
            session['profile_completed'] = True
            flash('Profil tamamlandı!', 'success')

            if continue_action == 'yes':
                return redirect(url_for('randevu_page'))
            else:
                return redirect(url_for('profile_page'))

        except Exception as e:
            print(f'Hata: {e}')
            return redirect(url_for('profile_setup_page'))
            
    return redirect(url_for('profile_setup_page'))

# PROFİL SAYFASI
@app.route('/profile')
@app.route('/profile/<int:user_id>')
@login_required 
def profile_page(user_id=None):
    # 1. YÖNETİCİ KONTROLÜ: Eğer yönetici profil sayfasına girmek isterse, Dashboard'a at.
    if session.get('is_admin'):
        return redirect(url_for('admin_dashboard'))

    current_user_id = session.get('user_id')
    # Başkasının profiline girmeyi engelle (Opsiyonel)
    target_id = user_id if user_id else current_user_id
    if target_id != current_user_id:
         target_id = current_user_id

    cur = mysql.connection.cursor()
    
    # Kullanıcı bilgisi
    cur.execute("SELECT * FROM users WHERE user_id = %s", [target_id])
    user_info = cur.fetchone()
    
    # Randevuları Çek
    cur.execute("""
        SELECT a.*, d.design_name, d.design_image, d.design_id
        FROM appointments a
        LEFT JOIN designs d ON a.design_id = d.design_id
        WHERE a.user_id = %s
        ORDER BY a.appointment_date DESC
    """, [target_id])
    
    all_appointments_base = cur.fetchall()
    
    # Hizmet İsimlerini Çek
    cur.execute("SELECT service_id, name FROM services")
    services_dict = {row['service_id']: row['name'] for row in cur.fetchall()}
    
    future_appointments = []
    past_appointments = []
    now = datetime.now()
    
    for appt in all_appointments_base:
        # Randevuya ait hizmetleri bul
        cur.execute("SELECT service_id FROM appointment_services WHERE appointment_id = %s", [appt['appointment_id']])
        s_ids = [r['service_id'] for r in cur.fetchall()]
        appt['service_name'] = ', '.join([services_dict.get(sid, '') for sid in s_ids])
        
        # Özel tasarım varsa görsel yolunu ayarla
        if appt.get('custom_design_path'):
            appt['appointment_image_path'] = appt['custom_design_path']
        else:
            appt['appointment_image_path'] = None

        if appt['appointment_date'] > now:
            future_appointments.append(appt)
        else:
            past_appointments.append(appt)
    
    cur.close()
    return render_template('profile.html', user_info=user_info, future_appointments=future_appointments, past_appointments=past_appointments)

# PROFİL GÜNCELLEME
@app.route('/profile/update', methods=['POST'])
@login_required
def update_profile_info():
    user_id = session.get('user_id')
    phone = request.form.get('phone')
    birth_date_str = request.form.get('birth_date')
    full_name = request.form.get('full_name')
    username = request.form.get('username')
    
    if not is_over_18(birth_date_str):
        flash('Yaşınız 18 altı olamaz.', 'error')
        return redirect(url_for('profile_page'))

    cur = mysql.connection.cursor()
    try:
        cur.execute("""
            UPDATE users SET full_name=%s, username=%s, phone=%s, birth_date=%s WHERE user_id=%s
        """, (full_name, username, phone, birth_date_str, user_id))
        mysql.connection.commit()
        cur.close()
        session['username'] = username
        flash('Profil güncellendi.', 'success')
    except Exception as e:
        flash(f'Hata: {e}', 'error')
        
    return redirect(url_for('profile_page'))

@app.route('/profile/upload_image/<int:user_id>', methods=['POST'])
@login_required
def upload_profile_image(user_id):
    if 'profile_image_file' not in request.files:
        return redirect(url_for('profile_page'))

    file = request.files['profile_image_file']
    if file.filename == '' or not allowed_file(file.filename):
        flash('Geçersiz dosya.', 'error')
        return redirect(url_for('profile_page'))

    try:
        filename = secure_filename(file.filename)
        ext = filename.rsplit('.', 1)[1].lower()
        filename_unique = f"user_{user_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.{ext}"
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename_unique))
        
        db_path = f"uploads/{filename_unique}"
        
        cur = mysql.connection.cursor()
        cur.execute("UPDATE users SET profile_image = %s WHERE user_id = %s", (db_path, user_id))
        mysql.connection.commit()
        cur.close()
        
        session['profile_image'] = db_path
        flash('Fotoğraf güncellendi.', 'success')
    except Exception as e:
        print(f"Upload Hata: {e}")
        flash('Hata oluştu.', 'error')

    return redirect(url_for('profile_page'))

# --- 4. YÖNETİCİ PANELİ (ADMIN DASHBOARD) ---

@app.route('/admin/dashboard')
def admin_dashboard():
    # Güvenlik Kontrolü
    if not session.get('logged_in') or not session.get('is_admin'):
        flash('Yönetici erişimi gerekli.', 'error')
        return redirect(url_for('index'))

    cur = mysql.connection.cursor()
    
    # GÜNCELLEME BURADA: GROUP_CONCAT ile hizmet isimlerini 'service_names' olarak çekiyoruz
    cur.execute("""
        SELECT 
            a.appointment_id, 
            u.full_name as user_name, 
            a.appointment_date, 
            a.total_price, 
            a.status, 
            a.payment_method,
            GROUP_CONCAT(s.name SEPARATOR ', ') as service_names 
        FROM appointments a
        JOIN users u ON a.user_id = u.user_id
        LEFT JOIN appointment_services aps ON a.appointment_id = aps.appointment_id
        LEFT JOIN services s ON aps.service_id = s.service_id
        GROUP BY a.appointment_id
        ORDER BY a.appointment_date DESC
    """)
    appointments = cur.fetchall()
    
    # Tasarımları Çekme
    cur.execute("SELECT * FROM designs ORDER BY design_id DESC")
    designs = cur.fetchall()
    cur.close()

    return render_template('admin_dashboard.html', appointments=appointments, designs=designs)

@app.route('/admin/designs/add', methods=['POST'])
def admin_add_design():
    if not session.get('is_admin'): return redirect(url_for('index'))

    file = request.files.get('file')
    name = request.form.get('design_name')
    price = request.form.get('design_price')

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        ext = filename.rsplit('.', 1)[1].lower()
        unique_name = f"design_{datetime.now().strftime('%Y%m%d%H%M%S')}.{ext}"
        
        # diff/static/uploads/designs klasörüne kaydet
        design_folder = os.path.join(app.root_path, 'diff', 'static', 'uploads', 'designs')
        os.makedirs(design_folder, exist_ok=True)
        
        file.save(os.path.join(design_folder, unique_name))
        db_path = f'uploads/designs/{unique_name}'

        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO designs (design_name, design_price, design_image) VALUES (%s,%s,%s)", (name, price, db_path))
        mysql.connection.commit()
        cur.close()
        flash('Tasarım eklendi.', 'success')
    
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/designs/delete/<int:design_id>', methods=['POST'])
def admin_delete_design(design_id):
    if not session.get('is_admin'): return redirect(url_for('index'))
    
    cur = mysql.connection.cursor()
    cur.execute("SELECT design_image FROM designs WHERE design_id = %s", [design_id])
    design = cur.fetchone()
    
    if design:
        # Dosyayı silmeye çalış
        try:
            full_path = os.path.join(app.root_path, 'diff', 'static', design['design_image'])
            if os.path.exists(full_path):
                os.remove(full_path)
        except: pass
        
        cur.execute("DELETE FROM designs WHERE design_id = %s", [design_id])
        mysql.connection.commit()
        flash('Tasarım silindi.', 'success')
    
    cur.close()
    return redirect(url_for('admin_dashboard'))

# --- 5. RANDEVU İŞLEMLERİ ---

@app.route('/randevu', methods=['GET', 'POST'])
@login_required 
def randevu_page():
    user_id = session.get('user_id')
    cur = mysql.connection.cursor() 
    
    # Verileri Çek
    cur.execute("SELECT * FROM services ORDER BY service_id")
    services = cur.fetchall()
    cur.execute("SELECT * FROM designs ORDER BY design_id")
    designs = cur.fetchall()
    
    if request.method == 'POST':
        services_ids = request.form.getlist('selected_services')
        design_id = request.form.get('selected_design')
        date = request.form.get('appointment_date')
        time = request.form.get('appointment_time')
        price = request.form.get('total_price')
        pay_method = request.form.get('payment_method')
        length = request.form.get('nail_length')
        shape = request.form.get('nail_shape')
        
        custom_path = None
        if 'custom_design_file' in request.files:
            f = request.files['custom_design_file']
            if f.filename != '' and allowed_file(f.filename):
                fname = secure_filename(f.filename)
                ext = fname.rsplit('.', 1)[1].lower()
                unique = f"custom_{user_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.{ext}"
                custom_folder = os.path.join(app.root_path, 'diff', 'static', 'uploads', 'custom')
                os.makedirs(custom_folder, exist_ok=True)
                f.save(os.path.join(custom_folder, unique))
                custom_path = f"uploads/custom/{unique}"

        dt = datetime.strptime(f"{date} {time}", '%Y-%m-%d %H:%M')
        
        try:
            # Ana Randevu Kaydı
            design_id_int = int(design_id) if design_id and design_id.isdigit() else None
            primary_service = services_ids[0] if services_ids else None
            
            cur.execute("""INSERT INTO appointments 
                (user_id, service_id, design_id, custom_design_path, appointment_date, total_price, status, payment_method, nail_length, nail_shape) 
                VALUES (%s, %s, %s, %s, %s, %s, 'pending', %s, %s, %s)""", 
                (user_id, primary_service, design_id_int, custom_path, dt, price, pay_method, length, shape))
            
            appt_id = cur.lastrowid
            
            # Ek Hizmetler
            for sid in services_ids:
                cur.execute("INSERT INTO appointment_services (appointment_id, service_id) VALUES (%s, %s)", (appt_id, sid))
            
            mysql.connection.commit()
            cur.close()
            flash('Randevu oluşturuldu!', 'success')
            return redirect(url_for('profile_page'))
            
        except Exception as e:
            mysql.connection.rollback()
            print(f"Hata: {e}")
            flash('Hata oluştu.', 'error')
    
    cur.close()
    return render_template('randevu.html', services=services, designs=designs, today=datetime.now(), is_update=False, appointment=None)

@app.route('/update_appointment/<int:appointment_id>', methods=['GET', 'POST'])
@login_required
def update_appointment(appointment_id):
    user_id = session.get('user_id')
    cur = mysql.connection.cursor()
    
    cur.execute("SELECT * FROM appointments WHERE appointment_id=%s AND user_id=%s", (appointment_id, user_id))
    appt = cur.fetchone()
    
    if not appt:
        flash('Randevu bulunamadı.', 'error')
        return redirect(url_for('profile_page'))
        
    # --- POST (Güncelleme İşlemi) ---
    if request.method == 'POST':
        new_service_ids = request.form.getlist('selected_services') 
        new_design_id_raw = request.form.get('selected_design') 
        new_date = request.form.get('appointment_date')
        new_time = request.form.get('appointment_time')
        new_total_price = request.form.get('total_price') 
        new_length = request.form.get('nail_length')
        new_shape = request.form.get('nail_shape')
        
        new_datetime = datetime.strptime(f"{new_date} {new_time}", '%Y-%m-%d %H:%M')
        new_design_id = int(new_design_id_raw) if new_design_id_raw and new_design_id_raw.isdigit() else None
        
        try:
            # Ana Randevuyu Güncelle
            cur.execute("""
                UPDATE appointments SET 
                    appointment_date = %s, 
                    design_id = %s,
                    total_price = %s,
                    nail_length = %s,  
                    nail_shape = %s,
                    status = 'pending' 
                WHERE appointment_id = %s AND user_id = %s
            """, (new_datetime, new_design_id or None, new_total_price, new_length, new_shape, appointment_id, user_id))
            
            # Hizmetleri Sıfırla ve Yeniden Ekle
            cur.execute("DELETE FROM appointment_services WHERE appointment_id = %s", [appointment_id])
            for service_id_str in new_service_ids:
                cur.execute("""
                    INSERT INTO appointment_services (appointment_id, service_id) VALUES (%s, %s)
                """, (appointment_id, int(service_id_str)))

            mysql.connection.commit()
            flash('Randevu güncellendi.', 'success')
            cur.close()
            return redirect(url_for('profile_page'))

        except Exception as e:
            mysql.connection.rollback()
            flash(f'Hata: {e}', 'error')
            cur.close()
            return redirect(url_for('update_appointment', appointment_id=appointment_id))

    # --- GET (Formu Gösterme) ---
    cur.execute("SELECT service_id FROM appointment_services WHERE appointment_id = %s", [appointment_id])
    selected_service_ids = [row['service_id'] for row in cur.fetchall()]
    
    cur.execute("SELECT * FROM services")
    services = cur.fetchall()
    cur.execute("SELECT * FROM designs")
    designs = cur.fetchall()
    
    cur.close()
    
    return render_template('randevu.html', 
                           services=services, 
                           designs=designs, 
                           today=datetime.now(), 
                           is_update=True, 
                           appointment=appt, 
                           initial_date=appt['appointment_date'].strftime('%Y-%m-%d'), 
                           initial_time=appt['appointment_date'].strftime('%H:%M'),
                           selected_service_ids=selected_service_ids,
                           appointment_id=appointment_id)

@app.route('/delete_appointment/<int:appointment_id>', methods=['POST'])
@login_required
def delete_appointment(appointment_id):
    user_id = session.get('user_id')
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM appointments WHERE appointment_id=%s AND user_id=%s", (appointment_id, user_id))
    mysql.connection.commit()
    cur.close()
    flash('Randevu silindi.', 'success')
    return redirect(url_for('profile_page'))

@app.route('/api/booked-hours')
def get_booked_hours():
    date_str = request.args.get('date')
    if not date_str: return jsonify([])
    
    cur = mysql.connection.cursor()
    cur.execute("SELECT DATE_FORMAT(appointment_date, '%%H:%%i') as time FROM appointments WHERE DATE(appointment_date) = %s", [date_str])
    times = [r['time'] for r in cur.fetchall()]
    cur.close()
    return jsonify(times)

# --- 6. YORUM SİSTEMİ ---

@app.route('/submit_review', methods=['POST'])
@login_required
def submit_review():
    user_id = session['user_id']
    rating = request.form.get('rating')
    content = request.form.get('content')
    
    if rating and content:
        try:
            cur = mysql.connection.cursor()
            cur.execute("INSERT INTO reviews (user_id, rating, content) VALUES (%s, %s, %s)", (user_id, rating, content))
            mysql.connection.commit()
            cur.close()
            flash('Yorumunuz için teşekkürler!', 'success')
        except:
            flash('Hata oluştu.', 'error')
            
    return redirect(url_for('profile_page'))

if __name__ == '__main__':
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    app.run(debug=True)