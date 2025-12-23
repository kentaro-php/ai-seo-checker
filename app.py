import streamlit as st
import pandas as pd
import datetime
import os
from openai import OpenAI

# --- 1. Streamlitの基本設定（必ず一番最初に書く！） ---
st.set_page_config(page_title="LLOM Checker", layout="wide")

# --- 2. URLパラメータの取得とサイドバー非表示処理 ---
# URLに ?view=user があるか確認
query_params = st.query_params
is_user_view = "view" in query_params and query_params["view"] == "user"

if is_user_view:
    st.markdown(
        """
        <style>
            [data-testid="stSidebar"] {
                display: none;
            }
        </style>
        """,
        unsafe_allow_html=True
    )

# --- 設定 ---
LOG_FILE = "search_log.csv"
ADMIN_PASSWORD = "admin"
LOG_COLUMNS = ["日時", "検索キーワード", "対象サービス", "推奨結果", "AI回答(抜粋)"]

# --- 関数: ログ保存 ---
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

# --- 関数: ログ読み込み ---
def load_log():
    if not os.path.exists(LOG_FILE) or os.stat(LOG_FILE).st_size == 0:
        return pd.DataFrame(columns=LOG_COLUMNS)
    try:
        df = pd.read_csv(LOG_FILE)
        if not all(col in df.columns for col in ["日時", "検索キーワード"]):
            raise ValueError("ヘッダー破損")
        return df
    except Exception:
        return None

# --- 関数: LLOMチェック実行 ---
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

# --- 画面構築 ---

# ▼ APIキーの処理（重要）
# ユーザーモードならSecretsから取得、なければサイドバー入力を使う
# Streamlit CloudのSecrets機能を使うことを強く推奨しますが、
# 一旦動作させるためにサイドバー入力を優先し、なければ環境変数やSecretsを見に行くロジックにします。

# デフォルト値を設定
api_key = ""
view_mode = "🔍 ユーザー検索画面" # デフォルト

# サイドバーの中身（ユーザーモードでもコード上は実行されるが、CSSで見えなくなる）
st.sidebar.title("🛠 設定・メニュー")

# Secretsにキーがあればそれをデフォルトに、なければ空欄
default_key = st.secrets.get("OPENAI_API_KEY", "") if "OPENAI_API_KEY" in st.secrets else ""
input_api_key = st.sidebar.text_input("OpenAI API Key", value=default_key, type="password")

# 優先順位: サイドバー入力 > Secrets
api_key = input_api_key

st.sidebar.markdown("---")
view_mode_select = st.sidebar.radio("表示モード", ["🔍 ユーザー検索画面", "📊 管理者ダッシュボード"])

# URLパラメータでユーザーモード指定があれば、強制的にユーザー画面扱いにする
if is_user_view:
    view_mode = "🔍 ユーザー検索画面"
else:
    view_mode = view_mode_select


# === 1. ユーザー検索画面 ===
if view_mode == "🔍 ユーザー検索画面":
    if not is_user_view:
        # 管理者がプレビューしているときだけタイトルを出す（埋め込み時はHTML側でタイトル出してるので不要かも）
        st.title("🤖 AI検索・推奨チェッカー")
    else:
        # 埋め込み時は上部の余白を少し詰めるなどの調整（任意）
        st.write("") 

    with st.container(border=True):
        col1, col2 = st.columns(2)
        with col1:
            keyword = st.text_input("狙っているキーワード", placeholder="例：渋谷 居酒屋 デート")
        with col2:
            company = st.text_input("確認したい自社名", placeholder="例：〇〇ダイニング")
            
        check_btn = st.button("チェック開始", type="primary")
    
    if check_btn:
        if not api_key:
            st.error("APIキーが設定されていません。管理者に連絡してください。")
        elif not keyword or not company:
            st.warning("項目をすべて入力してください。")
        else:
            with st.spinner("AIに問い合わせ中..."):
                success, is_rec, answer = check_llom(api_key, keyword, company)
                
                if success:
                    save_log(keyword, company, is_rec, answer)
                    st.divider()
                    if is_rec:
                        st.success(f"🎉 **「{company}」は推奨されています！**")
                    else:
                        st.error(f"⚠️ **圏外です**")
                    
                    with st.expander("AIの回答詳細", expanded=True):
                        st.markdown(answer)
                else:
                    st.error(f"エラー: {answer}")

# === 2. 管理者ダッシュボード ===
elif view_mode == "📊 管理者ダッシュボード":
    st.title("管理者用: 需要分析")
    
    # ユーザーモードでサイドバーが隠れている場合、ここには到達できないので安全
    password = st.sidebar.text_input("管理者パスワード", type="password")
    
    if password == ADMIN_PASSWORD:
        st.success("ログイン中")
        df = load_log()
        
        if df is not None:
            if not df.empty:
                st.subheader("📋 最新ログ")
                st.dataframe(df.sort_values("日時", ascending=False), use_container_width=True)
                st.subheader("📈 人気キーワード")
                st.bar_chart(df["検索キーワード"].value_counts())
                csv = df.to_csv(index=False).encode('utf-8-sig')
                st.download_button("CSVダウンロード", data=csv, file_name='llom_logs.csv', mime='text/csv')
                
                with st.expander("⚠️ データをリセットする"):
                     if st.button("ログを全削除する", type="primary"):
                        if os.path.exists(LOG_FILE):
                            os.remove(LOG_FILE)
                            st.rerun()
            else:
                st.info("まだデータがありません。")
        else:
            st.error("⚠️ **データファイルが破損しています**")
            if st.button("💥 壊れたデータを削除して修復する", type="primary"):
                if os.path.exists(LOG_FILE):
                    os.remove(LOG_FILE)
                st.rerun()
    else:
        st.warning("サイドバーでパスワードを入力してください (初期: admin)")