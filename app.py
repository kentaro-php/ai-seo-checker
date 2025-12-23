import streamlit as st
import pandas as pd
import datetime
import os
from openai import OpenAI

# --- 1. Streamlitの基本設定 ---
# initial_sidebar_state="collapsed" にすることで、万が一表示されても閉じた状態にします
st.set_page_config(page_title="LLOM Checker", layout="wide", initial_sidebar_state="collapsed")

# --- 2. URLパラメータによるモード判定 ---
# 最新のStreamlitでは st.query_params を使用
query_params = st.query_params
# ?view=user があるかどうかでフラグを立てる
is_user_view = query_params.get("view") == "user"

# ユーザーモードの場合、CSSでハンバーガーメニューなども完全に隠す
if is_user_view:
    st.markdown(
        """
        <style>
            [data-testid="stSidebar"] {display: none;}
            [data-testid="collapsedControl"] {display: none;}
            section[data-testid="stSidebar"] {display: none;}
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
        </style>
        """,
        unsafe_allow_html=True
    )

# --- 設定 ---
LOG_FILE = "search_log.csv"
ADMIN_PASSWORD = "admin" # 本番環境ではこれも secrets.toml で管理推奨
LOG_COLUMNS = ["日時", "検索キーワード", "対象サービス", "推奨結果", "AI回答(抜粋)"]

# --- 関数: ログ保存 (簡易排他制御付き) ---
def save_log(keyword, company_name, is_recommended, full_answer):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # 改行やカンマを除去してCSV崩れを防ぐ
    clean_answer = full_answer[:100].replace("\n", " ").replace(",", "、").replace('"', '') + "..."
    
    new_data = pd.DataFrame([[
        timestamp, keyword, company_name, "〇" if is_recommended else "×", clean_answer
    ]], columns=LOG_COLUMNS)
    
    try:
        # ファイルが存在しない場合は新規作成
        if not os.path.exists(LOG_FILE) or os.stat(LOG_FILE).st_size == 0:
            new_data.to_csv(LOG_FILE, index=False, encoding="utf-8-sig")
        else:
            # 追記モード
            new_data.to_csv(LOG_FILE, mode='a', header=False, index=False, encoding="utf-8-sig")
    except PermissionError:
        st.error("ログファイルの書き込みに失敗しました。他のプロセスが開いている可能性があります。")
    except Exception as e:
        st.error(f"ログ保存エラー: {e}")

# --- 関数: ログ読み込み ---
def load_log():
    if not os.path.exists(LOG_FILE) or os.stat(LOG_FILE).st_size == 0:
        return pd.DataFrame(columns=LOG_COLUMNS)
    try:
        df = pd.read_csv(LOG_FILE)
        # 必要なカラムがあるかチェック
        if not set(["日時", "検索キーワード"]).issubset(df.columns):
            return pd.DataFrame(columns=LOG_COLUMNS) # 形式が違う場合は空を返す
        return df
    except Exception:
        return None

# --- 関数: LLOMチェック実行 ---
def check_llom(api_key, keyword, company_name):
    if not api_key:
        return False, False, "APIキーが設定されていません。"
        
    try:
        client = OpenAI(api_key=api_key)
        
        # プロンプトエンジニアリング: 明確なフォーマットを指定
        prompt = f"""
        あなたはSEOとローカル検索の専門家です。
        以下のユーザーの検索意図に基づき、具体的におすすめのサービス・店舗・商品を厳選して5つリストアップしてください。
        
        検索キーワード: 「{keyword}」
        
        条件:
        1. ユーザーが本当に満足できる質の高いものを提案すること。
        2. 実在する名称であること。
        3. 各推奨項目の特徴を簡潔に説明すること。
        """
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
            temperature=0.7
        )
        answer = response.choices[0].message.content
        
        # 判定ロジック: 自社名が含まれているか（大文字小文字無視）
        is_recommended = company_name.lower() in answer.lower()
        
        return True, is_recommended, answer
    except Exception as e:
        return False, False, str(e)

# --- メインロジック ---

# SecretsからAPIキーを取得 (ユーザー/管理者共通)
# .streamlit/secrets.toml がない場合のフォールバック用に空文字を設定
api_key = st.secrets.get("OPENAI_API_KEY", "")

# 画面モードの変数を初期化
current_mode = "user" # デフォルト

