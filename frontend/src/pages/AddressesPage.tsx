import { useState } from "react";
import { Plus } from "lucide-react";
import { USE_MOCK } from "@/api/config";
import { useAddresses, useAddressMutations } from "@/hooks/useAddresses";
import { useI18n } from "@/lib/i18n";
import AddressForm from "@/components/AddressForm";
import AddressText from "@/components/AddressText";

export default function AddressesPage() {
  const { t } = useI18n();
  const { data, isLoading, isError, refetch } = useAddresses();
  const m = useAddressMutations();
  const [editing, setEditing] = useState<number | "new" | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<number | null>(null);

  if (USE_MOCK) return <p className="chip-neon">{t("addr.mockOnly")}</p>;

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <header className="flex items-end justify-between gap-4 border-b border-line pb-5">
        <h1 className="text-3xl">{t("addr.title")}</h1>
        {editing !== "new" && (
          <button type="button" className="btn-primary" onClick={() => setEditing("new")}>
            <Plus className="h-4 w-4" aria-hidden />
            {t("addr.add")}
          </button>
        )}
      </header>

      {editing === "new" && (
        <AddressForm
          onSubmit={async (d) => {
            await m.create.mutateAsync(d);
            setEditing(null);
          }}
          onCancel={() => setEditing(null)}
        />
      )}

      {isLoading && <p className="text-ink-soft">{t("cart.loading")}...</p>}
      {isError && (
        <div className="space-y-2">
          <p className="text-danger">{t("addr.loadErr")}</p>
          <button type="button" className="btn-dark" onClick={() => refetch()}>
            {t("products.retry")}
          </button>
        </div>
      )}
      {data && data.length === 0 && editing !== "new" && <p className="text-ink-soft">{t("addr.empty")}</p>}

      <ul className="space-y-4">
        {data?.map((a) =>
          editing === a.id ? (
            <li key={a.id}>
              <AddressForm
                initial={a}
                onSubmit={async (d) => {
                  await m.update.mutateAsync({ id: a.id, d });
                  setEditing(null);
                }}
                onCancel={() => setEditing(null)}
              />
            </li>
          ) : (
            <li key={a.id} className={`card flex flex-wrap items-start justify-between gap-4 p-5 ${a.is_default ? "border-accent" : ""}`}>
              <div className="space-y-2">
                {a.is_default && <span className="chip-neon">{t("addr.default")}</span>}
                <AddressText a={a} />
              </div>
              <div className="flex flex-wrap gap-2">
                {!a.is_default && (
                  <button type="button" className="btn-ghost !px-3 !py-2 text-xs" onClick={() => m.makeDefault.mutate(a.id)}>
                    {t("addr.makeDefault")}
                  </button>
                )}
                <button type="button" className="btn-ghost !px-3 !py-2 text-xs" onClick={() => setEditing(a.id)}>
                  {t("addr.edit")}
                </button>
                {confirmDelete === a.id ? (
                  <button
                    type="button"
                    className="btn !border-danger !px-3 !py-2 text-xs text-danger"
                    onClick={() => m.remove.mutate(a.id, { onSettled: () => setConfirmDelete(null) })}
                  >
                    {t("addr.confirmDelete")}
                  </button>
                ) : (
                  <button type="button" className="btn-ghost !px-3 !py-2 text-xs hover:!text-danger" onClick={() => setConfirmDelete(a.id)}>
                    {t("addr.delete")}
                  </button>
                )}
              </div>
            </li>
          ),
        )}
      </ul>
    </div>
  );
}
