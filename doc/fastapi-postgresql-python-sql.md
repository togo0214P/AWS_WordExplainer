# 学習記録：2026-10-12

この記録では、AWS Word Explainer の開発を通じて学んだ API、Python、PostgreSQL、SQL、Docker の基本をまとめる。

## Web API と FastAPI

### API の通信

Web API は、クライアント（ブラウザーや別のプログラム）とサーバーが HTTP のリクエスト／レスポンスで情報をやり取りする窓口。

リクエストには主に次の情報がある。

- **メソッド**：何をしたいかを表す。例：`GET` は取得、`POST` は作成や処理依頼、`PUT` は全体置換、`PATCH` は一部変更、`DELETE` は削除。
- **パス**：対象や機能を示す。例：`/users/42`。
- **ヘッダー**：本文の形式や認証情報などを伝える。
- **本文（body）**：サーバーへ渡すデータ。JSON などを入れる。

レスポンスにはステータスコード、ヘッダー、本文が含まれる。例として `200` は成功、`201` は作成成功、`404` は対象なし、`422` は入力検証エラー。

### エンドポイントと FastAPI

`/users/{user_id}` はパス（エンドポイントのパス）。`{user_id}` はパスパラメーターで、たとえば `/users/42` の `42` が値になる。

```python
@app.get("/users/{user_id}")
def get_user(user_id: int):
    return {"id": user_id}
```

`@app.get(...)` や `@app.post(...)` は、そのメソッドとパスへのリクエストを直後の関数で処理するよう FastAPI に登録する書き方。`tags` は `/docs` の自動生成ドキュメントで API をグループ分けするための設定。

`FastAPI(title=..., description=..., version=...)` の各値は、主に自動生成ドキュメントに表示するアプリの名前・説明・バージョン。

FastAPI はアプリを定義するフレームワークで、Uvicorn はそのアプリを HTTP 経由で動かす ASGI サーバー。たとえば `uvicorn app:app --reload` は「`app.py` の `app` を Uvicorn で起動する」という指定。

### JSON リクエストと Pydantic

JSON は通常、HTTP リクエストの本文に入れ、`Content-Type: application/json` ヘッダーを付けて送信する。

```bash
curl http://localhost:8000/api/entries \
  -H 'Content-Type: application/json' \
  -d '{"word":"サブネット","category_id":1,"explanation":"ネットワークを分割した領域"}'
```

`curl` では `-H` がヘッダー指定、`-d` が本文データ指定。`-d` を付けると通常 POST になるため、`-X POST` は省略できる。`-X` は HTTP メソッドを明示するオプション。

```python
class CreateEntryRequest(BaseModel):
    word: str = Field(min_length=1)
    category_id: int = Field(gt=0)
    explanation: str = Field(min_length=1)
```

これはリクエスト本文の形と制約を定義する Pydantic モデル。`word: str` は `word` フィールドが文字列であるという型宣言で、関数の引数ではない。

```python
def create_entry(request: CreateEntryRequest):
    ...
```

この型ヒントを FastAPI が利用し、受信 JSON から `CreateEntryRequest` のインスタンスを作って検証し、`request` に渡す。検証失敗時は通常、関数本体に入る前に `422` が返る。

`Field(min_length=1)` は空文字を禁止し、`Field(gt=0)` は 0 より大きい値を要求する。`@field_validator("word", "explanation")` は、指定したフィールド名ではなく、それらのフィールドに届いた値を検証する関数を登録する。

```python
@field_validator("word", "explanation")
@classmethod
def strip_and_require_text(cls, value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("空白だけの値は指定できません。")
    return value
```

この例は前後の空白を取り除き、空白だけならエラーにする。関数はモデルのインスタンス生成時に Pydantic から呼ばれる。

## Python の `with`、`yield`、`@contextmanager`

### `with`

`with` は、対象を使い始めてから使い終わるまでをブロックとして示し、ブロック終了時の後片付けを自動で行う構文。

```python
with open("note.txt", "w") as file:
    file.write("こんにちは")
```

`with` 行で `open(...)` が実行され、返されたファイルオブジェクトが `file` に結び付く。インデントされた処理が終わるとファイルが閉じられる。概念的には `file = open(...)` に近いが、`with` は終了処理も管理する。

`with` の後ろに置けるのは、コンテキスト管理に対応したオブジェクトを返す処理。普通の関数でも、その戻り値が `with` に対応していれば使える。文字列などを返すだけの通常関数は、そのままでは `with` に使えない。

### `yield`

ジェネレーター関数では、`yield` は値を1つ渡して処理を一時停止する。次の値が求められると、停止した位置から再開する。

```python
def generate_values():
    yield 1
    yield 2

for value in generate_values():
    print(value)
```

関数を呼び出しただけでは本体はまだ進まず、`for` などが値を取り出すたびに次の `yield` まで実行される。

### `@contextmanager`

`@contextmanager` は `contextlib` のデコレーターで、`yield` を1回含むジェネレーター関数を `with` で使えるコンテキストマネージャーにする。

```python
from contextlib import contextmanager

@contextmanager
def example():
    print("開始")
    yield "渡す値"
    print("終了")

with example() as value:
    print(value)
```

実行順は「開始」→ `yield` した値を `value` に入れる → `with` ブロックの中を実行 → `yield` の後から再開して「終了」。この用途では `yield` の前が開始処理、後が終了処理になる。

