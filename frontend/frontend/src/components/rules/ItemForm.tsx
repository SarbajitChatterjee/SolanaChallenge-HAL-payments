import { useEffect, useState } from "react";

import { PillButton } from "@/components/ab/PillButton";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { api, type ItemCreate, type ItemPatch, type RuleItem } from "@/lib/api";
import { useSettings } from "@/lib/settings";

import { Field, UsdcInput, handleRulesError, inputClass, type FieldErrors } from "./shared";

type Values = {
  tool: string;
  name: string;
  vendor: string;
  url: string;
  price: string;
  description: string;
};
const empty: Values = { tool: "", name: "", vendor: "", url: "", price: "", description: "" };

function fromItem(item: RuleItem): Values {
  return {
    tool: item.tool,
    name: item.name,
    vendor: item.vendor,
    url: item.url,
    price: item.price,
    description: item.description ?? "",
  };
}

export function ItemForm({
  open,
  onOpenChange,
  item,
  onSaved,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  item: RuleItem | null;
  onSaved: () => void;
}) {
  const { config } = useSettings();
  const [values, setValues] = useState<Values>(empty);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (open) {
      setValues(item ? fromItem(item) : empty);
      setErrors({});
    }
  }, [open, item]);

  const set = (key: keyof Values, value: string) =>
    setValues((current) => ({ ...current, [key]: value }));

  async function save() {
    setBusy(true);
    setErrors({});
    try {
      if (item) {
        const original = fromItem(item);
        const patch: ItemPatch = {};
        if (values.name !== original.name) patch.name = values.name.trim();
        if (values.vendor !== original.vendor) patch.vendor = values.vendor.trim();
        if (values.url !== original.url) patch.url = values.url.trim();
        if (
          values.price.trim() !== original.price &&
          Number(values.price) !== Number(original.price)
        )
          patch.price = values.price.trim();
        if (values.description !== original.description) patch.description = values.description;
        if (Object.keys(patch).length > 0) await api.updateItem(config, item.tool, patch);
      } else {
        const body: ItemCreate = {
          tool: values.tool.trim(),
          name: values.name.trim(),
          vendor: values.vendor.trim(),
          url: values.url.trim(),
          price: values.price.trim(),
        };
        if (values.description.trim()) body.description = values.description.trim();
        await api.createItem(config, body);
      }
      onSaved();
      onOpenChange(false);
    } catch (error) {
      handleRulesError(error, setErrors);
    } finally {
      setBusy(false);
    }
  }

  const text = (key: keyof Values, label: string, help?: string) => (
    <Field id={`item-${key}`} label={label} {...(help ? { help } : {})} error={errors[key]}>
      <input
        id={`item-${key}`}
        required={key !== "description"}
        value={values[key]}
        onChange={(event) => set(key, event.target.value)}
        className={inputClass}
        autoComplete="off"
      />
    </Field>
  );

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full overflow-y-auto bg-[var(--card)] sm:max-w-md">
        <SheetHeader>
          <SheetTitle className="font-display text-2xl">
            {item ? `Edit ${item.name}` : "Add item"}
          </SheetTitle>
          <SheetDescription>Changes apply to the next purchase.</SheetDescription>
        </SheetHeader>
        <form
          className="mt-4 space-y-5 px-4 pb-6"
          onSubmit={(event) => {
            event.preventDefault();
            void save();
          }}
        >
          {item
            ? null
            : text(
                "tool",
                "Item id",
                "Lowercase letters, digits and underscores, e.g. weather_lookup",
              )}
          {text("name", "Name")}
          {text("vendor", "Seller")}
          {text("url", "Address", "The seller's full https:// address for this item")}
          <Field
            id="item-price"
            label="Agreed price (USDC)"
            help="The most this seller can charge. If they ask for more, nothing is paid."
            error={errors["price"]}
          >
            <UsdcInput id="item-price" value={values.price} onChange={(v) => set("price", v)} />
          </Field>
          <Field id="item-description" label="Description" error={errors["description"]}>
            <textarea
              id="item-description"
              rows={2}
              value={values.description}
              onChange={(event) => set("description", event.target.value)}
              className={inputClass}
            />
          </Field>
          <div className="flex gap-2">
            <PillButton type="submit" variant="primary" disabled={busy}>
              Save
            </PillButton>
            <PillButton type="button" onClick={() => onOpenChange(false)}>
              Cancel
            </PillButton>
          </div>
        </form>
      </SheetContent>
    </Sheet>
  );
}
