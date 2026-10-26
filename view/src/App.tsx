import { useEffect, useState } from "react";
import { Icon } from "./components/Icon";
import { GeneratePage } from "./pages/GeneratePage";
import { LibraryPage } from "./pages/LibraryPage";

const currentPage = () =>
  window.location.hash === "#/entries" ? "library" : "generate";

export default function App() {
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
          <span className="topbar-caption">AWS WORD EXPLAINER</span>
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
