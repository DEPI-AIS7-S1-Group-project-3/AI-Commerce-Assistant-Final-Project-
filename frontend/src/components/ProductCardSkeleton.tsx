export default function ProductCardSkeleton() {
  return (
    <div className="card animate-pulse overflow-hidden" aria-hidden>
      <div className="aspect-square bg-sand" />
      <div className="space-y-3 p-4">
        <div className="h-3 w-16 rounded bg-sand" />
        <div className="h-4 w-full rounded bg-sand" />
        <div className="h-4 w-2/3 rounded bg-sand" />
        <div className="h-6 w-28 rounded bg-sand" />
        <div className="h-10 w-full rounded-ctl bg-sand" />
      </div>
    </div>
  );
}
