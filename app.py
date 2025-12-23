import streamlit as st
import traceback

# --- 診断モード: エラー捕捉用ラッパー ---
try:
    # 1. 基本設定（これが失敗するとOh no画面になることが多い）
    st.set_page_config(page_title="LLOM Checker", layout="centered")

    # 2. 必要なライブラリのインポートテスト
    import pandas as pd
    import datetime
    import os
    from openai import OpenAI

    # --- ここからメインのアプリ処理 ---

    # CSSデザイン
    st.markdown("""
        <style>
            /* サイドバーを非表示 */
            [data-testid="stSidebar"] {
                display: none;
            }
            
            /* "Built with Streamlit" フッターを完全に消す（スペースも詰める） */
            footer {
                display: none !important;
            }

            /* ページ上部の装飾バー（カラーライン）や右上のメニューも隠したい場合 */
            header {
                visibility: hidden !important;
            }
            
            /* 右上の「...」メニューなども完全に消す場合 */
            #MainMenu {
                display: none !important;
            }
        </style>
    """, unsafe_allow_html=True)

    # URLパラメータ取得（安全策）
    try:
        query_params = st.query_params
    except Exception:
        query_params = {}

    is_user_view = "view" in query_params and query_params["view"] == "user"

    if is_user_view:
        st.markdown("""<style>[data-testid="stSidebar"] { display: none; }</style>""", unsafe_allow_html=True)

    # 設定値
    LOG_FILE = "search_log.csv"
    ADMIN_PASSWORD = "admin"
    LOG_COLUMNS = ["日時", "検索キーワード", "対象サービス", "推奨結果", "AI回答(抜粋)"]

    # 関数定義
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
        return pd.read_csv(LOG_FILE)

    def check_llom(api_key, keyword, company_name):
        client = OpenAI(api_key=api_key)
        prompt = f"""
        あなたはユーザーの役に立つ検索アシスタントです。
        以下の質問に対して、具体的におすすめのサービスや商品、店舗名を5つリストアップして教えてください。
        
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

    # APIキー取得（超安全策）
    def get_secret_key():
        try:
            # st.secretsへのアクセス自体をtryで囲む
            if hasattr(st, "secrets") and "OPENAI_API_KEY" in st.secrets:
                return st.secrets["OPENAI_API_KEY"]
        except Exception:
            pass
        return ""

    default_key = get_secret_key()
    api_key = ""
    view_mode = "🔍 ユーザー検索画面" 

    # サイドバー構築
    st.sidebar.title("🛠 設定・メニュー")
    input_api_key = st.sidebar.text_input("OpenAI API Key", value=default_key, type="password")
    api_key = input_api_key
    st.sidebar.markdown("---")
    view_mode_select = st.sidebar.radio("表示モード", ["🔍 ユーザー検索画面", "📊 管理者ダッシュボード"])

    if is_user_view:
        view_mode = "🔍 ユーザー検索画面"
    else:
        view_mode = view_mode_select

    # 画面表示ロジック
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
                with st.spinner("AI分析中..."):
                    try:
                        success, is_rec, answer = check_llom(api_key, keyword, company)
                        if success:
                            save_log(keyword, company, is_rec, answer)
                            st.divider()
                            if is_rec:
                                st.success(f"🎉 **「{company}」は推奨されています！**")
                            else:
                                st.error(f"⚠️ **圏外です**")
                            with st.expander("詳細"):
                                st.markdown(answer)
                        else:
                            st.error(f"エラー: {answer}")
                    except Exception as e:
                        st.error(f"実行エラー: {e}")

    elif view_mode == "📊 管理者ダッシュボード":
        st.title("管理者用: 需要分析")
        password = st.sidebar.text_input("管理者パスワード", type="password")
        if password == ADMIN_PASSWORD:
            st.success("ログイン成功")
            df = load_log()
            if df is not None and not df.empty:
                st.dataframe(df.sort_values("日時", ascending=False), use_container_width=True)
                csv = df.to_csv(index=False).encode('utf-8-sig')
                st.download_button("CSVダウンロード", data=csv, file_name='llom_logs.csv', mime='text/csv')
            else:
                st.info("データなし")

except Exception:
    st.error("🚨 アプリ起動中にエラーが発生しました")
    st.code(traceback.format_exc())