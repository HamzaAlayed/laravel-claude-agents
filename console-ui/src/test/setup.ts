import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// jsdom ships neither API, and both are reached for on mount by code the console
// renders on every run: @base-ui's Dialog (the decision sheet) and motion's
// AnimatePresence (the approval bar).
if (typeof window.matchMedia !== "function") {
  window.matchMedia = ((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  })) as typeof window.matchMedia;
}

if (typeof globalThis.ResizeObserver !== "function") {
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  } as unknown as typeof ResizeObserver;
}

afterEach(cleanup);
