import streamlit as st
import pandas as pd
import datetime
import os
from openai import OpenAI

# --- 設定 ---
LOG_FILE = "search_log.csv"
ADMIN_PASSWORD = "admin"  # 管理者画面に入るためのパスワード

# --- 関数: ログ保存（需要確認用） ---
def save_log(keyword, company_name, is_recommended, full_answer):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # ログデータの作成
    new_data = pd.DataFrame({
        "日時": [timestamp],
        "検索キーワード": [keyword],
        "対象サービス": [company_name],
        "推奨結果": ["〇" if is_recommended else "×"],
        "AI回答(抜粋)": [full_answer[:100] + "..."] # 長いので先頭だけ保存
    })
    
    # CSVファイルへの追記保存
    if not os.path.exists(LOG_FILE):
        new_data.to_csv(LOG_FILE, index=False, encoding="utf-8-sig")
    else:
        new_data.to_csv(LOG_FILE, mode='a', header=False, index=False, encoding="utf-8-sig")

# --- 関数: LLOMチェック実行 ---
def check_llom(api_key, keyword, company_name):
    try:
        client = OpenAI(api_key=api_key)
        
        # ユーザーが実際に検索しそうなプロンプトを投げる
        prompt = f"""
        あなたはユーザーの役に立つ検索アシスタントです。
        以下の質問に対して、具体的におすすめのサービスや商品、店舗名を5つリストアップして教えてください。
        それぞれの特徴も一言で添えてください。
        
        質問: 「{keyword}」
        """
        
        response = client.chat.completions.create(
            model="gpt-4o-mini", # コストが安く高速なモデル
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500
        )
        answer = response.choices[0].message.content
        
        # 自社名が含まれているか判定（大文字小文字を区別せず判定）
        is_recommended = company_name.lower() in answer.lower()
        return True, is_recommended, answer
        
    except Exception as e:
        return False, False, str(e)

# --- 画面構築 (Streamlit) ---
st.set_page_config(page_title="LLOM Checker", layout="wide")

# サイドバー設定
st.sidebar.title("🛠 設定・メニュー")
api_key = st.sidebar.text_input("OpenAI API Key", type="password", help="ご自身のAPIキーを入力してください")
st.sidebar.markdown("---")
view_mode = st.sidebar.radio("表示モード", ["🔍 ユーザー検索画面", "📊 管理者ダッシュボード"])

# === 1. ユーザー検索画面 ===
if view_mode == "🔍 ユーザー検索画面":
    st.title("🤖 AI検索・推奨チェッカー")
    st.markdown("""
    ChatGPTなどのAI検索で、**あなたのサービスが「おすすめ」として紹介されているか**を確認します。
    """)
    
    with st.container(border=True):
        col1, col2 = st.columns(2)
        with col1:
            keyword = st.text_input("狙っているキーワード", placeholder="例：渋谷 居酒屋 デート、会計ソフト おすすめ")
        with col2:
            company = st.text_input("確認したい自社名", placeholder="例：〇〇ダイニング、freee")
            
        check_btn = st.button("チェック開始", type="primary")
    
    if check_btn:
        if not api_key:
            st.error("サイドバーでAPIキーを入力してください。")
        elif not keyword or not company:
            st.warning("キーワードと自社名の両方を入力してください。")
        else:
            with st.spinner("AIに問い合わせ中..."):
                success, is_rec, answer = check_llom(api_key, keyword, company)
                
                if success:
                    # ログを保存（ここで管理者に需要データが溜まる）
                    save_log(keyword, company, is_rec, answer)
                    
                    st.divider()
                    if is_rec:
                        st.success(f"🎉 **おめでとうございます！「{company}」は推奨されています！**")
                    else:
                        st.error(f"⚠️ **残念ながら圏外です...** 今回の回答には「{company}」は含まれませんでした。")
                    
                    with st.expander("AIの実際の回答を見る", expanded=True):
                        st.markdown(answer)
                else:
                    st.error(f"エラーが発生しました: {answer}")

# === 2. 管理者ダッシュボード ===
elif view_mode == "📊 管理者ダッシュボード":
    st.title("管理者用: 需要分析データ")
    
    password = st.sidebar.text_input("管理者パスワード", type="password")
    if password == ADMIN_PASSWORD:
        st.success("ログインしました")
        
        if os.path.exists(LOG_FILE):
            df = pd.read_csv(LOG_FILE)
            
            # 直近のログを表示
            st.subheader("📋 最新の検索ログ")
            st.dataframe(df.sort_values("日時", ascending=False), use_container_width=True)
            
            # 簡易分析
            st.subheader("📈 人気の検索キーワード（需要）")
            if not df.empty:
                st.bar_chart(df["検索キーワード"].value_counts())
            
            # CSVダウンロード
            csv = df.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label="ログデータをCSVでダウンロード",
                data=csv,
                file_name='llom_logs.csv',
                mime='text/csv',
            )
        else:
            st.info("まだ検索データがありません。ユーザー画面でテストを行ってください。")
    else:
        st.warning("管理者パスワードを入力してください。(初期設定: admin)")