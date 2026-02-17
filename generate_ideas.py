"""
Cron Job 1: 記事アイデア生成
毎朝5:00に実行、2分で終了
重複防止: 過去記事履歴をGistで管理
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
        """descriptionで始まるGistを取得"""
        url = f"{self.api_base}/gists"
        response = requests.get(url, headers=self.headers)
        if response.status_code == 200:
            for gist in response.json():
                if gist.get("description", "").startswith(description_prefix):
                    return gist["id"]
        return None

    def get_gist_content(self, gist_id, filename):
        """Gistの特定ファイルの内容を取得"""
        url = f"{self.api_base}/gists/{gist_id}"
        response = requests.get(url, headers=self.headers)
        if response.status_code == 200:
            files = response.json().get("files", {})
            if filename in files:
                return json.loads(files[filename]["content"])
        return None

    def create_or_update_gist(self, gist_id, files_dict, description):
        """Gistを作成または更新（複数ファイル対応）"""
        data = {
            "description": description,
            "public": False,
            "files": {
                name: {"content": content}
                for name, content in files_dict.items()
            }
        }
        if gist_id:
            url = f"{self.api_base}/gists/{gist_id}"
            response = requests.patch(url, headers=self.headers, json=data)
        else:
            url = f"{self.api_base}/gists"
            response = requests.post(url, headers=self.headers, json=data)

        if response.status_code in [200, 201]:
            return response.json()
        else:
            print(f"❌ Gist操作失敗: {response.status_code} {response.text}")
            return None

    def load_history(self, gist_id):
        """過去記事履歴を読み込む"""
        if not gist_id:
            return []
        data = self.get_gist_content(gist_id, "article_history.json")
        if data:
            return data.get("articles", [])
        return []


class IdeaGenerator:
    """記事アイデア生成（重複防止付き）"""

    def __init__(self, api_key):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.today = datetime.now()

    def generate_ideas(self, past_articles: list):
        """過去記事を考慮して記事アイデアを3つ生成"""

        strategy_path = os.path.join(os.path.dirname(__file__), 'content_strategy.md')
        with open(strategy_path, 'r', encoding='utf-8') as f:
            strategy = f.read()

        if past_articles:
            history_text = "\n".join([
                f"- [{a['date']}] {a['title']} （カテゴリ: {a['category']}）"
                for a in past_articles[-50:]
            ])
            history_section = f"""
<past_articles>
以下の記事はすでに投稿済みです。これらと同じテーマ・内容・タイトルは絶対に提案しないでください。
類似テーマの場合は、切り口や対象読者を変えて差別化してください。

{history_text}
</past_articles>
"""
            print(f"📚 過去記事 {len(past_articles)} 件を参照して重複チェックします")
        else:
            history_section = ""
            print("📚 過去記事履歴なし（初回実行）")

        prompt = f"""
あなたはAI初心者向けNote記事のコンテンツプランナーです。

今日は{self.today.strftime('%Y年%m月%d日（%a）')}です。

以下のコンテンツ戦略に基づき、今日投稿すべき記事アイデアを3つ提案してください。
{history_section}
<content_strategy>
{strategy}
</content_strategy>

各アイデアには以下を含めてください：
1. キャッチーなタイトル（SEO最適化済み）
2. カテゴリ（戦略で定義された5つから選択）
3. 主なポイント（3-5個の箇条書き）
4. 今このテーマが重要な理由
5. 目標文字数
6. 推定読了時間

