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
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, password TEXT, 
                  affiliation TEXT, position TEXT, keywords TEXT, role TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS jobs 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, req_skills TEXT, created_by TEXT)''')
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
            new_affi = st.text_input("所属名（会社・部署など）")
            new_pos = st.text_input("職位（マネージャー、エンジニア等）")
            new_key = st.text_area("興味・スキルキーワード（カンマ区切り）")
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
    menu = ["マイページ", "過去の仕事登録", "案件を探す", "ユーザー一覧", "仕事一覧"]
    choice = st.sidebar.selectbox("メニュー", menu)
    if st.sidebar.button("ログアウト"):
        st.session_state.update({'logged_in': False, 'user_name': '', 'role': 'user'})
        st.rerun()

    # --- 1. マイページ ---
    if choice == "マイページ":
        st.subheader("📝 プロフィール詳細")
        user_data = pd.read_sql_query("SELECT * FROM users WHERE name = ?", conn, params=(st.session_state['user_name'],)).iloc[0]
        history_df = pd.read_sql_query("SELECT job_title FROM work_history WHERE user_name = ?", conn, params=(st.session_state['user_name'],))
        
        with st.container(border=True):
            st.markdown(f"### {user_data['name']}")
            st.write(f"🏢 **所属:** {user_data['affiliation']}")
            st.write(f"🏷️ **職位:** {user_data['position']}")
            st.write(f"🔍 **キーワード:** {user_data['keywords']}")
            st.write("---")
            st.write("📜 **過去に参加した仕事:**")
            if not history_df.empty:
                for h in history_df['job_title']:
                    st.write(f"- {h}")
            else:
                st.caption("履歴はまだありません")

    # --- 2. 過去の仕事登録 ---
    elif choice == "過去の仕事登録":
        st.subheader("✅ 参加実績の追加")
        job_name = st.text_input("参加した仕事の名前")
        if st.button("履歴に追加"):
            c = conn.cursor()
            c.execute("INSERT INTO work_history (user_name, job_title) VALUES (?, ?)", (st.session_state['user_name'], job_name))
            conn.commit()
            st.success("履歴を更新しました")

    # --- 3. 案件を探す ---
    elif choice == "案件を探す":
        st.subheader("🔍 あなたにオススメの案件")
        user_data = pd.read_sql_query("SELECT keywords FROM users WHERE name = ?", conn, params=(st.session_state['user_name'],)).iloc[0]
        jobs_df = pd.read_sql_query("SELECT * FROM jobs", conn)
        keywords = [k.strip().lower() for k in user_data['keywords'].replace('\n', ',').split(',') if k.strip()]
        matches = []
        for _, job in jobs_df.iterrows():
            job_text = (job['title'] + " " + job['req_skills']).lower()
            found = [k for k in keywords if k in job_text]
            if found:
                matches.append({"案件名": job['title'], "一致キーワード": ", ".join(found), "マッチ数": len(found)})
        if matches:
            st.table(pd.DataFrame(matches).sort_values(by="マッチ数", ascending=False))
        else:
            st.info("キーワードに一致する案件がありません。")

    # --- 4. ユーザー一覧 (詳細閲覧機能) ---
    elif choice == "ユーザー一覧":
        st.subheader("👥 登録ユーザー詳細一覧")
        # データベースから全ユーザー情報を取得
        users_df = pd.read_sql_query("SELECT * FROM users", conn)
        
        if users_df.empty:
            st.warning("登録されているユーザーはいません。")
        else:
            for _, row in users_df.iterrows():
                # 名前と所属をタイトルにした折りたたみパネル
                with st.expander(f"👤 {row['name']} （{row['affiliation']}）"):
                    col1, col2 = st.columns([2, 1])
                    
                    with col1:
                        st.write(f"**職位:** {row['position']}")
                        st.write(f"**キーワード:** {row['keywords']}")
                        
                        # そのユーザーの仕事履歴を取得して表示
                        h_df = pd.read_sql_query("SELECT job_title FROM work_history WHERE user_name = ?", conn, params=(row['name'],))
                        st.write("**過去の参加実績:**")
                        if not h_df.empty:
                            st.write(", ".join(h_df['job_title'].tolist()))
                        else:
                            st.write("実績なし")
                    
                    with col2:
                        st.write(f"**権限:** `{row['role']}`")
                        # 管理者の場合のみ削除ボタンを表示
                        if st.session_state['role'] == 'admin':
                            if st.button(f"❌ 削除", key=f"del_u_{row['id']}"):
                                c = conn.cursor()
                                c.execute("DELETE FROM users WHERE id=?", (row['id'],))
                                c.execute("DELETE FROM work_history WHERE user_name=?", (row['name'],))
                                conn.commit()
                                st.warning(f"{row['name']} を削除しました。")
                                st.rerun()

    # --- 5. 仕事一覧 ---
    elif choice == "仕事一覧":
        st.subheader("📋 案件の管理")
        jobs_df = pd.read_sql_query("SELECT * FROM jobs", conn)
        for _, row in jobs_df.iterrows():
            with st.expander(f"📌 {row['title']} (投稿: {row['created_by']})"):
                st.write(f"内容: {row['req_skills']}")
                if st.session_state['role'] == 'admin' or row['created_by'] == st.session_state['user_name']:
                    if st.button(f"🗑️ 削除", key=f"del_j_{row['id']}"):
                        c = conn.cursor()
                        c.execute("DELETE FROM jobs WHERE id=?", (row['id'],))
                        conn.commit()
                        st.rerun()

conn.close()