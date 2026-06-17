import { Outlet } from 'react-router-dom';
import { Navbar } from './Navbar';

/** Shell for authenticated pages: persistent navbar + routed content. */
export function Layout() {
  return (
    <>
      <Navbar />
      <main>
        <Outlet />
      </main>
    </>
  );
}
