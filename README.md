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
uvicorn app.main:app --reload --host 127.0.0.1 --port 8080
```

Ubuntuで `ensurepip is not available` と表示された場合は、Pythonのvenvパッケージを追加してから再実行します（例: `sudo apt install python3.12-venv`）。Docker Compose v2も必要です。

APIサーバーは `127.0.0.1:8080`、PostgreSQLは `127.0.0.1:5432` で起動します。停止するときはAPIサーバーで `Ctrl+C` を押し、DBは `docker compose stop db` で停止します。`docker compose down` はコンテナを削除しますが、DBデータのボリュームは保持します。

DBコンテナへの接続確認:

```bash
docker compose exec db psql -U word_explainer -d word_explainer
```

`.env` のパスワードはローカル開発専用です。Gitへコミットしないでください。

## curlで疎通確認

別のターミナルからヘルスチェックを呼び出します。

```bash
curl -i http://localhost:8080/health
```

応答例: `{"status":"ok"}`

Issue #1で定義したAPIのパスとHTTPメソッドも登録済みです。現段階では機能を実装していないため、APIを呼び出すと `501 Not Implemented` が返ります。

```bash
curl -i -X POST http://localhost:8080/api/explanations/generate \
  -H 'Content-Type: application/json' \
  -d '{"word":"サブネット"}'
```

FastAPIの対話型APIドキュメントは [http://localhost:8080/docs](http://localhost:8080/docs) で確認できます。

ほかの登録済みパス:

```text
POST   /api/entries
GET    /api/entries?word=...
GET    /api/categories
DELETE /api/entries/{id}
```

PostgreSQLコンテナの起動設定はありますが、FastAPIからのDB接続、テーブル作成、GPT連携、登録・検索・削除の処理はまだありません。
