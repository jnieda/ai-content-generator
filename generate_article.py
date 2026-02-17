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

以下のJSON形式で出力してください：
{{
  "title": "記事タイトル（SEO最適化済み）",
  "body": "記事本文（Markdown形式、見出し・箇条書き含む）",
  "hashtags": ["タグ1", "タグ2", "タグ3", "タグ4", "タグ5"],
  "summary": "記事の要約（150文字以内）",
  "estimated_read_time": "5分"
}}

重要な指示：
- 本文は{idea['target_word_count']}文字前後
- 見出しは ## と ### を使用
- 具体例を必ず含める
- 初心者にも分かりやすく
- 専門用語は必ず解説
- 最後にCTAを含める
"""

        print("🤖 Claudeに記事執筆を依頼中...")

        message = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8000,
            messages=[{"role": "user", "content": prompt}]
        )

        response_text = message.content[0].text
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()

        return json.loads(response_text)

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
    article = generator.generate_article(selected_idea)

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
