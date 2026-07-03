import React, {useEffect, useState} from "react";
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
  arrayMove,
  rectSortingStrategy,
  sortableKeyboardCoordinates,
  useSortable,
} from "@dnd-kit/sortable";
import {CSS} from "@dnd-kit/utilities";
import {
  Streamlit,
  withStreamlitConnection,
} from "streamlit-component-lib";

function Item({id, overlay = false}) {
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
      <span aria-hidden="true">⠿</span> {id}
    </button>
  );
}

function Container({container, index, total, onAction}) {
  const droppable = useDroppable({id: container.header});
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
              disabled={index === 0}
              onClick={() => onAction("up", container.groupId)}
              type="button"
            >↑</button>
            <button
              aria-label={`${container.header}を下へ`}
              disabled={index === total - 2}
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
          {container.items.map((item) => <Item id={item} key={item} />)}
        </div>
      </SortableContext>
    </section>
  );
}

function App({args}) {
  const [containers, setContainers] = useState(args.containers);
  const [active, setActive] = useState(null);
  const sensors = useSensors(
    useSensor(MouseSensor, {activationConstraint: {distance: 8}}),
    useSensor(TouchSensor, {activationConstraint: {delay: 220, tolerance: 8}}),
    useSensor(KeyboardSensor, {coordinateGetter: sortableKeyboardCoordinates}),
  );

  useEffect(() => {
    setContainers(args.containers);
  }, [args.containers]);
  useEffect(() => {
    Streamlit.setFrameHeight();
  }, [containers]);

  const findContainer = (id) => containers.findIndex(
    (container) => container.header === id || container.items.includes(id)
  );
  const emitAction = (action, groupId) => {
    Streamlit.setComponentValue({type: "action", action, groupId});
  };
  const dragOver = ({active: activeEvent, over}) => {
    if (!over) return;
    const from = findContainer(activeEvent.id);
    const to = findContainer(over.id);
    if (from < 0 || to < 0 || from === to) return;
    setContainers((current) => {
      const next = current.map((container) => ({...container, items: [...container.items]}));
      const itemIndex = next[from].items.indexOf(activeEvent.id);
      const [item] = next[from].items.splice(itemIndex, 1);
      const overIndex = next[to].items.indexOf(over.id);
      next[to].items.splice(overIndex < 0 ? next[to].items.length : overIndex, 0, item);
      return next;
    });
  };
  const dragEnd = ({active: activeEvent, over}) => {
    setActive(null);
    if (!over) return;
    setContainers((current) => {
      const target = findContainer(activeEvent.id);
      if (target < 0) return current;
      const fromIndex = current[target].items.indexOf(activeEvent.id);
      const toIndex = current[target].items.indexOf(over.id);
      const next = current.map((container, index) => (
        index === target && toIndex >= 0
          ? {...container, items: arrayMove(container.items, fromIndex, toIndex)}
          : container
      ));
      Streamlit.setComponentValue({type: "sort", containers: next});
      return next;
    });
  };

  return (
    <main className="sortable-component">
      <style>{args.customStyle}</style>
      <DndContext
        collisionDetection={closestCenter}
        onDragStart={({active: eventActive}) => setActive(eventActive.id)}
        onDragOver={dragOver}
        onDragEnd={dragEnd}
        onDragCancel={() => setActive(null)}
        sensors={sensors}
      >
        {containers.map((container, index) => (
          <Container
            container={container}
            index={index}
            key={container.header}
            onAction={emitAction}
            total={containers.length}
          />
        ))}
        <DragOverlay>{active ? <Item id={active} overlay /> : null}</DragOverlay>
      </DndContext>
    </main>
  );
}

const ConnectedApp = withStreamlitConnection(App);
createRoot(document.getElementById("root")).render(<ConnectedApp />);
