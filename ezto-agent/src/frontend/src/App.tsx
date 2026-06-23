import { Routes, Route, Navigate } from "react-router-dom";
import AppLayout from "./layouts/AppLayout";
import HomePage from "./pages/HomePage";
import NewProjectPage from "./pages/NewProjectPage";
import WorkflowPage from "./pages/WorkflowPage";
import ProjectPage from "./pages/ProjectPage";

export default function App() {
  return (
    <div className="app">
      <Routes>
        <Route element={<AppLayout />}>
          <Route path="/" element={<HomePage />} />
          <Route path="/new" element={<NewProjectPage />} />
          <Route path="/project/:id" element={<ProjectPage />} />
          <Route path="/workflow/:id/*" element={<WorkflowPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </div>
  );
}
