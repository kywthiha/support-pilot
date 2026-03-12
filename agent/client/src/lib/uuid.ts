/**
 * UUID utility – thin wrapper around the Web Crypto API.
 *
 * Centralising UUID generation here means we can swap the underlying
 * implementation (e.g. to a polyfill or `uuidv4` package) in one place
 * without touching every call-site.
 */

/**
 * Returns a cryptographically-random RFC-4122 v4 UUID string.
 * Uses the browser's built-in `crypto.randomUUID()` which is available
 * in all modern browsers (Chrome 92+, Firefox 95+, Safari 15.4+).
 *
 * @example
 * import { generateUUID } from "@/lib/uuid";
 * const id = generateUUID(); // "f47ac10b-58cc-4372-a567-0e02b2c3d479"
 */
export function generateUUID(): string {
  return crypto.randomUUID();
}
