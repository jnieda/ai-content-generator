"""
メール送信クラス
記事をメールで送信
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import Optional, Dict
from datetime import datetime


class EmailSender:
    def __init__(self):
        """
        メール送信クラスの初期化
        Gmail SMTPを使用
        """
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587
        self.sender_email = os.getenv('EMAIL_ADDRESS')
        self.sender_password = os.getenv('EMAIL_PASSWORD')
        self.receiver_email = os.getenv('EMAIL_ADDRESS')  # 自分宛に送信
        self.theme = os.getenv('CONTENT_THEME', 'AI初心者向け')
        
        if not self.sender_email or not self.sender_password:
            print("⚠️ 警告: EMAIL_ADDRESS または EMAIL_PASSWORD が設定されていません")
    
    def send_article(self, article: Dict, filepath: str) -> bool:
        """
        記事をメールで送信
        
        Args:
            article: 記事データ（title, body, hashtags, etc.）
            filepath: 記事ファイルのパス
            
        Returns:
            送信成功時True、失敗時False
        """
        if not self.sender_email or not self.sender_password:
            print("❌ メール設定が不完全です")
            return False
        
        try:
            # メールメッセージを作成
            msg = MIMEMultipart()
            msg['From'] = self.sender_email
            msg['To'] = self.receiver_email
            msg['Subject'] = f"📝 新しい記事が完成しました - {article['title']}"
            
            # 現在の日時
            now = datetime.now()
            year_month = now.strftime('%Y年%-m月')
            
            # メール本文（HTML形式）
            html_body = f"""
<html>
<head>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 10px 10px 0 0; text-align: center; }}
        .header h1 {{ margin: 0; font-size: 24px; }}
        .content {{ background: #f8f9fa; padding: 30px; border-radius: 0 0 10px 10px; }}
        .info-box {{ background: white; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #667eea; }}
        .info-item {{ margin: 10px 0; }}
        .info-label {{ font-weight: bold; color: #667eea; }}
        .hashtags {{ margin: 15px 0; }}
        .hashtag {{ display: inline-block; background: #e3f2fd; color: #1976d2; padding: 5px 12px; border-radius: 15px; margin: 3px; font-size: 13px; }}
        .button {{ display: inline-block; background: #667eea; color: white; padding: 12px 30px; border-radius: 5px; text-decoration: none; margin: 20px 0; }}
        .footer {{ text-align: center; color: #666; font-size: 12px; margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd; }}
        .steps {{ background: white; padding: 20px; border-radius: 8px; margin: 20px 0; }}
        .step {{ padding: 10px 0; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>✅ 記事が完成しました！</h1>
        </div>
        <div class="content">
            <div class="info-box">
                <h2 style="margin-top: 0; color: #333;">{article['title']}</h2>
                <div class="info-item">
                    <span class="info-label">📊 文字数:</span> 約{len(article['body'])}文字
                </div>
                <div class="info-item">
                    <span class="info-label">⏱️ 読了時間:</span> {article['estimated_read_time']}
                </div>
                <div class="info-item">
                    <span class="info-label">📁 テーマ:</span> {self.theme} > {year_month}
                </div>
                <div class="hashtags">
                    <span class="info-label">🏷️ ハッシュタグ:</span><br>
                    {''.join([f'<span class="hashtag">#{tag}</span>' for tag in article['hashtags']])}
                </div>
                <div style="margin-top: 15px; padding: 15px; background: #f0f7ff; border-radius: 5px;">
                    <strong>📝 要約:</strong><br>
                    {article['summary']}
                </div>
            </div>
            
            <div class="steps">
                <h3 style="margin-top: 0; color: #667eea;">📋 次のステップ</h3>
                <div class="step">1️⃣ 添付ファイル（.md）をダウンロード</div>
                <div class="step">2️⃣ テキストエディタで開いて確認</div>
                <div class="step">3️⃣ 内容をNoteにコピペ</div>
                <div class="step">4️⃣ 公開ボタンをクリック</div>
                <div style="margin-top: 15px; color: #667eea; font-weight: bold;">⏰ 所要時間: 約3分</div>
            </div>
        </div>
        <div class="footer">
            <p>AI記事自動生成システム</p>
            <p>{now.strftime('%Y年%m月%d日 %H:%M')}</p>
        </div>
    </div>
</body>
</html>
"""
            
            # HTML本文を追加
            msg.attach(MIMEText(html_body, 'html', 'utf-8'))
            
            # ファイルを添付
            with open(filepath, 'rb') as f:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(f.read())
                encoders.encode_base64(part)
                
                filename = os.path.basename(filepath)
                part.add_header(
                    'Content-Disposition',
                    f'attachment; filename= {filename}',
                )
                msg.attach(part)
            
            # SMTPサーバーに接続して送信
            print(f"📧 メールを送信中... ({self.receiver_email})")
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()  # TLS暗号化
                server.login(self.sender_email, self.sender_password)
                server.send_message(msg)
            
            print(f"✅ メールを送信しました: {article['title']}")
            return True
            
        except smtplib.SMTPAuthenticationError:
            print("❌ メール認証エラー: EMAIL_ADDRESS または EMAIL_PASSWORD が正しくありません")
            print("   Gmailの場合、アプリパスワードを使用してください")
            return False
        except Exception as e:
            print(f"❌ メール送信エラー: {e}")
            return False


# テスト用
if __name__ == "__main__":
    sender = EmailSender()
    
    if sender.sender_email and sender.sender_password:
        print("\n=== メール送信テスト ===")
        print(f"送信元: {sender.sender_email}")
        print(f"送信先: {sender.receiver_email}")
        
        # テスト記事
        test_article = {
            "title": "【テスト】ChatGPTで業務効率化",
            "body": "# テスト記事\n\nこれはテストです。" * 100,
            "hashtags": ["AI初心者", "ChatGPT", "テスト"],
            "summary": "これはテスト記事です。",
            "estimated_read_time": "3分"
        }
        
        # テストファイルを作成
        test_file = "test_article.md"
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write(test_article['body'])
        
        # メール送信テスト
        success = sender.send_article(test_article, test_file)
        
        if success:
            print("\n✅ テスト成功！メールボックスを確認してください。")
        else:
            print("\n❌ テスト失敗")
        
        # テストファイルを削除
        if os.path.exists(test_file):
            os.remove(test_file)
    else:
        print("❌ 環境変数が設定されていません")
