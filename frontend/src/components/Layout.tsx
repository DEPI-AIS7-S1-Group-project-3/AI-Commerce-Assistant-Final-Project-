import { useEffect } from "react";
import { Outlet, useLocation } from "react-router-dom";
import Navbar from "./Navbar";
import Footer from "./Footer";

function ScrollToTop() {
  const { pathname } = useLocation();
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);
  return null;
}

// Full-screen pages (the assistant chat) fill the viewport under the navbar and have no
// footer, so only their message list scrolls, like a chat app.
const FULL_SCREEN = new Set(["/assistant"]);

export default function Layout() {
  const full = FULL_SCREEN.has(useLocation().pathname);
  return (
    <div className={full ? "flex h-dvh flex-col" : "flex min-h-screen flex-col"}>
      <ScrollToTop />
      <Navbar />
      <main
        className={
          full
            ? "mx-auto flex min-h-0 w-full max-w-7xl flex-1 px-4 pb-3 pt-4 sm:px-6"
            : "mx-auto w-full max-w-7xl flex-1 px-4 py-8 sm:px-6"
        }
      >
        <Outlet />
      </main>
      {!full && <Footer />}
    </div>
  );
}