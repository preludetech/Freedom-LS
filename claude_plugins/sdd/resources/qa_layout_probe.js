// Loaded as a browser init script, so every page the QA run opens can call
// window.__qaLayoutProbe(regions). `regions` maps a region name to a CSS selector:
// "header" and "content" are compared for alignment, and every region is checked for
// overlap with the others. It returns the ink bounds of each region and any flags.
window.__qaLayoutProbe = (REGIONS = {}) => {
  const ALIGN_TOLERANCE = 8;

  const isVisible = (el) => {
    const style = getComputedStyle(el);
    if (style.visibility === "hidden" || style.display === "none" || Number(style.opacity) === 0) {
      return false;
    }
    const rect = el.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
  };

  // An element draws something itself: a border, a background, or replaced content.
  const paints = (el) => {
    if (["IMG", "SVG", "svg", "VIDEO", "CANVAS", "INPUT", "SELECT", "TEXTAREA", "BUTTON", "PROGRESS"].includes(el.tagName)) {
      return true;
    }
    const style = getComputedStyle(el);
    const hasBorder = ["Top", "Right", "Bottom", "Left"].some(
      (side) => parseFloat(style[`border${side}Width`]) > 0 && style[`border${side}Style`] !== "none",
    );
    const bg = style.backgroundColor;
    const hasBackground = (bg && bg !== "transparent" && !/rgba\(.*,\s*0\)$/.test(bg)) || style.backgroundImage !== "none";
    return hasBorder || hasBackground;
  };

  // The union of what is actually drawn inside the given roots, ignoring empty wrappers.
  const inkBounds = (roots) => {
    let left = Infinity, right = -Infinity, top = Infinity, bottom = -Infinity;
    const add = (rect) => {
      if (rect.width <= 0 || rect.height <= 0) return;
      left = Math.min(left, rect.left);
      right = Math.max(right, rect.right);
      top = Math.min(top, rect.top);
      bottom = Math.max(bottom, rect.bottom);
    };
    for (const root of roots) {
      if (!isVisible(root)) continue;
      const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT);
      let node = walker.currentNode;
      while (node) {
        if (node.nodeType === Node.TEXT_NODE) {
          if (node.textContent.trim() && node.parentElement && isVisible(node.parentElement)) {
            const range = document.createRange();
            range.selectNodeContents(node);
            for (const rect of range.getClientRects()) add(rect);
          }
        } else if (isVisible(node) && paints(node)) {
          add(node.getBoundingClientRect());
        }
        node = walker.nextNode();
      }
    }
    if (left === Infinity) return null;
    const round = (n) => Math.round(n);
    return { left: round(left), right: round(right), top: round(top), bottom: round(bottom) };
  };

  const regions = {};
  const missing = [];
  for (const [name, selector] of Object.entries(REGIONS)) {
    const roots = [...document.querySelectorAll(selector)];
    const bounds = roots.length ? inkBounds(roots) : null;
    if (bounds) regions[name] = bounds;
    else missing.push(name);
  }

  const flags = [];

  if (regions.header && regions.content) {
    const delta = regions.content.left - regions.header.left;
    if (Math.abs(delta) > ALIGN_TOLERANCE) {
      flags.push(`misaligned: header ink starts at x=${regions.header.left}, content at x=${regions.content.left} (${delta}px)`);
    }
  }

  const viewportWidth = document.documentElement.clientWidth;
  if (document.documentElement.scrollWidth > viewportWidth) {
    flags.push(`overflow: document is ${document.documentElement.scrollWidth}px wide in a ${viewportWidth}px viewport`);
  }
  for (const [name, bounds] of Object.entries(regions)) {
    if (bounds.right > viewportWidth + 1 || bounds.left < -1) {
      flags.push(`overflow: ${name} ink spans x=${bounds.left}..${bounds.right} in a ${viewportWidth}px viewport`);
    }
  }

  const names = Object.keys(regions);
  for (let i = 0; i < names.length; i++) {
    for (let j = i + 1; j < names.length; j++) {
      const a = regions[names[i]], b = regions[names[j]];
      const overlaps = a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom;
      if (overlaps) flags.push(`overlap: ${names[i]} and ${names[j]} ink intersect`);
    }
  }

  return { url: location.pathname, viewport: viewportWidth, regions, missing, flags };
};
