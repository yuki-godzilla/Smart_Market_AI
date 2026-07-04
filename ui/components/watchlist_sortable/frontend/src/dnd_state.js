export function cloneContainers(containers) {
  return containers.map((container) => ({
    ...container,
    items: [...container.items],
    labels: {...(container.labels || {})},
  }));
}

export function findContainerIndex(containers, id) {
  return containers.findIndex(
    (container) => container.id === id || container.items.includes(id),
  );
}

export function moveAcrossContainers(containers, activeId, overId) {
  const from = findContainerIndex(containers, activeId);
  const to = findContainerIndex(containers, overId);
  if (from < 0 || to < 0 || from === to) return containers;

  const next = cloneContainers(containers);
  const itemIndex = next[from].items.indexOf(activeId);
  if (itemIndex < 0) return containers;
  const [item] = next[from].items.splice(itemIndex, 1);
  const overIndex = next[to].items.indexOf(overId);
  next[to].items.splice(overIndex < 0 ? next[to].items.length : overIndex, 0, item);
  return next;
}

export function finalizeDrag(containers, activeId, overId) {
  const target = findContainerIndex(containers, activeId);
  if (target < 0) return null;
  const fromIndex = containers[target].items.indexOf(activeId);
  if (fromIndex < 0) return null;
  const overContainer = findContainerIndex(containers, overId);
  if (overContainer < 0 || overContainer !== target) return cloneContainers(containers);
  const toIndex = containers[target].items.indexOf(overId);
  if (toIndex < 0 || toIndex === fromIndex) return cloneContainers(containers);

  const next = cloneContainers(containers);
  const [item] = next[target].items.splice(fromIndex, 1);
  next[target].items.splice(toIndex, 0, item);
  return next;
}
