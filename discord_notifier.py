"""
Discord通知システム
記事アイデアの提案と完成通知を送信
"""

import os
import json
import requests
from typing import List, Dict, Optional
from datetime import datetime

class DiscordNotifier:
    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url or os.getenv('DISCORD_WEBHOOK_URL')
        if not self.webhook_url:
            print("⚠️  警告: DISCORD_WEBHOOK_URLが設定されていません")
    
    def send_message(self, content: str = None, embeds: Optional[List[Dict]] = None):
        """Discordにメッセージを送信"""
        if not self.webhook_url:
            print("📧 [通知メッセージ]")
            if content:
                print(content)
            return
        
        payload = {}
        if content:
            payload["content"] = content
        if embeds:
            payload["embeds"] = embeds
        
        try:
            response = requests.post(
                self.webhook_url,
                json=payload,
                headers={'Content-Type': 'application/json'}
            )
            if response.status_code in [200, 204]:
                print("✅ Discord通知を送信しました")
            else:
                print(f"❌ Discord通知の送信に失敗: {response.status_code}")
                print(f"   レスポンス: {response.text}")
        except Exception as e:
            print(f"❌ エラー: {e}")
    
    def send_article_ideas(self, ideas: List[Dict], date: str):
        """記事アイデアの提案通知"""
        
        # Discord Embed形式
        embeds = [
            {
                "title": f"🤖 {date}の記事アイデア",
                "description": "今日投稿する記事を選んでください！\n番号（1、2、3）で返信してください。",
                "color": 3447003,  # 青色
                "timestamp": datetime.utcnow().isoformat(),
                "footer": {
                    "text": "AI記事自動生成システム"
                }
            }
        ]
        
        # 各アイデアを別のEmbedとして追加
        for i, idea in enumerate(ideas, 1):
            embed = {
                "title": f"{i}. {idea['title']}",
                "color": 15844367 if i == 1 else (15105570 if i == 2 else 3066993),  # 異なる色
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
        
        # 最後に選択を促すEmbed
        embeds.append({
            "title": "👉 どの記事を書きますか？",
            "description": "このチャンネルに **1**、**2**、または **3** と返信してください",
            "color": 5763719,  # 緑色
        })
        
        self.send_message(embeds=embeds)
    
    def send_article_ready(self, article: Dict, filename: str):
        """記事完成通知"""
        
        embeds = [
            {
                "title": "✅ 記事が完成しました！",
                "description": f"**{article['title']}**",
                "color": 3066993,  # 緑色
                "timestamp": datetime.utcnow().isoformat(),
                "fields": [
                    {
                        "name": "📊 文字数",
                        "value": f"約{len(article['body'])}文字",
                        "inline": True
                    },
                    {
                        "name": "⏱️ 読了時間",
                        "value": article['estimated_read_time'],
                        "inline": True
                    },
                    {
                        "name": "\u200b",  # 空フィールド（改行用）
                        "value": "\u200b",
                        "inline": False
                    },
                    {
                        "name": "🏷️ ハッシュタグ",
                        "value": " ".join(['#' + tag for tag in article['hashtags']]),
                        "inline": False
                    },
                    {
                        "name": "📝 要約",
                        "value": article['summary'],
                        "inline": False
                    }
                ],
                "footer": {
                    "text": f"ファイル: {filename}"
                }
            },
            {
                "title": "📄 次のステップ",
                "description": (
                    "1️⃣ 記事ファイルをダウンロード\n"
                    "2️⃣ Noteの編集画面を開く\n"
                    "3️⃣ コピー&ペースト\n"
                    "4️⃣ 公開ボタンをクリック\n\n"
                    "⏰ **所要時間: 約3分**"
                ),
                "color": 15844367,  # オレンジ色
            }
        ]
        
        self.send_message(embeds=embeds)
    
    def send_weekly_report(self, stats: Dict):
        """週次レポート通知（日曜12:00）"""
        
        # 人気記事のフォーマット
        top_articles_text = "\n".join([
            f"{i+1}. **{article['title']}** ({article['views']:,} PV)" 
            for i, article in enumerate(stats.get('top_articles', []))
        ])
        
        if not top_articles_text:
            top_articles_text = "データ収集中..."
        
        embeds = [
            {
                "title": "📊 週次レポート",
                "description": "今週のパフォーマンスサマリー",
                "color": 10181046,  # 紫色
                "timestamp": datetime.utcnow().isoformat(),
                "fields": [
                    {
                        "name": "📝 投稿記事数",
                        "value": f"**{stats.get('articles_posted', 0)}本**",
                        "inline": True
                    },
                    {
                        "name": "👁️ 総PV",
                        "value": f"**{stats.get('total_views', 0):,}**",
                        "inline": True
                    },
                    {
                        "name": "👥 新規フォロワー",
                        "value": f"**{stats.get('new_followers', 0)}人**",
                        "inline": True
                    },
                    {
                        "name": "💰 収益",
                        "value": f"**¥{stats.get('revenue', 0):,}**",
                        "inline": True
                    },
                    {
                        "name": "\u200b",
                        "value": "\u200b",
                        "inline": False
                    },
                    {
                        "name": "🏆 人気記事TOP3",
                        "value": top_articles_text,
                        "inline": False
                    }
                ],
                "footer": {
                    "text": "AI記事自動生成システム 週次レポート"
                }
            },
            {
                "title": "💡 来週の提案",
                "description": stats.get('next_week_suggestion', '引き続き頑張りましょう！'),
                "color": 3447003,  # 青色
            }
        ]
        
        self.send_message(embeds=embeds)
    
    def send_simple_message(self, title: str, message: str, color: int = 3447003):
        """シンプルなメッセージ送信"""
        embeds = [
            {
                "title": title,
                "description": message,
                "color": color,
                "timestamp": datetime.utcnow().isoformat()
            }
        ]
        self.send_message(embeds=embeds)


# テスト用
if __name__ == "__main__":
    notifier = DiscordNotifier()
    
    # テスト通知
    test_ideas = [
        {
            "id": 1,
            "title": "ChatGPT無料版と有料版、どっちを選ぶべき？【2025年版】",
            "category": "基礎知識シリーズ",
            "target_word_count": 2000,
            "key_points": [
                "無料版でできること・できないこと",
                "有料版の3つのメリット",
                "あなたに最適なプランの見極め方"
            ],
            "why_now": "2025年に入りChatGPTの機能が大幅アップデート。無料版も強化されたため、改めて比較が必要",
            "estimated_read_time": "5分"
        },
        {
            "id": 2,
            "title": "議事録を3分で作成｜ChatGPTテンプレート【コピペOK】",
            "category": "実践チュートリアル",
            "target_word_count": 2500,
            "key_points": [
                "音声を自動でテキスト化する方法",
                "議事録に最適化されたプロンプト",
                "実際の使用例とビフォー・アフター"
            ],
            "why_now": "リモートワークが定着し、オンライン会議の議事録作成が日常業務に",
            "estimated_read_time": "7分"
        },
        {
            "id": 3,
            "title": "Google Gemini 2.0発表｜普通の人に何が変わる？【3分解説】",
            "category": "最新ニュース解説",
            "target_word_count": 1500,
            "key_points": [
                "Gemini 2.0の3つの新機能",
                "ChatGPTと何が違う？",
                "今日から試せる使い方"
            ],
            "why_now": "Googleが2月に発表したばかりの最新AI。初心者向けの解説がまだ少ない",
            "estimated_read_time": "4分"
        }
    ]
    
    print("\n=== 記事アイデア通知のテスト ===")
    notifier.send_article_ideas(test_ideas, "2025年2月14日（金）")
    
    print("\n=== 記事完成通知のテスト ===")
    test_article = {
        "title": "ChatGPT無料版と有料版、どっちを選ぶべき？【2025年版完全ガイド】",
        "body": "（本文省略）" * 100,
        "hashtags": ["AI初心者", "ChatGPT", "使い方", "比較", "解説"],
        "summary": "ChatGPTの無料版と有料版を徹底比較。あなたに最適なプランの選び方を初心者向けに解説します。",
        "estimated_read_time": "5分"
    }
    notifier.send_article_ready(test_article, "20250214_article.md")
    
    print("\n=== 週次レポート通知のテスト ===")
    test_stats = {
        "articles_posted": 3,
        "total_views": 4250,
        "new_followers": 42,
        "revenue": 3500,
        "top_articles": [
            {"title": "ChatGPT無料版vs有料版", "views": 1820},
            {"title": "議事録3分作成術", "views": 1340},
            {"title": "Gemini 2.0解説", "views": 1090}
        ],
        "next_week_suggestion": "「実践チュートリアル」カテゴリの人気が高いです。来週は業務効率化系の記事を2本投稿しましょう！"
    }
    notifier.send_weekly_report(test_stats)
    
    print("\n=== シンプルメッセージのテスト ===")
    notifier.send_simple_message(
        "✅ システム起動完了",
        "AI記事自動生成システムが正常に起動しました。",
        color=3066993
    )
