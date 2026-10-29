import { useEffect, useId, useRef } from "react";
import { createPortal } from "react-dom";
import "./Modal.css";

export default function Modal({ isOpen, onClose, title, children, wide = false }) {
  const container = useRef(null);
  const close = useRef(onClose);
  const titleId = useId();
  useEffect(() => { close.current = onClose; }, [onClose]);
  // Close on Escape key — standard modal accessibility expectation.
  useEffect(() => {
    if (!isOpen) return;
    const previous = document.activeElement;
    const previousOverflow = document.body.style.overflow;
    const root = document.getElementById('root');
    const previousInert = root?.inert;
    document.body.style.overflow = 'hidden';
    if (root) root.inert = true;
    const node = container.current;
    const focusables = () => [...node.querySelectorAll('button:not([disabled]),input:not([disabled]):not([type="hidden"]),select:not([disabled]),textarea:not([disabled]),a[href],[tabindex="0"]')].filter(el => el.offsetParent !== null);
    const items = focusables();
    (items.find(el => el.matches('input,select,textarea')) || items[0] || node).focus();

    function handleKeyDown(e) {
      if (e.key === "Escape") { e.preventDefault(); close.current(); }
      if (e.key === 'Tab') {
        const items = focusables(), first = items[0], last = items.at(-1);
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last?.focus(); }
        if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first?.focus(); }
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = previousOverflow;
      if (root) root.inert = previousInert;
      if (previous?.isConnected) previous.focus();
    };
  }, [isOpen]);

  if (!isOpen) return null;

  return createPortal(
    <div className="modal-overlay" onClick={onClose}>
      <div
        ref={container}
        className={`modal-content ${wide ? 'modal-content--wide' : ''}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-header">
          <h2 id={titleId} className="modal-title">{title}</h2>
          <button type="button" className="modal-close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>
        <div className="modal-body">{children}</div>
      </div>
    </div>, document.body
  );
}
