import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { createElement } from "react";

const oidc = vi.hoisted(() => ({
  callback: vi.fn(), getUser: vi.fn(), signin: vi.fn(), renew: vi.fn(), remove: vi.fn(), settings: vi.fn(),
}));
vi.mock("oidc-client-ts", () => ({
  WebStorageStateStore: class {},
  UserManager: class {
    constructor(settings: unknown) { oidc.settings(settings); }
    signinRedirectCallback = oidc.callback;
    getUser = oidc.getUser;
    signinRedirect = oidc.signin;
    signinSilent = oidc.renew;
    removeUser = oidc.remove;
  },
}));
const user = (expires = 3600) => ({
  access_token: "access-token", refresh_token: "refresh-token", expired: expires <= 0,
  expires_in: expires, profile: { sub: "user-1" },
});

beforeEach(() => {
  vi.resetModules();
  vi.clearAllMocks();
  sessionStorage.clear();
  vi.stubEnv("VITE_COGNITO_REGION", "ap-northeast-1");
  vi.stubEnv("VITE_COGNITO_USER_POOL_ID", "ap-northeast-1_test");
  vi.stubEnv("VITE_COGNITO_CLIENT_ID", "client-id");
  vi.stubEnv("VITE_COGNITO_DOMAIN", "example.auth.ap-northeast-1.amazoncognito.com");
  oidc.getUser.mockResolvedValue(null);
  oidc.remove.mockResolvedValue(undefined);
});

describe("Cognito session", () => {
  it("コールバックをOIDCライブラリで検証してURLからコードとstateを消す", async () => {
    window.history.replaceState(null, "", "/?code=secret&state=state#/entries");
    oidc.callback.mockResolvedValue(user());
    const session = await import("../auth/session");
    expect(await session.initialize()).toEqual(user());
    expect(oidc.callback).toHaveBeenCalledOnce();
    expect(window.location.search).toBe("");
    expect(window.location.hash).toBe("#/entries");
    expect(oidc.settings).toHaveBeenCalledWith(expect.objectContaining({
      authority: "https://cognito-idp.ap-northeast-1.amazonaws.com/ap-northeast-1_test",
      redirect_uri: `${window.location.origin}/`, response_type: "code",
    }));
  });

  it("コールバック検証失敗でも認可情報をURLから消す", async () => {
    window.history.replaceState(null, "", "/?code=secret&state=invalid");
    oidc.callback.mockRejectedValue(new Error("invalid state"));
    const session = await import("../auth/session");
    await expect(session.initialize()).rejects.toThrow();
    expect(window.location.search).toBe("");
  });

  it("有効期限が近いトークンを更新し、失敗時に認証を破棄する", async () => {
    oidc.getUser.mockResolvedValue(user(20));
    oidc.renew.mockResolvedValueOnce({ ...user(), access_token: "renewed" }).mockRejectedValueOnce(new Error("renew failed"));
    const session = await import("../auth/session");
    await session.initialize();
    expect(await session.accessToken()).toBe("renewed");
    expect(oidc.renew).toHaveBeenCalledOnce();
    // Load a near-expiry session again to exercise a subsequent renewal failure.
    oidc.getUser.mockResolvedValue(user(20));
    await session.initialize();
    const expired = vi.fn();
    session.setExpiryHandler(expired);
    await expect(session.accessToken()).rejects.toThrow();
    expect(expired).toHaveBeenCalledOnce();
    expect(oidc.remove).toHaveBeenCalledOnce();
    await expect(session.accessToken()).rejects.toThrow();
  });

  it("失効通信失敗後も認証情報を破棄し戻り先で警告する", async () => {
    oidc.getUser.mockResolvedValue(user());
    const fetchMock = vi.fn().mockRejectedValue(new Error("offline"));
    vi.stubGlobal("fetch", fetchMock);
    const session = await import("../auth/session");
    await session.initialize();
    await session.logout();
    expect(fetchMock).toHaveBeenCalledWith("https://example.auth.ap-northeast-1.amazoncognito.com/oauth2/revoke", expect.objectContaining({ method: "POST", body: expect.any(URLSearchParams) }));
    expect(oidc.remove).toHaveBeenCalledOnce();
    await expect(session.accessToken()).rejects.toThrow();
    expect(session.takeLogoutWarning()).toContain("失効を確認できませんでした");
    expect(session.takeLogoutWarning()).toBe("");
  });

  it("401で認証解除し、Bearerを付けて送信する", async () => {
    oidc.getUser.mockResolvedValue(user());
    const fetchMock = vi.fn().mockResolvedValue(new Response('{}', { status: 401 }));
    vi.stubGlobal("fetch", fetchMock);
    const session = await import("../auth/session");
    const expired = vi.fn();
    session.setExpiryHandler(expired);
    await session.initialize();
    const { api } = await import("../api");
    await expect(api.entries()).rejects.toMatchObject({ status: 401 });
    expect(fetchMock).toHaveBeenCalledWith("/api/entries", expect.objectContaining({ headers: expect.objectContaining({ Authorization: "Bearer access-token" }) }));
    expect(expired).toHaveBeenCalledOnce();
    expect(oidc.remove).toHaveBeenCalledOnce();
  });


  it("業務APIが401を返すと画面を解除して再ログインを促す", async () => {
    oidc.getUser.mockResolvedValue(user());
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response('{}', { status: 401 })));
    window.history.replaceState(null, "", "/#/entries");
    const { default: App } = await import("../App");
    render(createElement(App));
    expect(await screen.findByRole("button", { name: "ログイン" })).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("再ログインしてください");
    expect(screen.queryByRole("navigation", { name: "メインメニュー" })).not.toBeInTheDocument();
  });

  it("送信中にログアウトするとAPIの結果を破棄する", async () => {
    oidc.getUser.mockResolvedValue(user());
    let resolveRequest!: (response: Response) => void;
    const fetchMock = vi.fn().mockImplementationOnce(() => new Promise<Response>((resolve) => { resolveRequest = resolve; })).mockResolvedValueOnce(new Response(null, { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const session = await import("../auth/session");
    await session.initialize();
    const { api } = await import("../api");
    const request = api.entries();
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    const signal = fetchMock.mock.calls[0][1].signal as AbortSignal;
    await session.logout();
    expect(signal.aborted).toBe(true);
    resolveRequest(new Response('{"entries":[]}', { status: 200 }));
    await expect(request).rejects.toMatchObject({ name: "AbortError" });
  });
});
