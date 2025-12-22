import streamlit as st
import openai

# --- ページ設定 ---
st.set_page_config(layout="wide")

# --- CSSで余計なメニューやヘッダーを隠す ---
hide_streamlit_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            [data-testid="stSidebar"] {display: none;} /* サイドバーを完全に隠す */
            </style>
            """
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# --- APIキーの読み込み（Secretsから） ---
try:
    openai.api_key = st.secrets["OPENAI_API_KEY"]
except:
    st.error("APIキーが設定されていません。管理者に連絡してください。")
    st.stop()

# --- メイン画面 ---
st.title("🤖 AI検索・推奨チェッカー")
st.write("ChatGPTなどのAI検索で、**あなたのサービスが「おすすめ」として紹介されているか**を確認します。")

# 入力フォーム（カラム分けで見やすく）
col1, col2 = st.columns(2)
with col1:
    keyword = st.text_input("狙っているキーワード", placeholder="例：渋谷 居酒屋 デート、会計ソフト おすすめ")
with col2:
    brand_name = st.text_input("確認したい自社名", placeholder="例：〇〇ダイニング、freee")

# 実行ボタン
if st.button("チェック開始", type="primary"):
    if not keyword or not brand_name:
        st.warning("キーワードと自社名を入力してください。")
    else:
        with st.spinner('AIが検索結果を分析中...（これには数秒〜数十秒かかります）'):
            try:
                # --- ここでOpenAIに問い合わせ ---
                # ※GPT-4o-miniを使用（安価で高速）
                response = openai.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "あなたは優秀なSEOコンサルタントです。ユーザーの質問に対し、特定のブランドが推奨されているかをシミュレーションして答えてください。"},
                        {"role": "user", "content": f"質問：「{keyword}」について教えて。\n\nこの回答の中に、「{brand_name}」という名前は好意的に登場しますか？\n登場する場合は「推奨されています」と理由を、登場しない場合は「推奨されていません」と対策を簡潔に答えて。"}
                    ],
                    max_tokens=500
                )
                
                result = response.choices[0].message.content
                
                # --- 結果表示 ---
                st.success("分析完了！")
                st.markdown("### 🔍 分析結果")
                st.write(result)
                
            except Exception as e:
                st.error(f"エラーが発生しました: {e}")