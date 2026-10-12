# FastAPI・入力検証・依存関係の学習記録

## FastAPI の値の受け取り元

FastAPI はエンドポイント関数の引数について、ルートのパス、型、`Path`・`Query`・`Body` などの指定を見て、リクエストのどこから値を受け取るか判断する。

```python
@router.get("/api/entries")
def search_entries(
    word: str | None = None,
    category_id: int | None = None,
):
    ...
```

この例はパスに `{...}` がなく、引数は単純な型なので、`word` と `category_id` はクエリパラメーターになる。`= None` は省略可能という意味。

```text
GET /api/entries?word=サブネット&category_id=3
```

- **パスパラメーター**：URL パスに含まれる対象を指定する値。例：`/api/entries/{entry_id}` の `{entry_id}`。`/api/entries/5` なら関数引数 `entry_id` に `5` が渡る。
- **クエリパラメーター**：`?` の後ろに付ける検索・絞り込み条件など。複数は `&` でつなぐ。
- **Body**：JSON などリクエスト本文に入れるデータ。Pydantic モデル型の引数は通常 Body として解釈される。

```python
@router.post("/api/entries")
def create_entry(request: CreateEntryRequest):
    ...
```

`request` はパスではなく関数引数名。FastAPI は JSON Body から `CreateEntryRequest` のインスタンスを作り、検証してから関数に渡す。

同一パスでも HTTP メソッドで処理を分けられる。たとえば `GET /api/entries` は検索、`POST /api/entries` は登録に使える。

## Pydantic モデルとフィールド検証

Pydantic のモデルは、データ項目の形・型・制約をまとめたクラス。ここでのモデルは機械学習モデルではなく、データ構造の設計図を指す。

```python
class GenerateExplanationRequest(BaseModel):
    word: str = Field(min_length=1, max_length=100)
```

`word: str` は文字列フィールド、`Field(...)` はそのフィールドに追加する制約。ここでは長さを1〜100文字にする。

```python
@field_validator("word", mode="before")
@classmethod
def strip_word(cls, value: object) -> object:
    if isinstance(value, str):
        return value.strip()
    return value
```

- `@field_validator("word", ...)` は、モデル生成時に `word` を処理する検証関数として登録する。
- `mode="before"` は、Pydantic の通常の型・制約検証より先に関数を実行する指定。
- `strip()` は文字列の前後の空白を取り除く。文字列の途中にある空白はそのまま。
- 戻り値はその後 `str` 型や `Field` の制約にかけられる。空白だけの値は空文字になり、最小文字数の条件を満たさない。
- `@classmethod` はメソッドの最初の引数としてモデルクラスを渡す指定。慣例で引数名を `cls` とする。Pydantic が検証時に呼び出すため、ユーザーが直接呼ぶ必要はない。

```python
@field_validator("category", "explanation", mode="before")
@classmethod
def strip_text(cls, value: object) -> object:
    ...
```

対象フィールドを複数指定しても、関数に複数のフィールド値が一度に渡るわけではない。Pydantic が各フィールドについて別々に関数を呼び、そのときの値が `value` に入る。`cls` は classmethod として自動で渡される。

入力検証はクラス定義時ではなく、モデルのインスタンスを作るときに行われる。入力が合わなければ、FastAPI は通常エンドポイント本体の実行前に `422` を返す。このアプリでは `app/main.py` の共通ハンドラーで `400 Bad Request` に変換している。

## `Annotated` と `Path`

```python
@router.delete("/api/entries/{id}")
def delete_entry(id: Annotated[int, Path(gt=0)]):
    ...
```

`Annotated` は基本の型に追加情報を付ける記法。`int` が基本型で、`Path(gt=0)` が「パスから受け取り、0より大きい値」という FastAPI の情報を付けている。たとえば `DELETE /api/entries/5` の `5` が `id` に渡る。0以下なら入力検証エラー。

## SQL 検索条件の組み立て

```python
conditions: list[str] = []
parameters: list[str | int] = []
```

これは関数内のローカル変数を作って空リストで初期化する記法。`list[str]` は文字列のリストという型ヒントで、Python の実行時に値の型を完全に固定するものではない。

```python
if word is not None:
    conditions.append("word ILIKE %s")
    parameters.append(f"%{word}%")
if category_id is not None:
    conditions.append("category_id = %s")
    parameters.append(category_id)
```

`ILIKE` は PostgreSQL の大文字・小文字を区別しないパターン検索。`%` は任意の文字列を表すため、`%サブネット%` はその語を含む値を部分一致検索する。

```python
query += " AND " + " AND ".join(conditions)
```

`" AND ".join(conditions)` は、リストの文字列の間に ` AND ` を挟んで連結する。たとえば `['word ILIKE %s', 'category_id = %s']` なら `word ILIKE %s AND category_id = %s` となる。

両方の検索条件があると、SQL は概ね次の形になる。

```sql
SELECT id, word, category_id, explanation
FROM entries
WHERE deleted_at IS NULL
  AND word ILIKE %s
  AND category_id = %s
ORDER BY id
```

値は別の `parameters` に順番どおり入れ、`cursor.execute(query, parameters)` で渡す。SQL に値を直接連結しないことで、SQL インジェクションを避けやすくする。条件なしなら `%s` がなく `parameters` は空リストで、第二引数を省略することもできる。

## Python と Pydantic の関数

### `model_validate`

`GeneratedContent.model_validate(generated)` の `model_validate` は Pydantic v2 の `BaseModel` のメソッド。入力を指定した Pydantic モデルの形式に照らして検証し、成功すればモデルのインスタンスを返す。エラーなら `ValidationError` が発生する。

### `next()`

```python
category = next(
    (candidate for candidate in categories if candidate.name == content.category),
    None,
)
```

`next()` はイテレーターから次の値を1つ取り出す組み込み関数。ここではカテゴリ一覧から名前が一致する最初のものを取得する。見つからなければ第2引数の `None` が返る。

## FastAPI の依存性注入

```python
def generate_explanation(
    request: GenerateExplanationRequest,
    generator: ExplanationGenerator = Depends(get_explanation_generator),
):
    generated = generator.generate(request.word, categories)
```

`Depends(get_explanation_generator)` は、FastAPI に「依存関数を解決し、その戻り値を `generator` に渡す」と伝える。`request` は JSON Body のデータ、`generator` は説明生成の処理部品。依存関係として分けると、生成器の実装を差し替えやすく、テスト時にも別の生成器を使いやすい。

## curl と URL エンコード

```bash
curl -i --get "http://localhost:8080/api/entries" \
  --data-urlencode "word=サブネット" \
  --data-urlencode "category_id=3"
```

- `-i`：HTTP のステータス行とレスポンスヘッダーも表示。
- `--get`：データ指定を URL のクエリパラメーターとして送る。
- `--data-urlencode`：値を URL で安全に送れる形にエンコードする。日本語は `%e3...` のようなパーセントエンコードでログに表示されることがあるが、通常の URL エンコードであり文字化けではない。

## Git 差分の確認

`git diff --check` は変更差分の行末の余計な空白などを検出する。ファイルを変更したりコミットしたりはしない。問題がなければ通常は何も表示しない。
