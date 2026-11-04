import React, { forwardRef, useId } from 'react';

const Input = forwardRef(function Input(
  {
    label,
    error,
    helperText,
    type = 'text',
    id,
    className = '',
    required = false,
    ...props
  },
  ref
) {
  const generatedId = useId();
  const inputId = id || generatedId;
  const errorId = `${inputId}-error`;
  const helperId = `${inputId}-helper`;

  return (
    <div className="w-full space-y-1.5">
      {label && (
        <label
          htmlFor={inputId}
          className="block text-xs font-medium text-slate-300 select-none"
        >
          {label}
          {required && <span className="text-rose-400 ml-1">*</span>}
        </label>
      )}

      <input
        ref={ref}
        id={inputId}
        type={type}
        required={required}
        aria-invalid={Boolean(error)}
        aria-describedby={
          error ? errorId : helperText ? helperId : undefined
        }
        className={`w-full px-3 py-2 text-sm bg-slate-950 border rounded text-slate-100 placeholder:text-slate-500 focus:outline-hidden ${
          error
            ? 'border-rose-500/80 focus:border-rose-400'
            : 'border-slate-800 focus:border-sky-400'
        } ${className}`}
        {...props}
      />

      {error ? (
        <p id={errorId} className="text-xs text-rose-400">
          {error}
        </p>
      ) : helperText ? (
        <p id={helperId} className="text-xs text-slate-400">
          {helperText}
        </p>
      ) : null}
    </div>
  );
});

export default Input;

