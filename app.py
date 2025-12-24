import streamlit as st
import pandas as pd
import datetime
import os

# --- 1. Streamlitの基本設定 ---
st.set_page_config(page_title="LLOM Checker", layout="wide", initial_sidebar_state="collapsed")

# --- 2. [最強版] シームレス化のためのCSS ---
# これで「枠線」「フッター」「ヘッダー」をすべて強制的に消します
hide_streamlit_style = """
<style>
    /* 1. ヘッダー（右上のハンバーガーメニューやDeployボタン）を消す */
    header {
        visibility: hidden !important;
        height: 0px !important;
        display: none !important;
    }
    
    /* 2. フッター（Built with Streamlit / Fullscreen）を消す */
    /* 埋め込みモードのフッターバーもこれで消えます */
    footer {
        visibility: hidden !important;
        height: 0px !important;
        display: none !important;
    }
    
    /* 3. アプリ全体の余白を削除 */
    .block-container {
        padding-top: 0rem !important;
        padding-bottom: 0rem !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
    }
    
    /* 4. iframe埋め込み時の枠線対策 */
    iframe {
        border: none !important;
    }
    
    /* 5. 万が一コンテナの枠線が残ってしまっても、強制的に消すCSS */
    [data-testid="stVerticalBlockBorderWrapper"] {
        border: none !important;
        box-shadow: none !important;
        background-color: transparent !important;
    }
    
    /* 6. ビューワーバッジなどを消す */
    .stAppDeployButton {
        display: none !important;
    }
</style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# --- 3. URLパラメータ処理 ---
query_params = st.query_params
is_user_view = "view" in query_params and query_params["view"] == "user"

if is_user_view:
    st.markdown(
        """
        <style>
            [data-testid="stSidebar"] { display: none !important; }
            section[data-testid="stSidebar"] { display: none !important; }
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
    from openai import OpenAI
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
default_key = st.secrets.get("OPENAI_API_KEY", "") if "OPENAI_API_KEY" in st.secrets else ""
input_api_key = ""

if is_user_view:
    view_mode = "🔍 ユーザー検索画面"
    api_key = default_key
else:
    st.sidebar.title("🛠 設定")
    input_api_key = st.sidebar.text_input("OpenAI API Key", value=default_key, type="password")
    api_key = input_api_key
    view_mode_select = st.sidebar.radio("モード", ["🔍 ユーザー検索画面", "📊 管理者ダッシュボード"])
    view_mode = view_mode_select

# === 画面表示 ===
if view_mode == "🔍 ユーザー検索画面":
    
    # 【ここが重要】border=True を削除し、さらにCSSで強制排除
    with st.container(): 
        col1, col2 = st.columns(2)
        with col1:
            keyword = st.text_input("キーワード", placeholder="例：渋谷 居酒屋 デート", label_visibility="visible")
        with col2:
            company = st.text_input("自社名", placeholder="例：〇〇ダイニング", label_visibility="visible")
            
        check_btn = st.button("AIでチェックする", type="primary", use_container_width=True)
    
    if check_btn:
        if not api_key:
            st.error("システムエラー: API設定を確認してください")
        elif not keyword or not company:
            st.warning("キーワードと自社名を入力してください")
        else:
            with st.spinner("AIが検索結果を分析中..."):
                success, is_rec, answer = check_llom(api_key, keyword, company)
                
                if success:
                    save_log(keyword, company, is_rec, answer)
                    st.divider()
                    if is_rec:
                        st.success(f"🎉 **「{company}」は推奨されています！**")
                    else:
                        st.error(f"⚠️ **圏外です** (推奨リストに含まれていません)")
                    
                    with st.expander("詳細な分析結果を見る", expanded=False):
                        st.markdown(answer)
                else:
                    st.error(f"エラーが発生しました: {answer}")

elif view_mode == "📊 管理者ダッシュボード":
    st.title("管理者ダッシュボード")
    password = st.sidebar.text_input("管理者パスワード", type="password")
    
    if password == ADMIN_PASSWORD:
        st.success("認証成功")
        df = load_log()
        if df is not None and not df.empty:
            st.dataframe(df.sort_values("日時", ascending=False), use_container_width=True)
            st.download_button("CSVダウンロード", data=df.to_csv(index=False).encode('utf-8-sig'), file_name='log.csv')
        else:
            st.info("データなし")