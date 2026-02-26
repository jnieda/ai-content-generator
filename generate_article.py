"""
Cron Job 2: 記事生成
毎朝7:00に実行、30分で終了
記事生成完了後、タイトルを履歴に追記
"""

import anthropic
import json
import os
from datetime import datetime
import requests
from discord_notifier import DiscordNotifier


class GistManager:
    """GitHub Gist操作"""

    def __init__(self, token):
        self.token = token
        self.api_base = "https://api.github.com"
        self.headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }

    def get_gist_by_description(self, description_prefix):
        url = f"{self.api_base}/gists"
        response = requests.get(url, headers=self.headers)
        if response.status_code == 200:
            for gist in response.json():
                if gist.get("description", "").startswith(description_prefix):
                    return gist["id"]
        return None

    def get_gist_content(self, gist_id, filename):
        url = f"{self.api_base}/gists/{gist_id}"
        response = requests.get(url, headers=self.headers)
        if response.status_code == 200:
            files = response.json().get("files", {})
            if filename in files:
                return json.loads(files[filename]["content"])
        return None

    def update_file_in_gist(self, gist_id, filename, content):
        """Gist内の特定ファイルだけを更新"""
        data = {
            "files": {filename: {"content": content}}
        }
        url = f"{self.api_base}/gists/{gist_id}"
        response = requests.patch(url, headers=self.headers, json=data)
        return response.status_code in [200, 201]

    def add_to_history(self, gist_id, title, category):
        """記事タイトルを履歴に追記"""
        existing = self.get_gist_content(gist_id, "article_history.json")
        articles = existing.get("articles", []) if existing else []

        articles.append({
            "date": datetime.now().strftime('%Y-%m-%d'),
            "title": title,
            "category": category
        })

        new_content = json.dumps({"articles": articles}, ensure_ascii=False, indent=2)
        success = self.update_file_in_gist(gist_id, "article_history.json", new_content)

        if success:
            print(f"✅ 履歴に追記しました（累計 {len(articles)} 記事）")
        else:
            print("❌ 履歴の追記に失敗しました")
        return success


class ArticleGenerator:
    """記事生成"""

    def __init__(self, api_key):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.today = datetime.now()

    def generate_article(self, idea):
        strategy_path = os.path.join(os.path.dirname(__file__), 'content_strategy.md')
        with open(strategy_path, 'r', encoding='utf-8') as f:
            strategy = f.read()

        prompt = f"""
あなたはAI初心者向けNote記事の執筆者です。

以下のアイデアに基づいて、完全な記事を執筆してください。

<article_idea>
タイトル: {idea['title']}
カテゴリ: {idea['category']}
主なポイント: {', '.join(idea['key_points'])}
目標文字数: {idea['target_word_count']}文字
</article_idea>

<content_strategy>
{strategy}
</content_strategy>

重要な指示：
- 本文は{idea['target_word_count']}文字前後
- 見出しは ## と ### を使用
- 具体例を必ず含める
- 初心者にも分かりやすく
- 専門用語は必ず解説
- 最後にCTAを含める

**以下のXML形式で出力してください：**

<article>
<title>記事タイトル（SEO最適化済み）</title>
<body>
記事本文（Markdown形式、見出し・箇条書き含む）
複数行でOK
</body>
<hashtags>
<tag>タグ1</tag>
<tag>タグ2</tag>
<tag>タグ3</tag>
<tag>タグ4</tag>
<tag>タグ5</tag>
</hashtags>
<summary>記事の要約（150文字以内）</summary>
<estimated_read_time>5分</estimated_read_time>
</article>
"""

        print("🤖 Claudeに記事執筆を依頼中...")

        # リトライロジック（最大3回）
        max_retries = 3
        retry_delay = 5  # 秒
        
        for attempt in range(max_retries):
            try:
                message = self.client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=16000,
                    messages=[{"role": "user", "content": prompt}]
                )
                break  # 成功したらループを抜ける
                
            except Exception as e:
                error_type = type(e).__name__
                print(f"⚠️  試行 {attempt + 1}/{max_retries} 失敗: {error_type}")
                
                if attempt < max_retries - 1:
                    import time
                    wait_time = retry_delay * (2 ** attempt)  # 指数バックオフ: 5秒 → 10秒 → 20秒
                    print(f"   {wait_time}秒待機後に再試行...")
                    time.sleep(wait_time)
                else:
                    print(f"❌ {max_retries}回試行しましたが失敗しました")
                    raise

        response_text = message.content[0].text
        
        print(f"📝 応答の長さ: {len(response_text)} 文字")
        
        # ハイブリッド抽出：body は正規表現、他はXMLパース
        import re
        import xml.etree.ElementTree as ET
        
        try:
            # <article>...</article> を抽出
            if "<article>" in response_text and "</article>" in response_text:
                start = response_text.index("<article>")
                end = response_text.index("</article>") + len("</article>")
                xml_text = response_text[start:end]
            else:
                xml_text = response_text
            
            # body部分だけ正規表現で抽出（特殊文字に強い）
            body_match = re.search(r'<body>\s*(.*?)\s*</body>', xml_text, re.DOTALL)
            if not body_match:
                raise ValueError("body タグが見つかりません")
            body_content = body_match.group(1).strip()
            
            # bodyを一時的に削除してXMLパース
            xml_without_body = re.sub(r'<body>.*?</body>', '<body>PLACEHOLDER</body>', xml_text, flags=re.DOTALL)
            root = ET.fromstring(xml_without_body)
            
            # データを抽出
            article = {
                "title": root.find("title").text.strip() if root.find("title") is not None and root.find("title").text else "",
                "body": body_content,  # 正規表現で抽出した本文を使用
                "hashtags": [tag.text.strip() for tag in root.findall(".//hashtags/tag") if tag.text],
                "summary": root.find("summary").text.strip() if root.find("summary") is not None and root.find("summary").text else "",
                "estimated_read_time": root.find("estimated_read_time").text.strip() if root.find("estimated_read_time") is not None and root.find("estimated_read_time").text else "5分"
            }
            
            print(f"✅ XMLパース成功")
            return article
            
        except (ET.ParseError, ValueError) as e:
            print(f"❌ XMLパースエラー: {e}")
            print(f"❌ 応答の最初: {response_text[:500]}")
            
            # デバッグ用ファイル保存
            debug_file = f"debug_response_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            with open(debug_file, 'w', encoding='utf-8') as f:
                f.write(response_text)
            print(f"❌ 詳細は {debug_file} を確認してください")
            raise

    def save_article(self, article, filename):
        content = f"""# {article['title']}

{article['body']}

---

**ハッシュタグ**: {' '.join(['#' + tag for tag in article['hashtags']])}

**読了時間**: {article['estimated_read_time']}

**要約**: {article['summary']}
"""
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)

        meta_filename = filename.replace('.md', '_meta.json')
        with open(meta_filename, 'w', encoding='utf-8') as f:
            json.dump(article, f, ensure_ascii=False, indent=2)


