import { useEffect, useState } from "react";
import type { SellerRow, Slipbook, SlipDeskData, Stamp, Summary, TestVector } from "./types";

async function get<T>(name: string): Promise<T> {
  const res = await fetch(`data/${name}.json`);
  if (!res.ok) throw new Error(`failed to load data/${name}.json`);
  return res.json() as Promise<T>;
}

async function tryGet<T>(name: string): Promise<T | null> {
  try {
    return await get<T>(name);
  } catch {
    return null;
  }
}

/** Loads the pipeline payloads (written by scripts/build_web.py). */
export function useSlipDeskData() {
  const [data, setData] = useState<SlipDeskData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const [summary, sellers, slipbook, vectors, stamp] = await Promise.all([
          get<Summary>("summary"),
          get<SellerRow[]>("sellers"),
          get<Slipbook>("slipbook"),
          get<{ vectors: TestVector[] }>("test-vectors"),
          tryGet<Stamp>("stamp"),
        ]);
        setData({ summary, sellers, slipbook, vectors, stamp });
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      }
    })();
  }, []);

  return { data, error };
}
