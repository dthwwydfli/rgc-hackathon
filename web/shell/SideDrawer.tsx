import { X } from "lucide-react";
import { cn } from "../lib/cn";

export type ScreenId = "swimlanes" | "whatif";

interface SideDrawerProps {
  open: boolean;
  activeScreen: ScreenId;
  onClose: () => void;
  onNavigate: (screen: ScreenId) => void;
}

const NAV_ITEMS: Array<{ id: ScreenId; label: string }> = [
  { id: "swimlanes", label: "Moments" },
  { id: "whatif", label: "What-if" },
];
export function SideDrawer({ open, activeScreen, onClose, onNavigate }: SideDrawerProps) {
  return (
    <>
      <div
        className={cn(
          "fixed inset-0 z-40 bg-black/30 transition-opacity",
          open ? "opacity-100" : "pointer-events-none opacity-0",
        )}
        aria-hidden={!open}
        onClick={onClose}
      />
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex w-72 flex-col bg-[var(--bg)] shadow-xl transition-transform duration-200",
          open ? "translate-x-0" : "-translate-x-full",
        )}
        aria-label="Main menu"
        aria-hidden={!open}
      >
        <div className="flex h-16 items-center gap-1 border-b border-[var(--line)] px-2">
          <button
            type="button"
            onClick={onClose}
            aria-label="Close menu"
            className="inline-flex h-12 w-12 items-center justify-center rounded-full text-[var(--ink)] hover:bg-black/5"
          >
            <X size={22} aria-hidden="true" />
          </button>
          <span className="font-[family-name:var(--font-display)] text-lg tracking-tight text-[var(--ink)]">
            Moments
          </span>
        </div>

        <nav className="flex flex-col gap-1 p-3" aria-label="Screens">
          {NAV_ITEMS.map((item) => {
            const isActive = activeScreen === item.id;
            return (
              <button
                key={item.id}
                type="button"
                aria-selected={isActive}
                onClick={() => {
                  onNavigate(item.id);
                  onClose();
                }}
                className={cn(
                  "rounded-full px-4 py-2.5 text-left text-sm font-medium",
                  isActive
                    ? "bg-[var(--action-lime)] text-[var(--ink)]"
                    : "text-[var(--ink)] hover:bg-black/5",
                )}
              >
                {item.label}
              </button>
            );
          })}
        </nav>
      </aside>
    </>
  );
}
