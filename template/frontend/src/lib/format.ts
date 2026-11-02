/** Moments as people read them, in the interface's language. */

import { moment as format } from "@jmerhar/jigkit/format";
import { intlLocale } from "./language";

/** A moment in the reader's own time zone: "18 Oct 2026, 14:05". */
export const moment = (iso: string, locale: string = intlLocale()): string => format(iso, locale);
