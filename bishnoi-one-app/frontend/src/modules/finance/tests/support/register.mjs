// Tests only: `node --import ./src/modules/finance/tests/support/register.mjs --test "src/modules/finance/tests/*.test.mjs"`
import { register } from "node:module";

register("./resolve-ts.mjs", import.meta.url);
