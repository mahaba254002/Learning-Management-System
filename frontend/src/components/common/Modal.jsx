import { useEffect, useRef } from "react";
import "./Modal.css";

export default function Modal({ isOpen, onClose, title, children, wide = false }) {
  const container = useRef(null);
  // Close on Escape key — standard modal accessibility expectation.
  useEffect(() => {
    if (!isOpen) return;
    const previous = document.activeElement;
    const node = container.current;
    const focusables = () => [...node.querySelectorAll('button:not([disabled]),input:not([disabled]):not([type="hidden"]),select:not([disabled]),textarea:not([disabled]),a[href],[tabindex="0"]')].filter(el => el.offsetParent !== null);
    (node.querySelector('input:not([type="hidden"])') || focusables()[0])?.focus();

    function handleKeyDown(e) {
      if (e.key === "Escape") onClose();
      if (e.key === 'Tab') {
        const items = focusables(), first = items[0], last = items.at(-1);
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last?.focus(); }
        if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first?.focus(); }
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => { document.removeEventListener("keydown", handleKeyDown); previous?.focus(); };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        ref={container}
        className={`modal-content ${wide ? 'modal-content--wide' : ''}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-header">
          <h2 id="modal-title" className="modal-title">{title}</h2>
          <button className="modal-close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>
        <div className="modal-body">{children}</div>
      </div>
    </div>
  );
}
