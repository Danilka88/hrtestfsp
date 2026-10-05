import { useQuery } from "@tanstack/react-query";

import { fetchHealth, fetchReady } from "../api/client";

function Badge({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span
      className={`rounded-full px-3 py-1 text-xs font-medium ${
        ok ? "bg-emerald-500/15 text-emerald-300" : "bg-amber-500/15 text-amber-300"
      }`}
    >
      {label}: {ok ? "ok" : "degraded"}
    </span>
  );
}

export function HealthPage() {
  const health = useQuery({ queryKey: ["health"], queryFn: fetchHealth });
  const ready = useQuery({ queryKey: ["ready"], queryFn: fetchReady });

  return (
    <div>
      <h1 className="text-2xl font-bold tracking-tight">Состояние сервиса</h1>
      <p className="mt-2 text-sm text-slate-400">
        Данные берутся из <code className="text-sky-300">/api/v1/health</code> и{" "}
        <code className="text-sky-300">/api/v1/health/ready</code>.
      </p>

      <div className="mt-6 flex flex-wrap items-center gap-3">
        <Badge ok={health.data?.status === "ok"} label="API" />
        <Badge ok={ready.data?.database === "ok"} label="БД" />
        {ready.data
          ? Object.entries(ready.data.providers).map(([name, ok]) => (
              <Badge key={name} ok={ok} label={name} />
            ))
          : null}
      </div>

      {health.isError || ready.isError ? (
        <p className="mt-6 rounded-lg border border-amber-600/40 bg-amber-500/10 p-3 text-sm text-amber-200">
          Backend недоступен. Запустите API (<code>uvicorn app.main:app</code>) или весь стек через{" "}
          <code>docker compose up</code>.
        </p>
      ) : null}

      <pre className="mt-6 overflow-x-auto rounded-xl border border-slate-800 bg-slate-950 p-4 text-xs text-slate-300">
        {JSON.stringify(
          { health: health.data ?? null, ready: ready.data ?? null },
          null,
          2,
        )}
      </pre>
    </div>
  );
}
