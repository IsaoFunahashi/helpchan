import streamlit as st
import sqlite3
import pandas as pd
import hashlib
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- ユーティリティ関数：メール送信 ---
def send_email(to_email, subject, body):
    # StreamlitのSecretsから設定を読み込む
    try:
        smtp_server = st.secrets["email"]["smtp_server"]
        smtp_port = st.secrets["email"]["smtp_port"]
        sender_email = st.secrets["email"]["sender_email"]
        sender_password = st.secrets["email"]["sender_password"]

        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
            server.login(sender_email, sender_password)
            server.send_message(msg)
        return True
    except Exception as e:
        st.error(f"メール送信エラー: {e}")
        return False

# --- ユーティリティ関数：パスワード ---
def make_hashes(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_hashes(password, hashed_text):
    if make_hashes(password) == hashed_text:
        return hashed_text
    return False

# --- データベース設定 ---
def init_db():
    conn = sqlite3.connect('matching_app.db')
    c = conn.cursor()
    # usersにemailを追加
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, password TEXT, 
                  email TEXT, affiliation TEXT, position TEXT, keywords TEXT, role TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS jobs 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  title TEXT, content TEXT, keywords TEXT, created_by TEXT, department TEXT)''')
    conn.commit()
    return conn

conn = init_db()

# --- セッション状態 ---
if 'logged_in' not in st.session_state:
    st.session_state.update({'logged_in': False, 'user_name': '', 'role': 'user'})

st.title("🤝 プロフェッショナル・マッチング")

# --- 認証フロー ---
if not st.session_state['logged_in']:
    tab1, tab2 = st.tabs(["ログイン", "新規ユーザー登録"])
    with tab1:
        username = st.text_input("ユーザー名", key="login_user")
        password = st.text_input("パスワード", type='password', key="login_pass")
        if st.button("ログイン"):
            c = conn.cursor()
            c.execute('SELECT password, role FROM users WHERE name = ?', (username,))
            data = c.fetchone()
            if data and check_hashes(password, data[0]):
                st.session_state.update({'logged_in': True, 'user_name': username, 'role': data[1]})
                st.rerun()
            else:
                st.error("ログイン情報が正しくありません")
    with tab2:
        st.subheader("👤 アカウント作成")
        with st.form("signup_form"):
            new_user = st.text_input("名前（フルネーム）")
            new_password = st.text_input("パスワード", type='password')
            new_email = st.text_input("メールアドレス") # 追加
            new_affi = st.text_input("所属名")
            new_pos = st.text_input("職位")
            new_key = st.text_area("キーワード（カンマ区切り）")
            role = st.selectbox("権限", ["user", "admin"])
            if st.form_submit_button("登録"):
                c = conn.cursor()
                c.execute('INSERT INTO users(name, password, email, affiliation, position, keywords, role) VALUES (?,?,?,?,?,?,?)', 
                          (new_user, make_hashes(new_password), new_email, new_affi, new_pos, new_key, role))
                conn.commit()
                st.success("登録完了！")

else:
    # ログイン後サイドバー
    st.sidebar.write(f"Logged in: **{st.session_state['user_name']}**")
    menu = ["マイページ", "案件の登録", "マッチング", "ユーザー一覧", "仕事一覧"]
    choice = st.sidebar.selectbox("メニュー", menu)
    if st.sidebar.button("ログアウト"):
        st.session_state.update({'logged_in': False, 'user_name': '', 'role': 'user'})
        st.rerun()

    # --- 2. 案件の登録 & マッチング通知 ---
    if choice == "案件の登録":
        st.subheader("💼 新規案件の登録")
        with st.form("job_reg_form"):
            title = st.text_input("仕事のタイトル")
            content = st.text_area("仕事の内容")
            keywords_input = st.text_input("キーワード（カンマ区切り）")
            department = st.text_input("担当課")
            
            if st.form_submit_button("案件を公開して通知を送る"):
                if title and content and department:
                    c = conn.cursor()
                    c.execute('''INSERT INTO jobs (title, content, keywords, created_by, department) 
                                 VALUES (?, ?, ?, ?, ?)''', 
                              (title, content, keywords_input, st.session_state['user_name'], department))
                    conn.commit()
                    
                    # --- マッチング通知ロジック ---
                    st.write("📩 マッチングするユーザーにメールを送信中...")
                    job_keys = [k.strip().lower() for k in keywords_input.split(',') if k.strip()]
                    
                    users_df = pd.read_sql_query("SELECT name, email, keywords FROM users", conn)
                    notified_count = 0
                    
                    for _, user in users_df.iterrows():
                        user_keys = [k.strip().lower() for k in user['keywords'].split(',') if k.strip()]
                        common = set(job_keys).intersection(set(user_keys))
                        
                        if common and user['email']:
                            subject = f"【マッチング通知】新しい案件「{title}」が登録されました"
                            body = f"{user['name']}様\n\nあなたのキーワード「{', '.join(common)}」に一致する新しい仕事が登録されました！\n\n■案件名: {title}\n■担当課: {department}\n■内容: {content}\n\nアプリにログインして詳細を確認してください。"
                            
                            if send_email(user['email'], subject, body):
                                notified_count += 1
                    
                    st.success(f"案件を登録し、{notified_count}名のユーザーに通知を送信しました。")
                else:
                    st.error("必須項目を入力してください")

    # (その他のメニュー: マイページ、マッチング、ユーザー一覧などは前回同様)
    elif choice == "ユーザー一覧":
        st.subheader("👥 ユーザー詳細一覧")
        users_df = pd.read_sql_query("SELECT name, email, affiliation, position, keywords FROM users", conn)
        st.table(users_df)

conn.close()
