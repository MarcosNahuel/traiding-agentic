import type { ReactNode } from "react";

interface EmptyStateProps {
  title: string;
  description: string;
  action?: ReactNode;
}

export function EmptyState({ title, description, action }: EmptyStateProps) {
  return (
    <div className="rounded-xl border border-dashed border-white/20 bg-white/5 p-8 text-center">
      <h2 className="text-lg font-semibold text-white">{title}</h2>
      <p className="mx-auto mt-2 max-w-2xl text-sm text-slate-300">
        {description}
      </p>
      {action ? <div className="mt-5 flex justify-center">{action}</div> : null}
    </div>
  );
}

