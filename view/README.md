# AWS Word Explainer View

TypeScript・Reactで作成した画面です。Viteで開発し、S3に置く静的ファイルをビルドします。

## ローカルで起動

Node.js 22.12以降を使用します。初回は `view/` で依存パッケージをインストールしてください。

```bash
cd view
npm ci
```

リポジトリのルートでAPIを起動します。DB、テーブル、カテゴリ、AIプロバイダーとCognitoの設定はAPI側の手順で用意してください。

```bash
make run
```

別のターミナルで、リポジトリのルートから画面を起動します。

```bash
make view
```

`http://localhost:5173/` を開きます。CognitoのコールバックURLに登録したURLと一致させてください。開発時の `/api` リクエストはViteが `http://127.0.0.1:8080` に転送します。停止は各ターミナルで `Ctrl+C` を押します。

## Cognito設定

`view/.env.example` を参考に `view/.env.local` を作り、Cognitoのリージョン、ユーザープールID、アプリクライアントID、Cognitoドメインを設定します。実行中のViteへ変更を反映するときは再起動します。ユーザープールは認可コードフロー、PKCE、公開SPAクライアントを使用し、コールバックURLとサインアウトURLに `http://localhost:5173/` および公開画面のルートURLを登録してください。

API側の `.env` にも同じリージョン、ユーザープールID、クライアントIDを設定します。サインイン・サインアウトとトークン検証の動作確認には実際のCognitoユーザーが必要です。

## 画面の操作

- 「説明をつくる」で単語を入力し、説明候補を生成します。この時点ではDBに保存しません。
- 候補を確認して「この内容で登録する」を押すと保存します。「キャンセル」では保存しません。
- 「単語ライブラリ」でカテゴリごとの登録内容を表示します。
- 一覧から1件を選び、「この単語を削除」を押します。確認画面の「削除する」で論理削除します。

同じ単語が複数あっても、選択したレコードのIDで削除します。ページ切り替えはURLのハッシュ（`#/`、`#/entries`）を使用するため、S3で個別パスのフォールバック設定は不要です。

## S3用のビルド

`view/.env.production` にCognito設定を用意します。画面とAPIを同じCloudFrontドメインで配信する場合、API接続先は空欄とし、`/api` をALBへ転送します。

```env
VITE_API_BASE_URL=
```

リポジトリのルートで次を実行します。

```bash
make view-build
```

`view/dist/` 内のファイルをS3の配信元へアップロードします。`view/` のソースや `node_modules/` をアップロードする必要はありません。API接続先はビルド時に埋め込まれるため、変更後は再ビルドしてください。

Viteでは `.env.local` が `.env.production` より優先されます。環境ごとにCognitoを使い分ける場合は、ビルド前に `.env.local` の値と実際のビルド設定を確認してください。公開画面のURLと認証情報はブラウザに埋め込まれます。

APIサーバーの `.env` では、画面の配信元をCORS許可します。末尾のスラッシュやURLパスを含めずに指定します。

```env
CORS_ALLOWED_ORIGINS=https://words.example.com
```

複数の配信元はカンマ区切りで指定できます。設定後はAPIサーバーを再起動します。`VITE_` で始まる環境変数はブラウザに公開されるため、Gemini APIキーなどの秘密情報はAPIサーバー側の `.env` だけに置いてください。

## 確認

```bash
cd view
npm test
npm run build
```

テスト内のAPI通信はモックします。実DBやGemini APIを呼び出しません。
