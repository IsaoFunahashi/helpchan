import streamlit as st
import sqlite3
import pandas as pd
import hashlib

# --- ユーティリティ関数 ---
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
    # ユーザーテーブル
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, password TEXT, 
                  affiliation TEXT, position TEXT, keywords TEXT, role TEXT)''')
    
    # 仕事テーブル（項目を変更：内容、キーワード、登録者、担当課）
    c.execute('''CREATE TABLE IF NOT EXISTS jobs 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  title TEXT, 
                  content TEXT, 
                  keywords TEXT, 
                  created_by TEXT, 
                  department TEXT)''')
    
    # 過去の参加履歴
    c.execute('''CREATE TABLE IF NOT EXISTS work_history 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, user_name TEXT, job_title TEXT)''')
    conn.commit()
    return conn

conn = init_db()

# --- セッション状態の初期化 ---
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
            new_affi = st.text_input("所属名")
            new_pos = st.text_input("職位")
            new_key = st.text_area("自分のスキル・興味キーワード（カンマ区切り）")
            role = st.selectbox("権限", ["user", "admin"])
            if st.form_submit_button("登録"):
                c = conn.cursor()
                c.execute('INSERT INTO users(name, password, affiliation, position, keywords, role) VALUES (?,?,?,?,?,?)', 
                          (new_user, make_hashes(new_password), new_affi, new_pos, new_key, role))
                conn.commit()
                st.success("登録完了！ログインしてください")

else:
    # ログイン後サイドバー
    st.sidebar.write(f"Logged in: **{st.session_state['user_name']}** ({st.session_state['role']})")
    menu = ["マイページ", "案件の登録", "マッチング", "ユーザー一覧", "仕事一覧"]
    choice = st.sidebar.selectbox("メニュー", menu)
    if st.sidebar.button("ログアウト"):
        st.session_state.update({'logged_in': False, 'user_name': '', 'role': 'user'})
        st.rerun()

    # --- 1. マイページ ---
    if choice == "マイページ":
        st.subheader("📝 プロフィール詳細")
        user_data = pd.read_sql_query("SELECT * FROM users WHERE name = ?", conn, params=(st.session_state['user_name'],)).iloc[0]
        with st.container(border=True):
            st.markdown(f"### {user_data['name']}")
            st.write(f"🏢 **所属:** {user_data['affiliation']}")
            st.write(f"🏷️ **職位:** {user_data['position']}")
            st.write(f"🔍 **キーワード:** {user_data['keywords']}")

    # --- 2. 案件の登録 ---
    elif choice == "案件の登録":
        st.subheader("💼 新規案件の登録")
        with st.form("job_reg_form"):
            title = st.text_input("仕事のタイトル")
            content = st.text_area("仕事の内容（詳細）")
            keywords = st.text_input("キーワード（カンマ区切り。例: Python, 事務, 企画）")
            department = st.text_input("担当課")
            # 登録者は自動的にログインユーザーになる
            st.info(f"登録者: {st.session_state['user_name']}")
            
            if st.form_submit_button("案件を公開する"):
                if title and content and department:
                    c = conn.cursor()
                    c.execute('''INSERT INTO jobs (title, content, keywords, created_by, department) 
                                 VALUES (?, ?, ?, ?, ?)''', 
                              (title, content, keywords, st.session_state['user_name'], department))
                    conn.commit()
                    st.success("案件を登録しました！")
                else:
                    st.error("必須項目（タイトル・内容・担当課）を入力してください")

    # --- 3. マッチング ---
    elif choice == "マッチング":
        st.subheader("🔍 あなたにオススメの案件")
        user_data = pd.read_sql_query("SELECT keywords FROM users WHERE name = ?", conn, params=(st.session_state['user_name'],)).iloc[0]
        jobs_df = pd.read_sql_query("SELECT * FROM jobs", conn)
        
        user_keys = [k.strip().lower() for k in user_data['keywords'].replace('\n', ',').split(',') if k.strip()]
        
        matches = []
        for _, job in jobs_df.iterrows():
            job_keys = [k.strip().lower() for k in job['keywords'].replace('\n', ',').split(',') if k.strip()]
            # ユーザーのキーワードと仕事のキーワードの重なりをチェック
            common = set(user_keys).intersection(set(job_keys))
            if common:
                matches.append({
                    "案件名": job['title'],
                    "担当課": job['department'],
                    "一致したキーワード": ", ".join(common),
                    "マッチ数": len(common)
                })
        
        if matches:
            st.table(pd.DataFrame(matches).sort_values(by="マッチ数", ascending=False))
        else:
            st.info("あなたのキーワードに一致する案件はまだありません。")

    # --- 4. ユーザー一覧 ---
    elif choice == "ユーザー一覧":
        st.subheader("👥 ユーザー詳細一覧")
        users_df = pd.read_sql_query("SELECT * FROM users", conn)
        for _, row in users_df.iterrows():
            with st.expander(f"👤 {row['name']} （{row['affiliation']}）"):
                st.write(f"**職位:** {row['position']}")
                st.write(f"**キーワード:** {row['keywords']}")
                if st.session_state['role'] == 'admin':
                    if st.button(f"❌ ユーザー削除", key=f"del_u_{row['id']}"):
                        c = conn.cursor()
                        c.execute("DELETE FROM users WHERE id=?", (row['id'],))
                        conn.commit()
                        st.rerun()

    # --- 5. 仕事一覧 (新項目に対応) ---
    elif choice == "仕事一覧":
        st.subheader("📋 案件一覧")
        jobs_df = pd.read_sql_query("SELECT * FROM jobs", conn)
        
        if jobs_df.empty:
            st.write("現在登録されている案件はありません。")
        else:
            for _, row in jobs_df.iterrows():
                with st.expander(f"📌 {row['title']} （担当: {row['department']}）"):
                    st.write(f"**【仕事の内容】**\n\n{row['content']}")
                    st.write(f"**【キーワード】** {row['keywords']}")
                    st.write(f"**【登録者】** {row['created_by']}")
                    
                    # 削除権限: 管理者 または 作成者
                    if st.session_state['role'] == 'admin' or row['created_by'] == st.session_state['user_name']:
                        if st.button(f"🗑️ 案件を削除", key=f"del_j_{row['id']}"):
                            c = conn.cursor()
                            c.execute("DELETE FROM jobs WHERE id=?", (row['id'],))
                            conn.commit()
                            st.rerun()

conn.close()
