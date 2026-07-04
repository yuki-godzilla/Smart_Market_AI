import React, {useEffect, useRef, useState} from "react";
import {createRoot} from "react-dom/client";
import {
  DndContext,
  DragOverlay,
  KeyboardSensor,
  MouseSensor,
  TouchSensor,
  rectIntersection,
  pointerWithin,
  useDroppable,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import {
  SortableContext,
  rectSortingStrategy,
  sortableKeyboardCoordinates,
  useSortable,
} from "@dnd-kit/sortable";
import {CSS} from "@dnd-kit/utilities";
import {
  Streamlit,
  withStreamlitConnection,
} from "streamlit-component-lib";
import {
  cloneContainers,
  finalizeDrag,
  findContainerIndex,
  moveAcrossContainers,
  selectCollisionId,
  shouldAcceptServerState,
} from "./dnd_state.js";

function Item({id, label, overlay = false}) {
  const sortable = useSortable({id, disabled: overlay});
  const style = {
    transform: CSS.Transform.toString(sortable.transform),
    transition: sortable.transition,
    opacity: sortable.isDragging ? 0.35 : 1,
  };
  return (
    <button
      className={`sortable-item${overlay ? " sortable-overlay" : ""}`}
      ref={sortable.setNodeRef}
      style={style}
      type="button"
      {...sortable.attributes}
      {...sortable.listeners}
    >
      <span aria-hidden="true">⠿</span> {label}
    </button>
  );
}

function Container({canMoveDown, canMoveUp, container, onAction}) {
  const droppable = useDroppable({id: container.id});
  return (
    <section
      className={`sortable-container tone-${container.tone || "slate"}`}
      ref={droppable.setNodeRef}
    >
      <header className="sortable-container-header">
        <strong>{container.header}</strong>
        {!container.system && (
          <span className="group-actions">
            <button
              aria-label={`${container.header}を上へ`}
              disabled={!canMoveUp}
              onClick={() => onAction("up", container.groupId)}
              type="button"
            >↑</button>
            <button
              aria-label={`${container.header}を下へ`}
              disabled={!canMoveDown}
              onClick={() => onAction("down", container.groupId)}
              type="button"
            >↓</button>
            <button
              aria-label={`${container.header}を編集`}
              onClick={() => onAction("edit", container.groupId)}
              type="button"
            >編集</button>
          </span>
        )}
      </header>
      <SortableContext items={container.items} strategy={rectSortingStrategy}>
        <div className="sortable-container-body">
          {container.items.map((item) => (
            <Item id={item} key={item} label={container.labels[item] || item} />
          ))}
        </div>
      </SortableContext>
    </section>
  );
}

function App({args}) {
  const [containers, setContainers] = useState(args.containers);
  const [active, setActive] = useState(null);
  const containersRef = useRef(args.containers);
  const dragStartSnapshot = useRef(null);
  const lastOverId = useRef(null);
  const serverRevision = useRef(args.serverRevision || 0);
  const clientSequence = useRef(args.acknowledgedSequence || 0);
  const sensors = useSensors(
    useSensor(MouseSensor, {activationConstraint: {distance: 8}}),
    useSensor(TouchSensor, {activationConstraint: {delay: 220, tolerance: 8}}),
    useSensor(KeyboardSensor, {coordinateGetter: sortableKeyboardCoordinates}),
  );

  useEffect(() => {
    const incomingRevision = args.serverRevision || 0;
    const acknowledgedSequence = args.acknowledgedSequence || 0;
    if (!shouldAcceptServerState(
      incomingRevision,
      serverRevision.current,
      acknowledgedSequence,
      clientSequence.current,
    )) return;
    const next = cloneContainers(args.containers);
    containersRef.current = next;
    dragStartSnapshot.current = null;
    lastOverId.current = null;
    serverRevision.current = incomingRevision;
    clientSequence.current = acknowledgedSequence;
    setContainers(next);
  }, [args.acknowledgedSequence, args.containers, args.serverRevision]);
  useEffect(() => {
    Streamlit.setFrameHeight();
  }, [containers]);

  const emitAction = (action, groupId) => {
    clientSequence.current += 1;
    Streamlit.setComponentValue({
      type: "action",
      action,
      groupId,
      clientSequence: clientSequence.current,
    });
  };
  const dragOver = ({active: activeEvent, over}) => {
    if (!over) return;
    const next = moveAcrossContainers(
      containersRef.current,
      activeEvent.id,
      over.id,
    );
    containersRef.current = next;
    setContainers(next);
  };
  const dragEnd = ({active: activeEvent, over}) => {
    setActive(null);
    if (!over) {
      restoreSnapshot();
      return;
    }
    const originIndex = dragStartSnapshot.current
      ? findContainerIndex(dragStartSnapshot.current, activeEvent.id)
      : -1;
    const originContainerId = originIndex >= 0
      ? dragStartSnapshot.current[originIndex].id
      : null;
    const next = finalizeDrag(
      containersRef.current,
      activeEvent.id,
      over.id,
      originContainerId,
    );
    if (!next) {
      restoreSnapshot();
      return;
    }
    lastOverId.current = null;
    containersRef.current = next;
    setContainers(next);
    clientSequence.current += 1;
    Streamlit.setComponentValue({
      type: "sort",
      containers: next,
      clientSequence: clientSequence.current,
    });
  };
  const dragStart = ({active: eventActive}) => {
    dragStartSnapshot.current = cloneContainers(containersRef.current);
    lastOverId.current = null;
    setActive(eventActive.id);
  };
  const restoreSnapshot = () => {
    const snapshot = dragStartSnapshot.current;
    if (snapshot) {
      const restored = cloneContainers(snapshot);
      containersRef.current = restored;
      setContainers(restored);
    }
    dragStartSnapshot.current = null;
    lastOverId.current = null;
  };
  const dragCancel = () => {
    setActive(null);
    restoreSnapshot();
  };
  const activeLabel = containersRef.current
    .map((container) => container.labels?.[active])
    .find(Boolean);
  const editableContainerIds = containers
    .filter((container) => !container.system)
    .map((container) => container.id);
  const containerIds = containers.map((container) => container.id);
  const collisionDetection = (args) => {
    const pointerHits = pointerWithin(args).map((collision) => collision.id);
    const fallbackHits = pointerHits.length
      ? []
      : rectIntersection(args).map((collision) => collision.id);
    const overId = selectCollisionId(
      pointerHits.length ? pointerHits : fallbackHits,
      containerIds,
      args.active.id,
    );
    if (overId) lastOverId.current = overId;
    return overId
      ? [{id: overId}]
      : (lastOverId.current ? [{id: lastOverId.current}] : []);
  };

  return (
    <main className="sortable-component">
      <style>{args.customStyle}</style>
      <DndContext
        collisionDetection={collisionDetection}
        onDragStart={dragStart}
        onDragOver={dragOver}
        onDragEnd={dragEnd}
        onDragCancel={dragCancel}
        sensors={sensors}
      >
        {containers.map((container) => (
          <Container
            canMoveDown={
              !container.system
              && editableContainerIds.indexOf(container.id) < editableContainerIds.length - 1
            }
            canMoveUp={
              !container.system && editableContainerIds.indexOf(container.id) > 0
            }
            container={container}
            key={container.id}
            onAction={emitAction}
          />
        ))}
        <DragOverlay>
          {active ? <Item id={active} label={activeLabel || active} overlay /> : null}
        </DragOverlay>
      </DndContext>
    </main>
  );
}

const ConnectedApp = withStreamlitConnection(App);
createRoot(document.getElementById("root")).render(<ConnectedApp />);
