import streamlit as st
import openai
import pandas as pd
import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- ページ設定 ---
st.set_page_config(layout="wide", page_title="AI SEO Checker")

# --- URLパラメータを取得してモード判定 ---
query_params = st.query_params
is_admin_mode = query_params.get("mode") == "admin"

# --- CSS設定 ---
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

# --- APIキーとGoogle認証 ---
try:
    # OpenAI
    openai.api_key = st.secrets["OPENAI_API_KEY"]
    
    # Google Sheets
    # Secretsから辞書型として読み込む
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds_dict = dict(st.secrets["gcp_service_account"])
    
    # private_keyの改行コード(\n)を正しく変換する処理
    if "\\n" in creds_dict["private_key"]:
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    
    # スプレッドシートを開く（名前で指定）
    sheet_name = "seo_logs" 
    sheet = client.open(sheet_name).sheet1
    
except Exception as e:
    st.error(f"設定エラー: {e}")
    st.stop()

# ==========================================
#  ログ保存用の関数（スプレッドシート版）
# ==========================================
def save_log_to_sheet(keyword, brand_name, result):
    """ユーザーの検索内容をスプレッドシートに追記する"""
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    # 行を追加
    sheet.append_row([now, keyword, brand_name, result])

# ==========================================
#  画面の分岐
# ==========================================

if is_admin_mode:
    # ---------------------------
    # 📊 管理者ダッシュボード
    # ---------------------------
    st.sidebar.title("🔧 管理者メニュー")
    st.sidebar.success("管理者モード: Google Sheets連携済み")
    
    st.title("📊 検索ログ・分析ダッシュボード")
    
    if st.button("最新データを読み込む"):
        st.cache_data.clear()
    
    try:
        # スプレッドシートから全データを取得
        data = sheet.get_all_records()
        
        if data:
            df = pd.DataFrame(data)
            # 日時でソート（新しい順）
            # もしカラム名がずれている場合は調整が必要ですが、基本はそのまま表示
            st.subheader(f"📝 検索履歴 (全{len(df)}件)")
            st.dataframe(df, use_container_width=True)
        else:
            st.info("まだデータがありません。")
            
    except Exception as e:
        st.error(f"データの読み込みに失敗しました: {e}")

else:
    # ---------------------------
    # 🔍 一般ユーザー向け画面
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
                    # AI分析
                    response = openai.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {"role": "system", "content": "あなたはSEOコンサルタントです。ユーザーの質問に対し、特定のブランドが推奨されているかをシミュレーションして答えてください。"},
                            {"role": "user", "content": f"質問：「{keyword}」について教えて。\n\nこの回答の中に、「{brand_name}」という名前は好意的に登場しますか？\n登場する場合は「推奨されています」と理由を、登場しない場合は「推奨されていません」と対策を簡潔に答えて。"}
                        ],
                        max_tokens=500
                    )
                    
                    result_text = response.choices[0].message.content
                    
                    # ★スプレッドシートに保存
                    save_log_to_sheet(keyword, brand_name, result_text)
                    
                    st.success("分析完了！")
                    st.markdown("### 🔍 分析結果")
                    st.write(result_text)
                    
                except Exception as e:
                    st.error(f"エラーが発生しました: {e}")