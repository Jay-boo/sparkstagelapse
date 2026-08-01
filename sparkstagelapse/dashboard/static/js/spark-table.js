// SparkTable: sort / filter / pin / right-click "keep only or exclude" for
// one .spark-table container. Scoped entirely by DOM traversal from the
// container element passed to the constructor — no id-templated global
// functions (the old approach didn't scale past one table per page).
class SparkTable {
  constructor(container) {
    this.el = container;
    this.colNames = JSON.parse(container.dataset.colNames || "[]");
    this.numCols = this.colNames.length;
    this.sortState = { col: null, dir: 1 };
    // pinnedOrder[0] is the leftmost pinned column; newly pinned columns are
    // unshifted, so "most recently pinned" ends up furthest left.
    this.pinnedOrder = [];
    this.exactFilters = [];

    this.scroll = this.el.querySelector(".spark-scroll");
    this.tbody = this.el.querySelector("tbody");
    this.menu = this.el.querySelector('[data-role="ctxmenu"]');
    this.chipBar = this.el.querySelector('[data-role="chips"]');
    this.countEl = this.el.querySelector('[data-role="count"]');
    this.totalRows = this.tbody.querySelectorAll("tr").length;

    this._bind();
  }

  _rows() {
    return [
      this.el.querySelector("thead tr:first-child"),
      this.el.querySelector("thead tr:nth-child(2)"),
      ...this.tbody.querySelectorAll("tr"),
    ];
  }

  _bind() {
    this.el.querySelectorAll(".th-label").forEach((label, i) => {
      label.addEventListener("click", () => this.sortCol(i));
    });
    this.el.querySelectorAll(".col-filter").forEach((input) => {
      input.addEventListener("input", () => this.applyFilters());
      input.addEventListener("change", () => this.applyFilters());
    });
    this.el.querySelector(".global-search").addEventListener("input", () => this.applyFilters());
    this.el.querySelector(".clear-btn").addEventListener("click", () => this.clearFilters());

    this.tbody.addEventListener("contextmenu", (ev) => this._onCellContextMenu(ev));
    this.el.querySelector("thead").addEventListener("contextmenu", (ev) => this._onHeaderContextMenu(ev));

    document.addEventListener("click", (ev) => {
      if (!this.menu.contains(ev.target)) this._hideMenu();
    });
    document.addEventListener("keydown", (ev) => {
      if (ev.key === "Escape") this._hideMenu();
    });
    window.addEventListener("scroll", () => this._hideMenu(), true);
  }

  reorderColumns() {
    const visualOrder = [
      ...this.pinnedOrder,
      ...Array.from({ length: this.numCols }, (_, i) => i).filter((i) => !this.pinnedOrder.includes(i)),
    ];
    this._rows().forEach((row) => {
      if (!row) return;
      const cellByCol = {};
      row.querySelectorAll(":scope > th, :scope > td").forEach((cell) => {
        cellByCol[cell.dataset.col] = cell;
      });
      visualOrder.forEach((colIdx) => {
        const cell = cellByCol[colIdx];
        if (cell) row.appendChild(cell);
      });
    });
    this._relayoutStickyOffsets();
  }

  _relayoutStickyOffsets() {
    this.el.querySelectorAll("th, td").forEach((el) => {
      el.classList.remove("pinned-col");
      el.style.left = "";
    });
    if (this.pinnedOrder.length === 0) return;
    const headerRow = this.el.querySelector("thead tr:first-child");
    let offset = 0;
    this.pinnedOrder.forEach((colIdx) => {
      const headerCell = headerRow.querySelector(`[data-col="${colIdx}"]`);
      const width = headerCell ? headerCell.getBoundingClientRect().width : 0;
      this.el.querySelectorAll(`[data-col="${colIdx}"]`).forEach((el) => {
        if (el.tagName === "TH" || el.tagName === "TD") {
          el.classList.add("pinned-col");
          el.style.left = `${offset}px`;
        }
      });
      offset += width;
    });
  }

  _updatePinMarks() {
    const headerCells = this.el.querySelectorAll("thead tr:first-child th");
    headerCells.forEach((th, i) => {
      const mark = th.querySelector(".pin-mark");
      if (mark) mark.classList.toggle("active", this.pinnedOrder.includes(i));
    });
  }

  pinColumn(colIdx) {
    this.pinnedOrder = this.pinnedOrder.filter((c) => c !== colIdx);
    this.pinnedOrder.unshift(colIdx);
    this._updatePinMarks();
    this.reorderColumns();
  }

  unpinColumn(colIdx) {
    this.pinnedOrder = this.pinnedOrder.filter((c) => c !== colIdx);
    this._updatePinMarks();
    this.reorderColumns();
  }

  _renderChips() {
    this.chipBar.innerHTML = "";
    this.exactFilters.forEach((f, idx) => {
      const chip = document.createElement("span");
      chip.className = "chip";
      const label = (f.exclude ? "≠ " : "= ") + this.colNames[f.col] + ": " + f.value;
      const textSpan = document.createElement("span");
      textSpan.textContent = label;
      const x = document.createElement("span");
      x.className = "chip-x";
      x.textContent = "✕";
      x.onclick = () => {
        this.exactFilters.splice(idx, 1);
        this._renderChips();
        this.applyFilters();
      };
      chip.appendChild(textSpan);
      chip.appendChild(x);
      this.chipBar.appendChild(chip);
    });
  }

