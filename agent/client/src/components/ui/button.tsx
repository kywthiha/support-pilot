import React, { type ButtonHTMLAttributes } from "react";

export type ButtonVariant = "default" | "outline" | "ghost" | "secondary";
export type ButtonSize = "default" | "lg" | "icon";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
}

const baseClasses =
  "inline-flex shrink-0 items-center justify-center gap-2 rounded-xl border border-transparent px-4 py-2 text-sm font-semibold transition focus-visible:outline-none disabled:pointer-events-none disabled:opacity-50";

const variantClasses: Record<ButtonVariant, string> = {
  default: "bg-white text-slate-950 hover:bg-slate-100",
  outline: "border-white/14 bg-transparent text-white hover:bg-white/10",
  ghost: "bg-transparent text-white hover:bg-white/10",
  secondary: "bg-white/10 text-white hover:bg-white/20",
};

const sizeClasses: Record<ButtonSize, string> = {
  default: "h-10",
  lg: "h-12 px-5 text-base",
  icon: "h-10 w-10 p-0",
};

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className = "", variant = "default", size = "default", type = "button", ...props }, ref) => {
    return (
      <button
        ref={ref}
        type={type}
        className={`${baseClasses} ${variantClasses[variant]} ${sizeClasses[size]} ${className}`.trim()}
        {...props}
      />
    );
  }
);

Button.displayName = "Button";
