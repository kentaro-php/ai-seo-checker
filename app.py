import streamlit as st
import openai
import pandas as pd
import datetime
import os

# --- ページ設定 ---
st.set_page_config(layout="wide", page_title="AI SEO Checker")

# --- URLパラメータを取得してモード判定 ---
query_params = st.query_params
is_admin_mode = query_params.get("mode") == "admin"

# --- CSS設定（管理者以外はサイドバーを隠す） ---
if not is_admin_mode:
    hide_streamlit_style = """
                <style>
                #MainMenu {visibility: hidden;}
                footer {visibility: hidden;}
                header {visibility: hidden;}
                [data-testid="stSidebar"] {display: none;}
                </style>
                """
    st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# --- APIキーの読み込み ---
try:
    openai.api_key = st.secrets["OPENAI_API_KEY"]
except:
    st.error("APIキー設定エラー：SecretsにOPENAI_API_KEYを設定してください。")
    st.stop()

# ==========================================
#  ログ保存用の関数
# ==========================================
LOG_FILE = 'search_logs.csv'

def save_log(keyword, brand_name, result):
    """ユーザーの検索内容をCSVに保存する"""
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    # データフレームを作成
    new_data = pd.DataFrame({
        '日時': [now],
        'キーワード': [keyword],
        '自社名': [brand_name],
        'AIの回答': [result]
    })
    
    # ファイルがある場合は追記、なければ新規作成
    if os.path.exists(LOG_FILE):
        new_data.to_csv(LOG_FILE, mode='a', header=False, index=False)
    else:
        new_data.to_csv(LOG_FILE, mode='w', header=True, index=False)

# ==========================================
#  画面の分岐
# ==========================================

if is_admin_mode:
    # ---------------------------
    # 📊 管理者ダッシュボード（裏画面）
    # ---------------------------
    st.sidebar.title("🔧 管理者メニュー")
    st.sidebar.success("管理者モードでログイン中")
    
    st.title("📊 検索ログ・分析ダッシュボード")
    st.write("ユーザーが実際に検索した内容と、AIの回答履歴です。")
    
    # CSVファイルの読み込みと表示
    if os.path.exists(LOG_FILE):
        df = pd.read_csv(LOG_FILE)
        
        # 最新順に並び替え
        df = df.sort_values('日時', ascending=False)
        
        st.subheader(f"📝 検索履歴 (全{len(df)}件)")
        
        # テーブル表示（ダウンロードボタン付き）
        st.dataframe(df, use_container_width=True)
        
        # CSVダウンロードボタン
        csv = df.to_csv(index=False).encode('utf-8_sig')
        st.download_button(
            "📥 ログをダウンロード (CSV)",
            data=csv,
            file_name='seo_check_logs.csv',
            mime='text/csv',
        )
    else:
        st.info("まだ検索データがありません。")

else:
    # ---------------------------
    # 🔍 一般ユーザー向け画面（表画面）
    # ---------------------------
    st.title("🤖 AI検索・推奨チェッカー")
    st.write("ChatGPTなどのAI検索で、**あなたのサービスが「おすすめ」として紹介されているか**を確認します。")

    col1, col2 = st.columns(2)
    with col1:
        keyword = st.text_input("狙っているキーワード", placeholder="例：渋谷 居酒屋 デート")
    with col2:
        brand_name = st.text_input("確認したい自社名", placeholder="例：〇〇ダイニング")

    if st.button("チェック開始", type="primary"):
        if not keyword or not brand_name:
            st.warning("キーワードと自社名を入力してください。")
        else:
            with st.spinner('AIが分析中...'):
                try:
                    # AI分析実行
                    response = openai.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {"role": "system", "content": "あなたはSEOコンサルタントです。ユーザーの質問に対し、特定のブランドが推奨されているかをシミュレーションして答えてください。"},
                            {"role": "user", "content": f"質問：「{keyword}」について教えて。\n\nこの回答の中に、「{brand_name}」という名前は好意的に登場しますか？\n登場する場合は「推奨されています」と理由を、登場しない場合は「推奨されていません」と対策を簡潔に答えて。"}
                        ],
                        max_tokens=500
                    )
                    
                    result_text = response.choices[0].message.content
                    
                    # ★ここでログを保存！
                    save_log(keyword, brand_name, result_text)
                    
                    st.success("分析完了！")
                    st.markdown("### 🔍 分析結果")
                    st.write(result_text)
                    
                except Exception as e:
                    st.error(f"エラーが発生しました: {e}")