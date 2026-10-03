import { useState } from "react";
import { SideDrawer } from "./shell/SideDrawer";
import { SwimlanesScreen } from "./swimlanes/SwimlanesScreen";

export function App() {
  const [drawerOpen, setDrawerOpen] = useState(false);

  return (
    <div className="flex h-full flex-col bg-white">
      <SideDrawer
        open={drawerOpen}
        activeScreen="swimlanes"
        onClose={() => setDrawerOpen(false)}
        onNavigate={() => setDrawerOpen(false)}
      />
      <SwimlanesScreen
        onToggleDrawer={() => setDrawerOpen((open) => !open)}
      />
    </div>
  );
}
