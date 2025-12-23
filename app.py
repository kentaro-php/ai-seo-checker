import streamlit as st
import pandas as pd
import datetime
import os
from openai import OpenAI

# --- 1. Streamlitの基本設定（最優先） ---
st.set_page_config(page_title="LLOM Checker", layout="centered")

# --- 2. デザイン調整（CSS） ---
st.markdown("""
    <style>
        header {visibility: hidden;}
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        .block-container {
            padding-top: 1rem;
            padding-bottom: 1rem;
        }
        div.stButton > button {
            width: 100%;
            font-weight: bold;
        }
    </style>
""", unsafe_allow_html=True)

# --- 3. URLパラメータの取得 ---
# ストリームリットのバージョンによって挙動が違う可能性があるため安全に取得
try:
    query_params = st.query_params
except AttributeError:
    query_params = {} # 古いバージョンの場合の予備動作

is_user_view = "view" in query_params and query_params["view"] == "user"

if is_user_view:
    st.markdown(
        """
        <style>
            [data-testid="stSidebar"] { display: none; }
        </style>
        """,
        unsafe_allow_html=True
    )

# --- 設定 ---
LOG_FILE = "search_log.csv"
ADMIN_PASSWORD = "admin"
LOG_COLUMNS = ["日時", "検索キーワード", "対象サービス", "推奨結果", "AI回答(抜粋)"]

# --- 関数群 ---
def save_log(keyword, company_name, is_recommended, full_answer):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    clean_answer = full_answer[:100].replace("\n", " ").replace(",", "、") + "..."
    new_data = pd.DataFrame([[
        timestamp, keyword, company_name, "〇" if is_recommended else "×", clean_answer
    ]], columns=LOG_COLUMNS)
    
    if not os.path.exists(LOG_FILE) or os.stat(LOG_FILE).st_size == 0:
        new_data.to_csv(LOG_FILE, index=False, encoding="utf-8-sig")
    else:
        new_data.to_csv(LOG_FILE, mode='a', header=False, index=False, encoding="utf-8-sig")

def load_log():
    if not os.path.exists(LOG_FILE) or os.stat(LOG_FILE).st_size == 0:
        return pd.DataFrame(columns=LOG_COLUMNS)
    try:
        df = pd.read_csv(LOG_FILE)
        return df
    except Exception:
        return None

def check_llom(api_key, keyword, company_name):
    try:
        client = OpenAI(api_key=api_key)
        prompt = f"""
        あなたはユーザーの役に立つ検索アシスタントです。
        以下の質問に対して、具体的におすすめのサービスや商品、店舗名を5つリストアップして教えてください。
        それぞれの特徴も一言で添えてください。
        
        質問: 「{keyword}」
        """
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500
        )
        answer = response.choices[0].message.content
        is_recommended = company_name.lower() in answer.lower()
        return True, is_recommended, answer
    except Exception as e:
        return False, False, str(e)

# --- メイン処理 ---

# ▼▼▼【修正ポイント】Secretsを安全に読み込む処理 ▼▼▼
def get_secret_key():
    try:
        # secretsが存在し、かつキーがある場合のみ取得
        if hasattr(st, "secrets") and "OPENAI_API_KEY" in st.secrets:
            return st.secrets["OPENAI_API_KEY"]
    except (FileNotFoundError, AttributeError):
        # ファイルがない、または設定されていない場合は無視する
        pass
    return ""

default_key = get_secret_key()
# ▲▲▲ 修正ここまで ▲▲▲

api_key = ""
view_mode = "🔍 ユーザー検索画面" 

# サイドバー（ユーザーモードでは非表示）
st.sidebar.title("🛠 設定・メニュー")
input_api_key = st.sidebar.text_input("OpenAI API Key", value=default_key, type="password")
api_key = input_api_key

st.sidebar.markdown("---")
view_mode_select = st.sidebar.radio("表示モード", ["🔍 ユーザー検索画面", "📊 管理者ダッシュボード"])

if is_user_view:
    view_mode = "🔍 ユーザー検索画面"
else:
    view_mode = view_mode_select

# === 画面表示 ===
if view_mode == "🔍 ユーザー検索画面":
    if not is_user_view:
        st.title("🤖 AI検索・推奨チェッカー")
    else:
        st.write("")

    with st.container(border=True):
        st.markdown("### 🔍 自社指名検索チェック")
        keyword = st.text_input("検索キーワード", placeholder="例：渋谷 居酒屋 デート")
        company = st.text_input("確認したい自社名", placeholder="例：〇〇ダイニング")
            
        check_btn = st.button("チェック開始", type="primary")
    
    if check_btn:
        if not api_key:
            st.error("APIキーが設定されていません。")
        elif not keyword or not company:
            st.warning("項目をすべて入力してください。")
        else:
            with st.spinner("AIが検索結果を分析中..."):
                success, is_rec, answer = check_llom(api_key, keyword, company)
                
                if success:
                    save_log(keyword, company, is_rec, answer)
                    st.divider()
                    if is_rec:
                        st.success(f"🎉 **「{company}」は推奨されています！**")
                    else:
                        st.error(f"⚠️ **圏外です（推奨リストに含まれていません）**")
                    
                    with st.expander("AIの回答詳細を見る", expanded=False):
                        st.markdown(answer)
                else:
                    st.error(f"APIエラー: {answer}")

elif view_mode == "📊 管理者ダッシュボード":
    st.title("管理者用: 需要分析")
    password = st.sidebar.text_input("管理者パスワード", type="password")
    
    if password == ADMIN_PASSWORD:
        st.success("ログイン成功")
        df = load_log()
        if df is not None and not df.empty:
            st.subheader("📋 最新の検索ログ")
            st.dataframe(df.sort_values("日時", ascending=False), use_container_width=True)
            csv = df.to_csv(index=False).encode('utf-8-sig')
            st.download_button("CSVダウンロード", data=csv, file_name='llom_logs.csv', mime='text/csv')
            
            with st.expander("⚠️ 危険な操作"):
                 if st.button("ログを全削除する", type="primary"):
                    if os.path.exists(LOG_FILE):
                        os.remove(LOG_FILE)
                        st.rerun()
        else:
            st.info("データがまだありません。")
    else:
        st.warning("閲覧するにはサイドバーで管理者パスワードを入力してください")