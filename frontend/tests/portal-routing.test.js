import test from "node:test";
import assert from "node:assert/strict";
import { getProtectedRouteRedirect } from "../src/routes/roleRoutes.js";

const portals = [
  ["PLATFORM_ADMIN", "/login", "/change-password", "/platform/dashboard"],
  ["INSTITUTION_ADMIN", "/login", "/change-password", "/institution/dashboard"],
  ["TEACHER", "/teacher/login", "/teacher/change-password", "/teacher/dashboard"],
  ["STUDENT", "/student/login", "/student/change-password", "/student/dashboard"],
];

for (const [role, login, password, home] of portals) {
  test(`${role}: logged-out dashboard and password routes keep their portal`, () => {
    for (const path of [home, password]) {
      assert.equal(getProtectedRouteRedirect(null, [role], path), login);
    }
  });
  test(`${role}: temporary passwords cannot reach dashboards or loop on the password page`, () => {
    const user = { role, must_change_password: true };
    assert.equal(getProtectedRouteRedirect(user, [role], home), password);
    assert.equal(getProtectedRouteRedirect(user, [role], password), null);
  });
  test(`${role}: access is allowed only for the expected role`, () => {
    const user = { role, must_change_password: false };
    assert.equal(getProtectedRouteRedirect(user, [role], home), null);
    for (const [otherRole, , , otherHome] of portals) {
      if (otherRole !== role) {
        assert.equal(getProtectedRouteRedirect(user, [otherRole], otherHome), home);
      }
    }
  });
}

test("legacy shared password URL sends a forced-change student to their portal", () => {
  assert.equal(getProtectedRouteRedirect({ role: "STUDENT", must_change_password: true }, undefined, "/change-password"), "/student/change-password");
  assert.equal(getProtectedRouteRedirect(null, undefined, "/change-password"), "/login");
});
