import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import App from "../App";

const candidate = {
  word: "EC2",
  category_id: 1,
  category: "コンピューティング",
  explanation: "仮想サーバーを提供します。",
};
const categories = [
  { id: 1, name: "コンピューティング" },
  { id: 2, name: "ネットワーク" },
];
const initialEntries = [
  { id: 10, word: "EC2", category_id: 1, explanation: "一つ目の説明" },
  { id: 20, word: "EC2", category_id: 1, explanation: "二つ目の説明" },
];
function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}
function setupApi(
  options: {
    emptyCategories?: boolean;
    emptyEntries?: boolean;
    deletionStatus?: number;
    loadError?: boolean;
    generationError?: boolean;
  } = {},
) {
  let entries = options.emptyEntries ? [] : [...initialEntries];
  const fetchMock = vi.fn(
    async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input);
      if (path === "/api/explanations/generate")
        return options.generationError
          ? json({ error: { message: "生成サービスが混雑しています。" } }, 502)
          : json(candidate);
      if (path === "/api/entries" && init?.method === "POST")
        return json({ id: 30, ...JSON.parse(String(init.body)) }, 201);
      if (init?.method === "DELETE") {
        if (options.deletionStatus === 503)
          return json(
            {
              error: {
                code: "DATABASE_UNAVAILABLE",
                message: "データベースに接続できません。",
              },
            },
            503,
          );
        entries = entries.filter(
          (entry) => path !== `/api/entries/${entry.id}`,
        );
        if (options.deletionStatus === 404)
          return json(
            {
              error: {
                code: "ENTRY_NOT_FOUND",
                message: "指定されたエントリーが見つかりません。",
              },
            },
            404,
          );
        return new Response(null, { status: 204 });
      }
      if (options.loadError)
        return json({ error: { message: "一覧を取得できません。" } }, 503);
      if (path === "/api/categories")
        return json({ categories: options.emptyCategories ? [] : categories });
      if (path === "/api/entries") return json({ entries });
      throw new Error(`Unexpected API request: ${path}`);
    },
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}
function openLibrary() {
  window.history.replaceState(null, "", "/#/entries");
  render(<App />);
}

