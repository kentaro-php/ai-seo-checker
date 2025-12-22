import streamlit as st
import openai
import pandas as pd

# --- ページ設定 ---
st.set_page_config(layout="wide", page_title="AI SEO Checker")

# --- URLパラメータを取得してモード判定 ---
# URLの末尾に ?mode=admin がついているか確認
query_params = st.query_params
is_admin_mode = query_params.get("mode") == "admin"

# --- CSS設定 ---
# 管理者モードでなければ、サイドバーやメニューを隠す
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
#  ここから画面の分岐
# ==========================================

if is_admin_mode:
    # ---------------------------
    # 📊 管理者ダッシュボード（裏画面）
    # ---------------------------
    st.sidebar.title("🔧 管理者メニュー")
    st.sidebar.success("管理者モードでログイン中")
    
    st.title("📊 管理者ダッシュボード")
    st.write("ここは管理者（あなた）しか見られないページです。")
    
    # ダミーデータのグラフなどを表示（必要に応じてカスタマイズしてください）
    st.subheader("今月の検索数推移")
    chart_data = pd.DataFrame({
        '日付': pd.date_range(start='2024-01-01', periods=7),
        '検索回数': [10, 15, 8, 22, 18, 30, 25]
    })
    st.line_chart(chart_data.set_index('日付'))
    
    st.info("※この画面は URL末尾に `?mode=admin` をつけた時だけ表示されます。")

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
                    response = openai.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {"role": "system", "content": "あなたはSEOコンサルタントです。"},
                            {"role": "user", "content": f"質問：「{keyword}」について教えて。\n\nこの回答の中に、「{brand_name}」は推奨されていますか？"}
                        ]
                    )
                    st.success("分析完了！")
                    st.write(response.choices[0].message.content)
                except Exception as e:
                    st.error(f"エラー: {e}")