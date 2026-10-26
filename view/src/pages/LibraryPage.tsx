import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError, errorMessage } from "../api";
import type { Category, Entry } from "../types";
import { DeleteDialog } from "../components/DeleteDialog";
import { Icon } from "../components/Icon";
import { Notice } from "../components/Notice";

export function LibraryPage() {
  const [categories, setCategories] = useState<Category[]>([]);
  const [entries, setEntries] = useState<Entry[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [deleting, setDeleting] = useState<Entry | null>(null);
  const [deletePending, setDeletePending] = useState(false);
  const [deleteError, setDeleteError] = useState("");
  const inFlight = useRef(false);
  const requestController = useRef<AbortController | null>(null);

  const reload = useCallback(async () => {
    requestController.current?.abort();
    const controller = new AbortController();
    requestController.current = controller;
    setLoading(true);
    setError("");
    try {
      const [categoryResult, entryResult] = await Promise.all([
        api.categories(controller.signal),
        api.entries(controller.signal),
      ]);
      if (controller.signal.aborted) return;
      setCategories(categoryResult.categories);
      setEntries(entryResult.entries);
      setSelectedId((id) =>
        entryResult.entries.some((entry) => entry.id === id) ? id : null,
      );
      setLoaded(true);
    } catch (cause) {
      if (!controller.signal.aborted) setError(errorMessage(cause));
    } finally {
      if (!controller.signal.aborted) setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
    return () => requestController.current?.abort();
  }, [reload]);

  async function confirmDelete() {
    if (!deleting || inFlight.current) return;
    inFlight.current = true;
    setDeletePending(true);
    setDeleteError("");
    try {
      let alreadyDeleted = false;
      try {
        await api.delete(deleting.id);
      } catch (cause) {
        if (
          cause instanceof ApiError &&
          cause.status === 404 &&
          cause.code === "ENTRY_NOT_FOUND"
        )
          alreadyDeleted = true;
        else throw cause;
      }
      setEntries((current) =>
        current.filter((entry) => entry.id !== deleting.id),
      );
      setSelectedId(null);
      setDeleting(null);
      setNotice(
        alreadyDeleted
          ? "この単語はすでに削除されています。一覧を再取得します。"
          : `「${deleting.word}」を削除しました。`,
      );
      await reload();
    } catch (cause) {
      setDeleteError(errorMessage(cause));
    } finally {
      inFlight.current = false;
      setDeletePending(false);
    }
  }

  const selected = entries.find((entry) => entry.id === selectedId);
  const categoryName = (entry: Entry) =>
    categories.find((category) => category.id === entry.category_id)?.name ??
    "カテゴリ不明";

  return (
    <>
      <div className="page-intro">
        <p className="eyebrow">
          <span /> YOUR COLLECTION{" "}
          <span className="page-index">02 / LIBRARY</span>
        </p>
        <div className="library-title">
          <div>
            <h1>
              単語<em>ライブラリ</em>
            </h1>
            <p className="lead">登録した言葉を、カテゴリごとに振り返る。</p>
          </div>
          <button
            className="button secondary"
            disabled={loading}
            onClick={() => void reload()}
          >
            <Icon name="refresh" /> 再読み込み
          </button>
        </div>
      </div>
      {notice && <Notice kind="success">{notice}</Notice>}
      {error && (
        <Notice kind="error">
          <span>{error}</span>
          <button
            className="inline-link"
            disabled={loading}
            onClick={() => void reload()}
          >
            再読み込み
          </button>
        </Notice>
      )}
      {loading ? (
        <div className="loading-state" role="status">
          <span className="spinner" /> ライブラリを読み込んでいます…
        </div>
      ) : (
        loaded && (
          <>
            <div className="library-summary">
              <span>
                <strong>{entries.length}</strong> 登録済み単語
              </span>
              <span>{categories.length} カテゴリ</span>
              <span className="library-hint">単語を選択して内容を確認</span>
            </div>
            {categories.length === 0 ? (
              <div className="empty-state">
                <Icon name="grid" />
                <h2>カテゴリが登録されていません</h2>
                <p>カテゴリを登録すると、ここに分類が表示されます。</p>
              </div>
            ) : (
              <div className="library-layout">
                <div className="category-list">
                  {entries.length === 0 && (
                    <Notice>
                      登録された単語はありません。説明を生成して、最初の単語を登録しましょう。
                    </Notice>
                  )}
                  {categories.map((category, index) => {
                    const categoryEntries = entries.filter(
                      (entry) => entry.category_id === category.id,
                    );
                    return (
                      <section
                        className="card category-section"
                        key={category.id}
                        aria-labelledby={`category-${category.id}`}
                      >
                        <div className="category-heading">
                          <h2 id={`category-${category.id}`}>
                            <span>{String(index + 1).padStart(2, "0")}</span>
                            {category.name}
                          </h2>
                          <span className="category-count">
                            {categoryEntries.length} WORDS
                          </span>
                        </div>
                        {categoryEntries.length === 0 ? (
                          <p className="category-empty">
                            このカテゴリに登録された単語はありません。
                          </p>
                        ) : (
                          <div className="entry-list">
                            {categoryEntries.map((entry) => (
                              <button
                                className={`entry ${selectedId === entry.id ? "selected" : ""}`}
                                key={entry.id}
                                aria-pressed={selectedId === entry.id}
                                onClick={() =>
                                  setSelectedId(
                                    selectedId === entry.id ? null : entry.id,
                                  )
                                }
                              >
                                <span className="selection-dot" />
                                <span className="entry-body">
                                  <strong>{entry.word}</strong>
                                  <span>{entry.explanation}</span>
                                </span>
                                <Icon name="arrow" />
                              </button>
                            ))}
                          </div>
                        )}
                      </section>
                    );
                  })}
                </div>
                <aside className="selection-panel" aria-live="polite">
                  <p className="section-label">
                    <Icon name="book" />{" "}
                    {selected ? "SELECTED WORD" : "WORD DETAILS"}
                  </p>
                  {selected ? (
                    <>
                      <span className="tag">{categoryName(selected)}</span>
                      <h2>{selected.word}</h2>
                      <p className="selected-explanation">
                        {selected.explanation}
                      </p>
                      <button
                        className="button danger"
                        onClick={() => {
                          setDeleting(selected);
                          setDeleteError("");
                        }}
                      >
                        <Icon name="trash" /> この単語を削除
                      </button>
                      <small>削除前に確認画面が表示されます。</small>
                    </>
                  ) : (
                    <>
                      <h2>単語を選択</h2>
                      <p>一覧から単語を選ぶと、説明の確認と削除ができます。</p>
                      <div className="selection-hint">
                        単語をクリックして選択
                      </div>
                    </>
                  )}
                </aside>
              </div>
            )}
          </>
        )
      )}
      {deleting && (
        <DeleteDialog
          entry={deleting}
          categoryName={categoryName(deleting)}
          pending={deletePending}
          error={deleteError}
          onCancel={() => setDeleting(null)}
          onConfirm={() => void confirmDelete()}
        />
      )}
      <p className="page-note">
        <span>NOTE 02</span> 削除した単語は、通常の一覧に表示されなくなります。
      </p>
    </>
  );
}
