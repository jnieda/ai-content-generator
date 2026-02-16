"""
Google Drive管理クラス
記事をGoogle Driveに自動保存
"""

import os
import json
import re
from datetime import datetime
from typing import Optional, Dict
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2 import service_account


class GoogleDriveManager:
    def __init__(self, credentials_json: Optional[str] = None):
        """
        Google Drive管理クラスの初期化
        
        Args:
            credentials_json: サービスアカウントのJSON文字列（環境変数から取得）
        """
        self.credentials_json = credentials_json or os.getenv('GOOGLE_CREDENTIALS')
        self.theme = os.getenv('CONTENT_THEME', 'AI初心者向け')
        self.service = None
        
        if self.credentials_json:
            self._initialize_service()
        else:
            print("⚠️ 警告: GOOGLE_CREDENTIALSが設定されていません")
    
    def _initialize_service(self):
        """Google Drive APIサービスを初期化"""
        try:
            # JSON文字列を辞書に変換
            credentials_dict = json.loads(self.credentials_json)
            
            # 認証情報を作成
            credentials = service_account.Credentials.from_service_account_info(
                credentials_dict,
                scopes=['https://www.googleapis.com/auth/drive.file']
            )
            
            # Drive APIサービスを構築
            self.service = build('drive', 'v3', credentials=credentials)
            print("✅ Google Drive APIに接続しました")
            
        except json.JSONDecodeError:
            print("❌ GOOGLE_CREDENTIALSのJSON形式が不正です")
        except Exception as e:
            print(f"❌ Google Drive API初期化エラー: {e}")
    
    def _sanitize_filename(self, filename: str) -> str:
        """ファイル名から使用できない文字を削除"""
        # Windowsで使えない文字を削除
        invalid_chars = r'[<>:"/\\|?*]'
        sanitized = re.sub(invalid_chars, '', filename)
        # 長すぎる場合は切り詰め（拡張子除く）
        if len(sanitized) > 100:
            sanitized = sanitized[:100]
        return sanitized
    
    def _find_or_create_folder(self, folder_name: str, parent_id: Optional[str] = None) -> Optional[str]:
        """フォルダを検索、なければ作成"""
        if not self.service:
            return None
        
        try:
            # フォルダを検索
            query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder'"
            if parent_id:
                query += f" and '{parent_id}' in parents"
            else:
                query += " and 'root' in parents"
            
            query += " and trashed=false"
            
            results = self.service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name)'
            ).execute()
            
            files = results.get('files', [])
            
            if files:
                # 既存のフォルダを返す
                print(f"📁 フォルダ '{folder_name}' を見つけました")
                return files[0]['id']
            else:
                # フォルダを作成
                folder_metadata = {
                    'name': folder_name,
                    'mimeType': 'application/vnd.google-apps.folder'
                }
                if parent_id:
                    folder_metadata['parents'] = [parent_id]
                
                folder = self.service.files().create(
                    body=folder_metadata,
                    fields='id'
                ).execute()
                
                print(f"✅ フォルダ '{folder_name}' を作成しました")
                return folder.get('id')
                
        except Exception as e:
            print(f"❌ フォルダ操作エラー: {e}")
            return None
    
    def _get_folder_structure(self) -> Optional[str]:
        """
        記事保存用のフォルダ構造を取得・作成
        AI記事自動生成/{テーマ名}/{YYYY年M月}/
        """
        if not self.service:
            return None
        
        try:
            # 現在の年月
            now = datetime.now()
            year_month = now.strftime('%Y年%-m月')  # 例: 2026年2月
            
            # ルートフォルダ: AI記事自動生成
            root_folder_id = self._find_or_create_folder('AI記事自動生成')
            if not root_folder_id:
                return None
            
            # テーマフォルダ: AI初心者向け
            theme_folder_id = self._find_or_create_folder(self.theme, root_folder_id)
            if not theme_folder_id:
                return None
            
            # 月フォルダ: 2026年2月
            month_folder_id = self._find_or_create_folder(year_month, theme_folder_id)
            
            return month_folder_id
            
        except Exception as e:
            print(f"❌ フォルダ構造作成エラー: {e}")
            return None
    
    def upload_article(self, filepath: str, article_title: str) -> Optional[str]:
        """
        記事ファイルをGoogle Driveにアップロード
        
        Args:
            filepath: アップロードするファイルのパス
            article_title: 記事のタイトル
            
        Returns:
            アップロードしたファイルのWebビューリンク（またはNone）
        """
        if not self.service:
            print("⚠️ Google Driveサービスが初期化されていません")
            return None
        
        try:
            # フォルダ構造を取得
            folder_id = self._get_folder_structure()
            if not folder_id:
                print("❌ フォルダの作成に失敗しました")
                return None
            
            # ファイル名を生成: YYYYMMDD_タイトル.md
            now = datetime.now()
            date_str = now.strftime('%Y%m%d')
            sanitized_title = self._sanitize_filename(article_title)
            filename = f"{date_str}_{sanitized_title}.md"
            
            # ファイルメタデータ
            file_metadata = {
                'name': filename,
                'parents': [folder_id]
            }
            
            # ファイルをアップロード
            media = MediaFileUpload(
                filepath,
                mimetype='text/markdown',
                resumable=True
            )
            
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, webViewLink, name'
            ).execute()
            
            file_id = file.get('id')
            web_link = file.get('webViewLink')
            file_name = file.get('name')
            
            print(f"✅ Google Driveにアップロードしました: {file_name}")
            print(f"   リンク: {web_link}")
            
            # 誰でも閲覧可能に設定（オプション）
            # self._make_public(file_id)
            
            return web_link
            
        except Exception as e:
            print(f"❌ アップロードエラー: {e}")
            return None
    
    def _make_public(self, file_id: str):
        """ファイルを誰でも閲覧可能にする（オプション）"""
        try:
            permission = {
                'type': 'anyone',
                'role': 'reader'
            }
            self.service.permissions().create(
                fileId=file_id,
                body=permission
            ).execute()
            print("✅ ファイルを公開設定にしました")
        except Exception as e:
            print(f"⚠️ 公開設定エラー: {e}")


# テスト用
if __name__ == "__main__":
    # 環境変数から認証情報を取得してテスト
    manager = GoogleDriveManager()
    
    if manager.service:
        print("\n=== Google Drive接続テスト ===")
        print(f"テーマ: {manager.theme}")
        
        # テストファイルを作成
        test_file = "test_article.md"
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write("# テスト記事\n\nこれはテストです。")
        
        # アップロードテスト
        link = manager.upload_article(test_file, "テスト記事")
        
        if link:
            print(f"\n✅ テスト成功！")
            print(f"リンク: {link}")
        else:
            print("\n❌ テスト失敗")
        
        # テストファイルを削除
        if os.path.exists(test_file):
            os.remove(test_file)
    else:
        print("❌ Google Driveサービスの初期化に失敗しました")
