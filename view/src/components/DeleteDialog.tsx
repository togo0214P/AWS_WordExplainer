import { useEffect, useRef } from "react";
import type { Entry } from "../types";
import { Icon } from "./Icon";

interface Props {
  entry: Entry;
  categoryName: string;
  pending: boolean;
  error: string;
  onCancel: () => void;
  onConfirm: () => void;
}

export function DeleteDialog({
  entry,
  categoryName,
  pending,
  error,
  onCancel,
  onConfirm,
}: Props) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const element = dialog.current;
    element?.showModal();
    return () => element?.close();
  }, []);
  return (
    <dialog
      ref={dialog}
      className="delete-dialog"
      aria-labelledby="delete-title"
      aria-describedby="delete-description"
      onCancel={(event) => {
        event.preventDefault();
        if (!pending) onCancel();
      }}
    >
      <span className="dialog-icon">
        <Icon name="trash" />
      </span>
      <p className="eyebrow">DELETE WORD</p>
      <h2 id="delete-title">この単語を削除しますか？</h2>
      <p id="delete-description">選択した1件をライブラリから削除します。</p>
      <div className="delete-preview">
        <span className="tag">{categoryName}</span>
        <h3>{entry.word}</h3>
        <p>{entry.explanation}</p>
      </div>
      {error && (
        <p className="dialog-error" role="alert">
          {error}
        </p>
      )}
      <div className="dialog-actions">
        <button
          className="button secondary"
          autoFocus
          disabled={pending}
          onClick={onCancel}
        >
          キャンセル
        </button>
        <button
          className="button danger"
          disabled={pending}
          onClick={onConfirm}
        >
          {pending ? <span className="spinner" /> : <Icon name="trash" />}
          {pending ? "削除中…" : "削除する"}
        </button>
      </div>
    </dialog>
  );
}
