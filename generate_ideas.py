"""
Cron Job 1: 記事アイデア生成
毎朝5:00に実行、2分で終了
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
    
    def create_or_update_gist(self, filename, content, description, gist_id=None):
        """Gistを作成または更新"""
        
        data = {
            "description": description,
            "public": False,  # プライベートGist
            "files": {
                filename: {
                    "content": content
                }
            }
        }
        
        if gist_id:
            # 既存Gistを更新
            url = f"{self.api_base}/gists/{gist_id}"
            response = requests.patch(url, headers=self.headers, json=data)
        else:
            # 新規Gist作成
            url = f"{self.api_base}/gists"
            response = requests.post(url, headers=self.headers, json=data)
        
        if response.status_code in [200, 201]:
            return response.json()
        else:
            print(f"❌ Gist操作失敗: {response.status_code}")
            print(f"   レスポンス: {response.text}")
            return None
    
    def get_latest_gist_id(self):
        """最新のGist IDを取得（AI Article用）"""
        url = f"{self.api_base}/gists"
        response = requests.get(url, headers=self.headers)
        
        if response.status_code == 200:
            gists = response.json()
            # "AI Article Selection"で始まるGistを探す
            for gist in gists:
                if gist.get("description", "").startswith("AI Article Selection"):
                    return gist["id"]
        return None


class IdeaGenerator:
    """記事アイデア生成"""
    
    def __init__(self, api_key):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.today = datetime.now()
    
    def generate_ideas(self):
        """記事アイデアを3つ生成"""
        
        # コンテンツ戦略を読み込み
        strategy_path = os.path.join(os.path.dirname(__file__), 'content_strategy.md')
        with open(strategy_path, 'r', encoding='utf-8') as f:
            strategy = f.read()
        
        prompt = f"""
あなたはAI初心者向けNote記事のコンテンツプランナーです。

今日は{self.today.strftime('%Y年%m月%d日（%a）')}です。

以下のコンテンツ戦略に基づき、今日投稿すべき記事アイデアを3つ提案してください。

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
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        # JSONをパース
        response_text = message.content[0].text
        # ```json ... ``` を除去
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()
        
        data = json.loads(response_text)
        return data["ideas"]


def main():
    """メイン処理"""
    
    print("=" * 60)
    print("Cron Job 1: 記事アイデア生成")
    print(f"日時: {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}")
    print("=" * 60)
    
    # APIキー取得
    anthropic_key = os.getenv('ANTHROPIC_API_KEY')
    github_token = os.getenv('GITHUB_TOKEN')
    
    if not anthropic_key or not github_token:
        print("❌ 環境変数が設定されていません")
        return
    
    # 記事アイデア生成
    generator = IdeaGenerator(anthropic_key)
    ideas = generator.generate_ideas()
    
    print(f"✅ {len(ideas)}件のアイデアを生成しました")
    for i, idea in enumerate(ideas, 1):
        print(f"\n{i}. {idea['title']}")
    
    # Gistに保存
    gist_manager = GistManager(github_token)
    
    # 保存するデータ
    gist_content = {
        "date": datetime.now().strftime('%Y-%m-%d'),
        "ideas": ideas,
        "selection": None  # ユーザーが編集する部分
    }
    
    # 既存のGist IDを取得（あれば更新、なければ新規作成）
    gist_id = gist_manager.get_latest_gist_id()
    
    gist_data = gist_manager.create_or_update_gist(
        filename="article_selection.json",
        content=json.dumps(gist_content, ensure_ascii=False, indent=2),
        description=f"AI Article Selection - {datetime.now().strftime('%Y-%m-%d')}",
        gist_id=gist_id
    )
    
    if not gist_data:
        print("❌ Gist保存に失敗しました")
        return
    
    gist_url = gist_data["html_url"]
    print(f"✅ Gistに保存しました: {gist_url}")
    
    # Discord通知
    notifier = DiscordNotifier()
    
    # 通知内容をカスタマイズ
    date_str = datetime.now().strftime('%Y年%m月%d日（%a）')
    weekday_map = {'Mon': '月', 'Tue': '火', 'Wed': '水', 'Thu': '木', 
                   'Fri': '金', 'Sat': '土', 'Sun': '日'}
    for en, ja in weekday_map.items():
        date_str = date_str.replace(en, ja)
    
    # カスタム通知
    embeds = [
        {
            "title": f"🤖 {date_str}の記事アイデア",
            "description": "今日投稿する記事を選んでください！\n下のリンクをクリックして、選択番号（1、2、3）を入力してください。",
            "color": 3447003,
            "timestamp": datetime.utcnow().isoformat(),
            "fields": [
                {
                    "name": "📝 選択方法",
                    "value": f"1. [このリンクをクリック]({gist_url})\n2. 右上の「Edit」をクリック\n3. `\"selection\": null` を `\"selection\": 1` に変更（1、2、3のいずれか）\n4. 「Update secret gist」をクリック",
                    "inline": False
                }
            ]
        }
    ]
    
    # 各アイデアを追加
    for i, idea in enumerate(ideas, 1):
        embed = {
            "title": f"{i}. {idea['title']}",
            "color": 15844367 if i == 1 else (15105570 if i == 2 else 3066993),
            "fields": [
                {
                    "name": "📁 カテゴリ",
                    "value": idea['category'],
                    "inline": True
                },
                {
                    "name": "📝 目標文字数",
                    "value": f"{idea['target_word_count']}文字",
                    "inline": True
                },
                {
                    "name": "⏱️ 読了時間",
                    "value": idea['estimated_read_time'],
                    "inline": True
                },
                {
                    "name": "💡 今このテーマが重要な理由",
                    "value": idea['why_now'],
                    "inline": False
                },
                {
                    "name": "📌 主なポイント",
                    "value": "\n".join([f"• {point}" for point in idea['key_points']]),
                    "inline": False
                }
            ]
        }
        embeds.append(embed)
    
    notifier.send_message(embeds=embeds)
    
    print("\n✅ Discord通知を送信しました")
    print("=" * 60)
    print("🎯 次は: Gistで選択番号を入力してください")
    print(f"🔗 {gist_url}")
    print("=" * 60)


if __name__ == "__main__":
    main()
