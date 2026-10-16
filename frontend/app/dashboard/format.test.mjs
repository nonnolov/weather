import assert from "node:assert/strict";
import test from "node:test";

test("selects the forecast hour containing the current-conditions time", async () => {
  const format = await import("./format.ts");
  assert.equal(typeof format.currentHourly, "function", "currentHourly should be exported");

  const hourly = [
    { valid_time: "2026-10-16T17:00:00Z", precipitation_probability: 20 },
    { valid_time: "2026-10-16T18:00:00Z", precipitation_probability: 70 },
  ];

  assert.equal(
    format.currentHourly(hourly, "2026-10-16T17:45:00Z"),
    hourly[0],
  );
});

test("returns undefined when no hourly forecast covers the current time", async () => {
  const { currentHourly } = await import("./format.ts");
  const hourly = [
    { valid_time: "2026-10-16T17:00:00Z", precipitation_probability: 20 },
  ];

  assert.equal(currentHourly(hourly, "2026-10-16T19:00:00Z"), undefined);
});
