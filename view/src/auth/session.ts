import { UserManager, WebStorageStateStore, type User } from "oidc-client-ts";

const region = import.meta.env.VITE_COGNITO_REGION;
const pool = import.meta.env.VITE_COGNITO_USER_POOL_ID;
const clientId = import.meta.env.VITE_COGNITO_CLIENT_ID;
const domainValue = import.meta.env.VITE_COGNITO_DOMAIN;
const domain = domainValue ? `https://${domainValue.replace(/^https?:\/\//, "").replace(/\/+$/, "")}` : "";
const root = `${window.location.origin}/`;
const warningKey = "word-explainer-logout-warning";

export const configurationError = !region || !pool || !clientId || !domainValue
  ? "認証設定が不足しています。Cognitoのリージョン、ユーザープール、クライアントID、ドメインを確認してください。"
  : "";

const manager = configurationError ? null : new UserManager({
  authority: `https://cognito-idp.${region}.amazonaws.com/${pool}`,
  client_id: clientId,
  redirect_uri: root,
  response_type: "code",
  scope: "openid email",
  automaticSilentRenew: false,
  userStore: new WebStorageStateStore({ store: window.sessionStorage }),
});

let activeUser: User | null = null;
let generation = 0;
let refreshing: Promise<User> | null = null;
let aborter = new AbortController();
let onExpired: (() => void) | undefined;

export function setExpiryHandler(handler: () => void) { onExpired = handler; }
export function requestSignal() { return aborter.signal; }
export function stopSession() {
  generation++;
  activeUser = null;
  aborter.abort();
  aborter = new AbortController();
}
export async function initialize(): Promise<User | null> {
  if (!manager) throw new Error(configurationError);
  const params = new URLSearchParams(window.location.search);
  let user: User | null;
  if (params.has("code") || params.has("error") || params.has("state")) {
    try { user = await manager.signinRedirectCallback(); }
    finally { window.history.replaceState(null, "", window.location.pathname + window.location.hash); }
  } else user = await manager.getUser();
  activeUser = user;
  if (user?.expired) return refresh();
  return user;
}
export async function login() {
  if (!manager) throw new Error(configurationError);
  await manager.signinRedirect({ nonce: crypto.randomUUID() });
}
async function refresh(): Promise<User> {
  if (!manager || !activeUser) throw new Error("再ログインしてください。");
  const version = generation;
  if (!refreshing) {
    refreshing = manager.signinSilent().then((user) => {
      if (!user) throw new Error("セッションを更新できませんでした。");
      if (version !== generation) { void manager.removeUser(); throw new Error("セッションが終了しました。"); }
      return user;
    }).finally(() => { refreshing = null; });
  }
  try {
    const user = await refreshing;
    if (version !== generation) throw new Error("セッションが終了しました。");
    activeUser = user;
    return user;
  } catch (error) {
    if (version === generation) {
      stopSession();
      void manager.removeUser();
      onExpired?.();
    }
    throw error;
  }
}
export async function accessToken(): Promise<string> {
  if (!activeUser) throw new Error("ログインが必要です。");
  const user = activeUser.expires_in !== undefined && activeUser.expires_in <= 60
    ? await refresh() : activeUser;
  return user.access_token;
}
export function unauthorized() {
  if (!activeUser) return;
  stopSession();
  void manager?.removeUser();
  onExpired?.();
}
export async function logout() {
  const user = activeUser;
  stopSession();
  let failed = !user?.refresh_token;
  if (user?.refresh_token) {
    try {
      const response = await fetch(`${domain}/oauth2/revoke`, {
        method: "POST",
        signal: AbortSignal.timeout(10000),
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({ token: user.refresh_token, client_id: clientId }),
      });
      failed = !response.ok;
    } catch { failed = true; }
  }
  try { await manager?.removeUser(); } catch { failed = true; }
  if (failed) sessionStorage.setItem(warningKey, "1");
  else sessionStorage.removeItem(warningKey);
  const url = new URL(`${domain}/logout`);
  url.search = new URLSearchParams({ client_id: clientId, logout_uri: root }).toString();
  window.location.assign(url.toString());
}
export function takeLogoutWarning() {
  const warning = sessionStorage.getItem(warningKey);
  sessionStorage.removeItem(warningKey);
  return warning ? "トークンの失効を確認できませんでした。ログアウトは実行されましたが、管理者にご相談ください。" : "";
}
