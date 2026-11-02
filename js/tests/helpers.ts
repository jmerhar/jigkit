/** Stand-ins the tests share. */

/** A Storage that keeps values in memory, or refuses every access when `refusing`. */
export class MemoryStorage implements Storage {
  private readonly values = new Map<string, string>();

  constructor(private readonly refusing = false) {}

  get length(): number {
    return this.values.size;
  }

  clear(): void {
    this.check();
    this.values.clear();
  }

  getItem(key: string): string | null {
    this.check();
    return this.values.get(key) ?? null;
  }

  key(index: number): string | null {
    return [...this.values.keys()][index] ?? null;
  }

  removeItem(key: string): void {
    this.check();
    this.values.delete(key);
  }

  setItem(key: string, value: string): void {
    this.check();
    this.values.set(key, value);
  }

  private check(): void {
    if (this.refusing) throw new DOMException("The operation is insecure.", "SecurityError");
  }
}
