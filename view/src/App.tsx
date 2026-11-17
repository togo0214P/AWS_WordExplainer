import { useEffect, useState } from "react";
import type { User } from "oidc-client-ts";
import * as session from "./auth/session";
import { Icon } from "./components/Icon";
import { GeneratePage } from "./pages/GeneratePage";
import { LibraryPage } from "./pages/LibraryPage";

const currentPage = () =>
  window.location.hash === "#/entries" ? "library" : "generate";

function Workspace({ user, onLogout }: { user: User; onLogout: () => void }) {
  const [page, setPage] = useState(currentPage);
  useEffect(() => {
    const update = () => setPage(currentPage());
    window.addEventListener("hashchange", update);
    return () => window.removeEventListener("hashchange", update);
  }, []);
  function navigate(next: "generate" | "library") {
    window.location.hash = next === "library" ? "/entries" : "/";
    setPage(next);
  }
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a
          className="brand"
          href="#/"
          onClick={(event) => {
            event.preventDefault();
            navigate("generate");
          }}
        >
          <span className="brand-icon">
            <Icon name="book" />
          </span>
          <span>
            <strong>Word Explainer</strong>
            <small>AWS 用語の学習ノート</small>
          </span>
        </a>
        <p className="nav-label">MY WORKSPACE</p>
        <nav aria-label="メインメニュー">
          <a
            href="#/"
            className={page === "generate" ? "active" : ""}
            aria-current={page === "generate" ? "page" : undefined}
            onClick={() => setPage("generate")}
          >
            <Icon name="spark" />
            <span>説明をつくる</span>
          </a>
          <a
            href="#/entries"
            className={page === "library" ? "active" : ""}
            aria-current={page === "library" ? "page" : undefined}
            onClick={() => setPage("library")}
          >
            <Icon name="grid" />
            <span>単語ライブラリ</span>
          </a>
        </nav>
        <div className="sidebar-note">
          <span>✳</span>
          <p>
            わからない言葉を、
            <br />
            ひとつずつ自分の知識に。
          </p>
          <small>YOUR PERSONAL GLOSSARY</small>
        </div>
      </aside>
      <main className="main-area">
        <header className="topbar">
          <span>
            WORKSPACE <b>/</b>{" "}
            <strong>
              {page === "generate" ? "説明をつくる" : "単語ライブラリ"}
            </strong>
          </span>
          <div className="auth-user"><span>{String(user.profile.email || user.profile["cognito:username"] || user.profile.sub)}</span><button className="button secondary" onClick={onLogout}>ログアウト</button></div>
        </header>
        <div className="page-content">
          <section hidden={page !== "generate"}>
            <GeneratePage onOpenLibrary={() => navigate("library")} />
          </section>
          {page === "library" && <LibraryPage />}
        </div>
      </main>
    </div>
  );
}

export default function App() {
  const [user, setUser] = useState<User | null>(null);
  const [status, setStatus] = useState<"checking" | "ready" | "error" | "logging-out">("checking");
  const [message, setMessage] = useState(() => session.takeLogoutWarning());
  useEffect(() => {
    let mounted = true;
    session.setExpiryHandler(() => {
      if (!mounted) return;
      setUser(null);
      setMessage("セッションの有効期限が切れたか、認証に失敗しました。再ログインしてください。");
      setStatus("error");
    });
    session.initialize().then((result) => {
      if (mounted) { setUser(result); setStatus("ready"); }
    }).catch(() => {
      if (mounted) { setMessage(session.configurationError || "認証を確認できませんでした。再ログインしてください。"); setStatus("error"); }
    });
    return () => { mounted = false; };
  }, []);
  async function startLogin() {
    try { setStatus("checking"); await session.login(); }
    catch { setMessage(session.configurationError || "ログインを開始できませんでした。設定と接続を確認してください。"); setStatus("error"); }
  }
  async function startLogout() {
    setUser(null);
    setStatus("logging-out");
    try { await session.logout(); }
    catch { setMessage("ログアウトを完了できませんでした。Cognitoのログアウト設定を確認してください。"); setStatus("error"); }
  }
  if (status === "checking" || status === "logging-out") return <main className="auth-screen"><div className="card auth-card" role="status">{status === "checking" ? "認証を確認しています…" : "ログアウトしています…"}</div></main>;
  if (user && status === "ready") return <Workspace user={user} onLogout={() => void startLogout()} />;
  return <main className="auth-screen"><div className="card auth-card"><p className="section-label">AWS WORD EXPLAINER</p><h1>Word Explainer</h1><p>気になるAWS・IT用語を学び、共有ライブラリに保存しましょう。</p>{message && <p role="alert" className="auth-error">{message}</p>}<button className="button primary" disabled={!!session.configurationError} onClick={() => void startLogin()}>ログイン</button></div></main>;
}
