"""
AI初心者向けNote記事自動生成システム
毎日午前5時に実行して、記事案の提案→承認→記事生成→通知を行う
Discord通知対応版
"""

import anthropic
import json
from datetime import datetime, timedelta
import os
from typing import List, Dict
import requests
from discord_notifier import DiscordNotifier

class AIContentGenerator:
    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.today = datetime.now()
        
    def search_latest_ai_news(self) -> str:
        """最新のAIニュースを検索"""
        # 実際の実装ではweb_search toolを使用
        # ここではプレースホルダー
        return "最新のAIニュース検索結果"
    
    def generate_article_ideas(self) -> List[Dict[str, str]]:
        """記事アイデアを3つ生成"""
        
        # 戦略ファイルを読み込み
        import os
        strategy_path = os.path.join(os.path.dirname(__file__), 'content_strategy.md')
        with open(strategy_path, 'r', encoding='utf-8') as f:
            strategy = f.read()
        
        prompt = f"""
あなたはAI活用初心者向けのNoteメディアの編集者です。

# コンテンツ戦略
{strategy}

# タスク
今日（{self.today.strftime('%Y年%m月%d日 %A')}）に投稿する記事のアイデアを3つ提案してください。

## 条件
1. 週間スケジュールに沿った内容
2. AI初心者が「今日から使える」実践的な内容
3. 最新のトレンドも考慮（ただし初心者向けに翻訳）
4. タイトルはNote向けに最適化（クリックされやすい）

## 出力形式（JSON）
{{
  "ideas": [
    {{
      "id": 1,
      "title": "記事タイトル",
      "category": "カテゴリ名",
      "target_word_count": 2000,
      "key_points": ["ポイント1", "ポイント2", "ポイント3"],
      "why_now": "今このテーマが重要な理由",
      "estimated_read_time": "5分"
    }}
  ]
}}
"""
        
        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        # JSONを抽出
        content = response.content[0].text
        # ```json ``` を除去
        json_str = content.replace('```json', '').replace('```', '').strip()
        ideas = json.loads(json_str)
        
        return ideas['ideas']
    
    def generate_full_article(self, idea: Dict[str, str]) -> Dict[str, str]:
        """選択されたアイデアから完全な記事を生成"""
        
        import os
        strategy_path = os.path.join(os.path.dirname(__file__), 'content_strategy.md')
        with open(strategy_path, 'r', encoding='utf-8') as f:
            strategy = f.read()
        
        prompt = f"""
あなたはAI活用初心者向けのプロのライターです。

# 記事企画
タイトル: {idea['title']}
カテゴリ: {idea['category']}
目標文字数: {idea['target_word_count']}文字
重要ポイント: {', '.join(idea['key_points'])}

# コンテンツガイドライン
{strategy}

# タスク
上記の企画に基づき、Note向けの完全な記事を執筆してください。

## 記事構成
1. アイキャッチ的な導入（150字程度）
2. 本文（見出しh2を3-5個、各セクション300-500字）
3. まとめ（150字程度）
4. CTA（次のアクション提案）

## 重要な執筆ルール
- AI初心者でも理解できる平易な言葉
- 専門用語には必ず説明を添える
- 具体例・手順を豊富に
- 「私も最初は〜」など共感表現を入れる
- 箇条書きを効果的に使う
- 実際に試せる内容を含める

## 出力形式（JSON）
{{
  "title": "最終的な記事タイトル（SEO最適化済み）",
  "subtitle": "サブタイトル（あれば）",
  "body": "記事本文（マークダウン形式）",
  "hashtags": ["タグ1", "タグ2", "タグ3", "タグ4", "タグ5"],
  "summary": "記事の要約（100字程度）",
  "estimated_read_time": "読了時間の目安"
}}

記事本文はNoteに直接コピペできる形式で、マークダウンで記述してください。
"""
        
        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        content = response.content[0].text
        json_str = content.replace('```json', '').replace('```', '').strip()
        article = json.loads(json_str)
        
        return article
    
    def save_article(self, article: Dict[str, str], filename: str):
        """生成した記事を保存"""
        
        # 記事をマークダウン形式で保存
        output = f"""# {article['title']}

{article.get('subtitle', '')}

{article['body']}

---

**ハッシュタグ**: {' '.join(['#' + tag for tag in article['hashtags']])}

**読了時間**: {article['estimated_read_time']}

**要約**: {article['summary']}
"""
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(output)
        
        # メタデータも保存
        meta_filename = filename.replace('.md', '_meta.json')
        with open(meta_filename, 'w', encoding='utf-8') as f:
            json.dump(article, f, ensure_ascii=False, indent=2)
    
    def send_notification(self, notifier: DiscordNotifier, ideas: List[Dict] = None, 
                         article: Dict = None, notification_type: str = "ideas"):
        """通知を送信（Discord）"""
        
        if notification_type == "ideas" and ideas:
            date_str = self.today.strftime('%Y年%m月%d日（%a）')
            # 曜日を日本語に変換
            weekday_map = {'Mon': '月', 'Tue': '火', 'Wed': '水', 'Thu': '木', 
                          'Fri': '金', 'Sat': '土', 'Sun': '日'}
            for en, ja in weekday_map.items():
                date_str = date_str.replace(en, ja)
            
            notifier.send_article_ideas(ideas, date_str)
            
        elif notification_type == "article_ready" and article:
            filename = f"{self.today.strftime('%Y%m%d')}_article.md"
            notifier.send_article_ready(article, filename)