  applyFilters() {
    const globalQ = (this.el.querySelector(".global-search").value || "").toLowerCase().trim();
    const colFilters = Array.from(this.el.querySelectorAll(".col-filter"))
      .map((el) => ({ col: parseInt(el.dataset.col, 10), val: (el.value || "").toLowerCase().trim() }))
      .filter((f) => f.val !== "");

    let visible = 0;
    this.tbody.querySelectorAll("tr").forEach((row) => {
      let ok = true;
      if (globalQ && !row.dataset.search.includes(globalQ)) ok = false;

      if (ok) {
        for (const f of colFilters) {
          const cell = row.querySelector(`td[data-col="${f.col}"]`);
          const text = cell ? cell.textContent.toLowerCase() : "";
          if (!text.includes(f.val)) { ok = false; break; }
        }
      }

      if (ok) {
        for (const f of this.exactFilters) {
          const cell = row.querySelector(`td[data-col="${f.col}"]`);
          const text = cell ? cell.textContent : "";
          const matches = text === f.value;
          if (f.exclude ? matches : !matches) { ok = false; break; }
        }
      }

      row.classList.toggle("row-hidden", !ok);
      if (ok) visible++;
    });
    this.countEl.textContent = visible === this.totalRows ? `${this.totalRows} rows` : `${visible} / ${this.totalRows} rows`;
  }

  clearFilters() {
    this.el.querySelector(".global-search").value = "";
    this.el.querySelectorAll(".col-filter").forEach((el) => (el.value = ""));
    this.exactFilters = [];
    this._renderChips();
    this.applyFilters();
  }

  sortCol(colIdx) {
    const rows = Array.from(this.tbody.querySelectorAll("tr"));
    const dir = this.sortState.col === colIdx ? -this.sortState.dir : 1;
    this.sortState = { col: colIdx, dir };

    rows.sort((a, b) => {
      const av = a.querySelector(`td[data-col="${colIdx}"]`).textContent.trim();
      const bv = b.querySelector(`td[data-col="${colIdx}"]`).textContent.trim();
      const an = parseFloat(av), bn = parseFloat(bv);
      const bothNum = !isNaN(an) && !isNaN(bn) && av !== "" && bv !== "";
      if (bothNum) return (an - bn) * dir;
      return av.localeCompare(bv) * dir;
    });
    rows.forEach((r) => this.tbody.appendChild(r));

    const headerCells = this.el.querySelectorAll("thead tr:first-child th");
    headerCells.forEach((th, i) => {
      const arrow = th.querySelector(".sort-arrow");
      if (arrow) arrow.textContent = i === colIdx ? (dir === 1 ? "▲" : "▼") : "";
    });
  }

  _hideMenu() {
    this.menu.style.display = "none";
  }

  _positionMenu(x, y, w, h) {
    const vw = window.innerWidth, vh = window.innerHeight;
    this.menu.style.left = `${Math.min(x, vw - w - 8)}px`;
    this.menu.style.top = `${Math.min(y, vh - h - 8)}px`;
    this.menu.style.display = "block";
  }

  _addExactFilter(colIdx, value, exclude) {
    if (!exclude) {
      this.exactFilters = this.exactFilters.filter((f) => !(f.col === colIdx && !f.exclude));
    } else if (this.exactFilters.some((f) => f.col === colIdx && f.exclude && f.value === value)) {
      return;
    }
    this.exactFilters.push({ col: colIdx, value, exclude });
    this._renderChips();
    this.applyFilters();
  }

  _onCellContextMenu(ev) {
    const td = ev.target.closest("td");
    if (!td) return;
    ev.preventDefault();
    const colIdx = parseInt(td.dataset.col, 10);
    const value = td.textContent;
    const colName = this.colNames[colIdx];
    const display = value.length > 30 ? value.slice(0, 30) + "…" : value;

    this.menu.innerHTML = "";
    const label = document.createElement("div");
    label.className = "ctx-label";
    label.textContent = colName;
    this.menu.appendChild(label);

    const keepItem = document.createElement("div");
    keepItem.className = "ctx-item";
    keepItem.textContent = `Keep only "${display}"`;
    keepItem.onclick = () => { this._addExactFilter(colIdx, value, false); this._hideMenu(); };
    this.menu.appendChild(keepItem);

    const excludeItem = document.createElement("div");
    excludeItem.className = "ctx-item";
    excludeItem.textContent = `Exclude "${display}"`;
    excludeItem.onclick = () => { this._addExactFilter(colIdx, value, true); this._hideMenu(); };
    this.menu.appendChild(excludeItem);

    this._positionMenu(ev.clientX, ev.clientY, 220, 90);
  }

  _onHeaderContextMenu(ev) {
    const th = ev.target.closest("th");
    if (!th) return;
    ev.preventDefault();
    const colIdx = parseInt(th.dataset.col, 10);
    const colName = this.colNames[colIdx];
    const isPinned = this.pinnedOrder.includes(colIdx);

    this.menu.innerHTML = "";
    const label = document.createElement("div");
    label.className = "ctx-label";
    label.textContent = colName;
    this.menu.appendChild(label);

    const item = document.createElement("div");
    item.className = "ctx-item";
    item.textContent = isPinned ? "Unpin column" : "Pin column (move to left)";
    item.onclick = () => {
      if (isPinned) this.unpinColumn(colIdx); else this.pinColumn(colIdx);
      this._hideMenu();
    };
    this.menu.appendChild(item);

    this._positionMenu(ev.clientX, ev.clientY, 220, 60);
  }
}
