import React, { useEffect, useRef } from 'react';

export default function Modal({
  isOpen,
  onClose,
  title,
  description,
  children,
  maxWidth = 'max-w-lg',
}) {
  const modalRef = useRef(null);
  const previouslyFocusedElement = useRef(null);
  const onCloseRef = useRef(onClose);

  // Keep latest onClose in a ref so listeners never re-attach when onClose changes
  useEffect(() => {
    onCloseRef.current = onClose;
  });

  // Track the focused element while modal is closed so we know what opened it
  useEffect(() => {
    if (isOpen) return;

    function handleFocus(e) {
      if (e.target && e.target !== document.body && !e.target.closest?.('[role="dialog"]')) {
        previouslyFocusedElement.current = e.target;
      }
    }

    if (
      document.activeElement &&
      document.activeElement !== document.body &&
      !document.activeElement.closest?.('[role="dialog"]')
    ) {
      previouslyFocusedElement.current = document.activeElement;
    }

    document.addEventListener('focus', handleFocus, true);
    return () => {
      document.removeEventListener('focus', handleFocus, true);
    };
  }, [isOpen]);

  function restoreFocus() {
    if (previouslyFocusedElement.current && typeof previouslyFocusedElement.current.focus === 'function') {
      const el = previouslyFocusedElement.current;
      previouslyFocusedElement.current = null;
      setTimeout(() => {
        el.focus();
      }, 0);
    }
  }

  useEffect(() => {
    if (!isOpen) {
      restoreFocus();
      return;
    }

    // Move focus into modal ONLY ONCE when it opens:
    // Prefer:
    // 1. Element with autoFocus attribute
    // 2. First form input, textarea, or select
    // 3. Fallback: first focusable element (only if no form fields)
    const container = modalRef.current;
    if (container) {
      const autoFocusEl =
        container.querySelector('[autofocus]') ||
        Array.from(container.querySelectorAll('input, textarea, select, button')).find(
          (el) => el.autofocus
        );

      const formField = container.querySelector(
        'input:not([disabled]):not([type="hidden"]), textarea:not([disabled]), select:not([disabled])'
      );

      const firstFocusable = container.querySelector(
        'button:not([disabled]), a[href], input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
      );

      const target = autoFocusEl || formField || firstFocusable;
      if (target && typeof target.focus === 'function') {
        target.focus();
      }
    }

    function handleKeyDown(e) {
      if (e.key === 'Escape') {
        e.preventDefault();
        onCloseRef.current?.();
        return;
      }

      // Accessible Focus Trap: acts only on keydown events, never on re-render
      if (e.key === 'Tab' && modalRef.current) {
        const focusables = Array.from(
          modalRef.current.querySelectorAll(
            'button:not([disabled]), a[href], input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
          )
        );

        if (focusables.length === 0) {
          e.preventDefault();
          return;
        }

        const first = focusables[0];
        const last = focusables[focusables.length - 1];

        if (e.shiftKey) {
          if (document.activeElement === first || !modalRef.current.contains(document.activeElement)) {
            e.preventDefault();
            last.focus();
          }
        } else {
          if (document.activeElement === last || !modalRef.current.contains(document.activeElement)) {
            e.preventDefault();
            first.focus();
          }
        }
      }
    }

    document.addEventListener('keydown', handleKeyDown);

    // Prevent background scrolling while open
    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = originalOverflow;
      restoreFocus();
    };
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-title"
      aria-describedby={description ? 'modal-desc' : undefined}
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-xs"
      onClick={(e) => {
        if (e.target === e.currentTarget) {
          onCloseRef.current?.();
        }
      }}
    >
      <div
        ref={modalRef}
        className={`w-full ${maxWidth} bg-slate-900 border border-slate-800 rounded-lg shadow-xl overflow-hidden`}
      >
        <div className="flex items-center justify-between p-6 border-b border-slate-800">
          <div>
            <h2 id="modal-title" className="text-base font-semibold text-slate-100">
              {title}
            </h2>
            {description && (
              <p id="modal-desc" className="text-xs text-slate-400 mt-1">
                {description}
              </p>
            )}
          </div>
          <button
            type="button"
            onClick={() => onCloseRef.current?.()}
            aria-label="Close dialog"
            className="text-slate-400 hover:text-slate-200 p-1 rounded hover:bg-slate-800 text-lg leading-none cursor-pointer"
          >
            &times;
          </button>
        </div>

        <div className="p-6">{children}</div>
      </div>
    </div>
  );
}
