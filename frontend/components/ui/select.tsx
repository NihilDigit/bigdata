import * as React from "react";
import { cn } from "@/lib/utils";

type SelectProps = React.SelectHTMLAttributes<HTMLSelectElement> & {
  label: string;
};

export function Select({ className, label, children, ...props }: SelectProps) {
  return (
    <label className="ui-select-label">
      <span>{label}</span>
      <select
        className={cn("ui-select-input", className)}
        {...props}
      >
        {children}
      </select>
    </label>
  );
}
