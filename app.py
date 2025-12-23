import streamlit as st
import pandas as pd
import datetime
import os
from openai import OpenAI

# --- 設定 ---
LOG_FILE = "search_log.csv"
ADMIN_PASSWORD = "admin"  # 管理者パスワード
# 列名を固定定義
LOG_COLUMNS = ["日時", "検索キーワード", "対象サービス", "推奨結果", "AI回答(抜粋)"]

# --- 関数: ログ保存（安全版） ---
def save_log(keyword, company_name, is_recommended, full_answer):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # CSVを壊さないように改行やカンマを置換して保存
    clean_answer = full_answer[:100].replace("\n", " ").replace(",", "、") + "..."
    
    new_data = pd.DataFrame([[
        timestamp,
        keyword,
        company_name,
        "〇" if is_recommended else "×",
        clean_answer
    ]], columns=LOG_COLUMNS)
    
    # ファイルが存在しない、または空（0バイト）の場合はヘッダー付きで作成
    if not os.path.exists(LOG_FILE) or os.stat(LOG_FILE).st_size == 0:
        new_data.to_csv(LOG_FILE, index=False, encoding="utf-8-sig")
    else:
        # 存在する場合はデータのみ追記（ヘッダーなし）
        new_data.to_csv(LOG_FILE, mode='a', header=False, index=False, encoding="utf-8-sig")

# --- 関数: ログ読み込み（修復機能付き） ---
def load_log():
    # ファイルがない場合は空データを返す
    if not os.path.exists(LOG_FILE) or os.stat(LOG_FILE).st_size == 0:
        return pd.DataFrame(columns=LOG_COLUMNS)

    try:
        df = pd.read_csv(LOG_FILE)
        # ヘッダーチェック：必須カラムが含まれているか確認
        if not all(col in df.columns for col in ["日時", "検索キーワード"]):
            raise ValueError("ヘッダー破損")
        return df
    except Exception:
        # 読み込みに失敗した場合は None を返す（これで画面側に異常を伝える）
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

# --- 画面構築 (Streamlit) ---
st.set_page_config(page_title="LLOM Checker", layout="wide")

st.sidebar.title("🛠 設定・メニュー")
api_key = st.sidebar.text_input("OpenAI API Key", type="password")
st.sidebar.markdown("---")
view_mode = st.sidebar.radio("表示モード", ["🔍 ユーザー検索画面", "📊 管理者ダッシュボード"])

# === 1. ユーザー検索画面 ===
if view_mode == "🔍 ユーザー検索画面":
    st.title("🤖 AI検索・推奨チェッカー")
    
    with st.container(border=True):
        col1, col2 = st.columns(2)
        with col1:
            keyword = st.text_input("狙っているキーワード", placeholder="例：渋谷 居酒屋 デート")
        with col2:
            company = st.text_input("確認したい自社名", placeholder="例：〇〇ダイニング")
            
        check_btn = st.button("チェック開始", type="primary")
    
    if check_btn:
        if not api_key:
            st.error("サイドバーでAPIキーを入力してください。")
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
    
    password = st.sidebar.text_input("管理者パスワード", type="password")
    if password == ADMIN_PASSWORD:
        st.success("ログイン中")
        
        # データの読み込みを試みる
        df = load_log()
        
        if df is not None:
            # --- 正常な場合 ---
            if not df.empty:
                st.subheader("📋 最新ログ")
                st.dataframe(df.sort_values("日時", ascending=False), use_container_width=True)
                
                st.subheader("📈 人気キーワード")
                st.bar_chart(df["検索キーワード"].value_counts())
                
                csv = df.to_csv(index=False).encode('utf-8-sig')
                st.download_button("CSVダウンロード", data=csv, file_name='llom_logs.csv', mime='text/csv')
            else:
                st.info("まだデータがありません。ユーザー画面で検索を行ってください。")
                
            # 手動リセットボタン（開発中便利なので常設）
            with st.expander("⚠️ データをリセットする"):
                 if st.button("ログを全削除する", type="primary"):
                    if os.path.exists(LOG_FILE):
                        os.remove(LOG_FILE)
                        st.rerun()

        else:
            # --- エラー（データ破損）の場合 ---
            st.error("⚠️ **データファイルが破損しています**")
            st.warning("ファイル内のヘッダー情報がおかしくなっています（重複エラーなど）。以下のボタンで修復してください。")
            
            if st.button("💥 壊れたデータを削除して修復する", type="primary"):
                if os.path.exists(LOG_FILE):
                    os.remove(LOG_FILE)
                st.success("修復しました！再度ユーザー画面で検索を行ってください。")
                st.rerun()
            
    else:
        st.warning("パスワードを入力してください (初期: admin)")