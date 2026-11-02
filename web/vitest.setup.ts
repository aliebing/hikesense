import "@testing-library/jest-dom/vitest";

// Existing tests assert German texts: components rendered without a provider use German,
// and a provider mounting in a test reads German from storage unless the test says otherwise.
(globalThis as { __HIKEALL_DEFAULT_LOCALE__?: string }).__HIKEALL_DEFAULT_LOCALE__ = "de";
beforeEach(() => {
  try {
    window.localStorage.setItem("hikeall.lang", "de");
  } catch {
    // no storage in this environment
  }
});
