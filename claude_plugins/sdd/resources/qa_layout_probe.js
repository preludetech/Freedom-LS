// Loaded as a browser init script, so every page the QA run opens can call
// window.__qaLayoutProbe(regions). `regions` maps a region name to a CSS selector:
// "header" and "content" are compared for alignment, "sidebar" and "content" for
// placement (a sidebar sits beside the content, sharing its vertical span and
// taking less than half the viewport), and every region is checked for overlap
// with the others. It returns the ink bounds of each region and any flags.
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

  // An element clips what it contains: overflow other than visible, or a clip.
  const clips = (el) => {
    const style = getComputedStyle(el);
    return (
      style.overflowX !== "visible" || style.overflowY !== "visible" ||
      style.clip !== "auto" || style.clipPath !== "none"
    );
  };

  const UNBOUNDED = { left: -Infinity, top: -Infinity, right: Infinity, bottom: Infinity };
  const intersect = (a, b) => ({
    left: Math.max(a.left, b.left),
    top: Math.max(a.top, b.top),
    right: Math.min(a.right, b.right),
    bottom: Math.min(a.bottom, b.bottom),
  });

  // The box an element's contents are clipped to by it and every ancestor,
  // memoised because siblings share their ancestors.
  const contentClips = new Map();
  const contentClip = (el) => {
    if (!el || el === document.documentElement) return UNBOUNDED;
    if (contentClips.has(el)) return contentClips.get(el);
    const inherited = contentClip(el.parentElement);
    const box = clips(el) ? intersect(inherited, el.getBoundingClientRect()) : inherited;
    contentClips.set(el, box);
    return box;
  };

  // The union of what is actually drawn inside the given roots, ignoring empty
  // wrappers and whatever an ancestor clips away: ink past an overflow hidden,
  // auto or scroll edge, such as an ellipsis-truncated label, a screen-reader-only
  // span or a table inside a horizontal scroll region, is measured at what shows.
  const inkBounds = (roots) => {
    let left = Infinity, right = -Infinity, top = Infinity, bottom = -Infinity;
    const add = (rect, clip) => {
      const shown = intersect(rect, clip);
      if (shown.right - shown.left <= 0 || shown.bottom - shown.top <= 0) return;
      left = Math.min(left, shown.left);
      right = Math.max(right, shown.right);
      top = Math.min(top, shown.top);
      bottom = Math.max(bottom, shown.bottom);
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
            const clip = contentClip(node.parentElement);
            for (const rect of range.getClientRects()) add(rect, clip);
          }
        } else if (isVisible(node) && paints(node)) {
          // Its own overflow clips its contents, not its border or background.
          add(node.getBoundingClientRect(), contentClip(node.parentElement));
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

  // A sidebar that is drawn at all is a column beside the content: its ink shares
  // the content's vertical span and stays narrower than half the viewport. A
  // sidebar stacked above or below the content, or spanning the page, has lost
  // its column, which a glance at a screenshot passes as "a menu at the top".
  if (regions.sidebar && regions.content) {
    const s = regions.sidebar, c = regions.content;
    if (s.bottom <= c.top || s.top >= c.bottom) {
      flags.push(`stacked: sidebar ink spans y=${s.top}..${s.bottom}, outside the content's y=${c.top}..${c.bottom}`);
    }
    if (s.right - s.left > viewportWidth / 2) {
      flags.push(`stacked: sidebar ink spans x=${s.left}..${s.right}, more than half of the ${viewportWidth}px viewport`);
    }
  }

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
