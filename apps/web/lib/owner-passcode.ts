/**
 * 网站主人的口令（公开模式，板块 7）。只存在这台电脑的浏览器里，请求时放在 X-Owner-Passcode 请求头。
 * 本机开发时后端不查口令，这里存不存都一样。
 */
const KEY = "wuhanmemory.owner-passcode";

export function getOwnerPasscode(): string | null {
  try {
    return window.localStorage.getItem(KEY);
  } catch {
    return null;
  }
}

export function setOwnerPasscode(value: string | null): void {
  try {
    if (value) window.localStorage.setItem(KEY, value);
    else window.localStorage.removeItem(KEY);
  } catch {
    // 浏览器不让存（例如无痕模式）：这次照样能用，只是下次还要再输
  }
}
