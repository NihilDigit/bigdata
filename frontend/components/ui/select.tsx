import * as React from "react";
import { cn } from "@/lib/utils";

type SelectProps = React.SelectHTMLAttributes<HTMLSelectElement> & {
  label: string;
};

export function Select({ className, label, children, ...props }: SelectProps) {
  return (
    <label className="grid gap-1.5 text-xs font-medium text-[color:var(--muted-foreground)]">
      <span>{label}</span>
      <select
        className={cn(
          "h-10 min-w-40 rounded-lg border border-[color:var(--border)] bg-[color:var(--surface)] px-3 text-sm text-[color:var(--foreground)] outline-none transition-colors focus:border-[color:var(--primary)]",
          className,
        )}
        {...props}
      >
        {children}
      </select>
    </label>
  );
}
