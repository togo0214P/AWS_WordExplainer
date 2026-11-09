# AWS Word Explainer API

単語解説APIのローカル開発用スケルトンです。Python 3.10以降とFastAPIを使います。

AWSへ配置する際の全体構成・VPC構成・通信経路は [AWS構成図](doc/aws-architecture.md) を参照してください。

## セットアップと起動

リポジトリのルートでローカル設定ファイルを作り、仮想環境と依存パッケージを準備します。

```bash
cp -n .env.example .env
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
docker compose up -d db
docker compose ps
```

Ubuntuで `ensurepip is not available` と表示された場合は、Pythonのvenvパッケージを追加してから再実行します（例: `sudo apt install python3.12-venv`）。Docker Compose v2も必要です。

APIサーバーは `127.0.0.1:8080`、PostgreSQLは `127.0.0.1:5432` で起動します。APIサーバーはリポジトリのルートで `make run` を実行すると起動します。ログは実行したターミナルに表示され、ソース変更時は自動で再起動します。停止するときはAPIサーバーで `Ctrl+C` を押し、DBは `docker compose stop db` で停止します。`docker compose down` はコンテナを削除しますが、DBデータのボリュームは保持します。

DBコンテナへの接続確認:

```bash
docker compose exec db psql -U word_explainer -d word_explainer
```

## エントリー保存APIの疎通確認

DBコンテナが起動している状態で、リポジトリのルートからスキーマを適用します。

```bash
docker compose exec -T db psql -U word_explainer -d word_explainer \
  -v ON_ERROR_STOP=1 < db/schema.sql
```

初期カテゴリを登録します。既に登録済みの名前は追加されません。

```bash
docker compose exec -T db psql -U word_explainer -d word_explainer \
  -v ON_ERROR_STOP=1 < db/seed.sql
```

登録されたカテゴリとIDを確認します。

```bash
docker compose exec db psql -U word_explainer -d word_explainer \
  -c "SELECT id, name FROM categories ORDER BY id;"
```

保存APIを試すときは、表示されたカテゴリIDを使います。APIサーバーを起動します。

```bash
make run
```

別のターミナルから保存APIを呼びます。`category_id`は、カテゴリ登録時に表示されたIDに置き換えてください。

```bash
curl -i -X POST http://localhost:8080/api/entries \
  -H 'Content-Type: application/json' \
  -d '{"word":"サブネット","category_id":1,"explanation":"ネットワークを分割した領域です。"}'
```

`201 Created`と登録IDを含むJSONが返れば登録成功です。同じcurlをもう一度実行すると、同じ単語を複数件登録できることも確認できます。

psqlで保存内容を確認します。

```bash
docker compose exec db psql -U word_explainer -d word_explainer
```

```sql
SELECT e.id, e.word, c.name AS category, e.explanation
FROM entries AS e
JOIN categories AS c ON c.id = e.category_id
WHERE e.word = 'サブネット'
ORDER BY e.id;
```

確認後はpsqlで `\q` を実行し、APIサーバーは `Ctrl+C` で停止します。

`.env` の `DB_HOST`、`DB_PORT`、`DB_NAME`、`DB_USER`、`DB_PASSWORD` がAPIのDB接続設定です。Composeも同じ設定を使います。Gemini連携では `GEMINI_API_KEY` と `GEMINI_MODEL` を使います。作成したAPIキーはローカルの `.env` に設定し、`.env.example` やGitHub、ソースコードに書かないでください。`.env` はGit管理対象外です。`cp -n` は既存の `.env` を上書きしません。

## ブラウザ画面

TypeScript・React・Viteで作成した画面を `view/` に配置しています。初回に `cd view && npm ci` を実行した後、APIを `make run`、画面を別のターミナルで `make view` で起動します。画面のURLは `http://127.0.0.1:5173` です。

`make view-build` はS3配置用の静的ファイルを `view/dist/` に生成します。API接続先・CORS設定・操作手順は [view/README.md](view/README.md) を参照してください。

## curlで疎通確認

別のターミナルからヘルスチェックを呼び出します。

```bash
curl -i http://localhost:8080/health
```

応答例: `{"status":"ok"}`

登録済みカテゴリは次のAPIで取得できます。カテゴリが0件の場合も `200 OK` と `{"categories": []}` を返すため、案内表示はView側で行います。

```bash
curl -i http://localhost:8080/api/categories
```

エントリーは、単語の部分一致やカテゴリIDで絞り込めます。どちらも指定しない場合は未削除のエントリーを一覧で返します。

```bash
curl -i --get http://localhost:8080/api/entries \
  --data-urlencode 'word=サブネット'

curl -i 'http://localhost:8080/api/entries?category_id=1'
```