def main():
    print("=" * 60)
    print("Cron Job 2: 記事生成")
    print(f"日時: {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}")
    print("=" * 60)

    anthropic_key = os.getenv('ANTHROPIC_API_KEY')
    github_token = os.getenv('GITHUB_TOKEN')

    if not anthropic_key or not github_token:
        print("❌ 環境変数が設定されていません")
        return

    gist_manager = GistManager(github_token)
    gist_id = gist_manager.get_gist_by_description("AI Article Selection")

    if not gist_id:
        print("❌ Gistが見つかりません（先にCron Job 1を実行してください）")
        return

    # 1. Gistから選択を読み取り
    selection_data = gist_manager.get_gist_content(gist_id, "article_selection.json")

    if not selection_data:
        print("❌ Gistの読み取りに失敗しました")
        return

    selection = selection_data.get("selection")

    if selection is None:
        print("⚠️  まだ記事が選択されていません")
        notifier = DiscordNotifier()
        notifier.send_simple_message(
            "⚠️ 記事が選択されていません",
            "Gistで選択番号（1、2、3）を入力してください。\n次回の実行時に記事を生成します。",
            color=16776960
        )
        return

    # 2. 選択されたアイデアを取得
    ideas = selection_data["ideas"]
    selected_idea = ideas[int(selection) - 1]
    print(f"✅ 選択された記事: {selected_idea['title']}")

    # 3. 記事生成
    generator = ArticleGenerator(anthropic_key)
    
    try:
        article = generator.generate_article(selected_idea)
    except Exception as e:
        print(f"❌ 記事生成に失敗しました: {e}")
        
        # Discord通知
        notifier = DiscordNotifier()
        notifier.send_simple_message(
            "❌ 記事生成に失敗",
            f"選択された記事: {selected_idea['title']}\n\n"
            f"APIエラーが発生しました。\n"
            f"エラー: {type(e).__name__}\n"
            f"詳細: {str(e)[:200]}\n\n"
            f"次回の実行時に再試行されます。",
            color=15158332  # 赤色
        )
        return

    print(f"\n✅ 記事生成完了！")
    print(f"   タイトル: {article['title']}")
    print(f"   文字数: 約{len(article['body'])}文字")

    # 4. 記事を保存
    filename = f"{datetime.now().strftime('%Y%m%d')}_article.md"
    generator.save_article(article, filename)
    print(f"💾 記事を保存しました: {filename}")

    # 5. 履歴に追記（重複防止のため）
    print("\n📚 過去記事履歴に追記中...")
    gist_manager.add_to_history(gist_id, article['title'], selected_idea['category'])

    # 6. Discordにファイル送信
    notifier = DiscordNotifier()
    print("\n📤 記事ファイルをDiscordに送信中...")
    notifier.send_article_file(article, filename, filename)

    print("\n" + "=" * 60)
    print("✅ すべての処理が完了しました！")
    print("📱 Discordで記事ファイルをダウンロードできます")
    print("=" * 60)


if __name__ == "__main__":
    main()
