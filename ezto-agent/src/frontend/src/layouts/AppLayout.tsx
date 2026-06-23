import { Outlet } from "react-router-dom";
import ProjectSidebar from "../components/ProjectSidebar";
import { ProjectListProvider } from "../contexts/ProjectListContext";

export default function AppLayout() {
  return (
    <ProjectListProvider>
      <div className="app-shell">
        <ProjectSidebar />
        <main className="app-main">
          <Outlet />
        </main>
      </div>
    </ProjectListProvider>
  );
}
