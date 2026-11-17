import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import App from "../App";

const auth = vi.hoisted(() => ({ initialize: vi.fn() }));
vi.mock("../auth/session", () => ({
  configurationError: "",
  takeLogoutWarning: () => "",
  setExpiryHandler: () => {},
  initialize: auth.initialize,
  login: vi.fn(), logout: vi.fn(),
  accessToken: vi.fn(), requestSignal: () => new AbortController().signal,
  unauthorized: vi.fn(),
}));

describe("認証ガード", () => {
  it("認証確認中と未ログイン時は業務画面やAPIを実行しない", async () => {
    let finish!: (value: null) => void;
    auth.initialize.mockReturnValue(new Promise((resolve) => { finish = resolve; }));
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    window.history.replaceState(null, "", "/#/entries");
    render(<App />);
    expect(screen.getByRole("status")).toHaveTextContent("認証を確認しています");
    expect(fetchMock).not.toHaveBeenCalled();
    finish(null);
    expect(await screen.findByRole("button", { name: "ログイン" })).toBeInTheDocument();
    expect(screen.queryByText("単語ライブラリ")).not.toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
