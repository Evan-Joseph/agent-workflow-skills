(() => {
  if (window.__claudePaymentCountryReview) return;

  const style = document.createElement("style");
  style.textContent = `
    #claude-payment-country-review {
      position: fixed;
      z-index: 2147483647;
      top: 12px;
      right: 12px;
      width: min(360px, calc(100vw - 24px));
      padding: 10px;
      background: #ffffff;
      color: #171717;
      border: 1px solid #b8b8b8;
      border-radius: 6px;
      box-shadow: 0 4px 16px #00000033;
      font: 13px/1.4 system-ui, sans-serif;
      display: grid;
      grid-template-columns: 40px minmax(0, 1fr) 40px;
      gap: 8px;
      text-align: left;
    }
    #claude-payment-country-review[hidden] { display: none; }
    #claude-payment-country-review button {
      min-width: 36px;
      min-height: 32px;
      border: 1px solid #a8a8a8;
      border-radius: 4px;
      background: #f4f4f4;
      color: #171717;
      cursor: pointer;
    }
    #claude-payment-country-review button:disabled {
      cursor: not-allowed;
      opacity: 0.45;
    }
    #review-title { grid-column: 1 / 3; font-weight: 650; }
    #review-hide { grid-column: 3; grid-row: 1; }
    #review-prev { grid-column: 1; }
    #review-position { grid-column: 2; align-self: center; text-align: center; }
    #review-next { grid-column: 3; }
    #review-unique,
    #review-methods,
    #review-note,
    #review-actions,
    #review-status {
      grid-column: 1 / -1;
      min-width: 0;
      white-space: normal;
    }
    #review-methods, #review-note {
      width: 100%;
      box-sizing: border-box;
      border: 1px solid #a8a8a8;
      border-radius: 4px;
      padding: 7px;
      color: #171717;
      background: #ffffff;
      font: inherit;
    }
    #review-note { min-height: 52px; resize: vertical; }
    #review-actions { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
    #review-status { min-height: 20px; color: #444444; overflow-wrap: anywhere; }
  `;
  document.documentElement.appendChild(style);

  const root = document.createElement("section");
  root.id = "claude-payment-country-review";
  root.setAttribute("aria-label", "付款国家人工审阅");
  root.innerHTML = `
    <strong id="review-title">付款国家人工审阅</strong>
    <button id="review-hide" type="button" title="隐藏控制条" aria-label="隐藏控制条">&#215;</button>
    <button id="review-prev" type="button" title="上一个国家" aria-label="上一个国家">&#8592;</button>
    <output id="review-position">付款表单未就绪</output>
    <button id="review-next" type="button" title="下一个国家" aria-label="下一个国家">&#8594;</button>
    <label id="review-unique"><input id="review-unique-input" type="checkbox"> 发现独特付款方式</label>
    <input id="review-methods" type="text" maxlength="819" placeholder="付款方式，使用逗号分隔">
    <textarea id="review-note" maxlength="200" placeholder="备注"></textarea>
    <div id="review-actions">
      <button id="review-save" type="button">保存标记</button>
      <button id="review-clear" type="button">清除标记</button>
      <button id="review-export" type="button">导出JSON</button>
    </div>
    <output id="review-status" aria-live="polite"></output>`;
  document.documentElement.appendChild(root);

  const element = id => root.querySelector(`#${id}`);
  let sequence = 0;
  let renderedCountry = null;
  let renderedAnnotation = null;

  const send = (type, payload = {}) => {
    sequence += 1;
    window.__manualPaymentReviewEvent({
      id: `${Date.now()}-${sequence}`,
      type,
      ...payload,
    });
  };

  element("review-prev").addEventListener("click", () => send("previous"));
  element("review-next").addEventListener("click", () => send("next"));
  element("review-save").addEventListener("click", () => send("save", {
    has_unique_method: element("review-unique-input").checked,
    methods_text: element("review-methods").value,
    note: element("review-note").value,
  }));
  element("review-clear").addEventListener("click", () => send("clear"));
  element("review-export").addEventListener("click", () => send("export"));
  element("review-hide").addEventListener("click", () => { root.hidden = true; });
  document.addEventListener("keydown", event => {
    const target = event.target;
    const editing = target instanceof Element && (
      target.matches("input, textarea, select") || target.isContentEditable
    );
    if (!event.altKey || editing) return;
    if (event.key === "ArrowLeft") {
      event.preventDefault();
      send("previous");
    }
    if (event.key === "ArrowRight") {
      event.preventDefault();
      send("next");
    }
  });

  window.__claudePaymentCountryReview = {
    render(state) {
      const ready = state.ready === true;
      element("review-prev").disabled = !ready || state.previous_disabled === true;
      element("review-next").disabled = !ready || state.next_disabled === true;
      element("review-position").textContent = ready
        ? `${state.country_label} (${state.current_country}) ${state.position}/${state.total}`
        : "付款表单未就绪";
      const annotationKey = state.annotation_updated_at || "";
      if (state.current_country !== renderedCountry || annotationKey !== renderedAnnotation) {
        element("review-unique-input").checked = state.has_unique_method === true;
        element("review-methods").value = state.methods_text || "";
        element("review-note").value = state.note || "";
        renderedCountry = state.current_country || null;
        renderedAnnotation = annotationKey;
      }
      element("review-status").textContent = state.status_text || "";
    },
  };
})();
