import React from 'react';
import Spinner from './Spinner';

export default function Button({
  children,
  variant = 'primary',
  size = 'md',
  type = 'button',
  loading = false,
  disabled = false,
  className = '',
  onClick,
  ...props
}) {
  const baseStyles =
    'inline-flex items-center justify-center font-medium rounded border transition-colors select-none cursor-pointer disabled:cursor-not-allowed disabled:opacity-50';

  const sizeStyles = {
    sm: 'text-xs px-2.5 py-1.5 gap-1.5',
    md: 'text-sm px-4 py-2 gap-2',
    lg: 'text-base px-5 py-2.5 gap-2.5',
  };

  const variantStyles = {
    primary:
      'bg-blue-600 hover:bg-blue-700 active:bg-blue-800 text-white border-blue-500/30 shadow-xs',
    secondary:
      'bg-slate-800 hover:bg-slate-700 active:bg-slate-600 text-slate-200 border-slate-700',
    ghost:
      'bg-transparent hover:bg-slate-800/80 active:bg-slate-800 text-slate-300 border-transparent',
    danger:
      'bg-rose-950/80 hover:bg-rose-900 active:bg-rose-800 text-rose-200 border-rose-800/60',
  };

  return (
    <button
      type={type}
      disabled={disabled || loading}
      onClick={onClick}
      className={`${baseStyles} ${sizeStyles[size] || sizeStyles.md} ${
        variantStyles[variant] || variantStyles.primary
      } ${className}`}
      {...props}
    >
      {loading && <Spinner size="sm" />}
      {children}
    </button>
  );
}

