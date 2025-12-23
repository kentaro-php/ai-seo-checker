import streamlit as st
import traceback

# --- 診断モード: エラー捕捉用ラッパー ---
try:
    # 1. 基本設定（必ず最初に記述）
    st.set_page_config(page_title="LLOM Checker", layout="centered")

    # 2. ライブラリインポート
    import pandas as pd
    import datetime
    import os
    from openai import OpenAI

    # --- メイン処理 ---

    # ▼▼▼【修正箇所】最強力版：テキスト検索型JS + CSS ▼▼▼
    st.markdown("""
        <style>
            /* 念のためのCSS指定（標準的なクラス用） */
            footer, header, [data-testid="stFooter"], [data-testid="stToolbar"], [data-testid="stHeader"] {
                visibility: hidden !important;
                display: none !important;
                height: 0px !important;
                opacity: 0 !important;
                overflow: hidden !important;
            }
            /* アプリ下部の余白削除 */
            .main .block-container {
                padding-bottom: 0rem !important;
            }
            /* iframe埋め込み時の下部バー対策 */
            .viewerBadge_container__1QSob, .styles_viewerBadge__1yB5_, .viewerFooter_container__2KkK5 {
                display: none !important;
            }
        </style>

        <script>
            // 【最終手段】DOM内のテキストを検索して、該当要素の親を強制的に消す関数
            function killFooter() {
                // 1. "Built with Streamlit" を含む要素を探す
                const allElements = document.querySelectorAll('*');
                allElements.forEach(el => {
                    // テキストノードを持ち、かつ "Built with Streamlit" を含む場合
                    if (el.textContent && el.textContent.includes('Built with Streamlit')) {
                        // その要素自体、もしくは親要素がフッターっぽい場合は消す
                        // （誤爆を防ぐため、position: fixed や bottom: 0 のスタイルを持つ親まで遡る）
                        let target = el;
                        for (let i = 0; i < 5; i++) { // 親を5階層までチェック
                            if (!target) break;
                            const style = window.getComputedStyle(target);
                            // フッター特有のスタイルやタグ名を検知
                            if (
                                target.tagName === 'FOOTER' || 
                                style.position === 'fixed' || 
                                style.bottom === '0px' ||
                                target.getAttribute('data-testid') === 'stFooter' ||
                                target.className.includes('viewerBadge')
                            ) {
                                target.style.display = 'none';
                                target.style.visibility = 'hidden';
                                target.style.setProperty('display', 'none', 'important');
                                break;
                            }
                            target = target.parentElement;
                        }
                    }
                });
                
                // 2. "Fullscreen" ボタンも同様に消す（埋め込みモード用）
                const buttons = document.querySelectorAll('button');
                buttons.forEach(btn => {
                    if (btn.textContent && btn.textContent.includes('Fullscreen')) {
                        btn.style.display = 'none';
                        btn.style.visibility = 'hidden';
                    }
                });

                // 3. 既知のIDも再度念押しで消す
                const footerIds = ['stFooter', 'stToolbar', 'MainMenu'];
                footerIds.forEach(id => {
                    const elem = document.querySelector(`[data-testid="${id}"]`);
                    if (elem) elem.style.display = 'none';
                });
            }

            // 読み込み直後と、DOM変化時（画面描画時）にしつこく実行
            window.addEventListener('load', killFooter);
            
            // MutationObserverでDOMの変化を監視して即座に消す
            const observer = new MutationObserver(killFooter);
            observer.observe(document.body, { childList: true, subtree: true });
            
            // 念のための定期実行（1秒おき）
            setInterval(killFooter, 1000);
        </script>
    """, unsafe_allow_html=True)
    # ▲▲▲ 修正ここまで ▲▲▲

    # URLパラメータ取得
    try:
        query_params = st.query_params
    except Exception:
        query_params = {}

    is_user_view = "view" in query_params and query_params["view"] == "user"

    # ユーザーモード時のサイドバー非表示（CSSではなくロジックで制御する場合の補助）
    if is_user_view:
        st.markdown("""<style>[data-testid="stSidebar"] { display: none !important; }</style>""", unsafe_allow_html=True)

    # 設定値
    LOG_FILE = "search_log.csv"
    ADMIN_PASSWORD = "admin"
    LOG_COLUMNS = ["日時", "検索キーワード", "対象サービス", "推奨結果", "AI回答(抜粋)"]

    # --- 関数定義 ---
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

    # APIキー取得
    def get_secret_key():
        try:
            if hasattr(st, "secrets") and "OPENAI_API_KEY" in st.secrets:
                return st.secrets["OPENAI_API_KEY"]
        except Exception:
            pass
        return ""

    default_key = get_secret_key()
    api_key = ""
    view_mode = "🔍 ユーザー検索画面" 

    # サイドバー構築（管理者モード用）
    st.sidebar.title("🛠 設定・メニュー")
    input_api_key = st.sidebar.text_input("OpenAI API Key", value=default_key, type="password")
    api_key = input_api_key
    st.sidebar.markdown("---")
    view_mode_select = st.sidebar.radio("表示モード", ["🔍 ユーザー検索画面", "📊 管理者ダッシュボード"])

    if is_user_view:
        view_mode = "🔍 ユーザー検索画面"
    else:
        view_mode = view_mode_select

    # --- 画面表示ロジック ---
    if view_mode == "🔍 ユーザー検索画面":
        if not is_user_view:
            st.title("🤖 AI検索・推奨チェッカー")
        else:
            st.write("") # 埋め込み時の上部マージン調整

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