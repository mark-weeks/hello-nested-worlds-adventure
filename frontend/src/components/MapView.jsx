import { useId, useLayoutEffect, useMemo, useRef, useState } from "react";
import * as vendoredD3 from "../../../static/d3.v7.min.js";
import { findPath } from "../entry.js";
import { displayName, nodeAddress } from "../names.js";
import "./MapView.css";

// The same vendored UMD file exposes a browser global in Vite's dev server
// and CommonJS exports in its production bundle.
const d3 = globalThis.d3 ?? vendoredD3;
const rowGap = 5.5;
const columnGap = 15;

export function mapLayout(world, here, browsing) {
  const path = findPath(world, here) ?? [world];
  const branch = browsing === here ? path : findPath(world, browsing) ?? path;
  // Open both paths, including each destination's children. Other branches
  // unfold on demand so an eleven-scale world never needs thousands of buttons.
  const open = new Set([...path, ...branch]);
  const root = d3.hierarchy(world, place => open.has(place) ? place.children : null);
  d3.tree().nodeSize([rowGap, columnGap])(root);
  const nodes = root.descendants();
  const top = d3.min(nodes, node => node.x);
  for (const node of nodes) {
    node.left = node.y + columnGap / 2;
    node.top = node.x - top + rowGap / 2;
  }
  return {
    nodes,
    links: root.links(),
    trail: new Set(path),
    cursor: branch.at(-1).name,
    width: d3.max(nodes, node => node.left) + columnGap / 2,
    height: d3.max(nodes, node => node.top) + rowGap / 2,
  };
}

export function mapNeighbor(node, key) {
  if (key === "ArrowLeft") return node.parent;
  if (key === "ArrowRight") return node.children?.[0];
  const siblings = node.parent?.children ?? [];
  const index = siblings.indexOf(node);
  if (key === "ArrowUp") return siblings[index - 1];
  if (key === "ArrowDown") return siblings[index + 1];
  return null;
}

const linkPath = d3.linkHorizontal().x(node => node.left).y(node => node.top);

export default function MapView({ world, currentNode, onJump, focusOnOpen = false }) {
  const here = currentNode.name;
  const [cursor, setCursor] = useState(null);
  const browsing = cursor?.from === here ? cursor.name : here;
  const map = useMemo(() => mapLayout(world, here, browsing), [world, here, browsing]);
  const viewport = useRef(null);
  const marker = useRef(null);
  const focusMarker = useRef(focusOnOpen);
  const instructions = useId();

  // Passage buttons and traveler jumps can move us while we are inspecting
  // another branch. Returning to this place starts from the player's marker.
  useLayoutEffect(() => { setCursor(null); }, [here]);

  useLayoutEffect(() => {
    const view = viewport.current;
    const button = marker.current;
    if (focusMarker.current) {
      button.focus({ preventScroll: true });
      focusMarker.current = false;
    }
    // Scroll the map only. Opening it on a saved place or resizing it must
    // not move the document past Speak, the passage controls or the intro.
    function reveal() {
      const area = view.getBoundingClientRect();
      const target = button.getBoundingClientRect();
      if (target.left < area.left || target.right > area.left + view.clientWidth) {
        view.scrollLeft += target.left - area.left - (view.clientWidth - target.width) / 2;
      }
      if (target.top < area.top || target.bottom > area.top + view.clientHeight) {
        view.scrollTop += target.top - area.top - (view.clientHeight - target.height) / 2;
      }
    }
    reveal();
    const resize = new ResizeObserver(reveal);
    resize.observe(view);
    return () => resize.disconnect();
  }, [map]);

  function browse(event, node) {
    if (!["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(event.key)) return;
    event.preventDefault();
    const next = mapNeighbor(node, event.key);
    if (next) {
      focusMarker.current = true;
      setCursor({ from: here, name: next.data.name });
    }
  }

  return <div className="map-view" role="group" aria-label="World map">
    <div className="map-viewport" ref={viewport} tabIndex={-1}>
      <div className="map-board" style={{ width: `${map.width}rem`, height: `${map.height}rem` }}>
        <svg className="map-links" viewBox={`0 0 ${map.width} ${map.height}`} aria-hidden="true">
          {map.links.map(link => <path key={link.target.data.name} d={linkPath(link)}
            className={map.trail.has(link.target.data) ? "map-trail" : undefined}
            vectorEffect="non-scaling-stroke" />)}
        </svg>
        {map.nodes.map(node => {
          const { name, level } = node.data;
          const current = name === here;
          const active = name === map.cursor;
          const address = nodeAddress(name);
          return <button type="button" key={name} className="map-place"
            ref={active ? marker : undefined} tabIndex={active ? 0 : -1}
            aria-current={current ? "location" : undefined} aria-describedby={instructions}
            title={address ? `Address ${address}` : undefined}
            style={{ left: `${node.left}rem`, top: `${node.top}rem` }}
            onKeyDown={event => browse(event, node)} onClick={() => onJump(name)}>
            <span className="map-scale">
              {level}{node.data.properties?.locked && " · Sealed"}{current && " · You are here"}
            </span>
            <span className="map-name">{displayName(name)}</span>
          </button>;
        })}
      </div>
    </div>
    <p className="map-hint" id={instructions}>
      Choose a place to travel. With a keyboard, browse with the arrow keys and travel with Enter.
    </p>
  </div>;
}
