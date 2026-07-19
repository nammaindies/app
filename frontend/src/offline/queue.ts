// Simple IndexedDB queue for captures made while offline or when the POST
// fails. Deliberately minimal: one object store, no retries/backoff beyond
// "try once on flush". Good enough for a placeholder PWA.
import { openDB, type IDBPDatabase } from "idb";
import { postSighting, type PostSightingInput } from "../api";

const DB_NAME = "indiedex-queue";
const STORE = "pending";

let dbPromise: Promise<IDBPDatabase> | null = null;

function getDb() {
  if (!dbPromise) {
    dbPromise = openDB(DB_NAME, 1, {
      upgrade(db) {
        db.createObjectStore(STORE, { keyPath: "id", autoIncrement: true });
      },
    });
  }
  return dbPromise;
}

export async function enqueue(input: PostSightingInput): Promise<void> {
  const db = await getDb();
  await db.add(STORE, input);
}

export async function pendingCount(): Promise<number> {
  const db = await getDb();
  return db.count(STORE);
}

let flushing = false;

export async function flush(): Promise<void> {
  if (flushing) return;
  flushing = true;
  try {
    const db = await getDb();
    const all = await db.getAll(STORE);
    const keys = await db.getAllKeys(STORE);
    for (let i = 0; i < all.length; i++) {
      try {
        await postSighting(all[i]);
        await db.delete(STORE, keys[i]);
      } catch {
        // Stop on first failure (likely still offline/unauthed); try again later.
        break;
      }
    }
  } finally {
    flushing = false;
  }
}
