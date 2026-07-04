import assert from "node:assert/strict";
import test from "node:test";

import {
  cloneContainers,
  finalizeDrag,
  findContainerIndex,
  moveAcrossContainers,
  selectCollisionId,
  shouldAcceptServerState,
} from "./dnd_state.js";

const initial = () => [
  {id: "group:a", header: "A", items: ["AAA", "BBB"], labels: {}},
  {id: "group:b", header: "B", items: ["CCC"], labels: {}},
  {id: "system:unclassified", header: "未分類", items: ["DDD"], labels: {}},
];

test("repeated cross-container previews always use the latest state", () => {
  const first = moveAcrossContainers(initial(), "AAA", "CCC");
  const second = moveAcrossContainers(first, "AAA", "DDD");

  assert.deepEqual(first.map((row) => row.items), [["BBB"], ["AAA", "CCC"], ["DDD"]]);
  assert.deepEqual(second.map((row) => row.items), [["BBB"], ["CCC"], ["AAA", "DDD"]]);
});

test("two completed drags accumulate without waiting for a remount", () => {
  const firstPreview = moveAcrossContainers(initial(), "AAA", "CCC");
  const first = finalizeDrag(firstPreview, "AAA", "CCC", "group:a");
  const secondPreview = moveAcrossContainers(first, "DDD", "BBB");
  const second = finalizeDrag(secondPreview, "DDD", "BBB", "system:unclassified");

  assert.deepEqual(first.map((row) => row.items), [["BBB"], ["AAA", "CCC"], ["DDD"]]);
  assert.deepEqual(second.map((row) => row.items), [["DDD", "BBB"], ["AAA", "CCC"], []]);
});

test("a repeated stale drag-over cannot remove another tail item", () => {
  const moved = moveAcrossContainers(initial(), "AAA", "CCC");
  const repeated = moveAcrossContainers(moved, "AAA", "CCC");

  assert.deepEqual(repeated, moved);
  assert.equal(repeated.flatMap((row) => row.items).filter((id) => id === "AAA").length, 1);
});

test("same-container drop reorders only the active item", () => {
  const finalized = finalizeDrag(initial(), "AAA", "BBB");

  assert.deepEqual(finalized[0].items, ["BBB", "AAA"]);
  assert.deepEqual(finalized[1].items, ["CCC"]);
});

test("dropping over an empty container appends the item safely", () => {
  const state = initial();
  state[0].items = [];
  const moved = moveAcrossContainers(state, "CCC", "group:a");
  const finalized = finalizeDrag(moved, "CCC", "group:a", "group:b");

  assert.deepEqual(finalized[0].items, ["CCC"]);
  assert.deepEqual(finalized[1].items, []);
});

test("invalid identifiers are rejected without mutation", () => {
  const state = initial();

  assert.equal(moveAcrossContainers(state, "missing", "CCC"), state);
  assert.equal(finalizeDrag(state, "missing", "CCC"), null);
  assert.equal(findContainerIndex(state, "missing"), -1);
});

test("clone creates a rollback-safe snapshot", () => {
  const state = initial();
  const snapshot = cloneContainers(state);
  state[0].items.splice(0, 1);

  assert.deepEqual(snapshot[0].items, ["AAA", "BBB"]);
});

test("collision selection prefers the chip directly under the pointer", () => {
  assert.equal(
    selectCollisionId(["group:b", "CCC"], ["group:a", "group:b"], "AAA"),
    "CCC",
  );
  assert.equal(
    selectCollisionId(["group:b"], ["group:a", "group:b"], "AAA"),
    "group:b",
  );
});

test("collision selection ignores the active chip and supports no hit", () => {
  assert.equal(selectCollisionId(["AAA", "group:b"], ["group:b"], "AAA"), "group:b");
  assert.equal(selectCollisionId([], ["group:b"], "AAA"), null);
});

test("server state waits until every local drag sequence is acknowledged", () => {
  assert.equal(shouldAcceptServerState(1, 0, 1, 2), false);
  assert.equal(shouldAcceptServerState(2, 1, 2, 2), true);
  assert.equal(shouldAcceptServerState(2, 2, 2, 2), false);
});
