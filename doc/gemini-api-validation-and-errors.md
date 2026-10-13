# Gemini API・入力検証・例外処理の学習記録（2026-10-13）

## `field_validator` の実行タイミング

Pydantic の `field_validator` は、モデルのインスタンスを作るときに指定フィールドを検証・加工する関数を登録するデコレーター。クラス定義時に値を検証するのではなく、JSON などからモデルを生成するときに動く。

```python
class GeneratedCategory(BaseModel):
    id: int

    @field_validator("id")
    @classmethod
    def require_positive_id(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("IDは正の整数である必要があります")
        return value
```

`mode` を省略した場合、既定値は `after`。Pydantic が値をフィールド型に合わせて検証した後、バリデーターを実行する。`mode="before"` は型検証前の入力を処理する。たとえば文字列の前後の空白を取り除いてから型・制約を検証する場合に使う。

```python
word: str = Field(min_length=1, max_length=100)

@field_validator("word", mode="before")
@classmethod
def strip_word(cls, value: object) -> object:
    if isinstance(value, str):
        return value.strip()
    return value
```

この例では、前後の空白を取った後に `str` 型と1〜100文字の制約を検証する。空白だけの入力は空文字になり、最小文字数の条件でエラーになる。

`@classmethod` はクラスメソッドとして呼び出す指定。`cls` にはモデルクラスが渡される。この処理では `cls` を使わないが、Pydantic のバリデーターでよく使う書き方。

複数フィールドを指定しても、複数の値を一度に関数へ渡すわけではない。Pydantic がフィールドごとにバリデーターを呼び、その都度ひとつの値を `value` に渡す。

## `Annotated` と FastAPI の `Path`

```python
def delete_entry(id: Annotated[int, Path(gt=0)]):
    ...
```

`Annotated` は基本の型に追加情報を付ける記法。`int` が基本型で、`Path(gt=0)` はパスから受け取り、0より大きい値を要求する FastAPI の情報。ルートが `/api/entries/{id}` なら、URL の `/api/entries/5` の `5` が `id` に渡る。

## 独自例外と `raise` / `except`

```python
class GenerationUnavailableError(Exception):
    """Raised when Gemini generation cannot be configured."""
```

これは設定不足で生成機能が使えないことを表す独自例外。`Exception` を継承することで、Python の例外として `raise` でき、呼び出し元の `except GenerationUnavailableError` で識別できる。クラス内の三重引用符は docstring（説明文）で、例外を発生させても自動表示されない。

```python
if not self.api_key:
    raise GenerationUnavailableError
```

`raise` が実行されると、その場で現在の関数の処理を中断し、呼び出し元へ例外が伝わる。対応する `except` が捕まえると、専用のエラー応答などに変換できる。今回の API では、この例外を受け取ると `503 Service Unavailable` を返す。専用例外にすると、設定不足と予期しない障害を区別できる。

## Gemini の生成設定

```python
response = client.models.generate_content(
    model=self.model,
    contents=prompt,
    config=types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=GeneratedContent,
        max_output_tokens=512,
    ),
)
```

- `response_mime_type="application/json"`：応答を JSON 形式にするようモデルに指定する。
- `response_schema=GeneratedContent`：JSON に含める項目と構造を指定する。この例では `category` と `explanation`。
- `max_output_tokens=512`：生成する出力トークン数の上限。

MIME type とスキーマの指定は、モデルに構造化された JSON 出力を求める設定。受け取ったデータはアプリ側でも検証する。

```python
return GeneratedContent.model_validate_json(response.text)
```

`model_validate_json` は Pydantic v2 の `BaseModel` から使えるメソッド。JSON 文字列を読み取り、そのモデルの型・制約に合うか検証し、成功すればモデルのインスタンスを返す。これはファイル内で独自定義された関数ではなく、`BaseModel` から継承して使う。

## 依存性注入（`Depends`）

```python
def generate_explanation(
    request: GenerateExplanationRequest,
    generator: ExplanationGenerator = Depends(get_explanation_generator),
):
    generated = generator.generate(request.word, categories)
```

`request` は JSON Body から作られるリクエストモデル。`Depends(get_explanation_generator)` は、FastAPI に依存関数を解決させ、その戻り値を `generator` 引数へ渡す指定。生成処理をルート関数から分離でき、実装の差し替えやテスト用の生成器の利用がしやすくなる。

## `next()` で一致するカテゴリを探す

```python
category = next(
    (candidate for candidate in categories if candidate.name == content.category),
    None,
)
```

`next()` はイテレーターから次の要素を1つ取り出す Python の組み込み関数。括弧内のジェネレーター式がカテゴリを順に調べ、名前が一致する最初のカテゴリを返す。見つからないときは、第2引数で指定した `None` を返す。

## 生成 API の 503 エラー

```json
{
  "error": {
    "code": 503,
    "message": "This model is currently experiencing high demand...",
    "status": "UNAVAILABLE"
  }
}
```

HTTP 503 は Service Unavailable（一時的にサービスを利用できない）を表す。このメッセージの場合、生成先モデルの混雑による一時的な利用不可が示されている。入力値の誤りとは限らず、少し待ってから再試行する。繰り返す場合は生成先サービスの状態やアプリのログを確認する。

## タイムアウト値の読み方

```python
types.HttpOptions(timeout=30_000)
```

Python の数値中の `_` は桁を見やすくするための区切りなので、`30_000` は `30000` と同じ。Google GenAI SDK の `HttpOptions.timeout` はミリ秒単位なので、この値は30秒。