def main():
    """メイン実行フロー（午前5時に自動実行）"""
    
    # APIキーを環境変数から取得
    api_key = os.getenv('ANTHROPIC_API_KEY', 'your-api-key-here')
    
    generator = AIContentGenerator(api_key)
    notifier = DiscordNotifier()
    
    print("=" * 60)
    print("AI記事自動生成システム起動 (Discord版)")
    print(f"日時: {generator.today.strftime('%Y年%m月%d日 %H:%M:%S')}")
    print("=" * 60)
    
    # ステップ1: 記事アイデア生成
    print("\n📝 記事アイデアを生成中...")
    ideas = generator.generate_article_ideas()
    
    print(f"\n✅ {len(ideas)}件のアイデアを生成しました")
    for i, idea in enumerate(ideas, 1):
        print(f"\n{i}. {idea['title']}")
        print(f"   カテゴリ: {idea['category']}")
        print(f"   理由: {idea['why_now']}")
    
    # ステップ2: Discord通知送信
    print("\n📤 Discordに通知を送信中...")
    generator.send_notification(notifier, ideas=ideas, notification_type="ideas")
    
    # ステップ3: ユーザーの選択を待つ（実際には外部からの入力）
    print("\n⏳ あなたの選択を待っています...")
    print("（実際の運用では、Discord/Webhook経由で選択を受け付けます）")
    
    # デモ用に自動選択（実際の運用では外部入力を待つ）
    selected_id = 0  # 最初のアイデアを選択
    selected_idea = ideas[selected_id]
    
    print(f"\n✅ 選択された記事: {selected_idea['title']}")
    
    # ステップ4: 完全な記事を生成
    print("\n📝 記事を執筆中...")
    article = generator.generate_full_article(selected_idea)
    
    print(f"\n✅ 記事生成完了！")
    print(f"   タイトル: {article['title']}")
    print(f"   文字数: 約{len(article['body'])}文字")
    print(f"   ハッシュタグ: {', '.join(article['hashtags'])}")
    
    # ステップ5: 記事を保存
    filename = f"{generator.today.strftime('%Y%m%d')}_article.md"
    generator.save_article(article, filename)
    print(f"\n💾 記事を保存しました: {filename}")
    
    # ステップ6: 記事ファイルをDiscordに送信
    print("\n📤 記事ファイルをDiscordに送信中...")
    notifier.send_article_file(article, filename, filename)
    
    print("\n" + "=" * 60)
    print("✅ すべての処理が完了しました！")
    print("📱 Discordで記事ファイルをダウンロードできます")
    print("=" * 60)


if __name__ == "__main__":
    main()
