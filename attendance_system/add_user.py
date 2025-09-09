from app import app, db, User
from werkzeug.security import generate_password_hash

def add_user():
    with app.app_context():
        # Input data user baru
        print("=== TAMBAH USER BARU ===")
        username = input("Username: ")
        email = input("Email: ")
        password = input("Password: ")
        is_admin_input = input("Admin? (y/n): ").lower()
        
        is_admin = True if is_admin_input in ['y', 'yes', '1'] else False
        
        # Cek apakah username sudah ada
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            print(f"❌ User '{username}' sudah ada!")
            return
        
        # Cek apakah email sudah ada
        existing_email = User.query.filter_by(email=email).first()
        if existing_email:
            print(f"❌ Email '{email}' sudah digunakan!")
            return
        
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
            print(f"✅ User '{username}' berhasil ditambahkan sebagai {role}!")
        except Exception as e:
            print(f"❌ Error: {e}")
            db.session.rollback()

def list_users():
    with app.app_context():
        users = User.query.all()
        print("\n=== DAFTAR USER ===")
        print("ID | Username | Email | Role")
        print("-" * 40)
        for user in users:
            role = "Admin" if user.is_admin else "User"
            print(f"{user.id} | {user.username} | {user.email} | {role}")

if __name__ == '__main__':
    while True:
        print("\n=== MANAJEMEN USER ===")
        print("1. Tambah User")
        print("2. Lihat Daftar User")
        print("3. Keluar")
        
        choice = input("Pilih (1-3): ")
        
        if choice == '1':
            add_user()
        elif choice == '2':
            list_users()
        elif choice == '3':
            break
        else:
            print("❌ Pilihan tidak valid!")