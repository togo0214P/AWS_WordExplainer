-- 初期カテゴリ。既に同じ名前のカテゴリがあれば追加しない。
INSERT INTO categories (name)
SELECT seed.name
FROM (
    VALUES
        ('コンピューティング'),
        ('ストレージ'),
        ('データベース'),
        ('セキュリティ・認証'),
        ('監視・運用')
) AS seed(name)
WHERE NOT EXISTS (
    SELECT 1
    FROM categories AS existing
    WHERE existing.name = seed.name
);
