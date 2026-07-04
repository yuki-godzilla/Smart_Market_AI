import React, {useEffect, useRef, useState} from "react";
import {createRoot} from "react-dom/client";
import {
  DndContext,
  DragOverlay,
  KeyboardSensor,
  MouseSensor,
  TouchSensor,
  closestCenter,
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
  moveAcrossContainers,
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
  const commitPending = useRef(false);
  const sensors = useSensors(
    useSensor(MouseSensor, {activationConstraint: {distance: 8}}),
    useSensor(TouchSensor, {activationConstraint: {delay: 220, tolerance: 8}}),
    useSensor(KeyboardSensor, {coordinateGetter: sortableKeyboardCoordinates}),
  );

  useEffect(() => {
    const next = cloneContainers(args.containers);
    containersRef.current = next;
    dragStartSnapshot.current = null;
    commitPending.current = false;
    setContainers(next);
  }, [args.containers]);
  useEffect(() => {
    Streamlit.setFrameHeight();
  }, [containers]);

  const emitAction = (action, groupId) => {
    if (commitPending.current) return;
    commitPending.current = true;
    Streamlit.setComponentValue({type: "action", action, groupId});
  };
  const dragOver = ({active: activeEvent, over}) => {
    if (!over || commitPending.current) return;
    setContainers((current) => {
      const next = moveAcrossContainers(current, activeEvent.id, over.id);
      containersRef.current = next;
      return next;
    });
  };
  const dragEnd = ({active: activeEvent, over}) => {
    setActive(null);
    if (commitPending.current) return;
    if (!over) {
      restoreSnapshot();
      return;
    }
    const next = finalizeDrag(containersRef.current, activeEvent.id, over.id);
    if (!next) {
      restoreSnapshot();
      return;
    }
    commitPending.current = true;
    containersRef.current = next;
    setContainers(next);
    Streamlit.setComponentValue({type: "sort", containers: next});
  };
  const dragStart = ({active: eventActive}) => {
    if (commitPending.current) return;
    dragStartSnapshot.current = cloneContainers(containersRef.current);
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

  return (
    <main className="sortable-component">
      <style>{args.customStyle}</style>
      <DndContext
        collisionDetection={closestCenter}
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
