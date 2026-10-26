import { useRef, useState, type FormEvent } from "react";
import { api, errorMessage } from "../api";
import type { Candidate } from "../types";
import { Icon } from "../components/Icon";
import { Notice } from "../components/Notice";

export function GeneratePage({ onOpenLibrary }: { onOpenLibrary: () => void }) {
  const [word, setWord] = useState("");
  const [candidate, setCandidate] = useState<Candidate | null>(null);
  const [operation, setOperation] = useState<"generate" | "save" | null>(null);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const inFlight = useRef(false);
  const count = Array.from(word.trim()).length;

  async function generate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (inFlight.current || count < 1 || count > 100) return;
    inFlight.current = true;
    setOperation("generate");
    setError("");
    setSaved(false);
    setCandidate(null);
    try {
      setCandidate(await api.generate(word.trim()));
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      inFlight.current = false;
      setOperation(null);
    }
  }

  async function save() {
    if (inFlight.current || !candidate) return;
    inFlight.current = true;
    setOperation("save");
    setError("");
    try {
      await api.save(candidate);
      setCandidate(null);
      setWord("");
      setSaved(true);
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      inFlight.current = false;
      setOperation(null);
    }
  }

  return (
    <>
      <div className="page-intro">
        <p className="eyebrow">
          <span /> DISCOVER & LEARN{" "}
          <span className="page-index">01 / CREATE</span>
        </p>
        <h1>
          言葉を、<em>自分の知識に。</em>
        </h1>
        <p className="lead">
          気になるAWS・IT用語を入力して、自分だけの用語ノートを育てましょう。
        </p>
      </div>
      {error && <Notice kind="error">{error}</Notice>}
      {saved && (
        <Notice kind="success">
          <span>単語を登録しました。</span>
          <button className="inline-link" onClick={onOpenLibrary}>
            登録済み一覧を見る <Icon name="arrow" />
          </button>
        </Notice>
      )}
      <div className="create-layout">
        <section className="card input-card" aria-labelledby="input-title">
          <p className="section-label">
            <span className="step">01</span> WORD INPUT
          </p>
          <h2 id="input-title">解説したい言葉</h2>
          <p className="subtle">サービス名や略語も、そのまま入力できます。</p>
          <form onSubmit={(event) => void generate(event)}>
            <label htmlFor="word">単語</label>
            <div className="word-input">
              <input
                id="word"
                autoComplete="off"
                value={word}
                onChange={(event) => setWord(event.target.value)}
                placeholder="例：Amazon EC2"
                disabled={operation !== null}
                required
                aria-describedby="word-hint"
              />
              <span className={count > 100 ? "over-limit" : ""}>
                {count} / 100
              </span>
            </div>
            <p id="word-hint" className="field-hint">
              1〜100文字で入力してください。
            </p>
            <button
              className="button primary generate-button"
              disabled={operation !== null || count < 1 || count > 100}
              type="submit"
            >
              {operation === "generate" ? (
                <span className="spinner" />
              ) : (
                <Icon name="spark" />
              )}
              {operation === "generate"
                ? "説明を生成しています…"
                : "説明を生成する"}
              <Icon name="arrow" />
            </button>
          </form>
          <p className="save-note">
            <span>✳</span> 候補を確認し、登録するまで保存されません。
          </p>
        </section>
        <aside className="guide-card">
          <p className="section-label">
            <Icon name="book" /> HOW IT WORKS
          </p>
          <h2>
            ひとつの言葉から、
            <br />
            理解を広げる。
          </h2>
          <ol>
            <li>
              <span>用語を入力する</span>
            </li>
            <li>
              <span>説明とカテゴリを確認</span>
            </li>
            <li>
              <span>承諾してライブラリへ</span>
            </li>
          </ol>
          <span className="guide-art" aria-hidden="true">
            Aa.
          </span>
        </aside>
      </div>
      {candidate && (
        <section
          className="card candidate-card"
          aria-labelledby="candidate-title"
          aria-live="polite"
        >
          <div className="candidate-heading">
            <div>
              <p className="section-label">
                <span className="step">02</span> REVIEW & SAVE
              </p>
              <h2 id="candidate-title">この内容で登録しますか？</h2>
            </div>
            <span className="spark-box">
              <Icon name="spark" />
            </span>
          </div>
          <div className="candidate-preview">
            <div className="candidate-word">
              <div>
                <span className="small-label">WORD</span>
                <h3>{candidate.word}</h3>
              </div>
              <span className="tag">{candidate.category}</span>
            </div>
            <p>{candidate.explanation}</p>
          </div>
          <div className="candidate-actions">
            <button
              className="button text"
              disabled={operation !== null}
              onClick={() => {
                setCandidate(null);
                setError("");
              }}
            >
              キャンセル
            </button>
            <button
              className="button primary"
              disabled={operation !== null}
              onClick={() => void save()}
            >
              {operation === "save" ? (
                <span className="spinner" />
              ) : (
                <Icon name="plus" />
              )}
              {operation === "save" ? "登録中…" : "この内容で登録する"}
            </button>
          </div>
        </section>
      )}
      <p className="page-note">
        <span>NOTE 01</span> カテゴリは登録済みの分類から自動で選ばれます。
      </p>
    </>
  );
}