DB 接続ヘルパーの例では、内側の `with psycopg.connect(...) as connection:` が接続とトランザクションのライフサイクルを管理し、`yield connection` が接続を外側の `with get_connection() as connection:` に渡す。Psycopg の接続コンテキストは正常終了時にコミットし、例外終了時にロールバックし、コンテキストを抜けると接続を閉じる。

## PostgreSQL、Docker、psql、Psycopg

- **PostgreSQL** はデータベース管理システム。Docker なしでもインストールして利用できる。
- このプロジェクトでは Compose の `db` サービスで PostgreSQL を起動する設定。Docker は環境の用意・起動・停止・データ保存の管理をしやすくする。
- `docker compose up -d db` は `db` サービスをバックグラウンド起動する。`docker compose ps` で状態を確認する。
- Compose に `POSTGRES_USER` などを変更しても、既存データボリュームが初期化済みなら、初期化時のユーザー設定は自動で変わらない。
- Docker ソケットの権限エラーは、Linux/WSL のユーザーに Docker 操作権限がない場合に起きる。`docker` グループ追加後は WSL を `wsl --shutdown` で停止し、再起動するとグループ変更を反映できる。

`psql` は人がターミナルから PostgreSQL に接続して SQL を実行するコマンドラインクライアント。DB 自体を起動するものではない。

```bash
psql -h 127.0.0.1 -p 5432 -U word_explainer -d word_explainer -W
```

- `-h`：接続先ホスト
- `-p`：接続先ポート
- `-U`：DB ユーザー
- `-d`：データベース名
- `-W`：パスワード入力を促す

接続後の `word_explainer=#` は SQL を入力する対話プロンプト。`\dt` でテーブル一覧、`\d テーブル名` でテーブル定義、`\q` で終了する。これらは SQL ではなく psql のメタコマンド。

**Psycopg** は Python コードから PostgreSQL に接続するドライバー。`connection.cursor()` で SQL 実行と結果取得に使うカーソルを作る。

```python
cursor.execute(
    "SELECT 1 FROM categories WHERE id = %s",
    (entry.category_id,),
)
row = cursor.fetchone()
```

`%s` に値をパラメーターとして渡して SQL を実行する。文字列連結で SQL を組み立てず、パラメーターを使う。`fetchone()` は結果の次の1行をタプルで返し、行がなければ `None`。`SELECT 1` は条件に合う行の存在確認に使える。

## SQL の基本

### テーブルと列

`CREATE TABLE` でテーブルを作り、括弧の中に列ごとの定義を書く。列定義はおおむね「列名、データ型、制約、必要なら初期値」の形。

```sql
CREATE TABLE categories (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);
```

- `BIGINT`：大きな整数型
- `GENERATED ALWAYS AS IDENTITY`：ID を自動採番
- `PRIMARY KEY`：行を一意に識別する主キー。重複不可、NULL 不可
- `TEXT`：文字列型
- `NOT NULL`：値を必須にする制約
- `UNIQUE`：値の重複を禁止する制約
- `DEFAULT now()`：値を省略した場合の初期値
- `REFERENCES categories(id)`：参照先を指定する外部キー制約
- `TIMESTAMPTZ`：タイムゾーンを考慮する日時型

`entries.category_id` が `categories.id` を参照すると、存在しないカテゴリ ID を entries に登録できない。`deleted_at` に削除日時を記録して行を残す設計は論理削除と呼ぶ。`updated_at DEFAULT now()` は初回値を設定するだけで、更新のたびに自動変更するには別途処理が必要。

### 行の追加と取得

```sql
INSERT INTO categories (name)
VALUES ('ネットワーク')
RETURNING id;
```

`INSERT INTO` は行を追加し、`VALUES` は列に入れる値を指定する。`RETURNING id` は追加した行の ID を返す。

```sql
SELECT id, word, category_id, explanation
FROM entries
WHERE word = 'サブネット'
ORDER BY id;
```

SQL は基本的に `SELECT` を先に書き、`FROM` で対象テーブルを指定する。

- `SELECT`：取得する列を指定
- `FROM`：検索対象のテーブルを指定
- `WHERE`：条件に合う行に絞る
- `ORDER BY id`：ID の昇順で並べる。`DESC` を付けると降順

Psycopg で新しい行を追加する例：

```python
cursor.execute(
    """
    INSERT INTO entries (word, category_id, explanation)
    VALUES (%s, %s, %s)
    RETURNING id
    """,
    (entry.word, entry.category_id, entry.explanation),
)
row = cursor.fetchone()
```

3つの `%s` に、タプル内の値が順番に対応し、`fetchone()` で `RETURNING id` の結果を受け取る。

## スキーマファイルを実行する

```bash
docker compose exec -T db psql -U word_explainer -d word_explainer -v ON_ERROR_STOP=1 < db/schema.sql
```

Compose の `db` コンテナで `psql` を起動し、手元の `db/schema.sql` を標準入力として渡して実行する。

- `exec`：起動中コンテナ内でコマンドを実行
- `-T`：疑似端末（TTY）を割り当てない。入力リダイレクトやスクリプト実行で使う
- `-v ON_ERROR_STOP=1`：SQL エラーが出たら後続を止める
- `< db/schema.sql`：ホスト側ファイルの内容をコマンドに渡す