エントリーを論理削除するには、対象のIDを指定します。成功時は`204 No Content`が返り、行はDBに残りますが、通常の検索結果には含まれなくなります。

```bash
curl -i -X DELETE http://localhost:8080/api/entries/1
```

削除日時はpsqlで確認できます。

```bash
docker compose exec db psql -U word_explainer -d word_explainer \
  -c "SELECT id, deleted_at, updated_at FROM entries WHERE id = 1;"
```

説明生成APIはGeminiまたはOpenAIを呼び出して説明候補を返します。候補の生成だけでは `entries` に保存されません。

```bash
curl -i -X POST http://localhost:8080/api/explanations/generate \
  -H 'Content-Type: application/json' \
  -d '{"word":"サブネット"}'
```

`200 OK` と、入力単語・カテゴリID・カテゴリ名・説明を含むJSONが返ります。カテゴリIDとカテゴリ名は、現在のDBに登録されているカテゴリに応じて変わります。

プロジェクトルートの `.env` で生成プロバイダーを選びます。未指定の場合はOpenAIです。Geminiを使う場合は明示的に指定します。

```env
EXPLANATION_PROVIDER=gemini
GEMINI_API_KEY=自分のGemini APIキー
GEMINI_MODEL=gemini-3.8-flash
```

OpenAIを使う場合は、Structured Outputsに対応し利用権限のあるモデルを指定します。

```env
EXPLANATION_PROVIDER=openai
OPENAI_API_KEY=自分のOpenAI APIキー
OPENAI_MODEL=利用するモデル名
```

`.env` はサーバー側だけで管理し、キーをGitや画面、ログに含めないでください。自動的なプロバイダー切り替えは行いません。生成された候補のカテゴリID・名前はサーバーが登録済みカテゴリと照合します。外部APIの失敗や不正な応答には `502 Bad Gateway`、キー・モデル未設定や不明なプロバイダーには `503 Service Unavailable` を返します。

OpenAIへの応答待ちは60秒、再試行は0回です。Geminiは60秒で1回試行します。CloudFrontのオリジン応答タイムアウトやALBのアイドルタイムアウトがそれより短い場合、生成が完了する前に画面へ504が返ることがあります。AWSコンソールで各設定を確認し、必要に応じて調整してください。モデルの混雑によるエラーは待機時間の変更だけでは解消しません。

EC2では、変更したコードを反映した後、仮想環境の依存関係と `.env` を更新し、サービスを再起動します。

```bash
cd ~/AWS_WordExplainer
.venv/bin/pip install -r requirements.txt
# .env に利用するプロバイダーの設定を追加する
sudo systemctl restart word-explainer-api
sudo journalctl -u word-explainer-api -f
```

別のEC2ターミナルで上記のcurlを実行し、その後CloudFrontの画面からも説明生成を確認します。実APIの利用には、プロバイダー側でAPIキーと利用可能なモデルを用意してください。

空の単語や100文字を超える単語は `400 Bad Request`、カテゴリが未登録の場合は `503 Service Unavailable` を返します。生成候補を確認した後、利用者が承諾した内容を `POST /api/entries` に送ると保存されます。

生成APIが保存処理を行わないことは、呼び出し前後の登録件数で確認できます。

```bash
docker compose exec db psql -U word_explainer -d word_explainer \
  -c "SELECT COUNT(*) FROM entries;"
```

上のSQLを実行して件数を記録し、生成APIを呼んだ後にもう一度実行します。件数が変わらなければ、生成APIでは保存されていません。

`POST /api/entries` は、DBにテーブルとカテゴリを用意した後に使用できます。成功すると `201 Created` と登録内容・IDを返します。未登録カテゴリや不正な入力には、`error.code` と `error.message` を含むエラー応答を返します。

```bash
curl -i -X POST http://localhost:8080/api/entries \
  -H 'Content-Type: application/json' \
  -d '{"word":"サブネット","category_id":1,"explanation":"ネットワークを分割した領域です。"}'
```

FastAPIの対話型APIドキュメントは [http://localhost:8080/docs](http://localhost:8080/docs) で確認できます。

ほかの登録済みパス:

```text
POST   /api/explanations/generate
POST   /api/entries
GET    /api/entries?word=...
GET    /api/categories
DELETE /api/entries/{id}
```

APIテストは開発用依存関係をインストールしてから実行できます。Gemini SDKはテスト内でモックするため、テスト実行ではAPIキーや外部通信は使いません。

```bash
pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
```

PostgreSQL接続設定と接続ヘルパー、および `db/schema.sql` のテーブル定義を用意しています。テーブル作成やAPIからのDB接続確認は開発者が手元で実行します。エントリー登録・検索・論理削除API、カテゴリ一覧API、Gemini APIを使った説明生成APIを実装しています。
