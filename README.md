# AWS Word Explainer API

単語解説APIのローカル開発用スケルトンです。Python 3.10以降とFastAPIを使います。

## セットアップと起動

リポジトリのルートでローカル設定ファイルを作り、仮想環境と依存パッケージを準備します。

```bash
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
docker compose up -d db
docker compose ps
```

Ubuntuで `ensurepip is not available` と表示された場合は、Pythonのvenvパッケージを追加してから再実行します（例: `sudo apt install python3.12-venv`）。Docker Compose v2も必要です。

APIサーバーは `127.0.0.1:8080`、PostgreSQLは `127.0.0.1:5432` で起動します。停止するときはAPIサーバーで `Ctrl+C` を押し、DBは `docker compose stop db` で停止します。`docker compose down` はコンテナを削除しますが、DBデータのボリュームは保持します。

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
source .venv/bin/activate
uvicorn app.main:app --reload --host 127.0.0.1 --port 8080
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

`.env` の `DB_HOST`、`DB_PORT`、`DB_NAME`、`DB_USER`、`DB_PASSWORD` がAPIのDB接続設定です。Composeも同じ設定を使います。パスワードはローカル開発専用とし、Gitへコミットしないでください。

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

説明生成APIはまだ未実装のため、呼び出すと `501 Not Implemented` が返ります。

```bash
curl -i -X POST http://localhost:8080/api/explanations/generate \
  -H 'Content-Type: application/json' \
  -d '{"word":"サブネット"}'
```

`POST /api/entries` は、DBにテーブルとカテゴリを用意した後に使用できます。成功すると `201 Created` と登録内容・IDを返します。未登録カテゴリや不正な入力には、`error.code` と `error.message` を含むエラー応答を返します。

```bash
curl -i -X POST http://localhost:8080/api/entries \
  -H 'Content-Type: application/json' \
  -d '{"word":"サブネット","category_id":1,"explanation":"ネットワークを分割した領域です。"}'
```

FastAPIの対話型APIドキュメントは [http://localhost:8080/docs](http://localhost:8080/docs) で確認できます。

ほかの登録済みパス:

```text
POST   /api/entries
GET    /api/entries?word=...
GET    /api/categories
DELETE /api/entries/{id}
```

PostgreSQL接続設定と接続ヘルパー、および `db/schema.sql` のテーブル定義を用意しています。テーブル作成やAPIからのDB接続確認は開発者が手元で実行します。エントリー登録・検索・論理削除APIとカテゴリ一覧APIは実装済みです。GPT連携はまだありません。