describe("説明候補の承諾と保存", () => {
  it("生成とキャンセルでは保存APIを呼ばない", async () => {
    const fetchMock = setupApi();
    const user = userEvent.setup();
    render(<App />);
    await user.type(screen.getByLabelText("単語"), "  EC2  ");
    await user.click(screen.getByRole("button", { name: "説明を生成する" }));
    await screen.findByRole("heading", { name: "この内容で登録しますか？" });
    expect(
      fetchMock.mock.calls.filter(([, init]) => init?.method === "POST"),
    ).toHaveLength(1);
    expect(fetchMock.mock.calls[0][1]?.body).toBe(
      JSON.stringify({ word: "EC2" }),
    );
    await user.click(screen.getByRole("button", { name: "キャンセル" }));
    expect(
      screen.queryByRole("button", { name: "この内容で登録する" }),
    ).not.toBeInTheDocument();
    expect(
      fetchMock.mock.calls.some(
        ([path, init]) => path === "/api/entries" && init?.method === "POST",
      ),
    ).toBe(false);
  });

  it("承諾後に候補を保存し、保存処理中の連打を防ぐ", async () => {
    const fetchMock = setupApi();
    const user = userEvent.setup();
    render(<App />);
    await user.type(screen.getByLabelText("単語"), "EC2");
    await user.click(screen.getByRole("button", { name: "説明を生成する" }));
    const saveButton = await screen.findByRole("button", {
      name: "この内容で登録する",
    });
    let finishSave: (response: Response) => void = () => {};
    fetchMock.mockImplementationOnce(
      () =>
        new Promise<Response>((resolve) => {
          finishSave = resolve;
        }),
    );
    await user.dblClick(saveButton);
    expect(screen.getByRole("button", { name: "登録中…" })).toBeDisabled();
    const saveCalls = fetchMock.mock.calls.filter(
      ([path]) => path === "/api/entries",
    );
    expect(saveCalls).toHaveLength(1);
    expect(JSON.parse(String(saveCalls[0][1]?.body))).toEqual({
      word: candidate.word,
      category_id: candidate.category_id,
      explanation: candidate.explanation,
    });
    finishSave(json({ id: 30, ...candidate }, 201));
    await screen.findByText("単語を登録しました。");
    expect(
      screen.getByRole("button", { name: /登録済み一覧を見る/ }),
    ).toBeInTheDocument();
  });

  it("生成失敗時は入力を保持してエラーを表示する", async () => {
    setupApi({ generationError: true });
    const user = userEvent.setup();
    render(<App />);
    await user.type(screen.getByLabelText("単語"), "EC2");
    await user.click(screen.getByRole("button", { name: "説明を生成する" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "生成サービスが混雑しています。",
    );
    expect(screen.getByLabelText("単語")).toHaveValue("EC2");
    expect(
      screen.getByRole("button", { name: "説明を生成する" }),
    ).toBeEnabled();
  });
});

describe("カテゴリ別一覧と削除", () => {
  it("同名の単語でも選択したIDの1件だけを削除し、キャンセル時にはDELETEしない", async () => {
    const fetchMock = setupApi();
    const user = userEvent.setup();
    openLibrary();
    expect(
      await screen.findByRole("heading", { name: /コンピューティング/ }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /二つ目の説明/ }));
    await user.click(screen.getByRole("button", { name: "この単語を削除" }));
    expect(
      within(screen.getByRole("dialog")).getByText("二つ目の説明"),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "キャンセル" }));
    expect(
      fetchMock.mock.calls.filter(([, init]) => init?.method === "DELETE"),
    ).toHaveLength(0);
    await user.click(screen.getByRole("button", { name: "この単語を削除" }));
    await user.click(screen.getByRole("button", { name: "削除する" }));
    await screen.findByText("「EC2」を削除しました。");
    await waitFor(() =>
      expect(
        screen.queryByRole("button", { name: /二つ目の説明/ }),
      ).not.toBeInTheDocument(),
    );
    expect(
      await screen.findByRole("button", { name: /一つ目の説明/ }),
    ).toBeInTheDocument();
    expect(
      fetchMock.mock.calls
        .filter(([, init]) => init?.method === "DELETE")
        .map(([path]) => path),
    ).toEqual(["/api/entries/20"]);
    expect(
      fetchMock.mock.calls.filter(
        ([path, init]) => path === "/api/entries" && !init?.method,
      ).length,
    ).toBeGreaterThan(1);
  });

  it("削除済みの404を案内し、一覧を再取得する", async () => {
    setupApi({ deletionStatus: 404 });
    const user = userEvent.setup();
    openLibrary();
    await user.click(
      await screen.findByRole("button", { name: /二つ目の説明/ }),
    );
    await user.click(screen.getByRole("button", { name: "この単語を削除" }));
    await user.click(screen.getByRole("button", { name: "削除する" }));
    await screen.findByText(/すでに削除されています/);
    await waitFor(() =>
      expect(
        screen.queryByRole("button", { name: /二つ目の説明/ }),
      ).not.toBeInTheDocument(),
    );
  });

  it("削除失敗時は確認画面にエラーを表示し、選択を保持する", async () => {
    setupApi({ deletionStatus: 503 });
    const user = userEvent.setup();
    openLibrary();
    await user.click(
      await screen.findByRole("button", { name: /二つ目の説明/ }),
    );
    await user.click(screen.getByRole("button", { name: "この単語を削除" }));
    await user.click(screen.getByRole("button", { name: "削除する" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "データベースに接続できません。",
    );
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "キャンセル" }));
    expect(
      screen.getByRole("button", { name: /二つ目の説明/ }),
    ).toHaveAttribute("aria-pressed", "true");
  });

  it("カテゴリが0件なら案内する", async () => {
    setupApi({ emptyCategories: true, emptyEntries: true });
    openLibrary();
    expect(
      await screen.findByRole("heading", {
        name: "カテゴリが登録されていません",
      }),
    ).toBeInTheDocument();
  });

  it("単語0件と空の各カテゴリを表示する", async () => {
    setupApi({ emptyEntries: true });
    openLibrary();
    expect(
      await screen.findByText(/登録された単語はありません。説明を生成/),
    ).toBeInTheDocument();
    expect(
      screen.getAllByText("このカテゴリに登録された単語はありません。"),
    ).toHaveLength(2);
  });

  it("読み込み失敗と空データを区別し、再読み込みで復旧できる", async () => {
    const fetchMock = setupApi({ loadError: true });
    const user = userEvent.setup();
    openLibrary();
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "一覧を取得できません。",
    );
    expect(
      screen.queryByText("カテゴリが登録されていません"),
    ).not.toBeInTheDocument();
    fetchMock.mockImplementation(async (input) =>
      String(input) === "/api/categories"
        ? json({ categories })
        : json({ entries: initialEntries }),
    );
    await user.click(
      within(screen.getByRole("alert")).getByRole("button", {
        name: "再読み込み",
      }),
    );
    expect(
      await screen.findByRole("button", { name: /一つ目の説明/ }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});
