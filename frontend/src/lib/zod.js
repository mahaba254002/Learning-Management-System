// zod normally probes for eval to enable a faster parser. The site CSP blocks
// eval, so the probe only produces a browser warning. Forms are small, so use
// the standard parser and skip the probe. Import z from here, not from "zod".
import { z } from "zod";

z.config({ jitless: true });

export { z };
