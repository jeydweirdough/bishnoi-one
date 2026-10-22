// Tests only: `node --import ./tests/support/register.mjs --test "tests/*.test.mjs"`
import { register } from "node:module";

register("./resolve-ts.mjs", import.meta.url);
