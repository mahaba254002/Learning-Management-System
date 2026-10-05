import test from "node:test";
import assert from "node:assert/strict";
import { passwordSchema } from "../src/pages/auth/passwordSchema.js";

test("password policy rejects each missing requirement before submission", () => {
  for (const password of ["Aa1!", "lowercase1!", "UPPERCASE1!", "NoDigitsHere!", "NoSymbols123"]) {
    assert.equal(passwordSchema.safeParse(password).success, false);
  }
  for (const password of ["GoodPassword12!", "ValidPass123[", "ValidPass123]"]) {
    assert.equal(passwordSchema.safeParse(password).success, true);
  }
});
