
type Deal = {
  id: number;
  origin: string;
  destination: string;
  price: number;
  normal_price: number;
  discount_percent: number;
  airline: string;
  departure_date: string;
  return_date: string;
  cabin_class: string;
  deal_score: number;
  feed_score: number;
  quality_factors_json?: Record<string, number>;
  created_at: string;
};

async function getDeals(): Promise<Deal[]> {
  const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  const res = await fetch(`${baseUrl}/deals?sort_by=feed_score`, { cache: "no-store" });
  if (!res.ok) return [];
  return res.json();
}

export default async function HomePage() {
  const deals = await getDeals();

  return (
    <section className="space-y-6">
      <div className="card">
        <p className="mb-2 text-sm uppercase tracking-[0.2em] text-white/60">Rare flight deals</p>
        <h1 className="mb-2 text-4xl font-semibold">Top deals from your airports</h1>
        <p className="text-white/70">The feed now ranks deals by feed score, freshness, discount size, and premium-cabin bonuses.</p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {deals.length === 0 ? (
          <div className="card">No deals yet. Start the worker to seed scan results.</div>
        ) : deals.map((deal) => (
          <article key={deal.id} className="card">
            <div className="mb-3 flex items-center justify-between">
              <span className="badge">{deal.discount_percent}% off</span>
              <span className="text-sm text-white/50">Feed {deal.feed_score}</span>
            </div>
            <h2 className="text-2xl font-semibold">{deal.origin} → {deal.destination}</h2>
            <p className="mt-3 text-3xl font-bold">${deal.price}</p>
            <p className="text-white/70">Normally ${deal.normal_price}</p>
            <div className="mt-4 space-y-1 text-sm text-white/80">
              <p>Airline: {deal.airline}</p>
              <p>Cabin: {deal.cabin_class}</p>
              <p>Dates: {deal.departure_date} → {deal.return_date}</p>
              <p>Deal score: {deal.deal_score}</p>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
