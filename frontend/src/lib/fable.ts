import { useEffect, useState } from "react";

/**
 * Fable routing preference — persisted in localStorage, read at request time
 * by the API client so every report / focus-lens / temporal POST carries it.
 */
const STORAGE_KEY = "ai-mirror.fable";
const CHANGE_EVENT = "ai-mirror:fable-changed";

export function getFable(): boolean {
  try {
    return window.localStorage.getItem(STORAGE_KEY) === "true";
  } catch {
    return false;
  }
}

export function setFable(value: boolean): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, String(value));
  } catch {
    // Storage unavailable (private mode etc.) — in-session listeners still update.
  }
  window.dispatchEvent(new CustomEvent<boolean>(CHANGE_EVENT, { detail: value }));
}

/** React binding — stays in sync across components (and other tabs). */
export function useFable(): [boolean, (value: boolean) => void] {
  const [value, setValue] = useState<boolean>(getFable);

  useEffect(() => {
    const onLocal = (e: Event) => setValue((e as CustomEvent<boolean>).detail);
    const onStorage = (e: StorageEvent) => {
      if (e.key === STORAGE_KEY) setValue(e.newValue === "true");
    };
    window.addEventListener(CHANGE_EVENT, onLocal);
    window.addEventListener("storage", onStorage);
    return () => {
      window.removeEventListener(CHANGE_EVENT, onLocal);
      window.removeEventListener("storage", onStorage);
    };
  }, []);

  return [value, setFable];
}