if is_user_view:
    # --- A. ユーザー埋め込みモード ---
    # サイドバーのコードは一切実行しない
    current_mode = "user"
    
else:
    # --- B. 管理者・通常アクセスモード ---
    # ここでのみ st.sidebar を使用する
    st.sidebar.title("🛠 設定・メニュー")
    
    # APIキーの上書き設定（Secretsがない場合用）
    input_api_key = st.sidebar.text_input("OpenAI API Key", value=api_key, type="password", help="secrets.toml未設定時に使用")
    if input_api_key:
        api_key = input_api_key
        
    st.sidebar.markdown("---")
    
    # モード切替
    mode_selection = st.sidebar.radio("表示モード", ["🔍 ユーザー検索画面", "📊 管理者ダッシュボード"])
    
    if mode_selection == "🔍 ユーザー検索画面":
        current_mode = "user"
    else:
        current_mode = "admin"

# --- 画面描画 ---

if current_mode == "user":
    # === 1. ユーザー検索画面 ===
    # 埋め込み時の見栄えを考慮し、タイトルは控えめ、またはHTML側で制御
    if not is_user_view:
        st.title("🤖 AI検索・推奨チェッカー")
    
    # シンプルな入力フォーム
    with st.container():
        col1, col2 = st.columns(2)
        with col1:
            keyword = st.text_input("狙っているキーワード", placeholder="例：渋谷 イタリアン デート")
        with col2:
            company = st.text_input("確認したい自社名", placeholder="例：渋谷トラットリア")
            
        check_btn = st.button("チェック開始", type="primary", use_container_width=True)
    
    if check_btn:
        if not keyword or not company:
            st.warning("キーワードと自社名の両方を入力してください。")
        else:
            with st.spinner("AIが検索結果を分析中..."):
                success, is_rec, answer = check_llom(api_key, keyword, company)
                
                if success:
                    # ログ保存
                    save_log(keyword, company, is_rec, answer)
                    
                    st.divider()
                    if is_rec:
                        st.success(f"🎉 **おめでとうございます！「{company}」は推奨されています！**")
                        st.balloons()
                    else:
                        st.error(f"⚠️ **残念ながら「{company}」は推奨リストに入っていません。**")
                        st.info("💡 ヒント: SEO対策やMEO対策を見直すチャンスです。")
                    
                    with st.expander("AIによる推奨リスト詳細", expanded=True):
                        st.markdown(answer)
                else:
                    st.error(f"エラーが発生しました: {answer}")

elif current_mode == "admin":
    # === 2. 管理者ダッシュボード ===
    st.title("📊 管理者ダッシュボード")
    st.markdown("ここではユーザーの検索履歴とAIの推奨状況を確認できます。")
    
    # パスワード認証
    password = st.sidebar.text_input("管理者パスワード", type="password")
    
    if password == ADMIN_PASSWORD:
        st.success("認証成功: 管理者モード")
        
        # データの読み込み
        df = load_log()
        
        if df is not None and not df.empty:
            # メトリクス表示
            m1, m2, m3 = st.columns(3)
            m1.metric("総検索回数", len(df))
            recommended_count = len(df[df["推奨結果"] == "〇"])
            m2.metric("推奨成功数", recommended_count)
            m3.metric("推奨率", f"{recommended_count / len(df) * 100:.1f}%")
            
            st.subheader("📋 最新の検索ログ")
            # データフレームを表示（最新順）
            st.dataframe(
                df.sort_values("日時", ascending=False),
                use_container_width=True,
                hide_index=True
            )
            
            # ダウンロードボタン
            csv = df.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                "📥 CSVログをダウンロード",
                data=csv,
                file_name=f'llom_logs_{datetime.date.today()}.csv',
                mime='text/csv'
            )
            
            # データ管理
            with st.expander("⚠️ 危険地帯: データ管理"):
                st.warning("データを削除すると元に戻せません。")
                if st.button("ログを全て削除する", type="primary"):
                    if os.path.exists(LOG_FILE):
                        os.remove(LOG_FILE)
                        st.success("ログを削除しました。")
                        st.rerun()
        else:
            st.info("まだ検索ログがありません。ユーザー画面で検索を試してください。")
            
    elif password:
        st.error("パスワードが違います。")
    else:
        st.warning("サイドバーで管理者パスワードを入力してください。")