JSON形式で出力してください：
{{
  "ideas": [
    {{
      "id": 1,
      "title": "...",
      "category": "...",
      "key_points": ["...", "..."],
      "why_now": "...",
      "target_word_count": 2000,
      "estimated_read_time": "5分"
    }},
    ...
  ]
}}
"""

        print("🤖 Claudeに記事アイデアを依頼中...")

        message = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )

        response_text = message.content[0].text
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()

        data = json.loads(response_text)
        return data["ideas"]


def main():
    print("=" * 60)
    print("Cron Job 1: 記事アイデア生成（重複防止付き）")
    print(f"日時: {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}")
    print("=" * 60)

    anthropic_key = os.getenv('ANTHROPIC_API_KEY')
    github_token = os.getenv('GITHUB_TOKEN')

    if not anthropic_key or not github_token:
        print("❌ 環境変数が設定されていません")
        return

    gist_manager = GistManager(github_token)

    # 1. 過去記事履歴を読み込む
    gist_id = gist_manager.get_gist_by_description("AI Article Selection")
    past_articles = gist_manager.load_history(gist_id)

    # 2. 記事アイデア生成（重複回避）
    generator = IdeaGenerator(anthropic_key)
    ideas = generator.generate_ideas(past_articles)

    print(f"\n✅ {len(ideas)}件のアイデアを生成しました")
    for i, idea in enumerate(ideas, 1):
        print(f"  {i}. {idea['title']}")

    # 3. Gistに保存（選択ファイル + 履歴ファイルを同時に保存）
    selection_content = json.dumps({
        "date": datetime.now().strftime('%Y-%m-%d'),
        "ideas": ideas,
        "selection": None
    }, ensure_ascii=False, indent=2)

    history_content = json.dumps({
        "articles": past_articles  # 履歴は変更なしで保持（追記はgenerate_article.pyが行う）
    }, ensure_ascii=False, indent=2)

    gist_result = gist_manager.create_or_update_gist(
        gist_id=gist_id,
        files_dict={
            "article_selection.json": selection_content,
            "article_history.json": history_content,
        },
        description=f"AI Article Selection - {datetime.now().strftime('%Y-%m-%d')}"
    )

    if not gist_result:
        print("❌ Gist保存に失敗しました")
        return

    gist_url = gist_result["html_url"]
    print(f"✅ Gistに保存しました: {gist_url}")

    # 4. Discord通知
    notifier = DiscordNotifier()

    date_str = datetime.now().strftime('%Y年%m月%d日（%a）')
    weekday_map = {'Mon': '月', 'Tue': '火', 'Wed': '水', 'Thu': '木',
                   'Fri': '金', 'Sat': '土', 'Sun': '日'}
    for en, ja in weekday_map.items():
        date_str = date_str.replace(en, ja)

    embeds = [
        {
            "title": f"🤖 {date_str}の記事アイデア",
            "description": (
                f"過去 **{len(past_articles)}記事** との重複を避けて生成しました！\n\n"
                "今日投稿する記事を選んでください。\n"
                "下のリンクをクリックして選択番号（1、2、3）を入力してください。"
            ),
            "color": 3447003,
            "timestamp": datetime.utcnow().isoformat(),
            "fields": [
                {
                    "name": "📝 選択方法",
                    "value": (
                        f"1. [このリンクをクリック]({gist_url})\n"
                        "2. 右上の「Edit」をクリック\n"
                        "3. `\"selection\": null` を `\"selection\": 1` に変更（1、2、3のいずれか）\n"
                        "4. 「Update secret gist」をクリック"
                    ),
                    "inline": False
                }
            ]
        }
    ]

    for i, idea in enumerate(ideas, 1):
        embeds.append({
            "title": f"{i}. {idea['title']}",
            "color": 15844367 if i == 1 else (15105570 if i == 2 else 3066993),
            "fields": [
                {"name": "📁 カテゴリ", "value": idea['category'], "inline": True},
                {"name": "📝 目標文字数", "value": f"{idea['target_word_count']}文字", "inline": True},
                {"name": "⏱️ 読了時間", "value": idea['estimated_read_time'], "inline": True},
                {"name": "💡 今このテーマが重要な理由", "value": idea['why_now'], "inline": False},
                {
                    "name": "📌 主なポイント",
                    "value": "\n".join([f"• {p}" for p in idea['key_points']]),
                    "inline": False
                }
            ]
        })

    notifier.send_message(embeds=embeds)

    print("\n✅ Discord通知を送信しました")
    print(f"🔗 {gist_url}")
    print("=" * 60)


if __name__ == "__main__":
    main()
