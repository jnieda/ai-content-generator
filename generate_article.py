"""
Cron Job 2: 記事生成
毎朝7:00に実行、30分で終了
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
    
    def get_gist_content(self, gist_id):
        """Gistの内容を取得"""
        url = f"{self.api_base}/gists/{gist_id}"
        response = requests.get(url, headers=self.headers)
        
        if response.status_code == 200:
            gist_data = response.json()
            # article_selection.json の内容を取得
            for filename, file_data in gist_data["files"].items():
                if filename == "article_selection.json":
                    return json.loads(file_data["content"])
        return None
    
    def get_latest_gist_id(self):
        """最新のGist IDを取得"""
        url = f"{self.api_base}/gists"
        response = requests.get(url, headers=self.headers)
        
        if response.status_code == 200:
            gists = response.json()
            for gist in gists:
                if gist.get("description", "").startswith("AI Article Selection"):
                    return gist["id"]
        return None


class ArticleGenerator:
    """記事生成"""
    
    def __init__(self, api_key):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.today = datetime.now()
    
    def generate_article(self, idea):
        """完全な記事を生成"""
        
        # コンテンツ戦略を読み込み
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
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        # JSONをパース
        response_text = message.content[0].text
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()
        
        return json.loads(response_text)
    
    def save_article(self, article, filename):
        """記事をMarkdownファイルとして保存"""
        
        content = f"""# {article['title']}

{article['body']}

---

**ハッシュタグ**: {' '.join(['#' + tag for tag in article['hashtags']])}

**読了時間**: {article['estimated_read_time']}

**要約**: {article['summary']}
"""
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # メタデータも保存
        meta_filename = filename.replace('.md', '_meta.json')
        with open(meta_filename, 'w', encoding='utf-8') as f:
            json.dump(article, f, ensure_ascii=False, indent=2)


def main():
    """メイン処理"""
    
    print("=" * 60)
    print("Cron Job 2: 記事生成")
    print(f"日時: {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}")
    print("=" * 60)
    
    # APIキー取得
    anthropic_key = os.getenv('ANTHROPIC_API_KEY')
    github_token = os.getenv('GITHUB_TOKEN')
    
    if not anthropic_key or not github_token:
        print("❌ 環境変数が設定されていません")
        return
    
    # Gistから選択を読み取り
    gist_manager = GistManager(github_token)
    gist_id = gist_manager.get_latest_gist_id()
    
    if not gist_id:
        print("❌ Gistが見つかりません")
        return
    
    gist_data = gist_manager.get_gist_content(gist_id)
    
    if not gist_data:
        print("❌ Gistの読み取りに失敗しました")
        return
    
    selection = gist_data.get("selection")
    
    if selection is None:
        print("⚠️  まだ記事が選択されていません")
        print("   Gistで選択番号を入力してください")
        
        # Discord通知
        notifier = DiscordNotifier()
        notifier.send_simple_message(
            "⚠️ 記事が選択されていません",
            "Gistで選択番号（1、2、3）を入力してください。\n次回の実行時に記事を生成します。",
            color=16776960  # 黄色
        )
        return
    
    # 選択されたアイデアを取得
    ideas = gist_data["ideas"]
    selected_idea = ideas[selection - 1]
    
    print(f"✅ 選択された記事: {selected_idea['title']}")
    
    # 記事生成
    generator = ArticleGenerator(anthropic_key)
    article = generator.generate_article(selected_idea)
    
    print(f"\n✅ 記事生成完了！")
    print(f"   タイトル: {article['title']}")
    print(f"   文字数: 約{len(article['body'])}文字")
    
    # 記事を保存
    filename = f"{datetime.now().strftime('%Y%m%d')}_article.md"
    generator.save_article(article, filename)
    print(f"💾 記事を保存しました: {filename}")
    
    # Discordに送信
    notifier = DiscordNotifier()
    
    print("\n📤 記事ファイルをDiscordに送信中...")
    notifier.send_article_file(article, filename, filename)
    
    print("\n" + "=" * 60)
    print("✅ すべての処理が完了しました！")
    print("📱 Discordで記事ファイルをダウンロードできます")
    print("=" * 60)


if __name__ == "__main__":
    main()
