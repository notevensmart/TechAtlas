import { useCallback, useMemo, useSyncExternalStore } from "react";
import type { Filters, RangeValue } from "../types/api";

const RANGE_VALUES = new Set(["30", "90", "180", "all"]);

function subscribe(callback: () => void) {
  window.addEventListener("popstate", callback);
  window.addEventListener("techatlas:urlchange", callback);
  return () => {
    window.removeEventListener("popstate", callback);
    window.removeEventListener("techatlas:urlchange", callback);
  };
}

function snapshot() {
  return window.location.search;
}

function readFilters(): Filters {
  const params = new URLSearchParams(window.location.search);
  const days = params.get("days");
  return {
    days: RANGE_VALUES.has(days ?? "") ? (days as RangeValue) : "30",
    city: params.get("city") || undefined,
    role_family: params.get("role_family") || undefined,
    skill_category: params.get("skill_category") || undefined,
    experience_level: params.get("experience_level") || undefined,
    work_mode: params.get("work_mode") || undefined
  };
}

export function useFilters() {
  useSyncExternalStore(subscribe, snapshot, snapshot);
  const filters = useMemo(readFilters, [window.location.search]);

  const setFilter = useCallback((key: keyof Filters, value: string | undefined) => {
    const params = new URLSearchParams(window.location.search);
    if (value) {
      params.set(key, value);
    } else {
      params.delete(key);
    }
    const query = params.toString();
    window.history.replaceState({}, "", `${window.location.pathname}${query ? `?${query}` : ""}`);
    window.dispatchEvent(new Event("techatlas:urlchange"));
  }, []);

  const resetFilters = useCallback(() => {
    window.history.replaceState({}, "", window.location.pathname);
    window.dispatchEvent(new Event("techatlas:urlchange"));
  }, []);

  return { filters, setFilter, resetFilters };
}

