
type Overview = {
  queued_jobs: number;
  running_jobs: number;
  failed_jobs_24h: number;
  candidate_deals: number;
  validated_deals: number;
  active_alerts: number;
  notifications_sent_24h: number;
};

type ProviderHealth = {
  provider: string;
  ok_events: number;
  failed_events: number;
  last_status: string | null;
  last_error_message: string | null;
  avg_latency_ms: number | null;
  last_event_at: string | null;
};

async function getJson<T>(path: string): Promise<T | null> {
  const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  const res = await fetch(`${baseUrl}${path}`, { cache: "no-store" });
  if (!res.ok) return null;
  return res.json();
}

export default async function AdminPage() {
  const [overview, providers] = await Promise.all([
    getJson<Overview>("/admin/overview"),
    getJson<ProviderHealth[]>("/admin/provider-health"),
  ]);

  return (
    <section className="space-y-6">
      <div className="card">
        <h1 className="mb-2 text-3xl font-semibold">Ops dashboard</h1>
        <p className="text-white/70">A lightweight internal view for queue health, provider health, and deal funnel quality.</p>
      </div>

      {overview && (
        <div className="grid gap-4 md:grid-cols-3">
          {Object.entries(overview).map(([key, value]) => (
            <div key={key} className="card">
              <p className="text-sm uppercase tracking-[0.2em] text-white/50">{key.replaceAll("_", " ")}</p>
              <p className="mt-2 text-3xl font-bold">{value}</p>
            </div>
          ))}
        </div>
      )}

      <div className="card">
        <h2 className="mb-4 text-2xl font-semibold">Provider health</h2>
        <div className="grid gap-4 md:grid-cols-3">
          {(providers || []).map((provider) => (
            <article key={provider.provider} className="rounded-2xl border border-white/10 bg-black/20 p-4">
              <h3 className="text-xl font-semibold">{provider.provider}</h3>
              <p className="mt-2 text-white/70">OK events: {provider.ok_events}</p>
              <p className="text-white/70">Failed events: {provider.failed_events}</p>
              <p className="text-white/70">Avg latency: {provider.avg_latency_ms ?? "n/a"} ms</p>
              <p className="text-white/70">Last status: {provider.last_status ?? "n/a"}</p>
              {provider.last_error_message && (
                <p className="mt-2 text-sm text-amber-300">{provider.last_error_message}</p>
              )}
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
